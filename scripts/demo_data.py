"""Generate synthetic demo data to preview the web app without API keys.

Usage::

    python scripts/demo_data.py --out _demo
    python -m tormes_hoy.site --data _demo --out _site
    python -m http.server -d _site 8000

Never write demo data into ``data/``: that folder is published.
"""

import argparse
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

from tormes_hoy import yearbook
from tormes_hoy.collect import build_files, write_files
from tormes_hoy.config import load_config
from tormes_hoy.models import JsonDict, SourceResult, envelope
from tormes_hoy.river import daily_from_readings
from tormes_hoy.sources import aemet, chd, meteoblue, openmeteo
from tormes_hoy.timeutil import iso, now_in

DEMO = {"demo": True}


def _hourly(start: datetime, hours: int, offset: float) -> list[JsonDict]:
    rows = []
    for i in range(hours):
        t = start + timedelta(hours=i)
        h = t.hour
        temp = 13 + offset + 7 * math.sin(2 * math.pi * (h - 9) / 24)
        uv = max(0.0, 5.5 * math.sin(math.pi * (h - 8.5) / 11))
        rows.append(
            {
                "time": t.strftime("%Y-%m-%dT%H:%M"),
                "temperature": round(temp, 1),
                "apparent_temperature": round(temp - 1, 1),
                "precipitation_probability": 10 if i < 30 else 45,
                "precipitation": 0.0 if i < 30 else 0.6,
                "weather_code": 1 if 8 <= h <= 19 else 0,
                "wind_speed": 11.0,
                "uv": round(uv, 1),
            }
        )
    return rows


def _daily(start: datetime, offset: float) -> list[JsonDict]:
    return [
        {
            "date": (start + timedelta(days=d)).strftime("%Y-%m-%d"),
            "weather_code": [1, 2, 3, 61, 80, 2, 0][d],
            "temperature_max": round(22 - d * 0.6 + offset, 1),
            "temperature_min": round(9 + d * 0.3, 1),
            "precipitation_probability": [5, 10, 30, 70, 55, 20, 5][d],
            "precipitation": [0, 0, 0.5, 6, 3, 0, 0][d],
            "uv_max": round(5.5 - d * 0.3, 1),
        }
        for d in range(7)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("_demo"))
    args = parser.parse_args()
    config = load_config()
    tz = config.location.timezone
    now = now_in(tz)
    midnight = now.replace(hour=0, minute=0, second=0)
    rng = random.Random(42)

    def forecast(name: str, meta: JsonDict, offset: float) -> SourceResult:
        data: JsonDict = {
            "current": None,
            "hourly": _hourly(midnight, 72, offset),
            "daily": _daily(midnight, offset),
        }
        if name == "openmeteo":
            data["current"] = {**data["hourly"][now.hour], "humidity": 45}
        return SourceResult(name, "ok", data, iso(now), meta={**meta, **DEMO})

    weather = {
        "openmeteo": forecast("openmeteo", openmeteo.META, 0),
        "aemet": forecast("aemet", aemet.META, -0.8),
        "meteoblue": forecast("meteoblue", meteoblue.META, 0.9),
        "observation": SourceResult(
            "aemet",
            "ok",
            {
                "time": iso(now.replace(minute=0, second=0)),
                "station": "2867",
                "station_name": "SALAMANCA AEROPUERTO",
                "temperature": 19.4,
                "humidity": 47,
                "wind_speed": 12.6,
                "wind_direction": 250,
                "precipitation": 0.0,
                "pressure": 918.0,
            },
            iso(now),
            meta={**aemet.META, **DEMO},
        ),
    }

    # Observed river history: hourly readings since 1 Jan of last year.
    readings: list[JsonDict] = []
    start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0)
    hours = int((now - start).total_seconds() // 3600)
    for i in range(hours):
        t = start + timedelta(hours=i)
        doy = t.timetuple().tm_yday
        wet = 1.35 if t.year < now.year else 0.8  # a wetter previous year
        flow = 9 + 25 * wet * max(0, math.cos(2 * math.pi * (doy - 40) / 365))
        flow *= 1 + 0.25 * math.sin(doy / 9) * math.sin(doy / 23)
        flow *= 1 + 0.03 * rng.uniform(-1, 1)
        readings.append(
            {
                "time": iso(t),
                "level_m": round(0.9 + 0.025 * flow, 3),
                "flow_m3s": round(flow, 2),
            }
        )
    daily = daily_from_readings(readings)
    cutoff = iso(now - timedelta(days=30))
    raw = [r for r in readings if str(r["time"]) >= cutoff]
    current = SourceResult(
        "chd", "ok", raw[-1], iso(now), meta={**chd.META, **DEMO}
    )
    files = build_files(config, now, weather, current, raw, daily)

    # Yearbook statistics from a synthetic 10-year series.
    series: yearbook.DailySeries = {}
    day = datetime(2015, 1, 1).date()
    while day.year < 2025:
        doy = day.timetuple().tm_yday
        base = 8 + 30 * max(0, math.cos(2 * math.pi * (doy - 40) / 365))
        flow = base * math.exp(rng.gauss(0, 0.35))
        series[day] = {
            "flow_m3s": round(flow, 2),
            "level_m": round(0.9 + 0.025 * flow, 3),
        }
        day += timedelta(days=1)
    stats = yearbook.build(series, config)
    stats["source"]["demo"] = True
    files[yearbook.OUTPUT_NAME] = envelope(config, now, stats)

    write_files(args.out, files)
    print(json.dumps(sorted(files), indent=1))
    print(f"Demo data written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
