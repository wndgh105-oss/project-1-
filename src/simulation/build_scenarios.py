"""시나리오 그리드를 미리 다 돌려서 대시보드용 캐시(scenario_grid.parquet)를 만든다.

왜 필요한가: 대시보드에서 슬라이더를 움직일 때마다 몬테카를로 30회를 즉석에서 돌리면
느리다. 자주 쓰일 조합을 미리 계산해두면 대시보드는 조회만 하면 된다(STEP 11의
하이브리드 구조 — 캐시에 있으면 즉시 조회, 없으면 실시간 계산 — 의 캐시 쪽 절반).

그리드: buffer_cap × pm_interval = 6 × 5 = 30개 조합, 각 조합마다 몬테카를로 30회.
buffer_cap 값은 5개 버퍼(B1~B4) 전부에 동일하게 적용한다(개별 버퍼 크기를 다르게
튜닝하는 것은 이 프로젝트 범위 밖).
"""
import time
from itertools import product
from pathlib import Path

import pandas as pd

from src.simulation.line_sim import BUFFER_KEYS
from src.simulation.monte_carlo import run_monte_carlo

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

BUFFER_CAP_GRID = [0, 2, 5, 10, 15, 20]
PM_INTERVAL_GRID = [0, 200, 400, 800, 1600]
PM_DURATION = 30.0  # 분 — PM 1회 소요시간 (설계 가정치, 원래 STEP6 데모와 동일하게 고정)
N_RUNS_PER_SCENARIO = 30


def build_scenario_grid() -> pd.DataFrame:
    combos = list(product(BUFFER_CAP_GRID, PM_INTERVAL_GRID))
    total = len(combos)
    results = []

    t_start = time.time()
    for i, (buffer_cap, pm_interval) in enumerate(combos, start=1):
        scenario_id = f"buf{buffer_cap}_pm{pm_interval}"
        buffer_caps = {k: buffer_cap for k in BUFFER_KEYS}
        mc = run_monte_carlo(
            n_runs=N_RUNS_PER_SCENARIO,
            base_seed=42,
            buffer_caps=buffer_caps,
            pm_interval=pm_interval,
            pm_duration=PM_DURATION if pm_interval > 0 else 0.0,
            scenario_id=scenario_id,
        )
        mc["buffer_cap"] = buffer_cap
        mc["pm_interval"] = pm_interval
        results.append(mc)
        print(f"[{i}/{total}] {scenario_id} 완료 (경과 {time.time() - t_start:.1f}초)")

    elapsed = time.time() - t_start
    print(f"\n전체 {total}개 시나리오 x {N_RUNS_PER_SCENARIO}회 몬테카를로 소요시간: {elapsed:.1f}초")
    if elapsed > 600:
        print("경고: 총 소요시간이 10분을 넘었습니다 — 그리드 축소 또는 joblib.Parallel 병렬화를 검토해야 합니다.")

    grid = pd.concat(results, ignore_index=True)
    out_path = PROCESSED / "scenario_grid.parquet"
    grid.to_parquet(out_path, index=False)
    print(f"저장: {out_path.relative_to(ROOT)} ({len(grid)}행)")

    # 그리드의 기본 조합(buffer_cap=5, pm_interval=0)을 "base" 시나리오로 kpi.parquet에도
    # 남겨서, 대시보드 종합 탭이 kpi.parquet 하나만 보고도 대표 OEE/A/P/Q를 보여줄 수 있게 한다.
    from src.kpi.schema import append_kpi
    base_rows = grid[(grid["buffer_cap"] == 5) & (grid["pm_interval"] == 0)].drop(columns=["buffer_cap", "pm_interval"]).copy()
    base_rows["scenario_id"] = "base"
    append_kpi(base_rows, PROCESSED / "kpi.parquet")
    print(f"저장: kpi.parquet에 base 시나리오 {len(base_rows)}행 반영")

    return grid


def summarize(grid: pd.DataFrame) -> None:
    oee = grid[grid["kpi_name"] == "oee"][["scenario_id", "buffer_cap", "pm_interval", "kpi_value", "ci_low", "ci_high"]]

    print("\n=== OEE 상위 5개 시나리오 ===")
    print(oee.nlargest(5, "kpi_value").to_string(index=False))

    print("\n=== PM 없음(pm_interval=0) 조건에서 버퍼 크기별 OEE ===")
    no_pm = oee[oee["pm_interval"] == 0].sort_values("buffer_cap")
    print(no_pm[["buffer_cap", "kpi_value", "ci_low", "ci_high"]].to_string(index=False))
    diffs = no_pm["kpi_value"].diff()
    print("\n버퍼를 한 단계씩 늘렸을 때 OEE 개선폭:")
    print(pd.DataFrame({"buffer_cap": no_pm["buffer_cap"].values, "oee_delta": diffs.values}).to_string(index=False))

    print("\n=== buffer_cap=5 고정, PM 주기별 Availability ===")
    avail = grid[(grid["kpi_name"] == "availability") & (grid["buffer_cap"] == 5)][["pm_interval", "kpi_value"]].sort_values("pm_interval")
    print(avail.to_string(index=False))


if __name__ == "__main__":
    grid = build_scenario_grid()
    summarize(grid)
