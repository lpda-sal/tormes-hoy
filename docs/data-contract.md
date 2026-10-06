# Data contract (schema_version 1)

All files live in `data/` and share this envelope:

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-05T17:17:02+02:00",
  "app": {"name": "Tormes Hoy", "short_name": "Tormes Hoy"},
  "location": {"id": "salamanca", "name": "Salamanca", "lat": 40.965, "lon": -5.664, "timezone": "Europe/Madrid"}
}
```

Source blocks:

```json
{"status": "ok|stale|error", "source": {"name": "aemet", "label": "AEMET", "attribution": "..."},
 "fetched_at": "ISO 8601 | null", "error": "string | null", "data": {}}
```

Times: hourly series use local `YYYY-MM-DDTHH:MM`; instants use ISO 8601
with offset. Units: °C, %, mm, km/h, m³/s, m.

| File | Written by | Content |
|---|---|---|
| `summary.json` | hourly | `weather_now` (AEMET), `weather_now_model` (Open-Meteo current), `today` (rest of day, hourly), `uv` (now, level, max, protection), `river` (latest reading + `trend`), `next_days` |
| `weather.json` | hourly | `observation`; `forecasts.{aemet,openmeteo,meteoblue}` each with `data.hourly[]` and `data.daily[]` |
| `uv.json` | hourly | `data`: `date`, `threshold`, `now`, `now_level`, `max`, `max_time`, `protection{from,to}\|null`, `hourly[{time,uv}]` |
| `river-observed-30d.json` | hourly | `source` (kind `provisional`), `current` (source block), `readings[{time,level_m,flow_m3s}]` |
| `river-observed-daily.json` | hourly | `daily[{date, level_m{min,mean,max}, flow_m3s{min,mean,max}, n}]` from 1 January of the previous year (`river.daily_years = 2`) |
| `river-yearbook-stats.json` | yearly, local | `source` (kind `validated`), `method`, `variables.{flow_m3s,level_m}` with `years`, `period`, `detected_shifts`, `stats[{md:"MM-DD",p25,p50,p75,n}]` (366 rows) |

Hourly row: `time, temperature, apparent_temperature?, precipitation_probability,
precipitation, wind_speed, weather_code? (WMO), uv?, sky? (AEMET text), pictocode? (Meteoblue)`.

Daily row: `date, temperature_max, temperature_min, precipitation_probability,
precipitation?, weather_code?, uv_max?, sky?`.

UV levels: `low` < 3 ≤ `moderate` < 6 ≤ `high` < 8 ≤ `very_high` < 11 ≤ `extreme`.
River trend: `rising|falling|steady`, comparing the last reading with the one
`trend_window_hours` earlier (flow ±3 %, else level ±1 cm).
