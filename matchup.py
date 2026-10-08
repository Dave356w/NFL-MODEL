#!/usr/bin/env python3
"""Pre-registered H4: the pass-matchup interaction, recorded at lock for the forward test.

Reporting only (v1.12.3). Nothing here feeds the model, the recipe or
data/forward_predictions.jsonl. For each game newly locked in the forward ledger,
the build records the game's season-centred pass interaction (research Test 24)
from that run's half-life-16 pregame profiles, once, in data/h4_terms.jsonl
(append-only). grade_ledger.py correlates it with the home margin beyond the
market spread. A failure is logged and skipped; it never costs a pregame snapshot.

  term = z(home offense) * z(away defense allowed) - z(away offense) * z(home defense allowed)

on net pass yards per pass play (rates_core); z = (value - mean over this season's
games so far, pregame values only) / SD over 2019-2022 games. Positive favors home.
"""

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("data")
TERMS = DATA / "h4_terms.jsonl"
LEDGER = DATA / "forward_predictions.jsonl"
FEATURES = "pregame_features_half_life_16.csv"
STAT = "net_pass_yards_per_pass_play"
COLS = {(t, role): f"{t}__{role}__rates_core__{STAT}" for t in ("home", "away") for role in ("for", "allowed")}
SD_SEASONS = (2019, 2022)


def pass_terms(features, season, week):
    """{game_id: term} for the games of (season, week). Season means use this season's
    games up to and including `week` (pregame profiles only, no outcomes)."""
    f = features
    ref = f[f.season.between(*SD_SEASONS)]
    cur = f[(f.season == season) & (f.week <= week)]
    games = f[(f.season == season) & (f.week == week)]
    if ref.empty or games.empty:
        return {}
    z = {}
    for key, col in COLS.items():
        sd = ref[col].std()
        z[key] = (games[col] - cur[col].mean()) / sd
    term = z[("home", "for")] * z[("away", "allowed")] - z[("away", "for")] * z[("home", "allowed")]
    return {gid: float(v) for gid, v in zip(games.game_id, term) if np.isfinite(v)}


def load(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def record(outdir, data_dir=DATA, now=None):
    """Append terms for ledger games that kick off after `now` and have no term yet."""
    data_dir = Path(data_dir)
    now = now or dt.datetime.now(dt.timezone.utc)
    have = {r["game_id"] for r in load(data_dir / TERMS.name)}
    todo = {}
    for r in load(data_dir / LEDGER.name):
        if r["game_id"] not in have and r["game_id"] not in todo and dt.datetime.fromisoformat(r["kickoff_utc"]) > now:
            todo[r["game_id"]] = r
    if not todo:
        return 0
    f = pd.read_csv(Path(outdir) / FEATURES, usecols=["game_id", "season", "week", *COLS.values()])
    new, cache = [], {}
    for gid, r in todo.items():
        key = (int(r["season"]), int(r["week"]))
        if key not in cache:
            cache[key] = pass_terms(f, *key)
        if gid in cache[key]:
            new.append({"game_id": gid, "season": key[0], "week": key[1], "kickoff_utc": r["kickoff_utc"],
                        "captured_utc": now.isoformat(), "pass_term": round(cache[key][gid], 6),
                        "source": f"{FEATURES} season-to-date centring, 2019-22 SD"})
    if new:
        with (data_dir / TERMS.name).open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, allow_nan=False) + "\n")
    return len(new)


def safe_record(outdir, data_dir=DATA, now=None):
    """record() that never raises: the build must not lose a pregame snapshot to H4."""
    try:
        n = record(outdir, data_dir, now)
        print(f"h4: {n} pass-matchup term(s) recorded")
        return n
    except Exception as exc:  # noqa: BLE001 - reporting only; never fail the build
        print(f"h4: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 0


def partial_r(term, result, spread, reps=2000, seed=20261005):
    """Partial correlation of term with result controlling for spread, and a bootstrap 95% CI."""
    x, y, s = (np.asarray(v, float) for v in (term, result, spread))
    def resid(v, s):
        X = np.column_stack([np.ones(len(v)), s])
        return v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
    def r(i):
        a, b = resid(x[i], s[i]), resid(y[i], s[i])
        return float(np.corrcoef(a, b)[0, 1])
    n = len(x)
    if n < 10:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    bs = [r(rng.integers(0, n, n)) for _ in range(reps)]
    return r(np.arange(n)), float(np.nanquantile(bs, .025)), float(np.nanquantile(bs, .975))
