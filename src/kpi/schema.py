"""여러 분석(SimPy 라인, ML 모델, 정비이력 계산)의 결과를 하나의 형식으로 강제하는 계약.

왜 필요한가: 각 분석이 서로 다른 컬럼명·단위로 결과를 내면 대시보드가 분석 개수만큼
개별 처리 코드를 가져야 하고, 값의 단위 실수(예: 98 vs 0.98)를 아무도 못 잡는다.
이 파일은 "KPI 하나 = 표준 행 하나"를 강제해서 그 문제를 원천 차단한다.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# 컬럼명 -> pandas dtype. append_kpi()에서 저장 전에 이 순서/타입으로 맞춘다.
KPI_SCHEMA: dict[str, str] = {
    "scenario_id": "object",
    "source": "object",
    "process": "object",
    "kpi_name": "object",
    "kpi_value": "float64",
    "unit": "object",
    "ci_low": "float64",
    "ci_high": "float64",
    "run_id": "object",
    "timestamp": "datetime64[ns]",
}

# 이 목록에 없는 kpi_name은 오타이거나 계약 밖의 값이라고 간주하고 막는다.
ALLOWED_KPIS: set[str] = {
    "availability", "performance", "quality", "oee", "uph", "tact_time",
    "cycle_time", "line_efficiency", "mtbf", "mttr", "defect_ppm", "ftt",
    "makespan", "station_count", "bottleneck_ct", "recall", "precision",
    "pr_auc", "total_cost",
}

# 0~1 비율(ratio)로 표현되어야 하는 KPI들 — 이 목록에 있는데 값이 0~1 밖이면
# "98(%)를 0.98(비율)로 착각해서 넣었나?" 같은 실수를 여기서 잡는다.
RATIO_KPIS: set[str] = {"availability", "performance", "quality", "oee", "ftt", "line_efficiency", "recall", "precision", "pr_auc"}


def validate_kpi(df: pd.DataFrame) -> None:
    """스키마 위반을 찾으면 명확한 메시지와 함께 예외를 던진다. 통과하면 아무것도 반환하지 않는다."""

    # 1) 컬럼 누락 체크
    missing_cols = set(KPI_SCHEMA) - set(df.columns)
    if missing_cols:
        raise ValueError(f"[스키마 위반] 컬럼 누락: {sorted(missing_cols)}")

    # 2) dtype 체크 — object(str)은 실제로는 str이 들어있는지까지 확인
    for col, expected_dtype in KPI_SCHEMA.items():
        actual = df[col].dtype
        if expected_dtype == "float64" and not pd.api.types.is_float_dtype(actual):
            raise ValueError(f"[스키마 위반] '{col}'은 float64여야 하는데 {actual}임")
        if expected_dtype == "datetime64[ns]" and not pd.api.types.is_datetime64_any_dtype(actual):
            raise ValueError(f"[스키마 위반] '{col}'은 datetime64여야 하는데 {actual}임")
        if expected_dtype == "object" and not (
            pd.api.types.is_object_dtype(actual) or pd.api.types.is_string_dtype(actual)
        ):
            # pandas 3.0부터 문자열 컬럼 기본 dtype이 object가 아니라 전용 StringDtype일 수 있어
            # 둘 다 허용한다 (버전에 따라 달라지는 걸 여기서 흡수).
            raise ValueError(f"[스키마 위반] '{col}'은 문자열이어야 하는데 {actual}임")

    # 3) kpi_name이 허용 목록에 있는지
    unknown_kpis = set(df["kpi_name"]) - ALLOWED_KPIS
    if unknown_kpis:
        raise ValueError(f"[스키마 위반] 허용되지 않은 kpi_name: {sorted(unknown_kpis)} (ALLOWED_KPIS 참고)")

    # 4) 비율 단위 KPI는 값이 0~1 범위여야 함 (98 vs 0.98 실수 방지)
    ratio_rows = df[df["kpi_name"].isin(RATIO_KPIS)]
    out_of_range = ratio_rows[(ratio_rows["kpi_value"] < 0) | (ratio_rows["kpi_value"] > 1)]
    if not out_of_range.empty:
        bad = out_of_range[["kpi_name", "kpi_value"]].to_dict("records")
        raise ValueError(f"[스키마 위반] 비율 KPI인데 값이 0~1 범위 밖: {bad} (98을 0.98로 착각했는지 확인)")

    # 5) 신뢰구간 정합성: ci_low가 ci_high보다 크면 안 됨 (NaN인 행은 신뢰구간 미계산으로 간주하고 건너뜀)
    ci_rows = df.dropna(subset=["ci_low", "ci_high"])
    invalid_ci = ci_rows[ci_rows["ci_low"] > ci_rows["ci_high"]]
    if not invalid_ci.empty:
        raise ValueError(f"[스키마 위반] ci_low > ci_high인 행 발견:\n{invalid_ci[['kpi_name', 'ci_low', 'ci_high']]}")


def append_kpi(df: pd.DataFrame, path: Path) -> None:
    """검증을 통과한 경우에만 parquet에 append한다. 실패하면 파일에 아무것도 쓰지 않는다.

    같은 (scenario_id, source, process, kpi_name) 조합이 이미 있으면 새 값으로 덮어쓴다
    (keep="last") — 그렇지 않으면 같은 스크립트를 재실행할 때마다 중복이 쌓인다
    (2026-09-08 TROUBLESHOOTING 참고: 검증 실행 + 사용자 실행으로 kpi.parquet에 중복 발생).
    """
    validate_kpi(df)  # 여기서 실패하면 예외가 위로 던져지고 아래 저장 코드는 실행되지 않음

    path = Path(path)
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined = combined.drop_duplicates(
        subset=["scenario_id", "source", "process", "kpi_name"], keep="last"
    ).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
