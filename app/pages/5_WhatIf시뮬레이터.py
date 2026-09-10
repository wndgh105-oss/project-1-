"""Streamlit 페이지: What-if 디지털트윈 시뮬레이터 — 이 프로젝트의 핵심.

하이브리드 구조: 사전계산된 scenario_grid.parquet에 정확히 일치하는 (buffer_cap, pm_interval)
조합이 있으면 즉시 조회, 없으면 그 자리에서 몬테카를로를 돌린다. 실측을 위해 두 경로의
실제 응답시간을 화면과 콘솔에 그대로 기록한다(지어낸 비교 수치를 쓰지 않기 위함).
"""
import math
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.simulation.line_sim import BUFFER_KEYS, DEFAULT_CYCLE_TIMES  # noqa: E402
from src.simulation.monte_carlo import run_monte_carlo, run_monte_carlo_raw  # noqa: E402
from src.viz.fig_line import fig_yamazumi  # noqa: E402
from src.viz.fig_sim import fig_monte_carlo, fig_sensitivity  # noqa: E402

st.set_page_config(page_title="What-if 시뮬레이터", layout="wide")
st.title("What-if 디지털트윈 시뮬레이터")

PM_DURATION = 30.0  # build_scenarios.py와 동일한 설계 가정치


@st.cache_data
def load_scenario_grid() -> pd.DataFrame:
    path = ROOT / "data" / "processed" / "scenario_grid.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_base_kpi() -> dict:
    """기준(base) 시나리오(buffer=5, pm=0)의 대표 KPI — delta 비교 기준."""
    grid = load_scenario_grid()
    if grid.empty:
        return {}
    base = grid[(grid["buffer_cap"] == 5) & (grid["pm_interval"] == 0) & (grid["process"] == "열처리")]
    return dict(zip(base["kpi_name"], base["kpi_value"]))


grid_df = load_scenario_grid()
base_kpi = load_base_kpi()

st.sidebar.header("시뮬레이션 조건")
buffer_cap = st.sidebar.slider("버퍼 용량", min_value=0, max_value=20, value=5, step=1)
pm_interval = st.sidebar.slider("PM 주기 (분, 0=PM 없음)", min_value=0, max_value=2000, value=0, step=200)
target_tact = st.sidebar.slider("목표 Tact (초)", min_value=20, max_value=90, value=60, step=1)
mc_reps = st.sidebar.radio("몬테카를로 반복 횟수", [5, 10, 30], index=2, horizontal=True,
                            help="적을수록 빠르지만 신뢰구간이 넓어짐 (정확도 vs 속도)")
run_clicked = st.sidebar.button("시뮬레이션 실행", type="primary")

if "whatif_result" not in st.session_state:
    st.session_state.whatif_result = None

if run_clicked:
    buffer_caps = {k: buffer_cap for k in BUFFER_KEYS}

    # --- 하이브리드 조회: scenario_grid에 정확히 일치하는 조합이 있는지 먼저 확인 ---
    # elapsed(캐시/실시간 판단 표시용)는 "KPI 값을 얻기까지" 걸린 시간만 잰다.
    # 히스토그램용 개별 실행값 재생성은 캐시 히트 여부와 무관하게 항상 필요한 별도 작업이라
    # 여기 시간에 합치면 "캐시가 빠르다"는 주장이 왜곡된다 — 따로 잰다.
    cache_hit = False
    t0 = time.perf_counter()
    if not grid_df.empty:
        match = grid_df[(grid_df["buffer_cap"] == buffer_cap) & (grid_df["pm_interval"] == pm_interval)]
        if not match.empty:
            cache_hit = True
            mc_result = match.drop(columns=["buffer_cap", "pm_interval"])

    if not cache_hit:
        mc_result = run_monte_carlo(
            n_runs=mc_reps, base_seed=42, buffer_caps=buffer_caps, pm_interval=pm_interval,
            pm_duration=PM_DURATION if pm_interval > 0 else 0.0, scenario_id=f"whatif_buf{buffer_cap}_pm{pm_interval}",
        )
    elapsed = time.perf_counter() - t0

    # 히스토그램용 개별 실행값 — 캐시엔 집계값만 있어서 항상 새로 뽑아야 한다. 별도 시간 측정.
    t1 = time.perf_counter()
    raw = run_monte_carlo_raw(
        n_runs=30 if cache_hit else mc_reps, base_seed=42, buffer_caps=buffer_caps, pm_interval=pm_interval,
        pm_duration=PM_DURATION if pm_interval > 0 else 0.0,
    )
    hist_elapsed = time.perf_counter() - t1
    print(f"[WhatIf] buffer={buffer_cap} pm={pm_interval} cache_hit={cache_hit} "
          f"kpi_elapsed={elapsed:.4f}s hist_elapsed={hist_elapsed:.4f}s")

    st.session_state.whatif_result = {
        "mc_result": mc_result, "raw": raw, "cache_hit": cache_hit, "elapsed": elapsed,
        "hist_elapsed": hist_elapsed, "mc_reps": mc_reps,
        "buffer_cap": buffer_cap, "pm_interval": pm_interval, "target_tact": target_tact,
    }

result = st.session_state.whatif_result

if result is None:
    st.info("왼쪽 사이드바에서 조건을 설정하고 [시뮬레이션 실행]을 눌러주세요.")
else:
    mc_result = result["mc_result"]
    raw = result["raw"]

    if result["cache_hit"]:
        st.success(f"캐시 조회 — {result['elapsed'] * 1000:.2f}ms (scenario_grid.parquet에서 즉시 조회, "
                   f"히스토그램용 재계산 별도 {result['hist_elapsed']:.2f}초)")
    else:
        st.warning(f"실시간 계산 — {result['elapsed']:.2f}초 (몬테카를로 {result['mc_reps']}회, 그리드에 없는 조합)")

    # 주의: mc_result는 (process, kpi_name)으로 groupby된 뒤라 행 순서가 알파벳순으로 바뀌어
    # "첫 행 = 병목공정"이 성립하지 않는다. oee 행은 병목공정에서만 나오므로 그걸로 찾는다.
    oee_rows = mc_result[mc_result["kpi_name"] == "oee"]
    bottleneck_process = oee_rows["process"].iloc[0] if not oee_rows.empty else "미측정"

    def get_val(df, name):
        row = df[df["kpi_name"] == name]
        return float(row["kpi_value"].iloc[0]) if not row.empty else None

    oee = get_val(mc_result, "oee")
    uph = get_val(mc_result, "uph")
    availability = get_val(mc_result, "availability")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("OEE", f"{oee * 100:.2f}%" if oee is not None else "미측정",
                delta=f"{(oee - base_kpi.get('oee', oee)) * 100:+.2f}%p" if oee is not None and base_kpi else None)
    col2.metric("UPH", f"{uph:.1f}" if uph is not None else "미측정",
                delta=f"{uph - base_kpi.get('uph', uph):+.1f}" if uph is not None and base_kpi else None)
    col3.metric("병목공정", bottleneck_process)
    col4.metric("가동률", f"{availability * 100:.2f}%" if availability is not None else "미측정",
                delta=f"{(availability - base_kpi.get('availability', availability)) * 100:+.2f}%p" if availability is not None and base_kpi else None)

    st.divider()

    oee_values = raw[(raw["process"] == bottleneck_process) & (raw["kpi_name"] == "oee")]["kpi_value"]
    ci_row = mc_result[mc_result["kpi_name"] == "oee"]
    ci_low = float(ci_row["ci_low"].iloc[0]) if not ci_row.empty else oee_values.min()
    ci_high = float(ci_row["ci_high"].iloc[0]) if not ci_row.empty else oee_values.max()
    st.plotly_chart(
        fig_monte_carlo(oee_values, ci_low=ci_low, ci_high=ci_high, mean=oee, title="OEE 몬테카를로 분포", x_label="OEE"),
        width="stretch",
    )

    st.divider()

    if not grid_df.empty:
        sens_df = grid_df[grid_df["kpi_name"] == "oee"]
        st.plotly_chart(
            fig_sensitivity(sens_df, value_col="kpi_value", title="버퍼×PM 민감도 (OEE)",
                             current_point=(result["buffer_cap"], result["pm_interval"])),
            width="stretch",
        )
    else:
        st.info("scenario_grid.parquet이 없어 민감도 히트맵을 표시할 수 없습니다.")

    st.divider()

    st.plotly_chart(fig_yamazumi(DEFAULT_CYCLE_TIMES, tact=float(result["target_tact"])), width="stretch")

    st.divider()

    st.subheader("공정별 고장/블로킹/기아 진단")
    st.caption("이 표는 현재 선택 조건의 8시간(480분) 단일 실행(seed=42) 기준입니다 — 몬테카를로 평균이 아닙니다.")
    diag_rows = mc_result[mc_result["kpi_name"].isin(["mtbf", "mttr"])]
    if not diag_rows.empty:
        diag_pivot = diag_rows.pivot(index="process", columns="kpi_name", values="kpi_value")
        st.dataframe(diag_pivot, width="stretch")

    st.divider()

    with st.expander("이 결과를 어떻게 읽나"):
        bottleneck_ct = DEFAULT_CYCLE_TIMES[bottleneck_process] if bottleneck_process in DEFAULT_CYCLE_TIMES else None
        lines = [f"**병목공정**: {bottleneck_process}" + (f" (사이클타임 {bottleneck_ct:.0f}초)" if bottleneck_ct else "")]

        base_buf5_pm0_oee = base_kpi.get("oee")
        if base_buf5_pm0_oee is not None and oee is not None:
            if abs(oee - base_buf5_pm0_oee) < 1e-6:
                lines.append("**버퍼 효과**: 기준 시나리오와 OEE가 동일합니다 — 이 8시간 창에서는 고장이 거의 발생하지 않아 "
                             "버퍼가 흡수할 변동 자체가 없기 때문입니다(TROUBLESHOOTING.md 2026-09-08 참고). "
                             "버퍼를 늘려도 추가 효과가 없을 가능성이 큽니다.")
            elif oee > base_buf5_pm0_oee:
                lines.append(f"**버퍼 효과**: 기준 대비 OEE가 {oee - base_buf5_pm0_oee:+.4f} 개선되었습니다.")
            else:
                lines.append(f"**버퍼 효과**: 기준 대비 OEE가 {oee - base_buf5_pm0_oee:+.4f} 낮습니다 — PM 등 다른 요인의 영향을 확인해보세요.")

        if pm_interval := result["pm_interval"]:
            lines.append(f"**PM 영향**: {pm_interval}분 주기 예방보전이 라인 전체를 멈추므로, PM 주기가 짧을수록 "
                         "가동률(Availability)이 직접적으로 낮아집니다.")

        lines.append("**제약이론(TOC) 관점**: 병목공정(열처리) 자체의 사이클타임을 줄이거나 설비를 추가하지 않는 한, "
                     "다른 공정을 아무리 개선해도 라인 전체 처리량은 늘지 않습니다. 다음 개선 우선순위는 "
                     "열처리 공정의 사이클타임 단축 또는 이중화입니다.")

        st.markdown("\n\n".join(lines))
