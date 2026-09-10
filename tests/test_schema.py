"""validate_kpi()가 일부러 틀린 데이터를 제대로 막는지 확인하는 테스트.

pytest 없이도 `python tests/test_schema.py`로 바로 실행 가능하도록 순수 assert로 작성했다.
pytest가 있으면 `python -m pytest tests/` 로도 동일하게 실행된다.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kpi.schema import KPI_SCHEMA, validate_kpi  # noqa: E402


def _valid_row(**overrides) -> pd.DataFrame:
    """스키마를 통과하는 정상 행 1개. overrides로 특정 컬럼만 깨뜨려서 재사용한다."""
    row = {
        "scenario_id": "base",
        "source": "test",
        "process": "가공1",
        "kpi_name": "oee",
        "kpi_value": 0.85,
        "unit": "ratio",
        "ci_low": 0.80,
        "ci_high": 0.90,
        "run_id": "run_001",
        "timestamp": pd.Timestamp("2026-09-08"),
    }
    row.update(overrides)
    df = pd.DataFrame([row])
    for col, dtype in KPI_SCHEMA.items():
        if dtype == "datetime64[ns]":
            df[col] = pd.to_datetime(df[col])
    return df


def test_valid_row_passes():
    df = _valid_row()
    validate_kpi(df)  # 예외가 안 나면 통과


def test_missing_column_rejected():
    df = _valid_row().drop(columns=["unit"])
    try:
        validate_kpi(df)
    except ValueError as e:
        assert "컬럼 누락" in str(e)
    else:
        raise AssertionError("컬럼 누락인데도 통과함 — 검증 실패")


def test_unknown_kpi_name_rejected():
    df = _valid_row(kpi_name="존재하지_않는_kpi")
    try:
        validate_kpi(df)
    except ValueError as e:
        assert "허용되지 않은 kpi_name" in str(e)
    else:
        raise AssertionError("허용 목록에 없는 kpi_name인데도 통과함")


def test_ratio_out_of_range_rejected():
    # 98(%)을 0.98로 안 바꾸고 그대로 넣은 흔한 실수 시나리오
    df = _valid_row(kpi_name="availability", kpi_value=98.0)
    try:
        validate_kpi(df)
    except ValueError as e:
        assert "0~1 범위 밖" in str(e)
    else:
        raise AssertionError("비율 KPI가 0~1 범위를 벗어났는데도 통과함")


def test_ci_low_greater_than_high_rejected():
    df = _valid_row(ci_low=0.95, ci_high=0.80)
    try:
        validate_kpi(df)
    except ValueError as e:
        assert "ci_low > ci_high" in str(e)
    else:
        raise AssertionError("ci_low > ci_high인데도 통과함")


def test_wrong_dtype_rejected():
    df = _valid_row(kpi_value="0.85")  # float이어야 하는데 문자열로 넣음
    try:
        validate_kpi(df)
    except ValueError as e:
        assert "float64" in str(e)
    else:
        raise AssertionError("dtype이 틀렸는데도 통과함")


def _run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print(f"\n총 {len(tests)}개 테스트 통과")


if __name__ == "__main__":
    _run_all()
