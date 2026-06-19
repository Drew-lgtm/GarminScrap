"""Garmin Connect authentication.

Normal runs reuse a saved OAuth token (no password, no MFA). The one-time
`interactive_login` handles credentials + MFA and saves the token.
"""
import base64
import os
import sys
import time
from pathlib import Path

from garminconnect import Garmin

from . import config, gmail_mfa


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

    Uses the GARMIN_TOKEN_B64 env var (base64 token, used in CI) if present,
    otherwise the local token directory. The token auto-refreshes in process.
    Run `login` first if no token exists yet.
    """
    garmin = Garmin()
    token_b64 = os.environ.get("GARMIN_TOKEN_B64")
    if token_b64:
        # CI: secret holds base64 of the token JSON; decode and load it directly.
        garmin.login(base64.b64decode(token_b64).decode())
    else:
        garmin.login(config.TOKEN_DIR)
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
