"""Settings, all read from the environment (.env locally, secrets in CI)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Garmin credentials — only needed for the one-time interactive login.
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")
GARMIN_IS_CN = os.getenv("GARMIN_IS_CN", "false").lower() == "true"

# Local paths.
TOKEN_DIR = os.getenv("GARMINTOKENS", str(Path.cwd() / "tokens"))

# If set, the Garmin token lives in R2 at this key and is refreshed in place
# each run (keeps the sliding-window refresh token alive for unattended CI).
GARMIN_TOKEN_R2_KEY = os.getenv("GARMIN_TOKEN_R2_KEY")
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path.cwd() / "data")))

# Storage: "local" (default) or "r2".
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

# Cloudflare R2 (S3-compatible).
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")
R2_PREFIX = os.getenv("R2_PREFIX", "garmin")

# Optional AI report.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

# Gmail API (read-only) for automated MFA. If unset, login prompts for the code.
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GMAIL_OTP_QUERY = os.getenv("GMAIL_OTP_QUERY", "from:garmin newer_than:1d")
GMAIL_OTP_TIMEOUT = int(os.getenv("GMAIL_OTP_TIMEOUT", "120"))

# Weekly AI health report: Gemini (free tier) + Gmail SMTP email.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")            # SMTP sender
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # Gmail app password (not read-only OAuth)
REPORT_TO = os.getenv("REPORT_TO")                    # recipient (default: GMAIL_ADDRESS)
REPORT_SOURCE = os.getenv("REPORT_SOURCE", STORAGE_BACKEND)  # read data from local|r2
