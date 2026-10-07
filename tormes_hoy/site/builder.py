"""Assemble the static site (``web/`` + ``data/``) into ``_site/``.

Used by the GitHub Actions workflow and for local preview::

    tormes-hoy-build-site && python -m http.server -d _site 8000

Run directly with ``python -m tormes_hoy.build_site``.
"""

import argparse
import shutil
from pathlib import Path


def _build_site(root: Path, out: Path) -> Path:
    """Copy the web app and the data files into ``out``.

    Args:
        root: Repository root (contains ``web/`` and ``data/``).
        out: Output directory, recreated from scratch.
    """
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(root / "web", out)
    data_out = out / "data"
    data_out.mkdir(parents=True, exist_ok=True)
    for path in sorted((root / "data").glob("*.json")):
        shutil.copy2(path, data_out / path.name)
    (out / ".nojekyll").touch()
    return out


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Build the static site.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("_site"))
    args = parser.parse_args(argv)
    print(f"Built {_build_site(args.root, args.out)}")
    return 0
