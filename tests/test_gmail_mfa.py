import pytest

from garminscrap import config, gmail_mfa


def test_extract_code():
    assert gmail_mfa.extract_code("Your Garmin code is 872137 — expires soon") == "872137"
    assert gmail_mfa.extract_code("code: 952914.") == "952914"
    assert gmail_mfa.extract_code("no code here") is None
    assert gmail_mfa.extract_code("order 1234567 is 8 digits 12345678") is None


def test_configured(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_CLIENT_ID", "x")
    monkeypatch.setattr(config, "GMAIL_CLIENT_SECRET", "y")
    monkeypatch.setattr(config, "GMAIL_REFRESH_TOKEN", "z")
    assert gmail_mfa.configured() is True
    monkeypatch.setattr(config, "GMAIL_REFRESH_TOKEN", None)
    assert gmail_mfa.configured() is False


# --- minimal fake Gmail API surface ---
class _Exec:
    def __init__(self, val): self._val = val
    def execute(self): return self._val


class _Messages:
    def __init__(self, listing, msgs): self._listing, self._msgs = listing, msgs
    def list(self, **kw): return _Exec(self._listing)
    def get(self, *, userId, id, format): return _Exec(self._msgs[id])


class _Users:
    def __init__(self, m): self._m = m
    def messages(self): return self._m


class FakeService:
    def __init__(self, listing, msgs): self._u = _Users(_Messages(listing, msgs))
    def users(self): return self._u


def _msg(internal_ms, text):
    return {"internalDate": str(internal_ms), "snippet": text,
            "payload": {"headers": [], "parts": []}}


def test_get_code_returns_fresh(monkeypatch):
    after = 1_000_000  # seconds
    msgs = {"new": _msg((after + 5) * 1000, "code 654321")}
    monkeypatch.setattr(gmail_mfa, "_service",
                        lambda: FakeService({"messages": [{"id": "new"}]}, msgs))
    assert gmail_mfa.get_code(after, timeout=1, poll=0) == "654321"


def test_get_code_ignores_old_then_times_out(monkeypatch):
    after = 1_000_000
    # message is older than the (after - 30s) threshold -> ignored
    msgs = {"old": _msg((after - 100) * 1000, "code 111111")}
    monkeypatch.setattr(gmail_mfa, "_service",
                        lambda: FakeService({"messages": [{"id": "old"}]}, msgs))
    with pytest.raises(SystemExit):
        gmail_mfa.get_code(after, timeout=1, poll=0)


def test_get_code_picks_newest(monkeypatch):
    after = 1_000_000
    msgs = {
        "a": _msg((after + 5) * 1000, "code 222222"),
        "b": _msg((after + 50) * 1000, "code 333333"),  # newer
    }
    monkeypatch.setattr(gmail_mfa, "_service",
                        lambda: FakeService({"messages": [{"id": "a"}, {"id": "b"}]}, msgs))
    assert gmail_mfa.get_code(after, timeout=1, poll=0) == "333333"
