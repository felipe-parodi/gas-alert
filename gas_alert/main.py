"""Entry point: fetch cheapest Regular (87) per city, send email + SMS.

Usage:
  python -m gas_alert.main            # fetch and send
  python -m gas_alert.main --dry-run  # fetch and print, send nothing
  python -m gas_alert.main --demo     # print message formats with fake data
"""

import argparse
import datetime as dt
import sys

from .config import (
    PRICE_TIE_USD,
    Anchor,
    City,
    load_anchors,
    load_cities,
    load_excluded_stations,
    settings_from_env,
)
from .notify import PACIFIC, email_body, send_all, sms_text
from .sources import AnchorPick, SourceUnavailable, StationPrice, distance_km
from .sources import gasbuddy, google_places


def fetch_city(
    city: City, index: int, google_key: str | None, excluded: list[str],
    verbose: bool,
) -> StationPrice | None:
    """Try sources in order of preference; None if all fail for this city.

    CI logs are public (public repo), so progress lines identify cities only
    by index unless verbose (local --dry-run) is on.
    """
    label = city.name if verbose else f"city {index + 1}"
    try:
        return gasbuddy.cheapest_regular(city, excluded)
    except SourceUnavailable as exc:
        print(f"{label}: {exc if verbose else 'gasbuddy unavailable'}")
    try:
        return google_places.cheapest_regular(city, google_key, excluded)
    except SourceUnavailable as exc:
        print(f"{label}: {exc if verbose else 'google_places unavailable'}")
    return None


def fetch_anchor(
    anchor: Anchor, index: int, google_key: str | None, excluded: list[str],
    verbose: bool,
) -> AnchorPick | None:
    """Cheapest fresh price near the anchor; among stations within
    PRICE_TIE_USD of that price, the nearest one wins."""
    label = anchor.label if verbose else f"anchor {index + 1}"
    try:
        found = google_places.regular_prices(
            anchor.lat, anchor.lng, anchor.radius_km * 1000, google_key, excluded
        )
    except SourceUnavailable as exc:
        print(f"{label}: {exc if verbose else 'google_places unavailable'}")
        return None
    located = [s for s in found if s.lat is not None and s.lng is not None]
    if not located:
        print(f"{label}: no fresh prices in radius")
        return None
    floor = min(s.price for s in located)
    ties = [s for s in located if s.price <= floor + PRICE_TIE_USD]
    best = min(ties, key=lambda s: distance_km(anchor.lat, anchor.lng, s.lat, s.lng))
    return AnchorPick(
        label=anchor.label,
        short=anchor.short,
        radius_km=anchor.radius_km,
        station=best,
        distance_km=distance_km(anchor.lat, anchor.lng, best.lat, best.lng),
    )


def demo_results(cities: list[City]) -> dict[str, StationPrice | None]:
    fake = [
        StationPrice("Chevron", "450 10th St", 4.39, "demo", 37.7706, -122.4098),
        StationPrice("Safeway", "3550 Broadway", 4.29, "demo", 37.8225, -122.2555),
        StationPrice("ARCO", "1201 San Pablo Ave", 4.45, "demo", 37.8814, -122.2963),
    ]
    return {city.name: fp for city, fp in zip(cities, fake)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch prices but print instead of sending")
    parser.add_argument("--demo", action="store_true",
                        help="print message formats using fake data; no network")
    args = parser.parse_args()

    today = dt.datetime.now(PACIFIC).date()
    cities = load_cities()

    if args.demo:
        results = demo_results(cities)
        picks: list[AnchorPick] = [
            AnchorPick("Home", "Home", 5.0,
                       StationPrice("Shell", "2801 Telegraph Ave", 4.35, "demo",
                                    37.8580, -122.2603), 1.2),
        ]
    else:
        settings = settings_from_env()
        excluded = load_excluded_stations()
        verbose = args.dry_run
        results = {
            city.name: fetch_city(city, i, settings.google_maps_api_key,
                                  excluded, verbose)
            for i, city in enumerate(cities)
        }
        picks = [
            p for i, anchor in enumerate(load_anchors())
            if (p := fetch_anchor(anchor, i, settings.google_maps_api_key,
                                  excluded, verbose)) is not None
        ]

    if args.demo or args.dry_run:
        # Full message dump is for local runs only — in CI these logs are
        # public and would reveal the configured cities.
        print("SMS:  " + sms_text(cities, results, today, anchor_picks=picks))
        print("Email:\n" + email_body(cities, results, today, anchor_picks=picks))
        return 0

    priced = sum(1 for r in results.values() if r is not None)
    print(f"priced {priced}/{len(cities)} cities, {len(picks)} anchors")

    if all(r is None for r in results.values()) and not picks:
        print("ERROR: no prices from any source; not sending")
        return 1

    sent = send_all(settings, cities, results, today, anchor_picks=picks)
    print(f"Sent via: {', '.join(sent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
