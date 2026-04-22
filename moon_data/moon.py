from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from skyfield import almanac
from skyfield.api import Loader, wgs84

from moon_data.config import (
    DEFAULT_EPHEMERIS,
    EVENT_LOOKAHEAD_DAYS,
    VISIBILITY_LOOKAHEAD_DAYS,
    default_cache_dir,
)
from moon_data.location import ObserverLocation


class MoonDataError(Exception):
    """Raised for user-facing Moon Data runtime errors."""


def resolve_cache_dir(cache_dir: Path | None = None) -> Path:
    return cache_dir or default_cache_dir()


def phase_name_from_angle(phase_angle_degrees: float) -> str:
    normalized = phase_angle_degrees % 360.0

    if normalized < 22.5 or normalized >= 337.5:
        return "New Moon"
    if normalized < 67.5:
        return "Waxing Crescent"
    if normalized < 112.5:
        return "First Quarter"
    if normalized < 157.5:
        return "Waxing Gibbous"
    if normalized < 202.5:
        return "Full Moon"
    if normalized < 247.5:
        return "Waning Gibbous"
    if normalized < 292.5:
        return "Last Quarter"
    return "Waning Crescent"


@dataclass(frozen=True)
class MoonReport:
    observed_at: datetime
    timezone: str
    latitude: float
    longitude: float
    elevation_m: float
    phase_name: str
    illumination_percent: float
    moon_age_days: float
    next_new_moon: datetime | None
    next_full_moon: datetime | None
    right_ascension_hours: float
    declination_degrees: float
    altitude_degrees: float
    azimuth_degrees: float
    geocentric_distance_km: float
    topocentric_distance_km: float
    visible_now: bool
    good_viewing_now: bool
    next_moonrise: datetime | None
    next_moonset: datetime | None
    next_good_viewing_at: datetime | None
    next_good_viewing_ends_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        return payload


@dataclass(frozen=True)
class FullMoonViewingGuide:
    next_full_moon: datetime
    best_viewing_date: str
    viewing_window_start: datetime | None
    viewing_window_end: datetime | None
    sunset: datetime | None
    moonrise: datetime | None
    moonset: datetime | None
    peak_altitude_time: datetime | None
    peak_altitude_degrees: float | None
    recommended_direction: str | None
    recommended_azimuth_degrees: float | None
    selection_reason: str
    tips: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        return payload


def generate_report(
    location: ObserverLocation,
    observed_at: datetime | None = None,
    cache_dir: Path | None = None,
    ephemeris_name: str = DEFAULT_EPHEMERIS,
    no_download: bool = False,
) -> MoonReport:
    cache_root = resolve_cache_dir(cache_dir)
    loader, ephemeris = load_ephemeris(
        cache_dir=cache_root,
        ephemeris_name=ephemeris_name,
        no_download=no_download,
    )
    timescale = loader.timescale()

    earth = ephemeris["earth"]
    moon = ephemeris["moon"]
    sun = ephemeris["sun"]

    observed_at = observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    observed_at = observed_at.astimezone(UTC)
    t = timescale.from_datetime(observed_at)

    observer = wgs84.latlon(
        latitude_degrees=location.latitude,
        longitude_degrees=location.longitude,
        elevation_m=location.elevation_m,
    )

    geocentric = earth.at(t).observe(moon).apparent()
    topocentric = (earth + observer).at(t).observe(moon).apparent()
    sun_topocentric = (earth + observer).at(t).observe(sun).apparent()

    ra, dec, geocentric_distance = geocentric.radec()
    alt, az, topocentric_distance = topocentric.altaz()
    sun_alt, _, _ = sun_topocentric.altaz()

    illumination = almanac.fraction_illuminated(ephemeris, "moon", t) * 100.0
    phase_angle = almanac.moon_phase(ephemeris, t).degrees
    next_new, next_full = _next_major_phases(timescale, ephemeris, observed_at)
    previous_new = _previous_phase(timescale, ephemeris, observed_at, phase_code=0)
    moon_age = (observed_at - previous_new).total_seconds() / 86400.0 if previous_new else 0.0

    next_rise, next_set = _next_rise_set(timescale, ephemeris, observer, moon, observed_at)
    next_good_start, next_good_end = _next_good_viewing_window(
        timescale=timescale,
        ephemeris=ephemeris,
        observer=observer,
        moon=moon,
        sun=sun,
        observed_at=observed_at,
        moon_above_horizon=alt.degrees > 0.0,
        sun_below_horizon=sun_alt.degrees < 0.0,
    )
    visible_now = bool(alt.degrees > 0.0)
    good_viewing_now = bool(alt.degrees > 0.0 and sun_alt.degrees < 0.0)

    return MoonReport(
        observed_at=observed_at.astimezone(location.tzinfo),
        timezone=location.timezone_name,
        latitude=location.latitude,
        longitude=location.longitude,
        elevation_m=location.elevation_m,
        phase_name=phase_name_from_angle(phase_angle),
        illumination_percent=illumination,
        moon_age_days=moon_age,
        next_new_moon=next_new.astimezone(location.tzinfo) if next_new else None,
        next_full_moon=next_full.astimezone(location.tzinfo) if next_full else None,
        right_ascension_hours=ra.hours,
        declination_degrees=dec.degrees,
        altitude_degrees=alt.degrees,
        azimuth_degrees=az.degrees,
        geocentric_distance_km=geocentric_distance.km,
        topocentric_distance_km=topocentric_distance.km,
        visible_now=visible_now,
        good_viewing_now=good_viewing_now,
        next_moonrise=next_rise.astimezone(location.tzinfo) if next_rise else None,
        next_moonset=next_set.astimezone(location.tzinfo) if next_set else None,
        next_good_viewing_at=next_good_start.astimezone(location.tzinfo) if next_good_start else None,
        next_good_viewing_ends_at=next_good_end.astimezone(location.tzinfo) if next_good_end else None,
    )


def generate_full_moon_guide(
    location: ObserverLocation,
    observed_at: datetime | None = None,
    cache_dir: Path | None = None,
    ephemeris_name: str = DEFAULT_EPHEMERIS,
    no_download: bool = False,
) -> FullMoonViewingGuide:
    cache_root = resolve_cache_dir(cache_dir)
    loader, ephemeris = load_ephemeris(
        cache_dir=cache_root,
        ephemeris_name=ephemeris_name,
        no_download=no_download,
    )
    timescale = loader.timescale()

    earth = ephemeris["earth"]
    moon = ephemeris["moon"]
    observer = wgs84.latlon(
        latitude_degrees=location.latitude,
        longitude_degrees=location.longitude,
        elevation_m=location.elevation_m,
    )

    observed_at = observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    observed_at = observed_at.astimezone(UTC)

    _, next_full = _next_major_phases(timescale, ephemeris, observed_at)
    if next_full is None:
        raise MoonDataError("Unable to determine the next full moon.")

    local_full = next_full.astimezone(location.tzinfo)
    observed_local = observed_at.astimezone(location.tzinfo)
    candidate_dates = _candidate_viewing_dates(local_full.date(), observed_local.date())

    candidates = []
    for candidate_date in candidate_dates:
        candidate = _evaluate_full_moon_evening(
            timescale=timescale,
            ephemeris=ephemeris,
            earth=earth,
            moon=moon,
            observer=observer,
            location=location,
            next_full=next_full,
            candidate_date=candidate_date,
            full_moon_local_date=local_full.date(),
        )
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        raise MoonDataError("Unable to find a usable viewing window around the next full moon.")

    best = max(
        candidates,
        key=lambda item: (
            item["score"],
            item["candidate_date"] == local_full.date(),
            -abs((item["candidate_date"] - local_full.date()).days),
        ),
    )

    return FullMoonViewingGuide(
        next_full_moon=next_full.astimezone(location.tzinfo),
        best_viewing_date=_format_local_date(best["candidate_date"]),
        viewing_window_start=best["window_start"].astimezone(location.tzinfo),
        viewing_window_end=best["window_end"].astimezone(location.tzinfo),
        sunset=best["sunset"].astimezone(location.tzinfo),
        moonrise=best["moonrise"].astimezone(location.tzinfo) if best["moonrise"] else None,
        moonset=best["moonset"].astimezone(location.tzinfo) if best["moonset"] else None,
        peak_altitude_time=best["peak_time"].astimezone(location.tzinfo),
        peak_altitude_degrees=best["peak_altitude"],
        recommended_direction=best["direction"],
        recommended_azimuth_degrees=best["start_azimuth"],
        selection_reason=best["selection_reason"],
        tips=best["tips"],
    )


def fetch_ephemeris(
    cache_dir: Path | None = None,
    ephemeris_name: str = DEFAULT_EPHEMERIS,
) -> Path:
    cache_root = resolve_cache_dir(cache_dir)
    load_ephemeris(cache_dir=cache_root, ephemeris_name=ephemeris_name, no_download=False)
    return cache_root / ephemeris_name


def load_ephemeris(
    cache_dir: Path | None = None,
    ephemeris_name: str = DEFAULT_EPHEMERIS,
    no_download: bool = False,
):
    cache_root = resolve_cache_dir(cache_dir)
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MoonDataError(f"Unable to create cache directory '{cache_root}': {exc}") from exc

    loader = Loader(str(cache_root))
    ephemeris_path = cache_root / ephemeris_name
    if no_download and not ephemeris_path.exists():
        raise MoonDataError(
            f"Ephemeris '{ephemeris_name}' is not cached in '{cache_root}'. "
            "Run once without --no-download or point --cache-dir at an existing cache."
        )

    try:
        ephemeris = loader(ephemeris_name)
    except OSError as exc:
        raise MoonDataError(
            f"Unable to load ephemeris '{ephemeris_name}'. "
            "If this is the first run, allow downloads or pre-populate the cache directory."
        ) from exc

    return loader, ephemeris


def _candidate_viewing_dates(full_moon_local_date: date, observed_local_date: date) -> list[date]:
    dates = []
    for offset in (-1, 0, 1):
        candidate = full_moon_local_date + timedelta(days=offset)
        if candidate >= observed_local_date and candidate not in dates:
            dates.append(candidate)
    if not dates:
        dates.append(full_moon_local_date)
    return dates


def _evaluate_full_moon_evening(
    *,
    timescale,
    ephemeris,
    earth,
    moon,
    observer,
    location: ObserverLocation,
    next_full: datetime,
    candidate_date: date,
    full_moon_local_date: date,
):
    sunset, sunrise = _night_window_for_local_date(
        timescale=timescale,
        ephemeris=ephemeris,
        observer=observer,
        location=location,
        local_date=candidate_date,
    )
    if sunset is None or sunrise is None or sunrise <= sunset:
        return None

    moonrise, moonset = _moon_events_for_window(
        timescale=timescale,
        ephemeris=ephemeris,
        observer=observer,
        moon=moon,
        start_dt=sunset,
        end_dt=sunrise,
    )

    samples = _sample_moon_track(
        timescale=timescale,
        earth=earth,
        moon=moon,
        observer=observer,
        start_dt=sunset,
        end_dt=sunrise,
        step_minutes=15,
    )
    if not samples:
        return None

    peak_index = max(range(len(samples)), key=lambda idx: samples[idx]["altitude"])
    peak = samples[peak_index]

    threshold = 15.0 if any(sample["altitude"] >= 15.0 for sample in samples) else 5.0
    valid_indices = [idx for idx, sample in enumerate(samples) if sample["altitude"] >= threshold]
    if not valid_indices:
        threshold = 0.0
        valid_indices = [idx for idx, sample in enumerate(samples) if sample["altitude"] >= 0.0]
    if not valid_indices:
        return None

    anchor_index = peak_index if peak_index in valid_indices else max(valid_indices, key=lambda idx: samples[idx]["altitude"])
    start_index = anchor_index
    while start_index > 0 and samples[start_index - 1]["altitude"] >= threshold:
        start_index -= 1
    end_index = anchor_index
    while end_index + 1 < len(samples) and samples[end_index + 1]["altitude"] >= threshold:
        end_index += 1

    window_start = samples[start_index]["time"]
    window_end = samples[end_index]["time"]
    start_azimuth = samples[start_index]["azimuth"]
    peak_altitude = peak["altitude"]
    direction = _azimuth_to_direction(start_azimuth)

    score = peak_altitude
    if candidate_date == full_moon_local_date:
        score += 3.0
    score -= abs((candidate_date - full_moon_local_date).days) * 1.5
    if threshold == 0.0:
        score -= 8.0

    selection_reason = (
        "Chosen because it gives the highest dark-sky moon altitude on an evening nearest the next full moon."
    )
    tips = _build_full_moon_tips(
        candidate_date=candidate_date,
        direction=direction,
        threshold=threshold,
        window_start=window_start.astimezone(location.tzinfo),
        moonrise=moonrise.astimezone(location.tzinfo) if moonrise else None,
        peak_time=peak["time"].astimezone(location.tzinfo),
    )

    return {
        "candidate_date": candidate_date,
        "sunset": sunset,
        "sunrise": sunrise,
        "moonrise": moonrise,
        "moonset": moonset,
        "window_start": window_start,
        "window_end": window_end,
        "peak_time": peak["time"],
        "peak_altitude": peak_altitude,
        "start_azimuth": start_azimuth,
        "direction": direction,
        "selection_reason": selection_reason,
        "tips": tips,
        "score": score,
    }


def _night_window_for_local_date(*, timescale, ephemeris, observer, location: ObserverLocation, local_date: date):
    start_local = datetime.combine(local_date, time(12, 0), tzinfo=location.tzinfo)
    end_local = start_local + timedelta(days=1)
    event_fn = almanac.sunrise_sunset(ephemeris, observer)
    times, states = almanac.find_discrete(
        timescale.from_datetime(start_local.astimezone(UTC)),
        timescale.from_datetime(end_local.astimezone(UTC)),
        event_fn,
    )

    sunset: datetime | None = None
    sunrise: datetime | None = None
    for time_value, state in zip(times, states, strict=True):
        dt = time_value.utc_datetime().replace(tzinfo=UTC)
        if not state and sunset is None:
            sunset = dt
        elif state and sunset is not None:
            sunrise = dt
            break
    return sunset, sunrise


def _moon_events_for_window(*, timescale, ephemeris, observer, moon, start_dt: datetime, end_dt: datetime):
    event_fn = almanac.risings_and_settings(ephemeris, moon, observer)
    times, states = almanac.find_discrete(
        timescale.from_datetime(start_dt),
        timescale.from_datetime(end_dt),
        event_fn,
    )

    moonrise: datetime | None = None
    moonset: datetime | None = None
    for time_value, state in zip(times, states, strict=True):
        dt = time_value.utc_datetime().replace(tzinfo=UTC)
        if state and moonrise is None:
            moonrise = dt
        elif not state and moonset is None:
            moonset = dt
    return moonrise, moonset


def _sample_moon_track(*, timescale, earth, moon, observer, start_dt: datetime, end_dt: datetime, step_minutes: int):
    samples = []
    current = start_dt
    while current <= end_dt:
        t = timescale.from_datetime(current)
        apparent = (earth + observer).at(t).observe(moon).apparent()
        alt, az, _ = apparent.altaz()
        samples.append(
            {
                "time": current,
                "altitude": float(alt.degrees),
                "azimuth": float(az.degrees),
            }
        )
        current += timedelta(minutes=step_minutes)
    return samples


def _build_full_moon_tips(
    *,
    candidate_date: date,
    direction: str,
    threshold: float,
    window_start: datetime,
    moonrise: datetime | None,
    peak_time: datetime,
) -> list[str]:
    tips = [
        f"Plan for {candidate_date.strftime('%A')} evening, starting around {_format_short_local_dt(window_start)}.",
        f"Look toward the {direction.lower()} as the moon climbs.",
    ]
    if moonrise is not None:
        tips.append(f"Moonrise is around {_format_short_local_dt(moonrise)}.")
    if threshold >= 15.0:
        tips.append(f"Best contrast and height should build toward {_format_short_local_dt(peak_time)}.")
    else:
        tips.append("The moon stays fairly low that evening, so a clear horizon will help.")
    return tips


def _azimuth_to_direction(azimuth_degrees: float) -> str:
    directions = [
        "North",
        "Northeast",
        "East",
        "Southeast",
        "South",
        "Southwest",
        "West",
        "Northwest",
    ]
    index = int(((azimuth_degrees % 360.0) + 22.5) // 45) % len(directions)
    return directions[index]


def _format_local_date(value: date) -> str:
    month = value.strftime("%b")
    day = value.strftime("%d").lstrip("0") or "0"
    year = value.strftime("%Y")
    weekday = value.strftime("%A")
    return f"{weekday}, {month} {day}, {year}"


def _format_short_local_dt(value: datetime) -> str:
    month = value.strftime("%b")
    day = value.strftime("%d").lstrip("0") or "0"
    hour = value.strftime("%I").lstrip("0") or "12"
    minute = value.strftime("%M")
    meridiem = value.strftime("%p")
    tzname = value.tzname() or value.strftime("%z") or "UTC"
    return f"{month} {day} {hour}:{minute} {meridiem} {tzname}"


def _next_major_phases(timescale, ephemeris, observed_at: datetime) -> tuple[datetime | None, datetime | None]:
    start = timescale.from_datetime(observed_at)
    end = timescale.from_datetime(observed_at + timedelta(days=EVENT_LOOKAHEAD_DAYS))
    phase_fn = almanac.moon_phases(ephemeris)
    times, phases = almanac.find_discrete(start, end, phase_fn)

    next_new: datetime | None = None
    next_full: datetime | None = None
    for time, phase in zip(times, phases, strict=True):
        dt = time.utc_datetime().replace(tzinfo=UTC)
        if phase == 0 and next_new is None:
            next_new = dt
        if phase == 2 and next_full is None:
            next_full = dt
        if next_new and next_full:
            break
    return next_new, next_full


def _previous_phase(timescale, ephemeris, observed_at: datetime, phase_code: int) -> datetime | None:
    start = timescale.from_datetime(observed_at - timedelta(days=EVENT_LOOKAHEAD_DAYS))
    end = timescale.from_datetime(observed_at)
    phase_fn = almanac.moon_phases(ephemeris)
    times, phases = almanac.find_discrete(start, end, phase_fn)

    candidates = [
        time.utc_datetime().replace(tzinfo=UTC)
        for time, phase in zip(times, phases, strict=True)
        if phase == phase_code
    ]
    return candidates[-1] if candidates else None


def _next_rise_set(timescale, ephemeris, observer, moon, observed_at: datetime) -> tuple[datetime | None, datetime | None]:
    start = timescale.from_datetime(observed_at)
    end = timescale.from_datetime(observed_at + timedelta(days=VISIBILITY_LOOKAHEAD_DAYS))
    event_fn = almanac.risings_and_settings(ephemeris, moon, observer)
    times, states = almanac.find_discrete(start, end, event_fn)

    next_rise: datetime | None = None
    next_set: datetime | None = None
    for time, state in zip(times, states, strict=True):
        dt = time.utc_datetime().replace(tzinfo=UTC)
        if state and next_rise is None:
            next_rise = dt
        if not state and next_set is None:
            next_set = dt
        if next_rise and next_set:
            break
    return next_rise, next_set


def _next_good_viewing_window(
    *,
    timescale,
    ephemeris,
    observer,
    moon,
    sun,
    observed_at: datetime,
    moon_above_horizon: bool,
    sun_below_horizon: bool,
) -> tuple[datetime | None, datetime | None]:
    start = timescale.from_datetime(observed_at)
    end = timescale.from_datetime(observed_at + timedelta(days=VISIBILITY_LOOKAHEAD_DAYS))

    moon_event_fn = almanac.risings_and_settings(ephemeris, moon, observer)
    sun_event_fn = almanac.sunrise_sunset(ephemeris, observer)

    moon_times, moon_states = almanac.find_discrete(start, end, moon_event_fn)
    sun_times, sun_states = almanac.find_discrete(start, end, sun_event_fn)

    current_moon_above = moon_above_horizon
    current_sun_down = sun_below_horizon
    current_good = current_moon_above and current_sun_down
    next_good_start = observed_at if current_good else None
    next_good_end: datetime | None = None

    events: list[tuple[datetime, str, bool]] = []
    for time, state in zip(moon_times, moon_states, strict=True):
        events.append((time.utc_datetime().replace(tzinfo=UTC), "moon", bool(state)))
    for time, state in zip(sun_times, sun_states, strict=True):
        events.append((time.utc_datetime().replace(tzinfo=UTC), "sun", bool(state)))
    events.sort(key=lambda item: item[0])

    for event_time, event_type, state in events:
        previous_good = current_moon_above and current_sun_down

        if event_type == "moon":
            current_moon_above = state
        else:
            current_sun_down = not state

        current_good = current_moon_above and current_sun_down
        if not previous_good and current_good and next_good_start is None:
            next_good_start = event_time
        if previous_good and not current_good and next_good_start is not None:
            next_good_end = event_time
            break

    return next_good_start, next_good_end
