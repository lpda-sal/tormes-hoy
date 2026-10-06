"""Load the package configuration (``config.toml``) into typed objects."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.toml")


@dataclass(frozen=True)
class AppInfo:
    """Public identity of the app."""

    name: str
    short_name: str


@dataclass(frozen=True)
class Location:
    """Location every source is queried for."""

    id: str
    name: str
    lat: float
    lon: float
    timezone: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "timezone": self.timezone,
        }


@dataclass(frozen=True)
class OpenMeteoConfig:
    """Open-Meteo settings."""

    base_url: str
    forecast_days: int


@dataclass(frozen=True)
class AemetConfig:
    """AEMET OpenData settings."""

    base_url: str
    station_idema: str
    municipality_code: str
    stale_after_hours: float


@dataclass(frozen=True)
class MeteoblueConfig:
    """Meteoblue settings."""

    base_url: str
    refresh_every_hours: float
    stale_after_hours: float


@dataclass(frozen=True)
class RiverConfig:
    """CHD river gauging station settings."""

    station: str
    current_url: str
    station_field: str
    level_field: str
    flow_field: str
    time_field: str
    observed_days: int
    daily_years: int
    stale_after_hours: float
    trend_window_hours: float
    trend_flow_ratio: float
    trend_level_m: float


@dataclass(frozen=True)
class YearbookConfig:
    """Settings for the yearbook statistics."""

    years: int
    smoothing_window_days: int
    level_shift_threshold_m: float


@dataclass(frozen=True)
class UvConfig:
    """UV settings."""

    protection_threshold: float


@dataclass(frozen=True)
class Config:
    """Whole application configuration."""

    app: AppInfo
    location: Location
    openmeteo: OpenMeteoConfig
    aemet: AemetConfig
    meteoblue: MeteoblueConfig
    river: RiverConfig
    yearbook: YearbookConfig
    uv: UvConfig
    data_dir: Path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load and validate the configuration file.

    Args:
        path: Path to a TOML file with the same layout as ``config.toml``.

    Returns:
        The parsed configuration.

    Raises:
        KeyError: If a required section or key is missing.
    """
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return Config(
        app=AppInfo(**raw["app"]),
        location=Location(**raw["location"]),
        openmeteo=OpenMeteoConfig(**raw["openmeteo"]),
        aemet=AemetConfig(**raw["aemet"]),
        meteoblue=MeteoblueConfig(**raw["meteoblue"]),
        river=RiverConfig(**raw["river"]),
        yearbook=YearbookConfig(**raw["yearbook"]),
        uv=UvConfig(**raw["uv"]),
        data_dir=Path(raw["output"]["data_dir"]),
    )
