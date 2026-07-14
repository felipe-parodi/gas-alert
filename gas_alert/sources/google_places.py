"""Google Places API (New) source — official, keyed, stable.

Gas stations in the Places API expose `fuelOptions.fuelPrices` (crowd/partner
sourced, same data you see on Google Maps). One searchNearby request per city
per day is far inside the free tier. Requires GOOGLE_MAPS_API_KEY with the
"Places API (New)" enabled.
"""

import datetime as dt

import requests

from ..config import MAX_PRICE_AGE_HOURS, City
from . import SourceUnavailable, StationPrice, is_excluded

SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = ",".join(
    [
        "places.displayName",
        "places.formattedAddress",
        "places.fuelOptions",
        "places.location",
    ]
)
RADIUS_METERS = 8000.0  # covers the city proper without bleeding far into neighbors
REGULAR_TYPES = {"REGULAR_UNLEADED"}


def _fresh(update_time: str | None) -> bool:
    if not update_time:
        return False
    try:
        updated = dt.datetime.fromisoformat(update_time.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = dt.datetime.now(dt.timezone.utc) - updated
    return age <= dt.timedelta(hours=MAX_PRICE_AGE_HOURS)


def cheapest_regular(
    city: City, api_key: str | None, excluded: list[str]
) -> StationPrice:
    if not api_key:
        raise SourceUnavailable("google_places: no GOOGLE_MAPS_API_KEY set")

    body = {
        "includedTypes": ["gas_station"],
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": city.lat, "longitude": city.lng},
                "radius": RADIUS_METERS,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    try:
        resp = requests.post(SEARCH_URL, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceUnavailable(f"google_places: {exc}") from exc

    best: StationPrice | None = None
    for place in data.get("places", []):
        name = (place.get("displayName") or {}).get("text", "Unknown")
        if is_excluded(name, excluded):
            continue
        fuel_prices = (place.get("fuelOptions") or {}).get("fuelPrices", [])
        for fp in fuel_prices:
            if fp.get("type") not in REGULAR_TYPES:
                continue
            money = fp.get("price") or {}
            if money.get("currencyCode") not in (None, "USD"):
                continue
            units = int(money.get("units", 0))
            nanos = int(money.get("nanos", 0))
            price = units + nanos / 1e9
            if price <= 0 or not _fresh(fp.get("updateTime")):
                continue
            location = place.get("location") or {}
            candidate = StationPrice(
                station=name,
                address=place.get("formattedAddress", ""),
                price=price,
                source="google_places",
                lat=location.get("latitude"),
                lng=location.get("longitude"),
            )
            if best is None or candidate.price < best.price:
                best = candidate
    if best is None:
        raise SourceUnavailable(
            f"google_places: no fresh regular prices for {city.name}"
        )
    return best
