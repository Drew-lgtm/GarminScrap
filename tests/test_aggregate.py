from garminscrap import aggregate


class FakeReader:
    def __init__(self, files):
        self.files = files  # {key: obj}

    def read_json(self, key):
        return self.files.get(key)

    def list_keys(self, prefix=""):
        return [k for k in self.files if k.startswith(prefix)]


def _day_files(ds):
    return {
        f"{ds}/sleep.json": {"dailySleepDTO": {
            "sleepTimeSeconds": 27000,  # 7.5 h
            "deepSleepSeconds": 3600, "remSleepSeconds": 5400,
            "lightSleepSeconds": 16200, "awakeSleepSeconds": 1800,
            "sleepScores": {"overall": {"value": 82, "qualifierKey": "GOOD"}},
        }},
        f"{ds}/user_summary.json": {
            "totalSteps": 9500, "restingHeartRate": 52, "averageStressLevel": 30,
            "moderateIntensityMinutes": 20, "vigorousIntensityMinutes": 10,
            "activeKilocalories": 640.4,
        },
        f"{ds}/hrv.json": {"hrvSummary": {"lastNightAvg": 68, "status": "BALANCED"}},
        f"{ds}/stress.json": {"avgStressLevel": 28, "maxStressLevel": 90},
        f"{ds}/training_readiness.json": [{"score": 74, "level": "HIGH", "acuteLoad": 320}],
        f"{ds}/body_battery.json": [{"charged": 55, "drained": 40}],
        f"{ds}/daily_weigh_ins.json": {"totalAverage": {"weight": 75200.0, "bmi": 23.4, "bodyFat": 18.1}},
    }


def test_day_summary_extraction():
    ds = "2026-06-15"
    reader = FakeReader(_day_files(ds))
    win = aggregate.load_window(reader, ds, ds)
    assert len(win["days"]) == 1
    d = win["days"][0]
    assert d["sleep_h"] == 7.5
    assert d["sleep_score"] == 82
    assert d["deep_min"] == 60
    assert d["resting_hr"] == 52
    assert d["hrv_night"] == 68 and d["hrv_status"] == "BALANCED"
    assert d["avg_stress"] == 28
    assert d["steps"] == 9500
    assert d["intensity_min"] == 30
    assert d["readiness"] == 74 and d["acute_load"] == 320
    assert d["bb_charged"] == 55
    assert d["weight_kg"] == 75.2 and d["bmi"] == 23.4  # grams -> kg


def test_empty_window():
    win = aggregate.load_window(FakeReader({}), "2026-06-01", "2026-06-03")
    assert win["days"] == [] and win["activities"] == []


def test_activities_filtered_and_deduped():
    files = {
        "activities/w1.json": [
            {"activityId": 1, "activityName": "Run", "activityType": {"typeKey": "running"},
             "startTimeLocal": "2026-06-15 07:00:00", "duration": 1800, "distance": 5000,
             "averageHR": 150, "calories": 400, "aerobicTrainingEffect": 3.1},
            {"activityId": 2, "activityName": "Old", "activityType": {"typeKey": "cycling"},
             "startTimeLocal": "2026-05-01 07:00:00", "duration": 600, "distance": 3000},
        ],
        # a detail file must be ignored, and a duplicate id deduped
        "activities/detail/1/summary.json": {"activityId": 1},
        "activities/w2.json": [
            {"activityId": 1, "activityName": "Run", "activityType": {"typeKey": "running"},
             "startTimeLocal": "2026-06-15 07:00:00", "duration": 1800, "distance": 5000},
        ],
    }
    acts = aggregate._load_activities(FakeReader(files), "2026-06-14", "2026-06-16")
    assert len(acts) == 1  # id 2 out of range, id 1 deduped
    assert acts[0]["type"] == "running" and acts[0]["dist_km"] == 5.0


def test_digest_text_contains_sections():
    win = aggregate.load_window(FakeReader(_day_files("2026-06-15")), "2026-06-15", "2026-06-15")
    text = aggregate.to_digest_text(win)
    assert "COMPUTED WEEKLY STATS" in text and "DAILY METRICS" in text and "ACTIVITIES" in text


def test_computed_stats_are_deterministic_and_dont_contradict():
    days = [
        {"date": "2026-07-21", "sleep_h": 7.8, "resting_hr": 55, "hrv_night": 52,
         "bb_charged": 79, "bb_drained": 82, "acute_load": 64, "weight_kg": 92.0},
        {"date": "2026-07-22", "sleep_h": 7.9, "resting_hr": 54, "hrv_night": 50,
         "bb_charged": 77, "bb_drained": 72, "acute_load": 55, "weight_kg": 92.0},
        {"date": "2026-07-25", "sleep_h": 4.7, "resting_hr": 57, "hrv_night": 49,
         "bb_charged": 69, "bb_drained": 86, "acute_load": 70, "weight_kg": None},
        {"date": "2026-07-26", "sleep_h": 7.8, "resting_hr": 53, "hrv_night": 55,
         "bb_charged": None, "bb_drained": None, "acute_load": 60, "weight_kg": 92.5},
    ]
    stats = aggregate._computed_stats(days)
    assert stats["nights_under_6_5h"] == 1  # only 07-25
    assert stats["bb_net_days_total"] == 3   # the day with None/None is excluded
    assert stats["bb_net_negative_days"] == 2   # 07-21 and 07-25 only, NOT "consistently"
    assert stats["weight_delta_kg"] == 0.5   # sparse readings still diff first->last
    assert stats["acute_load_start"] == 64 and stats["acute_load_end"] == 60


def _bb_day(ds, sleep_secs, wake, low, end):
    files = _day_files(ds)
    files[f"{ds}/sleep.json"]["dailySleepDTO"]["sleepTimeSeconds"] = sleep_secs
    files[f"{ds}/user_summary.json"].update(
        bodyBatteryAtWakeTime=wake, bodyBatteryLowestValue=low, bodyBatteryMostRecentValue=end)
    return files


def _two_week_reader():
    files = {}
    files.update(_bb_day("2026-06-15", 25200, 80, 20, 35))  # 7.0 h
    files.update(_bb_day("2026-06-17", 28800, 90, 30, 55))  # 8.0 h; 06-16 has no data
    files.update(_bb_day("2026-06-13", 21600, 70, 10, 25))  # prev window (06-12..06-14), 6.0 h
    files["activities/w.json"] = [
        {"activityId": 1, "startTimeLocal": "2026-06-15 07:00:00", "duration": 1800},
        {"activityId": 2, "startTimeLocal": "2026-06-15 18:00:00", "duration": 3600},
    ]
    return FakeReader(files)


def test_week_table_md_rows_gaps_and_prev_comparison():
    reader = _two_week_reader()
    win = aggregate.load_window(reader, "2026-06-15", "2026-06-17")
    pavg = aggregate.prev_avg(reader, "2026-06-15", "2026-06-17")

    lines = aggregate.week_table_md(win, "2026-06-15", "2026-06-17", pavg).splitlines()
    cells = lambda i: [c.strip() for c in lines[i].strip("|").split("|")]

    assert cells(0)[:2] == ["Day", "Sleep h"] and "BB end" in cells(0)
    mon = cells(2)                                   # first data row (06-15 is a Monday)
    assert mon[0] == "Mon 06-15" and mon[1] == "7"
    assert mon[cells(0).index("BB wake")] == "80" and mon[cells(0).index("BB end")] == "35"
    assert mon[cells(0).index("Acts")] == "2" and mon[cells(0).index("Act min")] == "90"
    gap = cells(3)                                   # 06-16: no data at all
    assert gap[0] == "Tue 06-16" and set(gap[1:]) == {"–"}
    assert cells(5)[:2] == ["**Avg**", "7.5"]        # mean of 7.0 and 8.0, gap ignored
    assert cells(6)[:2] == ["Prev avg", "6"]
    assert cells(7)[:2] == ["Δ", "+1.5"]
    assert "Body Battery" in lines[-1]               # legend


def test_week_over_week_matches_table_numbers():
    reader = _two_week_reader()
    win = aggregate.load_window(reader, "2026-06-15", "2026-06-17")
    pavg = aggregate.prev_avg(reader, "2026-06-15", "2026-06-17")
    wow = aggregate.week_over_week(win, "2026-06-15", "2026-06-17", pavg)

    assert wow["sleep_h"] == {"this_week": 7.5, "last_week": 6.0, "change": 1.5}  # table: 7.5 / 6 / +1.5
    assert wow["bb_wake"] == {"this_week": 85.0, "last_week": 70.0, "change": 15.0}
    assert wow["act_min"] == {"this_week": 45, "last_week": 0, "change": 45}       # 0 decimals -> int
    assert set(wow) == {key for _, key, _ in aggregate.TABLE_COLS}

    text = aggregate.to_digest_text(win, wow)
    assert "WEEK-OVER-WEEK" in text and '"sleep_h": {"this_week": 7.5' in text


def test_week_table_md_without_prev_data_omits_comparison():
    files = _bb_day("2026-06-15", 25200, 80, 20, 35)
    reader = FakeReader(files)
    win = aggregate.load_window(reader, "2026-06-15", "2026-06-15")
    pavg = aggregate.prev_avg(reader, "2026-06-15", "2026-06-15")
    assert pavg is None
    text = aggregate.week_table_md(win, "2026-06-15", "2026-06-15", pavg)
    assert "| Prev avg |" not in text and "| Δ |" not in text and "| **Avg** |" in text
    assert aggregate.week_over_week(win, "2026-06-15", "2026-06-15", pavg) is None
    assert "no data for last week" in aggregate.to_digest_text(win, None)


def test_prev_window_is_adjacent_and_equal_length():
    assert aggregate.prev_window("2026-06-08", "2026-06-14") == ("2026-06-01", "2026-06-07")


def test_computed_stats_empty_days():
    stats = aggregate._computed_stats([])
    assert stats["avg_sleep_h"] is None and stats["weight_delta_kg"] is None
    assert stats["bb_net_by_day"] == []
