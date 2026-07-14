import base64

import pytest

from garminscrap import auth, config

TOKEN_JSON = '{"di_token":"x","di_refresh_token":"y","di_client_id":"z"}'


class FakeInner:
    def __init__(self):
        self.dumped_to = None
        self.skip_strategies = set()

    def dump(self, path):
        self.dumped_to = path

    def dumps(self):
        return TOKEN_JSON


class FakeGarminClient:
    def __init__(self, *args, **kwargs):
        self.login_arg = "UNSET"
        self.client = FakeInner()

    def login(self, token=None):
        self.login_arg = token


def test_get_client_uses_token_dir(monkeypatch):
    created = {}
    monkeypatch.setattr(auth, "Garmin", lambda *a, **k: created.setdefault("c", FakeGarminClient()))
    monkeypatch.delenv("GARMIN_TOKEN_B64", raising=False)
    monkeypatch.setattr(config, "TOKEN_DIR", "tokens")
    auth.get_client()
    assert created["c"].login_arg == "tokens"


def test_get_client_prefers_b64_env(monkeypatch):
    created = {}
    monkeypatch.setattr(config, "GARMIN_TOKEN_R2_KEY", None)
    monkeypatch.setattr(auth, "Garmin", lambda *a, **k: created.setdefault("c", FakeGarminClient()))
    monkeypatch.setenv("GARMIN_TOKEN_B64", base64.b64encode(TOKEN_JSON.encode()).decode())
    auth.get_client()
    assert created["c"].login_arg == TOKEN_JSON  # decoded back to the token JSON


def test_get_client_r2_store_reads_and_writes_back(monkeypatch):
    import json
    monkeypatch.setattr(config, "GARMIN_TOKEN_R2_KEY", "_auth/token.json")
    stored = {"di_token": "a", "di_refresh_token": "b", "di_client_id": "c"}
    written = {}

    class FakeStore:
        def read_json(self, key): return stored
        def write_json(self, key, obj): written["key"], written["obj"] = key, obj

    monkeypatch.setattr("garminscrap.storage.R2Storage", lambda: FakeStore())
    created = {}
    monkeypatch.setattr(auth, "Garmin", lambda *a, **k: created.setdefault("c", FakeGarminClient()))

    auth.get_client()
    assert json.loads(created["c"].login_arg) == stored          # logged in with R2 token
    assert written["key"] == "_auth/token.json"
    assert written["obj"] == json.loads(TOKEN_JSON)              # refreshed token written back


def test_interactive_login_requires_credentials(monkeypatch):
    monkeypatch.setattr(config, "GARMIN_EMAIL", None)
    monkeypatch.setattr(config, "GARMIN_PASSWORD", None)
    with pytest.raises(SystemExit):
        auth.interactive_login()


def test_interactive_login_saves_token(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GARMIN_EMAIL", "a@b.c")
    monkeypatch.setattr(config, "GARMIN_PASSWORD", "pw")
    monkeypatch.setattr(config, "TOKEN_DIR", str(tmp_path / "tok"))
    monkeypatch.setattr(auth, "Garmin", lambda *a, **k: FakeGarminClient(*a, **k))

    _, b64 = auth.interactive_login()
    assert base64.b64decode(b64).decode() == TOKEN_JSON
    saved = (tmp_path / "tok" / "token_b64.txt").read_text(encoding="utf-8")
    assert saved == b64
