import json
from datetime import date, timedelta
from pathlib import Path

from tormes_hoy.utils.config import Config
from tormes_hoy.yearbook import builder as yearbook

EXPECTED_DAYS_IN_LEAP_YEAR = 366


def _write_csv(path: Path, years: range, level_jump_year: int | None) -> None:
    lines = ["date,flow_m3s,level_m"]
    for year in years:
        day = date(year, 1, 1)
        while day.year == year:
            flow = 10 + (day.timetuple().tm_yday % 30)
            level = 1.0 + (
                0.5 if level_jump_year and year >= level_jump_year else 0
            )
            lines.append(f"{day},{flow},{level}")
            day += timedelta(days=1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_stats_use_last_ten_complete_years(
    tmp_path: Path, config: Config
) -> None:
    csv_path = tmp_path / "daily.csv"
    _write_csv(csv_path, range(2010, 2025), None)
    payload = yearbook._build(yearbook._load_csv(csv_path), config)
    flow = payload["variables"]["flow_m3s"]
    assert flow["years"] == list(range(2015, 2025))
    assert flow["period"] == "2015-2024"
    assert len(flow["stats"]) == EXPECTED_DAYS_IN_LEAP_YEAR
    first = flow["stats"][0]
    assert first["p25"] <= first["p50"] <= first["p75"]
    assert payload["source"]["kind"] == "validated"


def test_level_shift_restricts_period(tmp_path: Path, config: Config) -> None:
    csv_path = tmp_path / "daily.csv"
    _write_csv(csv_path, range(2015, 2025), level_jump_year=2020)
    payload = yearbook._build(yearbook._load_csv(csv_path), config)
    level = payload["variables"]["level_m"]
    assert level["detected_shifts"] == [2020]
    assert level["years"] == list(range(2020, 2025))
    assert payload["variables"]["flow_m3s"]["years"] == list(range(2015, 2025))


def test_incomplete_years_are_ignored(tmp_path: Path) -> None:
    series = {
        date(2024, 1, d): {"flow_m3s": 1.0, "level_m": None}
        for d in range(1, 30)
    }
    assert yearbook._complete_years(series, "flow_m3s") == []


def test_cli_writes_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "daily.csv"
    _write_csv(csv_path, range(2023, 2025), None)
    out = tmp_path / "out"
    assert yearbook.main([str(csv_path), "--out-dir", str(out)]) == 0
    content = json.loads((out / yearbook._OUTPUT_NAME).read_text())
    assert content["schema_version"] == 1
    assert content["location"]["id"] == "salamanca"
