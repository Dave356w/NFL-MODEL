"""Append-only ATS research shadow captured only from NEW native v1.18 locks.

This never edits the original forward predictions. It starts after the explicit
launch cutoff and additionally requires the *first* v1.18 game snapshot to
have been created very recently and before kickoff; it does not backfill old
locks or create model outputs after an outcome. Price is PROXY -110, not a
historically verified ATS offer. For research only, not production bets.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtri

import fixed_bands
from research import ats_cover_probability as cp

REVISION = "boxscore-composite-v1.18"
START_UTC = dt.datetime.fromisoformat("2026-10-16T00:00:00+00:00")
MAX_CAPTURE_AGE_HOURS = 3.
STATE = "ats_forward_shadow.jsonl"


def utc(value: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timestamps must have UTC offset")
    return t.astimezone(dt.timezone.utc)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{n}: malformed JSON") from e
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{n}: expected object")
        result.append(item)
    return result


def possible_locks(data: Path, now: dt.datetime) -> list[dict]:
    original = read_jsonl(data / "forward_predictions.jsonl")
    earliest = {}
    for r in original:
        if r.get("revision") != REVISION:
            continue
        key = str(r["game_id"])
        if key not in earliest or utc(r["generated_utc"]) < utc(earliest[key]["generated_utc"]):
            earliest[key] = r
    rows = []
    for key, r in sorted(earliest.items()):
        generated, kickoff = utc(r["generated_utc"]), utc(r["kickoff_utc"])
        # Both guards matter: no retroactive declaration of a historical quote.
        age = (now - generated).total_seconds() / 3600.
        if generated < START_UTC or not 0 <= age <= MAX_CAPTURE_AGE_HOURS:
            continue
        if now >= kickoff or generated >= kickoff:
            continue
        if not np.isfinite(float(r.get("spread_line", np.nan))):
            continue
        if not np.isfinite(float(r.get("model_wp", np.nan))):
            continue
        rows.append(r)
    return rows


def kalshi_lock_quote(raw: dict, snapshots: list[dict]) -> dict | None:
    """Price the first available Kalshi-native balanced spread AFTER the model lock.

    The legacy nflverse spread never determines the Kalshi contract or side.
    Only a contemporaneous quote within 30 minutes of the initial model lock
    qualifies; later quotes cannot be attached retrospectively.
    """
    locked, kickoff = utc(raw["generated_utc"]), utc(raw["kickoff_utc"])
    eligible = sorted(
        (r for r in snapshots if r.get("game_id") == raw["game_id"]
         and locked <= utc(r["captured_utc"]) < kickoff
         and (utc(r["captured_utc"]) - locked).total_seconds() <= 1800),
        key=lambda r: utc(r["captured_utc"]),
    )
    for snap in eligible:
        win = snap.get("winner", {})
        try:
            home_win = float(win["home"]["ask"])
            away_win = float(win["away"]["ask"])
        except (ValueError, TypeError, KeyError):
            continue
        if not all(np.isfinite(v) and 0 < v < 1 for v in (home_win, away_win)):
            continue
        if np.isclose(home_win, away_win, atol=1e-9):
            continue
        favorite = raw["home"] if home_win > away_win else raw["away"]
        viable = []
        for rung in snap.get("spread_ladder", []):
            if rung.get("team") != favorite:
                continue
            try:
                strike = float(rung["strike"])
                bid, ask = float(rung["bid"]), float(rung["ask"])
            except (TypeError, ValueError, KeyError):
                continue
            if not (np.isfinite(strike) and np.isclose(strike % 1, .5)
                    and 0 < bid < ask < 1):
                continue
            viable.append((abs((bid + ask) / 2 - .5), strike, rung, bid, ask))
        if not viable:
            continue
        _, strike, rung, bid, ask = min(viable, key=lambda x: (x[0], x[1]))
        home_favorite = favorite == raw["home"]
        return {
            "spread_ticker": rung["ticker"], "captured_utc": snap["captured_utc"],
            "market_spread": strike if home_favorite else -strike,
            "favorite": favorite, "strike": strike,
            "home_ask": ask if home_favorite else 1 - bid,
            "away_ask": 1 - bid if home_favorite else ask,
            "spread_yes_bid": bid, "spread_yes_ask": ask,
            "winner_home_ask": home_win, "winner_away_ask": away_win,
            "price_basis": "Kalshi first post-lock observed order book, <=30m",
            "fee_rate_proxy": .07,
        }
    return None


def freeze(raw: dict, historical: pd.DataFrame, mapping: dict, kalshi_quote: dict | None = None) -> dict:
    year = int(raw["season"])
    if mapping is None or mapping["training_max_season"] >= year:
        raise ValueError("no chronological fixed-band rule")
    fit = cp.fit_prior(historical[historical.season < year], year)
    spread = float(cp.SIGMA * ndtri(np.clip(float(raw["model_wp"]), .005, .995)))
    fixed = float(fixed_bands.apply([spread], mapping)[0])
    line = float(kalshi_quote["market_spread"]) if kalshi_quote else None
    def side(gap):
        return "home" if gap > cp.EPS else "away" if gap < -cp.EPS else ""
    raw_side, fixed_side, probability_side = "", "", ""
    h = a = p = ev_h = ev_a = None
    if line is not None:
        raw_side, fixed_side = side(spread - line), side(fixed - line)
        _, adjusted = cp.distribution(line, spread - line, fit)
        h, a, p = cp.event(adjusted, line)
        home_ask, away_ask = (float(kalshi_quote[k]) for k in ("home_ask", "away_ask"))
        fee_h, fee_a = .07 * (1-home_ask), .07 * (1-away_ask)
        ev_h = h*(1/home_ask - 1-fee_h) - a*(1+fee_h)
        ev_a = a*(1/away_ask - 1-fee_a) - h*(1+fee_a)
        probability_side = ("home" if ev_h > ev_a else "away") if max(ev_h, ev_a) > cp.EPS else ""
    fit_json = json.dumps(fit, sort_keys=True, separators=(",", ":"))
    original_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return {
        "revision": REVISION, "game_id": raw["game_id"], "season": year,
        "week": int(raw["week"]), "away": raw["away"], "home": raw["home"],
        "generated_utc": raw["generated_utc"], "kickoff_utc": raw["kickoff_utc"],
        "market_spread": line, "raw_spread": spread,
        "fixed_band_spread": fixed,
        "raw_side": raw_side, "fixed_band_side": fixed_side,
        "probability_side": probability_side,
        "p_home_cover": h, "p_away_cover": a, "p_push": p,
        "home_ev_kalshi": ev_h, "away_ev_kalshi": ev_a,
        "kalshi_quote": kalshi_quote,
        "quote_basis": "kalshi_main_spread_verified" if kalshi_quote else "no_matching_kalshi_quote",
        "source_snapshot_sha256": hashlib.sha256(original_json.encode()).hexdigest(),
        "calibration_sha256": hashlib.sha256(fit_json.encode()).hexdigest(),
        "fixed_rule": mapping, "beta": fit["beta"],
        "training_max_season": fit["training_max_season"],
        "trained_games": fit["n_training"],
        "research_only": True,
    }


def record(data: Path | str = "data", now: dt.datetime | None = None) -> int:
    """Append only truly new first native locks; never revise stored predictions."""
    data = Path(data)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(dt.timezone.utc)
    possible = possible_locks(data, now)
    if not possible:
        return 0
    target = data / STATE
    stored = read_jsonl(target)
    keys = [(r["revision"], r["game_id"]) for r in stored]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate existing ATS shadow keys")
    existing = set(keys)
    latest = data / "latest"
    source = latest / "fixed_band_ledger.csv"
    rule_file = latest / "fixed_band_rules.json"
    if not source.exists() or not rule_file.exists():
        raise FileNotFoundError("required prior-season ATS research inputs missing")
    prior = pd.read_csv(source)
    rules = {int(r["season"]): r for r in json.loads(rule_file.read_text())}
    quotes = read_jsonl(data / "kalshi_snapshots.jsonl")
    new = []
    for r in possible:
        key = (REVISION, r["game_id"])
        if key in existing:
            continue
        row = freeze(r, prior, rules.get(int(r["season"])), kalshi_lock_quote(r, quotes))
        new.append(row)
        existing.add(key)
    if new:
        # Append + flush rather than overwrite; git workflow commits under data/.
        with target.open("a", encoding="utf-8") as f:
            for row in new:
                f.write(json.dumps(row, sort_keys=True, allow_nan=False)+"\n")
            f.flush()
            os.fsync(f.fileno())
    return len(new)


def graded_view(data: Path | str = "data") -> pd.DataFrame:
    """Join immutable pregame snapshots to current results without modifying them."""
    path = Path(data)
    rows = read_jsonl(path / STATE)
    if not rows:
        return pd.DataFrame()
    ledger = pd.read_csv(path / "forward_ledger.csv")
    g = pd.DataFrame(rows)
    if g.game_id.duplicated().any():
        raise ValueError("duplicated shadow game ID")
    outcomes = ledger[(ledger.revision == REVISION)].copy()
    outcomes = outcomes.sort_values("generated_utc").drop_duplicates("game_id")
    keep = ["game_id", "status", "result"]
    g = g.merge(outcomes[keep], how="left", on="game_id", validate="one_to_one")
    for arm, col in [("raw", "raw_side"), ("fixed_band", "fixed_band_side"),
                     ("cover_probability", "probability_side")]:
        grades, units, asks = [], [], []
        for _, r in g.iterrows():
            side = r[col]
            if side in ("home", "away") and pd.notna(r["result"]) and pd.notna(r["market_spread"]):
                grade, _ = cp.grade(float(r["result"]), float(r["market_spread"]), side)
            else:
                grade = "" if pd.isna(r["result"]) else "S"
            quote = r.get("kalshi_quote")
            ask = (quote or {}).get(side + "_ask") if side in ("home","away") else None
            if not grade or ask is None or grade == "S":
                value = np.nan
            elif grade == "P":
                value = 0.
            else:
                a = float(ask)
                fee_unit = .07*(1-a)
                value = (1/a-1-fee_unit) if grade == "W" else (-1-fee_unit)
            grades.append(grade)
            units.append(value)
            asks.append(ask if ask is not None else np.nan)
        g[arm+"_result"] = grades
        g[arm+"_kalshi_ask"] = asks
        g[arm+"_units_kalshi"] = units
    return g


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--grade-only", action="store_true")
    args = parser.parse_args()
    if not args.grade_only:
        print("new ATS research locks:", record(args.data))
    view = graded_view(args.data)
    if len(view):
        print(view[["game_id", "status", "raw_result", "fixed_band_result",
                    "cover_probability_result"]].to_string(index=False))


if __name__ == "__main__":
    main()
