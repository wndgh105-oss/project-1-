"""시뮬레이션 결과 차트(몬테카를로 분포, 민감도 히트맵). 모든 함수는 plotly Figure를 반환한다."""
import pandas as pd
import plotly.graph_objects as go

from src.viz.common import FIGURES, FONT_FAMILY, ROOT, set_horizontal_yaxis_label


def fig_monte_carlo(values, ci_low: float, ci_high: float, mean: float | None = None,
                     title: str = "몬테카를로 결과 분포", x_label: str = "값",
                     save_png: bool = False, filename: str = "fig_monte_carlo.png") -> go.Figure:
    """이 차트가 답하는 질문: 이 결과는 반복 실행했을 때 얼마나 흔들리는가(95% 신뢰구간은 어디인가)?

    values: 반복 실행(seed별)에서 나온 개별 값들의 배열.
    """
    values = list(values)
    n = len(values)
    if mean is None:
        mean = sum(values) / n if n else 0.0

    # n회 반복이 전부 완전히 같은 값이면(예: 8시간 시나리오에 고장이 한 번도 없는 경우)
    # 일반 히스토그램은 Plotly가 구간(bin) 폭을 정하지 못해 화면 전체를 채워버리는 등
    # 오해를 부르는 그림이 된다 — 이 경우는 "변동 없음"이라고 명시적으로 보여준다.
    value_range = (max(values) - min(values)) if values else 0.0
    is_degenerate = value_range < 1e-9 and abs(ci_high - ci_low) < 1e-9

    fig = go.Figure()
    if is_degenerate:
        spike_width = max(abs(mean) * 0.02, 1e-6)
        fig.add_trace(go.Bar(x=[mean], y=[n], width=[spike_width], marker_color="#1F77B4"))
        # 주석을 플롯 영역 "안"(예: x=0.5,y=0.5)에 두면 막대 높이(n)에 따라 막대와 겹쳐 보인다
        # (버퍼=5·PM=0 기본 시나리오에서 실제로 겹쳐 보이는 문제 발견, TROUBLESHOOTING.md
        # 2026-09-10 배포 QA 참고) — 막대 높이와 무관하게 항상 플롯 영역 "위쪽 바깥"에 고정한다.
        fig.add_annotation(
            text=f"{n}회 모두 동일한 값({mean:.4f}) — 변동 없음", xref="paper", yref="paper",
            x=0.5, y=1.08, yanchor="bottom", showarrow=False, font=dict(family=FONT_FAMILY, size=13),
        )
    else:
        fig.add_trace(go.Histogram(x=values, name="반복 실행값", marker_color="#1F77B4", opacity=0.85))
        fig.add_vrect(x0=ci_low, x1=ci_high, fillcolor="#2CA02C", opacity=0.15, line_width=0,
                      annotation_text="95% CI", annotation_position="top left")
        fig.add_vline(x=mean, line_dash="dash", line_color="#D62728",
                      annotation_text=f"평균={mean:.4f}", annotation_position="bottom right")

    fig.update_layout(
        title=f"{title} (n={n}회)",
        xaxis_title=x_label,
        font=dict(family=FONT_FAMILY),
        showlegend=False,
    )
    set_horizontal_yaxis_label(fig, "빈도")

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


def fig_sensitivity(grid_df: pd.DataFrame, x_col: str = "buffer_cap", y_col: str = "pm_interval",
                     value_col: str = "kpi_value", current_point: tuple[float, float] | None = None,
                     title: str = "민감도 히트맵", save_png: bool = False,
                     filename: str = "fig_sensitivity.png") -> go.Figure:
    """이 차트가 답하는 질문: 버퍼×PM 조합에 따라 OEE(또는 다른 KPI)가 어떻게 달라지는가?

    grid_df: x_col, y_col, value_col 컬럼을 가진 시나리오 그리드(이미 kpi_name으로 필터링된 상태).
    current_point: (x, y) — 현재 선택된 지점을 마커로 표시.
    """
    pivot = grid_df.pivot_table(index=y_col, columns=x_col, values=value_col, aggfunc="mean")

    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale="Blues", colorbar=dict(title=value_col),
    ))

    if current_point is not None:
        fig.add_trace(go.Scatter(
            x=[current_point[0]], y=[current_point[1]], mode="markers",
            marker=dict(color="#D62728", size=16, symbol="star", line=dict(color="white", width=1)),
            name="현재 선택",
        ))

    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_col,
        font=dict(family=FONT_FAMILY),
        showlegend=False,
    )

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from src.simulation.monte_carlo import run_monte_carlo_raw

    raw = run_monte_carlo_raw(n_runs=30, base_seed=42)
    oee_values = raw[(raw["process"] == "열처리") & (raw["kpi_name"] == "oee")]["kpi_value"]
    fig1 = fig_monte_carlo(oee_values, ci_low=oee_values.min(), ci_high=oee_values.max(),
                            title="OEE 몬테카를로 분포 (샘플)", x_label="OEE", save_png=True)
    fig1.show()
    print(f"저장 확인: {(FIGURES / 'fig_monte_carlo.png').exists()}")

    grid = pd.read_parquet(ROOT / "data" / "processed" / "scenario_grid.parquet")
    oee_grid = grid[grid["kpi_name"] == "oee"]
    fig2 = fig_sensitivity(oee_grid, value_col="kpi_value", current_point=(5, 0), save_png=True)
    fig2.show()
    print(f"저장 확인: {(FIGURES / 'fig_sensitivity.png').exists()}")
