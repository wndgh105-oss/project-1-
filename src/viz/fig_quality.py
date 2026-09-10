"""품질 관련 차트. 모든 함수는 plotly Figure를 반환한다."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.viz.common import FIGURES, FONT_FAMILY, ROOT, set_horizontal_yaxis_label


def fig_pareto(counts, title: str = "파레토", value_label: str = "건수", save_png: bool = False, filename: str = "fig_pareto.png") -> go.Figure:
    """이 차트가 답하는 질문: 상위 몇 개 항목이 전체의 80%를 차지하는가?

    counts: pandas Series (index=항목명, value=건수), 내림차순 정렬은 함수 내부에서 처리한다.
    """
    counts = counts.sort_values(ascending=False)
    cum_pct = counts.cumsum() / counts.sum() * 100
    n_total = int(counts.sum())

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=counts.index.astype(str), y=counts.values, name=value_label, marker_color="#1F77B4"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=counts.index.astype(str), y=cum_pct.values, name="누적 비율(%)",
                   mode="lines+markers", line=dict(color="#D62728")),
        secondary_y=True,
    )
    fig.add_hline(y=80, line_dash="dash", line_color="#9E9E9E", secondary_y=True,
                  annotation_text="80%", annotation_position="top left")

    fig.update_layout(
        title=f"{title} (n={n_total:,}건)",
        font=dict(family=FONT_FAMILY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(range=[0, 105], secondary_y=True)
    set_horizontal_yaxis_label(fig, value_label)
    fig.add_annotation(
        text="누적 비율 (%)", xref="paper", yref="paper", x=1.0, y=1.0,
        showarrow=False, xanchor="left", yanchor="bottom",
        font=dict(family=FONT_FAMILY, size=12),
    )

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


def fig_control_chart(subgroup_df, value_col: str, ucl_col: str, cl_col: str, lcl_col: str,
                       violation_col: str | None = None, title: str = "관리도",
                       y_label: str = "측정값", save_png: bool = False,
                       filename: str = "fig_control_chart.png") -> go.Figure:
    """이 차트가 답하는 질문: 이 공정은 통계적으로 안정한가(관리한계를 벗어난 점이 있는가)?

    subgroup_df: 부분군별 통계가 이미 계산된 DataFrame (subgroup, value_col, UCL/CL/LCL 컬럼 포함).
    UCL/CL/LCL은 구간 내 상수라고 가정하고 첫 값을 기준선으로 그린다.
    """
    n = len(subgroup_df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=subgroup_df["subgroup"], y=subgroup_df[value_col], mode="lines+markers",
        name=value_col, line=dict(color="#1F77B4", width=1), marker=dict(size=4),
    ))

    ucl, cl, lcl = subgroup_df[ucl_col].iloc[0], subgroup_df[cl_col].iloc[0], subgroup_df[lcl_col].iloc[0]
    fig.add_hline(y=ucl, line_dash="dash", line_color="#D62728", annotation_text=f"UCL={ucl:.3f}")
    fig.add_hline(y=cl, line_dash="dot", line_color="#9E9E9E", annotation_text=f"CL={cl:.3f}")
    fig.add_hline(y=lcl, line_dash="dash", line_color="#D62728", annotation_text=f"LCL={lcl:.3f}")

    if violation_col and violation_col in subgroup_df.columns:
        viol = subgroup_df[subgroup_df[violation_col].notna()]
        if not viol.empty:
            fig.add_trace(go.Scatter(
                x=viol["subgroup"], y=viol[value_col], mode="markers",
                marker=dict(color="#D62728", size=9, symbol="x"), name="관리이탈(Nelson Rule)",
            ))

    fig.update_layout(
        title=f"{title} (부분군 n={n}개)",
        xaxis_title="부분군 번호",
        font=dict(family=FONT_FAMILY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    set_horizontal_yaxis_label(fig, y_label)

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


def fig_cost_curve(cost_df, save_png: bool = False, filename: str = "fig_cost_curve.png") -> go.Figure:
    """이 차트가 답하는 질문: 임계값을 어디로 잡아야 (과검 10 vs 미검 500) 총비용이 최소가 되는가?

    cost_df: threshold, total_cost 컬럼을 포함한 DataFrame (STEP 8의 cost_curve.parquet).
    """
    best_row = cost_df.loc[cost_df["total_cost"].idxmin()]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cost_df["threshold"], y=cost_df["total_cost"], mode="lines",
        name="총비용", line=dict(color="#1F77B4"),
    ))
    fig.add_trace(go.Scatter(
        x=[best_row["threshold"]], y=[best_row["total_cost"]], mode="markers+text",
        marker=dict(color="#D62728", size=12, symbol="star"),
        text=[f"최적 임계값 {best_row['threshold']:.2f}, 비용 {best_row['total_cost']:,.0f}"],
        textposition="middle right", name="비용 최소점",
    ))

    fig.update_layout(
        title="임계값별 총비용 (과검=10, 미검=500)",
        xaxis_title="예측 임계값",
        font=dict(family=FONT_FAMILY),
        showlegend=False,
        margin=dict(l=90),
    )
    set_horizontal_yaxis_label(fig, "총비용")

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


if __name__ == "__main__":
    import pandas as pd
    sample = pd.Series({"comp2": 34, "comp1": 25, "comp4": 24, "comp3": 17})
    fig = fig_pareto(sample, title="샘플 고장 부품 파레토", save_png=True)
    fig.show()
    print(f"저장 확인: {(FIGURES / 'fig_pareto.png').exists()}")

    cost_df = pd.read_parquet(ROOT / "data" / "processed" / "cost_curve.parquet")
    fig2 = fig_cost_curve(cost_df, save_png=True)
    fig2.show()
    print(f"저장 확인: {(FIGURES / 'fig_cost_curve.png').exists()}")
