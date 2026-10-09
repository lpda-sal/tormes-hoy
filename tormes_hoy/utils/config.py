"""Load the package configuration (``config.toml``) into typed objects."""

import tomllib
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path(__file__).parents[1] / 'config' / 'config.toml'


@dataclass(frozen=True)
class _AppInfo:
    """Public identity of the app."""

    name: str
    short_name: str


@dataclass(frozen=True)
class _Location:
    """Location every source is queried for."""

    id: str
    name: str
    lat: float
    lon: float
    timezone: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            'id': self.id,
            'name': self.name,
            'lat': self.lat,
            'lon': self.lon,
            'timezone': self.timezone,
        }


@dataclass(frozen=True)
class _OpenMeteoConfig:
    """Open-Meteo settings."""

    base_url: str
    forecast_days: int


@dataclass(frozen=True)
class _AemetConfig:
    """AEMET OpenData settings."""

    base_url: str
    station_idema: str
    municipality_code: str
    stale_after_hours: float


@dataclass(frozen=True)
class _MeteoblueConfig:
    """Meteoblue settings."""

    base_url: str
    refresh_every_hours: float
    stale_after_hours: float


@dataclass(frozen=True)
class RiverConfig:
    """CHD river gauging station settings."""

    station: str
    flow_caution_m3s: float
    flow_danger_m3s: float
    current_url: str
    station_field: str
    level_field: str
    flow_field: str
    time_field: str
    observed_days: int
    daily_years: int
    stale_after_hours: float
    trend_flow_ratio: float
    trend_flow_min_m3s: float


@dataclass(frozen=True)
class _YearbookConfig:
    """Settings for the yearbook statistics."""

    years: int
    smoothing_window_days: int
    level_shift_threshold_m: float


@dataclass(frozen=True)
class _UvConfig:
    """UV settings."""

    protection_threshold: float


@dataclass(frozen=True)
class Config:
    """Whole application configuration."""

    app: _AppInfo
    location: _Location
    openmeteo: _OpenMeteoConfig
    aemet: _AemetConfig
    meteoblue: _MeteoblueConfig
    river: RiverConfig
    yearbook: _YearbookConfig
    uv: _UvConfig
    data_dir: Path


def load_config(path: Path = _DEFAULT_CONFIG_PATH) -> Config:
    """Load and validate the configuration file.

    Args:
        path: Path to a TOML file with the same layout as ``config.toml``.

    Returns:
        The parsed configuration.

    Raises:
        KeyError: If a required section or key is missing.
        ValueError: If river flow thresholds are invalid.
    """
    with path.open('rb') as fh:
        raw = tomllib.load(fh)
    river = RiverConfig(**raw['river'])
    if not (
        isfinite(river.flow_caution_m3s)
        and isfinite(river.flow_danger_m3s)
        and 0 < river.flow_caution_m3s < river.flow_danger_m3s
    ):
        raise ValueError(
            'River flow thresholds must be positive and increasing'
        )
    return Config(
        app=_AppInfo(**raw['app']),
        location=_Location(**raw['location']),
        openmeteo=_OpenMeteoConfig(**raw['openmeteo']),
        aemet=_AemetConfig(**raw['aemet']),
        meteoblue=_MeteoblueConfig(**raw['meteoblue']),
        river=river,
        yearbook=_YearbookConfig(**raw['yearbook']),
        uv=_UvConfig(**raw['uv']),
        data_dir=Path(raw['output']['data_dir']),
    )
