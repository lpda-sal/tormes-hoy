from urllib.parse import parse_qs, urlsplit

import pytest

from tormes_hoy.source_data.sources import openmeteo
from tormes_hoy.utils.config import Config

from .conftest import load_fixture

EXPECTED_HOURLY_FORECAST_LENGTH = 48
EXPECTED_DAILY_MAX_TEMPERATURE_C = 22.1
EXPECTED_CURRENT_HUMIDITY_PERCENT = 41


def test_build_url_uses_configured_location(config: Config) -> None:
    url = openmeteo._build_url(config)
    params = parse_qs(urlsplit(url).query)
    assert params["latitude"] == [str(config.location.lat)]
    assert params["longitude"] == [str(config.location.lon)]
    assert "uv_index" in url
    assert "timezone=Europe%2FMadrid" in url
    assert "wind_gusts_10m" in params["current"][0].split(",")
    assert params["wind_speed_unit"] == ["kmh"]
    assert "relative_humidity_2m" in params["hourly"][0].split(",")


def test_parse_normalises_blocks() -> None:
    data = openmeteo._parse(load_fixture("openmeteo_forecast.json"))
    assert len(data["hourly"]) == EXPECTED_HOURLY_FORECAST_LENGTH
    assert data["hourly"][12]["uv"] > 0
    assert (
        data["daily"][0]["temperature_max"] == EXPECTED_DAILY_MAX_TEMPERATURE_C
    )
    assert data["current"]["humidity"] == EXPECTED_CURRENT_HUMIDITY_PERCENT
    assert data["current"]["wind_gust"] is None


@pytest.mark.parametrize("gust", [None, 0.0, 24.0])
def test_parse_current_gust_in_requested_units(gust: float | None) -> None:
    payload = load_fixture("openmeteo_forecast.json")
    payload["current"]["wind_gusts_10m"] = gust
    assert openmeteo._parse(payload)["current"]["wind_gust"] == gust


def test_parse_rejects_incomplete_payload() -> None:
    with pytest.raises(ValueError):
        openmeteo._parse({"hourly": {}})


def test_parse_hourly_humidity() -> None:
    payload = load_fixture("openmeteo_forecast.json")
    length = len(payload["hourly"]["time"])
    payload["hourly"]["relative_humidity_2m"] = [0, 58] + [None] * (length - 2)
    rows = openmeteo._parse(payload)["hourly"]
    assert [row["humidity"] for row in rows[:3]] == [0, 58, None]
    del payload["hourly"]["relative_humidity_2m"]
    assert all(
        row["humidity"] is None for row in openmeteo._parse(payload)["hourly"]
    )
