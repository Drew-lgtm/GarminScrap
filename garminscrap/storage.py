"""Storage backends. Scrape always writes locally; R2 is an optional mirror."""
import json
from pathlib import Path

from . import config


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


class LocalStorage:
    def __init__(self, base=None):
        self.base = Path(base or config.DATA_DIR)

    def write_json(self, key, obj):
        path = self.base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(obj), encoding="utf-8")

    def exists(self, key):
        return (self.base / key).exists()


class R2Storage:
    """Cloudflare R2 via the S3-compatible API (boto3)."""

    def __init__(self):
        import boto3
        from botocore.config import Config

        if not all([config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY_ID,
                    config.R2_SECRET_ACCESS_KEY, config.R2_BUCKET]):
            raise SystemExit("STORAGE_BACKEND=r2 but R2_* env vars are not all set.")

        self.bucket = config.R2_BUCKET
        self.prefix = config.R2_PREFIX
        # R2 needs checksum calc disabled (boto3 >= 1.36 sends headers R2 rejects).
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def _full(self, key):
        return f"{self.prefix}/{key}" if self.prefix else key

    def write_json(self, key, obj):
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self._full(key),
            Body=_dump(obj).encode("utf-8"),
            ContentType="application/json",
        )


def remote_storage():
    """Return an R2Storage if the backend is configured, else None."""
    return R2Storage() if config.STORAGE_BACKEND == "r2" else None
