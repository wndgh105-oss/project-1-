"""실측 정비이력(failures, maint)에서 MTBF·MTTR·Availability를 계산한다.

왜 필요한가: STEP 6(SimPy 가상라인)에 넣을 고장/수리 파라미터를 추정값이 아니라
실제 데이터에서 뽑아야 한다(절대 규칙 1). 여기서 나온 숫자가 그대로 시뮬레이션 입력이 된다.

데이터 특성(중요): Azure PdM의 timestamp는 일 단위 해상도만 가진다(대부분 06:00).
그래서 같은 날 수리된 고장은 MTTR=0시간으로 계산된다 — 이는 계산 오류가 아니라
원본 데이터의 시간 해상도 한계다. 이 사실은 TROUBLESHOOTING.md에 별도로 기록한다.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "azure_pdm"
INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    failures = pd.read_csv(RAW / "PdM_failures.csv", parse_dates=["datetime"])
    maint = pd.read_csv(RAW / "PdM_maint.csv", parse_dates=["datetime"])

    # 중복 이벤트 제거 (같은 설비·부품·시각이 두 번 기록된 경우)
    n_fail_before, n_maint_before = len(failures), len(maint)
    failures = failures.drop_duplicates()
    maint = maint.drop_duplicates()
    if len(failures) != n_fail_before:
        print(f"[경고] failures 중복 {n_fail_before - len(failures)}건 제거")
    if len(maint) != n_maint_before:
        print(f"[경고] maint 중복 {n_maint_before - len(maint)}건 제거")

    failures = failures.rename(columns={"failure": "comp"}).sort_values(["machineID", "datetime"])
    maint = maint.sort_values(["machineID", "comp", "datetime"])
    return failures, maint


def compute_mtbf_by_machine(failures: pd.DataFrame) -> pd.DataFrame:
    """설비별 MTBF(시간) = 연속된 고장 시각 차이의 평균."""
    rows = []
    excluded = 0
    for machine_id, group in failures.groupby("machineID"):
        times = group["datetime"].sort_values()
        if len(times) < 2:
            # 고장이 1회뿐이면 '간격'이 정의되지 않는다 → NaN 처리 + 제외 건수 카운트
            rows.append({"machineID": machine_id, "mtbf_hours": float("nan"), "n_failures": len(times)})
            excluded += 1
            continue
        diffs_hours = times.diff().dropna().dt.total_seconds() / 3600
        if (diffs_hours < 0).any():
            print(f"[경고] machineID={machine_id}: 음수 시간차 발견 — 정렬/매칭 오류 가능성")
        rows.append({"machineID": machine_id, "mtbf_hours": diffs_hours.mean(), "n_failures": len(times)})

    print(f"MTBF 계산: 고장 1회뿐이라 제외된 설비 {excluded}대 (전체 {failures['machineID'].nunique()}대 중)")
    return pd.DataFrame(rows)


def compute_mtbf_by_component(failures: pd.DataFrame) -> pd.DataFrame:
    """부품별 MTBF(시간) = (설비, 부품) 쌍별 MTBF를 구한 뒤 부품별로 평균낸 값."""
    pair_rows = []
    for (machine_id, comp), group in failures.groupby(["machineID", "comp"]):
        times = group["datetime"].sort_values()
        if len(times) < 2:
            continue
        diffs_hours = times.diff().dropna().dt.total_seconds() / 3600
        pair_rows.append({"machineID": machine_id, "comp": comp, "mtbf_hours": diffs_hours.mean()})

    pair_df = pd.DataFrame(pair_rows)
    return pair_df.groupby("comp")["mtbf_hours"].agg(["mean", "count"]).rename(
        columns={"mean": "mtbf_hours", "count": "n_machines_used"}
    ).reset_index()


def compute_mttr(failures: pd.DataFrame, maint: pd.DataFrame) -> pd.DataFrame:
    """고장 시각부터, 같은 설비·부품의 다음 정비(교체) 시각까지의 시간(MTTR, 시간 단위)."""
    rows = []
    unmatched = 0
    for _, row in failures.iterrows():
        candidates = maint[
            (maint["machineID"] == row["machineID"])
            & (maint["comp"] == row["comp"])
            & (maint["datetime"] >= row["datetime"])
        ]
        if candidates.empty:
            unmatched += 1
            rows.append({"machineID": row["machineID"], "comp": row["comp"], "mttr_hours": float("nan")})
            continue
        repair_time = candidates["datetime"].min()
        delta_hours = (repair_time - row["datetime"]).total_seconds() / 3600
        if delta_hours < 0:
            print(f"[경고] machineID={row['machineID']} comp={row['comp']}: 음수 MTTR — 매칭 오류")
        rows.append({"machineID": row["machineID"], "comp": row["comp"], "mttr_hours": delta_hours})

    print(f"MTTR 계산: 매칭되는 정비 기록이 없어 제외된 고장 {unmatched}건 (전체 {len(failures)}건 중)")
    return pd.DataFrame(rows)


def compute_mttr_by_component(mttr_events: pd.DataFrame) -> pd.DataFrame:
    """부품별 MTTR(시간) = compute_mttr()이 만든 이벤트별 delta를 부품(comp)별로 평균낸 값.

    왜 필요한가: STEP 6 SimPy 라인은 공정(가공1~검사)마다 고장·수리 파라미터가 필요한데,
    설비 단위 평균만 있으면 공정별 차이를 반영할 수 없다. comp1~4는 실제 부품 단위 통계라
    라인의 개별 공정에 매핑해서 쓸 수 있다.
    """
    return mttr_events.groupby("comp")["mttr_hours"].agg(["mean", "count"]).rename(
        columns={"mean": "mttr_hours", "count": "n_events"}
    ).reset_index()


def main():
    failures, maint = _load()

    mtbf_machine = compute_mtbf_by_machine(failures)
    mtbf_comp = compute_mtbf_by_component(failures)
    mttr_events = compute_mttr(failures, maint)
    mttr_comp = compute_mttr_by_component(mttr_events)

    mttr_by_machine = mttr_events.groupby("machineID")["mttr_hours"].mean().reset_index()

    summary = mtbf_machine.merge(mttr_by_machine, on="machineID", how="left")
    summary["availability"] = summary["mtbf_hours"] / (summary["mtbf_hours"] + summary["mttr_hours"])

    out_path = INTERIM / "mtbf_mttr.parquet"
    summary.to_parquet(out_path, index=False)

    comp_path = INTERIM / "mtbf_mttr_by_component.parquet"
    comp_summary = mtbf_comp.merge(mttr_comp, on="comp", how="outer", suffixes=("_mtbf", "_mttr"))
    comp_summary.to_parquet(comp_path, index=False)

    print(f"\n{'=' * 60}")
    print("설비 단위 전체 평균 (NaN 제외):")
    print(f"  MTBF: {summary['mtbf_hours'].mean():.2f}시간")
    print(f"  MTTR: {summary['mttr_hours'].mean():.2f}시간")
    print(f"  Availability: {summary['availability'].mean() * 100:.2f}%")

    print("\nMTBF 상위 5개 설비 (고장이 뜸한 순):")
    print(summary.nlargest(5, "mtbf_hours")[["machineID", "mtbf_hours", "n_failures"]].to_string(index=False))
    print("\nMTBF 하위 5개 설비 (고장이 잦은 순):")
    print(summary.nsmallest(5, "mtbf_hours")[["machineID", "mtbf_hours", "n_failures"]].to_string(index=False))

    print("\n부품별 MTBF·MTTR (STEP 6 SimPy 라인 입력값):")
    print(comp_summary.to_string(index=False))

    print(f"\n저장: {out_path.relative_to(ROOT)}, {comp_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
