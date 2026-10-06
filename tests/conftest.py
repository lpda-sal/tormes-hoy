import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tormes_hoy.config import Config, load_config

FIXTURES = Path(__file__).parent / "fixtures"
TZ = "Europe/Madrid"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def config(tmp_path: Path) -> Config:
    base = load_config()
    river = dataclasses.replace(
        base.river, current_url="https://example.invalid/aforos.json"
    )
    return dataclasses.replace(base, data_dir=tmp_path / "data", river=river)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 5, 17, 20, tzinfo=ZoneInfo(TZ))
