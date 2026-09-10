# 데이터 출처 (Provenance)

이 프로젝트가 사용하는 모든 원본 데이터의 출처·라이선스·역할을 기록한다.
행수·열수는 `src/data/inspect_raw.py` 실행 결과(`data/interim/raw_inventory.csv`)에서 그대로 가져온 실측값이다.

| 데이터셋명 | 출처 URL | 원저자/기관 | 라이선스 | 다운로드일 | 파일 경로 | 행수 | 열수 | 이 프로젝트에서의 역할 (OEE의 A/P/Q) |
|---|---|---|---|---|---|---|---|---|
| Microsoft Azure Predictive Maintenance — telemetry | https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance | Microsoft (Kaggle 재게시: arnabbiswas1) | Kaggle 데이터셋 라이선스 (재배포 시 출처 명시) | 2026-09-08 | `azure_pdm/PdM_telemetry.csv` | 876,100 | 6 | 가동률(A) — 센서 열화로 고장 전조 탐지 |
| Microsoft Azure Predictive Maintenance — errors | 〃 | 〃 | 〃 | 2026-09-08 | `azure_pdm/PdM_errors.csv` | 3,919 | 3 | 가동률(A) — 고장으로 이어지지 않은 경고 이력 |
| Microsoft Azure Predictive Maintenance — maint | 〃 | 〃 | 〃 | 2026-09-08 | `azure_pdm/PdM_maint.csv` | 3,286 | 3 | 가동률(A) — MTTR 계산용 부품 교체 이력 |
| Microsoft Azure Predictive Maintenance — failures | 〃 | 〃 | 〃 | 2026-09-08 | `azure_pdm/PdM_failures.csv` | 761 | 3 | 가동률(A) — MTBF 계산용 고장 이력 (STEP 3 핵심 입력) |
| Microsoft Azure Predictive Maintenance — machines | 〃 | 〃 | 〃 | 2026-09-08 | `azure_pdm/PdM_machines.csv` | 100 | 3 | 설비 메타정보 (모델·설치연차) |
| APS Failure at Scania Trucks — training | https://archive.ics.uci.edu/dataset/421/aps+failure+at+scania+trucks | Scania CV AB / UCI ML Repository | GPL-3.0 (Scania CV AB, 2016) | 2026-09-08 | `aps_scania/aps_failure_training_set.csv` | 60,000 | 171 | 품질(Q) — 비용민감 고장예측 학습 (STEP 8) |
| APS Failure at Scania Trucks — test | 〃 | 〃 | 〃 | 2026-09-08 | `aps_scania/aps_failure_test_set.csv` | 16,000 | 171 | 품질(Q) — 비용민감 고장예측 평가 (STEP 8) |

## 라이선스 주의사항

- **APS Scania 데이터는 GPL-3.0**이다. 원본 CSV 앞부분에 라이선스 전문이 포함되어 있으며(`data/raw/aps_scania/*.csv` 첫 20줄),
  이 프로젝트는 원본 파일을 수정하지 않고 그대로 보관한다(절대 규칙 2).
- Azure PdM 데이터는 Kaggle 재게시본이며, 원 데이터는 Microsoft가 예지보전 튜토리얼용으로 공개한 것이다.
  재사용 시 출처 표기를 유지한다.

## 실측 라벨 분포 (2026-09-08, `inspect_raw.py` 실행 결과)

- APS Scania training: `neg 98.33% / pos 1.67%` (60,000행 중 1,000건 고장)
- APS Scania test: `neg 97.66% / pos 2.34%` (16,000행 중 375건 고장, neg 15,625건)
- Azure PdM failures 부품별 비중: comp2 34.0% / comp1 25.2% / comp4 23.5% / comp3 17.2% (761건 중)

## 참고 — 검토했으나 채택하지 않은 데이터

- **AI4I 2020 Predictive Maintenance** (원 계획서에서 sim2 재활용 대상으로 언급됨): 이 프로젝트는 기존 sim1~sim5 자산이
  이 PC에 존재하지 않아 처음부터 새로 설계하기로 했으므로(README.md 참고), AI4I는 이번 데이터 소싱에 포함하지 않았다.
- **Steel Plates Faults**, **KAMP CNC/프레스**: 예비 후보로만 검토, 미다운로드.
