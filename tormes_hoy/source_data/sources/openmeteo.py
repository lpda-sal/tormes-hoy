"""Open-Meteo forecast: current conditions, hourly (with UV) and daily."""

from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from tormes_hoy.source_data.network_client import get_json
from tormes_hoy.utils.config import Config
from tormes_hoy.utils.models import JsonDict

NAME = "openmeteo"
META: JsonDict = {
    "label": "Open-Meteo",
    "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
}

_HOURLY_VARS = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "uv_index",
)
_DAILY_VARS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "precipitation_sum",
    "uv_index_max",
    "sunrise",
    "sunset",
)
_CURRENT_VARS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "weather_code",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "uv_index",
)


def _build_url(config: Config) -> str:
    """Return the forecast URL for the configured location."""
    params = {
        "latitude": config.location.lat,
        "longitude": config.location.lon,
        "timezone": config.location.timezone,
        "forecast_days": config.openmeteo.forecast_days,
        "wind_speed_unit": "kmh",
        "current": ",".join(_CURRENT_VARS),
        "hourly": ",".join(_HOURLY_VARS),
        "daily": ",".join(_DAILY_VARS),
    }
    return f"{config.openmeteo.base_url}?{urlencode(params)}"


def _column(block: JsonDict, name: str, length: int) -> list[Any]:
    values = block.get(name)
    return list(values) if isinstance(values, list) else [None] * length


def _parse(payload: JsonDict) -> JsonDict:
    """Normalise an Open-Meteo response.

    Times are local (the request sets ``timezone``) and kept as
    ``YYYY-MM-DDTHH:MM`` strings.

    Raises:
        ValueError: If the payload lacks hourly or daily data.
    """
    hourly = payload.get("hourly")
    daily = payload.get("daily")
    if not isinstance(hourly, dict) or not isinstance(daily, dict):
        raise ValueError("Open-Meteo payload without hourly/daily blocks")

    times = hourly.get("time") or []
    n = len(times)
    cols = {v: _column(hourly, v, n) for v in _HOURLY_VARS}
    hourly_rows = [
        {
            "time": times[i],
            "temperature": cols["temperature_2m"][i],
            "apparent_temperature": cols["apparent_temperature"][i],
            "precipitation_probability": cols["precipitation_probability"][i],
            "precipitation": cols["precipitation"][i],
            "weather_code": cols["weather_code"][i],
            "wind_speed": cols["wind_speed_10m"][i],
            "uv": cols["uv_index"][i],
        }
        for i in range(n)
    ]

    days = daily.get("time") or []
    m = len(days)
    dcols = {v: _column(daily, v, m) for v in _DAILY_VARS}
    daily_rows = [
        {
            "date": days[i],
            "weather_code": dcols["weather_code"][i],
            "temperature_max": dcols["temperature_2m_max"][i],
            "temperature_min": dcols["temperature_2m_min"][i],
            "precipitation_probability": dcols[
                "precipitation_probability_max"
            ][i],
            "precipitation": dcols["precipitation_sum"][i],
            "uv_max": dcols["uv_index_max"][i],
            "sunrise": dcols["sunrise"][i],
            "sunset": dcols["sunset"][i],
        }
        for i in range(m)
    ]

    current_raw = payload.get("current")
    current = None
    if isinstance(current_raw, dict):
        current = {
            "time": current_raw.get("time"),
            "temperature": current_raw.get("temperature_2m"),
            "apparent_temperature": current_raw.get("apparent_temperature"),
            "humidity": current_raw.get("relative_humidity_2m"),
            "weather_code": current_raw.get("weather_code"),
            "wind_speed": current_raw.get("wind_speed_10m"),
            "wind_direction": current_raw.get("wind_direction_10m"),
            "precipitation": current_raw.get("precipitation"),
            "uv": current_raw.get("uv_index"),
        }
    return {"current": current, "hourly": hourly_rows, "daily": daily_rows}


def fetch(config: Config, get: Callable[[str], Any] = get_json) -> JsonDict:
    """Download and normalise the forecast."""
    return _parse(get(_build_url(config)))
