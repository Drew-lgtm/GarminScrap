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

Goal: daily unattended scrape → R2. The workflow already exists
(`.github/workflows/scrape.yml`, `--days 7 --full`); this is mostly wiring.

Steps:
- Add repo secrets: `GARMIN_TOKEN_B64` (from `tokens/token_b64.txt`), `R2_ACCOUNT_ID`,
  `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`; later the mail creds (item 1)
  and an LLM key (item 3).
- Enable Actions; test via `workflow_dispatch`; confirm objects land in R2.
- Pick cron time (UTC) + scrape window.

Watch out — **token write-back**: the DI token auto-refreshes in-process, but the
refreshed token is NOT saved back to the secret. If the refresh token expires/rotates, CI
login breaks. Plan: rely on item 1 (auto re-auth) to recover, and/or persist the
refreshed token (write back to R2 or update the secret via the GitHub API).

## 3. Automated AI report

Goal: generate the analysis from `analysis/INSTRUCTIONS.md` automatically each run instead
of feeding data to an AI by hand.

Notes:
- A year of raw JSON is far too big for any model context (and free-tier limits) — the
  report step must **aggregate to daily/weekly summaries first**, then send those.
- `analyze.py` already has a Claude path (paid). Add a selectable **Gemini** backend
  (`google-generativeai`) for a free option, chosen via env (e.g. `LLM_BACKEND`).
- Gemini caveat: a consumer **Gemini Advanced/Pro subscription does NOT grant API
  access**. Get a free **Gemini API key from Google AI Studio** (aistudio.google.com); its
  free tier (Flash models) is generous and fits this use. Store the key as a secret.
