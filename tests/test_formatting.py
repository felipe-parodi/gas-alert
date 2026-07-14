import datetime as dt

from gas_alert.config import DEFAULT_EXCLUDE_STATIONS, City
from gas_alert.notify import email_body, email_html, maps_links, sms_text
from gas_alert.sources import StationPrice, is_excluded

TODAY = dt.date(2026, 7, 12)

CITIES = [
    City("San Francisco", "SF", "San Francisco, CA", 37.7749, -122.4194),
    City("Oakland", "Oak", "Oakland, CA", 37.8044, -122.2712),
    City("Berkeley", "Berk", "Berkeley, CA", 37.8715, -122.2730),
]

RESULTS = {
    "San Francisco": StationPrice(
        "Chevron", "450 10th St", 4.39, "gasbuddy", 37.7706, -122.4098
    ),
    "Oakland": StationPrice(
        "Safeway", "3550 Broadway", 4.29, "google_places", 37.8225, -122.2555
    ),
    "Berkeley": None,
}


def test_sms_one_line_per_city_with_link():
    assert sms_text(CITIES, RESULTS, TODAY) == (
        "Gas 7/12\n"
        "SF $4.39 Chevron 10th\n"
        "https://maps.apple.com/?ll=37.770600,-122.409800&q=Chevron\n"
        "Oak $4.29 Safeway Broadway\n"
        "https://maps.apple.com/?ll=37.822500,-122.255500&q=Safeway\n"
        "Berk: n/a"
    )


def test_sms_maps_app_selectable():
    text = sms_text(CITIES, RESULTS, TODAY, maps_app="waze")
    assert "https://waze.com/ul?ll=37.770600,-122.409800&navigate=yes" in text


def test_sms_is_ascii_only():
    text = sms_text(CITIES, RESULTS, TODAY)
    assert text.isascii(), "carrier gateways mangle non-ASCII"


def test_short_label_strips_number_and_suffix():
    sp = StationPrice("ARCO", "1201 San Pablo Ave", 4.45, "x", "")
    assert sp.short_label == "ARCO San Pablo"


def test_email_includes_address_and_all_app_links():
    body = email_body(CITIES, RESULTS, TODAY)
    assert "$4.39 — Chevron" in body
    assert "450 10th St" in body
    assert "https://www.google.com/maps/search/?api=1&query=37.770600,-122.409800" in body
    assert "https://maps.apple.com/?ll=37.770600,-122.409800&q=Chevron" in body
    assert "https://waze.com/ul?ll=37.770600,-122.409800&navigate=yes" in body
    assert "Berkeley: no price available today" in body


def test_email_html_has_anchors():
    page = email_html(CITIES, RESULTS, TODAY)
    assert '<a href="https://maps.apple.com/?ll=37.770600,-122.409800&q=Chevron">' in page
    assert "no price available today" in page


def test_links_fall_back_to_address_query_without_coords():
    sp = StationPrice("Shell", "1 Main St, Oakland, CA", 4.50, "gasbuddy")
    links = maps_links(sp)
    assert links["apple"] == "https://maps.apple.com/?q=Shell%201%20Main%20St%2C%20Oakland%2C%20CA"


def test_membership_stations_excluded():
    for name in ["Costco Gasoline", "BJ's Gas", "Sam's Club Fuel Center"]:
        assert is_excluded(name, DEFAULT_EXCLUDE_STATIONS)
    for name in ["Chevron", "Safeway Fuel Station", "ARCO"]:
        assert not is_excluded(name, DEFAULT_EXCLUDE_STATIONS)
