"""FCFS vs SPT 디스패칭 규칙 비교 — 플로우샵(모든 잡이 같은 공정 순서를 거침) 스케줄링.

왜 새로 만들었나: 원 계획서는 sim3(ft10 job-shop 벤치마크)를 재활용하려 했으나, 이 프로젝트는
sim1~5 자산이 없어 처음부터 설계하기로 했다(README.md 2026-09-08 결정). ft10 같은 외부
벤치마크를 새로 끌어오는 대신, 이미 만든 라인(src/simulation/line_sim.py)의 5개 공정과
설계 가정 사이클타임을 그대로 이어받아 "여러 잡(Job)을 어떤 순서로 흘리느냐"의 문제로
확장했다.

절대 규칙: JOB_PROCESSING_TIMES는 실측치가 아니라 DEFAULT_CYCLE_TIMES(설계 가정치)에
시드 고정 난수(±20%)를 곱해 만든 시나리오다 — 여러 잡(제품 변형)이 있다고 가정한 것.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.simulation.line_sim import DEFAULT_CYCLE_TIMES, PROCESSES

ROOT = Path(__file__).resolve().parents[2]

N_JOBS = 6
SEED = 42


def generate_job_processing_times(n_jobs: int = N_JOBS, seed: int = SEED) -> dict[str, dict[str, float]]:
    """설계 가정: 각 잡(제품 변형)의 공정별 처리시간을 기본 사이클타임의 80~120% 범위에서
    시드 고정 난수로 생성한다. 실측 데이터가 아니다."""
    rng = np.random.default_rng(seed)
    jobs = {}
    for i in range(n_jobs):
        job_id = f"Job{i + 1}"
        jobs[job_id] = {p: DEFAULT_CYCLE_TIMES[p] * rng.uniform(0.8, 1.2) for p in PROCESSES}
    return jobs


def simulate_flow_shop(processing_times: dict[str, dict[str, float]], rule: str = "FCFS") -> tuple[pd.DataFrame, float]:
    """플로우샵 리스트 스케줄링. 모든 잡이 PROCESSES 순서대로 공정을 거친다고 가정.

    rule="FCFS": 각 공정에서 이전 공정을 먼저 끝낸(도착이 빠른) 잡부터 처리.
    rule="SPT": 각 공정에서 그 공정의 처리시간이 짧은 잡부터 처리(Shortest Processing Time).

    반환: (간트용 스케줄 DataFrame[job, station, start, end], makespan)
    """
    if rule not in ("FCFS", "SPT"):
        raise ValueError(f"rule은 'FCFS' 또는 'SPT'여야 함: {rule}")

    jobs = list(processing_times.keys())
    ready_time = {j: 0.0 for j in jobs}  # 잡이 다음 공정에 투입 가능해지는 시각
    schedule_rows = []

    for station in PROCESSES:
        if rule == "FCFS":
            order = sorted(jobs, key=lambda j: (ready_time[j], jobs.index(j)))
        else:  # SPT
            order = sorted(jobs, key=lambda j: (processing_times[j][station], ready_time[j]))

        current_time = 0.0
        for job in order:
            start = max(current_time, ready_time[job])
            end = start + processing_times[job][station]
            schedule_rows.append({"job": job, "station": station, "start": start, "end": end})
            current_time = end
            ready_time[job] = end

    schedule_df = pd.DataFrame(schedule_rows)
    makespan = schedule_df["end"].max()
    return schedule_df, makespan


if __name__ == "__main__":
    jobs = generate_job_processing_times()
    print(f"잡 {len(jobs)}개, 공정 {len(PROCESSES)}개 (시드 {SEED})")

    for rule in ("FCFS", "SPT"):
        schedule_df, makespan = simulate_flow_shop(jobs, rule=rule)
        print(f"\n=== {rule} ===")
        print(f"메이크스팬: {makespan:.1f}초")

    fcfs_df, fcfs_makespan = simulate_flow_shop(jobs, rule="FCFS")
    spt_df, spt_makespan = simulate_flow_shop(jobs, rule="SPT")
    print(f"\nSPT가 FCFS 대비 메이크스팬 단축: {fcfs_makespan - spt_makespan:.1f}초 "
          f"({(fcfs_makespan - spt_makespan) / fcfs_makespan * 100:.1f}%)")
