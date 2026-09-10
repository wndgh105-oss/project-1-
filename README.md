# PT 파워트레인 라인 통합 KPI·디지털트윈 대시보드

자동차 파워트레인(PT) 생산기술 직무 지원을 위한 포트폴리오 프로젝트.
여러 시뮬레이션·모델의 결과를 하나의 KPI 계약(OEE = 가동률×성능×품질)으로 통합하고,
SimPy 기반 디지털트윈 가상라인과 Streamlit What-if 시뮬레이터로 보여준다.

## 왜 이 프로젝트인가

"시뮬레이션과 대시보드는 만들었지만, 'OEE가 몇 %인가'라는 질문에 하나의 숫자로 답할 수 없었다"는
문제의식에서 출발한다. 각기 다른 형식으로 결과를 내는 여러 분석을 표준 KPI 스키마로 묶고,
실측 정비이력(MTBF/MTTR)을 가상라인에 주입해 "버퍼를 늘리면", "PM 주기를 바꾸면" 같은
질문에 실행 가능한 시뮬레이션으로 답한다.

## 핵심 결과 (실제 실행값)

| 항목 | 값 |
|---|---|
| 기준 시나리오 OEE (8시간, 버퍼 5, PM 없음) | 99.17% (A=100%, P=99.17%, Q=100%) |
| 비용민감 예지보전 모델 절감액 (더미 대비) | 178,830 (95.4% 절감), 임계값 0.05 |
| 몬테카를로 30회 vs 5회 신뢰구간 폭 (장기 시나리오 OEE) | 30회 2.05% vs 5회 7.43% (평균 대비) |
| What-if 시뮬레이터 캐시 조회 vs 실시간 계산 | 2.15ms vs 658ms (약 300배) |
| 시나리오 그리드 30개 × 몬테카를로 30회 총 소요시간 | 20.3초 |

## 진행 경과 메모

- 2026-09-08: 이 프로젝트는 애초 계획서(`단계별 프롬프트.md`)가 가정한 기존 시뮬레이션 자산
  (sim1~sim5: SECOM/AI4I/ft10/RSW/SALBP)이 이 PC에 존재하지 않아, **SimPy 가상라인·스케줄링을
  처음부터 새로 설계**하는 방향으로 진행했다. 기존 대시보드 HTML 2종(사출성형, 용접 SPC)과
  용접 SPC 관리도 엑셀(`data/legacy/`)은 실제로 존재해서 재활용했다.
- 2026-09-10: STEP 12 QA에서 발견한 주요 사항 — Kaleido(PNG 내보내기)가 받침 있는 한글을
  회전된 축 제목으로 그릴 때 깨지는 버그를 발견해 전체 차트를 수정, 설비예지보전 페이지
  로딩 시간을 10.27초→2.19초로 최적화. 자세한 내용은 `TROUBLESHOOTING.md` 참고.
- 2026-09-10: STEP 13 배포 준비 중 `1_설비예지보전.py`가 앱 실행 중에 `data/raw/`의 80MB
  telemetry CSV를 직접 읽는다는 걸 발견 — 배포 저장소에서 `data/raw/`를 빼기로 한 결정과
  충돌해서, 해당 계산을 `src/kpi/precompute_page1.py`로 옮기고 결과만 `data/interim/`에
  저장하도록 구조를 바꿨다. 이 덕분에 배포에 필요한 데이터 총량이 131MB → 약 116KB로
  줄어 Git LFS 없이 그대로 배포 가능해졌다.

## 폴더 구조

```
integrated_dashboard/
├─ data/raw/           원본, 수정 금지 (Azure PdM, APS Scania)
├─ data/interim/       정제 중간물 (MTBF/MTTR, 인벤토리 등)
├─ data/processed/     대시보드가 읽는 최종물 (kpi.parquet, scenario_grid.parquet 등)
├─ data/legacy/        이전에 만든 산출물 재활용 (용접 SPC 엑셀)
├─ notebooks/          Jupyter 탐색용 EDA
├─ src/data/           원본 정제 로직
├─ src/kpi/            KPI 스키마·계산식 (이 프로젝트의 계약 레이어)
├─ src/simulation/     SimPy 가상라인, 몬테카를로, 시나리오 그리드, FCFS/SPT 스케줄링
├─ src/models/         ML 학습 (비용민감 고장예측)
├─ src/viz/            Plotly 차트 함수 (fig_oee, fig_line, fig_quality, fig_sim, common)
├─ models/             학습된 .joblib
├─ figures/            PNG 내보내기 (포트폴리오용)
├─ legacy_html/        기존 대시보드 HTML 2종
├─ docs/               포트폴리오 최종 산출물
├─ app/                Streamlit 대시보드
│  ├─ main.py           Tab 0: 종합
│  └─ pages/            1: 설비예지보전, 2: 품질SPC, 3: 생산계획, 4: 라인밸런싱,
│                        5: What-if 시뮬레이터, 6: 데이터출처
├─ .streamlit/         배포 테마·설정 (config.toml)
├─ requirements.txt     대시보드 실행에만 필요한 최소 패키지 (배포용)
├─ requirements-dev.txt 원본부터 전체 재현(모델 학습 등)에 필요한 나머지 패키지
└─ tests/              KPI 계약 단위 테스트
```

## 실행 방법

```powershell
# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\Activate.ps1

# 패키지 설치 (대시보드만 실행할 거면 이걸로 충분)
pip install -r requirements.txt

# 대시보드 실행
streamlit run app/main.py
```

`data/interim/`, `data/processed/`에 이미 계산 결과가 들어있으므로 위 명령만으로 대시보드가
바로 뜬다. `data/raw/`부터 전체를 다시 계산하려면 아래 "처음부터 전체 재현하기"를 따른다.

## 처음부터 전체 재현하기

모든 랜덤 요소는 `seed=42`로 고정되어 있어 같은 순서로 실행하면 같은 결과가 나온다.
이 단계는 `data/raw/`(원본, 이 저장소엔 포함 안 됨 — `data/raw/PROVENANCE.md`의 출처에서
직접 받아야 함)가 있어야 하고, `requirements-dev.txt`도 추가로 설치해야 한다.

```powershell
pip install -r requirements.txt -r requirements-dev.txt

python -m src.data.inspect_raw            # 원본 데이터 인벤토리
python -m src.kpi.reliability              # MTBF/MTTR 계산
python -m src.kpi.precompute_page1         # 고장 파레토·센서 전조 계산 (설비예지보전 페이지용)
python -m src.simulation.build_scenarios   # 시나리오 그리드 + base KPI
python -m src.models.pdm_cost_sensitive    # 비용민감 모델
streamlit run app/main.py                  # 대시보드 실행
```

## 배포 (Streamlit Community Cloud)

이 대시보드는 `data/processed/`, `data/interim/`, `data/legacy/`에 미리 계산된 결과만
읽으므로(총 용량 약 116KB), `data/raw/`(131MB) 없이도 그대로 배포할 수 있다 — Git LFS는
필요 없다.

1. GitHub에 새 저장소 생성 (Public 또는 Private 둘 다 가능, Private는 Streamlit Cloud
   계정 연동 시 접근 권한만 있으면 됨)
2. 이 폴더에서:
   ```powershell
   git init
   git add .
   git commit -m "대시보드 초기 배포 준비: STEP 13"
   git branch -M main
   git remote add origin <저장소 URL>
   git push -u origin main
   ```
3. [share.streamlit.io](https://share.streamlit.io) 접속 → GitHub 계정 연동 → New app
4. Repository/Branch 선택, Main file path에 `app/main.py` 입력 → Deploy

### 흔한 실패 원인

- **ModuleNotFoundError**: `requirements.txt`에 빠진 패키지가 있는 경우. 이 프로젝트는
  `requirements.txt`(배포용 최소)와 `requirements-dev.txt`(로컬 전체 재현용)를 분리해뒀는데,
  대시보드가 `requirements-dev.txt`의 패키지를 import하도록 잘못 고치면 배포가 깨진다.
- **FileNotFoundError (data/raw/...)**: 어떤 페이지가 `data/raw/`를 직접 읽도록 되돌아가면
  배포 환경엔 그 파일이 없어서 깨진다(이번에 `1_설비예지보전.py`에서 실제로 겪은 문제 —
  TROUBLESHOOTING.md 2026-09-10 참고). `data/interim/`·`data/processed/`만 읽도록 유지할 것.
- **한글 폰트 깨짐**: Streamlit UI 자체 텍스트는 브라우저가 알아서 시스템 한글 폰트로
  대체하지만, Plotly 차트 폰트를 특정 한글 폰트 하나로만 고정하면 그 폰트가 없는 환경에서
  깨질 수 있다. `src/viz/common.py`의 `FONT_FAMILY`가 이미 "Malgun Gothic, Apple SD Gothic
  Neo, sans-serif" 폴백 체인으로 되어 있으니 이 상수를 계속 써야 한다.
- **빈 화면/구버전 표시**: Streamlit Cloud는 GitHub push를 감지해 자동 재배포하지만 캐시가
  남아있을 수 있다 — 앱 메뉴의 "Reboot app"으로 강제 재시작.

### 배포 후 확인 체크리스트

- [ ] 공개 URL 접속 시 6개 페이지(종합/설비예지보전/품질SPC/생산계획/라인밸런싱/What-if/
      데이터출처)가 전부 에러 없이 로딩되는가
- [ ] 모든 한글 텍스트·차트 라벨이 깨지지 않고 표시되는가
- [ ] What-if 시뮬레이터의 슬라이더(버퍼·PM 주기·목표 tact)와 "시뮬레이션 실행" 버튼이
      정상 동작하는가
- [ ] 로컬 대비 로딩 속도 차이를 실제로 재서 기록 (미리 짐작하지 말고 `TROUBLESHOOTING.md`에
      실측값으로 남길 것)
- [ ] 휴대폰 등 다른 기기에서 열어도 정상 동작하는가

## 스크린샷

`figures/` 폴더의 PNG 참고 (`fig_oee_waterfall.png`, `fig_yamazumi.png`, `fig_control_chart.png` 등).
대시보드 자체 화면은 `streamlit run app/main.py` 실행 후 확인.

## 데이터 출처

`data/raw/PROVENANCE.md` 또는 대시보드의 "데이터출처" 페이지(`app/pages/6_데이터출처.py`) 참고 —
출처·라이선스·이 프로젝트의 한계·재현 방법을 함께 정리해뒀다.

## 알려진 이슈 및 진단 기록

`TROUBLESHOOTING.md` 참고 — 지금까지 겪은 문제를 [증상]→[원인]→[해결]→[근거수치] 형식으로 기록했다.
