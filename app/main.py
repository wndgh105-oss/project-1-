"""Streamlit 대시보드 진입점 — Tab 0(종합).

경로 규칙: 이 파일은 app/ 아래 있으므로, 프로젝트 루트는 한 단계 위(parents[1])다.
배포 환경(Streamlit Community Cloud 등)에서도 항상 이 파일 기준 상대경로로 찾아야
절대경로 하드코딩으로 인한 배포 실패를 피할 수 있다(STEP 13에서 다시 다룸).
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # src.* 임포트를 위해 프로젝트 루트를 경로에 추가

from src.viz.fig_oee import fig_kpi_gauge, fig_oee_waterfall  # noqa: E402

st.set_page_config(page_title="PT 라인 통합 KPI 대시보드", layout="wide")


@st.cache_data
def load_kpi() -> pd.DataFrame:
    """kpi.parquet 읽기 — 슬라이더 조작마다 파일을 다시 읽지 않도록 캐시."""
    path = ROOT / "data" / "processed" / "kpi.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data
def load_scenario_grid() -> pd.DataFrame:
    path = ROOT / "data" / "processed" / "scenario_grid.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


kpi_df = load_kpi()
scenario_df = load_scenario_grid()

st.sidebar.header("시나리오 선택")
if not scenario_df.empty:
    scenario_options = sorted(scenario_df["scenario_id"].unique())
    selected_scenario = st.sidebar.selectbox("시나리오 (buffer_cap × pm_interval)", scenario_options)
else:
    selected_scenario = "base"
    st.sidebar.info("scenario_grid.parquet이 아직 없습니다 (STEP 7 build_scenarios.py 실행 필요)")

st.title("Dashboard project 1")
st.caption("모든 수치는 실제 스크립트 실행 결과입니다. 데이터 출처는 사이드바 하단 또는 '데이터 출처' 페이지 참고.")

# --- 상단 스코어카드: base 시나리오 기준 OEE/A/P/Q ---
if kpi_df.empty:
    st.warning("kpi.parquet이 없습니다. src/simulation/build_scenarios.py를 먼저 실행해주세요.")
else:
    base = kpi_df[(kpi_df["scenario_id"] == "base") & (kpi_df["source"] == "line_sim_mc")]

    def get_kpi(name: str) -> float | None:
        row = base[base["kpi_name"] == name]
        return float(row["kpi_value"].iloc[0]) if not row.empty else None

    oee = get_kpi("oee")
    availability = get_kpi("availability")
    performance = get_kpi("performance")
    quality = get_kpi("quality")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("OEE", f"{oee * 100:.2f}%" if oee is not None else "미측정")
    col2.metric("가동률 (A)", f"{availability * 100:.2f}%" if availability is not None else "미측정")
    col3.metric("성능 (P)", f"{performance * 100:.2f}%" if performance is not None else "미측정")
    col4.metric("품질 (Q)", f"{quality * 100:.2f}%" if quality is not None else "미측정")

    st.divider()

    if None not in (availability, performance, quality, oee):
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(fig_oee_waterfall(availability, performance, quality), width='stretch')
        with chart_col2:
            st.plotly_chart(fig_kpi_gauge(oee), width='stretch')

    st.divider()

    # --- 소스별 KPI 요약표 ---
    # 원 계획은 "5개 시뮬레이션 요약표"였으나, 이 프로젝트는 sim1~5 대신 처음부터 설계한
    # SimPy 라인(line_sim_mc)과 비용민감 모델(pdm_cost_sensitive) 2개 소스로 구성된다
    # (README.md의 2026-09-08 결정 참고).
    st.subheader("소스별 KPI 요약")
    pivot = kpi_df.pivot_table(index=["source", "process", "kpi_name"], values="kpi_value", aggfunc="first").reset_index()
    st.dataframe(pivot, width='stretch', hide_index=True)
