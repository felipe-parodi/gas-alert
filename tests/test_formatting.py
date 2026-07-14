import datetime as dt

from gas_alert.config import City
from gas_alert.notify import email_body, sms_text
from gas_alert.sources import StationPrice

TODAY = dt.date(2026, 7, 12)

CITIES = [
    City("San Francisco", "SF", "San Francisco, CA", 37.7749, -122.4194),
    City("Oakland", "Oak", "Oakland, CA", 37.8044, -122.2712),
    City("Berkeley", "Berk", "Berkeley, CA", 37.8715, -122.2730),
]

RESULTS = {
    "San Francisco": StationPrice(
        "Costco", "450 10th St", 4.39, "gasbuddy", "https://maps.example/1"
    ),
    "Oakland": StationPrice(
        "Safeway", "3550 Broadway", 4.29, "google_places", "https://maps.example/2"
    ),
    "Berkeley": None,
}


def test_sms_matches_spec_shape():
    text = sms_text(CITIES, RESULTS, TODAY)
    assert text == (
        "Gas 7/12 — SF: $4.39 Costco 10th"
        " | Oak: $4.29 Safeway Broadway"
        " | Berk: n/a"
    )


def test_sms_fits_in_one_segment_ballpark():
    assert len(sms_text(CITIES, RESULTS, TODAY)) < 160


def test_short_label_strips_number_and_suffix():
    sp = StationPrice("ARCO", "1201 San Pablo Ave", 4.45, "x", "")
    assert sp.short_label == "ARCO San Pablo"


def test_email_includes_address_and_link():
    body = email_body(CITIES, RESULTS, TODAY)
    assert "$4.39 — Costco" in body
    assert "450 10th St" in body
    assert "https://maps.example/1" in body
    assert "Berkeley: no price available today" in body
