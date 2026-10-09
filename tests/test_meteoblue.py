from datetime import datetime
from zoneinfo import ZoneInfo

from tormes_hoy.source_data.network_client import _redact
from tormes_hoy.source_data.sources import meteoblue
from tormes_hoy.utils.config import Config

from .conftest import TZ, load_fixture

EXPECTED_DAILY_PRECIPITATION_MM = 2.4


def test_parse() -> None:
    data = meteoblue._parse(load_fixture("meteoblue_basic.json"))
    assert data["hourly"][0]["time"] == "2026-10-05T00:00"
    assert data["daily"][1]["precipitation"] == EXPECTED_DAILY_PRECIPITATION_MM


def test_parse_hourly_humidity() -> None:
    payload = load_fixture("meteoblue_basic.json")
    length = len(payload["data_1h"]["time"])
    payload["data_1h"]["relativehumidity"] = [0, 58] + [None] * (length - 2)
    rows = meteoblue._parse(payload)["hourly"]
    assert [row["humidity"] for row in rows[:3]] == [0, 58, None]
    del payload["data_1h"]["relativehumidity"]
    assert all(
        row["humidity"] is None for row in meteoblue._parse(payload)["hourly"]
    )


def test_parse_daily_pictocode() -> None:
    payload = load_fixture("meteoblue_basic.json")
    payload["data_day"]["pictocode"] = [1, 12]
    rows = meteoblue._parse(payload)["daily"]
    assert [row["pictocode"] for row in rows] == [1, 12]
    payload["data_day"]["pictocode"] = [None, 999]
    rows = meteoblue._parse(payload)["daily"]
    assert [row["pictocode"] for row in rows] == [None, 999]
    del payload["data_day"]["pictocode"]
    assert all(
        row["pictocode"] is None for row in meteoblue._parse(payload)["daily"]
    )


def test_should_refresh_every_six_hours() -> None:
    now = datetime(2026, 10, 5, 17, 17, tzinfo=ZoneInfo(TZ))
    assert meteoblue.should_refresh(None, now, 6, TZ)
    assert not meteoblue.should_refresh(
        "2026-10-05T14:17:00+02:00", now, 6, TZ
    )
    assert meteoblue.should_refresh("2026-10-05T11:17:00+02:00", now, 6, TZ)


def test_api_key_is_redacted_in_errors(config: Config) -> None:
    url = meteoblue._build_url(config, "SECRET")
    assert "SECRET" not in _redact(url)
