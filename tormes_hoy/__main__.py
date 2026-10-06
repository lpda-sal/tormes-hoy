"""Entry point: ``python -m tormes_hoy`` runs the hourly collection."""

import logging

from tormes_hoy.collect import run, write_files
from tormes_hoy.config import load_config


def main() -> int:
    """Collect data, write ``data/*.json`` and print source statuses.

    Always returns 0: a failing source is reported in the data, not by
    failing the scheduled job.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()
    files = run(config)
    write_files(config.data_dir, files)
    summary = files["summary.json"]
    for key in ("weather_now", "today", "uv", "river", "next_days"):
        print(f"{key}: {summary[key]['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
