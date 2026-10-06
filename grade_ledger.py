#!/usr/bin/env python3
"""Grade the forward ledger: data/forward_predictions.jsonl -> data/forward_ledger.csv
and data/ledger_report.txt.

The JSONL is the record of truth and is never rewritten here: it holds each
game's FIRST pregame snapshot per experiment, written by nfl_model.record_forward.
This script only joins final scores onto it. Re-running is idempotent; a game
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

import nfl_model as m

DATA = Path("data")
LEDGER = DATA / "forward_predictions.jsonl"
GRADED = DATA / "forward_ledger.csv"
REPORT = DATA / "ledger_report.txt"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
COLUMNS = ["experiment", "revision", "season", "week", "game_id", "away", "home",
           "kickoff_utc", "generated_utc", "lead_hours", "model_wp", "market_wp",
           "homefield_wp", "spread_line", "away_injury_report", "home_injury_report",
           "away_score", "home_score", "result", "home won", "status",
           "model_pick", "model_hit", "market_hit", "model_log_loss", "market_log_loss",
           "model_brier", "market_brier"]


def load_records(path=LEDGER):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_results(url=SCHEDULE_URL):
    s = pd.read_csv(url, usecols=["game_id", "away_score", "home_score", "result"])
    return s


def grade(records, results):
    """Flat graded frame, one row per ledger snapshot, newest kickoff first."""
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
    g = g.sort_values(["kickoff_utc", "game_id"], ascending=[False, True]).reset_index(drop=True)
    return g[COLUMNS]


def summary(g):
    """Headline numbers on ONE row set: graded games with a market probability."""
    s = g[(g.status == "graded") & g.market_wp.notna()]
    out = {"snapshots": int(len(g)), "pending": int((g.status == "pending").sum()),
           "ties": int((g.status == "tie").sum()), "graded": int((g.status == "graded").sum()),
           "scored": int(len(s))}
    if len(s):
        mh, kh = s.model_hit.dropna(), s.market_hit.dropna()
        d = (s.market_log_loss - s.model_log_loss).to_numpy(float)
        out.update(model_wins=int(mh.sum()), model_losses=int(len(mh) - mh.sum()),
                   market_wins=int(kh.sum()), market_losses=int(len(kh) - kh.sum()),
                   model_log_loss=float(s.model_log_loss.mean()), market_log_loss=float(s.market_log_loss.mean()),
                   ll_gain=float(d.mean()), ll_gain_se=float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else np.nan,
                   model_brier=float(s.model_brier.mean()), market_brier=float(s.market_brier.mean()))
    return out


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
             "Market: spread-derived home win probability saved in the same snapshot (no independent quote timestamp).",
             ""]
    if g.empty:
        return "\n".join(lines + ["No snapshots recorded yet."]) + "\n"
    for rev, part in g.groupby("revision", sort=False):
        sm = summary(part)
        lines.append(f"== {rev}: {sm['snapshots']} snapshots, {sm['graded']} graded, "
                     f"{sm['pending']} pending, {sm['ties']} ties")
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
    g = grade(records, results)
    write_outputs(g, args.data_dir)
    sm = summary(g)
    print(f"ledger: {sm['snapshots']} snapshots, {sm['graded']} graded, {sm['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
