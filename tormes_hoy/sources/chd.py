"""CHD (Confederación Hidrográfica del Duero) current river readings.

The exact endpoint and field names of the open data "Estado Aforos" JSON
are configurable in ``config.toml`` until verified (see docs/review.md).
"""

from collections.abc import Callable
from typing import Any

from tormes_hoy.config import Config, RiverConfig
from tormes_hoy.models import JsonDict
from tormes_hoy.net import get_json
from tormes_hoy.timeutil import iso, parse_local

NAME = "chd"
META: JsonDict = {
    "label": "CHD (SAIH Duero)",
    "attribution": "Confederación Hidrográfica del Duero",
    "kind": "provisional",
}


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _records(payload: Any) -> list[JsonDict]:
    """Accept a list or common wrappers (``{"data": [...]}`` etc.)."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "datos", "features", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                items = [r for r in value if isinstance(r, dict)]
                # GeoJSON: use the properties of each feature.
                return [r.get("properties", r) for r in items]
    raise ValueError("CHD payload: no list of records found")


def parse_current(payload: Any, river: RiverConfig, tz_name: str) -> JsonDict:
    """Extract the configured station's latest reading.

    Raises:
        ValueError: If the station is missing or has no level/flow.
    """
    for record in _records(payload):
        if str(record.get(river.station_field, "")).strip() != river.station:
            continue
        level = _to_float(record.get(river.level_field))
        flow = _to_float(record.get(river.flow_field))
        raw_time = record.get(river.time_field)
        if level is None and flow is None:
            raise ValueError(f"CHD station {river.station} without values")
        if not raw_time:
            raise ValueError(f"CHD station {river.station} without time")
        return {
            "time": iso(parse_local(str(raw_time), tz_name)),
            "level_m": level,
            "flow_m3s": flow,
        }
    raise ValueError(f"CHD station {river.station} not found")


def fetch(config: Config, get: Callable[[str], Any] = get_json) -> JsonDict:
    """Download the current reading of the configured station.

    Raises:
        ValueError: If ``river.current_url`` is not configured yet.
    """
    if not config.river.current_url:
        raise ValueError("river.current_url not configured (pending review)")
    return parse_current(
        get(config.river.current_url), config.river, config.location.timezone
    )
