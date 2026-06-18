"""Garmin data fetchers, grouped by call shape. A failing endpoint is skipped."""
import logging
import time

log = logging.getLogger(__name__)

# Core per-day wellness datasets: name -> fn(client, "YYYY-MM-DD").
DAILY = {
    "user_summary": lambda c, d: c.get_user_summary(d),
    "steps": lambda c, d: c.get_steps_data(d),
    "heart_rate": lambda c, d: c.get_heart_rates(d),
    "resting_hr": lambda c, d: c.get_rhr_day(d),
    "stats": lambda c, d: c.get_stats(d),
    "sleep": lambda c, d: c.get_sleep_data(d),
    "stress": lambda c, d: c.get_stress_data(d),
    "body_battery": lambda c, d: c.get_body_battery(d, d),
    "spo2": lambda c, d: c.get_spo2_data(d),
    "hrv": lambda c, d: c.get_hrv_data(d),
    "respiration": lambda c, d: c.get_respiration_data(d),
    "max_metrics": lambda c, d: c.get_max_metrics(d),
    "training_readiness": lambda c, d: c.get_training_readiness(d),
    "training_status": lambda c, d: c.get_training_status(d),
    "intensity_minutes": lambda c, d: c.get_intensity_minutes_data(d),
    "floors": lambda c, d: c.get_floors(d),
    "body_composition": lambda c, d: c.get_body_composition(d),
}

# Extra per-day datasets (only with --full): name -> fn(client, "YYYY-MM-DD").
DAILY_EXTRA = {
    "fitness_age": lambda c, d: c.get_fitnessage_data(d),
    "daily_weigh_ins": lambda c, d: c.get_daily_weigh_ins(d),
    "hydration": lambda c, d: c.get_hydration_data(d),
}

# Whole-window metrics (only with --full): name -> fn(client, start, end).
PERIOD = {
    "race_predictions": lambda c, s, e: c.get_race_predictions(),
    "endurance_score": lambda c, s, e: c.get_endurance_score(s, e),
    "hill_score": lambda c, s, e: c.get_hill_score(s, e),
    "running_tolerance": lambda c, s, e: c.get_running_tolerance(s, e),
    "lactate_threshold": lambda c, s, e: c.get_lactate_threshold(
        latest=False, start_date=s, end_date=e),
    "weigh_ins": lambda c, s, e: c.get_weigh_ins(s, e),
    "blood_pressure": lambda c, s, e: c.get_blood_pressure(s, e),
    "cycling_ftp": lambda c, s, e: c.get_cycling_ftp(),
    "personal_records": lambda c, s, e: c.get_personal_record(),
}

# Per-activity detail (only with --full): name -> fn(client, activity_id).
ACTIVITY = {
    "summary": lambda c, a: c.get_activity(a),
    "details": lambda c, a: c.get_activity_details(a),
    "splits": lambda c, a: c.get_activity_splits(a),
    "typed_splits": lambda c, a: c.get_activity_typed_splits(a),
    "split_summaries": lambda c, a: c.get_activity_split_summaries(a),
    "hr_zones": lambda c, a: c.get_activity_hr_in_timezones(a),
    "power_zones": lambda c, a: c.get_activity_power_in_timezones(a),
    "weather": lambda c, a: c.get_activity_weather(a),
    "exercise_sets": lambda c, a: c.get_activity_exercise_sets(a),
    "gear": lambda c, a: c.get_activity_gear(a),
}


def fetch_datasets(client, date_str, datasets, pause=0.4):
    """Fetch the given {name: fn(client, date)} datasets for one date."""
    out = {}
    for name, fn in datasets.items():
        try:
            out[name] = fn(client, date_str)
        except Exception as e:  # one bad endpoint shouldn't kill the day
            log.warning("%s failed for %s: %s", name, date_str, e)
        time.sleep(pause)  # be gentle with the unofficial API
    return out


def fetch_day(client, date_str, pause=0.4):
    """Fetch the core daily wellness datasets for one date."""
    return fetch_datasets(client, date_str, DAILY, pause)


def fetch_period(client, start_str, end_str, pause=0.4):
    """Fetch whole-window performance/health metrics once."""
    out = {}
    for name, fn in PERIOD.items():
        try:
            out[name] = fn(client, start_str, end_str)
        except Exception as e:
            log.warning("period %s failed: %s", name, e)
        time.sleep(pause)
    return out


def fetch_activity(client, activity_id, pause=0.4):
    """Fetch per-activity detail for one activity id."""
    out = {}
    for name, fn in ACTIVITY.items():
        try:
            out[name] = fn(client, activity_id)
        except Exception as e:
            log.warning("activity %s %s failed: %s", activity_id, name, e)
        time.sleep(pause)
    return out


def fetch_activities(client, start_str, end_str):
    """Return the list of activities in [start, end]."""
    try:
        return client.get_activities_by_date(start_str, end_str)
    except Exception as e:
        log.warning("activities failed for %s..%s: %s", start_str, end_str, e)
        return []
