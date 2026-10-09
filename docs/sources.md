# Data sources

| Source | Used for | Auth | Module (relative to `tormes_hoy/`) |
|---|---|---|---|
| AEMET OpenData – conventional observation (`/observacion/convencional/datos/estacion/{idema}`) | Weather now | `AEMET_API_KEY` (free) | `source_data/sources/aemet.py` |
| AEMET OpenData – municipality forecast (`/prediccion/especifica/municipio/{horaria,diaria}/{code}`) | Forecast comparison | same | `source_data/sources/aemet.py` |
| Open-Meteo `/v1/forecast` | Summary forecast, UV, comparison | none | `source_data/sources/openmeteo.py` |
| Meteoblue `basic-1h_basic-day` | Forecast comparison | `METEOBLUE_API_KEY` (1-year free trial) | `source_data/sources/meteoblue.py` |
| SAIH Duero station EA087 | River now | none | `source_data/sources/chd.py` |
| CHD yearbooks (anuarios de aforos) | River statistics | none | `yearbook/builder.py` |

## Reference location

The public CSCK canoe club coordinates are configured in the `[location]`
section of `tormes_hoy/config/config.toml`. The collector publishes them in
each file's location envelope. Sunrise-Sunset.org, Open-Meteo and Meteoblue
use this same point; the latter two provide model forecasts, not observations
from a selected physical station. Changing the location invalidates cached
weather results, including Meteoblue's usual multi-hour cache, on the next
collection. Existing published JSON is updated by the collector, not by hand.

## Solar times

The web app calls `https://api.sunrise-sunset.org/v2` using the coordinates,
timezone and local date from the configured location. No API key is needed.
It reads `civil_twilight_begin`, `sunrise`, `sunset` and
`civil_twilight_end`. Responses are cached in browser storage by location and
date, with an in-memory fallback if storage is unavailable. New dates require
a successful request; yesterday's solar times are never used for today.
The request sends coordinates and date to this third-party service. It does
not change the collector, hourly Actions budget or published JSON contract.
The solar detail view (`#/sun`) shows the date in Spanish without a separate
location label. Its plain-text attribution reads "Fuente: Sunrise-Sunset";
nautical and astronomical events are also shown when available, as required by
the API.

## AEMET

The configured observation station is Salamanca, in the city rather than
Salamanca Airport (Matacan). On 2026-10-08, the official hourly station list
for Salamanca province contained 15 stations. Comparing their published
coordinates with the club's configured point gave Salamanca as the nearest:
about 4.05 km, compared with 11.76 km for the airport and 13.29 km for
Barbadillo. These are straight-line distances, not road distances.
Only stations in the hourly observation catalogue were compared, not every
historical or privately operated weather station.

Official references:

- [AEMET hourly observations and station coordinates](https://www.aemet.es/es/eltiempo/observacion/ultimosdatos).
- [Salamanca municipality forecast and nearby observation stations](https://www.aemet.es/es/eltiempo/prediccion/municipios/salamanca-id37274).

The municipality forecast remains for Salamanca capital. It is independent
of the observation station; all station and municipality identifiers remain
in configuration.

Two-step API: the first call returns `{"estado": 200, "datos": url}`; the
data is downloaded from `datos`. Payloads may be ISO-8859-15 (handled in
`source_data/network_client.get_json`). Observation `fint` is assumed UTC;
wind `vv` and maximum gust `vmax` m/s → km/h. Gusts belong to the latest
observation interval; a missing gust is not replaced with an older reading.

The current-weather model fallback requests Open-Meteo `wind_gusts_10m`
with `wind_speed_unit=kmh`. Both sources publish the optional `wind_gust`
field. The home card shows the maximum gust for the selected source's
interval, not the daily maximum; model values keep the estimate caption.

## Meteoblue budget

Free trial: 10 M credits for one year. If a call costs ~8,000 credits,
that is ~1,250 calls/year. Every 6 h = 1,460 calls/year: **slightly above**;
measure the real cost of `basic-1h_basic-day` and adjust
`meteoblue.refresh_every_hours` (8 h ≈ 1,095 calls). Without a key, or
after the trial, the source reports `error` and the rest keeps working.

The collector preserves `data_day.pictocode` from the existing `basic-day`
package for daily icons, without changing the refresh budget. Old cached
rows remain without this optional field until the next normal refresh.
The web follows the official [daily pictogram meanings](https://docs.meteoblue.com/en/meteo/variables/pictograms):
codes 1-17 and 20-25 are supported; 18/19 are unused. These are Meteoblue's
native codes, not WMO codes.

Hourly rows use a different official set: `pictocode` 1-35 (36/37 unused),
with other meanings, e.g. 4 is "clear with few low clouds" and 7 is "partly
cloudy" (daily 4 is overcast and daily 7 is showers). The web therefore reads
hourly and daily codes with separate tables and never mixes them. Day and night
variants share a code, so night is derived from sunrise/sunset in the web.

## CHD current readings

The collector reads the official station page at
`https://www.saihduero.es/risr/EA087`. Its `Nivel` and `Caudal` table uses
decimal commas and local `DD/MM/YYYY HH:MM` timestamps. These readings are
provisional and may be revised by SAIH Duero.

The same page's statistics table (identified by its `Ayer` column header)
gives yesterday's mean flow, which the collector stores as
`yesterday_flow_m3s` for the river trend. The page also shows a "Tendencia"
icon; it is not used because its window and thresholds are undocumented and
it cannot be backtested. No extra request is made.

## Yearbook import (once a year, locally)

1. Download [CEDEX station 2087: Tormes at Salamanca](https://ceh.cedex.es/anuarioaforos/afo/estaf-datos_descarga.asp?indroea=2087).
   Select "Alturas y caudales medios diarios" and the available year range.
   The yearbook station code differs from the SAIH code `EA087`.
2. Import the original TXT download directly from the repository root:
   ```bash
   mamba run -n tormes-hoy tormes-hoy-build-yearbook resultado5655.txt
   ```
   The reader skips the header, parses `DD/MM/YYYY`, and reads height in m
   and flow in m3/s. `-100.00` means missing, not a negative reading;
   legitimate zeros remain zero. UTF-8 and Latin-1 exports are supported.
   Mixed stations, duplicate dates and malformed daily rows are rejected.
3. The command writes `data/river-yearbook-stats.json` by default and prints
   its absolute path. Use `--out-dir path/to/output` to change that directory.
   Rebuild the preview with `tormes-hoy-build-site` and reload the river view.
4. Normalised CSV input remains supported, with one row per day:
   ```csv
   date,flow_m3s,level_m
   2015-01-01,12.4,0.98
   ```
   Empty cells are allowed. Do not use `data/river-observed-daily.json` as
   input: provisional observations are not yearbook data.

The statistics use the last 10 complete years **available in the
yearbooks** (not necessarily the last 10 calendar years). Completeness is
checked per calendar year and variable, requiring at least 300 values.
Minimum, P25, median (`p50`), P75 and maximum all use the same calendar date
across the selected years (`smoothing_window_days = 0`), without neighbouring
days. Dates with fewer than two available samples retain only their date and
sample count, without invented statistics; this can affect February 29.
For level, a yearly median jump above
`level_shift_threshold_m` is treated as a datum change and only later years
are used. Observed readings are never added to these statistics.
