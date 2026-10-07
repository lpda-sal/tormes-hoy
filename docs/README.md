It runs without servers:

```text
GitHub Actions (hourly, ~30 s)          GitHub Pages
python -m tormes_hoy.collect_data  ──► data/*.json ──► web/ (PWA) ──► phone / tablet
```

## Screens

| Route | Content |
|---|---|
| `#/` | Weather now (AEMET), rest of the day, UV now + protection window, river now, next days |
| `#/weather` | Compare AEMET / Open-Meteo / Meteoblue: 48 h temperature and rain, 7-day table |
| `#/uv` | Full-day UV chart with WHO risk bands and protection window |
| `#/river` | Flow or level; last month, or current and previous year on a 1 Jan – 31 Dec axis, with yearbook median and quartiles |

## Quick start

```bash
mamba env create -f environment.yaml
mamba activate tormes-hoy
pytest

# Collect current data (requires API keys)
export AEMET_API_KEY=...  METEOBLUE_API_KEY=...
tormes-hoy-collect-data                   # writes data/*.json
tormes-hoy-build-site
python -m http.server -d _site 8000      # http://localhost:8000
```

## Documentation

- [`design.md`](design.md) — architecture and decisions
- [`data-contract.md`](data-contract.md) — JSON files
- [`sources.md`](sources.md) — data sources and yearbook import
- [`operations.md`](operations.md) — GitHub setup and Actions budget
- [`review.md`](review.md) — **items to verify before going live**
- [`../AGENTS.md`](../AGENTS.md) — rules for AI coding agents

Charts use [Chart.js](https://www.chartjs.org) 3.9.1 (MIT), vendored in
`web/vendor/chartjs/`. Touch or drag a finger on a chart to see the values.