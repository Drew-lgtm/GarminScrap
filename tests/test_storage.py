import json

from garminscrap import config
from garminscrap.storage import LocalStorage, R2Storage, remote_storage


def test_local_write_and_exists(tmp_path):
    s = LocalStorage(base=tmp_path)
    assert not s.exists("2026-06-16/sleep.json")
    s.write_json("2026-06-16/sleep.json", {"score": 88})
    assert s.exists("2026-06-16/sleep.json")
    loaded = json.loads((tmp_path / "2026-06-16" / "sleep.json").read_text(encoding="utf-8"))
    assert loaded == {"score": 88}


def test_remote_storage_none_for_local(monkeypatch):
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    assert remote_storage() is None


def _patch_r2(monkeypatch, fake_client):
    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake_client)
    monkeypatch.setattr(config, "R2_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "R2_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(config, "R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(config, "R2_BUCKET", "bucket")
    monkeypatch.setattr(config, "R2_PREFIX", "garmin")


def test_r2_put_object(monkeypatch):
    calls = {}

    class FakeS3:
        def put_object(self, **kw):
            calls.update(kw)

    _patch_r2(monkeypatch, FakeS3())
    R2Storage().write_json("2026-06-16/sleep.json", {"score": 88})

    assert calls["Bucket"] == "bucket"
    assert calls["Key"] == "garmin/2026-06-16/sleep.json"
    assert calls["ContentType"] == "application/json"
    assert json.loads(calls["Body"].decode("utf-8")) == {"score": 88}


def test_remote_storage_r2(monkeypatch):
    _patch_r2(monkeypatch, object())
    monkeypatch.setattr(config, "STORAGE_BACKEND", "r2")
    assert remote_storage() is not None
