# Review checklist

This project was generated as a complete first version **without access to
the real APIs**. Parsers follow the public documentation and are tested
with synthetic fixtures (`tests/fixtures/README.md`). Verify each item,
replace fixtures with real responses and tick it.

## Data sources

- [ ] **AEMET station**: confirm `station_idema = "2867"` (Salamanca
      Aeropuerto, Matacán) or choose a station closer to the city.
- [ ] **AEMET municipality**: confirm `municipality_code = "37274"`.
- [ ] **AEMET observation**: confirm `fint` is UTC and field names
      (`ta`, `hr`, `vv`, `dv`, `prec`, `pres`, `ubi`).
- [ ] **AEMET forecasts**: check hourly blocks (`temperatura`,
      `estadoCielo`, `precipitacion`, `probPrecipitacion` with 6-hour
      `periodo` like `"0814"`, `vientoAndRachaMax`) and daily fields
      (`temperatura.maxima/minima`, `probPrecipitacion` `"00-24"`, `uvMax`).
- [ ] **Open-Meteo**: check variables and that `uv_index` is present.
- [ ] **Meteoblue**: confirm package URL, field names (`data_1h`,
      `data_day`, `windspeed`, `uvindex`, `pictocode`) and **credits per
      call**; adjust `refresh_every_hours`.
- [ ] **CHD current**: find the "Estado Aforos" JSON URL on
      datos.chduero.es; set `river.current_url` and the field names
      (`station_field`, `level_field`, `flow_field`, `time_field`).
      Until then the river shows "No disponible".
- [ ] **CHD time zone**: confirm CHD timestamps are local time.
- [ ] **CHD yearbooks**: format, last available year, whether level is
      included, station code; prepare the CSV and run the import.

## Design choices to confirm

- [ ] Charts with vendored Chart.js **3.9.1** (copied from a local MIT
      distribution because the npm registry was not reachable). Verify the
      file against the official release (SHA-256
      `82548102b21d9dd6f0dccd758979d1c3d75c116a9a446d89719980efd9516608`)
      or replace it with the latest 4.x UMD build (`chart.umd.js`); the
      wrapper only uses APIs common to 3.x and 4.x.
- [ ] River "by year" view: previous and current year **overlaid** on one
      chart (alternative: two separate charts or a year selector).
- [ ] Tooltip size and position on a real phone.
- [ ] Collect, commit and deploy in a single hourly job.
- [ ] Summary forecasts come from Open-Meteo (AEMET only in comparison).
- [ ] Protection window = first to last hour with UV ≥ 3.
- [ ] Trend thresholds (3 h window, ±3 % flow, ±1 cm level).
- [ ] Level datum-shift threshold 0.15 m.
- [ ] Repository growth from hourly data commits is acceptable.
- [ ] Icons are placeholders (`web/icons/`).

## Verified so far

- `ruff format`, `ruff check`, `mypy --strict`: clean.
- `pytest`: all tests pass (parsers, UV, river history, yearbook stats,
  collection isolation, Meteoblue cadence, site build).
- Web views rendered with demo data in headless Chromium with an
  emulated touchscreen: tapping a chart shows the tooltip with every
  value at that point; no console errors. Also checked with every source
  failing. Not yet tested on a real phone or with real data.
- Workflows not yet executed on GitHub.
