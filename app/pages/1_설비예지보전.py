"""Streamlit 페이지: 설비 예지보전 — STEP 3(MTBF/MTTR)과 STEP 8(비용민감 모델) 결과를 보여준다."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.viz.fig_quality import fig_pareto  # noqa: E402

st.set_page_config(page_title="설비 예지보전", layout="wide")
st.title("설비 예지보전")


@st.cache_data
def load_mtbf_mttr_machine() -> pd.DataFrame:
    path = ROOT / "data" / "interim" / "mtbf_mttr.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_mtbf_mttr_component() -> pd.DataFrame:
    path = ROOT / "data" / "interim" / "mtbf_mttr_by_component.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_failure_pareto() -> pd.DataFrame:
    """src/kpi/precompute_page1.py가 미리 계산해둔 결과를 읽는다 — data/raw/azure_pdm(80MB
    telemetry 포함)는 배포 저장소에 올리지 않기로 했기 때문이다(TROUBLESHOOTING.md
    2026-09-10, STEP 13 배포 준비 중 발견). 값 자체는 원래 계산과 동일하다."""
    path = ROOT / "data" / "interim" / "failure_pareto.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_sensor_precursor() -> pd.DataFrame:
    """고장 직전 24시간 센서 평균 vs 평상시 평균. 원래 여기서 telemetry 876,100행을 직접
    읽어 계산했지만(machineID 그룹핑으로 10.27초→2.19초 최적화, TROUBLESHOOTING.md
    2026-09-10), 배포 시 data/raw/를 저장소에서 빼기로 하면서 그 계산 자체를
    src/kpi/precompute_page1.py로 옮기고 여기서는 결과만 읽는다."""
    path = ROOT / "data" / "interim" / "sensor_precursor.parquet"
    return pd.read_parquet(path).set_index("센서") if path.exists() else pd.DataFrame()


@st.cache_data
def load_pdm_comparison() -> pd.DataFrame:
    path = ROOT / "data" / "interim" / "pdm_cost_comparison.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


mtbf_machine = load_mtbf_mttr_machine()
mtbf_comp = load_mtbf_mttr_component()
failure_pareto = load_failure_pareto()
comparison = load_pdm_comparison()

st.subheader("MTBF / MTTR (STEP 3 실측)")
tab1, tab2 = st.tabs(["부품별 (comp1~4)", "설비별 (상위·하위 5개)"])
with tab1:
    if mtbf_comp.empty:
        st.info("mtbf_mttr_by_component.parquet이 없습니다 — src/kpi/reliability.py를 먼저 실행해주세요.")
    else:
        st.dataframe(mtbf_comp, width='stretch', hide_index=True)
with tab2:
    if mtbf_machine.empty:
        st.info("mtbf_mttr.parquet이 없습니다 — src/kpi/reliability.py를 먼저 실행해주세요.")
    else:
        col1, col2 = st.columns(2)
        col1.write("MTBF 상위 5개 설비 (고장이 뜸한 순)")
        col1.dataframe(mtbf_machine.nlargest(5, "mtbf_hours"), width='stretch', hide_index=True)
        col2.write("MTBF 하위 5개 설비 (고장이 잦은 순)")
        col2.dataframe(mtbf_machine.nsmallest(5, "mtbf_hours"), width='stretch', hide_index=True)

st.divider()

st.subheader("고장 유형 파레토")
if failure_pareto.empty:
    st.info("data/interim/failure_pareto.csv가 없습니다 — src/kpi/precompute_page1.py를 먼저 실행해주세요.")
else:
    counts = failure_pareto.set_index("failure")["count"]
    st.plotly_chart(fig_pareto(counts, title="고장 부품 파레토", value_label="고장 건수"), width='stretch')

st.divider()

st.subheader("센서 열화 추이 — 고장 직전 24시간 vs 평상시")
precursor = load_sensor_precursor()
if precursor.empty:
    st.info("data/interim/sensor_precursor.parquet이 없습니다 — src/kpi/precompute_page1.py를 먼저 실행해주세요.")
else:
    st.dataframe(precursor.style.format("{:.3f}"), width='stretch')
    st.caption("변화율(%)이 0에서 멀수록 그 센서가 고장 직전에 평소와 달라진다는 뜻 — 전조 신호 후보.")

st.divider()

st.subheader("비용민감 예지보전 모델 (STEP 8, APS Scania)")
if comparison.empty:
    st.info("pdm_cost_comparison.csv가 없습니다 — src/models/pdm_cost_sensitive.py를 먼저 실행해주세요.")
else:
    st.dataframe(comparison, width='stretch', hide_index=True)
    dummy_cost = comparison.loc[comparison["label"].str.contains("더미"), "total_cost"]
    optimal_cost = comparison.loc[comparison["label"].str.contains("비용최적"), "total_cost"]
    if not dummy_cost.empty and not optimal_cost.empty:
        savings = int(dummy_cost.iloc[0] - optimal_cost.iloc[0])
        st.metric("더미 대비 비용 절감액", f"{savings:,}", delta=f"-{savings / dummy_cost.iloc[0] * 100:.1f}%")
