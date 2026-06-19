"""Read the Garmin verification code from Gmail via the Gmail API (read-only).

Used as the `prompt_mfa` callback during login: after login triggers the code
email, this polls Gmail for a Garmin message newer than the login start and
returns the 6-digit code. Configured via GMAIL_* env vars; if unset, login
falls back to manual entry.
"""
import base64
import logging
import re
import time

from . import config

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")  # a standalone 6-digit code


def configured():
    return all([config.GMAIL_CLIENT_ID, config.GMAIL_CLIENT_SECRET,
                config.GMAIL_REFRESH_TOKEN])


def extract_code(text):
    m = CODE_RE.search(text or "")
    return m.group(1) if m else None


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=config.GMAIL_REFRESH_TOKEN,
        client_id=config.GMAIL_CLIENT_ID,
        client_secret=config.GMAIL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _message_text(svc, msg_id):
    """Return (internalDate_ms, combined subject+snippet+body text) for a message."""
    msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
    internal = int(msg.get("internalDate", "0"))
    chunks = [msg.get("snippet", "")]
    payload = msg.get("payload", {})
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == "subject":
            chunks.append(h.get("value", ""))

    def walk(part):
        data = part.get("body", {}).get("data")
        if data:
            try:
                chunks.append(base64.urlsafe_b64decode(data).decode("utf-8", "ignore"))
            except Exception:
                pass
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return internal, "\n".join(chunks)


def get_code(after_epoch_s, timeout=None, poll=5):
    """Poll Gmail for a Garmin OTP newer than after_epoch_s; return the 6-digit code.

    Raises SystemExit on timeout so login fails with a clear message.
    """
    timeout = timeout or config.GMAIL_OTP_TIMEOUT
    after_ms = int((after_epoch_s - 30) * 1000)  # small buffer for clock skew
    svc = _service()
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = svc.users().messages().list(
            userId="me", q=config.GMAIL_OTP_QUERY, maxResults=5).execute()
        best = None  # (internalDate_ms, code) of the newest matching message
        for m in resp.get("messages", []) or []:
            internal, text = _message_text(svc, m["id"])
            if internal < after_ms:
                continue
            code = extract_code(text)
            if code and (best is None or internal > best[0]):
                best = (internal, code)
        if best:
            log.info("got Garmin verification code from Gmail")
            return best[1]
        time.sleep(poll)
    raise SystemExit("Timed out waiting for the Garmin code email in Gmail.")
