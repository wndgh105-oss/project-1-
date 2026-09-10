"""Streamlit 페이지: 품질 SPC — 관리도, Cp/Cpk, 임계값 슬라이더, 기존 대시보드 임베드.

관리도용 데이터는 이 프로젝트의 src/ 파이프라인이 새로 만든 게 아니라 이전에 만든
포트폴리오 산출물(data/legacy/용접_SPC_대시보드.xlsx)을 재활용한다(data/legacy/README.md 참고).
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.viz.fig_quality import fig_control_chart, fig_cost_curve  # noqa: E402

st.set_page_config(page_title="품질 SPC", layout="wide")
st.title("품질 SPC — 용접 공정 (RSW)")
st.caption("관리도·Cp/Cpk는 기존 포트폴리오 산출물(data/legacy/)을 재활용한 실측 산출값입니다.")


@st.cache_data
def load_xbar_r() -> pd.DataFrame:
    path = ROOT / "data" / "legacy" / "용접_SPC_대시보드.xlsx"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name="Xbar_R_Data", skiprows=3, engine="openpyxl")


@st.cache_data
def load_cpk_table() -> pd.DataFrame:
    path = ROOT / "data" / "legacy" / "용접_SPC_대시보드.xlsx"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name="Cpk_Table", skiprows=3, engine="openpyxl")


@st.cache_data
def load_cost_curve() -> pd.DataFrame:
    path = ROOT / "data" / "processed" / "cost_curve.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


xbar_r = load_xbar_r()
cpk_table = load_cpk_table()
cost_curve = load_cost_curve()

st.subheader("관리도 (X-bar / R) — WELD-L1 너겟 지름(mm), n=5, 600부분군")
if xbar_r.empty:
    st.info("용접_SPC_대시보드.xlsx가 없습니다.")
else:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            fig_control_chart(xbar_r, value_col="xbar", ucl_col="UCL_x", cl_col="CL_x", lcl_col="LCL_x",
                               violation_col="viol_xbar", title="X-bar 관리도", y_label="X-bar (mm)"),
            width='stretch',
        )
    with col2:
        st.plotly_chart(
            fig_control_chart(xbar_r, value_col="r", ucl_col="UCL_r", cl_col="CL_r", lcl_col="LCL_r",
                               violation_col="viol_r", title="R 관리도", y_label="R (mm)"),
            width='stretch',
        )
    n_viol = xbar_r["rule_violation"].notna().sum() if "rule_violation" in xbar_r.columns else 0
    st.caption(f"Nelson Rule 위반 부분군: {n_viol}개 / 전체 {len(xbar_r)}개")

st.divider()

st.subheader("공정능력지수 (Cp/Cpk)")
if cpk_table.empty:
    st.info("Cpk_Table 시트를 읽을 수 없습니다.")
else:
    st.dataframe(cpk_table, width='stretch', hide_index=True)
    st.caption("규격: LSL 5.4mm / USL 6.6mm / 목표 6.0mm. Cpk < 1.00이면 부적합 수준으로 판정.")

st.divider()

st.subheader("시나리오별 불량 건수 비교")
st.caption("이 데이터셋은 불량 유형이 '너겟 지름 규격이탈' 1종뿐이라 유형별 파레토 대신 "
           "정기샘플링(Before)·SPC 즉시조치(After)·미조치 방치 시나리오별 실측 불량 건수를 비교합니다.")
if not cpk_table.empty and "표본수(n)" in cpk_table.columns:
    st.dataframe(cpk_table[["구간", "표본수(n)", "Cpk"]], width='stretch', hide_index=True)

st.divider()

st.subheader("비용민감 모델 임계값 조정 (STEP 8, 실시간)")
if cost_curve.empty:
    st.info("cost_curve.parquet이 없습니다 — src/models/pdm_cost_sensitive.py를 먼저 실행해주세요.")
else:
    threshold = st.slider("예측 임계값", min_value=0.01, max_value=0.99, value=0.05, step=0.01)
    st.plotly_chart(fig_cost_curve(cost_curve), width='stretch')
    nearest = cost_curve.iloc[(cost_curve["threshold"] - threshold).abs().idxmin()]
    col1, col2, col3 = st.columns(3)
    col1.metric("선택 임계값 총비용", f"{nearest['total_cost']:,.0f}")
    col2.metric("Recall", f"{nearest['recall'] * 100:.1f}%")
    col3.metric("Precision", f"{nearest['precision'] * 100:.1f}%")

st.divider()

st.subheader("기존 대시보드 (재활용)")
legacy_html_path = ROOT / "legacy_html" / "dashboard2_welding_spc.html"
if legacy_html_path.exists():
    with open(legacy_html_path, "r", encoding="utf-8") as f:
        components.html(f.read(), height=800, scrolling=True)
else:
    st.info("legacy_html/dashboard2_welding_spc.html이 없습니다.")
