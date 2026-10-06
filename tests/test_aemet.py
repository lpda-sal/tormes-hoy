from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tormes_hoy.config import Config
from tormes_hoy.net import HttpError
from tormes_hoy.sources import aemet

from .conftest import TZ, load_fixture

EXPECTED_TEMPERATURE_C = 20.7
EXPECTED_OBSERVATION_WIND_SPEED_KMH = 12.6
EXPECTED_PRECIPITATION_PROBABILITIES = (10, 20)
EXPECTED_HOURLY_WIND_SPEED_KMH = 10
EXPECTED_DAILY_PRECIPITATION_PROBABILITY = 5
EXPECTED_DAILY_MAX_TEMPERATURE_C = 22


def test_observation_takes_latest_and_converts_units() -> None:
    obs = aemet.parse_observation(load_fixture("aemet_observation.json"), TZ)
    # 15:00 UTC is 17:00 in Madrid (CEST).
    assert obs["time"] == "2026-10-05T17:00:00+02:00"
    assert obs["temperature"] == EXPECTED_TEMPERATURE_C
    assert obs["wind_speed"] == EXPECTED_OBSERVATION_WIND_SPEED_KMH


def test_observation_without_records_fails() -> None:
    with pytest.raises(ValueError):
        aemet.parse_observation([], TZ)


def test_hourly_forecast_maps_probability_blocks() -> None:
    data = aemet.parse_hourly_forecast(load_fixture("aemet_hourly.json"), TZ)
    rows = {r["time"]: r for r in data["hourly"]}
    assert (
        rows["2026-10-05T18:00"]["precipitation_probability"]
        == EXPECTED_PRECIPITATION_PROBABILITIES[0]
    )
    assert (
        rows["2026-10-05T21:00"]["precipitation_probability"]
        == EXPECTED_PRECIPITATION_PROBABILITIES[1]
    )
    assert rows["2026-10-05T18:00"]["sky"] == "Poco nuboso"
    assert (
        rows["2026-10-05T18:00"]["wind_speed"]
        == EXPECTED_HOURLY_WIND_SPEED_KMH
    )


def test_daily_forecast_uses_whole_day_values() -> None:
    data = aemet.parse_daily_forecast(load_fixture("aemet_daily.json"))
    first = data["daily"][0]
    assert (
        first["precipitation_probability"]
        == EXPECTED_DAILY_PRECIPITATION_PROBABILITY
    )
    assert first["temperature_max"] == EXPECTED_DAILY_MAX_TEMPERATURE_C
    assert first["sky"] == "Poco nuboso"


def test_resolve_follows_datos_url() -> None:
    calls: list[str] = []

    def fake_get(url: str, headers: dict[str, str]) -> Any:
        calls.append(url)
        if url.endswith("/first"):
            assert headers["api_key"] == "k"
            return {"estado": 200, "datos": "https://x/data"}
        return [{"ok": True}]

    assert aemet.resolve("https://x/first", "k", fake_get) == [{"ok": True}]
    assert calls == ["https://x/first", "https://x/data"]


def test_resolve_raises_on_api_error() -> None:
    with pytest.raises(HttpError):
        aemet.resolve("u", "k", lambda url, h: {"estado": 401})


def test_fetch_observation_builds_station_url(config: Config) -> None:
    seen: list[str] = []

    def fake_get(url: str, headers: dict[str, str]) -> Any:
        seen.append(url)
        if "estacion" in url:
            return {"datos": "https://x/d"}
        return load_fixture("aemet_observation.json")

    aemet.fetch_observation(config, "k", fake_get)
    assert seen[0].endswith("/estacion/2867")


def test_stale_observation() -> None:
    now = datetime(2026, 10, 5, 21, 0, tzinfo=ZoneInfo(TZ))
    obs = {"time": "2026-10-05T17:00:00+02:00"}
    assert aemet.observation_is_stale(obs, now, TZ, 3)
    assert not aemet.observation_is_stale(obs, now, TZ, 5)
