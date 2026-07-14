import datetime as dt

from gas_alert.config import DEFAULT_EXCLUDE_STATIONS, City
from gas_alert.notify import email_body, sms_text
from gas_alert.sources import StationPrice, is_excluded

TODAY = dt.date(2026, 7, 12)

CITIES = [
    City("San Francisco", "SF", "San Francisco, CA", 37.7749, -122.4194),
    City("Oakland", "Oak", "Oakland, CA", 37.8044, -122.2712),
    City("Berkeley", "Berk", "Berkeley, CA", 37.8715, -122.2730),
]

RESULTS = {
    "San Francisco": StationPrice(
        "Chevron", "450 10th St", 4.39, "gasbuddy",
        "https://maps.google.com/?cid=111"
    ),
    "Oakland": StationPrice(
        "Safeway", "3550 Broadway", 4.29, "google_places",
        "https://maps.google.com/?cid=222"
    ),
    "Berkeley": None,
}


def test_sms_one_line_per_city_with_link():
    assert sms_text(CITIES, RESULTS, TODAY) == (
        "Gas 7/12\n"
        "SF $4.39 Chevron 10th\n"
        "https://maps.google.com/?cid=111\n"
        "Oak $4.29 Safeway Broadway\n"
        "https://maps.google.com/?cid=222\n"
        "Berk: n/a"
    )


def test_sms_is_ascii_only():
    text = sms_text(CITIES, RESULTS, TODAY)
    assert text.isascii(), "carrier gateways mangle non-ASCII"


def test_short_label_strips_number_and_suffix():
    sp = StationPrice("ARCO", "1201 San Pablo Ave", 4.45, "x", "")
    assert sp.short_label == "ARCO San Pablo"


def test_email_includes_address_and_link():
    body = email_body(CITIES, RESULTS, TODAY)
    assert "$4.39 — Chevron" in body
    assert "450 10th St" in body
    assert "https://maps.google.com/?cid=111" in body
    assert "Berkeley: no price available today" in body


def test_membership_stations_excluded():
    for name in ["Costco Gasoline", "BJ's Gas", "Sam's Club Fuel Center"]:
        assert is_excluded(name, DEFAULT_EXCLUDE_STATIONS)
    for name in ["Chevron", "Safeway Fuel Station", "ARCO"]:
        assert not is_excluded(name, DEFAULT_EXCLUDE_STATIONS)
