"""Decide whether a scheduled workflow run should do the full model build.

GitHub cron is static, so build.yml polls hourly and this script gates the
expensive run (play-by-play reconstruction, weekly refits) against the live
NFL schedule. Stdlib only, so the plan job needs no pip install.

Runs the build when:
  * the event is not a schedule (push, manual dispatch): always;
  * the cron is the daily pass (DAILY_CRON): always -- it grades finished
    games and refreshes the board;
  * an unplayed regular-season game kicks off within LEDGER_WINDOW_HOURS and
    the forward ledger has no snapshot of it for the current REVISION yet.
    nfl_model.record_forward only writes a game once BOTH injury reports carry
    game statuses (Friday; Wednesday for Thursday games), so this keeps
    polling hourly until the first post-report snapshot lands, then stops;
  * any game kicks off within FINAL_REFRESH_MINUTES: a last pregame board
    refresh (market line, late statuses) even if it is already recorded.
A schedule lookup failure fails open: an extra build costs minutes, a missed
first snapshot costs a forward observation nothing can re-derive.

The ledger window (30h) is longer than the gap between hourly polls by a wide
margin, so a dropped cron delivery delays a snapshot instead of losing it.
"""

import csv
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DAILY_CRON = "13 6 * * *"
LEDGER_WINDOW_HOURS = 30
FINAL_REFRESH_MINUTES = 150
MIN_MINUTES_BEFORE = 15
LEDGER_PATH = Path("data/forward_predictions.jsonl")
MODEL_PATH = Path("nfl_model.py")


def current_revision(model_path=MODEL_PATH):
    m = re.search(r"^REVISION='([^']+)'", Path(model_path).read_text(encoding="utf-8"), re.M)
    if not m:
        raise ValueError(f"no REVISION in {model_path}")
    return m.group(1)


def recorded_games(revision, ledger_path=LEDGER_PATH):
    if not Path(ledger_path).exists():
        return set()
    out = set()
    for line in Path(ledger_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("revision") == revision:
                out.add(r["game_id"])
    return out


def kickoff(row):
    """gameday + gametime are US/Eastern in nflverse games.csv."""
    try:
        naive = datetime.fromisoformat(f"{row['gameday']}T{row['gametime']}")
    except (KeyError, ValueError):
        return None
    return naive.replace(tzinfo=ET).astimezone(timezone.utc)


def fetch_games(url=SCHEDULE_URL):
    req = Request(url, headers={"User-Agent": "nfl-model-schedule-gate/1.0"})
    with urlopen(req, timeout=30) as response:
        text = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def due_games(games, now, recorded):
    """(game_id, reason) for every game that justifies a build right now."""
    now = now.astimezone(timezone.utc)
    due = []
    for g in games:
        if g.get("game_type") != "REG" or (g.get("result") or "").strip():
            continue
        ko = kickoff(g)
        if ko is None:
            continue
        minutes = (ko - now).total_seconds() / 60
        if minutes < MIN_MINUTES_BEFORE:
            continue
        if minutes <= FINAL_REFRESH_MINUTES:
            due.append((g["game_id"], "final pregame refresh"))
        elif minutes <= 60 * LEDGER_WINDOW_HOURS and g["game_id"] not in recorded:
            due.append((g["game_id"], "awaiting first ledger snapshot"))
    return due


def season_of(now):
    d = now.astimezone(ET)
    return d.year if d.month >= 8 else d.year - 1


def decision(event_name, event_schedule, now=None, games=None, recorded=None):
    now = now or datetime.now(timezone.utc)
    season = season_of(now)
    if event_name != "schedule":
        return True, season, f"{event_name or 'manual'} event"
    if event_schedule == DAILY_CRON:
        return True, season, "daily grading and refresh pass"
    try:
        games = fetch_games() if games is None else games
        recorded = recorded_games(current_revision()) if recorded is None else recorded
        due = due_games(games, now, recorded)
    except Exception as exc:  # noqa: BLE001 -- fail open, see module docstring
        return True, season, f"schedule lookup failed; fail-open ({type(exc).__name__})"
    if due:
        return True, season, "; ".join(f"{gid}: {why}" for gid, why in due[:6])
    return False, season, "no unrecorded game within 30h and none within 150 minutes"


def emit_output(name, value):
    value = str(value).replace("\n", " ")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")
    print(f"{name}={value}")


def main():
    should_run, season, reason = decision(
        os.environ.get("EVENT_NAME", "workflow_dispatch"),
        os.environ.get("EVENT_SCHEDULE", ""),
    )
    emit_output("should_run", str(should_run).lower())
    emit_output("season", season)
    emit_output("reason", reason)


if __name__ == "__main__":
    main()
