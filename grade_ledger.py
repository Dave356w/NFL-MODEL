#!/usr/bin/env python3
"""Grade the forward ledger: data/forward_predictions.jsonl -> data/forward_ledger.csv
and data/ledger_report.txt.

The JSONL is the record of truth and is never rewritten here: it holds each
game's FIRST pregame snapshot per experiment, written by nfl_model.record_forward.
This script only joins final scores onto it and grades the headline bet:
1u flat on the model's side at the moneyline saved in the snapshot, next to
the same-row market-favorite baseline. Re-running is idempotent; a game
with no final score stays `pending`, a tie is `tie` and is excluded from W/L and
probability scores (the model's fit and backtests exclude ties the same way).

    python grade_ledger.py            # schedule from nflverse games.csv
"""

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

import kalshi as k
import matchup
import nfl_model as m
import totals

DATA = Path("data")
LEDGER = DATA / "forward_predictions.jsonl"
GRADED = DATA / "forward_ledger.csv"
REPORT = DATA / "ledger_report.txt"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
COLUMNS = ["experiment", "revision", "season", "week", "game_id", "away", "home",
           "kickoff_utc", "generated_utc", "lead_hours", "model_wp", "market_wp",
           "homefield_wp", "spread_line", "home_moneyline", "away_moneyline",
           "away_injury_report", "home_injury_report",
           "away_score", "home_score", "result", "home won", "status",
           "model_pick", "model_hit", "market_hit", "model_log_loss", "market_log_loss",
           "model_brier", "market_brier", "bet_side", "bet_team", "bet_price", "bet_band",
           "bet_q", "bet_result", "units", "null_ev", "fav_units",
           "model_spread", "spread_gap", "ats_side", "ats_result",
           "kalshi_captured_utc", "kalshi_lag_hours", "kalshi_home_mid", "kalshi_side_ask", "kalshi_units",
           "kalshi_null", "kalshi_fav_units", "alt_rule", "alt_team", "alt_strike", "alt_ask", "alt_result",
           "alt_units", "alt_fav_units", "ladder_ticker", "ladder_team", "ladder_strike", "ladder_est",
           "ladder_ask", "ladder_edge", "ladder_result", "ladder_units", "ladder_null", "h4_pass_term",
           "close_home_moneyline", "close_away_moneyline", "close_q", "clv_pp", "fp_wp", "fp_log_loss"]
ATS_GAP_POINTS = 3.  # diagnostic split; chosen after seeing held-out 2023-25 (v1.12.1)
ATS_BREAKEVEN = 110 / 210  # win rate needed at -110 on both sides
# research/PREREGISTRATION.md, addendum 2026-10-13: H1/H2 apply to the forward rows of v1.16 under
# its frozen configuration for games from 2026 week 6 on (cumulative across seasons). Changing
# REVISION, the config signature or the recipe ends the sample. Earlier samples (to v1.12) ended.
H12_REVISION = "boxscore-composite-v1.16"
FP_REVISION = "boxscore-composite-v1.16"  # v1.16.2 favorite-confidence penalty applies to v1.16 only
H12_EXPERIMENT = ("9dad9b9ad0eda3c043c4227d211e8c1cb460beaac6c649f09787c296a62dcd26:"
                  "rates_core_avail_cs_peaks_nosacks_h8_r0.1_market_product_1sd_i0.1:")  # + season
H12_FROM = (2026, 6)  # (season, week): the first week after the addendum
H1_MIN_GAP = .17
# research/PREREGISTRATION.md, addendum 2026-10-15: H9 (moneyline vs spread disagreement), one row per
# game from the first production snapshot (v1.18 on; prices only, so a model change does not end it).
# Append-only: add every new production REVISION here, never remove one (a test checks m.REVISION).
H9_PRODUCTION = ("boxscore-composite-v1.18",)
H9_FROM = (2026, 6)
H9_T = 0.11133        # 75th percentile of |dis| on 2013-2026, outcome-free (research/ML_SPREAD_2006_12.md)
H9_CLIP = 1e-4
H9_MIN_GAMES, H9_MIN_WEEKS = 30, 10  # below these the interim b and its cluster SE are not printed


def load_records(path=LEDGER):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_results(url=SCHEDULE_URL):
    """Final scores, plus nflverse's moneylines after the game (its closing line; no quote timestamp)."""
    s = pd.read_csv(url, usecols=["game_id", "away_score", "home_score", "result", "away_moneyline", "home_moneyline"])
    return s.rename(columns={"away_moneyline": "close_away_moneyline", "home_moneyline": "close_home_moneyline"})


def grade(records, results, kalshi=None, ladder=None, h4=None):
    """Flat graded frame, one row per ledger snapshot, newest kickoff first. `kalshi` is the
    list of data/kalshi_snapshots.jsonl records (secondary prices; optional); `ladder` the
    loaded H3 reference table (kalshi.load_ladder_table; optional)."""
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    rows = []
    for r in records:
        inj = r.get("injury_report") or {}
        rows.append({"experiment": r["experiment"], "revision": r.get("revision"),
                     "season": r["season"], "week": r["week"], "game_id": r["game_id"],
                     "away": r["away"], "home": r["home"], "kickoff_utc": r["kickoff_utc"],
                     "generated_utc": r["generated_utc"], "model_wp": r["model_wp"],
                     "market_wp": r.get("market_wp"), "homefield_wp": r.get("homefield_wp"),
                     "spread_line": r.get("spread_line"),
                     "home_moneyline": r.get("home_moneyline"), "away_moneyline": r.get("away_moneyline"),
                     "away_injury_report": inj.get("away"), "home_injury_report": inj.get("home")})
    g = pd.DataFrame(rows)
    g["lead_hours"] = ((pd.to_datetime(g.kickoff_utc, utc=True) - pd.to_datetime(g.generated_utc, utc=True))
                       .dt.total_seconds() / 3600).round(1)
    res = results.drop_duplicates("game_id")
    g = g.merge(res, on="game_id", how="left", validate="many_to_one")
    g["home won"] = g.result.map(m.won)
    g["status"] = np.where(g.result.isna(), "pending", np.where(g.result == 0, "tie", "graded"))
    y = g["home won"].where(g.status == "graded")
    p = g.model_wp.astype(float)
    q = pd.to_numeric(g.market_wp, errors="coerce")
    g["model_pick"] = np.where(np.isclose(p, .5), "", np.where(p > .5, g.home, g.away))
    g["model_hit"] = np.where(y.notna() & ~np.isclose(p, .5), ((p > .5) == (y == 1)).astype(float), np.nan)
    g["market_hit"] = np.where(y.notna() & q.notna() & ~np.isclose(q.fillna(.5), .5),
                               ((q > .5) == (y == 1)).astype(float), np.nan)
    clip = lambda v: np.clip(v, 1e-12, 1 - 1e-12)
    g["model_log_loss"] = np.where(y.notna(), -(y * np.log(clip(p)) + (1 - y) * np.log(clip(1 - p))), np.nan)
    g["market_log_loss"] = np.where(y.notna() & q.notna(),
                                    -(y * np.log(clip(q)) + (1 - y) * np.log(clip(1 - q))), np.nan)
    # v1.16.2, reporting only: favorite-confidence penalty on v1.16 rows (research/FAVORITE_PENALTY.md)
    fp = pd.Series(m.favorite_penalized_wp(p, q), index=g.index).where(g.revision.eq(FP_REVISION) & q.notna())
    g["fp_wp"] = fp
    g["fp_log_loss"] = np.where(y.notna() & fp.notna(), -(y * np.log(clip(fp)) + (1 - y) * np.log(clip(1 - fp))), np.nan)
    g["model_brier"] = np.where(y.notna(), (p - y) ** 2, np.nan)
    g["market_brier"] = np.where(y.notna() & q.notna(), (q - y) ** 2, np.nan)
    hw = g["home won"].where(g.status != "pending")
    bets = m.flat_bets(g.assign(**{"home won": hw}), "model_wp")
    fav = m.flat_bets(g.assign(**{"home won": hw, "market_ml_wp": m.market_ml_wp(g)}), "market_ml_wp")
    g["bet_side"], g["bet_price"], g["bet_band"], g["bet_q"] = bets.side, bets.price, bets.band, bets.q
    g["bet_team"] = np.where(bets.side == "home", g.home, np.where(bets.side == "away", g.away, ""))
    g["bet_result"], g["units"], g["null_ev"] = bets.result, bets.units, bets.null_ev
    g["fav_units"] = fav.units.where(bets.units.notna())  # same rows as the model's bets
    g["model_spread"], g["spread_gap"], g["ats_side"], g["ats_result"] = ats(g)
    close_cols = ["close_home_moneyline", "close_away_moneyline"]
    for c in close_cols:
        g[c] = pd.to_numeric(g[c], errors="coerce").astype(float) if c in g else np.nan
    g.loc[g.status == "pending", close_cols] = np.nan  # a pre-game price is not a close
    g["close_q"], g["clv_pp"] = closing_value(g)
    g = g.join(kalshi_grades(g, kalshi or [], ladder))
    g["h4_pass_term"] = g.game_id.map({r["game_id"]: r["pass_term"] for r in (h4 or [])})
    g = g.sort_values(["kickoff_utc", "game_id"], ascending=[False, True]).reset_index(drop=True)
    return g[COLUMNS]


def ats(g):
    """Diagnostic, not the goal metric (v1.12.1): the model-implied spread, its gap to
    the snapshot spread_line (positive = model likes home more), the side that gap
    takes against the snapshot spread, and W/L/P against that spread once final."""
    sp = m.implied_spread(g.model_wp)
    line = pd.to_numeric(g.spread_line, errors="coerce").to_numpy(float)
    gap = sp - line
    side = np.where(~np.isfinite(gap) | np.isclose(np.nan_to_num(gap), 0), "",
                    np.where(gap > 0, "home", "away"))
    cover = pd.to_numeric(g.result, errors="coerce").to_numpy(float) - line  # home margin over the line
    res = np.where((side == "") | ~np.isfinite(cover), "",
                   np.where(np.isclose(np.nan_to_num(cover), 0), "P",
                            np.where((cover > 0) == (side == "home"), "W", "L")))
    return sp, gap, side, res


def closing_value(g):
    """Diagnostic, not the goal metric: nflverse's no-vig closing home probability (its
    moneylines once the game is over) and how far the model's side moved from the snapshot
    quote, in percentage points. Positive = the market moved toward the model's side."""
    close = pd.DataFrame({"home_moneyline": g.get("close_home_moneyline", np.nan),
                          "away_moneyline": g.get("close_away_moneyline", np.nan)}, index=g.index)
    close_q = pd.Series(m.market_ml_wp(close), index=g.index).where(g.status != "pending")
    lock_q = pd.Series(m.market_ml_wp(g), index=g.index)
    sign = np.where(g.bet_side.eq("home"), 1., np.where(g.bet_side.eq("away"), -1., np.nan))
    return close_q, 100 * sign * (close_q - lock_q)


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def clv_summary(part):
    """Mean closing-line value on the model's side, the same on games where the model
    backs the market underdog, and the slope of the line move on the model's departure."""
    d = part[part.clv_pp.notna()]
    if not len(d):
        return {"n": 0}
    v = d.clv_pp.astype(float)
    lock_q = m.market_ml_wp(d)
    dog = d.bet_side.eq(np.where(lock_q > .5, "away", "home")).to_numpy()
    out = {"n": len(d), "mean": float(v.mean()), "se": float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else np.nan,
           "dog_n": int(dog.sum()), "dog_mean": float(v[dog].mean()) if dog.any() else np.nan,
           "slope": np.nan, "slope_se": np.nan}
    x = _logit(d.model_wp) - _logit(lock_q)
    y = _logit(d.close_q) - _logit(lock_q)
    if len(d) >= 3 and np.var(x) > 0:
        b, a = np.polyfit(x, y, 1)
        resid = y - (a + b * x)
        out["slope"] = float(b)
        out["slope_se"] = float(np.sqrt(resid @ resid / (len(d) - 2) / np.sum((x - x.mean()) ** 2)))
    return out


def h12_rows(g):
    """The registered H1/H2 sample: the first v1.16 snapshot per game under its frozen
    configuration, from 2026 week 6, with the no-vig q from the snapshot moneylines."""
    season, week = H12_FROM
    later = (g.season > season) | ((g.season == season) & (g.week >= week))
    d = g[g.revision.eq(H12_REVISION) & g.experiment.astype(str).str.startswith(H12_EXPERIMENT) & later]
    d = d.sort_values("generated_utc").drop_duplicates("game_id").copy()
    d["h_q"] = m.market_ml_wp(d)
    return d[np.isfinite(d.h_q)]


def _subset_summary(rows, d):
    """Flat 1u on the model's side over the qualifying rows d of the registered sample `rows`:
    ROI with its null and the same-row favorite, and the paired log-loss gain over q."""
    b = d[d.units.notna()]
    out = m.roi_summary(pd.DataFrame({"result": b.bet_result, "units": b.units, "q": b.bet_q, "null_ev": b.null_ev}))
    out["fav_roi"] = float(b.fav_units.mean()) if len(b) else np.nan
    s = b[b.status == "graded"]
    y, p, q = s["home won"].astype(float), s.model_wp.astype(float), s.h_q.astype(float)
    gain = -(y * np.log(q) + (1 - y) * np.log(1 - q)) + (y * np.log(p) + (1 - y) * np.log(1 - p))
    out["ll_gain"] = float(gain.mean()) if len(gain) else np.nan
    out["rows"] = int(len(rows))
    return out


def _subset_text(s):
    if not s["bets"]:
        return ""
    return (f"; {s['wins']}-{s['losses']}-{s['pushes']}, {s['units']:+.2f}u, ROI {100 * s['roi']:+.1f}%"
            + (f" +/- {100 * s['roi_se']:.1f}" if np.isfinite(s["roi_se"]) else "")
            + f", null {100 * s['null_roi']:+.1f}%, same-row favorite {100 * s['fav_roi']:+.1f}%"
            + (f", log-loss gain vs q {s['ll_gain']:+.4f}" if np.isfinite(s["ll_gain"]) else ""))


def h1_summary(g):
    """Pre-registered H1: rows with |model_wp - q| > 0.17, flat 1u on the model's side."""
    rows = h12_rows(g)
    return _subset_summary(rows, rows[(rows.model_wp - rows.h_q).abs() > H1_MIN_GAP])


def h6_summary(g):
    """Pre-registered H6, on the H1/H2 sample: rows where the model backs the market underdog
    (the no-vig probability of its side, from the snapshot moneylines, is below 0.5)."""
    rows = h12_rows(g)
    return _subset_summary(rows, rows[pd.to_numeric(rows.bet_q, errors="coerce") < .5])


def h1_verdict(s):
    """Decision rule fixed in research/PREREGISTRATION.md (H1)."""
    if not s["bets"]:
        return "no qualifying graded rows"
    edge = s["roi"] - s["null_roi"]
    if np.isfinite(s["roi_se"]) and edge >= 2 * s["roi_se"]:
        return "supported (ROI minus null >= 2 SE)"
    if s["bets"] >= 50 and s["roi"] <= s["null_roi"]:
        return "falsified (n >= 50, ROI at or below the null)"
    return "unresolved"


def h6_verdict(s):
    """Decision rule fixed in research/PREREGISTRATION.md (H6)."""
    if s["bets"] < 10 or not np.isfinite(s["roi_se"]):
        return "no verdict before 10 graded bets"
    if s["roi"] - s["null_roi"] >= 2 * s["roi_se"]:
        return "supported (ROI minus null >= 2 SE)"
    if s["bets"] >= 50 and s["roi"] <= s["null_roi"]:
        return "falsified (n >= 50, ROI at or below the null)"
    return "unresolved"


def h2_summary(g):
    """Pre-registered H2: per-game log-loss gain over q, weeks 14-18 against weeks 5-13;
    flat 1u ROI per group, with its null and the same-row favorite, as secondary."""
    rows = h12_rows(g)
    d = rows[rows.status == "graded"].copy()
    y, p, q = d["home won"].astype(float), d.model_wp.astype(float), d.h_q.astype(float)
    d["gain"] = -(y * np.log(q) + (1 - y) * np.log(1 - q)) + (y * np.log(p) + (1 - y) * np.log(1 - p))
    bets = rows[rows.units.notna()]

    def grp(lo, hi):
        v = d.loc[d.week.between(lo, hi), "gain"].astype(float)
        b = bets[bets.week.between(lo, hi)]
        r = m.roi_summary(pd.DataFrame({"result": b.bet_result, "units": b.units, "q": b.bet_q, "null_ev": b.null_ev}))
        return {"n": len(v), "mean": float(v.mean()) if len(v) else np.nan,
                "se": float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else np.nan,
                "bets": r["bets"], "roi": r["roi"], "roi_se": r["roi_se"], "null_roi": r["null_roi"],
                "fav_roi": float(b.fav_units.mean()) if len(b) else np.nan}
    out = {"mid": grp(5, 13), "late": grp(14, 18), "late_14_17": grp(14, 17), "week_18": grp(18, 18)}
    mid, late = out["mid"], out["late"]
    out["diff"] = late["mean"] - mid["mean"] if mid["n"] and late["n"] else np.nan
    out["diff_se"] = float(np.hypot(mid["se"], late["se"])) if mid["n"] > 1 and late["n"] > 1 else np.nan
    return out


def h2_verdict(s):
    """Decision rule fixed in research/PREREGISTRATION.md (H2)."""
    if not s["late"]["n"] or not s["mid"]["n"]:
        return "no late-season rows" if s["mid"]["n"] else "no graded rows"
    if not np.isfinite(s["diff_se"]):
        return "unresolved (too few rows for a standard error)"
    if s["diff"] <= -2 * s["diff_se"]:
        return "supported (late minus mid <= -2 SE)"
    if s["diff"] >= 0:
        return "falsified (late minus mid >= 0)"
    return "unresolved"


def kalshi_units(won, ask):
    """1u staked at a Kalshi ask: win (or a tie's $0.50) per contract minus the estimated
    taker fee, FEE_RATE * P * (1 - P) per contract, i.e. FEE_RATE * (1 - P) per unit staked."""
    if not np.isfinite(ask) or not np.isfinite(won):
        return np.nan
    return won / ask - 1 - k.FEE_RATE * (1 - ask)


def kalshi_grades(g, snaps, ladder=None):
    """Secondary prices from Kalshi captures (v1.12.2, reporting only).

    Each snapshot uses its game's first capture at or after its lock (generated_utc).
    Snapshots locked after the game's last capture fall back to that earlier capture;
    kalshi_lag_hours is then negative and the report counts them.

    kalshi_*: 1u on the model's side at that side's game-winner ask, beside the Kalshi
    favorite (higher mid) at its ask on the same rows; kalshi_null is the ROI if the
    normalized Kalshi mid were exactly right (negative by the spread and fee).
    alt_*: the alt-line rule. When the model and the market spread make the same team
    the favorite and the model's spread is smaller, buy "favorite wins by over X.5" at
    the largest Kalshi strike below the model's spread (the game-winner market when no
    strike is below it). alt_fav_units: the favorite's game-winner ask on the same rows.
    ladder_*: pre-registered H3 (research/PREREGISTRATION.md). The one Kalshi rung whose
    frozen reference probability (kalshi_ladder_reference.csv, 2006-2024 margins at the
    snapshot's no-vig moneyline) beats the ask by the most after the fee, if by >= $0.03;
    ladder_null is the ROI if that rung's Kalshi mid were exactly right."""
    by = {}
    for s in sorted(snaps or [], key=lambda s: pd.Timestamp(s["captured_utc"])):
        by.setdefault(s["game_id"], []).append(s)
    rows = []
    for r in g.itertuples(index=False):
        caps, out = by.get(r.game_id, []), {}
        lock = pd.Timestamp(r.generated_utc)
        s = next((c for c in caps if pd.Timestamp(c["captured_utc"]) >= lock), caps[-1] if caps else None)
        if s:
            hq, aq = s["winner"].get("home"), s["winner"].get("away")
            mids = {sd: (q["bid"] + q["ask"]) / 2 for sd, q in (("home", hq), ("away", aq)) if q}
            hm = mids["home"] / (mids["home"] + mids["away"]) if len(mids) == 2 else np.nan
            res = float(r.result) if pd.notna(r.result) else np.nan
            hw = np.nan if not np.isfinite(res) else 1. if res > 0 else 0. if res < 0 else .5
            lag = (pd.Timestamp(s["captured_utc"]) - pd.Timestamp(r.generated_utc)).total_seconds() / 3600
            out = {"kalshi_captured_utc": s["captured_utc"], "kalshi_lag_hours": round(lag, 2), "kalshi_home_mid": hm}
            p = float(r.model_wp)
            if not np.isclose(p, .5) and np.isfinite(hm):
                side = "home" if p > .5 else "away"
                q = s["winner"][side]["ask"]
                won = hw if side == "home" else 1 - hw
                qs = hm if side == "home" else 1 - hm
                out.update(kalshi_side_ask=q, kalshi_units=kalshi_units(won, q),
                           kalshi_null=qs / q - 1 - k.FEE_RATE * (1 - q))
                fav = "home" if hm >= .5 else "away"
                out["kalshi_fav_units"] = kalshi_units(hw if fav == "home" else 1 - hw, s["winner"][fav]["ask"])
            ms, line = float(r.model_spread), pd.to_numeric(r.spread_line, errors="coerce")
            if np.isfinite(line) and line != 0 and np.sign(ms) == np.sign(line) and abs(ms) < abs(line):
                fside = "home" if line > 0 else "away"
                team = r.home if fside == "home" else r.away
                strikes = [x for x in s["spread_ladder"] if x["team"] == team and x["strike"] < abs(ms)]
                pick = max(strikes, key=lambda x: x["strike"]) if strikes else {"strike": 0., **s["winner"][fside]}
                margin = res if fside == "home" else -res
                won = np.nan if not np.isfinite(res) else (1. if margin > pick["strike"] else
                                                          .5 if pick["strike"] == 0 and margin == 0 else 0.)
                out.update(alt_rule=True, alt_team=team, alt_strike=pick["strike"], alt_ask=pick["ask"],
                           alt_result="" if not np.isfinite(won) else "W" if won == 1 else "P" if won == .5 else "L",
                           alt_units=kalshi_units(won, pick["ask"]),
                           alt_fav_units=kalshi_units(np.nan if not np.isfinite(res) else 1. if margin > 0 else .5 if margin == 0 else 0.,
                                                      s["winner"][fside]["ask"]))
        if s and ladder is not None:
            pick = k.ladder_pick(s, r.home_moneyline, r.away_moneyline, ladder)
            if pick:
                res = float(r.result) if pd.notna(r.result) else np.nan
                margin = res if pick["side"] == "home" else -res
                won = np.nan if not np.isfinite(res) else (1. if margin > pick["strike"] else
                                                          .5 if pick["strike"] == 0 and margin == 0 else 0.)
                a = pick["ask"]
                out.update(ladder_ticker=pick["ticker"], ladder_team=pick["team"], ladder_strike=pick["strike"],
                           ladder_est=pick["est"], ladder_ask=a, ladder_edge=pick["edge"],
                           ladder_result="" if not np.isfinite(won) else "W" if won == 1 else "P" if won == .5 else "L",
                           ladder_units=kalshi_units(won, a), ladder_null=pick["mid"] / a - 1 - k.FEE_RATE * (1 - a))
        rows.append(out)
    cols = [c for c in COLUMNS if c.startswith(("kalshi_", "alt_", "ladder_"))]
    out = pd.DataFrame(rows, index=g.index, columns=cols)
    out["alt_rule"] = out.alt_rule.eq(True)
    return out


def kalshi_summary(g, col, base):
    """Units/ROI for `col` beside `base` on the same graded rows."""
    b = g[g[col].notna() & g[base].notna()]
    u = b[col].astype(float)
    return {"n": len(b), "wins": int((u > 0).sum()), "losses": int((u < -.5).sum()),
            "units": float(u.sum()), "roi": float(u.mean()) if len(b) else np.nan,
            "roi_se": float(u.std(ddof=1) / np.sqrt(len(b))) if len(b) > 1 else np.nan,
            "base_units": float(b[base].sum()), "base_roi": float(b[base].mean()) if len(b) else np.nan}


def ats_summary(g, min_gap=0.):
    """W-L-P against the snapshot spread on the model's side, for |spread_gap| >= min_gap."""
    b = g[(g.ats_result != "") & (g.spread_gap.abs() >= min_gap)]
    w, l = int((b.ats_result == "W").sum()), int((b.ats_result == "L").sum())
    lo, hi = m.wilson(w, w + l)
    return {"wins": w, "losses": l, "pushes": int((b.ats_result == "P").sum()),
            "win_pct": w / (w + l) if w + l else np.nan, "lo": lo, "hi": hi}


def roi(g):
    """Headline: 1u flat on the model's side at the saved moneyline. The market-favorite
    baseline is scored on the same rows (games where both have a priced bet)."""
    b = g[g.units.notna() & g.fav_units.notna()] if len(g) else g
    bets = pd.DataFrame({"result": b.get("bet_result", []), "units": b.get("units", []),
                         "q": b.get("bet_q", []), "null_ev": b.get("null_ev", [])})
    out = m.roi_summary(bets)
    out["fav_units"] = float(b.fav_units.sum()) if len(b) else 0.
    out["fav_roi"] = float(b.fav_units.mean()) if len(b) else np.nan
    return out


def summary(g):
    """Headline numbers on ONE row set: graded games with a market probability."""
    s = g[(g.status == "graded") & g.market_wp.notna()]
    out = {"snapshots": int(len(g)), "pending": int((g.status == "pending").sum()),
           "ties": int((g.status == "tie").sum()), "graded": int((g.status == "graded").sum()),
           "scored": int(len(s)), "roi": roi(g)}
    if len(s):
        mh, kh = s.model_hit.dropna(), s.market_hit.dropna()
        d = (s.market_log_loss - s.model_log_loss).to_numpy(float)
        out.update(model_wins=int(mh.sum()), model_losses=int(len(mh) - mh.sum()),
                   market_wins=int(kh.sum()), market_losses=int(len(kh) - kh.sum()),
                   model_log_loss=float(s.model_log_loss.mean()), market_log_loss=float(s.market_log_loss.mean()),
                   ll_gain=float(d.mean()), ll_gain_se=float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else np.nan,
                   model_brier=float(s.model_brier.mean()), market_brier=float(s.market_brier.mean()))
        f = s[s.fp_log_loss.notna()] if "fp_log_loss" in s else s.iloc[:0]
        if len(f):
            e = (f.model_log_loss - f.fp_log_loss).to_numpy(float)
            out.update(fp_n=int(len(f)), fp_log_loss=float(f.fp_log_loss.mean()),
                       fp_model_log_loss=float(f.model_log_loss.mean()), fp_gain=float(e.mean()),
                       fp_gain_se=float(e.std(ddof=1) / np.sqrt(len(e))) if len(e) > 1 else np.nan,
                       fp_changed=int((~np.isclose(f.fp_wp.astype(float), f.model_wp.astype(float))).sum()),
                       fp_gain_cluster_se=_cluster_se(e, f.season.astype(str) + "_" + f.week.astype(str)),
                       fp_clusters=int((f.season.astype(str) + "_" + f.week.astype(str)).nunique()))
    return out


def _cluster_se(v, groups):
    """SE of the mean of v with season-week clusters; NaN below two clusters."""
    v = np.asarray(v, float)
    c = pd.Series(v).groupby(np.asarray(groups)).sum()
    return float(np.sqrt(len(c)) * c.std(ddof=1) / len(v)) if len(c) > 1 else np.nan


# research/FAVORITE_PENALTY.md, addendum 2026-10-15: three-way verdict at the January checkpoints.
# 97.5% two-sided bounds with t(G - 1) critical values, G = season-week clusters. Simulated over the
# five looks with resampled historical weeks: false falsification at +0.0023 <= 4.8%, false support
# at 0 <= 2.3% (research/forward_monitoring_results/).
FP_MIN_GAMES = 200
FP_ALPHA = .025
FP_DELTA = .002      # the smallest gain the penalty was adopted for


def fp_critical(clusters):
    return float(t_dist.ppf(1 - FP_ALPHA / 2, clusters - 1))


def fp_verdict(gain, se, n, clusters):
    """Penalty forward verdict (FAVORITE_PENALTY.md addendum 2026-10-15), with the week-cluster SE."""
    if n < FP_MIN_GAMES or clusters < 2 or not np.isfinite(se):
        return f"no verdict before {FP_MIN_GAMES} graded games"
    c = fp_critical(clusters)
    if gain - c * se > 0:
        return "supported (lower bound above 0)"
    if gain + c * se < FP_DELTA:
        return f"falsified (upper bound below +{FP_DELTA:g})"
    return "unresolved"


def roi_bands(g):
    """Model-side flat ROI per price band of the picked side, plus all games."""
    b = g[g.units.notna() & g.fav_units.notna()]
    rows = []
    for lab in list(m.ML_BANDS) + ["All games"]:
        part = b if lab == "All games" else b[b.bet_band == lab]
        bets = pd.DataFrame({"result": part.bet_result, "units": part.units, "q": part.bet_q,
                             "null_ev": part.null_ev})
        rows.append({"group": lab, **m.roi_summary(bets),
                     "fav_units": float(part.fav_units.sum()), "fav_roi": float(part.fav_units.mean()) if len(part) else np.nan})
    return pd.DataFrame(rows)


def scored_frame(g):
    """Rows in the shape nfl_model's calibration/record helpers expect."""
    s = g[(g.status == "graded") & g.market_wp.notna()].copy()
    s["market_wp"] = s.market_wp.astype(float)
    return s


def h4_summary(g):
    """Pre-registered H4 over every graded game with a recorded term (one row per game,
    whatever the experiment): partial r of the term with the home margin, controlling
    for the snapshot's market spread, with a bootstrap 95% CI."""
    if "h4_pass_term" not in g:
        return {"n": 0}
    d = g[(g.status == "graded") & g.h4_pass_term.notna() & g.spread_line.notna()].drop_duplicates("game_id")
    r, lo, hi = matchup.partial_r(d.h4_pass_term, d.result, d.spread_line)
    return {"n": len(d), "r": r, "lo": lo, "hi": hi}


def disagreement(part):
    """Model and market favorite on the graded games where they pick different sides
    (v1.14.2): everywhere else they make the same bet, so this is the whole difference."""
    t = m.disagreement_table(part, by="season")
    t = t[t.group == "All games"].set_index("source")
    return t.loc["model"].to_dict(), t.loc["market favorite"].to_dict()


def h5_grades(h5, results):
    """Pre-registered H5: 1u on the moneyline underdog of every recorded game whose total
    at lock is <= totals.H5_MAX_TOTAL, at the moneylines recorded with it; the market
    favorite is scored on the same rows. One row per game, independent of the model."""
    cols = ["game_id", "season", "week", "home", "away", "total_line", "home_moneyline", "away_moneyline"]
    d = pd.DataFrame(h5 or [], columns=cols).drop_duplicates("game_id")
    d = d[pd.to_numeric(d.total_line, errors="coerce") <= totals.H5_MAX_TOTAL]
    res = results.drop_duplicates("game_id")[["game_id", "result"]]
    d = d.merge(res, on="game_id", how="left")
    d["home won"] = d.result.map(m.won)
    d["fav_wp"] = m.market_ml_wp(d)
    d["dog_wp"] = 1 - d.fav_wp
    dog, fav = m.flat_bets(d, "dog_wp"), m.flat_bets(d, "fav_wp")
    d["bet_side"], d["bet_result"], d["units"], d["null_ev"], d["bet_q"] = dog.side, dog.result, dog.units, dog.null_ev, dog.q
    d["fav_units"] = fav.units.where(dog.units.notna())
    return d


def h5_summary(d):
    b = d[d.units.notna()] if len(d) else d
    out = m.roi_summary(pd.DataFrame({"result": b.get("bet_result", []), "units": b.get("units", []),
                                      "q": b.get("bet_q", []), "null_ev": b.get("null_ev", [])}))
    out["recorded"] = len(d)
    out["fav_units"] = float(b.fav_units.sum()) if len(b) else 0.
    out["fav_roi"] = float(b.fav_units.mean()) if len(b) else np.nan
    return out


def h5_verdict(s):
    """Decision rule fixed in research/PREREGISTRATION.md (H5)."""
    if s["bets"] < 10 or not np.isfinite(s["roi_se"]):
        return "needs 10 graded bets to report"
    edge = s["roi"] - s["null_roi"]
    if edge - 1.96 * s["roi_se"] > 0:
        return "supported (95% CI of ROI minus null above zero)"
    if s["bets"] >= 300 and edge <= 0:
        return "falsified (n >= 300, ROI at or below the null)"
    return "unresolved"


def h9_rows(g):
    """The registered H9 sample: the first production snapshot per game (v1.18 on) from 2026 week 6,
    with q from its moneylines, q_s = Phi(spread_line/12.37) and dis = logit(q) - logit(q_s)."""
    season, week = H9_FROM
    later = (g.season > season) | ((g.season == season) & (g.week >= week))
    prod = g.revision.isin(set(H9_PRODUCTION) | {m.REVISION})
    d = g[prod & later].sort_values("generated_utc").drop_duplicates("game_id").copy()
    d["h_q"] = m.market_ml_wp(d)
    sp = pd.to_numeric(d.spread_line, errors="coerce").astype(float)
    d = d[np.isfinite(d.h_q) & np.isfinite(sp)].copy()
    qs = m.ndtr(sp.loc[d.index] / m.MARKET_SIGMA)
    d["h9_dis"] = _logit(np.clip(d.h_q, H9_CLIP, 1 - H9_CLIP)) - _logit(np.clip(qs, H9_CLIP, 1 - H9_CLIP))
    return d


def _h9_fit(d):
    """Home win ~ 1 + logit(q) + dis (free slopes), Newton, season-week cluster-robust SE of b."""
    X = np.column_stack([np.ones(len(d)), _logit(np.clip(d.h_q, H9_CLIP, 1 - H9_CLIP)), d.h9_dis])
    y = d["home won"].to_numpy(float)
    b = np.zeros(3)
    for _ in range(100):
        p = 1 / (1 + np.exp(-X @ b))
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < 1e-12:
            break
    p = 1 / (1 + np.exp(-X @ b))
    S = pd.DataFrame(X * (y - p)[:, None]).groupby((d.season.astype(str) + "_" + d.week.astype(str)).to_numpy()).sum().to_numpy()
    Hi = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    return float(b[2]), float(np.sqrt((Hi @ (S.T @ S) @ Hi)[2, 2]))


def h9_summary(g):
    d = h9_rows(g)
    graded = d[d.status != "pending"]
    binary = graded[graded.status == "graded"]
    weeks = (binary.season.astype(str) + "_" + binary.week.astype(str)).nunique()
    out = {"rows": len(d), "n": len(binary), "weeks": weeks, "b": np.nan, "se": np.nan}
    if len(binary) >= H9_MIN_GAMES and weeks >= H9_MIN_WEEKS and binary["home won"].nunique() == 2:
        try:
            b, se = _h9_fit(binary)
            if np.isfinite(b) and np.isfinite(se):
                out["b"], out["se"] = b, se
        except np.linalg.LinAlgError:
            pass
    x = graded[graded.h9_dis.abs() >= H9_T].copy()
    if x.empty:
        out["rule"] = {**m.roi_summary(pd.DataFrame(columns=["units", "result", "q", "null_ev"])), "fav_units": 0.}
        return out
    x["h9_wp"] = np.where(x.h9_dis < 0, 1., 0.)   # the side the spread favors more: home if dis < 0
    bets = m.flat_bets(x, "h9_wp")
    fav = m.flat_bets(x.assign(fwp=x.h_q), "fwp")
    r = m.roi_summary(bets[bets.units.notna()])
    r["fav_units"] = float(fav.units.where(bets.units.notna()).sum())
    out["rule"] = r
    return out


def h9_verdict(s):
    """Decision rule fixed in research/PREREGISTRATION.md (H9, 2026-10-15)."""
    if s["n"] < 300 or not np.isfinite(s["se"]):
        return "no verdict before 300 graded binary games"
    if s["b"] <= -2 * s["se"]:
        return "supported (b <= -2 SE)"
    if s["n"] >= 600 and s["b"] >= 0:
        return "falsified (n >= 600, b >= 0)"
    return "unresolved"


def h9_rule_verdict(r):
    if r["bets"] < 100 or not np.isfinite(r["roi_se"]):
        return "no verdict before 100 bets"
    edge = r["roi"] - r["null_roi"]
    if edge >= 2 * r["roi_se"]:
        return "supported (ROI - null >= 2 SE)"
    if edge <= 0:
        return "falsified (ROI at or below the null)"
    return "unresolved"


def report_text(g, now=None, h5=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    lines = [f"NFL forward ledger report -- {now.strftime('%Y-%m-%d %H:%M UTC')}",
             "Source: data/forward_predictions.jsonl (first pregame snapshot per game and experiment).",
             "Basis: native forward observations only; no reconstructed or backfilled rows.",
             "Headline: 1u flat on the model's side at the moneyline saved in the snapshot (not necessarily the close).",
             "Log loss/Brier market: the probability saved in each original snapshot; no-vig moneylines for v1.16/v1.17, spread-derived for earlier revisions.",
             ""]
    if g.empty:
        return "\n".join(lines + ["No snapshots recorded yet."]) + "\n"
    for rev, part in g.groupby("revision", sort=False):
        sm = summary(part)
        lines.append(f"== {rev}: {sm['snapshots']} snapshots, {sm['graded']} graded, "
                     f"{sm['pending']} pending, {sm['ties']} ties")
        r = sm["roi"]
        if r["bets"]:
            lines += [f"  HEADLINE flat 1u, model's side at the snapshot moneyline: {r['wins']}-{r['losses']}-{r['pushes']}, "
                      f"{r['units']:+.2f}u, ROI {100 * r['roi']:+.1f}% +/- {100 * r['roi_se']:.1f} (1 SE)",
                      f"    win {100 * r['win_pct']:.1f}% vs no-vig q {100 * r['mean_q']:.1f}% (excess {r['excess_pp']:+.1f}pp); "
                      f"market-correct null ROI {100 * r['null_roi']:+.1f}%",
                      f"    same rows, market favorite every game: {r['fav_units']:+.2f}u, ROI {100 * r['fav_roi']:+.1f}%",
                      ]
            dm, df_ = disagreement(part)
            lines.append(f"  Model vs favorite, games where they pick different sides (all other bets are identical): "
                         f"n={dm['bets']}" + (f", model {dm['units']:+.2f}u (ROI {100 * dm['roi']:+.1f}%) vs favorite "
                                              f"{df_['units']:+.2f}u (ROI {100 * df_['roi']:+.1f}%); "
                                              f"difference {dm['units'] - df_['units']:+.2f}u" if dm["bets"] else ""))
            lines.append("  ROI by the picked side's price band (model):")
            bt = roi_bands(part)
            for row in bt.itertuples(index=False):
                if row.bets:
                    lines.append(f"    {row.group:>14}  n={row.bets:<4} {row.wins}-{row.losses}-{row.pushes}  "
                                 f"{row.units:+7.2f}u  ROI {100 * row.roi:+6.1f}%  q {100 * row.mean_q:.1f}%")
        else:
            lines.append("  No graded bets with a saved moneyline yet.")
        decided = part.ats_result.isin(["W", "L"]).sum()
        if decided:
            lines.append(f"  Diagnostic, not the goal metric: model-implied spread vs the snapshot spread "
                         f"(break-even at -110: {100 * ATS_BREAKEVEN:.1f}%)")
            for lab, gap in (("all games", 0.), (f"|gap| >= {ATS_GAP_POINTS:g} pts", ATS_GAP_POINTS)):
                a = ats_summary(part, gap)
                if a["wins"] + a["losses"]:
                    lines.append(f"    {lab:>15}  {a['wins']}-{a['losses']}-{a['pushes']}  "
                                 f"cover {100 * a['win_pct']:.1f}% (Wilson 95% {100 * a['lo']:.1f}-{100 * a['hi']:.1f})")
                else:
                    lines.append(f"    {lab:>15}  no decided games")
        ks = kalshi_summary(part, "kalshi_units", "kalshi_fav_units")
        if ks["n"]:
            nl = part.loc[part.kalshi_units.notna(), "kalshi_null"].mean()
            lag = part.loc[part.kalshi_units.notna(), "kalshi_lag_hours"]
            early = int((lag < 0).sum())
            lines += [f"  Secondary: model's side at the Kalshi ask, first capture at or after lock (est. fee incl.): "
                      f"{ks['wins']}-{ks['losses']}, {ks['units']:+.2f}u, ROI {100 * ks['roi']:+.1f}%"
                      + (f" +/- {100 * ks['roi_se']:.1f}" if np.isfinite(ks["roi_se"]) else ""),
                      f"    Kalshi-correct null {100 * nl:+.1f}%; same rows, Kalshi favorite {ks['base_units']:+.2f}u, "
                      f"ROI {100 * ks['base_roi']:+.1f}%; capture lag after lock median {lag.median():.1f}h, max {lag.max():.1f}h"
                      + (f"; {early} captured BEFORE lock (no later capture; min {lag.min():.1f}h)" if early else "")]
        al = kalshi_summary(part[part.alt_rule], "alt_units", "alt_fav_units")
        if al["n"]:
            lines += [f"  Diagnostic, not the goal metric: alt-line rule at Kalshi prices: {al['wins']}-{al['losses']}, "
                      f"{al['units']:+.2f}u, ROI {100 * al['roi']:+.1f}%"
                      + (f" +/- {100 * al['roi_se']:.1f}" if np.isfinite(al["roi_se"]) else ""),
                      f"    same rows, favorite at its Kalshi game-winner ask: {al['base_units']:+.2f}u, ROI {100 * al['base_roi']:+.1f}%"]
        lb = part[part.ladder_units.notna()]
        if len(lb):
            u = lb.ladder_units.astype(float)
            lines += [f"  Pre-registered H3, not the goal metric: Kalshi ladder priced from 2006-2024 margins "
                      f"(edge >= ${k.LADDER_MIN_EDGE:.2f}/contract after fee): {(u > 0).sum()}-{(u < -.5).sum()}, "
                      f"{u.sum():+.2f}u, ROI {100 * u.mean():+.1f}%"
                      + (f" +/- {100 * u.std(ddof=1) / np.sqrt(len(u)):.1f}" if len(u) > 1 else ""),
                      f"    Kalshi-mid null {100 * lb.ladder_null.mean():+.1f}% on the same bets; "
                      f"{int(part.ladder_ticker.notna().sum())} games qualified so far"]
        cv = clv_summary(part)
        if cv["n"]:
            lines += ["  Diagnostic, not the goal metric: closing-line value against nflverse's moneyline after the game "
                      "(its closing line; no independent quote timestamp)",
                      f"    model's side, n={cv['n']}: the no-vig price moved {cv['mean']:+.2f} pts"
                      + (f" +/- {cv['se']:.2f}" if np.isfinite(cv["se"]) else "")
                      + " on average (positive = toward the model's side)"
                      + (f"; on its underdog picks (n={cv['dog_n']}) {cv['dog_mean']:+.2f} pts" if cv["dog_n"] else "")]
            if np.isfinite(cv["slope"]):
                lines.append(f"    line move vs the model's departure from the lock price: slope {cv['slope']:+.3f} "
                             f"+/- {cv['slope_se']:.3f} (positive = the market moved toward the model)")
        if sm["scored"]:
            lines += [f"  Scored rows (graded, market present): {sm['scored']}",
                      f"  Model picks  {m.record_text(sm['model_wins'], sm['model_losses'])}",
                      f"  Market picks {m.record_text(sm['market_wins'], sm['market_losses'])}",
                      f"  Log loss  model {sm['model_log_loss']:.4f}  market {sm['market_log_loss']:.4f}  "
                      f"gain {sm['ll_gain']:+.4f} +/- {sm['ll_gain_se']:.4f} (1 SE; positive = model better)",
                      f"  Brier     model {sm['model_brier']:.4f}  market {sm['market_brier']:.4f}"]
            if sm.get("fp_n"):
                gain = f"{sm['fp_gain']:+.4f}" + (f" +/- {sm['fp_gain_se']:.4f}" if np.isfinite(sm["fp_gain_se"]) else "")
                cse = sm["fp_gain_cluster_se"]
                lines.append(f"  Reporting only (v1.16.2, research/FAVORITE_PENALTY.md): favorite-confidence penalty "
                             f"(lambda {m.FAVORITE_PENALTY:g}) log loss {sm['fp_log_loss']:.4f} vs model "
                             f"{sm['fp_model_log_loss']:.4f}, gain {gain} (1 SE; n={sm['fp_n']}, "
                             f"{sm['fp_changed']} probabilities changed); bets unchanged; week-cluster SE "
                             + (f"{cse:.4f} over {sm['fp_clusters']} weeks" if np.isfinite(cse) else "n/a")
                             + ("; January checkpoint verdict: " if now.month == 1 else
                                "; interim reading, not a verdict (judged only at the January checkpoints): ")
                             + fp_verdict(sm["fp_gain"], cse, sm["fp_n"], sm["fp_clusters"]))
            recs = m.band_records(scored_frame(part))
            lines.append("  Pick records by confidence band (model | market):")
            for i, b in recs.groupby("band_index"):
                mm, kk = b[b.source == "model"].iloc[0], b[b.source == "market"].iloc[0]
                lines.append(f"    {mm.band:>9}  {mm.record:>16} | {kk.record:>16}")
        lines.append("")
    h = h4_summary(g)
    if h["n"]:
        verdict = ("supported (95% CI above zero)" if h["lo"] > 0 else
                   "falsified (CI below +0.05)" if h["hi"] < .05 else
                   "falsified (n >= 600, r <= 0)" if h["n"] >= 600 and h["r"] <= 0 else "unresolved")
        lines += ["== Pre-registered H4 (all revisions, one row per game): pass-matchup term vs the margin beyond the spread",
                  f"  n={h['n']} graded games" + (f", partial r {h['r']:+.3f} [{h['lo']:+.3f}, {h['hi']:+.3f}] (95%): {verdict}"
                                                 if np.isfinite(h["r"]) else " (needs 10 to report)"), ""]
    if g.revision.eq(H12_REVISION).any():
        s1, s2, s6 = h1_summary(g), h2_summary(g), h6_summary(g)
        lines += [f"== Pre-registered H1/H2/H6 (sample: first {H12_REVISION} snapshots, config {H12_EXPERIMENT[:8]}, for games "
                  f"from {H12_FROM[0]} week {H12_FROM[1]} on; addenda 2026-10-13 in research/PREREGISTRATION.md)",
                  f"  H1, |model - q| > {H1_MIN_GAP:g} with q from the snapshot moneylines: {s1['bets']} qualifying graded "
                  f"bets of {s1['rows']} priced rows" + _subset_text(s1) + f"; verdict: {h1_verdict(s1)}",
                  "  H2, log-loss gain vs q, weeks 14-18 against weeks 5-13: "
                  + "; ".join(f"{label} n={s2[key]['n']}" + (f" {s2[key]['mean']:+.4f}" if s2[key]["n"] else "")
                              for key, label in (("mid", "weeks 5-13"), ("late", "weeks 14-18"),
                                                 ("late_14_17", "14-17"), ("week_18", "18")))
                  + f"; verdict: {h2_verdict(s2)}",
                  "  H2 secondary, flat 1u ROI: "
                  + "; ".join(f"{label} n={s2[key]['bets']}"
                              + (f" {100 * s2[key]['roi']:+.1f}%"
                                 + (f" +/- {100 * s2[key]['roi_se']:.1f}" if np.isfinite(s2[key]["roi_se"]) else "")
                                 + f" (null {100 * s2[key]['null_roi']:+.1f}%, favorite {100 * s2[key]['fav_roi']:+.1f}%)"
                                 if s2[key]["bets"] else "")
                              for key, label in (("mid", "weeks 5-13"), ("late", "weeks 14-18"))),
                  f"  H6, the model backs the market underdog (its side's no-vig q < 0.5): {s6['bets']} graded bets of "
                  f"{s6['rows']} priced rows" + _subset_text(s6) + f"; verdict: {h6_verdict(s6)}",
                  "  Judged only at the season checkpoints; interim numbers are not acted on.", ""]
    if len(h9_rows(g)):
        s9 = h9_summary(g)
        r9 = s9["rule"]
        lines += [f"== Pre-registered H9 (one row per game, first production snapshot from {H9_FROM[0]} week {H9_FROM[1]}; "
                  "prices only): moneyline vs spread disagreement",
                  f"  {s9['rows']} games with lock prices, {s9['n']} graded binary"
                  + (f"; b on dis {s9['b']:+.3f} +/- {s9['se']:.3f} (negative = outcome leans to the spread's view)"
                     if np.isfinite(s9["b"]) else
                     f"; b needs {H9_MIN_GAMES} graded games over {H9_MIN_WEEKS} weeks"
                     if s9["n"] < H9_MIN_GAMES or s9["weeks"] < H9_MIN_WEEKS else "; b not estimable")
                  + f"; verdict: {h9_verdict(s9)}",
                  f"  Rule, |dis| >= {H9_T:g}, 1u on the side the spread favors more: {r9['bets']} graded bets"
                  + (f", {r9['wins']}-{r9['losses']}-{r9['pushes']}, {r9['units']:+.2f}u, ROI {100 * r9['roi']:+.1f}%"
                     + (f" +/- {100 * r9['roi_se']:.1f}" if np.isfinite(r9["roi_se"]) else "")
                     + f"; null {100 * r9['null_roi']:+.1f}%; same rows, favorite {r9['fav_units']:+.2f}u" if r9["bets"] else "")
                  + f"; verdict: {h9_rule_verdict(r9)}",
                  "  Judged only at the season checkpoints; interim numbers are not acted on.", ""]
    if h5 is not None and len(h5):
        s = h5_summary(h5)
        lines += [f"== Pre-registered H5 (one row per game, independent of the model): 1u on the moneyline underdog "
                  f"when the total at lock is <= {totals.H5_MAX_TOTAL:g}",
                  f"  {s['recorded']} qualifying games recorded, {s['bets']} graded"]
        if s["bets"]:
            lines += [f"  {s['wins']}-{s['losses']}-{s['pushes']}, {s['units']:+.2f}u, ROI {100 * s['roi']:+.1f}%"
                      + (f" +/- {100 * s['roi_se']:.1f} (1 SE)" if np.isfinite(s["roi_se"]) else "")
                      + f"; market-correct null {100 * s['null_roi']:+.1f}%; same rows, favorite {s['fav_units']:+.2f}u",
                      f"  verdict: {h5_verdict(s)}"]
        lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(g, data_dir=DATA, now=None, h5=None):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    g.to_csv(data_dir / GRADED.name, index=False, float_format="%.6g")
    (data_dir / REPORT.name).write_text(report_text(g, now, h5), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(DATA))
    args = ap.parse_args(argv)
    records = load_records(Path(args.data_dir) / LEDGER.name)
    results = load_results() if records else pd.DataFrame(columns=["game_id", "away_score", "home_score", "result"])
    table = Path(args.data_dir) / k.LADDER_TABLE.name
    g = grade(records, results, k.load(Path(args.data_dir) / k.SNAPSHOTS.name),
              k.load_ladder_table(table) if table.exists() else None, matchup.load(Path(args.data_dir) / matchup.TERMS.name))
    h5 = h5_grades(totals.load(Path(args.data_dir) / totals.TOTALS.name), results)
    write_outputs(g, args.data_dir, h5=h5)
    sm = summary(g)
    print(f"ledger: {sm['snapshots']} snapshots, {sm['graded']} graded, {sm['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
