# Data sources

| Source | Used for | Auth | Module |
|---|---|---|---|
| AEMET OpenData – conventional observation (`/observacion/convencional/datos/estacion/{idema}`) | Weather now | `AEMET_API_KEY` (free) | `sources/aemet.py` |
| AEMET OpenData – municipality forecast (`/prediccion/especifica/municipio/{horaria,diaria}/{code}`) | Forecast comparison | same | `sources/aemet.py` |
| Open-Meteo `/v1/forecast` | Summary forecast, UV, comparison | none | `sources/openmeteo.py` |
| Meteoblue `basic-1h_basic-day` | Forecast comparison | `METEOBLUE_API_KEY` (1-year free trial) | `sources/meteoblue.py` |
| CHD open data "Estado Aforos" | River now | none | `sources/chd.py` |
| CHD yearbooks (anuarios de aforos) | River statistics | none | `tormes_hoy/yearbook.py` |

## AEMET

Two-step API: the first call returns `{"estado": 200, "datos": url}`; the
data is downloaded from `datos`. Payloads may be ISO-8859-15 (handled in
`net.get_json`). Observation `fint` is assumed UTC; wind `vv` m/s → km/h.

## Meteoblue budget

Free trial: 10 M credits for one year. If a call costs ~8,000 credits,
that is ~1,250 calls/year. Every 6 h = 1,460 calls/year: **slightly above**;
measure the real cost of `basic-1h_basic-day` and adjust
`meteoblue.refresh_every_hours` (8 h ≈ 1,095 calls). Without a key, or
after the trial, the source reports `error` and the rest keeps working.

## CHD current readings

Endpoint and field names are configurable (`[river]` in `config.toml`)
until verified. The parser accepts a list of records or common wrappers
(`data`, `datos`, `features[].properties`…), decimal commas, and
`YYYY-MM-DD HH:MM` local times.

## Yearbook import (once a year, locally)

1. Download the yearbook data of the Salamanca station (check its code in
   the yearbooks; it may differ from `EA087`).
2. Build a CSV, one row per day:
   ```csv
   date,flow_m3s,level_m
   2015-01-01,12.4,0.98
   ```
   Empty cells are allowed. Years with < 300 values are ignored.
3. Run `python -m tormes_hoy.yearbook path/to/daily.csv` and commit
   `data/river-yearbook-stats.json`.

The statistics use the last 10 complete years **available in the
yearbooks** (not calendar years), a ±7-day window around each calendar day,
and P25/P50/P75. For level, a yearly median jump above
`level_shift_threshold_m` is treated as a datum change and only later years
are used. Observed readings are never added to these statistics.
