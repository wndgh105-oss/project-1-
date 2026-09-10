"""시각화 함수들의 공통 상수·헬퍼.

왜 필요한가: Kaleido(PNG 내보내기)가 받침 있는 한글 음절(예: '공정', '병목', '가동률'의
'동'·'률')을 90도 회전된 텍스트로 그릴 때 글자가 깨지는 버그가 있다
(2026-09-10 STEP 12 QA에서 발견 — 받침 없는 음절인 '시간', '가'는 정상 렌더링됨,
TROUBLESHOOTING.md 참고). Plotly의 기본 y축 제목은 항상 90도 회전되어 그려지므로,
이 버그를 피하려면 회전된 축 제목 대신 가로로 눕힌 텍스트 주석을 써야 한다.
"""
from pathlib import Path

import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

FONT_FAMILY = "Malgun Gothic, Apple SD Gothic Neo, sans-serif"


def set_horizontal_yaxis_label(fig: go.Figure, text: str, x: float = 0.0, y: float = 1.0,
                                xanchor: str = "right") -> None:
    """y축 제목을(회전 없이) 플롯 영역 왼쪽 위 모서리 바로 위에 가로로 표시한다.
    받침 있는 한글이 회전 렌더링에서 깨지는 Kaleido 버그를 피하기 위한 대체 방법이다.

    범례를 쓰는 차트는 legend의 y를 1.02 근처(플롯 바로 위)로 두면 이 레이블과 겹치지
    않는다 — legend를 제목과 같은 높이(1.1~1.2)에 두면 이 레이블과 겹친다.
    """
    fig.update_yaxes(title=None)
    fig.add_annotation(
        text=text, xref="paper", yref="paper", x=x, y=y,
        showarrow=False, xanchor=xanchor, yanchor="bottom",
        font=dict(family=FONT_FAMILY, size=12),
    )
