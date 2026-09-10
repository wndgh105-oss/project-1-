"""app/pages/1_설비예지보전.py가 쓰는 두 개의 무거운 계산(고장 파레토, 센서 전조 비교)을
미리 만들어 data/interim에 저장한다.

왜 필요한가: 이 두 계산은 원래 앱이 매번 data/raw/azure_pdm/PdM_telemetry.csv(80MB)를
직접 읽어서 했다. 로컬에서는 문제 없지만, STEP 13 배포 준비 중 data/raw/ 전체를
저장소에서 제외하기로 하면서(용량 + "원본은 읽기 전용" 원칙) 배포 환경에는 이 파일이
아예 없다는 게 드러났다 — 배포하면 페이지1이 바로 깨질 뻔한 문제였다(TROUBLESHOOTING.md
2026-09-10 참고). 다른 KPI들처럼 이 결과도 실측값이므로, "계산 결과만" data/interim에
저장해두고 앱은 그걸 읽게 바꾼다. 원본 원리는 그대로(값은 동일), 배포 시 무거운 raw
CSV를 저장소에 넣지 않아도 되는 것만 다르다.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "azure_pdm"
INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)


def compute_failure_pareto() -> pd.DataFrame:
    failures = pd.read_csv(RAW / "PdM_failures.csv")
    counts = failures["failure"].value_counts().rename_axis("failure").reset_index(name="count")
    return counts


def compute_sensor_precursor() -> pd.DataFrame:
    """app/pages/1_설비예지보전.py의 load_sensor_precursor()와 동일한 계산 — 실행 위치만
    옮겼다(TROUBLESHOOTING.md 2026-09-10, machineID 그룹핑 최적화도 그대로 유지)."""
    telemetry = pd.read_csv(RAW / "PdM_telemetry.csv", parse_dates=["datetime"])
    failures = pd.read_csv(RAW / "PdM_failures.csv", parse_dates=["datetime"])
    sensors = ["volt", "rotate", "pressure", "vibration"]

    telemetry_by_machine = {
        machine_id: group.set_index("datetime")
        for machine_id, group in telemetry.sort_values(["machineID", "datetime"]).groupby("machineID")
    }

    pre_failure_rows = []
    for _, row in failures.iterrows():
        machine_telemetry = telemetry_by_machine.get(row["machineID"])
        if machine_telemetry is None:
            continue
        window = machine_telemetry.loc[
            (machine_telemetry.index < row["datetime"])
            & (machine_telemetry.index >= row["datetime"] - pd.Timedelta(hours=24))
        ]
        if len(window) == 0:
            continue
        pre_failure_rows.append(window[sensors].mean())

    pre_failure_avg = pd.DataFrame(pre_failure_rows).mean()
    overall_avg = telemetry[sensors].mean()
    compare = pd.DataFrame({"평상시 평균": overall_avg, "고장 직전 24h 평균": pre_failure_avg})
    compare["변화율(%)"] = (compare["고장 직전 24h 평균"] - compare["평상시 평균"]) / compare["평상시 평균"] * 100
    return compare.reset_index(names="센서")


def main() -> None:
    pareto = compute_failure_pareto()
    pareto.to_csv(INTERIM / "failure_pareto.csv", index=False)
    print(f"failure_pareto.csv 저장 완료 ({len(pareto)}행)")
    print(pareto)

    precursor = compute_sensor_precursor()
    precursor.to_parquet(INTERIM / "sensor_precursor.parquet", index=False)
    print(f"\nsensor_precursor.parquet 저장 완료 ({len(precursor)}행)")
    print(precursor)


if __name__ == "__main__":
    main()
