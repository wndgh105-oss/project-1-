"""OEE 관련 차트. 모든 함수는 plotly Figure를 반환한다(Streamlit에서 st.plotly_chart로 바로 사용).

공통 규칙: 한글 폰트는 layout에 명시적으로 지정한다(배포 환경에 Malgun Gothic이 없을 수 있어
Apple SD Gothic Neo, sans-serif를 폴백으로 같이 넣는다).
"""
import plotly.graph_objects as go

from src.viz.common import FIGURES, FONT_FAMILY, set_horizontal_yaxis_label

TARGET_OEE = 0.85


def fig_oee_waterfall(a: float, p: float, q: float, target: float = TARGET_OEE, save_png: bool = False) -> go.Figure:
    """이 차트가 답하는 질문: 100%에서 시작해 가동률·성능·품질 손실로 얼마씩 깎여서
    최종 OEE가 되는가?

    a, p, q는 0~1 비율(Availability, Performance, Quality)이다.
    """
    if not (0 <= a <= 1 and 0 <= p <= 1 and 0 <= q <= 1):
        raise ValueError(f"a, p, q는 0~1 비율이어야 함: a={a}, p={p}, q={q}")

    start = 100.0
    after_a = start * a
    after_ap = after_a * p
    after_apq = after_ap * q  # = OEE * 100

    avail_loss = -(start - after_a)
    perf_loss = -(after_a - after_ap)
    qual_loss = -(after_ap - after_apq)

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["시작 (100%)", f"가동률 손실\n(A={a * 100:.1f}%)", f"성능 손실\n(P={p * 100:.1f}%)",
           f"품질 손실\n(Q={q * 100:.1f}%)", "OEE"],
        y=[start, avail_loss, perf_loss, qual_loss, 0],
        text=[f"{start:.1f}%", f"{avail_loss:.1f}%p", f"{perf_loss:.1f}%p", f"{qual_loss:.1f}%p", f"{after_apq:.1f}%"],
        textposition="outside",
        connector={"line": {"color": "#9E9E9E"}},
        increasing={"marker": {"color": "#1F77B4"}},
        decreasing={"marker": {"color": "#D62728"}},
        totals={"marker": {"color": "#1F77B4"}},
    ))

    fig.add_hline(
        y=target * 100,
        line_dash="dash",
        line_color="#2CA02C",
        annotation_text=f"목표 OEE {target * 100:.0f}%",
        annotation_position="top left",
    )

    fig.update_layout(
        title="OEE 손실 구조 — 100%에서 무엇이 얼마나 깎였는가",
        font=dict(family=FONT_FAMILY),
        showlegend=False,
        margin=dict(t=80, b=60),
    )
    set_horizontal_yaxis_label(fig, "비율 (%)")

    if save_png:
        fig.write_image(str(FIGURES / "fig_oee_waterfall.png"), scale=2)

    return fig


def fig_kpi_gauge(oee: float, target: float = TARGET_OEE, save_png: bool = False) -> go.Figure:
    """이 차트가 답하는 질문: 현재 OEE는 목표 대비 어느 수준인가?"""
    if not (0 <= oee <= 1):
        raise ValueError(f"oee는 0~1 비율이어야 함: {oee}")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=oee * 100,
        number={"suffix": "%"},
        delta={"reference": target * 100, "increasing": {"color": "#1F77B4"}, "decreasing": {"color": "#D62728"}},
        title={"text": "OEE (종합설비효율)"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#1F77B4"},
            "steps": [
                {"range": [0, 60], "color": "#F2F2F2"},
                {"range": [60, target * 100], "color": "#E0E0E0"},
                {"range": [target * 100, 100], "color": "#D6EAF8"},
            ],
            "threshold": {
                "line": {"color": "#2CA02C", "width": 3},
                "thickness": 0.9,
                "value": target * 100,
            },
        },
    ))

    fig.update_layout(font=dict(family=FONT_FAMILY), margin=dict(t=60, b=20))

    if save_png:
        fig.write_image(str(FIGURES / "fig_kpi_gauge.png"), scale=2)

    return fig


if __name__ == "__main__":
    # STEP 6 3단계 기본 시나리오(8시간, 버퍼 5, PM 없음)의 실제 실행 결과값
    fig1 = fig_oee_waterfall(a=1.0, p=0.991667, q=1.0, save_png=True)
    fig1.show()
    print(f"저장 확인: {(FIGURES / 'fig_oee_waterfall.png').exists()}")

    fig2 = fig_kpi_gauge(oee=0.991667, save_png=True)
    fig2.show()
    print(f"저장 확인: {(FIGURES / 'fig_kpi_gauge.png').exists()}")
