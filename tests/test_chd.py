import dataclasses

import pytest

from tormes_hoy.source_data.sources import chd
from tormes_hoy.utils.config import Config

from .conftest import TZ, load_fixture

EXPECTED_FLOW_M3S = 7.31
EXPECTED_SAIH_FLOW_M3S = 7.15
EXPECTED_PAGE_FLOW_M3S = 6.76
SAIH_CURRENT_HTML = """
<table><tbody>
<tr><td>Nivel</td><td>1,33 <span>m</span></td>
<td><span>07/10/2026 23:00</span><span>23:00</span></td></tr>
<tr><td>Caudal</td><td>7,15 <span>m³/s</span></td>
<td><span>07/10/2026 23:00</span><span>23:00</span></td></tr>
</tbody></table>
"""
SAIH_STATISTICS_HTML = """
<table><thead><tr><th>Variable</th><th>Valor</th><th>Fecha</th>
<th><span>Tendencia</span></th></tr></thead><tbody>
<tr><td>Nivel</td><td class="variable">1,32 <span>m</span></td>
<td><span>09/10/2026 13:00</span><span>13:00</span></td>
<td><i class="wi wi-direction-right"></i></td></tr>
<tr><td>Caudal</td><td class="variable">6,76 <span>m³/s</span></td>
<td><span>09/10/2026 13:00</span><span>13:00</span></td>
<td><i class="wi wi-direction-right"></i></td></tr>
</tbody></table>
<table><thead><tr><th>Variable</th><th>Ayer</th><th>Mín. mes</th>
<th>Máx. mes</th><th>Mín. año</th><th>Máx. año</th></tr></thead><tbody>
<tr><td>Nivel</td><td>1,33 <span>m</span></td><td>1,32 <span>m</span></td>
<td>1,34 <span>m</span></td><td>1,32 <span>m</span></td>
<td>1,34 <span>m</span></td></tr>
<tr><td>Caudal</td><td>7,15 <span>m³/s</span></td>
<td>6,38 <span>m³/s</span></td><td>7,46 <span>m³/s</span></td>
<td>6,47 <span>m³/s</span></td><td>7,46 <span>m³/s</span></td></tr>
</tbody></table>
"""


def test_parse_current_selects_station(config: Config) -> None:
    reading = chd._parse_current(
        load_fixture('chd_estado_aforos.json'), config.river, TZ
    )
    assert reading == {
        'time': '2026-10-05T16:30:00+02:00',
        'level_m': 1.34,
        'flow_m3s': 7.31,
    }


def test_parse_current_accepts_wrapped_payload(config: Config) -> None:
    payload = {'data': load_fixture('chd_estado_aforos.json')}
    assert (
        chd._parse_current(payload, config.river, TZ)['flow_m3s']
        == EXPECTED_FLOW_M3S
    )


def test_missing_station_fails(config: Config) -> None:
    with pytest.raises(ValueError, match='not found'):
        chd._parse_current([{'codigo': 'X'}], config.river, TZ)


def test_parse_saih_station_page(config: Config) -> None:
    reading = chd._parse_current(SAIH_CURRENT_HTML, config.river, TZ)
    assert reading == {
        'time': '2026-10-07T23:00:00+02:00',
        'level_m': 1.33,
        'flow_m3s': 7.15,
    }


def test_parse_saih_page_reads_yesterday_flow(config: Config) -> None:
    reading = chd._parse_current(SAIH_STATISTICS_HTML, config.river, TZ)
    assert reading == {
        'time': '2026-10-09T13:00:00+02:00',
        'level_m': 1.32,
        'flow_m3s': 6.76,
        'yesterday_flow_m3s': 7.15,
    }


def test_statistics_columns_are_not_read_as_current(config: Config) -> None:
    html = SAIH_STATISTICS_HTML.replace('<th>Ayer</th>', '<th>Otro</th>')
    reading = chd._parse_current(html, config.river, TZ)
    assert 'yesterday_flow_m3s' not in reading
    assert reading['flow_m3s'] == EXPECTED_PAGE_FLOW_M3S


def test_fetch_uses_configured_station_url(config: Config) -> None:
    seen: list[str] = []

    def get(url: str) -> str:
        seen.append(url)
        return SAIH_CURRENT_HTML

    reading = chd.fetch(config, get)
    assert seen == [config.river.current_url]
    assert reading['flow_m3s'] == EXPECTED_SAIH_FLOW_M3S


def test_fetch_requires_configured_url(config: Config) -> None:
    river = dataclasses.replace(config.river, current_url='')
    with pytest.raises(ValueError, match='not configured'):
        chd.fetch(dataclasses.replace(config, river=river))
