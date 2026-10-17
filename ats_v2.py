"""Production ATS v2: scoring-aware decision gate with a frozen fixed-band benchmark.

This is an explicitly separate ATS selection policy. The original production
moneyline model, original raw spread, and legacy fixed bands are unchanged.
Fits use *strictly earlier seasons*; historical scores and ATS quotes are
retrospective and assumed -110, not independently verified pregame wagers.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import fixed_bands
from research import ats_cover_probability as probability

POLICY_VERSION = "ats-v2-key-aware-2026-10-16-v1"
WIN_PROFIT = 10.0 / 11.0
EPS = fixed_bands.EPS
MIN_EV = 0.0  # Break-even at proxy -110; no forced selection-coverage target.


def _side(edge: float) -> str:
    if not math.isfinite(edge) or abs(edge) <= EPS:
        return ""
    return "home" if edge > 0 else "away"


def decide(raw: float, mapped: float, line: float, p_home: float,
           p_away: float, p_push: float) -> dict:
    """Decide using a discrete 3-way scoring PMF, not mapped-point direction alone.

    The original and the frozen fixed-band spread may propose opposite teams.
    In a disagreement, select only the candidate with positive probability-
    implied return. Original-side fallback is permitted; an unsupported
    reversal is never forced. Push probability has zero payoff at -110.
    """
    values = [raw, mapped, line, p_home, p_away, p_push]
    if not all(math.isfinite(float(v)) for v in values):
        return dict(side="", source="", reason="unavailable", ev=math.nan)
    if min(p_home, p_away, p_push) < -1e-9 or abs(p_home + p_away + p_push - 1) > 1e-7:
        raise ValueError("Invalid three-way ATS probability distribution")
    raw_side = _side(raw - line)
    mapped_side = _side(mapped - line)
    ev_home = WIN_PROFIT * p_home - p_away
    ev_away = WIN_PROFIT * p_away - p_home
    evs = {"home": ev_home, "away": ev_away}
    candidates = {s for s in (raw_side, mapped_side) if s}
    if not candidates:
        return dict(side="", source="", reason="no_candidate", ev=max(ev_home, ev_away))
    supported = [s for s in candidates if evs[s] > MIN_EV + EPS]
    if not supported:
        return dict(side="", source="", reason="no_positive_ev", ev=max(evs[s] for s in candidates))
    chosen = max(supported, key=lambda s: (evs[s], s == raw_side))
    if chosen == raw_side == mapped_side:
        source = "agreement"
    elif chosen == raw_side:
        source = "original_confirmed"
    else:
        source = "fixed_reversal_confirmed" if raw_side and raw_side != mapped_side else "fixed_only"
    return dict(side=chosen, source=source, reason="", ev=evs[chosen])


def _apply(frame: pd.DataFrame, historical: pd.DataFrame, fits: dict) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        return out
    rows = []
    for r in out.itertuples(index=False):
        year = int(r.season)
        line = float(getattr(r, "spread_line", math.nan))
        raw = float(getattr(r, "model_spread", math.nan))
        fixed = float(getattr(r, "fixed_band_spread", math.nan))
        unavailable = dict(side="", source="", reason="unavailable", ev=math.nan)
        if not all(math.isfinite(v) for v in (line, raw, fixed)):
            decision, probabilities = unavailable, (math.nan, math.nan, math.nan)
        elif year not in fits:
            decision, probabilities = dict(side="", source="", reason="insufficient_prior_seasons",
                                            ev=math.nan), (math.nan, math.nan, math.nan)
        else:
            prior_fit = fits[year]
            _, adjusted = probability.distribution(line, raw - line, prior_fit)
            probabilities = probability.event(adjusted, line)
            decision = decide(raw, fixed, line, *probabilities)
        rows.append(dict(v2_ats_side=decision["side"], v2_ats_source=decision["source"],
                         v2_ats_skip_reason=decision["reason"], v2_ats_ev=decision["ev"],
                         v2_p_home_cover=probabilities[0], v2_p_away_cover=probabilities[1],
                         v2_p_push=probabilities[2], v2_policy=POLICY_VERSION))
    for col in rows[0]:
        out[col] = [row[col] for row in rows]
    out["v2_ats_team"] = np.where(out.v2_ats_side == "home", out.home,
                                  np.where(out.v2_ats_side == "away", out.away, ""))
    out["v2_ats_handicap"] = np.where(out.v2_ats_side == "home", -out.spread_line,
                                     np.where(out.v2_ats_side == "away", out.spread_line, np.nan))
    residual = out.result.to_numpy(float) - out.spread_line.to_numpy(float)
    decided = np.isfinite(residual)
    side_sign = np.where(out.v2_ats_side == "home", 1,
                         np.where(out.v2_ats_side == "away", -1, 0))
    out["v2_ats_result"] = np.where(~decided, "", np.where(side_sign == 0, "S",
                                np.where(np.abs(residual) <= EPS, "P",
                                np.where(side_sign * residual > 0, "W", "L"))))
    out["v2_ats_units"] = np.where(out.v2_ats_result == "W", WIN_PROFIT,
                                 np.where(out.v2_ats_result == "L", -1.0,
                                 np.where(out.v2_ats_result.isin(["P", "S"]), 0., np.nan)))
    return out


def prepare(latest: dict) -> None:
    """Attach v2 policy to historical and current boards without overwriting frozen bands."""
    history = latest.get("fixed_band_ledger", pd.DataFrame())
    if history.empty:
        return
    board = latest.get("board", pd.DataFrame())
    years = set(history.season.astype(int))
    if not board.empty:
        years.update(board.season.astype(int))
    fits = {}
    for year in sorted(years):
        prior = history[history.season < year]
        try:
            fits[year] = probability.fit_prior(prior, year)
        except ValueError as exc:
            # Only insufficient training history may cause a missing fit.
            if "requires >=2 earlier seasons and >=300 games" not in str(exc):
                raise
    latest["ats_v2_ledger"] = _apply(history, history, fits)
    if not board.empty:
        latest["board"] = _apply(board, history, fits)


def summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["season", "opportunities", "bets", "wins",
                                     "losses", "pushes", "skips", "coverage", "units", "roi"])
    d = frame[frame.fixed_band_spread.notna() & frame.result.notna() &
              frame.spread_line.notna()].copy()
    rows = []
    for season, g in [("All", d), *[(str(y), group) for y, group in d.groupby("season")]]:
        r = g.v2_ats_result
        w, l, p, s = [int(r.eq(v).sum()) for v in ("W", "L", "P", "S")]
        n = w+l+p
        if n+s != len(g):
            raise AssertionError("V2 must account for every eligible ATS opportunity")
        units = WIN_PROFIT * w - l
        rows.append(dict(season=season, opportunities=len(g), bets=n, wins=w,
                         losses=l, pushes=p, skips=s, coverage=n/len(g) if len(g) else 0.,
                         units=units, roi=units/n if n else math.nan))
    return pd.DataFrame(rows)
