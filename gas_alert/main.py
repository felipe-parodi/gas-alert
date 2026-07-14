"""Entry point: fetch cheapest Regular (87) per city, send email + SMS.

Usage:
  python -m gas_alert.main            # fetch and send
  python -m gas_alert.main --dry-run  # fetch and print, send nothing
  python -m gas_alert.main --demo     # print message formats with fake data
"""

import argparse
import datetime as dt
import sys

from .config import City, load_cities, settings_from_env
from .notify import PACIFIC, email_body, send_all, sms_text
from .sources import SourceUnavailable, StationPrice
from .sources import gasbuddy, google_places


def fetch_city(city: City, google_key: str | None) -> StationPrice | None:
    """Try sources in order of preference; None if all fail for this city."""
    try:
        return gasbuddy.cheapest_regular(city)
    except SourceUnavailable as exc:
        print(f"{city.name}: {exc}")
    try:
        return google_places.cheapest_regular(city, google_key)
    except SourceUnavailable as exc:
        print(f"{city.name}: {exc}")
    return None


def demo_results(cities: list[City]) -> dict[str, StationPrice | None]:
    fake = [
        StationPrice("Costco", "450 10th St", 4.39, "demo",
                     "https://maps.google.com/?q=demo"),
        StationPrice("Safeway", "3550 Broadway", 4.29, "demo",
                     "https://maps.google.com/?q=demo"),
        StationPrice("ARCO", "1201 San Pablo Ave", 4.45, "demo",
                     "https://maps.google.com/?q=demo"),
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
    else:
        settings = settings_from_env()
        results = {
            city.name: fetch_city(city, settings.google_maps_api_key)
            for city in cities
        }

    print("SMS:  " + sms_text(cities, results, today))
    print("Email:\n" + email_body(cities, results, today))

    if args.demo or args.dry_run:
        return 0

    if all(r is None for r in results.values()):
        print("ERROR: no prices from any source for any city; not sending")
        return 1

    sent = send_all(settings, cities, results, today)
    print(f"Sent via: {', '.join(sent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
