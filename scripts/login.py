"""One-time interactive Garmin login.

Run locally once. Saves the OAuth token to the token dir (gitignored). The
base64 blob for the GitHub Actions GARMIN_TOKEN_B64 secret is written to
<token dir>/token_b64.txt. Needs GARMIN_EMAIL and GARMIN_PASSWORD in your .env.

    python scripts/login.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garminscrap import auth, config  # noqa: E402


def main():
    auth.interactive_login()
    b64_path = Path(config.TOKEN_DIR) / "token_b64.txt"
    print(f"\nLogin OK. Token saved to: {config.TOKEN_DIR}")
    print(f"GARMIN_TOKEN_B64 (for GitHub Actions) saved to: {b64_path}")


if __name__ == "__main__":
    main()
