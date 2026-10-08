"""Validated river statistics from CHD yearbooks (anuarios de aforos).

Run once a year, locally (not in GitHub Actions)::

    tormes-hoy-build-yearbook path/to/yearbook.txt

Run directly with ``python -m tormes_hoy.build_yearbook``.

The input is a CEDEX daily TXT download or a normalised CSV with columns
``date,flow_m3s,level_m`` (one row per day; empty cells allowed).
The CEDEX missing-data sentinel -100 is excluded.
Output: ``data/river-yearbook-stats.json`` with day-of-year minimum,
P25, median, P75 and maximum for flow and level. Yearbook data is never
mixed with our own observed readings.
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import isfinite
from pathlib import Path
from statistics import median, quantiles

from tormes_hoy.utils.config import Config, load_config
from tormes_hoy.utils.models import JsonDict, envelope
from tormes_hoy.utils.timeutil import now_in

_OUTPUT_NAME = 'river-yearbook-stats.json'
_VARIABLES = ('flow_m3s', 'level_m')
_REFERENCE_YEAR = 2000  # leap year: every MM-DD (incl. 02-29) has a slot
_MIN_DAYS_PER_YEAR = 300
_CEDEX_MISSING_VALUE = -100.0
_CEDEX_COLUMN_COUNT = 4


_DailySeries = dict[date, dict[str, float | None]]


def _to_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    number = float(value.replace(',', '.'))
    if not isfinite(number):
        raise ValueError('Yearbook values must be finite')
    return None if number == _CEDEX_MISSING_VALUE else number


def _load_csv(path: Path) -> _DailySeries:
    """Read the normalised yearbook CSV."""
    series: _DailySeries = {}
    with path.open(newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            day = date.fromisoformat(row['date'].strip())
            series[day] = {v: _to_float(row.get(v)) for v in _VARIABLES}
    return series


def _parse_cedex(text: str) -> _DailySeries:
    """Parse a single-station CEDEX daily heights and flows download."""
    if 'alturas y caudales medios diarios' not in text.lower():
        raise ValueError('Expected a CEDEX daily heights and flows download')
    series: _DailySeries = {}
    stations: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = line.split()
        if not fields or not fields[0].isdigit():
            continue
        if len(fields) != _CEDEX_COLUMN_COUNT:
            raise ValueError(f'Invalid CEDEX daily row at line {line_number}')
        station, timestamp, level, flow = fields
        stations.add(station)
        if len(stations) > 1:
            raise ValueError('Yearbook input must contain only one station')
        day = datetime.strptime(timestamp, '%d/%m/%Y').date()
        if day in series:
            raise ValueError(f'Duplicate yearbook date: {day}')
        series[day] = {
            'flow_m3s': _to_float(flow),
            'level_m': _to_float(level),
        }
    if not series:
        raise ValueError('No daily readings found in the CEDEX download')
    return series


def _load_daily(path: Path) -> _DailySeries:
    """Read normalised CSV or the original CEDEX TXT export."""
    if path.suffix.lower() == '.csv':
        return _load_csv(path)
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='latin-1')
    return _parse_cedex(text)


def _complete_years(series: _DailySeries, variable: str) -> list[int]:
    """Years with at least ``_MIN_DAYS_PER_YEAR`` values of ``variable``."""
    counts: dict[int, int] = defaultdict(int)
    for day, values in series.items():
        if values.get(variable) is not None:
            counts[day.year] += 1
    return sorted(y for y, n in counts.items() if n >= _MIN_DAYS_PER_YEAR)


def _yearly_medians(series: _DailySeries, variable: str) -> dict[int, float]:
    """Median of ``variable`` per year."""
    by_year: dict[int, list[float]] = defaultdict(list)
    for day, values in series.items():
        value = values.get(variable)
        if value is not None:
            by_year[day.year].append(value)
    return {year: median(vals) for year, vals in sorted(by_year.items())}


def _detect_shifts(medians: dict[int, float], threshold: float) -> list[int]:
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
    start = date(_REFERENCE_YEAR, 1, 1)
    return [start + timedelta(days=i) for i in range(366)]


def _slot(day: date) -> int:
    """Index 0..365 of a calendar day in the leap reference year."""
    return (
        date(_REFERENCE_YEAR, day.month, day.day) - date(_REFERENCE_YEAR, 1, 1)
    ).days


def _day_of_year_stats(
    series: _DailySeries, variable: str, years: list[int], window: int
) -> list[JsonDict]:
    """Extrema and quartiles using a +/- ``window`` day window."""
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
        minimum_samples = 2
        if len(pool) < minimum_samples:
            out.append({'md': ref.strftime('%m-%d'), 'n': len(pool)})
            continue
        q1, q2, q3 = quantiles(pool, n=4, method='inclusive')
        out.append(
            {
                'md': ref.strftime('%m-%d'),
                'min': round(min(pool), 3),
                'p25': round(q1, 3),
                'p50': round(q2, 3),
                'p75': round(q3, 3),
                'max': round(max(pool), 3),
                'n': len(pool),
            }
        )
    return out


def _build(series: _DailySeries, config: Config) -> JsonDict:
    """Compute the statistics payload for flow and level."""
    cfg = config.yearbook
    variables: JsonDict = {}
    for variable in _VARIABLES:
        years = _complete_years(series, variable)[-cfg.years :]
        shifts: list[int] = []
        if variable == 'level_m' and years:
            medians = {
                y: m
                for y, m in _yearly_medians(series, variable).items()
                if y in years
            }
            shifts = _detect_shifts(medians, cfg.level_shift_threshold_m)
            if shifts:
                years = [y for y in years if y >= shifts[-1]]
        variables[variable] = {
            'years': years,
            'period': f'{years[0]}-{years[-1]}' if years else None,
            'detected_shifts': shifts,
            'stats': _day_of_year_stats(
                series, variable, years, cfg.smoothing_window_days
            )
            if years
            else [],
        }
    return {
        'status': 'ok',
        'source': {
            'name': 'chd-yearbook',
            'label': 'CHD – anuarios de aforos',
            'kind': 'validated',
            'station': config.river.station,
        },
        'method': {
            'percentiles': [25, 50, 75],
            'smoothing_window_days': cfg.smoothing_window_days,
            'max_years': cfg.years,
        },
        'variables': variables,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        'input', type=Path, help='CEDEX daily TXT or normalised daily CSV'
    )
    parser.add_argument('--out-dir', type=Path, default=None)
    args = parser.parse_args(argv)
    config = load_config()
    out_dir = args.out_dir or config.data_dir
    payload = envelope(
        config,
        now_in(config.location.timezone),
        _build(_load_daily(args.input), config),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / _OUTPUT_NAME
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8',
    )
    print(f'Wrote {target.resolve()}')
    return 0
