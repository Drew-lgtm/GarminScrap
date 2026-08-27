"""Generate an MD-style wellness report from a data window and email it.

Uses Google Gemini (free tier) for the analysis and Gmail SMTP to send. The
report is descriptive only — no diagnoses, prescriptions, or treatment.
"""
import logging
import time
from pathlib import Path

from . import aggregate, config
from .storage import get_reader

log = logging.getLogger(__name__)

# Backoff (seconds) for Gemini "high demand" 503s — these are transient on
# Google's side; the SDK's own built-in retries give up too quickly for that.
_RETRY_DELAYS = [30, 90, 180]

MD_SYSTEM = """You are an experienced endurance & strength coach with a preventive-health \
background, reviewing a person's own Garmin data. Be direct, practical, and concise.

Start with a **TL;DR** — 2-4 sentences in plain language, leading with what matters most:
the bottom line on training load (too much / too little / about right), sleep (getting
enough or running a deficit), recovery (fresh / strained), and any notable weight change —
then ONE clear recommendation for the coming week (e.g. "go to bed earlier", "you're fresh,
fine to train hard", "ease off and take it easier this week"). Make it punchy and useful.

Then the detail sections (markdown headings):
1. Sleep
2. Recovery & stress (HRV, resting HR, body battery, stress)
3. Activity & training load
4. Recovery-vs-load balance
5. Weight & body composition (only if weight data is present)
6. Anomalies & data gaps
7. Focus for next week

Rules:
- Section 7 ("Focus for next week") is the payoff section — 2-4 bullets, each one a
  specific, prioritized, actionable focus point tied to a concrete number from the data
  (e.g. "Sleep: you were under 6.5h on 3/7 nights — protect a 7.5h window, especially the
  night after a hard session"; "Training: acute load rose from X to Y — a short/easy day
  would let it settle before it climbs further"; "Recovery: Body Battery ended net-negative
  on N/M days — that's the one to watch, not readiness"). Order by what matters most this
  week. Skip a point if nothing in that area needs attention — don't pad with filler.
- A COMPUTED WEEKLY STATS block is provided alongside the daily rows — it is ground truth.
  Base every weekly-level claim (averages, counts, net balances, "consistently"/"always"/
  "every day" style generalizations) on those precomputed numbers exactly. Do not eyeball
  or re-derive weekly aggregates yourself from the daily rows — that's how wrong claims like
  "consistently drained more than charged" slip in when the data doesn't actually show that.
- Quantify with real numbers from the data; never invent values.
- Weight: people don't weigh in every day (travel, no scale, etc.) — sparse weight_readings
  is completely normal, NOT a data quality problem. Never flag missing weight days as an
  anomaly and never recommend weighing in more consistently. Just report the trend from
  whatever readings exist (weight_delta_kg if available); skip the section entirely if
  fewer than 2 readings exist. Missing weight is not an "anomaly" for section 6 either.
- For other datasets, note genuinely missing days if it affects confidence in a claim.
- Give direct, actionable guidance like a coach. Do NOT diagnose medical conditions or
  prescribe medication; if something looks genuinely off, say so plainly and suggest it's
  worth getting checked — but WITHOUT any legal/medical disclaimer.
- Do NOT add a closing reminder or boilerplate. End after the last section.
"""


def _gemini(prompt):
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=MD_SYSTEM, max_output_tokens=4000),
            )
            return resp.text
        except errors.ServerError:
            if attempt == len(_RETRY_DELAYS):
                raise
            delay = _RETRY_DELAYS[attempt]
            log.warning("Gemini server error (attempt %d/%d), retrying in %ds",
                        attempt + 1, len(_RETRY_DELAYS) + 1, delay)
            time.sleep(delay)


def _send_email(subject, body, to):
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        s.send_message(msg)


def run(start, end, source=None, email=True):
    if not config.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY not set.")

    reader = get_reader(source or config.REPORT_SOURCE)
    summary = aggregate.load_window(reader, start, end)
    if not summary["days"]:
        raise SystemExit(f"No data found for {start}..{end} (source={source or config.REPORT_SOURCE}).")

    prompt = (f"Here is my Garmin data for {start} to {end}.\n\n"
              f"{aggregate.to_digest_text(summary)}\n\n"
              "Write the report per your instructions.")
    report_md = _gemini(prompt)

    out = Path(config.DATA_DIR) / f"report-{start}_{end}.md"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report_md, encoding="utf-8")
    except Exception:
        pass

    if email:
        if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
            raise SystemExit("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set for emailing.")
        to = config.REPORT_TO or config.GMAIL_ADDRESS
        _send_email(f"Garmin health report {start} to {end}", report_md, to)
        log.info("emailed report to %s", to)
    return report_md
