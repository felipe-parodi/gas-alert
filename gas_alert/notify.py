"""Message formatting and delivery: Gmail SMTP (email + SMS gateway), ntfy."""

import datetime as dt
import html
import smtplib
from email.message import EmailMessage
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from .config import City, Settings
from .sources import StationPrice

PACIFIC = ZoneInfo("America/Los_Angeles")


def maps_links(sp: StationPrice) -> dict[str, str]:
    """One link per maps app. No URL opens 'whichever app you prefer' —
    each domain is claimed by one app — so we generate all of them."""
    if sp.lat is not None and sp.lng is not None:
        ll = f"{sp.lat:.6f},{sp.lng:.6f}"
        return {
            "google": f"https://www.google.com/maps/search/?api=1&query={ll}",
            "apple": f"https://maps.apple.com/?ll={ll}&q={quote(sp.station)}",
            "waze": f"https://waze.com/ul?ll={ll}&navigate=yes",
        }
    q = quote(f"{sp.station} {sp.address}")
    return {
        "google": f"https://www.google.com/maps/search/?api=1&query={q}",
        "apple": f"https://maps.apple.com/?q={q}",
        "waze": f"https://waze.com/ul?q={q}",
    }


def sms_text(
    cities: list[City],
    results: dict[str, StationPrice | None],
    today: dt.date,
    maps_app: str = "apple",
) -> str:
    """One line per city with a tappable map link. ASCII only — carrier
    gateways mangle anything fancier (em dashes get eaten).

    Gas 7/12
    SF $4.39 Chevron 10th
    https://maps.apple.com/?ll=...
    """
    lines = [f"Gas {today.month}/{today.day}"]
    for city in cities:
        r = results.get(city.name)
        if r is None:
            lines.append(f"{city.short}: n/a")
        else:
            lines.append(f"{city.short} ${r.price:.2f} {r.short_label}")
            lines.append(maps_links(r)[maps_app])
    return "\n".join(lines)


def email_body(
    cities: list[City], results: dict[str, StationPrice | None], today: dt.date
) -> str:
    lines = [f"Cheapest Regular (87) for {today.strftime('%A, %B %-d, %Y')}:", ""]
    for city in cities:
        r = results.get(city.name)
        if r is None:
            lines.append(f"{city.name}: no price available today")
        else:
            links = maps_links(r)
            lines.append(f"{city.name}: ${r.price:.2f} — {r.station}")
            lines.append(f"  {r.address}")
            lines.append(f"  Google Maps: {links['google']}")
            lines.append(f"  Apple Maps:  {links['apple']}")
            lines.append(f"  Waze:        {links['waze']}")
            lines.append(f"  (source: {r.source})")
        lines.append("")
    return "\n".join(lines)


def email_html(
    cities: list[City], results: dict[str, StationPrice | None], today: dt.date
) -> str:
    """HTML alternative so the links are real anchors — some mail clients
    don't auto-link URLs in plain text."""
    rows = [f"<h3>Cheapest Regular (87) for {today.strftime('%A, %B %-d, %Y')}</h3>"]
    for city in cities:
        r = results.get(city.name)
        if r is None:
            rows.append(f"<p><b>{html.escape(city.name)}</b>: no price available today</p>")
            continue
        links = maps_links(r)
        anchors = " | ".join(
            f'<a href="{links[app]}">{label}</a>'
            for app, label in [("google", "Google Maps"), ("apple", "Apple Maps"),
                               ("waze", "Waze")]
        )
        rows.append(
            f"<p><b>{html.escape(city.name)}</b>: ${r.price:.2f} — "
            f"{html.escape(r.station)}<br>"
            f"{html.escape(r.address)}<br>"
            f"{anchors}</p>"
        )
    return "\n".join(rows)


def _send_via_gmail(
    settings: Settings, to: str, subject: str, body: str, html_body: str | None = None
) -> None:
    msg = EmailMessage()
    msg["From"] = settings.gmail_address
    msg["To"] = to
    if subject:
        msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.send_message(msg)


def send_all(
    settings: Settings,
    cities: list[City],
    results: dict[str, StationPrice | None],
    today: dt.date,
) -> list[str]:
    """Send email, SMS, and ntfy as configured. Returns channels that succeeded.

    Channels fail independently — a dead SMS gateway must not kill the email.
    """
    short = sms_text(cities, results, today, settings.maps_app)
    sent: list[str] = []
    errors: list[str] = []

    subject = f"Gas {today.month}/{today.day}: " + " | ".join(
        f"{c.short} ${results[c.name].price:.2f}" if results.get(c.name) else
        f"{c.short} n/a"
        for c in cities
    )
    try:
        _send_via_gmail(
            settings,
            settings.email_to,
            subject,
            email_body(cities, results, today),
            email_html(cities, results, today),
        )
        sent.append("email")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"email: {exc}")

    if settings.sms_to:
        try:
            # No subject: gateways render subject + body awkwardly; body alone
            # arrives as a clean single text.
            _send_via_gmail(settings, settings.sms_to, "", short)
            sent.append("sms")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"sms: {exc}")

    if settings.ntfy_topic:
        try:
            requests.post(
                f"https://ntfy.sh/{settings.ntfy_topic}",
                data=short.encode(),
                headers={"Title": "Daily gas prices"},
                timeout=30,
            ).raise_for_status()
            sent.append("ntfy")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ntfy: {exc}")

    for err in errors:
        print(f"WARNING: delivery failed — {err}")
    if not sent:
        raise RuntimeError(f"all delivery channels failed: {errors}")
    return sent
