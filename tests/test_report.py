import pytest

from garminscrap import aggregate, config, report


def test_run_requires_api_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    with pytest.raises(SystemExit):
        report.run("2026-06-15", "2026-06-15", email=False)


def test_run_emails(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(config, "GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setattr(config, "GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setattr(config, "REPORT_TO", "me@gmail.com")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(report, "get_reader", lambda source=None: object())
    monkeypatch.setattr(aggregate, "load_window",
                        lambda r, s, e: {"days": [{"date": s, "sleep_h": 7.5}], "activities": [],
                                         "stats": aggregate._computed_stats([{"date": s, "sleep_h": 7.5}])})
    monkeypatch.setattr(report, "_gemini", lambda prompt: "# Report\nlooks fine")
    sent = {}
    monkeypatch.setattr(report, "_send_email",
                        lambda subject, body, to: sent.update(subject=subject, body=body, to=to))

    out = report.run("2026-06-15", "2026-06-15", email=True)
    assert out.startswith("# Report")
    assert sent["to"] == "me@gmail.com"
    assert "looks fine" in sent["body"]
    assert (tmp_path / "report-2026-06-15_2026-06-15.md").exists()


def test_run_no_data(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(report, "get_reader", lambda source=None: object())
    monkeypatch.setattr(aggregate, "load_window", lambda r, s, e: {"days": [], "activities": []})
    with pytest.raises(SystemExit):
        report.run("2026-06-15", "2026-06-15", email=False)


def test_gemini_retries_transient_server_error(monkeypatch):
    from google.genai import errors as genai_errors

    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(report, "_RETRY_DELAYS", [0, 0])  # skip real sleeps
    monkeypatch.setattr(report.time, "sleep", lambda s: None)

    calls = {"n": 0}

    class FakeResp:
        text = "# Report\nok"

    class FakeModels:
        def generate_content(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise genai_errors.ServerError(503, {"error": {"message": "busy"}})
            return FakeResp()

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    assert report._gemini("prompt") == "# Report\nok"
    assert calls["n"] == 3


def test_gemini_raises_after_exhausting_retries(monkeypatch):
    from google.genai import errors as genai_errors

    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(report, "_RETRY_DELAYS", [0])
    monkeypatch.setattr(report.time, "sleep", lambda s: None)

    class FakeModels:
        def generate_content(self, **kwargs):
            raise genai_errors.ServerError(503, {"error": {"message": "busy"}})

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    with pytest.raises(genai_errors.ServerError):
        report._gemini("prompt")
