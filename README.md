# gas-alert

Every morning (6:15 AM Pacific), finds the cheapest **Regular (87)** station in
each of your configured cities and sends one email + one free SMS:

> ```
> Gas 7/12
> SF $4.39 Chevron 10th
> https://maps.google.com/?cid=...
> Oak $4.29 Safeway Broadway
> https://maps.google.com/?cid=...
> ```

Membership-only pumps (Costco, BJ's, Sam's Club) are skipped by default;
override with `EXCLUDE_STATIONS`.

All personal configuration — cities, email, phone — lives in environment
variables / GitHub Actions secrets, never in the repo.

The email carries the same info plus addresses and Google Maps links.

## How it works

```
GitHub Actions cron (6:15 AM PT)
  └─ python -m gas_alert.main
       ├─ per city: GasBuddy GraphQL → fallback: Google Places API (New)
       ├─ pick lowest fresh (≤48h) Regular price per city
       └─ send: Gmail SMTP → EMAIL_TO, SMS_TO (@tmomail.net), optional ntfy.sh
```

**Data sources** (tried in order per city):

1. **GasBuddy** (unofficial GraphQL) — best coverage, $0, no key. As of July
   2026 it is Cloudflare-blocked for non-browser clients, so expect this to
   fail from CI; it's kept first because it costs one request and may work
   again. (Costco's site is likewise Akamai-blocked, so the "scrape the usual
   cheap stations" fallback from the spec isn't viable either.)
2. **Google Places API (New)** — official, stable. Gas stations return
   `fuelOptions.fuelPrices` (the prices you see on Google Maps). ~3
   requests/day is far inside the free tier. Needs `GOOGLE_MAPS_API_KEY`.

If every source fails for every city, nothing is sent and the workflow fails
(GitHub emails you about failed runs). Partial data still sends, with `n/a`
for missing cities.

## Setup

1. **Gmail app password**: Google Account → Security → 2-Step Verification →
   App passwords. (Regular password won't work over SMTP.)
2. **Google Maps key**: Google Cloud console → enable **Places API (New)** →
   create an API key. Restrict it to that API.
3. **Repo secrets** (Settings → Secrets and variables → Actions):

   | Secret | Required | Example |
   |---|---|---|
   | `CITIES_JSON` | yes | see `.env.example` |
   | `GMAIL_ADDRESS` | yes | `you@gmail.com` |
   | `GMAIL_APP_PASSWORD` | yes | app password |
   | `EMAIL_TO` | no (defaults to sender) | `you@gmail.com` |
   | `SMS_TO` | no | `4085551234@tmomail.net` |
   | `NTFY_TOPIC` | no | `gas-alerts-x8f3k2q` |
   | `GOOGLE_MAPS_API_KEY` | effectively yes | see above |

4. Test it: Actions tab → **Daily gas alert** → *Run workflow*.

## Local development

```bash
uv sync
uv run pytest
uv run python -m gas_alert.main --demo     # message formats, fake data, no network
uv run python -m gas_alert.main --dry-run  # real fetch, prints, sends nothing
uv run python -m gas_alert.main            # real fetch + send (needs env vars)
```

## SMS reliability caveat

Carriers have been quietly killing email-to-SMS gateways. T-Mobile's
(`@tmomail.net`) still works for many people but can **silently drop**
messages. If texts get flaky, set `NTFY_TOPIC` and install the
[ntfy](https://ntfy.sh) app — free, more reliable — or just rely on email.

## Tuning

- Cities / labels: `CITIES_JSON` env var (see `.env.example`); defaults in
  `gas_alert/config.py`
- Skipped stations: `EXCLUDE_STATIONS` (repo variable; default:
  membership-only brands)
- SMS map-link app: `MAPS_APP` = `apple` | `google` | `waze` (repo variable;
  default apple; the email always carries all three links)
- Price freshness window: `MAX_PRICE_AGE_HOURS` (48h)
- Search radius for Places: `RADIUS_METERS` in `gas_alert/sources/google_places.py`
- Schedule: `.github/workflows/daily.yml` (dual cron + DST guard keeps it at
  6:15 AM Pacific year-round)
