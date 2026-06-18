from garminscrap import fetch


def test_fetch_day_returns_all_datasets(fake_garmin):
    out = fetch.fetch_day(fake_garmin, "2026-06-16", pause=0)
    assert set(out) == set(fetch.DAILY)
    assert out["sleep"]["_method"] == "get_sleep_data"
    assert out["body_battery"]["args"] == ["2026-06-16", "2026-06-16"]


def test_fetch_day_skips_failing_endpoints(make_garmin):
    client = make_garmin(fail={"get_sleep_data", "get_hrv_data"})
    out = fetch.fetch_day(client, "2026-06-16", pause=0)
    assert "sleep" not in out
    assert "hrv" not in out
    assert "steps" in out  # unaffected datasets still present


def test_fetch_activities_ok(fake_garmin):
    res = fetch.fetch_activities(fake_garmin, "2026-06-01", "2026-06-07")
    assert res["_method"] == "get_activities_by_date"


def test_fetch_activities_returns_empty_on_error(make_garmin):
    client = make_garmin(fail={"get_activities_by_date"})
    assert fetch.fetch_activities(client, "a", "b") == []
