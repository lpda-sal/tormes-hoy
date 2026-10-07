# Design

## Goals

- Glanceable summary on a phone/tablet; detail views on tap.
- Free, no ads, no servers to maintain, minimal GitHub Actions time.
- Location-independent code: everything location-specific is in
  `tormes_hoy/config/config.toml`.

## Architecture

```text
┌──────────── GitHub Actions: update-data.yml (cron 17 * * * *) ────────────┐
│ python3 -m tormes_hoy.collect_data                                          │
│   sources/openmeteo  sources/aemet  sources/meteoblue(6 h)  sources/chd    │
│        └── source_data/collector.py (isolation, stale reuse) ──────────┘   │
│   writes data/*.json ─► git commit ─► tormes_hoy.build_site ─► deploy Pages│
└────────────────────────────────────────────────────────────────────────────┘
Locally, once a year: tormes-hoy-build-yearbook daily.csv
                      ─► data/river-yearbook-stats.json (commit by hand)
```

## Decisions

| Topic | Decision | Reason |
|---|---|---|
| Hosting | GitHub Pages + Actions, public repo | Free, HTTPS (needed by PWA) |
| Cadence | Hourly at minute 17, 24 h | Minute 0 is congested on GitHub |
| Collector deps | Standard library only | No install step in the hourly job |
| Single job | collect + commit + deploy in one job | One runner start per hour |
| Data history | Committed JSON in `data/` | History for free, keeps cron alive |
| Weather now | AEMET station observation | Measured, not modelled. Fallback: Open-Meteo current |
| Forecasts | AEMET, Open-Meteo, Meteoblue | Compare sources; spread = uncertainty |
| Summary forecasts | Open-Meteo | One consistent model with WMO codes and UV |
| Meteoblue | Every 6 h | Free trial is credit-limited |
| UV | Open-Meteo hourly UV, threshold 3 | WHO: protection from "moderate" |
| River now | CHD open data, station EA087 | Official source |
| River stats | Yearbook day-of-year P25/P50/P75, last 10 available years, ±7 days | Validated data, smooth band |
| No mixing | Yearbook and observed stored and computed separately | Validated vs provisional |
| Level shifts | Yearly median jump > 0.15 m → use only years after the jump | Datum changes |
| Web | Vanilla JS, hash routes, no build | No toolchain to maintain |
| Charts | Chart.js 3.9.1 vendored, wrapped by `web/charts.js` | Touch tooltips with all values at a point; one wrapper isolates the library |
| River years | Previous year and current year to date on one 1 Jan – 31 Dec axis | Compare years and the yearbook band directly |
| PWA | Shell cache-first, data network-first | Fast start, offline last data |
| Languages | Code/docs English, UI Spanish (`es.json`) | Project rule |

## Failure behaviour

Each source returns `ok`, `stale` or `error`. On failure the previous
payload is reused as `stale` (with the error message), so the dashboard
shows the last known values with a badge. A failing source never fails the
job: the workflow always deploys.

## Charts

`web/charts.js` is the only module that uses Chart.js. Views pass a spec
(shared `x` array, series, optional percentile band, zones, "now" marker,
highlighted dots, formatters); the wrapper builds the chart. Every series
of a chart shares the same `x` values, so a touch shows all values at that
point in one tooltip (`interaction.mode = "index"`), with a crosshair.

The river year chart uses a day-of-year axis of a leap year (366 slots:
1 Jan = 0, 29 Feb = 59, 31 Dec = 365). Each year is placed on it by month
and day; the 29 Feb gap of non-leap years is bridged (`spanGaps: 2`).
Yearbook statistics are keyed by `MM-DD`, so they fit the same axis.

## Changes versus the initial plan

- uPlot → Chart.js: uPlot's cursor is designed for mouse; Chart.js shows
  tooltips on touch out of the box. *(review)*
- The site is built in the same hourly job instead of a separate Pages
  workflow, to halve runner starts. *(review)*
- "Last year" (rolling 365 days) → previous calendar year and current year
  to date, both on a 1 Jan – 31 Dec axis. *(review)*
