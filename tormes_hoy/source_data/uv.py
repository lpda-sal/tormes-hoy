"""UV index helpers: risk levels and sun-protection window."""

from datetime import datetime
from typing import Any

from tormes_hoy.utils.models import JsonDict

# WHO UV index categories (upper bounds are exclusive).
_RISK_LEVELS: tuple[tuple[float, str], ...] = (
    (3, "low"),
    (6, "moderate"),
    (8, "high"),
    (11, "very_high"),
    (float("inf"), "extreme"),
)


def _risk_level(uv: float | None) -> str | None:
    """Return the WHO risk category key for a UV value."""
    if uv is None:
        return None
    for upper, name in _RISK_LEVELS:
        if uv < upper:
            return name
    return "extreme"  # pragma: no cover - inf bound always matches


def _day_curve(hourly: list[JsonDict], date: str) -> list[JsonDict]:
    """Return ``[{time, uv}]`` for the given ``YYYY-MM-DD``."""
    return [
        {"time": row["time"], "uv": row.get("uv")}
        for row in hourly
        if str(row.get("time", "")).startswith(date)
    ]


def _protection_window(
    curve: list[JsonDict], threshold: float
) -> JsonDict | None:
    """Return first and last hour with UV >= threshold, or None.

    ``to`` is the last hourly value above the threshold, so the message
    reads "protection needed from ``from`` to ``to``".
    """
    hours = [
        str(row["time"])[11:16]
        for row in curve
        if row.get("uv") is not None and row["uv"] >= threshold
    ]
    if not hours:
        return None
    return {"from": hours[0], "to": hours[-1]}


def _value_at(curve: list[JsonDict], now: datetime) -> Any:
    """Return the UV value of the current hour, if available."""
    key = now.strftime("%Y-%m-%dT%H:00")
    for row in curve:
        if row.get("time") == key:
            return row.get("uv")
    return None


def summarize(
    hourly: list[JsonDict], now: datetime, threshold: float
) -> JsonDict:
    """Build the UV block used by the summary and the UV view."""
    curve = _day_curve(hourly, now.strftime("%Y-%m-%d"))
    values = [r["uv"] for r in curve if r.get("uv") is not None]
    peak = max(curve, key=lambda r: r.get("uv") or 0) if values else None
    current = _value_at(curve, now)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "threshold": threshold,
        "now": current,
        "now_level": _risk_level(current),
        "max": peak["uv"] if peak else None,
        "max_time": str(peak["time"])[11:16] if peak else None,
        "max_level": _risk_level(peak["uv"]) if peak else None,
        "protection": _protection_window(curve, threshold),
        "hourly": curve,
    }
