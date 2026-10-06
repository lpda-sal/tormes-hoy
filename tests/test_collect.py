from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any

from tormes_hoy import collect
from tormes_hoy.config import Config
from tormes_hoy.sources import aemet, chd, meteoblue, openmeteo

from .conftest import TZ, load_fixture

ENV = {"AEMET_API_KEY": "a", "METEOBLUE_API_KEY": "m"}
EXPECTED_FLOW_M3S = 7.31
EXPECTED_OPENMETEO_CALLS = 4
EXPECTED_METEOBLUE_CALLS_BEFORE_REFRESH = 1
EXPECTED_METEOBLUE_CALLS_AFTER_REFRESH = 2


def _fetchers(
    calls: dict[str, int] | None = None,
    fail: Collection[str] = (),
) -> collect.Fetchers:
    calls = calls if calls is not None else {}

    def wrap(name: str, fn: Any) -> Any:
        def inner(*args: Any) -> Any:
            calls[name] = calls.get(name, 0) + 1
            if name in fail:
                raise RuntimeError(f"{name} down")
            return fn(*args)

        return inner

    return collect.Fetchers(
        openmeteo=wrap(
            "openmeteo",
            lambda c: openmeteo.parse(load_fixture("openmeteo_forecast.json")),
        ),
        aemet_observation=wrap(
            "obs",
            lambda c, k: aemet.parse_observation(
                load_fixture("aemet_observation.json"), TZ
            ),
        ),
        aemet_forecast=wrap(
            "aemet",
            lambda c, k: {
                **aemet.parse_hourly_forecast(
                    load_fixture("aemet_hourly.json"), TZ
                ),
                **aemet.parse_daily_forecast(load_fixture("aemet_daily.json")),
            },
        ),
        meteoblue=wrap(
            "meteoblue",
            lambda c, k: meteoblue.parse(load_fixture("meteoblue_basic.json")),
        ),
        chd=wrap(
            "chd",
            lambda c: chd.parse_current(
                load_fixture("chd_estado_aforos.json"), c.river, TZ
            ),
        ),
    )


def test_full_run_produces_all_files(config: Config, now: datetime) -> None:
    files = collect.run(config, now, ENV, _fetchers())
    assert set(files) == set(collect.FILES)
    summary = files["summary.json"]
    assert summary["schema_version"] == 1
    assert summary["location"]["name"] == "Salamanca"
    assert summary["weather_now"]["status"] == "ok"
    assert summary["river"]["data"]["flow_m3s"] == EXPECTED_FLOW_M3S
    assert all(
        r["time"] >= "2026-10-05T17:00" for r in summary["today"]["data"]
    )
    weather = files["weather.json"]["forecasts"]
    assert {k: v["status"] for k, v in weather.items()} == {
        "aemet": "ok",
        "openmeteo": "ok",
        "meteoblue": "ok",
    }


def test_failing_source_is_isolated(config: Config, now: datetime) -> None:
    files = collect.run(config, now, ENV, _fetchers(fail={"openmeteo", "chd"}))
    summary = files["summary.json"]
    assert summary["today"]["status"] == "error"
    assert summary["river"]["status"] == "error"
    assert summary["weather_now"]["status"] == "ok"


def test_missing_keys_report_error(config: Config, now: datetime) -> None:
    files = collect.run(config, now, {}, _fetchers())
    forecasts = files["weather.json"]["forecasts"]
    assert forecasts["aemet"]["status"] == "error"
    assert forecasts["meteoblue"]["error"] == "METEOBLUE_API_KEY not set"
    assert forecasts["openmeteo"]["status"] == "ok"


def test_previous_data_is_reused_as_stale(
    config: Config, now: datetime
) -> None:
    collect.write_files(
        config.data_dir, collect.run(config, now, ENV, _fetchers())
    )
    later = now + timedelta(hours=1)
    files = collect.run(config, later, ENV, _fetchers(fail={"openmeteo"}))
    om = files["weather.json"]["forecasts"]["openmeteo"]
    assert om["status"] == "stale"
    assert om["data"]["hourly"]
    assert om["error"] == "openmeteo down"


def test_meteoblue_is_not_called_every_hour(
    config: Config, now: datetime
) -> None:
    calls: dict[str, int] = {}
    collect.write_files(
        config.data_dir, collect.run(config, now, ENV, _fetchers(calls))
    )
    for hours in (1, 2, 3):
        later = now + timedelta(hours=hours)
        collect.write_files(
            config.data_dir, collect.run(config, later, ENV, _fetchers(calls))
        )
    assert calls["meteoblue"] == EXPECTED_METEOBLUE_CALLS_BEFORE_REFRESH
    assert calls["openmeteo"] == EXPECTED_OPENMETEO_CALLS
    later = now + timedelta(hours=6)
    collect.run(config, later, ENV, _fetchers(calls))
    assert calls["meteoblue"] == EXPECTED_METEOBLUE_CALLS_AFTER_REFRESH


def test_river_history_accumulates(config: Config, now: datetime) -> None:
    collect.write_files(
        config.data_dir, collect.run(config, now, ENV, _fetchers())
    )
    files = collect.run(config, now + timedelta(hours=1), ENV, _fetchers())
    readings = files["river-observed-30d.json"]["readings"]
    assert len(readings) == 1  # same CHD timestamp is deduplicated
    assert (
        files["river-observed-daily.json"]["daily"][0]["date"] == "2026-10-05"
    )
