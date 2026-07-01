"""Generate an MD-style wellness report from a data window and email it.

Uses Google Gemini (free tier) for the analysis and Gmail SMTP to send. The
report is descriptive only — no diagnoses, prescriptions, or treatment.
"""
import logging
from pathlib import Path

from . import aggregate, config
from .storage import get_reader

log = logging.getLogger(__name__)

MD_SYSTEM = """You are a preventive- and sports-medicine physician reviewing a person's own \
wearable (Garmin) data. Produce a clear, honest, useful report.

Hard rules:
- You are NOT the reader's doctor. Do NOT diagnose, prescribe, or give treatment plans.
- Describe observations, trends, and things worth discussing with a licensed physician.
- Quantify with real numbers from the data; never invent values. Note data gaps.
- Close with a plain reminder to confirm anything concerning with a licensed doctor.

Structure the report as markdown:
1. Snapshot (3-5 sentences)
2. Sleep
3. Recovery & stress (HRV, resting HR, body battery, stress)
4. Activity & training load
5. Recovery-vs-load balance
6. Anomalies & data gaps
7. Things to consider / discuss with a physician
"""


def _gemini(prompt):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=MD_SYSTEM, max_output_tokens=4000),
    )
    return resp.text


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
