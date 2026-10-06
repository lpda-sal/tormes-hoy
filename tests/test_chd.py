import dataclasses

import pytest

from tormes_hoy.config import Config
from tormes_hoy.sources import chd

from .conftest import TZ, load_fixture

EXPECTED_FLOW_M3S = 7.31


def test_parse_current_selects_station(config: Config) -> None:
    reading = chd.parse_current(
        load_fixture("chd_estado_aforos.json"), config.river, TZ
    )
    assert reading == {
        "time": "2026-10-05T16:30:00+02:00",
        "level_m": 1.34,
        "flow_m3s": 7.31,
    }


def test_parse_current_accepts_wrapped_payload(config: Config) -> None:
    payload = {"data": load_fixture("chd_estado_aforos.json")}
    assert (
        chd.parse_current(payload, config.river, TZ)["flow_m3s"]
        == EXPECTED_FLOW_M3S
    )


def test_missing_station_fails(config: Config) -> None:
    with pytest.raises(ValueError, match="not found"):
        chd.parse_current([{"codigo": "X"}], config.river, TZ)


def test_fetch_requires_configured_url(config: Config) -> None:
    river = dataclasses.replace(config.river, current_url="")
    with pytest.raises(ValueError, match="not configured"):
        chd.fetch(dataclasses.replace(config, river=river))
