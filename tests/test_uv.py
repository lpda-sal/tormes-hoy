from datetime import datetime
from zoneinfo import ZoneInfo

from tormes_hoy.source_data import uv
from tormes_hoy.source_data.sources import openmeteo

from .conftest import TZ, load_fixture

HOURS_PER_DAY = 24


def test_risk_levels() -> None:
    assert uv._risk_level(None) is None
    assert uv._risk_level(2.9) == "low"
    assert uv._risk_level(3) == "moderate"
    assert uv._risk_level(7.5) == "high"
    assert uv._risk_level(10) == "very_high"
    assert uv._risk_level(11) == "extreme"


def test_protection_window() -> None:
    curve = [
        {"time": "2026-06-01T10:00", "uv": 2.0},
        {"time": "2026-06-01T11:00", "uv": 3.5},
        {"time": "2026-06-01T15:00", "uv": 4.0},
        {"time": "2026-06-01T16:00", "uv": 2.0},
    ]
    assert uv._protection_window(curve, 3) == {
        "from": "11:00",
        "to": "15:00",
    }
    assert uv._protection_window(curve, 5) is None


def test_summarize_today() -> None:
    hourly = openmeteo._parse(load_fixture("openmeteo_forecast.json"))[
        "hourly"
    ]
    now = datetime(2026, 10, 5, 13, 30, tzinfo=ZoneInfo(TZ))
    block = uv.summarize(hourly, now, 3)
    assert len(block["hourly"]) == HOURS_PER_DAY
    assert block["now"] == hourly[13]["uv"]
    assert block["max"] == max(r["uv"] for r in hourly[:HOURS_PER_DAY])
    assert block["protection"] is not None
