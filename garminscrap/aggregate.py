"""Turn raw scraped JSON into a compact digest for the AI report.

A year of raw data is far too big for a model; this pulls the clinically useful
numbers into one small row per day plus an activity list.
"""
import json
from datetime import date, timedelta

# Daily datasets the report needs (read per date).
DAILY_LOAD = ["sleep", "user_summary", "hrv", "stress", "training_readiness",
              "body_battery", "max_metrics", "daily_weigh_ins"]


def _daterange(start, end):
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)


def _mins(x):
    return round(x / 60) if isinstance(x, (int, float)) else None


def _day_summary(ds, files):
    dto = (files.get("sleep") or {}).get("dailySleepDTO") or {}
    us = files.get("user_summary") or {}
    hrv = (files.get("hrv") or {}).get("hrvSummary") or {}
    stress = files.get("stress") or {}
    tr = files.get("training_readiness") or []
    tr0 = tr[0] if isinstance(tr, list) and tr else {}
    bb = files.get("body_battery") or []
    bb0 = bb[0] if isinstance(bb, list) and bb else {}
    wavg = (files.get("daily_weigh_ins") or {}).get("totalAverage") or {}
    wg = wavg.get("weight")
    weight_kg = round(wg / 1000, 1) if isinstance(wg, (int, float)) and wg > 500 else (
        round(wg, 1) if isinstance(wg, (int, float)) else None)
    sleep_secs = dto.get("sleepTimeSeconds")
    overall = (dto.get("sleepScores") or {}).get("overall") or {}
    return {
        "date": ds,
        "sleep_h": round(sleep_secs / 3600, 1) if sleep_secs else None,
        "sleep_score": overall.get("value"),
        "deep_min": _mins(dto.get("deepSleepSeconds")),
        "rem_min": _mins(dto.get("remSleepSeconds")),
        "light_min": _mins(dto.get("lightSleepSeconds")),
        "awake_min": _mins(dto.get("awakeSleepSeconds")),
        "resting_hr": us.get("restingHeartRate"),
        "hrv_night": hrv.get("lastNightAvg"),
        "hrv_status": hrv.get("status"),
        "avg_stress": stress.get("avgStressLevel", us.get("averageStressLevel")),
        "steps": us.get("totalSteps"),
        "intensity_min": (us.get("moderateIntensityMinutes") or 0)
                         + (us.get("vigorousIntensityMinutes") or 0),
        "active_kcal": round(us["activeKilocalories"]) if us.get("activeKilocalories") else None,
        "readiness": tr0.get("score"),
        "readiness_level": tr0.get("level"),
        "acute_load": tr0.get("acuteLoad"),
        "bb_charged": bb0.get("charged"),
        "bb_drained": bb0.get("drained"),
        "weight_kg": weight_kg,
        "bmi": round(wavg["bmi"], 1) if isinstance(wavg.get("bmi"), (int, float)) else None,
        "body_fat_pct": round(wavg["bodyFat"], 1) if isinstance(wavg.get("bodyFat"), (int, float)) else None,
    }


def _load_activities(reader, start, end):
    seen = {}
    for key in reader.list_keys("activities/"):
        if "/detail/" in key or not key.endswith(".json"):
            continue
        lst = reader.read_json(key)
        if not isinstance(lst, list):
            continue
        for a in lst:
            d = (a.get("startTimeLocal") or "")[:10]
            if start <= d <= end:
                seen[a.get("activityId")] = {
                    "date": d,
                    "name": a.get("activityName"),
                    "type": (a.get("activityType") or {}).get("typeKey"),
                    "dur_min": round((a.get("duration") or 0) / 60),
                    "dist_km": round((a.get("distance") or 0) / 1000, 2),
                    "avg_hr": a.get("averageHR"),
                    "max_hr": a.get("maxHR"),
                    "kcal": round(a["calories"]) if a.get("calories") else None,
                    "aerobic_te": a.get("aerobicTrainingEffect"),
                    "anaerobic_te": a.get("anaerobicTrainingEffect"),
                    "load": a.get("activityTrainingLoad"),
                }
    return sorted(seen.values(), key=lambda x: x["date"])


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else None


def _computed_stats(days):
    """Deterministic weekly aggregates, computed in code so the model never has
    to eyeball arithmetic across days (source of past self-contradictions)."""
    sleep_hs = [d["sleep_h"] for d in days if d.get("sleep_h") is not None]
    rhrs = [d["resting_hr"] for d in days if d.get("resting_hr") is not None]
    hrvs = [d["hrv_night"] for d in days if d.get("hrv_night") is not None]
    nets = [(d["date"], round(d["bb_charged"] - d["bb_drained"], 1)) for d in days
            if d.get("bb_charged") is not None and d.get("bb_drained") is not None]
    loads = [d["acute_load"] for d in days if d.get("acute_load") is not None]
    weights = [(d["date"], d["weight_kg"]) for d in days if d.get("weight_kg") is not None]

    return {
        "avg_sleep_h": _avg(sleep_hs),
        "nights_with_sleep_data": len(sleep_hs),
        "nights_under_6_5h": sum(1 for h in sleep_hs if h < 6.5),
        "avg_resting_hr": _avg(rhrs),
        "resting_hr_range": [min(rhrs), max(rhrs)] if rhrs else None,
        "hrv_night_range": [min(hrvs), max(hrvs)] if hrvs else None,
        "bb_net_by_day": nets,  # [(date, charged-drained)]
        "bb_net_negative_days": sum(1 for _, n in nets if n < 0),
        "bb_net_days_total": len(nets),
        "avg_bb_net": _avg([n for _, n in nets]),
        "acute_load_start": loads[0] if loads else None,
        "acute_load_end": loads[-1] if loads else None,
        "weight_readings": weights,  # [(date, kg)], sparse by design
        "weight_delta_kg": (round(weights[-1][1] - weights[0][1], 1)
                             if len(weights) >= 2 else None),
    }


def load_window(reader, start, end):
    """Return {'days': [...], 'activities': [...], 'stats': {...}} for [start, end]."""
    days = []
    for ds in _daterange(start, end):
        files = {}
        for name in DAILY_LOAD:
            obj = reader.read_json(f"{ds}/{name}.json")
            if obj is not None:
                files[name] = obj
        if files:
            days.append(_day_summary(ds, files))
    return {
        "days": days,
        "activities": _load_activities(reader, start, end),
        "stats": _computed_stats(days),
    }


def to_digest_text(summary):
    """Compact text form of the window for the model prompt."""
    return (
        "COMPUTED WEEKLY STATS (ground truth for weekly-level claims):\n"
        + json.dumps(summary["stats"], ensure_ascii=False)
        + "\n\nDAILY METRICS (one row per day):\n"
        + json.dumps(summary["days"], ensure_ascii=False)
        + f"\n\nACTIVITIES ({len(summary['activities'])}):\n"
        + json.dumps(summary["activities"], ensure_ascii=False)
    )
