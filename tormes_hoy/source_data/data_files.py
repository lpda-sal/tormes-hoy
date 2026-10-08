"""Assemble and write the JSON files consumed by the static site."""

import json
from datetime import datetime
from math import isfinite
from pathlib import Path

from tormes_hoy.source_data import observed_river, uv
from tormes_hoy.source_data.sources import chd
from tormes_hoy.utils.config import Config, RiverConfig
from tormes_hoy.utils.models import JsonDict, SourceResult, envelope


def _rest_of_day(hourly: list[JsonDict], now: datetime) -> list[JsonDict]:
    start = now.strftime("%Y-%m-%dT%H:00")
    today = now.strftime("%Y-%m-%d")
    return [
        row
        for row in hourly
        if str(row["time"]) >= start and str(row["time"]).startswith(today)
    ]


def build_files(
    config: Config,
    now: datetime,
    weather: dict[str, SourceResult],
    river_data: tuple[SourceResult, list[JsonDict], list[JsonDict]],
) -> dict[str, JsonDict]:
    """Assemble every output file from the collected results."""
    river_current, readings, daily = river_data
    openmeteo = weather["openmeteo"]
    openmeteo_data: JsonDict = openmeteo.data or {}
    hourly: list[JsonDict] = openmeteo_data.get("hourly") or []
    uv_block = uv.summarize(hourly, now, config.uv.protection_threshold)
    river_trend = observed_river.trend(
        readings,
        config.river.trend_window_hours,
        config.river.trend_flow_ratio,
        config.river.trend_level_m,
        config.location.timezone,
    )
    river_meta = {**chd.META, "station": config.river.station}

    summary: JsonDict = {
        "weather_now": weather["observation"].to_dict(),
        "weather_now_model": {
            "status": openmeteo.status,
            "source": {"name": openmeteo.name, **openmeteo.meta},
            "data": openmeteo_data.get("current"),
        },
        "today": {
            "status": openmeteo.status,
            "source": {"name": openmeteo.name, **openmeteo.meta},
            "data": _rest_of_day(hourly, now),
        },
        "uv": {
            "status": openmeteo.status,
            "source": {"name": openmeteo.name, **openmeteo.meta},
            "data": {
                key: value
                for key, value in uv_block.items()
                if key != "hourly"
            },
        },
        "river": {
            "status": river_current.status,
            "flow_status": _flow_status(
                (river_current.data or {}).get("flow_m3s"), config.river
            ),
            "source": {"name": chd.NAME, **river_meta},
            "error": river_current.error,
            "data": (
                {**river_current.data, "trend": river_trend}
                if river_current.data
                else None
            ),
        },
        "next_days": {
            "status": openmeteo.status,
            "source": {"name": openmeteo.name, **openmeteo.meta},
            "data": openmeteo_data.get("daily") or [],
        },
    }
    files: dict[str, JsonDict] = {
        "summary.json": summary,
        "weather.json": {
            "observation": weather["observation"].to_dict(),
            "forecasts": {
                key: weather[key].to_dict()
                for key in ("aemet", "openmeteo", "meteoblue")
            },
        },
        "uv.json": {
            "status": openmeteo.status,
            "source": {"name": openmeteo.name, **openmeteo.meta},
            "data": uv_block,
        },
        "river-observed-30d.json": {
            "source": river_meta,
            "current": river_current.to_dict(),
            "readings": readings,
        },
        "river-observed-daily.json": {"source": river_meta, "daily": daily},
    }
    return {name: envelope(config, now, body) for name, body in files.items()}


def _flow_status(flow: float | None, config: RiverConfig) -> str | None:
    if not isinstance(flow, (int, float)) or not isfinite(flow) or flow < 0:
        return None
    if flow >= config.flow_danger_m3s:
        return "danger"
    if flow >= config.flow_caution_m3s:
        return "caution"
    return "safe"


def write_files(data_dir: Path, files: dict[str, JsonDict]) -> None:
    """Write JSON files (compact indentation keeps git diffs readable)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (data_dir / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
