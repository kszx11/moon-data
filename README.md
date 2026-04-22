# Moon Data CLI

`moon-data` is a Python CLI that reports the moon's current state for a given observer location and can prefetch its astronomy data for offline use.

## Features

- Current moon phase and illumination
- Moon age since the last new moon
- Next new moon and next full moon
- Right ascension and declination
- Altitude and azimuth for the observer
- Distance from Earth
- Whether the moon is above the horizon right now
- Whether the moon is in a dark-sky viewing window right now
- Next moonrise and moonset
- Next dark-sky viewing window

## Install

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Cache Setup

The CLI uses the JPL `de421.bsp` ephemeris file. You can fetch it explicitly:

```bash
moon-data fetch-ephemeris
moon-data fetch-ephemeris --cache-dir /tmp/moon-data
```

By default the cache lives under `~/.cache/moon-data/`. You can override that with `--cache-dir` or `XDG_CACHE_HOME`.

For offline runs:

```bash
moon-data fetch-ephemeris --cache-dir /tmp/moon-data
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --cache-dir /tmp/moon-data --no-download
```

## Usage

```bash
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --json
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --at 2026-04-21T22:00:00
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --units mi
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --compact
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --full-moon-guide
moon-data --lat 39.7392 --lon -104.9903 --tz America/Denver --cache-dir /tmp/moon-data --no-download
```

`--compact` gives a dense terminal summary. `--json` keeps the full machine-readable payload stable for scripting.
`--full-moon-guide` adds a best-viewing recommendation for the next full moon at your location, including the best evening, suggested window, direction, and tips.

## Testing

The fast unit tests do not require a live download:

```bash
venv/bin/python -m pytest -q
```

The astronomy regression tests use cached ephemeris data and skip automatically if it is missing. To force those tests to use a specific cache, set `MOON_DATA_TEST_CACHE`.

## Notes

- `--lat` and `--lon` are required because altitude, azimuth, rise/set times, and visibility depend on the observer.
- `visible_now` means the moon is above the horizon.
- `good_viewing_now` means the moon is above the horizon and the sun is below the horizon.
- `--no-download` is useful for offline runs once the ephemeris has already been cached.
