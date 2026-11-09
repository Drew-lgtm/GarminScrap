import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

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
                        lambda subject, body, to, html=None: sent.update(
                            subject=subject, body=body, to=to, html=html))

    out = report.run("2026-06-15", "2026-06-15", email=True)
    assert out.startswith("# Report")
    assert sent["to"] == "me@gmail.com"
    assert "looks fine" in sent["body"]
    assert "Week at a glance" in sent["body"] and "| Day |" in sent["body"]
    assert "<table" in sent["html"] and "Week at a glance" in sent["html"]
    assert (tmp_path / "report-2026-06-15_2026-06-15.md").exists()


def test_to_html_styles_aligned_table_cells():
    md = "| A | B |\n|---|---:|\n| 1 | 2 |\n"
    html = report._to_html(md)
    assert "<table" in html and "overflow-x:auto" in html
    assert f'{report._CELL_STYLE}text-align: right;' in html  # merged styles


def test_send_email_attaches_html_alternative(monkeypatch):
    import smtplib

    monkeypatch.setattr(config, "GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setattr(config, "GMAIL_APP_PASSWORD", "pw")
    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, *a): pass
        def send_message(self, msg): captured["msg"] = msg

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    report._send_email("subj", "plain body", "me@gmail.com", html="<p>hi</p>")
    msg = captured["msg"]
    assert msg.is_multipart()
    assert msg.get_body(("plain",)).get_content().strip() == "plain body"
    assert "<p>hi</p>" in msg.get_body(("html",)).get_content()


def test_run_no_data(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "key")
    monkeypatch.setattr(report, "get_reader", lambda source=None: object())
    monkeypatch.setattr(aggregate, "load_window", lambda r, s, e: {"days": [], "activities": []})
    with pytest.raises(SystemExit):
        report.run("2026-06-15", "2026-06-15", email=False)


@contextmanager
def _fake_gemini(monkeypatch, payload):
    """Point the real google-genai SDK at a local server that answers with `payload`."""
    seen = {}

    class FakeGemini(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), FakeGemini)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", f"http://127.0.0.1:{server.server_port}/")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    try:
        yield seen
    finally:
        server.shutdown()


def _answer(text, finish="STOP"):
    return {"candidates": [{"finishReason": finish,
                            "content": {"role": "model", "parts": [{"text": text}]}}]}


def test_gemini_real_sdk_request_uses_v1beta_with_system_instruction(monkeypatch):
    """Regression: google-genai 3.x defaults to API v1, which rejects system_instruction."""
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    with _fake_gemini(monkeypatch, _answer("# Report")) as seen:
        assert report._gemini("my data") == "# Report"

    assert seen["path"].startswith("/v1beta/models/gemini-3.5-flash-lite:generateContent")
    assert "my data" in json.dumps(seen["body"]["contents"])
    assert "coach" in json.dumps(seen["body"]["systemInstruction"])
    assert seen["body"]["generationConfig"]["maxOutputTokens"] == report._MAX_OUTPUT_TOKENS


def test_gemini_blocked_prompt_fails_clearly(monkeypatch):
    blocked = {"promptFeedback": {"blockReason": "SAFETY"}}  # no candidates, text is None
    with _fake_gemini(monkeypatch, blocked):
        with pytest.raises(RuntimeError, match="no report text.*SAFETY"):
            report._gemini("my data")


def test_gemini_empty_answer_fails_clearly(monkeypatch):
    empty = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}]}
    with _fake_gemini(monkeypatch, empty):
        with pytest.raises(RuntimeError, match="no report text.*MAX_TOKENS"):
            report._gemini("my data")


def test_gemini_truncated_report_is_flagged(monkeypatch):
    with _fake_gemini(monkeypatch, _answer("# Report\npartial", finish="MAX_TOKENS")):
        out = report._gemini("my data")
    assert out.startswith("# Report\npartial") and "Report cut off" in out


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
        def __init__(self, api_key=None, http_options=None):
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
        def __init__(self, api_key=None, http_options=None):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    with pytest.raises(genai_errors.ServerError):
        report._gemini("prompt")
