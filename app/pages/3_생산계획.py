"""Streamlit 페이지: 생산계획 — FCFS vs SPT 디스패칭 규칙 비교, 간트 차트."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.simulation.scheduling import generate_job_processing_times, simulate_flow_shop  # noqa: E402
from src.viz.fig_line import fig_gantt  # noqa: E402

st.set_page_config(page_title="생산계획", layout="wide")
st.title("생산계획 — 디스패칭 규칙 비교")
st.caption("잡별 공정 처리시간은 라인의 설계 가정 사이클타임(±20%, 시드 고정 난수)에서 생성한 시나리오입니다. "
           "실측 주문 데이터가 아닙니다.")


@st.cache_data
def get_jobs():
    return generate_job_processing_times()


@st.cache_data
def get_schedule(rule: str):
    jobs = get_jobs()
    schedule_df, makespan = simulate_flow_shop(jobs, rule=rule)
    return schedule_df, makespan


rule = st.radio("디스패칭 규칙", ["FCFS", "SPT"], horizontal=True,
                 help="FCFS: 도착 순서대로 처리 / SPT: 그 공정에서 처리시간이 짧은 잡부터 처리")

schedule_df, makespan = get_schedule(rule)
fcfs_df, fcfs_makespan = get_schedule("FCFS")
spt_df, spt_makespan = get_schedule("SPT")

col1, col2, col3 = st.columns(3)
col1.metric(f"{rule} 메이크스팬", f"{makespan:.1f}초")
col2.metric("FCFS 메이크스팬", f"{fcfs_makespan:.1f}초")
col3.metric("SPT 메이크스팬", f"{spt_makespan:.1f}초")

st.plotly_chart(fig_gantt(schedule_df, title=f"{rule} 스케줄 (메이크스팬 {makespan:.0f}초)"), width="stretch")

st.divider()

st.subheader("해석")
if spt_makespan > fcfs_makespan:
    diff = spt_makespan - fcfs_makespan
    st.warning(
        f"이 시나리오에서는 **SPT가 FCFS보다 메이크스팬이 {diff:.1f}초({diff / fcfs_makespan * 100:.1f}%) 더 깁니다.** "
        "'SPT가 항상 더 낫다'는 통념과 다른 결과입니다.\n\n"
        "**원인**: SPT를 5개 공정 각각에서 독립적으로 적용하면, 여러 공정에서 처리시간이 상대적으로 긴 잡이 "
        "매 공정마다 계속 뒤로 밀려 대기시간이 누적됩니다(다른 잡들이 항상 새치기). "
        "SPT는 **단일 공정**의 평균 흐름시간을 최적화하는 데는 이론적으로 우수하지만, "
        "**다단계 플로우샵의 메이크스팬**을 최적화한다는 보장은 없습니다(2단계 흐름생산에는 Johnson's rule 같은 "
        "전용 알고리즘이 필요합니다). TROUBLESHOOTING.md 2026-09-08 참고."
    )
else:
    diff = fcfs_makespan - spt_makespan
    st.success(f"이 시나리오에서는 SPT가 FCFS보다 메이크스팬이 {diff:.1f}초({diff / fcfs_makespan * 100:.1f}%) 더 짧습니다.")
