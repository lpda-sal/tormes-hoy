"""CHD (Confederación Hidrográfica del Duero) current river readings.

The exact endpoint and field names of the open data "Estado Aforos" JSON
are configurable in ``config.toml`` until verified (see docs/review.md).
"""

import re
from collections.abc import Callable
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from tormes_hoy.source_data.network_client import get_text
from tormes_hoy.utils.config import Config, RiverConfig
from tormes_hoy.utils.models import JsonDict
from tormes_hoy.utils.timeutil import iso, parse_local

NAME = "chd"
_MIN_CURRENT_ROW_CELLS = 3
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


class _CurrentReadingsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._cells: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self.readings: dict[datetime, dict[str, float | None]] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "tr":
            self._cells = []
            self._cell_parts = None
        elif tag == "td" and self._cells is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cells is not None:
            if self._cell_parts is not None:
                self._cells.append("".join(self._cell_parts).strip())
                self._cell_parts = None
        elif tag == "tr" and self._cells is not None:
            self._read_row()
            self._cells = None
            self._cell_parts = None

    def _read_row(self) -> None:
        if (
            self._cells is None
            or len(self._cells) < _MIN_CURRENT_ROW_CELLS
        ):
            return
        variable = {"nivel": "level_m", "caudal": "flow_m3s"}.get(
            self._cells[0].casefold()
        )
        if variable is None:
            return
        timestamp_match = re.search(
            r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", self._cells[2]
        )
        value_match = re.search(r"[-+]?\d+(?:[.,]\d+)?", self._cells[1])
        if timestamp_match is None or value_match is None:
            return
        timestamp = datetime.strptime(
            timestamp_match.group(), "%d/%m/%Y %H:%M"
        )
        reading = self.readings.setdefault(
            timestamp, {"level_m": None, "flow_m3s": None}
        )
        reading[variable] = _to_float(value_match.group())


def _parse_current_html(payload: str, tz_name: str) -> JsonDict:
    parser = _CurrentReadingsParser()
    parser.feed(payload)
    parser.close()
    if not parser.readings:
        raise ValueError("CHD station page without current readings")
    timestamp, values = max(parser.readings.items())
    return {
        "time": iso(parse_local(timestamp.isoformat(), tz_name)),
        **values,
    }


def _parse_current(payload: Any, river: RiverConfig, tz_name: str) -> JsonDict:
    """Extract the configured station's latest reading.

    Raises:
        ValueError: If the station is missing or has no level/flow.
    """
    if isinstance(payload, str):
        return _parse_current_html(payload, tz_name)
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


def fetch(config: Config, get: Callable[[str], str] = get_text) -> JsonDict:
    """Download the current reading of the configured station.

    Raises:
        ValueError: If ``river.current_url`` is not configured yet.
    """
    if not config.river.current_url:
        raise ValueError("river.current_url not configured (pending review)")
    return _parse_current(
        get(config.river.current_url), config.river, config.location.timezone
    )
