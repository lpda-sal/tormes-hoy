import pytest

from tormes_hoy.source_data.sources import openmeteo
from tormes_hoy.utils.config import Config

from .conftest import load_fixture

EXPECTED_HOURLY_FORECAST_LENGTH = 48
EXPECTED_DAILY_MAX_TEMPERATURE_C = 22.1
EXPECTED_CURRENT_HUMIDITY_PERCENT = 41


def test_build_url_uses_configured_location(config: Config) -> None:
    url = openmeteo._build_url(config)
    assert "latitude=40.965" in url
    assert "uv_index" in url
    assert "timezone=Europe%2FMadrid" in url


def test_parse_normalises_blocks() -> None:
    data = openmeteo._parse(load_fixture("openmeteo_forecast.json"))
    assert len(data["hourly"]) == EXPECTED_HOURLY_FORECAST_LENGTH
    assert data["hourly"][12]["uv"] > 0
    assert (
        data["daily"][0]["temperature_max"] == EXPECTED_DAILY_MAX_TEMPERATURE_C
    )
    assert data["current"]["humidity"] == EXPECTED_CURRENT_HUMIDITY_PERCENT


def test_parse_rejects_incomplete_payload() -> None:
    with pytest.raises(ValueError):
        openmeteo._parse({"hourly": {}})
