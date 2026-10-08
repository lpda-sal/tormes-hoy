"""Hourly collection: query every source in isolation and build data files."""

import json
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tormes_hoy.source_data import observed_river as river
from tormes_hoy.source_data.data_files import build_files, write_files
from tormes_hoy.source_data.sources import aemet, chd, meteoblue, openmeteo
from tormes_hoy.utils.config import Config, load_config
from tormes_hoy.utils.models import (
    JsonDict,
    SourceResult,
    previous_block,
    reuse_or_error,
)
from tormes_hoy.utils.timeutil import (
    is_older_than,
    iso,
    now_in,
    parse_local,
)

log = logging.getLogger(__name__)

_FILES = (
    'summary.json',
    'weather.json',
    'uv.json',
    'river-observed-30d.json',
    'river-observed-daily.json',
)


@dataclass(frozen=True)
class _Fetchers:
    """Injectable I/O functions (replaced by fakes in tests)."""

    openmeteo: Callable[[Config], JsonDict] = openmeteo.fetch
    aemet_observation: Callable[[Config, str], JsonDict] = (
        aemet.fetch_observation
    )
    aemet_forecast: Callable[[Config, str], JsonDict] = aemet.fetch_forecast
    meteoblue: Callable[[Config, str], JsonDict] = meteoblue.fetch
    chd: Callable[[Config], JsonDict] = chd.fetch


def _load_previous(data_dir: Path) -> dict[str, JsonDict | None]:
    """Load previously generated files (missing or broken -> None)."""
    previous: dict[str, JsonDict | None] = {}
    for name in _FILES:
        path = data_dir / name
        try:
            content = json.loads(path.read_text(encoding='utf-8'))
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
        log.warning('%s failed: %s', name, exc)
        return reuse_or_error(name, str(exc), previous, meta)
    return SourceResult(name, 'ok', data, iso(now), meta=meta)


def _missing_key(name: str, meta: JsonDict, var: str) -> SourceResult:
    return SourceResult(name, 'error', error=f'{var} not set', meta=meta)


def _collect_weather(
    config: Config,
    now: datetime,
    env: Mapping[str, str],
    fetchers: _Fetchers,
    previous: dict[str, JsonDict | None],
) -> dict[str, SourceResult]:
    """Query weather sources (observation and three forecasts)."""
    prev = previous.get('weather.json')
    if prev and prev.get('location') != config.location.to_dict():
        prev = None
    tz = config.location.timezone
    results: dict[str, SourceResult] = {}

    results['openmeteo'] = _attempt(
        openmeteo.NAME,
        openmeteo.META,
        lambda: fetchers.openmeteo(config),
        previous_block(prev, 'forecasts', 'openmeteo'),
        now,
    )

    aemet_key = env.get('AEMET_API_KEY', '')
    if aemet_key:
        observation = _attempt(
            aemet.NAME,
            aemet.META,
            lambda: fetchers.aemet_observation(config, aemet_key),
            previous_block(prev, 'observation'),
            now,
        )
        if observation.status == 'ok' and aemet.observation_is_stale(
            observation.data, now, tz, config.aemet.stale_after_hours
        ):
            observation.status = 'stale'
        results['observation'] = observation
        results['aemet'] = _attempt(
            aemet.NAME,
            aemet.META,
            lambda: fetchers.aemet_forecast(config, aemet_key),
            previous_block(prev, 'forecasts', 'aemet'),
            now,
        )
    else:
        results['observation'] = _missing_key(
            aemet.NAME, aemet.META, 'AEMET_API_KEY'
        )
        results['aemet'] = _missing_key(
            aemet.NAME, aemet.META, 'AEMET_API_KEY'
        )

    results['meteoblue'] = _collect_meteoblue(
        config,
        now,
        env,
        fetchers,
        previous_block(prev, 'forecasts', 'meteoblue'),
    )
    return results


def _collect_meteoblue(
    config: Config,
    now: datetime,
    env: Mapping[str, str],
    fetchers: _Fetchers,
    prev: JsonDict | None,
) -> SourceResult:
    """Meteoblue is only queried every ``refresh_every_hours`` (credits)."""
    key = env.get('METEOBLUE_API_KEY', '')
    if not key:
        return _missing_key(
            meteoblue.NAME, meteoblue.META, 'METEOBLUE_API_KEY'
        )
    tz = config.location.timezone
    last = prev.get('fetched_at') if prev else None
    if (
        prev is not None
        and prev.get('data')
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
            'stale' if stale else 'ok',
            prev['data'],
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


def _collect_river(
    config: Config,
    now: datetime,
    fetchers: _Fetchers,
    previous: dict[str, JsonDict | None],
) -> tuple[SourceResult, list[JsonDict], list[JsonDict]]:
    """Query the current reading and update the observed history."""
    tz = config.location.timezone
    prev_raw = previous.get('river-observed-30d.json')
    prev_daily = previous.get('river-observed-daily.json')
    current = _attempt(
        chd.NAME,
        chd.META,
        lambda: fetchers.chd(config),
        previous_block(prev_raw, 'current'),
        now,
    )
    new = current.data if current.status == 'ok' else None
    if new and is_older_than(
        parse_local(new['time'], tz), now, config.river.stale_after_hours
    ):
        current.status = 'stale'
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


def _run(
    config: Config,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
    fetchers: _Fetchers | None = None,
) -> dict[str, JsonDict]:
    """Collect everything and return ``{file_name: content}``."""
    now = now or now_in(config.location.timezone)
    env = os.environ if env is None else env
    fetchers = fetchers or _Fetchers()
    previous = _load_previous(config.data_dir)
    weather = _collect_weather(config, now, env, fetchers, previous)
    river_data = _collect_river(config, now, fetchers, previous)
    return build_files(config, now, weather, river_data)


def main() -> int:
    """Collect data, write ``data/*.json`` and print source statuses.

    Always returns 0: a failing source is reported in the data, not by
    failing the scheduled job.
    """
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    config = load_config()
    files = _run(config)
    write_files(config.data_dir, files)
    summary = files['summary.json']
    for key in ('weather_now', 'today', 'uv', 'river', 'next_days'):
        print(f'{key}: {summary[key]["status"]}')
    return 0
