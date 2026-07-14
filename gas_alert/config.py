"""Cities to check and environment-driven settings."""

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    name: str  # full name for email
    short: str  # short label for SMS
    search: str  # search term for data sources
    lat: float
    lng: float


# Demo/default cities. Set the real ones privately via the CITIES_JSON env var
# (a secret in CI) so they never appear in the repo:
#   CITIES_JSON='[{"name":"San Francisco","short":"SF","search":"San Francisco, CA","lat":37.7749,"lng":-122.4194}, ...]'
DEFAULT_CITIES = [
    City("San Francisco", "SF", "San Francisco, CA", 37.7749, -122.4194),
    City("Oakland", "Oak", "Oakland, CA", 37.8044, -122.2712),
    City("Berkeley", "Berk", "Berkeley, CA", 37.8715, -122.2730),
]


def load_cities() -> list[City]:
    raw = os.environ.get("CITIES_JSON")
    if not raw:
        return DEFAULT_CITIES
    return [City(**entry) for entry in json.loads(raw)]

# Ignore prices older than this — a 3-day-old crowd-sourced price is noise.
MAX_PRICE_AGE_HOURS = 48

# Stations that require a membership to pump (matched case-insensitively as
# substrings of the station name). Override with EXCLUDE_STATIONS, comma-sep.
DEFAULT_EXCLUDE_STATIONS = ["costco", "bj's", "bjs", "sam's club", "sams club"]


def load_excluded_stations() -> list[str]:
    raw = os.environ.get("EXCLUDE_STATIONS")
    if raw is None:
        return DEFAULT_EXCLUDE_STATIONS
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    gmail_address: str
    gmail_app_password: str
    email_to: str
    sms_to: str | None  # e.g. 4085551234@tmomail.net
    ntfy_topic: str | None  # optional ntfy.sh fallback channel
    google_maps_api_key: str | None
    maps_app: str  # which app the SMS link opens: apple | google | waze


def settings_from_env() -> Settings:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    maps_app = (os.environ.get("MAPS_APP") or "apple").lower()
    if maps_app not in ("apple", "google", "waze"):
        raise ValueError(f"MAPS_APP must be apple, google, or waze, not {maps_app!r}")
    return Settings(
        gmail_address=gmail_address,
        gmail_app_password=os.environ["GMAIL_APP_PASSWORD"],
        email_to=os.environ.get("EMAIL_TO") or gmail_address,
        sms_to=os.environ.get("SMS_TO") or None,
        ntfy_topic=os.environ.get("NTFY_TOPIC") or None,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY") or None,
        maps_app=maps_app,
    )
