"""Data contract shared by every generated JSON file."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from tormes_hoy.utils.config import Config

SCHEMA_VERSION = 1

_Status = Literal["ok", "stale", "error"]
JsonDict = dict[str, Any]


@dataclass
class SourceResult:
    """Outcome of querying one source.

    Attributes:
        name: Source identifier (``aemet``, ``openmeteo``...).
        status: ``ok``, ``stale`` (old or reused data) or ``error``.
        data: Normalised payload, or ``None`` if nothing is available.
        fetched_at: When the data was obtained (ISO 8601).
        error: Human-readable error, if any.
        meta: Extra source metadata (attribution, kind of data...).
    """

    name: str
    status: _Status
    data: Any = None
    fetched_at: str | None = None
    error: str | None = None
    meta: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        """Return a JSON-serialisable representation."""
        return {
            "status": self.status,
            "source": {"name": self.name, **self.meta},
            "fetched_at": self.fetched_at,
            "error": self.error,
            "data": self.data,
        }


def envelope(config: Config, now: datetime, payload: JsonDict) -> JsonDict:
    """Wrap ``payload`` with the fields every data file must contain."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "app": {
            "name": config.app.name,
            "short_name": config.app.short_name,
        },
        "location": config.location.to_dict(),
        **payload,
    }


def previous_block(previous: JsonDict | None, *keys: str) -> JsonDict | None:
    """Return a nested block of a previously generated file, if present."""
    node: Any = previous
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None


def reuse_or_error(
    name: str,
    error: str,
    previous: JsonDict | None,
    meta: JsonDict | None = None,
) -> SourceResult:
    """Build the result for a failed source.

    If a previous successful payload exists it is kept and marked ``stale``
    so the dashboard can still show the last known values.
    """
    if previous and previous.get("data") is not None:
        return SourceResult(
            name=name,
            status="stale",
            data=previous["data"],
            fetched_at=previous.get("fetched_at"),
            error=error,
            meta=meta or {},
        )
    return SourceResult(
        name=name, status="error", error=error, meta=meta or {}
    )
