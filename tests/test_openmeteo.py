from tormes_hoy.config import Config
from tormes_hoy.sources import openmeteo

from .conftest import load_fixture


def test_build_url_uses_configured_location(config: Config) -> None:
    url = openmeteo.build_url(config)
    assert "latitude=40.965" in url
    assert "uv_index" in url
    assert "timezone=Europe%2FMadrid" in url


def test_parse_normalises_blocks() -> None:
    data = openmeteo.parse(load_fixture("openmeteo_forecast.json"))
    assert len(data["hourly"]) == 48
    assert data["hourly"][12]["uv"] > 0
    assert data["daily"][0]["temperature_max"] == 22.1
    assert data["current"]["humidity"] == 41


def test_parse_rejects_incomplete_payload() -> None:
    import pytest

    with pytest.raises(ValueError):
        openmeteo.parse({"hourly": {}})
