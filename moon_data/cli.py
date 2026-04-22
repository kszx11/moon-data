from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from moon_data.formatting import format_report_json, format_report_text
from moon_data.location import ObserverLocation
from moon_data.moon import (
    MoonDataError,
    fetch_ephemeris,
    generate_full_moon_guide,
    generate_report,
    resolve_cache_dir,
)


def build_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show current moon data for an observer.")
    parser.add_argument("--lat", type=float, required=True, help="Observer latitude in decimal degrees.")
    parser.add_argument("--lon", type=float, required=True, help="Observer longitude in decimal degrees.")
    parser.add_argument("--elevation", type=float, default=0.0, help="Observer elevation in meters.")
    parser.add_argument("--tz", default="UTC", help="IANA timezone name, for example America/Denver.")
    parser.add_argument(
        "--at",
        help="Observation time in ISO-8601. If omitted, the current time is used.",
    )
    parser.add_argument("--units", choices=("km", "mi"), default="km", help="Distance units for output.")
    parser.add_argument("--cache-dir", type=Path, help="Override the ephemeris cache directory.")
    parser.add_argument("--compact", action="store_true", help="Emit a condensed text layout.")
    parser.add_argument(
        "--full-moon-guide",
        action="store_true",
        help="Include a best-viewing guide for the next full moon at this location.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Require the ephemeris to already exist in the cache instead of downloading it.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text.")
    return parser


def build_fetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download and cache the Skyfield ephemeris file.")
    parser.add_argument("--cache-dir", type=Path, help="Override the ephemeris cache directory.")
    return parser


def parse_observation_time(raw: str | None) -> datetime | None:
    if raw is None:
        return None

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise MoonDataError(f"Invalid --at value '{raw}'. Use ISO-8601, for example 2026-04-21T22:00:00-06:00.") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90.0 <= latitude <= 90.0:
        raise MoonDataError(f"Invalid latitude {latitude}. Expected a value between -90 and 90.")
    if not -180.0 <= longitude <= 180.0:
        raise MoonDataError(f"Invalid longitude {longitude}. Expected a value between -180 and 180.")


def validate_timezone(timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise MoonDataError(
            f"Unknown timezone '{timezone_name}'. Use an IANA name such as America/Denver."
        ) from exc


def run_fetch_ephemeris(argv: list[str]) -> int:
    parser = build_fetch_parser()
    args = parser.parse_args(argv)

    try:
        ephemeris_path = fetch_ephemeris(cache_dir=args.cache_dir)
    except MoonDataError as exc:
        print(f"moon-data error: {exc}", file=sys.stderr)
        return 1

    cache_root = resolve_cache_dir(args.cache_dir)
    print(f"Ephemeris cached at {ephemeris_path}")
    print(f"Cache directory: {cache_root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if argv and argv[0] == "fetch-ephemeris":
        return run_fetch_ephemeris(argv[1:])

    parser = build_report_parser()
    args = parser.parse_args(argv)

    try:
        validate_coordinates(args.lat, args.lon)
        validate_timezone(args.tz)
        location = ObserverLocation(
            latitude=args.lat,
            longitude=args.lon,
            elevation_m=args.elevation,
            timezone_name=args.tz,
        )
        observed_at = parse_observation_time(args.at)
        report = generate_report(
            location=location,
            observed_at=observed_at,
            cache_dir=args.cache_dir,
            no_download=args.no_download,
        )
        guide = None
        if args.full_moon_guide:
            guide = generate_full_moon_guide(
                location=location,
                observed_at=observed_at,
                cache_dir=args.cache_dir,
                no_download=args.no_download,
            )
    except MoonDataError as exc:
        print(f"moon-data error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"moon-data error: {exc}", file=sys.stderr)
        return 1

    output = (
        format_report_json(report, units=args.units, guide=guide)
        if args.json
        else format_report_text(report, units=args.units, compact=args.compact, guide=guide)
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
