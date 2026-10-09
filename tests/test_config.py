import json
import tomllib
from pathlib import Path

import pytest

from tormes_hoy.utils.config import load_config

EXPECTED_CLUB_LATITUDE = 40.95726767218838
EXPECTED_CLUB_LONGITUDE = -5.638355587757416


def test_location_is_centralized_in_config() -> None:
    config = load_config()
    assert config.location.id == "salamanca"
    assert config.location.timezone == "Europe/Madrid"
    assert config.location.lat == EXPECTED_CLUB_LATITUDE
    assert config.location.lon == EXPECTED_CLUB_LONGITUDE
    assert config.app.name == "Tormes Hoy"


def test_river_station_is_salamanca() -> None:
    assert load_config().river.station == "EA087"


def test_weather_station_is_salamanca_city() -> None:
    assert load_config().aemet.station_idema == "2870X"


@pytest.mark.parametrize(
    "caution", ["equal", "above", "0.0", "-1.0", "nan", "inf"]
)
def test_invalid_flow_thresholds_fail(tmp_path: Path, caution: str) -> None:
    source = Path(__file__).parents[1] / "tormes_hoy/config/config.toml"
    raw = tomllib.loads(source.read_text(encoding="utf-8"))
    danger = raw["river"]["flow_danger_m3s"]
    raw["river"]["flow_caution_m3s"] = float(
        {"equal": danger, "above": danger + 1}.get(caution, caution)
    )
    path = tmp_path / "config.toml"
    path.write_text(
        "\n\n".join(
            f"[{section}]\n"
            + "\n".join(
                f"{key} = "
                + (
                    repr(value)
                    if isinstance(value, float)
                    else json.dumps(value)
                )
                for key, value in fields.items()
            )
            for section, fields in raw.items()
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="thresholds"):
        load_config(path)
