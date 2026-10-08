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

import kalshi as k
import nfl_model as m

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
           "ladder_ask", "ladder_edge", "ladder_result", "ladder_units", "ladder_null"]
ATS_GAP_POINTS = 3.  # diagnostic split; chosen after seeing held-out 2023-25 (v1.12.1)
ATS_BREAKEVEN = 110 / 210  # win rate needed at -110 on both sides


def load_records(path=LEDGER):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_results(url=SCHEDULE_URL):
    s = pd.read_csv(url, usecols=["game_id", "away_score", "home_score", "result"])
    return s


def grade(records, results, kalshi=None, ladder=None):
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
    g = g.join(kalshi_grades(g, kalshi or [], ladder))
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


def kalshi_units(won, ask):
    """1u staked at a Kalshi ask: win (or a tie's $0.50) per contract minus the estimated
    taker fee, FEE_RATE * P * (1 - P) per contract, i.e. FEE_RATE * (1 - P) per unit staked."""
    if not np.isfinite(ask) or not np.isfinite(won):
        return np.nan
    return won / ask - 1 - k.FEE_RATE * (1 - ask)


def kalshi_grades(g, snaps, ladder=None):
    """Secondary prices from the first Kalshi capture per game (v1.12.2, reporting only).

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
    by = {r["game_id"]: r for r in snaps}
    rows = []
    for r in g.itertuples(index=False):
        s, out = by.get(r.game_id), {}
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
    return out


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


def report_text(g, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    lines = [f"NFL forward ledger report -- {now.strftime('%Y-%m-%d %H:%M UTC')}",
             "Source: data/forward_predictions.jsonl (first pregame snapshot per game and experiment).",
             "Basis: native forward observations only; no reconstructed or backfilled rows.",
             "Headline: 1u flat on the model's side at the moneyline saved in the snapshot (not necessarily the close).",
             "Log loss/Brier market: spread-derived home win probability from the same snapshot.",
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
                      "  ROI by the picked side's price band (model):"]
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
            lines += [f"  Secondary: model's side at the Kalshi ask captured after lock (est. fee incl.): "
                      f"{ks['wins']}-{ks['losses']}, {ks['units']:+.2f}u, ROI {100 * ks['roi']:+.1f}%"
                      + (f" +/- {100 * ks['roi_se']:.1f}" if np.isfinite(ks["roi_se"]) else ""),
                      f"    Kalshi-correct null {100 * nl:+.1f}%; same rows, Kalshi favorite {ks['base_units']:+.2f}u, "
                      f"ROI {100 * ks['base_roi']:+.1f}%; capture lag after lock median {lag.median():.1f}h, max {lag.max():.1f}h"]
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
        if sm["scored"]:
            lines += [f"  Scored rows (graded, market present): {sm['scored']}",
                      f"  Model picks  {m.record_text(sm['model_wins'], sm['model_losses'])}",
                      f"  Market picks {m.record_text(sm['market_wins'], sm['market_losses'])}",
                      f"  Log loss  model {sm['model_log_loss']:.4f}  market {sm['market_log_loss']:.4f}  "
                      f"gain {sm['ll_gain']:+.4f} +/- {sm['ll_gain_se']:.4f} (1 SE; positive = model better)",
                      f"  Brier     model {sm['model_brier']:.4f}  market {sm['market_brier']:.4f}"]
            recs = m.band_records(scored_frame(part))
            lines.append("  Pick records by confidence band (model | market):")
            for i, b in recs.groupby("band_index"):
                mm, kk = b[b.source == "model"].iloc[0], b[b.source == "market"].iloc[0]
                lines.append(f"    {mm.band:>9}  {mm.record:>16} | {kk.record:>16}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(g, data_dir=DATA, now=None):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    g.to_csv(data_dir / GRADED.name, index=False, float_format="%.6g")
    (data_dir / REPORT.name).write_text(report_text(g, now), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(DATA))
    args = ap.parse_args(argv)
    records = load_records(Path(args.data_dir) / LEDGER.name)
    results = load_results() if records else pd.DataFrame(columns=["game_id", "away_score", "home_score", "result"])
    table = Path(args.data_dir) / k.LADDER_TABLE.name
    g = grade(records, results, k.load(Path(args.data_dir) / k.SNAPSHOTS.name),
              k.load_ladder_table(table) if table.exists() else None)
    write_outputs(g, args.data_dir)
    sm = summary(g)
    print(f"ledger: {sm['snapshots']} snapshots, {sm['graded']} graded, {sm['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
