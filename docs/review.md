# Review checklist

This project was generated as a complete first version **without access to
the real APIs**. Parsers follow the public documentation and are tested
with synthetic fixtures (`tests/fixtures/README.md`). Verify each item,
replace fixtures with real responses and tick it.

## Data sources

- [x] **AEMET station**: Salamanca capital selected. Official hourly
      catalogue checked on 2026-10-08: nearest of the 15 listed stations in
      Salamanca province to the CSCK club (4.05 km; airport 11.76 km).
- [x] **AEMET municipality**: official forecast page confirms Salamanca
      capital; municipality identifier remains in configuration.
- [ ] **AEMET observation**: confirm `fint` is UTC and field names
      (`ta`, `hr`, `vv`, `vmax`, `dv`, `prec`, `pres`, `ubi`).
- [ ] **AEMET forecasts**: check hourly blocks (`temperatura`,
      `estadoCielo`, `precipitacion`, `probPrecipitacion` with 6-hour
      `periodo` like `"0814"`, `vientoAndRachaMax`) and daily fields
      (`temperatura.maxima/minima`, `probPrecipitacion` `"00-24"`, `uvMax`).
- [ ] **Open-Meteo**: check variables and that `uv_index` is present.
- [ ] **Meteoblue**: confirm package URL, field names (`data_1h`,
      `data_day`, `windspeed`, `uvindex`, `pictocode`) and **credits per
      call**; adjust `refresh_every_hours`.
- [ ] **CHD current**: confirm the SAIH EA087 page remains available at
      `https://www.saihduero.es/risr/EA087` and retains its `Nivel`, `Caudal`,
      and local date/time fields.
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
- [x] UV protection window uses linear threshold crossings, rounded outwards
      to minutes. Missing adjacent readings are not interpolated.
- [ ] Club river flow bands: provisional caution/danger thresholds are
      configurable; validate them for actual club use, not official alerts.
- [ ] Trend thresholds (3 h window, ±3 % flow, ±1 cm level).
- [ ] Level datum-shift threshold 0.15 m.
- [ ] Repository growth from hourly data commits is acceptable.
- [ ] Icons are placeholders (`web/icons/`).
- [x] Home solar ranges: civil dawn to sunrise and sunset to civil dusk,
      from Sunrise-Sunset.org. Header links to solar details with attribution
      and civil, nautical and astronomical twilight times.

## Verified so far

- Public CSCK club coordinates configured as the reference point for solar
      times and model forecasts. Tests verify the configured coordinates reach
      the output envelope and request URLs; changing the point refreshes weather
      caches on the next collection.

- `ruff format`, `ruff check`, `mypy --strict`: clean.
- `pytest`: all tests pass (parsers, UV, river history, yearbook stats,
  collection isolation, Meteoblue cadence, site build).
- Web views rendered with a representative dataset in headless Chromium with an
  emulated touchscreen: tapping a chart shows the tooltip with every
  value at that point; no console errors. Also checked with every source
  failing. Not yet tested on a real phone or with real data.
- Workflows not yet executed on GitHub.
- Compact home screen checked with available site data at 360 × 640,
  390 × 844 and 1280 × 800 CSS pixels: all cards and the daily forecast link
  fit without vertical scrolling; hourly overflow stays inside its card.
      Home links reach the intended detail views.
- Solar ranges checked against a live Sunrise-Sunset.org response at
      360 × 640 CSS pixels without vertical scrolling. Tests cover timezone
      conversion, daily cache reuse, invalid and missing events, and API failure.
- Four-row home layout checked at 360 × 640, 390 × 844 and 1280 × 800:
      all five cards and the daily forecast link fill the available page height
      without page scrolling. Hours, rain and UV use full-width rows; the home
      screen has no attribution or generated-data footer. Rain and UV canvases
      contain plotted pixels and tapping them shows values without navigation.
      Tests cover their series, rain's 0–100% scale and missing chart data.
- Home content checked over 24 hours with night shading and civil-twilight
      UV bounds and risk-colour backgrounds. Weather shows precipitation and
      reading age without a station name; river level stays in the detail view.
      Tests cover flow band boundaries, invalid thresholds, interpolation,
      UTC-device rendering and the next-day forecast cutoff.
- Home maximum gust uses AEMET's latest interval (m/s converted to km/h)
      or Open-Meteo current conditions (requested in km/h). Tests cover zero,
      missing values, unit conversion and model fallback without mixing sources.
      Compact home styling also checked at 260 × 562 CSS pixels with 150%
      browser zoom: the detail link no longer overlaps the UV section.
- Legacy river categories are completed during site assembly from configured
      thresholds without changing source files, readings or timestamps. Tests
      cover every band, invalid flow and preservation of published categories.
      Home tests cover coloured categories, UV order and line break, and the
      daily forecast and CSCK links with a placeholder and return navigation.
- Home rainfall and river reading age have separate lines. River highlighting
      uses the UV palette on the value and units; its category is plain muted
      text on the following line. The flow label is omitted on home.
      Home rain compares all three source colours without a legend; tests cover
      alignment, missing values, a missing main model and the 24-hour window.
- UV summary and chart have equal heights with a top-left title and separate
      current, maximum and protection blocks. Layout verified from the compact
      260 × 562 viewport through desktop, without page overflow or overlap.
      Title and current reading are grouped with the same heading spacing as
      current weather. River and UV category typography matches in computed
      font family, size, weight and line height at every checked viewport.
- Current weather facts are ordered humidity, rain, wind and gust in four
      equally spaced rows. Tests verify order and row count. Browser checks
      confirm uniform spacing and short fixed UV gaps without page overflow.
- Pixel 8 portrait (412 × 915 CSS pixels) is the fixed preview reference.
      River trend and UV blocks have 12px gaps; river reading age is
      right-aligned. Verified without resizing the user's preview or overflow.
- Secondary text increased to 14px, solar times to 12.8px and compact chart
      ticks to 11px. Pixel 8 checks confirm titles and large values are unchanged,
      and no text clipping or page overflow occurs. Chart tick sizes are tested.
- Current weather reading age is right-aligned. The river category has a
      4px gap below its chip, smaller than the UV category's measured 7.9px
      gap. Verified at the fixed Pixel 8 viewport without page overflow.
- The first home row fits its content; upcoming hours receive the released
      height with vertically centred cells and horizontal scrolling intact.
      At Pixel 8, top cards changed from 207px to 185px and upcoming hours
      from 139px to 165px. Charts remain about 206px with no page overflow.
- The current UV reference hour appears above its category beside the chip.
      Home and detail now choose the higher UV from the two hourly samples
      nearest the browser clock, independent of the generation timestamp.
      Regression tests cover both screens and the chart point, earlier/later
      selections, exact hours, ties, Madrid timezone, midnight, zero UV,
      invalid samples and missing data. Equal distances favour the later hour.
- Solar detail shows a Spanish date with an initial capital, no location label,
      reversed event order and plain-text source attribution. Tests cover the
      date, omitted location, row order and removed explanatory note.
- Weather detail uses temperature and rain probability charts, with
      the latest temperature observation plotted as a point.
      A "Fuentes:" list below puts observation first with reading age, then
      the three forecasts with update ages in parentheses. The spread note is above.
      Tests cover percentage scales, axis units, observation timestamps,
      missing/error sources, stale readings, chart order and no duplicate legends.
      Humidity parsers cover optional source columns and missing values.
- Weather forecasts cover the next 24 hours plus the observation timestamp.
      Tests at 23:30 and 00:30 confirm the previous reading stays at the left
      with its original date. No rainfall amount is reinterpreted as probability.
      Axis labels show only hours; tooltip dates distinguish midnight transitions.
- Both weather-detail charts shade civil-twilight night intervals using the
      shared home-screen calculation; tests verify the dusk-to-dawn band.
- Home hourly cards and rain comparison cover the next 24 hours. Tests check
      midday and pre-dawn windows, exclude the end-hour sample, and repeat
      today's civil-twilight times for night shading without another solar call.
- UV detail matches the home current reading and civil-twilight bounds, uses
      an orange line without a series legend or protection-window shading,
      and frames only the chart. Tests cover the reference hour, timezone,
      note/hint/source placement and unavailable solar or hourly data.
- Upcoming-days comparison omits the update-age legend, table subtitle and
      bottom weather link. Known daily WMO codes reuse the home icons with
      accessible descriptions; missing or unsupported codes omit the icon.
- River detail uses the title "Río Tormes" and home-style current readings.
      Flow shares the matching summary category; level has no background. Tests
      cover colour bands, unmatched/missing categories, unavailable readings
      and the level chart selector.
- River month comparison aligns daily observed means for the current and
      previous year, orange and blue respectively, matching annual colours.
      Tests cover both variables, missing years, gaps and leap-day alignment.
      Reading age is omitted; the hint precedes the chart card and yearbook
      notices, CHD attribution and danger disclaimer follow it. Observed
      history notices and the data-origin paragraph are omitted.
- Home UV bounds follow the payload date rather than the browser's current
      day. A midnight regression keeps the orange forecast curve visible
      until new UV data arrives, without moving yesterday's values to today.
- Yearbook import accepts the original CEDEX daily TXT, including missing
      sentinels and UTF-8/Latin-1 encoding, while preserving CSV support.
      Tests reject malformed rows, mixed stations and duplicate dates.
      Min/max use the same configured window as P25/P50/P75; the
      CLI prints the absolute path of its generated statistics JSON.
- River charts layer the historical min/max envelope beneath the quartile
      band and every line. Tests cover both ranges, per-band tooltips,
      variable-specific periods, missing extrema and removed history text.
- Yearbook statistics use a zero-day window, comparing only the same
      calendar date across years. Regression tests exclude neighbouring
      samples and verify insufficient leap-day data remains unavailable.
- Home footer omits the CSCK link while keeping the daily forecast link
      and the existing placeholder route. Rendering tests verify its absence.
