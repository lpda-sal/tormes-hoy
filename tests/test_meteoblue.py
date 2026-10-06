from datetime import datetime
from zoneinfo import ZoneInfo

from tormes_hoy.config import Config
from tormes_hoy.net import _redact
from tormes_hoy.sources import meteoblue

from .conftest import TZ, load_fixture

EXPECTED_DAILY_PRECIPITATION_MM = 2.4


def test_parse() -> None:
    data = meteoblue.parse(load_fixture("meteoblue_basic.json"))
    assert data["hourly"][0]["time"] == "2026-10-05T00:00"
    assert data["daily"][1]["precipitation"] == EXPECTED_DAILY_PRECIPITATION_MM


def test_should_refresh_every_six_hours() -> None:
    now = datetime(2026, 10, 5, 17, 17, tzinfo=ZoneInfo(TZ))
    assert meteoblue.should_refresh(None, now, 6, TZ)
    assert not meteoblue.should_refresh(
        "2026-10-05T14:17:00+02:00", now, 6, TZ
    )
    assert meteoblue.should_refresh("2026-10-05T11:17:00+02:00", now, 6, TZ)


def test_api_key_is_redacted_in_errors(config: Config) -> None:
    url = meteoblue.build_url(config, "SECRET")
    assert "SECRET" not in _redact(url)
