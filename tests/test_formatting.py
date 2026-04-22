import json
from datetime import UTC, datetime

import pytest

from moon_data.formatting import format_report_json, format_report_text
from moon_data.moon import FullMoonViewingGuide, MoonReport, phase_name_from_angle


def build_report() -> MoonReport:
    return MoonReport(
        observed_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        timezone="UTC",
        latitude=39.7392,
        longitude=-104.9903,
        elevation_m=1609.0,
        phase_name="Full Moon",
        illumination_percent=99.1,
        moon_age_days=14.2,
        next_new_moon=datetime(2026, 5, 1, 3, 0, tzinfo=UTC),
        next_full_moon=datetime(2026, 5, 16, 18, 0, tzinfo=UTC),
        right_ascension_hours=13.1,
        declination_degrees=-8.4,
        altitude_degrees=31.5,
        azimuth_degrees=122.8,
        geocentric_distance_km=384400.0,
        topocentric_distance_km=384050.0,
        visible_now=True,
        good_viewing_now=False,
        next_moonrise=datetime(2026, 4, 21, 20, 15, tzinfo=UTC),
        next_moonset=datetime(2026, 4, 22, 6, 45, tzinfo=UTC),
        next_good_viewing_at=datetime(2026, 4, 21, 20, 30, tzinfo=UTC),
        next_good_viewing_ends_at=datetime(2026, 4, 22, 5, 55, tzinfo=UTC),
    )


def build_guide() -> FullMoonViewingGuide:
    return FullMoonViewingGuide(
        next_full_moon=datetime(2026, 5, 1, 11, 23, tzinfo=UTC),
        best_viewing_date="Friday, May 1, 2026",
        viewing_window_start=datetime(2026, 5, 1, 22, 24, tzinfo=UTC),
        viewing_window_end=datetime(2026, 5, 2, 4, 9, tzinfo=UTC),
        sunset=datetime(2026, 5, 1, 19, 54, tzinfo=UTC),
        moonrise=datetime(2026, 5, 1, 20, 24, tzinfo=UTC),
        moonset=None,
        peak_altitude_time=datetime(2026, 5, 2, 1, 9, tzinfo=UTC),
        peak_altitude_degrees=27.6,
        recommended_direction="Southeast",
        recommended_azimuth_degrees=139.4,
        selection_reason="Chosen because it gives the highest dark-sky moon altitude on an evening nearest the next full moon.",
        tips=[
            "Plan for Friday evening, starting around May 1 10:24 PM UTC.",
            "Look toward the southeast as the moon climbs.",
        ],
    )


def test_format_report_text_contains_key_fields() -> None:
    text = format_report_text(build_report())
    assert "MOON DATA :: FULL MOON" in text
    assert "[VISIBLE:YES]" in text
    assert "+" in text and "|" in text
    assert "| Lunar State" in text
    assert "Phase" in text and "Full Moon" in text
    assert "Apr 21, 2026 12:00 PM UTC" in text
    assert "2026-04-21T12:00:00+00:00" not in text


def test_format_report_json_contains_iso_timestamps() -> None:
    payload = json.loads(format_report_json(build_report()))
    assert payload["phase_name"] == "Full Moon"
    assert payload["next_new_moon"] == "2026-05-01T03:00:00+00:00"
    assert payload["distance_unit"] == "km"


def test_format_report_text_supports_miles() -> None:
    text = format_report_text(build_report(), units="mi")
    assert "238,855 mi" in text


def test_format_report_text_supports_compact_mode() -> None:
    text = format_report_text(build_report(), compact=True)
    assert "MOON DATA :: FULL MOON" in text
    assert "Full Moon | illum 99.10% | age 14.20 d" in text
    assert "[VISIBLE:YES] [DARK-SKY:NO]" in text
    assert "next rise Apr 21, 2026 8:15 PM UTC" in text


def test_format_report_json_supports_miles() -> None:
    payload = json.loads(format_report_json(build_report(), units="mi"))
    assert payload["distance_unit"] == "mi"
    assert payload["geocentric_distance"] == pytest.approx(238855.0124)


def test_format_report_text_includes_full_moon_guide() -> None:
    text = format_report_text(build_report(), guide=build_guide())
    assert "| Next Full Moon Guide" in text
    assert "Friday, May 1, 2026" in text
    assert "Southeast (139.4 deg)" in text
    assert "| Guide Tips" in text


def test_format_report_json_includes_full_moon_guide() -> None:
    payload = json.loads(format_report_json(build_report(), guide=build_guide()))
    assert payload["full_moon_guide"]["best_viewing_date"] == "Friday, May 1, 2026"
    assert payload["full_moon_guide"]["recommended_direction"] == "Southeast"


def test_phase_name_from_angle_uses_eight_phase_buckets() -> None:
    assert phase_name_from_angle(10.0) == "New Moon"
    assert phase_name_from_angle(45.0) == "Waxing Crescent"
    assert phase_name_from_angle(90.0) == "First Quarter"
    assert phase_name_from_angle(135.0) == "Waxing Gibbous"
    assert phase_name_from_angle(180.0) == "Full Moon"
    assert phase_name_from_angle(225.0) == "Waning Gibbous"
    assert phase_name_from_angle(270.0) == "Last Quarter"
    assert phase_name_from_angle(315.0) == "Waning Crescent"
