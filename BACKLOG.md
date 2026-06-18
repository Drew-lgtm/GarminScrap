# Backlog

Prioritized follow-ups. The core is done (login, scraper, R2, tests, full-year local
pull). These make it fully autonomous and add the AI report.

## 1. Autonomous email-based authentication  (do first)

Goal: re-login with no human in the loop, so the whole pipeline can run unattended —
including the ~yearly token refresh in CI.

Why: Garmin's mobile login path needs no code, but when it's rate-limited (429) the flow
falls back to the web/widget path, which **emails a verification code**. Today that code
is typed by hand (`login` prompts for it).

Approach:
- After triggering login, read the inbox over **IMAP**, find the most recent Garmin
  verification email, extract the 6-digit code via regex, and feed it to the `prompt_mfa`
  callback — or use the library's `return_on_mfa=True` + `resume_login()` two-step for a
  clean non-interactive flow.
- Poll IMAP with short retry/backoff (the email lands a few seconds after login starts).
- Prefer the no-code mobile path first (retry/backoff); use email-code automation only as
  the fallback when the widget path is forced.

Open questions / inputs needed:
- Which inbox receives the Garmin code (IMAP host)? A read-only mail credential
  (e.g. a Gmail **app password**) stored as a secret — never in the repo.
- Confirm sender + code format so the regex is reliable.

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
