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
| River stats | Yearbook day-of-year min/P25/P50/P75/max, last 10 available years, 0-day window | Validated data, same calendar date only |
| No mixing | Yearbook and observed stored and computed separately | Validated vs provisional |
| Level shifts | Yearly median jump > 0.15 m → use only years after the jump | Datum changes |
| Web | Vanilla JS, hash routes, no build | No toolchain to maintain |
| Charts | Chart.js 3.9.1 vendored, wrapped by `web/charts.js` | Touch tooltips with all values at a point; one wrapper isolates the library |
| River years | Previous year and current year to date on one 1 Jan – 31 Dec axis | Compare years and the yearbook band directly |
| PWA | Shell cache-first, data network-first | Fast start, offline last data |
| Languages | Code/docs English, UI Spanish (`es.json`) | Project rule |

## Weather detail

The weather detail title is "Tiempo". It has two charts in order:
temperature (degrees Celsius) and rain probability (%).
Rain covers 0–100%; both vertical axes display their units.
The time window covers the next 24 hours and the latest observation, with
only hours on the horizontal axis and dates retained in tooltips.
Both charts shade civil-twilight nights using the same intervals as the home
rain chart.
Forecasts remain lines; the latest temperature observation is a point
with a tooltip at its exact timestamp. Observed
rainfall in mm is not plotted as probability. Error observations and
missing values are not plotted. Stale readings retain their timestamp.
One shared legend below the charts identifies forecast colours and the
observation marker. Under "Fuentes:", a vertical list puts observation first
with reading age, followed by AEMET, Open-Meteo and Meteoblue with update ages
in parentheses. Individual
chart legends and the observation card are omitted. The forecast-divergence
note appears above the charts; the daily-forecast link is omitted. Axes use
the configured timezone regardless of the browser timezone.

Weather temperature and rain chart canvases use a compact 10rem height so
the hourly comparison fits in the Pixel 8 first viewport. Other detail
charts retain their default 15rem height.

Between the charts and source list, a compact framed comparison shows only
weather-condition icons for AEMET, Open-Meteo and Meteoblue. The box has no
visible heading; its scrolling region retains an accessible name. Twenty-four
columns start at the current configured local hour, independent of the
observation timestamp and available forecast rows. Source labels remain
visible during horizontal scrolling. Native hourly sky/WMO/pictocode fields
map to the shared icon set with accessible descriptions; Meteoblue's hourly
`pictocode` uses its own 1-35 hourly set (36/37 unused), which differs from
the daily 1-17/20-25 set, so each is read with its own table.
Missing hours, unknown conditions and error sources leave empty cells.
No temperatures, humidity or precipitation probabilities appear in this box.
Hour tooltips include the date to distinguish midnight transitions.
The horizontal scrollbar has bottom clearance below the final icon row;
the box does not scroll vertically.

The home "Próximas horas" card and this box show night icons for every source:
an hour whose midpoint is before sunrise or from sunset onward uses the
configured location's sunrise and sunset clock (Sunrise-Sunset.org, applied to
every date like the night shading). Clear and mostly clear skies become a
moon, partly cloudy becomes a cloud and drizzle with sun becomes rain; other
conditions are unchanged. Without solar times, day icons are kept. The home
card waits for the solar request so icons do not change after first paint.

The upcoming-days view contains only its title, back link and comparison
table. Source names remain in the column headers, without an update-age
legend, table subtitle or bottom weather link. All three sources reuse the
home-screen weather symbols with source-specific accessible descriptions and
tooltips: AEMET uses its daily `sky` text, Open-Meteo its WMO code, and
Meteoblue its native daily `pictocode`. Meteoblue codes are not WMO codes;
their official daily meanings determine only the shared visual category.
Missing or unsupported conditions omit the icon. Hourly conditions and rain
probabilities are never substituted for a missing daily condition.
Dates before the current calendar day in the configured timezone are removed
from all sources before sorting and limiting the comparison to seven dates.
Cached forecasts cannot bring yesterday back after local midnight.

## River detail

The river detail title is "Río Tormes", without the station identifier.
Current flow and level appear above the chart, using the home reading's
typography and value/unit chips. Flow repeats the home colour and category
only when the summary's classification matches the raw reading's timestamp
and flow; missing or mismatched categories remain unclassified. Level retains
the same typography without a background. Reading age is omitted.
The interaction hint precedes the chart card. Yearbook availability and
level-reference notices follow it, outside the card, followed by the CHD
attribution and provisional danger-level disclaimer. Observed-history notices
and the data-origin paragraph are omitted.
Both chart ranges use blue for the previous year and orange for the current
year. The default "Últimos meses" range compares daily observed means from
the same date two calendar months ago through today with the same calendar
dates one year earlier, aligned on one axis. If the starting month lacks
that day, its final day is used. "Últimos años" retains the current and
previous calendar-year comparison.
Annual flow uses a fixed vertical range of 0–250 m³/s; monthly flow keeps
automatic bounds. Level-axis labels use two decimal places in both ranges.
In both ranges, current-year flow and level lines include daily means only
through yesterday; today's partial mean and future dates are omitted. The
latest instantaneous reading remains a separate dot, using its actual
timestamp in the monthly view rather than the daily mean's noon position.
Missing values remain gaps; absent years never acquire invented data.
February 29 has no previous-year value when that date did not exist.
Provisional observations and validated yearbook statistics remain separate.
Both ranges show a lightly shaded historical minimum-to-maximum region behind
the darker P25-P75 region, median and observed series. Region labels use the
selected variable's actual yearbook period, and tooltips report each region's
own endpoints. Older yearbooks without extrema retain only the quartile band.

## Home screen

The home grid has four rows: current weather and river; full-width upcoming
weather hours; full-width rain probability; and a full-width UV card with its
existing summary on the left and the daily UV chart on the right. The layout
distributes available viewport height across the rows, keeping all cards and
the daily forecast link visible on the checked phone and desktop sizes.
Upcoming hours keep
their fixed width and scroll horizontally inside the card without adding
rows. Hours cover a 24-hour window starting at the current local hour,
excluding the following day's same-hour endpoint. Rain uses the same window
with a fixed 0–100% scale. Night shading repeats today's local civil-dusk
and civil-dawn times on each visible date, without requesting tomorrow's solar
data; daylight after the repeated dawn remains unshaded.
UV uses `uv.json` with the visible axis limited to civil dawn through civil
dusk for the UV payload's date and the same risk-colour bands as the detail
chart. After midnight, an older payload retains its own day's bounds so the
orange curve is not clipped away by today's axis. The solar header still
shows today. Missing solar times
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
civil, nautical and astronomical twilight when provided by the API. The detail
shows the date in Spanish with an initial capital, without a separate location
label; configured coordinates and timezone still determine the solar data.
Rows run from sunrise/sunset through civil, nautical and astronomical twilight;
the solar row is labelled Orto/Ocaso. Its footer shows the plain-text source
label "Fuente: Sunrise-Sunset".
There is no generated-data footer.

The bottom navigation shows only the daily forecast link on the left.
The existing `#/csck` route remains a placeholder with
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
Home and detail select the higher UV value among the two valid hourly
samples nearest the browser's current time, and display that sample's time
in the configured timezone. Equal UV values favour the nearer sample;
equal distances favour the later timestamp. A single valid sample is used
on its own; no valid samples leave the reading unavailable and omit its time.
Both UV charts show a dashed vertical line at the browser's current time
and a risk-coloured dot at the selected sample's time and value.
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

The home rain chart compares AEMET, Open-Meteo and Meteoblue over 24 hours
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
The UV detail view uses the same hourly selection and typography as home,
and highlights the selected sample's value and time on its chart.
Only its chart is framed; the estimation note and interaction hint precede it,
and the risk legend and Open-Meteo attribution follow it. Its orange line spans
civil dawn through civil dusk, with WHO risk bands but no protection-window
shading, threshold caption or series legend. Missing solar boundaries leave
the chart unavailable without hiding the current reading.

## Failure behaviour

Each source returns `ok`, `stale` or `error`. On failure the previous
payload is reused as `stale` (with the error message), so the dashboard
shows the last known values with a badge. A failing source never fails the
job: the workflow always deploys.

## Charts

`web/charts.js` is the only module that uses Chart.js. Views pass a spec
(shared `x` array, series, optional layered bands, zones, "now" marker,
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
