# AGENTS.md

> Instructions for AI coding agents working in this repository.
> This is a "README for machines" — humans read `README.md`, agents read this.
> Keep it under ~150 lines. Commands over prose. Examples over explanations.

## Project

Tormes Hoy: serverless PWA with weather, UV and river Tormes data for
Salamanca. A Python collector (GitHub Actions, hourly) writes `data/*.json`;
a static web app (GitHub Pages) reads them. Design: `docs/design.md`.

## Tooling

- Python 3.12+, Mamba, pytest, Ruff, mypy (strict).
- `pyproject.toml` is the single source of truth for project configuration.
- Web: vanilla HTML/CSS/JS (ES modules), vendored Chart.js. No framework,
  no build step, no npm.

## Setup

```bash
mamba env create -f environment.yaml   # creates env "tormes-hoy" (-e .[dev])
mamba activate tormes-hoy
mamba env update -f environment.yaml --prune   # after editing the file
```

Always work inside the project environment. Never install packages globally.

## Commands

```bash
ruff format .            # format
ruff check --fix .       # lint
mypy .                   # type-check
pytest                   # full test suite
pytest -k "name" -v      # tests matching a pattern
tormes-hoy-collect-data  # collect (needs AEMET_API_KEY, METEOBLUE_API_KEY)
tormes-hoy-build-yearbook daily.csv                # yearbook statistics
tormes-hoy-build-site && python -m http.server -d _site 8000
```

## Project Structure

```text
tormes-hoy/
├── tormes_hoy/          # package and four CLI modules
│   ├── config/          # config.toml
│   ├── utils/           # shared config, models, and time helpers
│   ├── source_data/     # collector, outputs, observed river, UV, sources
│   ├── site/            # static site assembly
│   └── yearbook/        # validated yearbook statistics
├── web/                 # static PWA (views/, i18n/es.json, sw.js)
├── data/                # generated JSON, committed by the workflow
├── tests/               # pytest suite + fixtures/
├── docs/                # design, data contract, sources, operations, review
├── .github/workflows/   # update-data.yml (hourly), ci.yml
├── environment.yaml
└── pyproject.toml
```

Do not move files or reorganize directories unless explicitly requested.

## Project Rules

- Code, identifiers, file names, routes, comments and docs: **English**.
- UI text: **Spanish**, only in `web/i18n/es.json` (use `t("key")`).
- Location, app name and station IDs live only in
  `tormes_hoy/config/config.toml`.
  Never hardcode them elsewhere; the collector copies them into every JSON and
  the web reads them from there.
- Sources are isolated: a failure sets that source's `status` to `error` (or
  `stale` reusing previous data) and never breaks the others.
- Never mix CHD yearbook data (validated) with observed readings (provisional),
  neither in storage nor in computations. Charts may show both, clearly
  labeled.
- Every data file follows `docs/data-contract.md`; bump `SCHEMA_VERSION`
  in `tormes_hoy/utils/models.py` on breaking changes and update the web.
- Insert external text in HTML only through `esc()` (`web/format.js`).
- Bump `CACHE_VERSION` in `web/sw.js` when shell files change.

## GitHub Actions Budget

The hourly job must stay short (target < 30 s):

- Runtime code uses the standard library only (`dependencies = []`).
- No `setup-python`, no `pip install` in `update-data.yml`.
- Meteoblue is queried every `refresh_every_hours` (credit budget).
- Heavy or occasional work (yearbook statistics) runs locally, never in CI.

## Code Style

- Type hints on all public functions, methods, and attributes.
- `pathlib.Path`, not `os.path`. f-strings, not `%` or `.format()`.
- Raise specific exceptions; never a bare `except:`. The only broad
  `except Exception` is the source-isolation boundary in
  `source_data/collector.py`.
- Pure, small functions; parsing separated from I/O (`parse_*` vs `fetch`).
- Public APIs require Google-style docstrings.
- Prefer ≤79 columns; do not reformat lines only for that.

```python
# Good
def parse_current(payload: Any, river: RiverConfig, tz_name: str) -> JsonDict:
    """Extract the configured station's latest reading."""


# Bad — I/O mixed with parsing, no types
def get(url):
    return json.loads(urlopen(url).read())["x"]
```

## Dependencies

- Prefer the standard library. Runtime dependencies are forbidden without
  approval (they slow down the hourly job). Dev dependencies need approval.
- Web: the only third-party JS is Chart.js, vendored in `web/vendor/` and used
  only through `web/charts.js`. No CDN, no npm.

## Configuration

- Stable settings: `tormes_hoy/config/config.toml` (version-controlled).
- Secrets: environment variables / GitHub Secrets only. Document new ones
  in `.env.example`. Never log or print them
  (see `source_data.network_client._redact`).

## Ignore Files

Keep `.gitignore` minimal: generated, tooling-produced or temporary files.

## Testing

- Tests in `tests/`, files `test_*.py`. Fixtures in `tests/fixtures/`.
- Never call real APIs in tests; inject fakes (`collect.Fetchers`, `get=`).
- New features require tests; bug fixes require regression tests.

## Git & Pull Requests

- Branch from `main`. Conventional Commits (`feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `chore:`). Small, focused PRs. CI must pass.
- Never commit to `data/` by hand; the workflow owns it.

## Agent Workflow

1. Read the relevant code and `docs/` first.
2. Make the smallest reasonable change following existing patterns.
3. Run format, lint, type check and tests.
4. Update docs when behavior or the data contract changes.
5. Check `docs/review.md`; update it when you resolve or add an item.

## Boundaries

### ✅ Always
- Run `ruff`, `mypy`, and `pytest` before declaring a task complete.
- Preview UI changes using available site data before finishing.

### ⚠️ Ask First
- Adding any dependency (Python or JS).
- Changing the data contract, `config.toml` layout or routes.
- Changing workflow schedules or anything that increases Actions time.

### 🚫 Never
- Commit no secrets, tokens, or private addresses.
- Edit `.github/workflows/` without explicit approval.
- Delete or weaken tests to make the build pass.
- Mix yearbook and observed river data.

## Definition of Done

1. `ruff format .` and `ruff check .` pass.
2. `mypy .` reports no errors.
3. `pytest` is green; new behavior is tested.
4. Docs (and `docs/review.md`) updated when behavior changes.
