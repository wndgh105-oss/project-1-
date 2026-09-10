"""SimPy 기반 5공정 직렬 가상 생산라인 (디지털트윈).

라인 구조: [가공1] -> B1 -> [가공2] -> B2 -> [열처리] -> B3 -> [조립] -> B4 -> [검사]

개발 단계 (한 번에 다 만들면 어디가 틀렸는지 못 찾으므로 단계별로 검증한다):
  1단계 (완료): 고장 없음, 불량 없음, 버퍼 무한 — 이론적 최대 UPH와 비교 검증.
  2단계 (완료): STEP 3 실측 MTBF/MTTR(comp1~4)을 주입해 고장·수리 모델링.
  3단계 (현재 파일): 불량률, 예방보전(PM), 유한 버퍼(블로킹/기아) 추가.

절대 규칙: cycle_times 기본값은 실측 데이터가 아니라 이 프로젝트가 처음부터 설계한
가상 라인의 시나리오 파라미터다(sim1~5 미재활용 결정에 따라 실제 SALBP 결과가 없음).
MTBF/MTTR은 STEP 3(src/kpi/reliability.py)에서 계산한 실측값을 공정에 매핑해 재사용한다
(매핑 자체는 가정, 매핑된 숫자는 실측). defect_rates는 실측 불량 데이터가 아직 없어
기본값 0으로 둔다(STEP 8 비용민감 모델 결과가 나오면 대체 가능하도록 인자로만 열어둠).
"""
import random
from pathlib import Path

import pandas as pd
import simpy

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"

PROCESSES = ["가공1", "가공2", "열처리", "조립", "검사"]

# 설계 가정치 — 실제 라인 실측값이 아니다. 열처리를 의도적으로 병목(최대 CT)으로 설계했다.
DEFAULT_CYCLE_TIMES = {
    "가공1": 45.0,
    "가공2": 50.0,
    "열처리": 60.0,
    "조립": 55.0,
    "검사": 40.0,
}

# STEP 3 실측값(data/interim/mtbf_mttr_by_component.parquet, 2026-09-08 실행 결과)을
# 공정에 매핑한 것. 매핑(어느 공정=어느 부품)은 가정이지만 숫자 자체는 실측이다.
# 검사는 대응 부품이 없어 설비 단위 전체 평균(mtbf_mttr.parquet)을 재사용했다.
DEFAULT_MTBF_HOURS = {
    "가공1": 3045.158730,  # comp1
    "가공2": 2561.567308,  # comp2
    "열처리": 2176.386364,  # comp3
    "조립": 2328.657292,  # comp4
    "검사": 1410.72,  # 설비 단위 전체 평균 (대응 부품 없음)
}
DEFAULT_MTTR_HOURS = {
    "가공1": 36.015625,  # comp1
    "가공2": 23.200772,  # comp2
    "열처리": 24.435115,  # comp3
    "조립": 12.653631,  # comp4
    "검사": 19.98,  # 설비 단위 전체 평균
}

# 실측 불량 데이터 없음 — 기본값 0 (STEP 8 이후 실측값으로 교체 가능하도록 인자로만 열어둠)
DEFAULT_DEFECT_RATES = {p: 0.0 for p in PROCESSES}

# 공정 사이 버퍼 4개(B1~B4). 각 버퍼는 "그 버퍼가 채우는 다음 공정" 이름으로 표기한다.
BUFFER_KEYS = PROCESSES[1:]  # ["가공2", "열처리", "조립", "검사"]
DEFAULT_BUFFER_CAPS = {p: 5 for p in BUFFER_KEYS}  # 설계변수, 기본 5


def run_line(
    cycle_times: dict[str, float] | None = None,
    mtbf: dict[str, float] | None = None,
    mttr: dict[str, float] | None = None,
    defect_rates: dict[str, float] | None = None,
    buffer_caps: dict[str, int] | None = None,
    pm_interval: float = 0.0,
    pm_duration: float = 0.0,
    sim_time: float = 480.0,
    seed: int = 42,
    verbose: bool = False,
    scenario_id: str = "base",
) -> pd.DataFrame:
    """5공정 직렬 라인을 시뮬레이션하고 KPI_SCHEMA 형식의 DataFrame을 반환한다.

    3단계 구현 범위: cycle_times, mtbf/mttr, defect_rates, buffer_caps, pm_interval/duration
    전부 반영한다.

    고장 모델링(비선점형 근사): 공정이 고장 나면 "다음 부품을 새로 시작하기 전"에
    수리가 끝날 때까지 대기한다. 가공 도중 중간에 끊기지는 않는다 — 코드를 이해하기
    쉽게 유지하기 위한 의도적 근사다.

    PM(예방보전)은 라인 전체가 동시에 멈추는 계획정지로 모델링한다(공정별 PM이 아님) —
    실제 현장에서도 전체 라인을 세우고 하는 정기 보전이 흔하기 때문이다.

    버퍼 용량 0은 SimPy Store가 지원하지 않아(capacity must be > 0) 최소 1로 대체한다 —
    완전한 "무버퍼 동기식 전달"을 표현하려면 별도 메커니즘이 필요하나 이 프로젝트 범위를
    벗어난다(TROUBLESHOOTING.md 참고).
    """
    cycle_times = cycle_times or DEFAULT_CYCLE_TIMES
    if set(cycle_times) != set(PROCESSES):
        raise ValueError(f"cycle_times는 {PROCESSES} 5개 공정을 모두 가져야 함: {list(cycle_times)}")

    mtbf = mtbf or DEFAULT_MTBF_HOURS
    mttr = mttr or DEFAULT_MTTR_HOURS
    defect_rates = defect_rates or DEFAULT_DEFECT_RATES
    buffer_caps = buffer_caps or DEFAULT_BUFFER_CAPS
    mtbf_sec = {k: v * 3600 for k, v in mtbf.items()}
    mttr_sec = {k: v * 3600 for k, v in mttr.items()}

    env = simpy.Environment()
    sim_time_sec = sim_time * 60  # 분 -> 초 (cycle_times가 초 단위이므로)
    pm_interval_sec = pm_interval * 60
    pm_duration_sec = pm_duration * 60

    buffer_caps_clamped = {k: max(1, int(v)) for k, v in buffer_caps.items()}
    buffers = [simpy.Store(env, capacity=buffer_caps_clamped[BUFFER_KEYS[i]]) for i in range(len(BUFFER_KEYS))]

    output_log: list[float] = []
    defective_count = 0

    station_up = [True] * len(PROCESSES)
    down_event = [env.event() for _ in range(len(PROCESSES))]
    total_down_time = [0.0] * len(PROCESSES)
    n_failures = [0] * len(PROCESSES)

    blocking_time = [0.0] * len(PROCESSES)  # 다음 버퍼가 가득 차서 못 넘긴 시간
    starvation_time = [0.0] * len(PROCESSES)  # 앞 버퍼가 비어서 못 받은 시간

    line_paused = [False]
    pm_event = [env.event()]
    total_pm_time = [0.0]

    class Part:
        """라인을 흐르는 부품 1개. defective 플래그는 어느 공정에서든 한 번 True가 되면
        이후 계속 유지된다(중간에 고쳐지지 않음 — 최종 검사에서만 판정)."""
        __slots__ = ("defective",)

        def __init__(self):
            self.defective = False

    def wait_until_ready(idx: int):
        """이 공정이 (고장 복구 + PM 종료) 둘 다 끝날 때까지 대기."""
        while not station_up[idx] or line_paused[0]:
            if not station_up[idx] and line_paused[0]:
                yield down_event[idx] | pm_event[0]
            elif not station_up[idx]:
                yield down_event[idx]
            else:
                yield pm_event[0]

    def station(idx: int):
        nonlocal defective_count
        name = PROCESSES[idx]
        ct = cycle_times[name]
        defect_rng = random.Random(seed * 3000 + idx)  # 불량 판정 전용 독립 스트림

        while True:
            if idx == 0:
                part = Part()  # 원자재 무한 가정 — 새 부품을 바로 만듦
            else:
                t0 = env.now
                part = yield buffers[idx - 1].get()
                starvation_time[idx] += env.now - t0

            yield from wait_until_ready(idx)

            yield env.timeout(ct)

            if defect_rng.random() < defect_rates.get(name, 0.0):
                part.defective = True

            if idx < len(PROCESSES) - 1:
                t0 = env.now
                yield buffers[idx].put(part)
                blocking_time[idx] += env.now - t0
            else:
                output_log.append(env.now)
                if part.defective:
                    defective_count += 1

            if verbose:
                print(f"[{env.now:10.1f}s] {name} 1개 처리 완료 (불량={part.defective})")

    def breakdown(idx: int):
        name = PROCESSES[idx]
        rng = random.Random(seed * 1000 + idx)
        while True:
            time_to_failure = rng.expovariate(1 / mtbf_sec[name])
            yield env.timeout(time_to_failure)

            station_up[idx] = False
            n_failures[idx] += 1
            down_start = env.now
            if verbose:
                print(f"[{env.now:10.1f}s] *** {name} 고장 발생 ***")

            repair_time = rng.expovariate(1 / mttr_sec[name])
            yield env.timeout(repair_time)

            station_up[idx] = True
            total_down_time[idx] += env.now - down_start
            if verbose:
                print(f"[{env.now:10.1f}s] *** {name} 수리 완료 (다운타임 {repair_time:.1f}s) ***")

            old_event = down_event[idx]
            down_event[idx] = env.event()
            old_event.succeed()

    def pm_process():
        if pm_interval_sec <= 0:
            return
        while True:
            yield env.timeout(pm_interval_sec)
            line_paused[0] = True
            pm_start = env.now
            if verbose:
                print(f"[{env.now:10.1f}s] === 전체 라인 예방보전(PM) 시작 ===")
            yield env.timeout(pm_duration_sec)
            line_paused[0] = False
            total_pm_time[0] += env.now - pm_start
            if verbose:
                print(f"[{env.now:10.1f}s] === PM 종료 ===")
            old_event = pm_event[0]
            pm_event[0] = env.event()
            old_event.succeed()

    for i in range(len(PROCESSES)):
        env.process(station(i))
        env.process(breakdown(i))
    env.process(pm_process())

    env.run(until=sim_time_sec)

    total_output = len(output_log)
    good_output = total_output - defective_count
    bottleneck_ct = max(cycle_times.values())
    bottleneck_process = max(cycle_times, key=cycle_times.get)
    bottleneck_idx = PROCESSES.index(bottleneck_process)

    # 라인 전체 처리량은 병목공정이 좌우하므로(TOC 관점), 병목공정의 실제 다운타임 +
    # 라인 전체가 멈추는 PM 시간을 합쳐 Availability·실가동시간을 계산한다.
    bottleneck_down = total_down_time[bottleneck_idx] + total_pm_time[0]
    availability = (sim_time_sec - bottleneck_down) / sim_time_sec if sim_time_sec > 0 else 0.0
    quality = good_output / total_output if total_output > 0 else 0.0
    run_time_sec = sim_time_sec - bottleneck_down
    performance = (bottleneck_ct * total_output) / run_time_sec if run_time_sec > 0 else 0.0
    oee = availability * performance * quality
    uph = good_output / (sim_time / 60) if sim_time > 0 else 0.0

    if verbose:
        print(f"\n총 생산량: {total_output}개 (양품 {good_output}, 불량 {defective_count}), 병목공정: {bottleneck_process}({bottleneck_ct}s)")
        print(f"PM 총 시간: {total_pm_time[0] / 3600:.2f}시간")
        print("공정별 고장/블로킹/기아:")
        for i, name in enumerate(PROCESSES):
            print(f"  {name}: 고장 {n_failures[i]}회 {total_down_time[i] / 3600:.2f}h, "
                  f"블로킹 {blocking_time[i] / 3600:.2f}h, 기아 {starvation_time[i] / 3600:.2f}h")

    timestamp = pd.Timestamp.now()
    rows = [
        {"process": bottleneck_process, "kpi_name": "availability", "kpi_value": availability, "unit": "ratio"},
        {"process": bottleneck_process, "kpi_name": "performance", "kpi_value": performance, "unit": "ratio"},
        {"process": bottleneck_process, "kpi_name": "quality", "kpi_value": quality, "unit": "ratio"},
        {"process": bottleneck_process, "kpi_name": "oee", "kpi_value": oee, "unit": "ratio"},
        {"process": bottleneck_process, "kpi_name": "uph", "kpi_value": uph, "unit": "count/hour"},
        {"process": bottleneck_process, "kpi_name": "bottleneck_ct", "kpi_value": bottleneck_ct, "unit": "sec"},
        {"process": bottleneck_process, "kpi_name": "defect_ppm", "kpi_value": (defective_count / total_output * 1_000_000) if total_output > 0 else 0.0, "unit": "ppm"},
    ]
    for name in PROCESSES:
        rows.append({"process": name, "kpi_name": "mtbf", "kpi_value": mtbf[name], "unit": "hour"})
        rows.append({"process": name, "kpi_name": "mttr", "kpi_value": mttr[name], "unit": "hour"})

    df = pd.DataFrame(rows)
    df["scenario_id"] = scenario_id
    df["source"] = "line_sim"
    df["ci_low"] = float("nan")
    df["ci_high"] = float("nan")
    df["run_id"] = f"line_sim_seed{seed}"
    df["timestamp"] = timestamp

    ordered_cols = ["scenario_id", "source", "process", "kpi_name", "kpi_value", "unit", "ci_low", "ci_high", "run_id", "timestamp"]
    return df[ordered_cols]


if __name__ == "__main__":
    print("=== 3단계: 8시간(480분), 버퍼=5, PM 없음 ===")
    r1 = run_line(verbose=False)
    print(r1[r1["kpi_name"].isin(["availability", "performance", "quality", "oee", "uph", "defect_ppm"])].to_string(index=False))

    print("\n=== 재현성 확인 (같은 seed 2회) ===")
    r2 = run_line()
    print("동일 여부:", r1["kpi_value"].reset_index(drop=True).equals(r2["kpi_value"].reset_index(drop=True)))

    print("\n=== 버퍼 0 vs 20 비교 (8시간) ===")
    r_buf0 = run_line(buffer_caps={k: 0 for k in BUFFER_KEYS})
    r_buf20 = run_line(buffer_caps={k: 20 for k in BUFFER_KEYS})
    for label, r in [("buffer=0", r_buf0), ("buffer=20", r_buf20)]:
        oee = r.loc[r["kpi_name"] == "oee", "kpi_value"].iloc[0]
        uph = r.loc[r["kpi_name"] == "uph", "kpi_value"].iloc[0]
        print(f"{label}: OEE={oee:.4f}, UPH={uph:.2f}")

    print("\n=== PM 유무 비교 (8시간, PM 200분 주기 30분 소요) ===")
    r_no_pm = run_line()
    r_with_pm = run_line(pm_interval=200, pm_duration=30)
    for label, r in [("PM 없음", r_no_pm), ("PM 있음", r_with_pm)]:
        avail = r.loc[r["kpi_name"] == "availability", "kpi_value"].iloc[0]
        print(f"{label}: Availability={avail:.4f}")
