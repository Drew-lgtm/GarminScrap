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
