from datetime import UTC, datetime
import os
from pathlib import Path

import pytest

from moon_data.cli import (
    build_fetch_parser,
    build_report_parser,
    main,
    parse_observation_time,
    run_fetch_ephemeris,
    validate_coordinates,
    validate_timezone,
)
from moon_data.location import ObserverLocation
from moon_data.moon import MoonDataError, generate_report


def test_parse_observation_time_with_offset() -> None:
    parsed = parse_observation_time("2026-04-21T12:30:00-06:00")
    assert parsed == datetime(2026, 4, 21, 18, 30, tzinfo=UTC)


def test_parse_observation_time_assumes_utc_for_naive_values() -> None:
    parsed = parse_observation_time("2026-04-21T12:30:00")
    assert parsed == datetime(2026, 4, 21, 12, 30, tzinfo=UTC)


def test_parse_observation_time_rejects_invalid_values() -> None:
    with pytest.raises(MoonDataError):
        parse_observation_time("not-a-time")


def test_validate_coordinates_rejects_out_of_range_values() -> None:
    with pytest.raises(MoonDataError):
        validate_coordinates(91.0, 0.0)

    with pytest.raises(MoonDataError):
        validate_coordinates(0.0, 181.0)


def test_validate_timezone_rejects_unknown_zone() -> None:
    with pytest.raises(MoonDataError):
        validate_timezone("Mars/Olympus_Mons")


def test_main_reports_validation_errors(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--lat", "95", "--lon", "0"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Invalid latitude" in captured.err


def test_generate_report_no_download_requires_cached_ephemeris(tmp_path: Path) -> None:
    with pytest.raises(MoonDataError):
        generate_report(
            location=ObserverLocation(latitude=0.0, longitude=0.0),
            cache_dir=tmp_path,
            no_download=True,
        )


def test_build_report_parser_supports_compact_flag() -> None:
    args = build_report_parser().parse_args(["--lat", "0", "--lon", "0", "--compact"])
    assert args.compact is True


def test_build_report_parser_supports_full_moon_guide_flag() -> None:
    args = build_report_parser().parse_args(["--lat", "0", "--lon", "0", "--full-moon-guide"])
    assert args.full_moon_guide is True


def test_build_fetch_parser_accepts_cache_dir(tmp_path: Path) -> None:
    args = build_fetch_parser().parse_args(["--cache-dir", str(tmp_path)])
    assert args.cache_dir == tmp_path


def test_run_fetch_ephemeris_reports_cached_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "de421.bsp"

    def fake_fetch(cache_dir: Path | None = None) -> Path:
        assert cache_dir == tmp_path
        return target

    monkeypatch.setattr("moon_data.cli.fetch_ephemeris", fake_fetch)
    exit_code = run_fetch_ephemeris(["--cache-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert str(target) in captured.out


def test_main_dispatches_fetch_ephemeris(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("moon_data.cli.fetch_ephemeris", lambda cache_dir=None: Path("/tmp/moon-data/de421.bsp"))
    exit_code = main(["fetch-ephemeris"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Ephemeris cached at" in captured.out
