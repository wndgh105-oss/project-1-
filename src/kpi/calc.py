"""KPI 계산식 모음. 각 함수는 계산식을 docstring에 명시하고, 물리적으로 말이 안 되는
입력(음수 시간, 0으로 나누기 등)은 값을 지어내지 않고 예외로 막는다.
"""


def calc_availability(mtbf: float, mttr: float) -> float:
    """가동률(Availability) = MTBF / (MTBF + MTTR).

    설비가 고장·수리 사이클 중 '가동 가능한' 시간의 비율.
    """
    if mtbf < 0 or mttr < 0:
        raise ValueError(f"MTBF·MTTR은 음수일 수 없음: mtbf={mtbf}, mttr={mttr}")
    if mtbf + mttr == 0:
        raise ValueError("MTBF+MTTR이 0이라 가동률을 정의할 수 없음")
    return mtbf / (mtbf + mttr)


def calc_performance(ideal_ct: float, output: float, run_time: float) -> float:
    """성능(Performance) = (이론 사이클타임 × 생산량) / 실가동시간.

    실제로 낼 수 있었던 최대 생산량 대비, 실제로 낸 생산량의 비율.
    """
    if ideal_ct <= 0:
        raise ValueError(f"이론 사이클타임은 0보다 커야 함: {ideal_ct}")
    if output < 0:
        raise ValueError(f"생산량은 음수일 수 없음: {output}")
    if run_time <= 0:
        raise ValueError(f"실가동시간은 0보다 커야 함: {run_time}")
    return (ideal_ct * output) / run_time


def calc_quality(good: float, total: float) -> float:
    """품질(Quality) = 양품수 / 총생산수."""
    if total <= 0:
        raise ValueError(f"총생산수는 0보다 커야 함: {total}")
    if good < 0 or good > total:
        raise ValueError(f"양품수는 0 이상 총생산수 이하여야 함: good={good}, total={total}")
    return good / total


def calc_oee(a: float, p: float, q: float) -> float:
    """OEE(종합설비효율) = Availability × Performance × Quality.

    A/P/Q 각각은 0~1 비율이어야 한다 (98(%)이 아니라 0.98을 넣을 것).
    """
    for name, v in (("a", a), ("p", p), ("q", q)):
        if not (0 <= v <= 1):
            raise ValueError(f"{name}는 0~1 비율이어야 함 (98을 0.98로 착각했는지 확인): {v}")
    return a * p * q


def calc_uph(output: float, hours: float) -> float:
    """UPH(시간당 생산량) = 생산량 / 가동시간(시간)."""
    if hours <= 0:
        raise ValueError(f"가동시간은 0보다 커야 함: {hours}")
    if output < 0:
        raise ValueError(f"생산량은 음수일 수 없음: {output}")
    return output / hours


def calc_tact(available_time: float, demand: float) -> float:
    """Tact time(초) = 가용시간 / 수요량. '수요를 맞추려면 몇 초에 하나씩 나와야 하는가'."""
    if demand <= 0:
        raise ValueError(f"수요량은 0보다 커야 함: {demand}")
    if available_time <= 0:
        raise ValueError(f"가용시간은 0보다 커야 함: {available_time}")
    return available_time / demand


def calc_ppm(defects: float, total: float) -> float:
    """불량 PPM(백만분율) = 불량수 / 총생산수 × 1,000,000."""
    if total <= 0:
        raise ValueError(f"총생산수는 0보다 커야 함: {total}")
    if defects < 0 or defects > total:
        raise ValueError(f"불량수는 0 이상 총생산수 이하여야 함: defects={defects}, total={total}")
    return defects / total * 1_000_000
