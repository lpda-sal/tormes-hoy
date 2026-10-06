from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tormes_hoy import river

from .conftest import TZ

NOW = datetime(2026, 10, 5, 17, 0, tzinfo=ZoneInfo(TZ))


def _reading(
    hours_ago: float, flow: float, level: float = 1.3
) -> dict[str, object]:
    t = (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    return {"time": t, "level_m": level, "flow_m3s": flow}


def test_merge_dedupes_sorts_and_trims() -> None:
    old = [_reading(24 * 40, 5.0), _reading(2, 7.0), _reading(1, 7.1)]
    merged = river.merge_readings(old, _reading(1, 7.2), NOW, 30, TZ)
    assert [r["flow_m3s"] for r in merged] == [7.0, 7.2]


def test_daily_aggregation() -> None:
    readings = [_reading(3, 7.0, 1.30), _reading(2, 9.0, 1.40)]
    (day,) = river.daily_from_readings(readings)
    assert day["flow_m3s"] == {"min": 7.0, "mean": 8.0, "max": 9.0}
    assert day["n"] == 2


def test_merge_daily_keeps_old_days_and_skips_partial_oldest() -> None:
    previous = [
        {"date": "2025-12-01", "flow_m3s": {"mean": 1}},
        {"date": "2026-10-04", "flow_m3s": {"mean": 99}},
    ]
    readings = [_reading(30, 5.0), _reading(1, 7.0)]
    daily = river.merge_daily(previous, readings, NOW, 2)
    by_date = {d["date"]: d for d in daily}
    assert by_date["2025-12-01"]["flow_m3s"]["mean"] == 1
    assert by_date["2026-10-04"]["flow_m3s"]["mean"] == 99  # partial skipped
    assert by_date["2026-10-05"]["flow_m3s"]["mean"] == 7.0


def test_merge_daily_keeps_previous_and_current_calendar_year() -> None:
    previous = [
        {"date": "2024-12-31"},  # two years ago: dropped
        {"date": "2025-01-01"},  # first day of previous year: kept
        {"date": "2025-07-15"},
    ]
    daily = river.merge_daily(previous, [], NOW, 2)
    assert [d["date"] for d in daily] == ["2025-01-01", "2025-07-15"]


def test_merge_daily_single_year_keeps_current_year_only() -> None:
    previous = [{"date": "2025-12-31"}, {"date": "2026-01-01"}]
    daily = river.merge_daily(previous, [], NOW, 1)
    assert [d["date"] for d in daily] == ["2026-01-01"]


def test_trend() -> None:
    rising = [_reading(4, 7.0), _reading(0, 7.5)]
    steady = [_reading(4, 7.0), _reading(0, 7.1)]
    falling = [_reading(4, 7.0), _reading(0, 6.0)]
    assert river.trend(rising, 3, 0.03, 0.01, TZ) == "rising"
    assert river.trend(steady, 3, 0.03, 0.01, TZ) == "steady"
    assert river.trend(falling, 3, 0.03, 0.01, TZ) == "falling"
    assert river.trend(rising[:1], 3, 0.03, 0.01, TZ) is None


def test_trend_falls_back_to_level() -> None:
    a = {**_reading(4, 0), "flow_m3s": None, "level_m": 1.30}
    b = {**_reading(0, 0), "flow_m3s": None, "level_m": 1.40}
    assert river.trend([a, b], 3, 0.03, 0.01, TZ) == "rising"
