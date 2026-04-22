from __future__ import annotations

from pathlib import Path
import os


DEFAULT_EPHEMERIS = "de421.bsp"
EVENT_LOOKAHEAD_DAYS = 40
VISIBILITY_LOOKAHEAD_DAYS = 7


def default_cache_dir() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "moon-data"
    return Path.home() / ".cache" / "moon-data"
