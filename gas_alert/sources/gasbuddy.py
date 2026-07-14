"""GasBuddy unofficial GraphQL source.

Best price coverage when it works, but the endpoint sits behind Cloudflare
and rejects plain HTTP clients (403/400 as of July 2026). We still try it
first — it's one cheap request — and fall back if blocked.
"""

import datetime as dt

import requests

from ..config import MAX_PRICE_AGE_HOURS, City
from . import SourceUnavailable, StationPrice

GRAPHQL_URL = "https://www.gasbuddy.com/graphql"
FUEL_REGULAR = 1

QUERY = """
query LocationBySearchTerm($fuel: Int, $maxAge: Int, $search: String) {
  locationBySearchTerm(search: $search) {
    stations(fuel: $fuel, maxAge: $maxAge) {
      results {
        id
        name
        address { line1 locality region }
        prices {
          fuelProduct
          cash { price postedTime }
          credit { price postedTime }
        }
      }
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.gasbuddy.com",
    "Referer": "https://www.gasbuddy.com/home",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}


def _fresh(posted_time: str | None) -> bool:
    if not posted_time:
        return False
    try:
        posted = dt.datetime.fromisoformat(posted_time.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = dt.datetime.now(dt.timezone.utc) - posted
    return age <= dt.timedelta(hours=MAX_PRICE_AGE_HOURS)


def cheapest_regular(city: City) -> StationPrice:
    payload = {
        "operationName": "LocationBySearchTerm",
        "variables": {"fuel": FUEL_REGULAR, "maxAge": 0, "search": city.search},
        "query": QUERY,
    }
    try:
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceUnavailable(f"gasbuddy: {exc}") from exc

    stations = (
        (data.get("data") or {})
        .get("locationBySearchTerm", {})
        .get("stations", {})
        .get("results", [])
    )
    best: StationPrice | None = None
    for st in stations:
        for price_entry in st.get("prices", []):
            for pay_type in ("cash", "credit"):
                p = price_entry.get(pay_type) or {}
                price = p.get("price")
                if not price or not _fresh(p.get("postedTime")):
                    continue
                addr = st.get("address") or {}
                candidate = StationPrice(
                    station=st.get("name", "Unknown"),
                    address=addr.get("line1", ""),
                    price=float(price),
                    source="gasbuddy",
                    maps_url=(
                        "https://www.google.com/maps/search/?api=1&query="
                        + requests.utils.quote(
                            f"{st.get('name', '')} {addr.get('line1', '')} "
                            f"{addr.get('locality', '')} {addr.get('region', '')}"
                        )
                    ),
                )
                if best is None or candidate.price < best.price:
                    best = candidate
    if best is None:
        raise SourceUnavailable(f"gasbuddy: no fresh regular prices for {city.name}")
    return best
