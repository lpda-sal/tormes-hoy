"""AEMET OpenData: station observation and municipality forecasts.

AEMET answers in two steps: the API returns ``{"estado": 200, "datos":
url}`` and the actual data must be downloaded from ``datos``.
Field names follow the AEMET OpenData documentation and must be checked
against real responses (see docs/review.md).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from tormes_hoy.source_data.network_client import HttpError, get_json
from tormes_hoy.utils.config import Config
from tormes_hoy.utils.models import JsonDict
from tormes_hoy.utils.timeutil import (
    is_older_than,
    iso,
    parse_local,
    parse_utc,
)

NAME = 'aemet'
META: JsonDict = {
    'label': 'AEMET',
    'attribution': '© AEMET. Información elaborada por AEMET',
}

_Getter = Callable[[str, dict[str, str]], Any]


def _get_with_key(url: str, headers: dict[str, str]) -> Any:
    return get_json(url, headers=headers)


def _resolve(url: str, api_key: str, get: _Getter = _get_with_key) -> Any:
    """Perform AEMET's two-step request and return the final data."""
    headers = {'api_key': api_key, 'Accept': 'application/json'}
    first = get(url, headers)
    if not isinstance(first, dict) or 'datos' not in first:
        estado = first.get('estado') if isinstance(first, dict) else None
        raise HttpError(f'AEMET request failed (estado={estado})')
    return get(str(first['datos']), {'Accept': 'application/json'})


def _parse_observation(records: list[JsonDict], tz_name: str) -> JsonDict:
    """Return the most recent observation of a station.

    ``fint`` is the end of the observation interval in UTC.
    Wind speed ``vv`` and maximum gust ``vmax`` are converted from m/s
    to km/h.

    Raises:
        ValueError: If there are no usable records.
    """
    valid = [r for r in records if isinstance(r, dict) and r.get('fint')]
    if not valid:
        raise ValueError('AEMET observation without records')
    latest = max(valid, key=lambda r: str(r['fint']))
    wind = latest.get('vv')
    gust = latest.get('vmax')
    return {
        'time': iso(parse_utc(str(latest['fint']), tz_name)),
        'station': latest.get('idema'),
        'station_name': latest.get('ubi'),
        'temperature': latest.get('ta'),
        'humidity': latest.get('hr'),
        'wind_speed': round(wind * 3.6, 1) if wind is not None else None,
        'wind_gust': round(gust * 3.6, 1) if gust is not None else None,
        'wind_direction': latest.get('dv'),
        'precipitation': latest.get('prec'),
        'pressure': latest.get('pres'),
    }


def _hourly_values(day: JsonDict, key: str) -> dict[int, Any]:
    """Map hour -> value (e.g. ``{"value": "12", "periodo": "07"}``)."""
    hour_period_length = 2
    out: dict[int, Any] = {}
    for item in day.get(key) or []:
        periodo = str(item.get('periodo', ''))
        if len(periodo) == hour_period_length and periodo.isdigit():
            out[int(periodo)] = item.get('value')
    return out


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _prob_for_hour(day: JsonDict, hour: int) -> float | None:
    """Precipitation probability is given per 6-hour block (``"0814"``)."""
    block_period_length = 4
    for item in day.get('probPrecipitacion') or []:
        periodo = str(item.get('periodo', ''))
        if len(periodo) == block_period_length and periodo.isdigit():
            start, end = int(periodo[:2]), int(periodo[2:])
            inside = (
                start <= hour < end
                if start < end
                else hour >= start or hour < end  # wraps midnight: "2002"
            )
            if inside:
                return _to_float(item.get('value'))
    return None


def _parse_hourly_forecast(payload: list[JsonDict], tz_name: str) -> JsonDict:
    """Normalise the hourly municipality forecast."""
    days = payload[0]['prediccion']['dia']
    rows: list[JsonDict] = []
    for day in days:
        date = str(day['fecha'])[:10]
        temps = _hourly_values(day, 'temperatura')
        sky = {
            int(i['periodo']): i.get('descripcion')
            for i in day.get('estadoCielo') or []
            if str(i.get('periodo', '')).isdigit()
        }
        rain = _hourly_values(day, 'precipitacion')
        wind = {
            int(i['periodo']): i.get('velocidad', [None])[0]
            for i in day.get('vientoAndRachaMax') or []
            if str(i.get('periodo', '')).isdigit() and 'velocidad' in i
        }
        for hour in sorted(temps):
            stamp = parse_local(f'{date}T{hour:02d}:00', tz_name)
            rows.append(
                {
                    'time': stamp.strftime('%Y-%m-%dT%H:%M'),
                    'temperature': _to_float(temps[hour]),
                    'precipitation_probability': _prob_for_hour(day, hour),
                    'precipitation': _to_float(rain.get(hour)),
                    'wind_speed': _to_float(wind.get(hour)),
                    'sky': sky.get(hour),
                }
            )
    return {'hourly': rows}


def _first_whole_day(items: list[JsonDict], key: str = 'value') -> Any:
    """Pick the whole-day value (no ``periodo`` or ``00-24``)."""
    for item in items or []:
        if item.get('periodo') in (None, '00-24') and item.get(key) not in (
            None,
            '',
        ):
            return item.get(key)
    return None


def _parse_daily_forecast(payload: list[JsonDict]) -> JsonDict:
    """Normalise the daily municipality forecast."""
    rows: list[JsonDict] = []
    for day in payload[0]['prediccion']['dia']:
        temp = day.get('temperatura') or {}
        rows.append(
            {
                'date': str(day['fecha'])[:10],
                'temperature_max': _to_float(temp.get('maxima')),
                'temperature_min': _to_float(temp.get('minima')),
                'precipitation_probability': _to_float(
                    _first_whole_day(day.get('probPrecipitacion') or [])
                ),
                'sky': _first_whole_day(
                    day.get('estadoCielo') or [], 'descripcion'
                ),
                'uv_max': _to_float(day.get('uvMax')),
            }
        )
    return {'daily': rows}


def fetch_observation(
    config: Config, api_key: str, get: _Getter = _get_with_key
) -> JsonDict:
    """Download the latest observation of the configured station."""
    url = (
        f'{config.aemet.base_url}/observacion/convencional/datos/estacion/'
        f'{config.aemet.station_idema}'
    )
    return _parse_observation(
        _resolve(url, api_key, get), config.location.timezone
    )


def fetch_forecast(
    config: Config, api_key: str, get: _Getter = _get_with_key
) -> JsonDict:
    """Download hourly and daily forecasts for the configured municipality."""
    base = f'{config.aemet.base_url}/prediccion/especifica/municipio'
    code = config.aemet.municipality_code
    hourly = _parse_hourly_forecast(
        _resolve(f'{base}/horaria/{code}', api_key, get),
        config.location.timezone,
    )
    daily = _parse_daily_forecast(
        _resolve(f'{base}/diaria/{code}', api_key, get)
    )
    return {**hourly, **daily}


def observation_is_stale(
    observation: JsonDict, now: datetime, tz_name: str, hours: float
) -> bool:
    """Return True if the observation is older than ``hours``."""
    stamp = parse_local(str(observation['time']), tz_name)
    return is_older_than(stamp, now, hours)
