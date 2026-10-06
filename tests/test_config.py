from tormes_hoy.config import load_config


def test_location_is_centralized_in_config() -> None:
    config = load_config()
    assert config.location.id == "salamanca"
    assert config.location.timezone == "Europe/Madrid"
    assert config.app.name == "Tormes Hoy"


def test_river_station_is_salamanca() -> None:
    assert load_config().river.station == "EA087"
