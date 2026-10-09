import json
from datetime import date, timedelta
from pathlib import Path

import pytest

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
    assert (
        first["min"]
        <= first["p25"]
        <= first["p50"]
        <= first["p75"]
        <= first["max"]
    )
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


def test_cedex_txt_handles_dates_columns_and_missing_values(
    tmp_path: Path,
) -> None:
    text = """---Alturas y caudales medios diarios---
NOTA: El valor -100.00 indica que no existe dato.
 Estac.      Fecha Altura(m)Caudal(m3/s)
----------------------------------------
   2087 01/10/2010     0.370    10.800
   2087 02/10/2010   -100.00     0.000
   2087 03/10/2010     0.000   -100.00
"""
    path = tmp_path / "download.txt"
    path.write_text(text, encoding="utf-8-sig")
    series = yearbook._load_daily(path)
    assert series[date(2010, 10, 1)] == {"level_m": 0.37, "flow_m3s": 10.8}
    assert series[date(2010, 10, 2)] == {"level_m": None, "flow_m3s": 0.0}
    assert series[date(2010, 10, 3)] == {"level_m": 0.0, "flow_m3s": None}


@pytest.mark.parametrize(
    "rows, message",
    [
        ("2087 01/10/2010 0.370", "Invalid CEDEX daily row"),
        ("2087 31/02/2010 0.370 10.800", "day is out of range"),
        ("2087 01/10/2010 nan 10.800", "must be finite"),
        (
            "2087 01/10/2010 0.370 10.800\n2088 02/10/2010 0.370 10.800",
            "only one station",
        ),
        (
            "2087 01/10/2010 0.370 10.800\n2087 01/10/2010 0.370 10.800",
            "Duplicate yearbook date",
        ),
        ("", "No daily readings"),
    ],
)
def test_cedex_rejects_invalid_rows(rows: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        yearbook._parse_cedex("Alturas y caudales medios diarios\n" + rows)


def test_cedex_rejects_other_exports() -> None:
    with pytest.raises(ValueError, match="Expected a CEDEX daily"):
        yearbook._parse_cedex("Datos mensuales\n2087 01/10/2010 1 2")


def test_cedex_cli_and_latin1_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "download.txt"
    rows = ["Alturas y caudales medios diarios", "Estación: Salamanca"]
    for year in (2020, 2021):
        day = date(year, 1, 1)
        while day.year == year:
            rows.append(f"2087 {day:%d/%m/%Y} 0.370 10.800")
            day += timedelta(days=1)
    path.write_text("\n".join(rows), encoding="latin-1")
    out = tmp_path / "output"
    assert yearbook.main([str(path), "--out-dir", str(out)]) == 0
    target = out / yearbook._OUTPUT_NAME
    assert str(target.resolve()) in capsys.readouterr().out
    content = json.loads(target.read_text())
    for variable, expected in [("flow_m3s", 10.8), ("level_m", 0.37)]:
        block = content["variables"][variable]
        assert block["years"] == [2020, 2021]
        assert len(block["stats"]) == EXPECTED_DAYS_IN_LEAP_YEAR
        for row in block["stats"]:
            if row["md"] == "02-29":
                assert row == {"md": "02-29", "n": 1}
                continue
            assert row["n"] == len(block["years"])
            assert all(
                row[key] == expected
                for key in ("min", "p25", "p50", "p75", "max")
            )


def test_extrema_and_quartiles_share_the_same_window() -> None:
    series: dict[date, dict[str, float | None]] = {
        date(2020, 1, 1): {"flow_m3s": 0.0},
        date(2021, 1, 1): {"flow_m3s": 4.0},
        date(2021, 1, 2): {"flow_m3s": 8.0},
        date(2021, 1, 3): {"flow_m3s": 100.0},
    }
    stats = yearbook._day_of_year_stats(
        series, "flow_m3s", [2020, 2021], window=1
    )
    assert stats[0] == {
        "md": "01-01",
        "min": 0.0,
        "p25": 2.0,
        "p50": 4.0,
        "p75": 6.0,
        "max": 8.0,
        "n": 3,
    }


def test_zero_window_excludes_neighbouring_days() -> None:
    series: dict[date, dict[str, float | None]] = {
        date(2020, 1, 1): {"flow_m3s": 0.0},
        date(2021, 1, 1): {"flow_m3s": 4.0},
        date(2021, 1, 2): {"flow_m3s": 100.0},
        date(2020, 2, 29): {"flow_m3s": 8.0},
    }
    stats = yearbook._day_of_year_stats(
        series, "flow_m3s", [2020, 2021], window=0
    )
    assert stats[0] == {
        "md": "01-01",
        "min": 0.0,
        "p25": 1.0,
        "p50": 2.0,
        "p75": 3.0,
        "max": 4.0,
        "n": 2,
    }
    assert next(row for row in stats if row["md"] == "02-29") == {
        "md": "02-29",
        "n": 1,
    }
