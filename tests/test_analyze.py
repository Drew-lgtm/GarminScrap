import json

import pytest

from garminscrap import analyze, config


def test_load_window_collects_days_and_activities(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    day = tmp_path / "2026-06-16"
    day.mkdir()
    (day / "sleep.json").write_text(json.dumps({"score": 90}), encoding="utf-8")
    (day / "steps.json").write_text(json.dumps({"steps": 1000}), encoding="utf-8")
    acts = tmp_path / "activities"
    acts.mkdir()
    (acts / "win.json").write_text(json.dumps([{"id": 1}]), encoding="utf-8")

    data = analyze._load_window("2026-06-16", "2026-06-16")
    assert data["2026-06-16"]["sleep"] == {"score": 90}
    assert data["2026-06-16"]["steps"] == {"steps": 1000}
    assert data["activities"]["win"] == [{"id": 1}]


def test_load_window_empty_when_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    assert analyze._load_window("2026-06-10", "2026-06-12") == {}


def test_run_requires_api_key(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    with pytest.raises(SystemExit):
        analyze.run("2026-06-16", "2026-06-16")
