"""Streamlit 페이지: 데이터 출처 — PROVENANCE.md 렌더링, 이 프로젝트의 한계, 재현 방법.

한계 섹션은 이 프로젝트에서 실제로 있었던 결정만 정직하게 기술한다.
(원 계획서 템플릿이 언급한 AI4I·Bosch는 애초에 이 프로젝트가 안 쓴 데이터라 그대로
베끼지 않고, 실제로 무엇을 왜 안 썼는지로 대체했다 — README.md 2026-09-08 결정 참고.)
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="데이터 출처", layout="wide")
st.title("데이터 출처 및 재현 방법")


@st.cache_data
def load_provenance_text() -> str:
    path = ROOT / "data" / "raw" / "PROVENANCE.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


provenance_text = load_provenance_text()
if provenance_text:
    st.markdown(provenance_text)
else:
    st.info("data/raw/PROVENANCE.md가 없습니다.")

st.divider()

st.subheader("이 프로젝트의 한계")
st.markdown("""
- **SimPy 가상라인은 실제 파워트레인 라인이 아니라 가정한 5공정 모델이다.** 원래 계획은
  기존 시뮬레이션 자산(sim1~sim5: SECOM/AI4I/ft10/RSW/SALBP)을 재활용하는 것이었으나,
  해당 자산이 이 작업 환경(PC)에 존재하지 않아 이 프로젝트는 라인 구조·사이클타임을
  처음부터 설계했다(README.md 2026-09-08 결정). 사이클타임(`DEFAULT_CYCLE_TIMES`)은
  실측이 아니라 설계 가정치다.
- **AI4I 2020 Predictive Maintenance는 이번 프로젝트에서 아예 사용하지 않았다.**
  원 계획서는 AI4I를 sim2 재활용 대상으로 언급했지만, sim1~5를 재활용하지 않기로
  결정하면서 AI4I 데이터 자체도 검토 후 미채택으로 처리했다(대신 Azure Predictive
  Maintenance 실측 데이터만 사용). Bosch Production Line Performance(14.3GB) 같은
  대용량 공개데이터는 애초에 이 프로젝트의 데이터 소싱 후보에 포함되지 않았다 —
  검토 자체를 하지 않았으므로 "용량 문제로 제외했다"고 말하는 것도 부정확하다.
- **공정-부품 매핑(가공1=comp1, 가공2=comp2, 열처리=comp3, 조립=comp4)은 임의 가정이다.**
  MTBF/MTTR 수치 자체는 Azure PdM 실측값이지만, "어느 라인 공정이 어느 실제 부품에
  대응하는가"는 실측 근거가 없어 순서대로 매핑했다. 5번째 공정(검사)은 대응되는
  부품이 없어 설비 단위 전체 평균을 재사용했다.
- **8시간(480분) 시프트 시뮬레이션에서는 버퍼·PM 효과가 잘 드러나지 않는다.**
  실측 MTBF가 수천 시간 단위로 매우 높아, 8시간 창 안에서는 고장이 거의 발생하지
  않는다. 버퍼 크기를 늘려도 흡수할 변동 자체가 없어 OEE가 그대로다
  (TROUBLESHOOTING.md 2026-09-08 참고). 이 현상을 재현하려면 시뮬레이션 기간을
  훨씬 길게(예: MTBF와 비슷한 수백 일) 잡아야 한다.
- **생산계획(FCFS/SPT) 페이지의 잡 처리시간도 설계 가정치다.** ft10 같은 표준 벤치마크를
  가져오는 대신, 이 라인의 사이클타임에 ±20% 시드 고정 난수를 곱해 6개 잡 시나리오를
  만들었다 — 실제 주문 데이터가 아니다.
- **품질 SPC 페이지의 관리도·Cp/Cpk는 이 프로젝트가 새로 측정한 데이터가 아니다.**
  이전에 만든 포트폴리오 산출물(`data/legacy/용접_SPC_대시보드.xlsx`)을 그대로
  재사용한 것이다(`data/legacy/README.md` 참고).
- **APS Scania 데이터는 클래스가 심하게 불균형하다** (pos 1.67~2.34%). STEP 8의
  비용최적 모델도 이 불균형을 극복하려는 시도이지 완전히 없앤 것은 아니다 — 비용최적
  임계값(0.05)에서 Precision은 34.2%로 낮다(과검이 여전히 많다는 뜻).
- **비용 수치(과검=10, 미검=500)는 APS Scania 대회가 정한 기준**이며, 실제 정비 원가나
  이 라인의 실제 비용 구조를 반영한 것이 아니다.
""")

st.divider()

st.subheader("재현 방법")
st.markdown("""
아래 순서대로 실행하면 이 대시보드의 모든 수치를 그대로 재현할 수 있다 (모든 랜덤 요소는
`seed=42`로 고정되어 있어 같은 환경이면 같은 결과가 나온다).

1. `python -m src.data.inspect_raw` — 원본 데이터 인벤토리 (`data/interim/raw_inventory.csv`)
2. `python -m src.kpi.reliability` — MTBF/MTTR 계산 (`data/interim/mtbf_mttr*.parquet`)
3. `python -m src.simulation.build_scenarios` — 시나리오 그리드 + base KPI (`data/processed/scenario_grid.parquet`, `kpi.parquet`)
4. `python -m src.models.pdm_cost_sensitive` — 비용민감 모델 (`data/processed/cost_curve.parquet`, `models/*.joblib`, `kpi.parquet`에 추가)
5. `streamlit run app/main.py` — 대시보드 실행

3번과 4번은 둘 다 `kpi.parquet`에 쓰므로, 완전히 새로 재현하려면 `data/processed/kpi.parquet`을
지우고 3번 → 4번 순서로 다시 실행해야 한다(순서가 바뀌어도 `append_kpi`가 중복을 덮어써서
결과는 같다 — TROUBLESHOOTING.md 2026-09-08 참고).
""")
