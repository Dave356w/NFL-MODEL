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
from ats_locks import ADOPTED_UTC
from research import ats_cover_probability as cp

REVISION = "boxscore-composite-v1.18"
START_UTC = dt.datetime.fromisoformat("2026-10-17T05:31:00+00:00")
MAX_CAPTURE_AGE_HOURS = 3.
STATE = "ats_forward_shadow.jsonl"
POLICY_VERSION = fixed_bands.POLICY_VERSION
EPS = fixed_bands.EPS


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
        if generated < START_UTC or generated >= ADOPTED_UTC or not 0 <= age <= MAX_CAPTURE_AGE_HOURS:
            continue
        if now >= kickoff or generated >= kickoff:
            continue
        if not np.isfinite(float(r.get("spread_line", np.nan))):
            continue
        if not np.isfinite(float(r.get("model_wp", np.nan))):
            continue
        rows.append(r)
    return rows


def freeze(raw: dict, historical: pd.DataFrame, mapping: dict,
           archived_utc: dt.datetime | None = None) -> dict:
    year = int(raw["season"])
    if mapping is None or mapping["training_max_season"] >= year:
        raise ValueError("no chronological fixed-band rule")
    if mapping.get("policy_version") != POLICY_VERSION or mapping.get("method") != fixed_bands.METHOD:
        raise ValueError("mapping does not match the current median-MOV policy")
    fit = cp.fit_prior(historical[historical.season < year], year)
    spread = float(cp.SIGMA * ndtri(np.clip(float(raw["model_wp"]), .005, .995)))
    line = float(raw["spread_line"])
    fixed = float(fixed_bands.apply([spread], mapping)[0])
    base, adjusted = cp.distribution(line, spread - line, fit)
    mh, ma, mp = cp.event(base, line)
    h, a, p = cp.event(adjusted, line)
    ev_h, ev_a = cp.WIN_PROFIT*h-a, cp.WIN_PROFIT*a-h
    probability_side = ("home" if ev_h > ev_a else "away") if max(ev_h, ev_a) > cp.EPS else ""
    def side(gap):
        return "home" if gap > cp.EPS else "away" if gap < -cp.EPS else ""
    fit_json = json.dumps(fit, sort_keys=True, separators=(",", ":"))
    original_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    fixed_side = side(fixed - line)
    return {
        "revision": REVISION, "game_id": raw["game_id"], "season": year,
        "week": int(raw["week"]), "away": raw["away"], "home": raw["home"],
        "generated_utc": raw["generated_utc"], "kickoff_utc": raw["kickoff_utc"],
        "archived_utc": archived_utc.isoformat() if archived_utc is not None else None,
        "policy_version": POLICY_VERSION, "zero_edge_tolerance": EPS,
        "market_spread": line, "raw_spread": spread,
        "fixed_band_spread": fixed,
        "fixed_band_edge": fixed - line,
        "selected_side": fixed_side,
        "skip_reason": "zero_edge" if not fixed_side else None,
        "raw_side": side(spread-line), "fixed_band_side": fixed_side,
        "probability_side": probability_side,
        "p_home_cover": h, "p_away_cover": a, "p_push": p,
        "market_p_home_cover": mh, "market_p_away_cover": ma, "market_p_push": mp,
        "home_ev_proxy_minus110": ev_h, "away_ev_proxy_minus110": ev_a,
        "assumed_price": -110, "quote_basis": "unverified_proxy_only",
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
    new = []
    for r in possible:
        key = (REVISION, r["game_id"])
        if key in existing:
            continue
        row = freeze(r, prior, rules.get(int(r["season"])), archived_utc=now)
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
        graded = [cp.grade(float(r["result"]), float(r["market_spread"]), r[col])
                  if pd.notna(r["result"]) else ("", np.nan)
                  for _, r in g.iterrows()]
        g[arm+"_result"] = [v[0] for v in graded]
        g[arm+"_units_proxy_minus110"] = [v[1] for v in graded]
    # Proper scores are calculated for every completed game (including
    # policy skips and actual ATS pushes), not only the selected bets.
    # The three events are mutually exclusive: home cover, away cover, push.
    delta = pd.to_numeric(g["result"], errors="coerce") - pd.to_numeric(g["market_spread"], errors="coerce")
    outcome = np.where(np.abs(delta) <= EPS, 2, np.where(delta > 0, 0, 1))
    targets = np.eye(3)[outcome]
    for name, cols in [
        ("model", ["p_home_cover", "p_away_cover", "p_push"]),
        ("market", ["market_p_home_cover", "market_p_away_cover", "market_p_push"]),
    ]:
        # Older research locks did not store a market probability control;
        # leave their market proper scores unavailable rather than fabricate it.
        if not set(cols).issubset(g.columns):
            continue
        p = g[cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        valid = np.isfinite(delta.to_numpy(float)) & np.isfinite(p).all(axis=1)
        valid &= np.all((p >= 0) & (p <= 1), axis=1) & np.isclose(p.sum(axis=1), 1., atol=1e-8)
        observed = p[np.arange(len(g)), outcome]
        g[name+"_ats_3way_log_loss"] = np.where(
            valid, -np.log(np.clip(observed, 1e-15, 1.)), np.nan)
        g[name+"_ats_3way_brier"] = np.where(
            valid, ((p - targets)**2).sum(axis=1), np.nan)
    return g


def summary(view: pd.DataFrame) -> pd.DataFrame:
    """All game opportunities, policy skips and separate three-way scores."""
    if view.empty:
        return pd.DataFrame()
    done = view[pd.to_numeric(view["result"], errors="coerce").notna()]
    rows = []
    done = done.copy()
    if 'policy_version' not in done:
        done['policy_version'] = 'legacy-unversioned'
    done['policy_version'] = done.policy_version.fillna('legacy-unversioned')
    for policy_version, version_games in done.groupby('policy_version', sort=True):
        for season, games in [("All", version_games), *[(str(k), v) for k, v in version_games.groupby("season")]]:
            if games.empty:
                continue
            for arm in ("raw", "fixed_band", "cover_probability"):
                result = games[arm+"_result"]
                bets = int(result.ne("S").sum())
                units = float(games[arm+"_units_proxy_minus110"].sum())
                rows.append(dict(season=season, policy=arm, policy_version=policy_version, opportunities=len(games), selections=bets,
                    skips=int(result.eq("S").sum()), wins=int(result.eq("W").sum()),
                    losses=int(result.eq("L").sum()), pushes=int(result.eq("P").sum()),
                    selection_rate=bets/len(games), units_proxy_minus110=units,
                    roi_proxy_minus110=units/bets if bets else np.nan,
                    model_3way_ll=games["model_ats_3way_log_loss"].mean()
                        if "model_ats_3way_log_loss" in games else np.nan,
                    market_3way_ll=games["market_ats_3way_log_loss"].mean()
                        if "market_ats_3way_log_loss" in games else np.nan,
                    model_3way_brier=games["model_ats_3way_brier"].mean()
                        if "model_ats_3way_brier" in games else np.nan,
                    market_3way_brier=games["market_ats_3way_brier"].mean()
                        if "market_ats_3way_brier" in games else np.nan))
    return pd.DataFrame(rows)


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
        print(summary(view).to_string(index=False))


if __name__ == "__main__":
    main()
