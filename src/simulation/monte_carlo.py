"""몬테카를로 반복 실행 — 1회 시뮬레이션의 표본 변동 문제를 극복한다.

왜 필요한가: STEP 6에서 실제로 확인했듯(TROUBLESHOOTING.md 2026-09-08),
같은 파라미터라도 시드 하나로 딱 1회만 돌리면 "실제 경향"과 "우연히 그렇게 나온 것"을
구분할 수 없다. 여러 시드로 반복해서 평균과 신뢰구간을 같이 봐야 한다.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.simulation.line_sim import run_line

ROOT = Path(__file__).resolve().parents[2]


def run_monte_carlo_raw(n_runs: int = 30, base_seed: int = 42, **line_kwargs) -> pd.DataFrame:
    """run_line()을 n_runs회 반복해 개별 실행 결과를 전부 이어붙여 반환한다(집계하지 않음).

    fig_monte_carlo 같은 분포 히스토그램을 그리려면 평균만으론 부족하고 실행마다의
    개별 값이 필요해서 별도로 뺐다. run_monte_carlo()도 내부적으로 이 함수를 재사용한다.
    """
    scenario_id = line_kwargs.pop("scenario_id", "base")
    all_runs = []
    for i in range(n_runs):
        df_i = run_line(seed=base_seed + i, scenario_id=scenario_id, **line_kwargs)
        df_i["_run_idx"] = i
        all_runs.append(df_i)
    return pd.concat(all_runs, ignore_index=True)


def run_monte_carlo(n_runs: int = 30, base_seed: int = 42, confidence: float = 0.95, **line_kwargs) -> pd.DataFrame:
    """run_line()을 seed=base_seed, base_seed+1, ..., base_seed+n_runs-1로 n_runs회 반복하고,
    (process, kpi_name)별 평균·95% 신뢰구간(t분포)을 계산해 KPI_SCHEMA 형식으로 반환한다.

    한 그룹(같은 process+kpi_name)의 표준편차가 0이면(예: mtbf/mttr처럼 입력 그대로인 값)
    신뢰구간을 mean=ci_low=ci_high로 둔다 — 변동이 없는 값에 억지로 구간을 만들지 않는다.
    """
    scenario_id = line_kwargs.get("scenario_id", "base")
    combined = run_monte_carlo_raw(n_runs=n_runs, base_seed=base_seed, **line_kwargs)

    rows = []
    for (process, kpi_name), group in combined.groupby(["process", "kpi_name"]):
        values = group["kpi_value"].to_numpy()
        mean = values.mean()
        std = values.std(ddof=1) if len(values) > 1 else 0.0
        if std == 0 or len(values) < 2:
            ci_low, ci_high = mean, mean
        else:
            se = std / np.sqrt(len(values))
            margin = stats.t.ppf((1 + confidence) / 2, df=len(values) - 1) * se
            ci_low, ci_high = mean - margin, mean + margin
        rows.append({
            "process": process, "kpi_name": kpi_name, "kpi_value": mean,
            "unit": group["unit"].iloc[0], "ci_low": ci_low, "ci_high": ci_high,
        })

    result = pd.DataFrame(rows)
    result["scenario_id"] = scenario_id
    result["source"] = "line_sim_mc"
    result["run_id"] = f"mc_base{base_seed}_n{n_runs}"
    result["timestamp"] = pd.Timestamp.now()
    ordered_cols = ["scenario_id", "source", "process", "kpi_name", "kpi_value", "unit", "ci_low", "ci_high", "run_id", "timestamp"]
    return result[ordered_cols]


def compare_ci_width(kpi_name: str = "oee", process: str | None = None, n_runs_list=(5, 10, 30, 50), base_seed: int = 42, **line_kwargs) -> pd.DataFrame:
    """n_runs를 바꿔가며 지정한 kpi_name의 신뢰구간 폭이 어떻게 줄어드는지 비교표를 만든다.
    "몇 회가 충분한가"를 실제 숫자(폭이 평균 대비 몇 %인지)로 판단하기 위한 근거 표.
    """
    rows = []
    for n in n_runs_list:
        mc = run_monte_carlo(n_runs=n, base_seed=base_seed, **line_kwargs)
        target = mc[mc["kpi_name"] == kpi_name]
        if process is not None:
            target = target[target["process"] == process]
        if target.empty:
            continue
        row = target.iloc[0]
        width = row["ci_high"] - row["ci_low"]
        rows.append({
            "n_runs": n, "mean": row["kpi_value"], "ci_low": row["ci_low"],
            "ci_high": row["ci_high"], "ci_width": width,
            "ci_width_pct_of_mean": (width / row["kpi_value"] * 100) if row["kpi_value"] else float("nan"),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("=== 몬테카를로 30회 — 기본 8시간 시나리오 ===")
    mc_short = run_monte_carlo(n_runs=30, base_seed=42)
    print(mc_short[mc_short["kpi_name"].isin(["availability", "performance", "quality", "oee", "uph"])].to_string(index=False))
    print("\n(참고: 8시간 안에는 고장이 거의 안 일어나서 위 신뢰구간 폭이 매우 좁게 나올 수 있음 —")
    print(" 아래 장기 시나리오에서 변동을 더 뚜렷하게 볼 수 있다.)")

    print("\n=== n_runs별 OEE 신뢰구간 폭 비교 (장기 시나리오: 열처리 MTBF와 동일한 기간) ===")
    from src.simulation.line_sim import DEFAULT_MTBF_HOURS
    long_sim_time = DEFAULT_MTBF_HOURS["열처리"] * 60  # 시간 -> 분, 약 1 MTBF 기간
    comparison = compare_ci_width(kpi_name="oee", process="열처리", n_runs_list=(5, 10, 30, 50), sim_time=long_sim_time)
    print(f"(sim_time = {long_sim_time:.0f}분 ≈ {long_sim_time / 60 / 24:.0f}일)")
    print(comparison.to_string(index=False))
