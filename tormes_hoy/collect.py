"""Hourly collection: query every source in isolation and build data files."""

import json
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tormes_hoy import river, uv
from tormes_hoy.config import Config
from tormes_hoy.models import (
    JsonDict,
    SourceResult,
    envelope,
    previous_block,
    reuse_or_error,
)
from tormes_hoy.sources import aemet, chd, meteoblue, openmeteo
from tormes_hoy.timeutil import is_older_than, iso, now_in, parse_local

log = logging.getLogger(__name__)

FILES = (
    "summary.json",
    "weather.json",
    "uv.json",
    "river-observed-30d.json",
    "river-observed-daily.json",
)


@dataclass(frozen=True)
class Fetchers:
    """Injectable I/O functions (replaced by fakes in tests)."""

    openmeteo: Callable[[Config], JsonDict] = openmeteo.fetch
    aemet_observation: Callable[[Config, str], JsonDict] = (
        aemet.fetch_observation
    )
    aemet_forecast: Callable[[Config, str], JsonDict] = aemet.fetch_forecast
    meteoblue: Callable[[Config, str], JsonDict] = meteoblue.fetch
    chd: Callable[[Config], JsonDict] = chd.fetch


def load_previous(data_dir: Path) -> dict[str, JsonDict | None]:
    """Load previously generated files (missing or broken -> None)."""
    previous: dict[str, JsonDict | None] = {}
    for name in FILES:
        path = data_dir / name
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            previous[name] = content if isinstance(content, dict) else None
        except (OSError, json.JSONDecodeError):
            previous[name] = None
    return previous


def _attempt(
    name: str,
    meta: JsonDict,
    call: Callable[[], JsonDict],
    previous: JsonDict | None,
    now: datetime,
) -> SourceResult:
    """Run one source call; any failure is contained to that source."""
    try:
        data = call()
    except Exception as exc:  # noqa: BLE001 - isolation is the contract
        log.warning("%s failed: %s", name, exc)
        return reuse_or_error(name, str(exc), previous, meta)
    return SourceResult(name, "ok", data, iso(now), meta=meta)


def _missing_key(name: str, meta: JsonDict, var: str) -> SourceResult:
    return SourceResult(name, "error", error=f"{var} not set", meta=meta)


def collect_weather(
    config: Config,
    now: datetime,
    env: Mapping[str, str],
    fetchers: Fetchers,
    previous: dict[str, JsonDict | None],
) -> dict[str, SourceResult]:
    """Query weather sources (observation and three forecasts)."""
    prev = previous.get("weather.json")
    tz = config.location.timezone
    results: dict[str, SourceResult] = {}

    results["openmeteo"] = _attempt(
        openmeteo.NAME,
        openmeteo.META,
        lambda: fetchers.openmeteo(config),
        previous_block(prev, "forecasts", "openmeteo"),
        now,
    )

    aemet_key = env.get("AEMET_API_KEY", "")
    if aemet_key:
        observation = _attempt(
            aemet.NAME,
            aemet.META,
            lambda: fetchers.aemet_observation(config, aemet_key),
            previous_block(prev, "observation"),
            now,
        )
        if observation.status == "ok" and aemet.observation_is_stale(
            observation.data, now, tz, config.aemet.stale_after_hours
        ):
            observation.status = "stale"
        results["observation"] = observation
        results["aemet"] = _attempt(
            aemet.NAME,
            aemet.META,
            lambda: fetchers.aemet_forecast(config, aemet_key),
            previous_block(prev, "forecasts", "aemet"),
            now,
        )
    else:
        results["observation"] = _missing_key(
            aemet.NAME, aemet.META, "AEMET_API_KEY"
        )
        results["aemet"] = _missing_key(
            aemet.NAME, aemet.META, "AEMET_API_KEY"
        )

    results["meteoblue"] = _collect_meteoblue(
        config,
        now,
        env,
        fetchers,
        previous_block(prev, "forecasts", "meteoblue"),
    )
    return results


def _collect_meteoblue(
    config: Config,
    now: datetime,
    env: Mapping[str, str],
    fetchers: Fetchers,
    prev: JsonDict | None,
) -> SourceResult:
    """Meteoblue is only queried every ``refresh_every_hours`` (credits)."""
    key = env.get("METEOBLUE_API_KEY", "")
    if not key:
        return _missing_key(
            meteoblue.NAME, meteoblue.META, "METEOBLUE_API_KEY"
        )
    tz = config.location.timezone
    last = prev.get("fetched_at") if prev else None
    if (
        prev is not None
        and prev.get("data")
        and isinstance(last, str)
        and not meteoblue.should_refresh(
            last, now, config.meteoblue.refresh_every_hours, tz
        )
    ):
        stale = is_older_than(
            parse_local(last, tz), now, config.meteoblue.stale_after_hours
        )
        return SourceResult(
            meteoblue.NAME,
            "stale" if stale else "ok",
            prev["data"],
            last,
            meta=meteoblue.META,
        )
    return _attempt(
        meteoblue.NAME,
        meteoblue.META,
        lambda: fetchers.meteoblue(config, key),
        prev,
        now,
    )


def collect_river(
    config: Config,
    now: datetime,
    fetchers: Fetchers,
    previous: dict[str, JsonDict | None],
) -> tuple[SourceResult, list[JsonDict], list[JsonDict]]:
    """Query the current reading and update the observed history."""
    tz = config.location.timezone
    prev_raw = previous.get("river-observed-30d.json")
    prev_daily = previous.get("river-observed-daily.json")
    current = _attempt(
        chd.NAME,
        chd.META,
        lambda: fetchers.chd(config),
        previous_block(prev_raw, "current"),
        now,
    )
    new = current.data if current.status == "ok" else None
    if new and is_older_than(
        parse_local(new["time"], tz), now, config.river.stale_after_hours
    ):
        current.status = "stale"
    readings = river.merge_readings(
        river.readings_from(prev_raw),
        new,
        now,
        config.river.observed_days,
        tz,
    )
    daily = river.merge_daily(
        river.daily_from(prev_daily), readings, now, config.river.daily_years
    )
    return current, readings, daily


def _rest_of_day(hourly: list[JsonDict], now: datetime) -> list[JsonDict]:
    start = now.strftime("%Y-%m-%dT%H:00")
    today = now.strftime("%Y-%m-%d")
    return [
        r
        for r in hourly
        if str(r["time"]) >= start and str(r["time"]).startswith(today)
    ]


def build_files(
    config: Config,
    now: datetime,
    weather: dict[str, SourceResult],
    river_data: tuple[SourceResult, list[JsonDict], list[JsonDict]],
) -> dict[str, JsonDict]:
    """Assemble every output file from the collected results."""
    river_current, readings, daily = river_data
    om = weather["openmeteo"]
    om_data: JsonDict = om.data or {}
    hourly: list[JsonDict] = om_data.get("hourly") or []
    uv_block = uv.summarize(hourly, now, config.uv.protection_threshold)
    trend = river.trend(
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
            "status": om.status,
            "source": {"name": om.name, **om.meta},
            "data": om_data.get("current"),
        },
        "today": {
            "status": om.status,
            "source": {"name": om.name, **om.meta},
            "data": _rest_of_day(hourly, now),
        },
        "uv": {
            "status": om.status,
            "source": {"name": om.name, **om.meta},
            "data": {k: v for k, v in uv_block.items() if k != "hourly"},
        },
        "river": {
            "status": river_current.status,
            "source": {"name": chd.NAME, **river_meta},
            "error": river_current.error,
            "data": (
                {**river_current.data, "trend": trend}
                if river_current.data
                else None
            ),
        },
        "next_days": {
            "status": om.status,
            "source": {"name": om.name, **om.meta},
            "data": om_data.get("daily") or [],
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
            "status": om.status,
            "source": {"name": om.name, **om.meta},
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


def run(
    config: Config,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
    fetchers: Fetchers | None = None,
) -> dict[str, JsonDict]:
    """Collect everything and return ``{file_name: content}``."""
    now = now or now_in(config.location.timezone)
    env = os.environ if env is None else env
    fetchers = fetchers or Fetchers()
    previous = load_previous(config.data_dir)
    weather = collect_weather(config, now, env, fetchers, previous)
    river_data = collect_river(config, now, fetchers, previous)
    return build_files(config, now, weather, river_data)


def write_files(data_dir: Path, files: dict[str, Any]) -> None:
    """Write JSON files (compact indentation keeps git diffs readable)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (data_dir / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
