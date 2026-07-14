"""Garmin Connect authentication.

Normal runs reuse a saved OAuth token (no password, no MFA). The one-time
`interactive_login` handles credentials + MFA and saves the token.
"""
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

from garminconnect import Garmin

from . import config, gmail_mfa

log = logging.getLogger(__name__)


def _mfa_prompt():
    """Ask for the verification code Garmin sends (often by email).

    Fails fast when there's no interactive terminal instead of hanging on input.
    """
    if not sys.stdin or not sys.stdin.isatty():
        raise SystemExit(
            "Garmin asked for a verification code, but this isn't an interactive "
            "terminal. Run `python -m garminscrap.cli login` directly in your own "
            "terminal and paste the code Garmin emails you."
        )
    return input("Enter the Garmin verification code (check your email/app): ")


def get_client():
    """Return an authenticated Garmin client from a saved token.

    Token source, in priority order:
    1. R2 token store (GARMIN_TOKEN_R2_KEY) — read, log in, then write the
       refreshed token back so its sliding-window refresh token never goes
       stale. This is what keeps unattended CI runs working long-term.
    2. GARMIN_TOKEN_B64 env var (legacy; can't be refreshed back).
    3. Local token directory (also written back to stay fresh).
    Run `login` first if no token exists yet.
    """
    garmin = Garmin()

    if config.GARMIN_TOKEN_R2_KEY:
        from .storage import R2Storage
        store = R2Storage()
        tok = store.read_json(config.GARMIN_TOKEN_R2_KEY)
        if not tok:
            raise SystemExit(
                f"No Garmin token in R2 at '{config.GARMIN_TOKEN_R2_KEY}'. "
                "Bootstrap it once with `push-token` after a local `login`.")
        garmin.login(json.dumps(tok))
        # Persist the refreshed/rotated token so the window keeps sliding.
        try:
            store.write_json(config.GARMIN_TOKEN_R2_KEY, json.loads(garmin.client.dumps()))
        except Exception as e:
            log.warning("could not write refreshed token back to R2: %s", e)
        return garmin

    token_b64 = os.environ.get("GARMIN_TOKEN_B64")
    if token_b64:
        garmin.login(base64.b64decode(token_b64).decode())
        return garmin

    garmin.login(config.TOKEN_DIR)
    try:  # keep the local token fresh across runs
        garmin.client.dump(str(config.TOKEN_DIR))
    except Exception:
        pass
    return garmin


def interactive_login(skip_mobile=False):
    """Log in with credentials + MFA, save the token, return (client, base64).

    The base64 string can be pasted into the GARMIN_TOKEN_B64 GitHub secret.
    When skip_mobile is True, the rate-limited mobile strategies are skipped so
    login goes straight to the widget code prompt — useful when the mobile path
    is stuck on 429 and the emailed code keeps expiring during the delay.
    """
    if not config.GARMIN_EMAIL or not config.GARMIN_PASSWORD:
        raise SystemExit("Set GARMIN_EMAIL and GARMIN_PASSWORD in your .env first.")

    # If Gmail is configured, read the code automatically; else prompt for it.
    if gmail_mfa.configured():
        login_start = time.time()
        prompt = lambda: gmail_mfa.get_code(login_start)
    else:
        prompt = _mfa_prompt

    garmin = Garmin(
        email=config.GARMIN_EMAIL,
        password=config.GARMIN_PASSWORD,
        is_cn=config.GARMIN_IS_CN,
        prompt_mfa=prompt,
    )
    if skip_mobile:
        garmin.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
    garmin.login()

    token_dir = Path(config.TOKEN_DIR)
    token_dir.mkdir(parents=True, exist_ok=True)
    garmin.client.dump(str(token_dir))
    token_b64 = base64.b64encode(garmin.client.dumps().encode()).decode()
    (token_dir / "token_b64.txt").write_text(token_b64, encoding="utf-8")
    return garmin, token_b64
