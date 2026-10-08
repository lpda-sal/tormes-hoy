import json
import shutil
from pathlib import Path

import pytest

from tormes_hoy.site.builder import _build_site


def test_build_site_copies_web_and_data(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<html></html>")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "summary.json").write_text("{}")
    out = _build_site(tmp_path, tmp_path / "_site")
    assert (out / "index.html").exists()
    assert (out / "data" / "summary.json").exists()
    assert (out / ".nojekyll").exists()


@pytest.mark.parametrize(
    ("flow", "has_status", "published", "expected"),
    [
        (6.52, False, None, "safe"),
        (10.0, False, None, "caution"),
        (12.0, False, None, "danger"),
        (None, False, None, None),
        (-1.0, False, None, None),
        (6.52, True, "danger", "danger"),
        (6.52, True, None, None),
    ],
)
def test_build_site_completes_only_missing_flow_status(
    tmp_path: Path,
    flow: float | None,
    has_status: bool,
    published: str | None,
    expected: str | None,
) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "data").mkdir()
    config_dir = tmp_path / "tormes_hoy" / "config"
    config_dir.mkdir(parents=True)
    project = Path(__file__).resolve().parents[1]
    shutil.copy2(
        project / "tormes_hoy" / "config" / "config.toml",
        config_dir / "config.toml",
    )
    river: dict[str, object] = {"data": {"flow_m3s": flow}}
    if has_status:
        river["flow_status"] = published
    summary = {"generated_at": "2026-10-08T16:00:00+02:00", "river": river}
    source = tmp_path / "data" / "summary.json"
    source.write_text(json.dumps(summary), encoding="utf-8")
    original = source.read_bytes()
    out = _build_site(tmp_path, tmp_path / "_site")
    result = json.loads((out / "data" / "summary.json").read_text("utf-8"))
    assert result["river"]["flow_status"] == expected
    assert result["river"]["data"] == river["data"]
    assert result["generated_at"] == summary["generated_at"]
    assert source.read_bytes() == original
