from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ObserverLocation:
    latitude: float
    longitude: float
    elevation_m: float = 0.0
    timezone_name: str = "UTC"

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def to_local(self, when: datetime) -> datetime:
        return when.astimezone(self.tzinfo)
