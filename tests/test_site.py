from pathlib import Path

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
