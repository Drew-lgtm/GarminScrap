# Backlog

Prioritized follow-ups. The core is done (login, scraper, R2, tests, full-year local
pull). These make it fully autonomous and add the AI report.

## 1. Autonomous email-based authentication  (DONE — local)

Implemented via the **Gmail API (read-only)**: `garminscrap/gmail_mfa.py` polls Gmail
for the Garmin code (newer than login start) and feeds it to `prompt_mfa`; `auth.py`
uses it automatically when `GMAIL_*` env vars are set, else prompts. One-time setup is
`scripts/gmail_auth.py` (see README "Automated MFA").

Remaining: this makes the **local** `login` zero-touch. Fully autonomous **CI re-auth**
is still open — GitHub's cloud IPs get 429'd/Cloudflare-walled by Garmin even with the
code automated, so plan a self-hosted/fixed-IP runner or accept that the ~yearly re-auth
runs locally (now hands-off).

## 2. GitHub Actions automation

Goal: weekly unattended scrape → R2. Workflow is `.github/workflows/scrape.yml`:
runs **Mondays 04:30 UTC**, scrapes the **last ~10 days ending yesterday** (`--full`,
timezone `Europe/Prague`) into per-date R2 folders. `workflow_dispatch` takes an
optional `date` for manual single-day backfill.

Remaining (wiring):
- Add repo secrets: `GARMIN_TOKEN_B64` (from `tokens/token_b64.txt`), `R2_ACCOUNT_ID`,
  `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
- Test via `workflow_dispatch`; confirm objects land in R2.
- One-time: bulk-upload the existing local year to R2 (CI only adds new days going forward).

**Token write-back — DONE.** The token now lives in R2 (`_auth/token.json`, via
`GARMIN_TOKEN_R2_KEY`) and `get_client` writes the refreshed token back each run, so the
~2-week sliding-window refresh token keeps sliding forward. Re-auth is only needed if runs
lapse for >2 weeks: local `login`, then `push-token` to re-seed R2.

## 3. Automated AI report  (DONE)

Implemented: `aggregate.py` (window → compact digest), `report.py` (Gemini free tier
with a medical-advisor prompt → markdown → Gmail SMTP email), `cli report`, and the
weekly `.github/workflows/report.yml` (Mondays 05:30 UTC, reads R2, emails).

Remaining (wiring): free **Gemini API key** (Google AI Studio) + **Gmail app password**;
add secrets `GEMINI_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `REPORT_TO`.

Privacy note: Gemini's *free* tier may use prompts (health data) to improve models.
Possible future hardening: paid tier / Vertex, or a local model.
