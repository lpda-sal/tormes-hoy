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

## Home screen

The home grid has four rows: current weather and river; full-width upcoming
weather hours; full-width rain probability; and a full-width UV card with its
existing summary on the left and the daily UV chart on the right. The layout
distributes available viewport height across the rows, keeping all cards and
the daily forecast link visible on the checked phone and desktop sizes.
Upcoming hours keep
their fixed width and scroll horizontally inside the card without adding
rows. Hours include the next 04:00 in the configured timezone (the current
date before 04:00, otherwise the following date). Rain uses the same hours
with a fixed 0–100% scale and night shading outside the civil twilight window.
UV uses `uv.json` with the visible axis limited to civil dawn through civil
dusk and the same risk-colour bands as the detail chart. Missing solar times
leave UV's small chart unavailable rather than inventing daylight boundaries.
Both mini charts reuse the Chart.js wrapper
and can be inspected without following a link. Their headings or summaries
link to the detail views. The daily forecast is a separate text link.
Two compact solar ranges in the header, to the right of the title, show civil
dawn to sunrise and sunset to civil dusk, fetched from Sunrise-Sunset.org
by location and local date. Times use the configured location's timezone.
The browser caches successful results for that location and date; failed
requests show an unavailable state without replacing the other cards.
The header ranges link to `#/sun`, a detail view listing sunrise, sunset and
civil, nautical and astronomical twilight when provided by the API. Actual
usable light depends on weather and terrain as well as the astronomical times.
Source attribution appears on that detail view rather than the home screen.
There is no generated-data footer.

The bottom navigation places the daily forecast link on the left and CSCK
on the right. The explicitly requested `#/csck` route is a placeholder with
a development status and a return link. Current weather labels gusts as
"Racha". Weather and river share an equal-height grid row sized to its
content rather than expanded into unused space. The upcoming-hours row
absorbs the released height, with vertically centred hourly cells and
horizontal scrolling. Rain and UV charts keep nearly the same height.
The home river
card omits the flow label and highlights the value and units together using
the UV palette's green/yellow/red; its category is plain muted text on the
following line. Rainfall in current weather and the river reading age each
have their own line. UV's summary stretches to the chart's height. Its title
starts at the top left and groups with the current reading using the same
heading spacing as current weather.
The current UV chip has its reference hour above the category on its right.
This is the generation timestamp's hour in the configured timezone, with
minutes set to zero to match the collector's hourly UV selection, not the
browser's current time. Missing values or invalid timestamps omit the label.
Maximum and protection remain separate
blocks with a fixed 0.75rem gap rather than stretched spacing; protection's
time range remains on its own line. Current weather facts use equal-spaced
rows ordered humidity, rain, wind and gust. River and UV
categories share the same font size, weight and line height.
The river category has a 0.25rem gap below the highlighted flow.
River trend starts after a 0.75rem gap. Current weather and river reading
ages are right-aligned on separate lines.
Home secondary text and categories use 14px at the Pixel 8 reference size;
solar times use 12.8px and compact chart ticks 11px. Headings and large
numeric values retain their existing sizes.

The home rain chart compares AEMET, Open-Meteo and Meteoblue through 04:00
using the shared forecast-source colours from the weather detail view. It has
no legend, retains night shading and shows all available values in tooltips.
Missing values are gaps, not zero; unavailable sources do not hide the others.

Current weather includes rain in mm for the observation/model interval,
alongside humidity and wind. The observation station name is omitted on the
home screen; measured readings use the same age caption as the river, while
model fallback is labelled as an estimate. River level remains in the detail
view only. The home flow value uses green/yellow/red bands with provisional
club thresholds in configuration; these are not official safety alerts.
UV protection starts and ends at linearly interpolated threshold crossings,
rounded outwards to the minute. UV lines are straight to match that calculation.

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
