"""Message formatting and delivery: Gmail SMTP (email + SMS gateway), ntfy."""

import datetime as dt
import smtplib
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests

from .config import City, Settings
from .sources import StationPrice

PACIFIC = ZoneInfo("America/Los_Angeles")


def sms_text(
    cities: list[City], results: dict[str, StationPrice | None], today: dt.date
) -> str:
    """Short one-liner, e.g.
    Gas 7/12 — SF: $4.39 Costco 10th | Oak: $4.29 Safeway Broadway
    """
    parts = []
    for city in cities:
        r = results.get(city.name)
        if r is None:
            parts.append(f"{city.short}: n/a")
        else:
            parts.append(f"{city.short}: ${r.price:.2f} {r.short_label}")
    return f"Gas {today.month}/{today.day} — " + " | ".join(parts)


def email_body(
    cities: list[City], results: dict[str, StationPrice | None], today: dt.date
) -> str:
    lines = [f"Cheapest Regular (87) for {today.strftime('%A, %B %-d, %Y')}:", ""]
    for city in cities:
        r = results.get(city.name)
        if r is None:
            lines.append(f"{city.name}: no price available today")
        else:
            lines.append(f"{city.name}: ${r.price:.2f} — {r.station}")
            lines.append(f"  {r.address}")
            if r.maps_url:
                lines.append(f"  {r.maps_url}")
            lines.append(f"  (source: {r.source})")
        lines.append("")
    return "\n".join(lines)


def _send_via_gmail(settings: Settings, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.gmail_address
    msg["To"] = to
    if subject:
        msg["Subject"] = subject
    msg.set_content(body)
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
    short = sms_text(cities, results, today)
    sent: list[str] = []
    errors: list[str] = []

    try:
        _send_via_gmail(
            settings, settings.email_to, short, email_body(cities, results, today)
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
