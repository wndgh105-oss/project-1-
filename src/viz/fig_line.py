"""라인/스케줄링 관련 차트. 모든 함수는 plotly Figure를 반환한다."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.viz.common import FIGURES, FONT_FAMILY, ROOT, set_horizontal_yaxis_label


def fig_gantt(schedule_df: pd.DataFrame, title: str = "생산 스케줄", save_png: bool = False, filename: str = "fig_gantt.png"):
    """이 차트가 답하는 질문: 어느 잡이 어느 공정을 언제~언제 점유하는가?

    schedule_df: job, station, start, end 컬럼 (초 단위 상대시각).
    px.timeline은 실제 datetime이 필요하므로, 초 단위를 임의 기준일(2000-01-01) 위의
    시각으로 변환해서 그린다 — 실제 날짜가 아니라 상대 경과시간을 표현하기 위한 변환이다.
    """
    df = schedule_df.copy()
    base = pd.Timestamp("2000-01-01")
    df["start_dt"] = base + pd.to_timedelta(df["start"], unit="s")
    df["end_dt"] = base + pd.to_timedelta(df["end"], unit="s")

    fig = px.timeline(
        df, x_start="start_dt", x_end="end_dt", y="station", color="job",
        title=title,
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="경과 시간 (초, 기준일 임의 설정)", tickformat="%M:%S")
    fig.update_layout(font=dict(family=FONT_FAMILY), legend_title="잡")
    set_horizontal_yaxis_label(fig, "공정")

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


def fig_yamazumi(cycle_times: dict[str, float], tact: float, save_png: bool = False, filename: str = "fig_yamazumi.png") -> go.Figure:
    """이 차트가 답하는 질문: 어느 공정이 병목인가(Tact를 넘기는가), 어느 공정이 여유가 있는가?

    각 막대는 Tact까지 두 구간으로 쌓는다 — 실제 CT(파란색, Tact 이내분)와
    CT가 Tact를 넘긴 만큼(빨간색, 병목분), CT가 Tact보다 짧으면 남는 여유(회색)를 얹는다.
    """
    processes = list(cycle_times.keys())
    within_tact = [min(ct, tact) for ct in cycle_times.values()]
    over_tact = [max(ct - tact, 0) for ct in cycle_times.values()]
    idle = [max(tact - ct, 0) for ct in cycle_times.values()]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=processes, y=within_tact, name="사이클타임 (Tact 이내)", marker_color="#1F77B4"))
    fig.add_trace(go.Bar(x=processes, y=over_tact, name="Tact 초과분 (병목)", marker_color="#D62728"))
    fig.add_trace(go.Bar(x=processes, y=idle, name="여유시간", marker_color="#E0E0E0"))
    fig.update_layout(barmode="stack")

    fig.add_hline(y=tact, line_dash="dash", line_color="#2CA02C",
                  annotation_text=f"Tact = {tact:.1f}초", annotation_position="top left")

    fig.update_layout(
        title="야마즈미 차트 — 공정별 사이클타임 vs Tact",
        xaxis_title="공정",
        font=dict(family=FONT_FAMILY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    set_horizontal_yaxis_label(fig, "시간 (초)")

    if save_png:
        fig.write_image(str(FIGURES / filename), scale=2)

    return fig


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from src.simulation.scheduling import generate_job_processing_times, simulate_flow_shop

    jobs = generate_job_processing_times()
    schedule_df, makespan = simulate_flow_shop(jobs, rule="FCFS")
    fig = fig_gantt(schedule_df, title=f"FCFS 스케줄 (메이크스팬 {makespan:.0f}초)", save_png=True)
    fig.show()
    print(f"저장 확인: {(FIGURES / 'fig_gantt.png').exists()}")

    from src.simulation.line_sim import DEFAULT_CYCLE_TIMES
    fig2 = fig_yamazumi(DEFAULT_CYCLE_TIMES, tact=55.0, save_png=True)
    fig2.show()
    print(f"저장 확인: {(FIGURES / 'fig_yamazumi.png').exists()}")
