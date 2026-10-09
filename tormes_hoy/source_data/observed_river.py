"""Observed (provisional) river history built from our own readings.

These functions never touch yearbook data: the two sources are kept apart.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any

from tormes_hoy.utils.models import JsonDict
from tormes_hoy.utils.timeutil import parse_local

_VARIABLES = ('level_m', 'flow_m3s')


def merge_readings(
    previous: list[JsonDict],
    new: JsonDict | None,
    now: datetime,
    days: int,
    tz_name: str,
) -> list[JsonDict]:
    """Add ``new`` to the raw readings, dedupe by time and trim to ``days``."""
    by_time: dict[str, JsonDict] = {
        str(r['time']): r for r in previous if r.get('time')
    }
    if new is not None:
        by_time[str(new['time'])] = {
            'time': new['time'],
            'level_m': new.get('level_m'),
            'flow_m3s': new.get('flow_m3s'),
        }
    cutoff = now - timedelta(days=days)
    kept = [
        r
        for r in by_time.values()
        if parse_local(r['time'], tz_name) >= cutoff
    ]
    return sorted(kept, key=lambda r: parse_local(r['time'], tz_name))


def _stats(values: list[float]) -> JsonDict | None:
    if not values:
        return None
    return {
        'min': min(values),
        'mean': round(fmean(values), 3),
        'max': max(values),
    }


def _daily_from_readings(readings: list[JsonDict]) -> list[JsonDict]:
    """Aggregate raw readings into daily min/mean/max per variable."""
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {v: [] for v in _VARIABLES}
    )
    for reading in readings:
        date = str(reading['time'])[:10]
        for var in _VARIABLES:
            value = reading.get(var)
            if value is not None:
                grouped[date][var].append(float(value))
    return [
        {
            'date': date,
            'level_m': _stats(values['level_m']),
            'flow_m3s': _stats(values['flow_m3s']),
            'n': max(len(values['level_m']), len(values['flow_m3s'])),
        }
        for date, values in sorted(grouped.items())
    ]


def merge_daily(
    previous: list[JsonDict],
    readings: list[JsonDict],
    now: datetime,
    years: int,
) -> list[JsonDict]:
    """Update the daily series with days covered by raw readings.

    The series keeps whole calendar years: with ``years=2`` it starts on
    1 January of the previous year, so the web can draw the previous year
    and the current year to date on a 1 Jan - 31 Dec axis.

    The oldest raw day may be partial (trimmed by the 30-day window), so it
    never overwrites an already stored daily value.
    """
    by_date = {str(d['date']): d for d in previous if d.get('date')}
    recent = _daily_from_readings(readings)
    for index, day in enumerate(recent):
        if index == 0 and day['date'] in by_date:
            continue
        by_date[day['date']] = day
    first_day = f'{now.year - years + 1:04d}-01-01'
    return [by_date[d] for d in sorted(by_date) if d >= first_day]


def trend(
    flow: float | None,
    yesterday: float | None,
    ratio: float,
    min_change: float,
) -> str | None:
    """Return ``rising``, ``falling`` or ``steady`` against yesterday's mean.

    The change must exceed the larger of ``ratio`` times yesterday's mean
    and ``min_change`` (m3/s). Returns ``None`` if either flow is missing.
    """
    if flow is None or yesterday is None:
        return None
    limit = max(ratio * yesterday, min_change)
    change = flow - yesterday
    if change > limit:
        return 'rising'
    if change < -limit:
        return 'falling'
    return 'steady'


def readings_from(block: Any) -> list[JsonDict]:
    """Extract the readings list from a previously generated file."""
    if isinstance(block, dict) and isinstance(block.get('readings'), list):
        return [r for r in block['readings'] if isinstance(r, dict)]
    return []


def daily_from(block: Any) -> list[JsonDict]:
    """Extract the daily list from a previously generated file."""
    if isinstance(block, dict) and isinstance(block.get('daily'), list):
        return [d for d in block['daily'] if isinstance(d, dict)]
    return []
