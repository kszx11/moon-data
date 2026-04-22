from __future__ import annotations

from datetime import datetime
import json
from typing import Iterable

from moon_data.moon import FullMoonViewingGuide, MoonReport


def format_report_text(
    report: MoonReport,
    units: str = "km",
    compact: bool = False,
    guide: FullMoonViewingGuide | None = None,
) -> str:
    geocentric_distance, distance_unit = _convert_distance(report.geocentric_distance_km, units)
    topocentric_distance, _ = _convert_distance(report.topocentric_distance_km, units)
    if compact:
        lines = [
            _headline(report),
            f"{report.phase_name} | illum {report.illumination_percent:.2f}% | age {report.moon_age_days:.2f} d",
            f"alt {report.altitude_degrees:.2f} deg | az {report.azimuth_degrees:.2f} deg | dist {geocentric_distance:,.0f} {distance_unit}",
            f"{_badge('VISIBLE', report.visible_now)} {_badge('DARK-SKY', report.good_viewing_now)}",
            f"next rise {_format_dt(report.next_moonrise)} | next set {_format_dt(report.next_moonset)}",
        ]
        if guide is not None:
            lines.extend(
                [
                    f"full moon {guide.best_viewing_date} | window {_format_dt(guide.viewing_window_start)} to {_format_dt(guide.viewing_window_end)}",
                    f"look {guide.recommended_direction} | peak {guide.peak_altitude_degrees:.1f} deg at {_format_dt(guide.peak_altitude_time)}",
                ]
            )
        return "\n".join(lines)

    lines = [
        _headline(report),
        _summary_bar(report, geocentric_distance, distance_unit),
    ]
    lines.extend(
        _format_panel(
            "Observer",
            [
                ("Observed at", _format_dt(report.observed_at)),
                (
                    "Location",
                    f"lat {report.latitude:.4f}, lon {report.longitude:.4f}, elevation {report.elevation_m:.0f} m",
                ),
                ("Timezone", report.timezone),
            ],
        )
    )
    lines.extend(
        _format_panel(
            "Lunar State",
            [
                ("Phase", report.phase_name),
                ("Illumination", f"{report.illumination_percent:.2f}%"),
                ("Moon age", f"{report.moon_age_days:.2f} days"),
                ("Next new moon", _format_dt(report.next_new_moon)),
                ("Next full moon", _format_dt(report.next_full_moon)),
            ],
        )
    )
    lines.extend(
        _format_panel(
            "Position",
            [
                ("Right ascension", f"{report.right_ascension_hours:.4f} h"),
                ("Declination", f"{report.declination_degrees:.4f} deg"),
                ("Altitude", f"{report.altitude_degrees:.4f} deg"),
                ("Azimuth", f"{report.azimuth_degrees:.4f} deg"),
                ("Distance (geocentric)", f"{geocentric_distance:,.0f} {distance_unit}"),
                ("Distance (topocentric)", f"{topocentric_distance:,.0f} {distance_unit}"),
            ],
        )
    )
    lines.extend(
        _format_panel(
            "Visibility",
            [
                ("Visible now", _format_bool(report.visible_now)),
                ("Good viewing now", _format_bool(report.good_viewing_now)),
                ("Next moonrise", _format_dt(report.next_moonrise)),
                ("Next moonset", _format_dt(report.next_moonset)),
                ("Next viewing start", _format_dt(report.next_good_viewing_at)),
                ("Next viewing end", _format_dt(report.next_good_viewing_ends_at)),
            ],
        )
    )
    if guide is not None:
        lines.extend(
            _format_panel(
                "Next Full Moon Guide",
                [
                    ("Next full moon", _format_dt(guide.next_full_moon)),
                    ("Best viewing date", guide.best_viewing_date),
                    ("Viewing window", f"{_format_dt(guide.viewing_window_start)} to {_format_dt(guide.viewing_window_end)}"),
                    ("Sunset", _format_dt(guide.sunset)),
                    ("Moonrise", _format_dt(guide.moonrise)),
                    ("Moonset", _format_dt(guide.moonset)),
                    ("Peak altitude", f"{guide.peak_altitude_degrees:.1f} deg at {_format_dt(guide.peak_altitude_time)}"),
                    ("Look direction", f"{guide.recommended_direction} ({guide.recommended_azimuth_degrees:.1f} deg)"),
                    ("Why this night", guide.selection_reason),
                ],
            )
        )
        lines.extend(
            _format_panel(
                "Guide Tips",
                [(f"Tip {index}", tip) for index, tip in enumerate(guide.tips, start=1)],
            )
        )
    return "\n".join(lines)


def format_report_json(report: MoonReport, units: str = "km", guide: FullMoonViewingGuide | None = None) -> str:
    geocentric_distance, distance_unit = _convert_distance(report.geocentric_distance_km, units)
    topocentric_distance, _ = _convert_distance(report.topocentric_distance_km, units)
    payload = report.to_dict()
    payload["distance_unit"] = distance_unit
    payload["geocentric_distance"] = geocentric_distance
    payload["topocentric_distance"] = topocentric_distance
    if guide is not None:
        payload["full_moon_guide"] = guide.to_dict()
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_dt(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, datetime):
        month = value.strftime("%b")
        day = value.strftime("%d").lstrip("0") or "0"
        year = value.strftime("%Y")
        minute = value.strftime("%M")
        tzname = value.tzname() or value.strftime("%z") or "UTC"
        hour = value.strftime("%I").lstrip("0") or "12"
        meridiem = value.strftime("%p")
        return f"{month} {day}, {year} {hour}:{minute} {meridiem} {tzname}"
    return str(value)


def _convert_distance(distance_km: float, units: str) -> tuple[float, str]:
    if units == "mi":
        return distance_km * 0.621371, "mi"
    return distance_km, "km"


def _format_panel(title: str, rows: Iterable[tuple[str, str]]) -> list[str]:
    materialized = list(rows)
    width = max(len(label) for label, _ in materialized)
    value_width = max(len(value) for _, value in materialized)
    inner_width = max(len(title) + 2, width + value_width + 3)
    border = "+" + ("-" * (inner_width + 2)) + "+"
    lines = ["", border, f"| {title.ljust(inner_width)} |", border]
    lines.extend(
        f"| {label.ljust(width)} : {value.ljust(value_width)} |"
        for label, value in materialized
    )
    lines.append(border)
    return lines


def _headline(report: MoonReport) -> str:
    return f"MOON DATA :: {report.phase_name.upper()}"


def _summary_bar(report: MoonReport, geocentric_distance: float, distance_unit: str) -> str:
    parts = [
        f"observed {_format_dt(report.observed_at)}",
        f"illum {report.illumination_percent:.2f}%",
        f"age {report.moon_age_days:.2f} d",
        f"dist {geocentric_distance:,.0f} {distance_unit}",
        _badge("VISIBLE", report.visible_now),
        _badge("DARK-SKY", report.good_viewing_now),
    ]
    return " | ".join(parts)


def _badge(label: str, active: bool) -> str:
    state = "YES" if active else "NO"
    return f"[{label}:{state}]"
