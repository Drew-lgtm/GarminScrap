"""Optional AI report via the Claude API. Requires ANTHROPIC_API_KEY.

Reads the local scraped JSON for a date window, sends it to Claude with the
analysis brief in analysis/INSTRUCTIONS.md, and writes a markdown report.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from . import config

MAX_DATA_CHARS = 180_000  # rough guard against oversized prompts


def _load_window(start, end):
    """Collect per-day JSON in [start, end] from the local data dir."""
    base = Path(config.DATA_DIR)
    data = {}
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    while d <= e:
        ds = d.isoformat()
        day_dir = base / ds
        if day_dir.is_dir():
            data[ds] = {
                p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(day_dir.glob("*.json"))
            }
        d += timedelta(days=1)

    activities = {}
    for p in (base / "activities").glob("*.json") if (base / "activities").is_dir() else []:
        activities[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    if activities:
        data["activities"] = activities
    return data


def run(start, end):
    if not config.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY not set; cannot run analyze.")
    import anthropic

    instructions = Path("analysis/INSTRUCTIONS.md").read_text(encoding="utf-8")
    payload = json.dumps(_load_window(start, end), ensure_ascii=False)
    if len(payload) > MAX_DATA_CHARS:
        payload = payload[:MAX_DATA_CHARS]  # truncate; narrow the window for full detail

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=instructions,
        messages=[{
            "role": "user",
            "content": (
                f"Here is my Garmin data for {start}..{end} as JSON:\n\n"
                f"```json\n{payload}\n```\n\n"
                "Produce the analysis described in your instructions."
            ),
        }],
    )

    report = "".join(b.text for b in msg.content if b.type == "text")
    out = Path(config.DATA_DIR) / f"report-{start}_{end}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Report written to {out}")
