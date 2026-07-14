"""Data sources. Each exposes cheapest_regular(city) -> StationPrice.

Sources raise SourceUnavailable when they can't produce a usable answer
(blocked, no key, no fresh prices); the caller then tries the next source.
"""

import math
from dataclasses import dataclass


class SourceUnavailable(Exception):
    pass


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine great-circle distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class AnchorPick:
    """Best station near an anchor: cheapest, nearest among near-ties."""

    label: str
    short: str
    radius_km: float
    station: "StationPrice"
    distance_km: float


def is_excluded(station_name: str, excluded: list[str]) -> bool:
    name = station_name.lower()
    return any(pattern in name for pattern in excluded)


@dataclass(frozen=True)
class StationPrice:
    station: str  # e.g. "Chevron"
    address: str  # street address, e.g. "450 10th St"
    price: float  # USD per gallon, Regular (87)
    source: str  # which source produced this
    lat: float | None = None  # station coords when the source provides them;
    lng: float | None = None  # map links fall back to a name+address search

    @property
    def short_label(self) -> str:
        """Brand + street name for the SMS line, e.g. 'Costco Lawrence'."""
        street = self.address.split(",")[0]
        words = [w for w in street.split() if not w.replace("-", "").isdigit()]
        # Drop trailing suffixes like Rd/Ave/Blvd so the label stays short.
        suffixes = {"rd", "rd.", "ave", "ave.", "st", "st.", "blvd", "blvd.",
                    "dr", "dr.", "way", "hwy", "expy", "pkwy", "ln", "ct"}
        while len(words) > 1 and words[-1].lower() in suffixes:
            words.pop()
        return f"{self.station} {' '.join(words[:2])}".strip()
