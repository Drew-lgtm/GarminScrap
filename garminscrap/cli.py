"""Command line entry point: login / scrape / analyze."""
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from . import auth, config, fetch
from .storage import LocalStorage, remote_storage


def _daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _resolve_window(args):
    today = date.today()
    if args.date:
        d = date.fromisoformat(args.date)
        return d, d
    if args.start:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end) if args.end else today
        return start, end
    return today - timedelta(days=args.days - 1), today


def cmd_login(args):
    _, token_b64 = auth.interactive_login(skip_mobile=args.skip_mobile)
    b64_path = Path(config.TOKEN_DIR) / "token_b64.txt"
    print(f"\nLogin OK. Token saved to: {config.TOKEN_DIR}")
    print(f"GitHub Actions secret GARMIN_TOKEN_B64 saved to: {b64_path} (gitignored)")
    if args.show_token:
        print("\n--- GARMIN_TOKEN_B64 ---")
        print(token_b64)
        print("--- end ---")


def cmd_scrape(args):
    start, end = _resolve_window(args)
    client = auth.get_client()
    local = LocalStorage()
    remote = remote_storage()

    def put(key, data):
        local.write_json(key, data)
        if remote:
            remote.write_json(key, data)

    # 1. Daily datasets (per-dataset skip so an interrupted run resumes cleanly).
    daily = {**fetch.DAILY, **fetch.DAILY_EXTRA} if args.full else fetch.DAILY
    for d in _daterange(start, end):
        ds = d.isoformat()
        todo = {n: fn for n, fn in daily.items()
                if args.force or not local.exists(f"{ds}/{n}.json")}
        if not todo:
            logging.info("skip %s (complete)", ds)
            continue
        day = fetch.fetch_datasets(client, ds, todo)
        for name, data in day.items():
            put(f"{ds}/{name}.json", data)
        logging.info("stored %s (%d datasets)", ds, len(day))

    # 2. Activity list for the window.
    acts = fetch.fetch_activities(client, start.isoformat(), end.isoformat())
    put(f"activities/{start.isoformat()}_{end.isoformat()}.json", acts)
    logging.info("found %d activities", len(acts) if isinstance(acts, list) else 0)

    if not args.full:
        return

    # 3. Whole-window performance/health metrics.
    period = fetch.fetch_period(client, start.isoformat(), end.isoformat())
    for name, data in period.items():
        put(f"period/{name}_{start.isoformat()}_{end.isoformat()}.json", data)
    logging.info("stored %d period metrics", len(period))

    # 4. Per-activity detail (skip activities already detailed).
    detailed = 0
    for act in acts if isinstance(acts, list) else []:
        aid = act.get("activityId") if isinstance(act, dict) else None
        if not aid:
            continue
        base = f"activities/detail/{aid}"
        if not args.force and local.exists(f"{base}/summary.json"):
            continue
        for name, data in fetch.fetch_activity(client, aid).items():
            put(f"{base}/{name}.json", data)
        detailed += 1
    logging.info("stored details for %d activities", detailed)


def cmd_analyze(args):
    from . import analyze
    analyze.run(args.start, args.end)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="garminscrap")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login", help="One-time interactive login (handles MFA)")
    sp.add_argument("--show-token", action="store_true",
                    help="also print the base64 token to the terminal")
    sp.add_argument("--skip-mobile", action="store_true",
                    help="skip rate-limited mobile login; go straight to the code prompt")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("scrape", help="Fetch and store Garmin data")
    sp.add_argument("--days", type=int, default=7, help="last N days ending today")
    sp.add_argument("--date", help="single date YYYY-MM-DD")
    sp.add_argument("--start", help="start date YYYY-MM-DD")
    sp.add_argument("--end", help="end date YYYY-MM-DD (default today)")
    sp.add_argument("--force", action="store_true", help="re-fetch even if present")
    sp.add_argument("--full", action="store_true",
                    help="also fetch performance metrics, weigh-ins/BP/hydration, "
                         "and per-activity details")
    sp.set_defaults(func=cmd_scrape)

    sp = sub.add_parser("analyze", help="AI report for a window (needs ANTHROPIC_API_KEY)")
    sp.add_argument("--start", required=True)
    sp.add_argument("--end", required=True)
    sp.set_defaults(func=cmd_analyze)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
