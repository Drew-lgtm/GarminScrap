from datetime import date
from types import SimpleNamespace

from garminscrap import cli, config, fetch


def test_daterange_inclusive():
    days = list(cli._daterange(date(2026, 6, 1), date(2026, 6, 3)))
    assert days == [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]


def test_resolve_window_single_date():
    args = SimpleNamespace(date="2026-06-16", start=None, end=None, days=7)
    assert cli._resolve_window(args) == (date(2026, 6, 16), date(2026, 6, 16))


def test_resolve_window_start_end():
    args = SimpleNamespace(date=None, start="2026-06-01", end="2026-06-05", days=7)
    assert cli._resolve_window(args) == (date(2026, 6, 1), date(2026, 6, 5))


def test_resolve_window_days_spans_inclusive():
    args = SimpleNamespace(date=None, start=None, end=None, days=3)
    start, end = cli._resolve_window(args)
    assert (end - start).days == 2  # 3 days inclusive


def _scrape_args(**over):
    base = dict(date="2026-06-16", start=None, end=None, days=1, force=False, full=False)
    base.update(over)
    return SimpleNamespace(**base)


def test_scrape_writes_files(tmp_path, monkeypatch, make_garmin):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(fetch.time, "sleep", lambda *a: None)
    monkeypatch.setattr(cli.auth, "get_client", lambda: make_garmin())

    cli.cmd_scrape(_scrape_args())

    day_dir = tmp_path / "2026-06-16"
    files = {p.name for p in day_dir.glob("*.json")}
    assert "sleep.json" in files
    assert len(files) == len(fetch.DAILY)
    assert (tmp_path / "activities" / "2026-06-16_2026-06-16.json").exists()


def test_scrape_skips_existing_without_force(tmp_path, monkeypatch, make_garmin):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(fetch.time, "sleep", lambda *a: None)
    client = make_garmin()
    monkeypatch.setattr(cli.auth, "get_client", lambda: client)

    cli.cmd_scrape(_scrape_args())
    cli.cmd_scrape(_scrape_args())  # second run should skip already-present datasets

    daily_calls = [c for c in client.calls if c[0] != "get_activities_by_date"]
    assert len(daily_calls) == len(fetch.DAILY)  # each daily dataset fetched once


def test_scrape_full_includes_extras(tmp_path, monkeypatch, make_garmin):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(fetch.time, "sleep", lambda *a: None)
    monkeypatch.setattr(cli.auth, "get_client", lambda: make_garmin())
    monkeypatch.setattr(fetch, "fetch_activities", lambda c, s, e: [{"activityId": 999}])

    cli.cmd_scrape(_scrape_args(full=True))

    day_files = {p.name for p in (tmp_path / "2026-06-16").glob("*.json")}
    assert len(day_files) == len(fetch.DAILY) + len(fetch.DAILY_EXTRA)

    period_files = list((tmp_path / "period").glob("*.json"))
    assert len(period_files) == len(fetch.PERIOD)

    detail = tmp_path / "activities" / "detail" / "999"
    assert detail.is_dir()
    assert len(list(detail.glob("*.json"))) == len(fetch.ACTIVITY)
