import dataclasses

import pytest

from tormes_hoy.source_data.sources import chd
from tormes_hoy.utils.config import Config

from .conftest import TZ, load_fixture

EXPECTED_FLOW_M3S = 7.31
EXPECTED_SAIH_FLOW_M3S = 7.15
SAIH_CURRENT_HTML = """
<table><tbody>
<tr><td>Nivel</td><td>1,33 <span>m</span></td>
<td><span>07/10/2026 23:00</span><span>23:00</span></td></tr>
<tr><td>Caudal</td><td>7,15 <span>m³/s</span></td>
<td><span>07/10/2026 23:00</span><span>23:00</span></td></tr>
</tbody></table>
"""


def test_parse_current_selects_station(config: Config) -> None:
    reading = chd._parse_current(
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
        chd._parse_current(payload, config.river, TZ)["flow_m3s"]
        == EXPECTED_FLOW_M3S
    )


def test_missing_station_fails(config: Config) -> None:
    with pytest.raises(ValueError, match="not found"):
        chd._parse_current([{"codigo": "X"}], config.river, TZ)


def test_parse_saih_station_page(config: Config) -> None:
    reading = chd._parse_current(SAIH_CURRENT_HTML, config.river, TZ)
    assert reading == {
        "time": "2026-10-07T23:00:00+02:00",
        "level_m": 1.33,
        "flow_m3s": 7.15,
    }


def test_fetch_uses_configured_station_url(config: Config) -> None:
    seen: list[str] = []

    def get(url: str) -> str:
        seen.append(url)
        return SAIH_CURRENT_HTML

    reading = chd.fetch(config, get)
    assert seen == [config.river.current_url]
    assert reading["flow_m3s"] == EXPECTED_SAIH_FLOW_M3S


def test_fetch_requires_configured_url(config: Config) -> None:
    river = dataclasses.replace(config.river, current_url="")
    with pytest.raises(ValueError, match="not configured"):
        chd.fetch(dataclasses.replace(config, river=river))
