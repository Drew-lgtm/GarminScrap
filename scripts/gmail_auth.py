"""One-time Gmail OAuth consent to mint a read-only refresh token.

Run locally once after creating an OAuth client in Google Cloud:

    python scripts/gmail_auth.py path/to/client_secret.json

Opens a browser for consent, then prints the three values to put in your .env:
GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN. Nothing is committed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garminscrap.gmail_mfa import SCOPES  # noqa: E402


def main():
    secrets = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    if not Path(secrets).is_file():
        sys.exit(f"client secret file not found: {secrets}")

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh token is returned.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        sys.exit("No refresh token returned. Re-run; ensure prompt=consent worked.")

    print("\nPaste these into your .env (and later GitHub secrets):\n")
    print(f"GMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
