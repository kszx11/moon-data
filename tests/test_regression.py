import os
from datetime import datetime
from pathlib import Path

import pytest

from moon_data.location import ObserverLocation
from moon_data.moon import DEFAULT_EPHEMERIS, generate_full_moon_guide, generate_report


def regression_cache_dir() -> Path | None:
    candidates = []

    env_cache = os.environ.get("MOON_DATA_TEST_CACHE")
    if env_cache:
        candidates.append(Path(env_cache))

    candidates.extend(
        [
            Path("/tmp/moon-data"),
            Path.home() / ".cache" / "moon-data",
        ]
    )

    for candidate in candidates:
        if (candidate / DEFAULT_EPHEMERIS).exists():
            return candidate
    return None


pytestmark = pytest.mark.skipif(
    regression_cache_dir() is None,
    reason="cached ephemeris not available; run `moon-data fetch-ephemeris --cache-dir /tmp/moon-data` first",
)


def test_denver_waxing_crescent_regression() -> None:
    report = generate_report(
        location=ObserverLocation(39.7392, -104.9903, timezone_name="America/Denver"),
        observed_at=datetime.fromisoformat("2026-04-21T22:00:00-06:00"),
        cache_dir=regression_cache_dir(),
        no_download=True,
    )

    assert report.phase_name == "Waxing Crescent"
    assert report.illumination_percent == pytest.approx(28.7045, abs=0.01)
    assert report.right_ascension_hours == pytest.approx(6.4708, abs=0.01)
    assert report.declination_degrees == pytest.approx(27.7385, abs=0.02)
    assert report.altitude_degrees == pytest.approx(32.8724, abs=0.02)
    assert report.azimuth_degrees == pytest.approx(279.9428, abs=0.02)
    assert report.visible_now is True
    assert report.good_viewing_now is True
    assert report.next_moonset is not None
    assert report.next_moonrise is not None
    assert report.next_moonset < report.next_moonrise
    assert report.next_full_moon is not None
    assert report.next_new_moon is not None
    assert report.next_full_moon < report.next_new_moon


def test_new_york_full_moon_regression() -> None:
    report = generate_report(
        location=ObserverLocation(40.7128, -74.0060, timezone_name="America/New_York"),
        observed_at=datetime.fromisoformat("2026-05-01T22:00:00-04:00"),
        cache_dir=regression_cache_dir(),
        no_download=True,
    )

    assert report.phase_name == "Full Moon"
    assert report.illumination_percent == pytest.approx(99.7130, abs=0.02)
    assert report.altitude_degrees == pytest.approx(14.1612, abs=0.03)
    assert report.azimuth_degrees == pytest.approx(136.1692, abs=0.03)
    assert report.visible_now is True
    assert report.good_viewing_now is True
    assert report.next_good_viewing_ends_at is not None
    assert report.next_good_viewing_at == report.observed_at
    assert report.next_good_viewing_ends_at > report.observed_at


def test_london_hidden_moon_regression() -> None:
    report = generate_report(
        location=ObserverLocation(51.5074, -0.1278, timezone_name="Europe/London"),
        observed_at=datetime.fromisoformat("2026-10-28T12:00:00+00:00"),
        cache_dir=regression_cache_dir(),
        no_download=True,
    )

    assert report.phase_name == "Waning Gibbous"
    assert report.altitude_degrees < 0.0
    assert report.visible_now is False
    assert report.good_viewing_now is False
    assert report.next_moonrise is not None
    assert report.next_good_viewing_at is not None
    assert report.next_moonrise == report.next_good_viewing_at
    assert report.next_good_viewing_ends_at is not None
    assert report.next_good_viewing_ends_at < report.next_moonset


def test_denver_full_moon_guide_regression() -> None:
    guide = generate_full_moon_guide(
        location=ObserverLocation(39.7392, -104.9903, timezone_name="America/Denver"),
        observed_at=datetime.fromisoformat("2026-04-21T06:30:00-06:00"),
        cache_dir=regression_cache_dir(),
        no_download=True,
    )

    assert guide.best_viewing_date == "Friday, May 1, 2026"
    assert guide.recommended_direction == "Southeast"
    assert guide.recommended_azimuth_degrees == pytest.approx(139.4, abs=1.0)
    assert guide.peak_altitude_degrees == pytest.approx(27.6, abs=1.0)
    assert guide.viewing_window_start is not None
    assert guide.viewing_window_end is not None
    assert guide.viewing_window_start < guide.viewing_window_end
    assert "highest dark-sky moon altitude" in guide.selection_reason
    assert len(guide.tips) >= 3
