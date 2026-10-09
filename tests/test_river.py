from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tormes_hoy.source_data import observed_river as river

from .conftest import TZ

NOW = datetime(2026, 10, 5, 17, 0, tzinfo=ZoneInfo(TZ))
EXPECTED_DAILY_READING_COUNT = 2
PARTIAL_DAY_FLOW_MEAN = 99
CURRENT_DAY_FLOW_MEAN = 7.0


def _reading(
    hours_ago: float, flow: float, level: float = 1.3
) -> dict[str, object]:
    t = (NOW - timedelta(hours=hours_ago)).isoformat(timespec='seconds')
    return {'time': t, 'level_m': level, 'flow_m3s': flow}


def test_merge_dedupes_sorts_and_trims() -> None:
    old = [_reading(24 * 40, 5.0), _reading(2, 7.0), _reading(1, 7.1)]
    merged = river.merge_readings(old, _reading(1, 7.2), NOW, 30, TZ)
    assert [r['flow_m3s'] for r in merged] == [7.0, 7.2]


def test_daily_aggregation() -> None:
    readings = [_reading(3, 7.0, 1.30), _reading(2, 9.0, 1.40)]
    (day,) = river._daily_from_readings(readings)
    assert day['flow_m3s'] == {'min': 7.0, 'mean': 8.0, 'max': 9.0}
    assert day['n'] == EXPECTED_DAILY_READING_COUNT


def test_merge_daily_keeps_old_days_and_skips_partial_oldest() -> None:
    previous = [
        {'date': '2025-12-01', 'flow_m3s': {'mean': 1}},
        {'date': '2026-10-04', 'flow_m3s': {'mean': 99}},
    ]
    readings = [_reading(30, 5.0), _reading(1, 7.0)]
    daily = river.merge_daily(previous, readings, NOW, 2)
    by_date = {d['date']: d for d in daily}
    assert by_date['2025-12-01']['flow_m3s']['mean'] == 1
    assert (
        by_date['2026-10-04']['flow_m3s']['mean'] == PARTIAL_DAY_FLOW_MEAN
    )  # partial skipped
    assert by_date['2026-10-05']['flow_m3s']['mean'] == CURRENT_DAY_FLOW_MEAN


def test_merge_daily_keeps_previous_and_current_calendar_year() -> None:
    previous = [
        {'date': '2024-12-31'},  # two years ago: dropped
        {'date': '2025-01-01'},  # first day of previous year: kept
        {'date': '2025-07-15'},
    ]
    daily = river.merge_daily(previous, [], NOW, 2)
    assert [d['date'] for d in daily] == ['2025-01-01', '2025-07-15']


def test_merge_daily_single_year_keeps_current_year_only() -> None:
    previous = [{'date': '2025-12-31'}, {'date': '2026-01-01'}]
    daily = river.merge_daily(previous, [], NOW, 1)
    assert [d['date'] for d in daily] == ['2026-01-01']


@pytest.mark.parametrize(
    ('flow', 'yesterday', 'expected'),
    [
        (7.0, 7.0, 'steady'),
        (9.99, 7.0, 'steady'),  # +2.99, below the 3 m3/s floor
        (10.01, 7.0, 'rising'),
        (3.99, 7.0, 'falling'),
        (4.01, 7.0, 'steady'),
        (3.0, 7.0, 'falling'),
        (100.0, 100.0, 'steady'),
        (114.9, 100.0, 'steady'),  # +14.9 %, below the 15 % limit
        (115.1, 100.0, 'rising'),
        (84.9, 100.0, 'falling'),
        (85.1, 100.0, 'steady'),
        (None, 7.0, None),
        (7.0, None, None),
    ],
)
def test_trend(
    flow: float | None, yesterday: float | None, expected: str | None
) -> None:
    assert river.trend(flow, yesterday, 0.15, 3.0) == expected


def test_trend_floor_dominates_below_twenty_m3s() -> None:
    # 15 % of 19 is 2.85, so the 3 m3/s floor applies.
    assert river.trend(21.9, 19.0, 0.15, 3.0) == 'steady'
    assert river.trend(22.1, 19.0, 0.15, 3.0) == 'rising'
    # 15 % of 40 is 6, which exceeds the floor.
    assert river.trend(45.9, 40.0, 0.15, 3.0) == 'steady'
    assert river.trend(46.1, 40.0, 0.15, 3.0) == 'rising'
