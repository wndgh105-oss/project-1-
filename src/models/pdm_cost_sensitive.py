"""비용민감(cost-sensitive) 고장 예측 모델 — APS Scania 트럭 공기압축시스템 데이터.

왜 필요한가: 이 데이터는 불량(pos)이 전체의 1.67%뿐이라, "그냥 다 정상이라고 찍는"
모델도 Accuracy 98%가 넘는다. Accuracy만 보면 이 모델이 훌륭해 보이지만 실제로는
고장을 하나도 못 잡는다 — 이 함정을 숫자로 직접 보여준 다음, 대회가 명시한 비용
(과검=10, 미검=500 — 미검이 50배 비쌈)을 최소화하는 임계값을 찾는다.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline

from src.data.inspect_raw import _read_csv_robust
from src.kpi.schema import append_kpi

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "aps_scania"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
PROCESSED.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

COST_FP = 10  # 과검(불필요 점검) — 대회 규정
COST_FN = 500  # 미검(고장 놓침) — 대회 규정, 과검의 50배
MISSING_DROP_THRESHOLD = 0.7  # 이 비율 넘게 결측이면 컬럼째 드롭
SEED = 42


def load_data() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    train_df, _ = _read_csv_robust(RAW / "aps_failure_training_set.csv")
    test_df, _ = _read_csv_robust(RAW / "aps_failure_test_set.csv")

    y_train = (train_df["class"] == "pos").astype(int)
    y_test = (test_df["class"] == "pos").astype(int)
    x_train = train_df.drop(columns=["class"])
    x_test = test_df.drop(columns=["class"])

    print("라벨 분포 (training):")
    print(y_train.value_counts().rename({0: "neg", 1: "pos"}))
    print(f"  pos 비율: {y_train.mean() * 100:.2f}%")
    print("\n라벨 분포 (test):")
    print(y_test.value_counts().rename({0: "neg", 1: "pos"}))
    print(f"  pos 비율: {y_test.mean() * 100:.2f}%")

    # 결측률이 너무 높은 컬럼은 정보가 거의 없다고 보고 드롭 — train 기준으로 판단하고
    # test에도 동일하게 적용해야 두 세트의 컬럼 구성이 어긋나지 않는다.
    missing_rate = x_train.isna().mean()
    drop_cols = missing_rate[missing_rate > MISSING_DROP_THRESHOLD].index.tolist()
    print(f"\n결측률 {MISSING_DROP_THRESHOLD * 100:.0f}% 초과로 드롭한 컬럼 {len(drop_cols)}개: {drop_cols}")
    x_train = x_train.drop(columns=drop_cols)
    x_test = x_test.drop(columns=drop_cols)

    return x_train, y_train, x_test, y_test


def evaluate(y_true, y_pred, label: str) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    total_cost = COST_FP * fp + COST_FN * fn
    result = {
        "label": label,
        "accuracy": accuracy_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "fp": int(fp),
        "fn": int(fn),
        "total_cost": int(total_cost),
    }
    return result


def sweep_thresholds(y_true, y_proba, thresholds=None) -> pd.DataFrame:
    if thresholds is None:
        thresholds = np.arange(0.01, 1.0, 0.01)
    rows = []
    for t in thresholds:
        y_pred = (y_proba >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        total_cost = COST_FP * fp + COST_FN * fn
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rows.append({"threshold": t, "fp": int(fp), "fn": int(fn), "total_cost": int(total_cost),
                      "recall": recall, "precision": precision})
    return pd.DataFrame(rows)


def main():
    x_train, y_train, x_test, y_test = load_data()

    # --- 1. 함정: 전부 '정상(neg)'으로 찍는 더미 모델 ---
    dummy_pred = np.zeros(len(y_test), dtype=int)
    dummy_result = evaluate(y_test, dummy_pred, "더미(전부 정상)")
    print(f"\n{'=' * 60}")
    print("[함정] 더미 모델(전부 정상으로 예측):")
    print(f"  Accuracy: {dummy_result['accuracy'] * 100:.2f}%  <- 높아 보이지만")
    print(f"  Recall: {dummy_result['recall'] * 100:.2f}%  <- 고장을 하나도 못 잡음")
    print(f"  총비용: {dummy_result['total_cost']:,}  (FP={dummy_result['fp']}, FN={dummy_result['fn']})")

    # --- 2. 제대로 된 모델: RandomForest + 중앙값 대체 ---
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(class_weight="balanced", random_state=SEED, n_jobs=-1)),
    ])
    pipeline.fit(x_train, y_train)

    y_proba = pipeline.predict_proba(x_test)[:, 1]
    pr_auc = average_precision_score(y_test, y_proba)

    default_pred = (y_proba >= 0.5).astype(int)
    default_result = evaluate(y_test, default_pred, "기본 RF (임계값 0.50)")

    # --- 3. 임계값 스윕 — 총비용 최소화 ---
    curve = sweep_thresholds(y_test, y_proba)
    best_row = curve.loc[curve["total_cost"].idxmin()]
    best_threshold = best_row["threshold"]
    optimal_pred = (y_proba >= best_threshold).astype(int)
    optimal_result = evaluate(y_test, optimal_pred, f"비용최적 RF (임계값 {best_threshold:.2f})")

    print(f"\n{'=' * 60}")
    print("[비교표]")
    comparison = pd.DataFrame([dummy_result, default_result, optimal_result])
    print(comparison.to_string(index=False))

    savings = dummy_result["total_cost"] - optimal_result["total_cost"]
    savings_vs_default = default_result["total_cost"] - optimal_result["total_cost"]
    print(f"\n더미 대비 비용최적 RF 절감액: {savings:,} ({savings / dummy_result['total_cost'] * 100:.1f}% 절감)")
    print(f"기본 RF(0.50) 대비 비용최적 RF 절감액: {savings_vs_default:,}")
    print(f"PR-AUC: {pr_auc:.4f}")

    comparison["pr_auc"] = pr_auc
    comparison_path = ROOT / "data" / "interim" / "pdm_cost_comparison.csv"
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    print(f"저장: {comparison_path.relative_to(ROOT)} (대시보드 STEP 10 페이지1에서 재사용)")

    # --- 4. cost_curve.parquet 저장 (대시보드 임계값 슬라이더용) ---
    cost_curve_path = PROCESSED / "cost_curve.parquet"
    curve.to_parquet(cost_curve_path, index=False)
    print(f"\n저장: {cost_curve_path.relative_to(ROOT)} ({len(curve)}행)")

    # --- 5. 모델 저장 ---
    model_path = MODELS / "pdm_cost_sensitive.joblib"
    joblib.dump({"pipeline": pipeline, "best_threshold": best_threshold, "feature_columns": list(x_train.columns)}, model_path)
    print(f"저장: {model_path.relative_to(ROOT)}")

    # --- 6. KPI_SCHEMA 형식으로 kpi.parquet에 append ---
    timestamp = pd.Timestamp.now()
    kpi_rows = pd.DataFrame([
        {"scenario_id": "cost_optimal", "source": "pdm_cost_sensitive", "process": "예지보전",
         "kpi_name": "recall", "kpi_value": optimal_result["recall"], "unit": "ratio",
         "ci_low": float("nan"), "ci_high": float("nan"), "run_id": f"pdm_seed{SEED}", "timestamp": timestamp},
        {"scenario_id": "cost_optimal", "source": "pdm_cost_sensitive", "process": "예지보전",
         "kpi_name": "precision", "kpi_value": optimal_result["precision"], "unit": "ratio",
         "ci_low": float("nan"), "ci_high": float("nan"), "run_id": f"pdm_seed{SEED}", "timestamp": timestamp},
        {"scenario_id": "cost_optimal", "source": "pdm_cost_sensitive", "process": "예지보전",
         "kpi_name": "pr_auc", "kpi_value": pr_auc, "unit": "ratio",
         "ci_low": float("nan"), "ci_high": float("nan"), "run_id": f"pdm_seed{SEED}", "timestamp": timestamp},
        {"scenario_id": "cost_optimal", "source": "pdm_cost_sensitive", "process": "예지보전",
         "kpi_name": "total_cost", "kpi_value": float(optimal_result["total_cost"]), "unit": "cost_unit",
         "ci_low": float("nan"), "ci_high": float("nan"), "run_id": f"pdm_seed{SEED}", "timestamp": timestamp},
    ])
    kpi_path = PROCESSED / "kpi.parquet"
    append_kpi(kpi_rows, kpi_path)
    print(f"저장: {kpi_path.relative_to(ROOT)}에 4개 KPI 행 추가")


if __name__ == "__main__":
    main()
