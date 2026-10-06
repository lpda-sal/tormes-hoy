"""Validated river statistics from CHD yearbooks (anuarios de aforos).

Run once a year, locally (not in GitHub Actions)::

    python -m tormes_hoy.yearbook path/to/daily.csv

The input is a normalised CSV prepared from the yearbooks with columns
``date,flow_m3s,level_m`` (one row per day; empty cells allowed).
Output: ``data/river-yearbook-stats.json`` with day-of-year P25, median
and P75 for flow and level. Yearbook data is never mixed with our own
observed readings.
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median, quantiles

from tormes_hoy.config import Config, load_config
from tormes_hoy.models import JsonDict, envelope
from tormes_hoy.timeutil import now_in

OUTPUT_NAME = "river-yearbook-stats.json"
VARIABLES = ("flow_m3s", "level_m")
REFERENCE_YEAR = 2000  # leap year: every MM-DD (incl. 02-29) has a slot
MIN_DAYS_PER_YEAR = 300


DailySeries = dict[date, dict[str, float | None]]


def _to_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value.replace(",", "."))


def load_csv(path: Path) -> DailySeries:
    """Read the normalised yearbook CSV."""
    series: DailySeries = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            day = date.fromisoformat(row["date"].strip())
            series[day] = {v: _to_float(row.get(v)) for v in VARIABLES}
    return series


def complete_years(series: DailySeries, variable: str) -> list[int]:
    """Years with at least ``MIN_DAYS_PER_YEAR`` values of ``variable``."""
    counts: dict[int, int] = defaultdict(int)
    for day, values in series.items():
        if values.get(variable) is not None:
            counts[day.year] += 1
    return sorted(y for y, n in counts.items() if n >= MIN_DAYS_PER_YEAR)


def yearly_medians(series: DailySeries, variable: str) -> dict[int, float]:
    """Median of ``variable`` per year."""
    by_year: dict[int, list[float]] = defaultdict(list)
    for day, values in series.items():
        value = values.get(variable)
        if value is not None:
            by_year[day.year].append(value)
    return {year: median(vals) for year, vals in sorted(by_year.items())}


def detect_shifts(medians: dict[int, float], threshold: float) -> list[int]:
    """Years whose median jumps more than ``threshold`` from the previous.

    A jump in the level median usually means a gauge datum change, which
    makes older level values not comparable.
    """
    years = sorted(medians)
    return [
        cur
        for prev, cur in zip(years, years[1:], strict=False)
        if abs(medians[cur] - medians[prev]) > threshold
    ]


def _reference_days() -> list[date]:
    start = date(REFERENCE_YEAR, 1, 1)
    return [start + timedelta(days=i) for i in range(366)]


def _slot(day: date) -> int:
    """Index 0..365 of a calendar day in the leap reference year."""
    return (
        date(REFERENCE_YEAR, day.month, day.day) - date(REFERENCE_YEAR, 1, 1)
    ).days


def day_of_year_stats(
    series: DailySeries, variable: str, years: list[int], window: int
) -> list[JsonDict]:
    """P25/P50/P75 for each calendar day using a +/- ``window`` day window."""
    slots: dict[int, list[float]] = defaultdict(list)
    wanted = set(years)
    for day, values in series.items():
        value = values.get(variable)
        if value is not None and day.year in wanted:
            slots[_slot(day)].append(value)
    out: list[JsonDict] = []
    for index, ref in enumerate(_reference_days()):
        pool: list[float] = []
        for offset in range(-window, window + 1):
            pool.extend(slots.get((index + offset) % 366, []))
        if len(pool) < 2:
            out.append({"md": ref.strftime("%m-%d"), "n": len(pool)})
            continue
        q1, q2, q3 = quantiles(pool, n=4, method="inclusive")
        out.append(
            {
                "md": ref.strftime("%m-%d"),
                "p25": round(q1, 3),
                "p50": round(q2, 3),
                "p75": round(q3, 3),
                "n": len(pool),
            }
        )
    return out


def build(series: DailySeries, config: Config) -> JsonDict:
    """Compute the statistics payload for flow and level."""
    cfg = config.yearbook
    variables: JsonDict = {}
    for variable in VARIABLES:
        years = complete_years(series, variable)[-cfg.years :]
        shifts: list[int] = []
        if variable == "level_m" and years:
            medians = {
                y: m
                for y, m in yearly_medians(series, variable).items()
                if y in years
            }
            shifts = detect_shifts(medians, cfg.level_shift_threshold_m)
            if shifts:
                years = [y for y in years if y >= shifts[-1]]
        variables[variable] = {
            "years": years,
            "period": f"{years[0]}-{years[-1]}" if years else None,
            "detected_shifts": shifts,
            "stats": day_of_year_stats(
                series, variable, years, cfg.smoothing_window_days
            )
            if years
            else [],
        }
    return {
        "status": "ok",
        "source": {
            "name": "chd-yearbook",
            "label": "CHD – anuarios de aforos",
            "kind": "validated",
            "station": config.river.station,
        },
        "method": {
            "percentiles": [25, 50, 75],
            "smoothing_window_days": cfg.smoothing_window_days,
            "max_years": cfg.years,
        },
        "variables": variables,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="normalised daily CSV")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    config = load_config()
    out_dir = args.out_dir or config.data_dir
    payload = envelope(
        config,
        now_in(config.location.timezone),
        build(load_csv(args.csv), config),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / OUTPUT_NAME
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
