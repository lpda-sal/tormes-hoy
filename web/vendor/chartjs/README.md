# Chart.js (vendored)

- Version: 3.9.1, UMD minified build (`chart.min.js`), sets `window.Chart`.
- License: MIT — (c) 2022 Chart.js Contributors, https://www.chartjs.org
- SHA-256: see `docs/review.md` (verify against the official release).

Vendored on purpose: no CDN, no npm, no build step. Only `web/charts.js`
uses it. To upgrade, replace the file, bump `CACHE_VERSION` in `web/sw.js`
and check every view.
