"""Streamlit 페이지: 라인밸런싱 — 야마즈미 차트, 목표 Tact 슬라이더로 스테이션 수·라인효율 재계산."""
import math
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.simulation.line_sim import DEFAULT_CYCLE_TIMES  # noqa: E402
from src.viz.fig_line import fig_yamazumi  # noqa: E402

st.set_page_config(page_title="라인밸런싱", layout="wide")
st.title("라인밸런싱")
st.caption("사이클타임은 라인의 설계 가정치(DEFAULT_CYCLE_TIMES)입니다 — STEP 6 line_sim.py와 동일한 값.")

total_work = sum(DEFAULT_CYCLE_TIMES.values())
current_bottleneck_ct = max(DEFAULT_CYCLE_TIMES.values())
current_bottleneck = max(DEFAULT_CYCLE_TIMES, key=DEFAULT_CYCLE_TIMES.get)

st.sidebar.header("목표 Tact")
target_tact = st.sidebar.slider("목표 Tact (초)", min_value=20, max_value=90, value=60, step=1)

st.plotly_chart(fig_yamazumi(DEFAULT_CYCLE_TIMES, tact=float(target_tact)), width="stretch")

st.divider()

st.subheader("라인밸런싱 재계산")

# 이론적 최소 스테이션 수 = 총 작업량(모든 공정 CT의 합) / 목표 Tact, 올림.
# 목표 Tact가 병목공정 CT보다 작으면, 스테이션을 아무리 늘려도 물리적으로 그 공정 자체를
# Tact 안에 못 끝내므로 "달성 불가"로 표시한다 (지어낸 수치로 얼버무리지 않음).
if target_tact < current_bottleneck_ct:
    st.error(
        f"목표 Tact({target_tact}초)가 현재 병목공정({current_bottleneck}, {current_bottleneck_ct:.0f}초)보다 짧습니다. "
        "공정을 추가로 쪼개거나(스테이션 분할) 병목공정 자체의 CT를 줄이지 않는 한 이 Tact는 물리적으로 달성할 수 없습니다."
    )
else:
    min_stations = math.ceil(total_work / target_tact)
    line_efficiency = total_work / (min_stations * target_tact)

    col1, col2, col3 = st.columns(3)
    col1.metric("총 작업량 (ΣCT)", f"{total_work:.1f}초")
    col2.metric("이론 최소 스테이션 수", f"{min_stations}개")
    col3.metric("라인 효율", f"{line_efficiency * 100:.1f}%")

    st.caption(
        f"현재 라인은 5공정 5스테이션(1:1)으로 설계되어 있습니다. "
        f"목표 Tact {target_tact}초를 만족하려면 이론상 최소 {min_stations}개 스테이션이 필요합니다 "
        f"(공정을 스테이션 간에 재배분한다고 가정 — 실제 재배분 방법까지는 이 프로젝트 범위 밖입니다)."
    )

st.divider()

st.subheader("해석")
st.write(f"현재 병목공정은 **{current_bottleneck}**({current_bottleneck_ct:.0f}초)입니다. "
         f"목표 Tact를 {current_bottleneck_ct:.0f}초보다 짧게 잡으면 이 공정을 쪼개거나 개선하지 않는 한 달성 불가능합니다.")
