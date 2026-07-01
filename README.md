# GarminScrap

Scrape your own Garmin Connect data to JSON for AI analysis. Runs locally, and
optionally on a free daily GitHub Actions schedule that uploads to Cloudflare R2.

> **This repo is public. No personal data lives here.** Credentials, OAuth
> tokens and scraped data are all gitignored (`.env`, `tokens/`, `data/`).

## How it works

- `python-garminconnect` talks to Garmin's (unofficial) API.
- You log in **once locally** (handles MFA). That saves an OAuth token which
  auto-refreshes for ~1 year, so automated runs never need your password or MFA.
- Data is written as JSON under `data/<date>/<dataset>.json`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in GARMIN_EMAIL / GARMIN_PASSWORD
```

## Usage

**1. Log in once** (prompts for your MFA code, saves the token):

```bash
python -m garminscrap.cli login
```

This also prints a `GARMIN_TOKEN_B64` blob — save it for GitHub Actions later.

If Garmin asks for an emailed verification code, you can enter it by hand, or set
up **automated MFA** (see below) so login is fully hands-off.

### Automated MFA (Gmail API, read-only)

If the Garmin code arrives in Gmail, the login can read it automatically:

1. In [Google Cloud Console](https://console.cloud.google.com): create a project,
   enable the **Gmail API**, configure the OAuth consent screen (External), and
   **publish it to "Production"** — otherwise the refresh token expires after 7 days.
2. Create an **OAuth client ID** of type *Desktop app*; download `client_secret.json`.
3. Mint a refresh token (opens a browser once):
   ```bash
   python scripts/gmail_auth.py client_secret.json
   ```
4. Put the printed `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN`
   in `.env`. Now `login` reads the code itself — no typing.

**2. Scrape:**

```bash
python -m garminscrap.cli scrape --days 30      # last 30 days
python -m garminscrap.cli scrape --date 2026-06-16
python -m garminscrap.cli scrape --start 2026-01-01 --end 2026-06-01
python -m garminscrap.cli scrape --days 365 --full   # everything (see below)
```

Already-fetched datasets are skipped (use `--force` to overwrite), so an
interrupted run resumes cleanly.

`--full` adds, on top of the 17 core daily datasets: per-day fitness age /
weigh-ins / hydration; whole-window performance metrics (race predictions,
endurance & hill scores, lactate threshold, running tolerance, cycling FTP,
personal records) under `data/period/`; and per-activity detail (splits, HR/power
zones, weather, gear) under `data/activities/detail/<id>/`.

**3. Analyze** — either feed a day's `data/<date>/*.json` plus
[`analysis/INSTRUCTIONS.md`](analysis/INSTRUCTIONS.md) to Claude yourself (free),
or generate a report automatically (needs `ANTHROPIC_API_KEY` in `.env`):

```bash
python -m garminscrap.cli analyze --start 2026-06-10 --end 2026-06-16
```

## AI health report (Gemini + email)

`report` aggregates a window into a compact digest, sends it to Google **Gemini**
(free tier) with a medical-advisor prompt (observations & trends only — no diagnoses),
and emails the result via Gmail SMTP:

```bash
python -m garminscrap.cli report --days 7                 # read local, email
python -m garminscrap.cli report --days 7 --source r2 --no-email   # from R2, print/save only
```

Setup: a free **Gemini API key** from [Google AI Studio](https://aistudio.google.com),
and a **Gmail app password** (needs 2-Step Verification) for sending. Put
`GEMINI_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `REPORT_TO` in `.env`.
Note: Gemini's *free* tier may use your data to improve their models — a privacy
tradeoff to weigh for health data.

## Automated runs (GitHub Actions → Cloudflare R2)

The workflow in [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml)
runs daily and uploads to R2. Add these repo **Secrets**:

| Secret | From |
| --- | --- |
| `GARMIN_TOKEN_B64` | the `login` command output |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Cloudflare R2 |
| `ANTHROPIC_API_KEY` | optional — enables the auto-report step |

Re-run `login` locally ~once a year when the token expires.

## Tests

Unit tests mock the Garmin API and Claude, so they run offline with no credentials:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Notes

- Unofficial API; Garmin may change it. Be gentle (the scraper already paces requests).
- Personal use on your own account only.
