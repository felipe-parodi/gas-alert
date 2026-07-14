"""Data sources. Each exposes cheapest_regular(city) -> StationPrice.

Sources raise SourceUnavailable when they can't produce a usable answer
(blocked, no key, no fresh prices); the caller then tries the next source.
"""

from dataclasses import dataclass


class SourceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class StationPrice:
    station: str  # e.g. "Costco"
    address: str  # street address, e.g. "150 Lawrence Station Rd"
    price: float  # USD per gallon, Regular (87)
    source: str  # which source produced this
    maps_url: str  # link to the station on Google Maps

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
