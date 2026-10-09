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
| `river-yearbook-stats.json` | yearly, local | `source` (kind `validated`), `method`, `variables.{flow_m3s,level_m}` with `years`, `period`, `detected_shifts`, `stats[{md:"MM-DD",min?,p25,p50,p75,max?,n}]` (366 rows) |

Yearbook `min` and `max` are additive extrema for the same selected years
and configured calendar-day window as `p25`, `p50` (median) and `p75`.
All five statistics are omitted when fewer than two samples are available;
`md` and `n` remain. Older files may omit the extrema; schema version stays 1.
The import accepts validated CEDEX daily TXT or normalised CSV; the TXT
missing-data sentinel `-100.00` is excluded from every statistic.

Hourly row: `time, temperature, humidity?, apparent_temperature?, precipitation_probability,
precipitation, wind_speed, weather_code? (WMO), uv?, sky? (AEMET text), pictocode? (Meteoblue)`.

Hourly `humidity` is optional (number or `null`, %): Open-Meteo supplies
`relative_humidity_2m`, AEMET `humedadRelativa`, and Meteoblue
`relativehumidity`. Missing columns become `null`; older published files may
omit the field until each source refreshes. This additive field keeps schema
version 1. Weather detail uses precipitation probabilities on a 0–100% axis.
Observed rainfall amounts in mm are not plotted as probabilities.
The temperature chart uses degrees Celsius; humidity remains available in
the data but is not displayed as a chart in weather detail.
The latest observation is plotted at its own timestamp, including stale readings,
and is never substituted for a missing forecast value.

Daily row: `date, temperature_max, temperature_min, precipitation_probability,
precipitation?, weather_code?, uv_max?, sky?, pictocode?`.

Daily `pictocode` is optional (number or `null`), preserved from Meteoblue's
`data_day.pictocode`. It uses Meteoblue's daily pictogram set, not WMO codes.
Missing columns become `null`; older files can omit the field until the
next scheduled Meteoblue refresh. This additive field keeps schema version 1
and does not add requests, packages or credit consumption. The web uses each
source's own daily condition for icons and omits missing or unsupported ones.

Current weather observation and model blocks may include `wind_gust`
(number or `null`, km/h), also passed through to `summary.weather_now.data`
and `summary.weather_now_model.data`. It is the maximum gust for the source
interval, not the daily maximum. This additive field keeps schema version 1;
older files without it show an unavailable value. The home screen uses the
gust from the selected weather source, without mixing model and observation.

UV levels: `low` < 3 ≤ `moderate` < 6 ≤ `high` < 8 ≤ `very_high` < 11 ≤ `extreme`.
Stored UV `now` and `now_level` remain generation-time values. The web derives
its displayed reading from `uv.json` hourly samples: select the two valid
samples nearest the current browser time, then use the higher UV and that
sample's timestamp. No schema or stored values change.
River trend: `rising|falling|steady`, comparing the last reading with the one
`trend_window_hours` earlier (flow ±3 %, else level ±1 cm).

`summary.river.flow_status` is an optional, additive field:
`safe|caution|danger|null`. It compares the current flow with the configured
`river.flow_caution_m3s` and `river.flow_danger_m3s`; a threshold belongs to
the higher band. Missing, negative or non-finite flow produces `null`.
These are provisional club display bands, not official flood alerts or a
guarantee that paddling is safe. Static site assembly fills this field when
absent in an older summary, using the repository's configured thresholds and
the same calculation as the collector. It changes only the generated site,
not the source JSON, readings or timestamps, and preserves existing categories.
Missing or invalid flow remains unclassified, never automatically green.
Schema version remains 1.

UV `protection.from` and `protection.to` retain their `HH:MM` format but now
use linear interpolation at the first and last threshold crossings. The
start rounds down and the end rounds up to the minute. Missing adjacent
values are not interpolated; available above-threshold endpoints are used
instead. Multiple intervals are conservatively combined from first to last.
The web's upcoming-weather strip reads the full Open-Meteo forecast from
`weather.json` for 24 hours starting at the current local hour, with the
window end excluded; `summary.today` continues to mean the rest of the
current day.
The home rain chart aligns the three hourly forecast sources over that same
time window, preserving missing probabilities as gaps. Night shading repeats
today's civil-twilight clock times across the visible dates without an extra
solar request; missing solar data leaves the chart unshaded.
