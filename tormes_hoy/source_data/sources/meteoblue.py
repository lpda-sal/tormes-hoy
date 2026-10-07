"""Meteoblue forecast (free trial: credit-limited, refreshed every N hours).

Package and field names follow the meteoblue ``basic-1h`` / ``basic-day``
documentation and must be checked against a real response.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from tormes_hoy.source_data.network_client import get_json
from tormes_hoy.utils.config import Config
from tormes_hoy.utils.models import JsonDict
from tormes_hoy.utils.timeutil import is_older_than, parse_local

NAME = "meteoblue"
META: JsonDict = {"label": "Meteoblue", "attribution": "© meteoblue"}


def _build_url(config: Config, api_key: str) -> str:
    """Return the package URL for the configured location."""
    params = {
        "lat": config.location.lat,
        "lon": config.location.lon,
        "tz": config.location.timezone,
        "format": "json",
        "windspeed": "kmh",
        "apikey": api_key,
    }
    return f"{config.meteoblue.base_url}?{urlencode(params)}"


def should_refresh(
    previous_fetched_at: str | None,
    now: datetime,
    every_hours: float,
    tz_name: str,
) -> bool:
    """Decide whether to spend credits on a new request."""
    if not previous_fetched_at:
        return True
    last = parse_local(previous_fetched_at, tz_name)
    # Small margin so the 17-minute cron does not drift past the window.
    return is_older_than(last, now, every_hours - 0.25)


def _col(block: JsonDict, name: str, n: int) -> list[Any]:
    values = block.get(name)
    return list(values) if isinstance(values, list) else [None] * n


def _local_minute(value: str) -> str:
    return value.strip().replace(" ", "T")[:16]


def _parse(payload: JsonDict) -> JsonDict:
    """Normalise a ``basic-1h_basic-day`` response.

    Raises:
        ValueError: If the payload lacks ``data_1h`` or ``data_day``.
    """
    hourly = payload.get("data_1h")
    daily = payload.get("data_day")
    if not isinstance(hourly, dict) or not isinstance(daily, dict):
        raise ValueError("Meteoblue payload without data_1h/data_day")
    times = hourly.get("time") or []
    n = len(times)
    temp = _col(hourly, "temperature", n)
    prob = _col(hourly, "precipitation_probability", n)
    rain = _col(hourly, "precipitation", n)
    wind = _col(hourly, "windspeed", n)
    picto = _col(hourly, "pictocode", n)
    hourly_rows = [
        {
            "time": _local_minute(str(times[i])),
            "temperature": temp[i],
            "precipitation_probability": prob[i],
            "precipitation": rain[i],
            "wind_speed": wind[i],
            "pictocode": picto[i],
        }
        for i in range(n)
    ]
    days = daily.get("time") or []
    m = len(days)
    tmax = _col(daily, "temperature_max", m)
    tmin = _col(daily, "temperature_min", m)
    dprob = _col(daily, "precipitation_probability", m)
    drain = _col(daily, "precipitation", m)
    uv = _col(daily, "uvindex", m)
    daily_rows = [
        {
            "date": str(days[i])[:10],
            "temperature_max": tmax[i],
            "temperature_min": tmin[i],
            "precipitation_probability": dprob[i],
            "precipitation": drain[i],
            "uv_max": uv[i],
        }
        for i in range(m)
    ]
    return {"hourly": hourly_rows, "daily": daily_rows}


def fetch(
    config: Config, api_key: str, get: Callable[[str], Any] = get_json
) -> JsonDict:
    """Download and normalise the forecast (spends credits)."""
    return _parse(get(_build_url(config, api_key)))
