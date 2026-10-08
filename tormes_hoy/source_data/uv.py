"""UV index helpers: risk levels and sun-protection window."""

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from tormes_hoy.utils.models import JsonDict

# WHO UV index categories (upper bounds are exclusive).
_RISK_LEVELS: tuple[tuple[float, str], ...] = (
    (3, 'low'),
    (6, 'moderate'),
    (8, 'high'),
    (11, 'very_high'),
    (float('inf'), 'extreme'),
)


def _risk_level(uv: float | None) -> str | None:
    """Return the WHO risk category key for a UV value."""
    if uv is None:
        return None
    for upper, name in _RISK_LEVELS:
        if uv < upper:
            return name
    return 'extreme'  # pragma: no cover - inf bound always matches


def _day_curve(hourly: list[JsonDict], date: str) -> list[JsonDict]:
    """Return ``[{time, uv}]`` for the given ``YYYY-MM-DD``."""
    return [
        {'time': row['time'], 'uv': row.get('uv')}
        for row in hourly
        if str(row.get('time', '')).startswith(date)
    ]


def _protection_window(
    curve: list[JsonDict], threshold: float
) -> JsonDict | None:
    """Interpolate threshold crossings, rounding the window outwards."""
    rows = sorted(curve, key=lambda row: str(row['time']))
    active = [
        index
        for index, row in enumerate(rows)
        if isinstance(row.get('uv'), (int, float))
        and isfinite(row['uv'])
        and row['uv'] >= threshold
    ]
    if not active:
        return None
    boundaries = []
    for index, neighbor in (
        (active[0], active[0] - 1),
        (active[-1], active[-1] + 1),
    ):
        row = rows[index]
        stamp = datetime.fromisoformat(str(row['time']))
        if 0 <= neighbor < len(rows):
            other = rows[neighbor]
            value = other.get('uv')
            if (
                isinstance(value, (int, float))
                and isfinite(value)
                and value < threshold
            ):
                other_stamp = datetime.fromisoformat(str(other['time']))
                ratio = (threshold - row['uv']) / (value - row['uv'])
                stamp += (other_stamp - stamp) * ratio
        boundaries.append(stamp)
    end = boundaries[1]
    if end.second or end.microsecond:
        end = end.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return {
        'from': boundaries[0].strftime('%H:%M'),
        'to': end.strftime('%H:%M'),
    }


def _value_at(curve: list[JsonDict], now: datetime) -> Any:
    """Return the UV value of the current hour, if available."""
    key = now.strftime('%Y-%m-%dT%H:00')
    for row in curve:
        if row.get('time') == key:
            return row.get('uv')
    return None


def summarize(
    hourly: list[JsonDict], now: datetime, threshold: float
) -> JsonDict:
    """Build the UV block used by the summary and the UV view."""
    curve = _day_curve(hourly, now.strftime('%Y-%m-%d'))
    values = [r['uv'] for r in curve if r.get('uv') is not None]
    peak = max(curve, key=lambda r: r.get('uv') or 0) if values else None
    current = _value_at(curve, now)
    return {
        'date': now.strftime('%Y-%m-%d'),
        'threshold': threshold,
        'now': current,
        'now_level': _risk_level(current),
        'max': peak['uv'] if peak else None,
        'max_time': str(peak['time'])[11:16] if peak else None,
        'max_level': _risk_level(peak['uv']) if peak else None,
        'protection': _protection_window(curve, threshold),
        'hourly': curve,
    }
