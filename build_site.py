#!/usr/bin/env python3
"""Build the NFL model site: run the model, snapshot its outputs into data/,
grade the forward ledger, and render static pages into public/.

    python build_site.py               # full build (what build.yml runs)
    python build_site.py --pages-only  # re-render from committed data/ only

Pages (public: pooled 2026 ATS results; record, cover rate, units, ROI and
same-game baselines. Earlier seasons, median-map rules,
standard errors, log loss, model internals, earlier revisions and every research
arm stay in the repository's data/ledger_report.txt and data/latest/)
  index.html               this week's games: model vs market spread, pick, lock status, injury reports
  grades.html              pooled season results game by game
  market-calibration.html  ATS performance: running units, same-game baselines, by week (legacy URL)

Data written (committed by build.yml through commit_data.py)
  data/forward_predictions.jsonl   append-only ledger (written by nfl_model.record_forward)
  data/frozen_recipe_<season>_<REVISION>.json frozen hyperparameters (nfl_model.frozen_recipe)
  data/forward_ledger.csv, data/ledger_report.txt   graded view (grade_ledger.py)
  data/latest/                     the newest run's page inputs, so --pages-only needs no model run
  data/projections/<season>_week<NN>.csv   the latest board of each week, overwritten through the week

A model failure exits non-zero before any page is written, so the workflow
never uploads an artifact and the last good site stays live.
"""

import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
from html import escape
from urllib.parse import quote
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import grade_ledger
import nfl_model as m
import fixed_bands
import ats_locks
import forecast_history
import season_ats
import espn_spreads
import historical_calibration
import score_updates
import production_sanity

DATA = Path("data")
LATEST = DATA / "latest"
PROJECTIONS = DATA / "projections"
ASSETS = Path("assets/fonts")
PT = ZoneInfo("America/Los_Angeles")
SITE_NAME = "NFL ATS"
PUBLIC_CSV_EXPORTS = {'ats_2026_results.csv', 'ats_locked_picks.csv', 'fixed_band_board.csv',
                      'historical_calibration.csv'}

# run-folder file -> data/latest file
SNAPSHOT = {
    "current_game_score_contributions.csv": "contributions.csv",
    "outer_chronological_scorecard.csv": "outer_scorecard.csv",
    "outer_scorecard_by_season.csv": "outer_by_season.csv",
    "calibration_bands.csv": "calibration_bands.csv",
    "band_records.csv": "band_records.csv",
    "market_blend_diagnostic.csv": "market_blend.csv",
    "recipe_selection_diagnostics.csv": "recipe_selection.csv",
    "current_composite_weights.csv": "weights.csv",
    "season_scorecard.csv": "season_scorecard.csv",
    "roi_bands.csv": "roi_bands.csv",
    "roi_by_season.csv": "roi_by_season.csv",
    "disagree_roi_by_season.csv": "disagree_roi_by_season.csv",
    "season_roi.csv": "season_roi.csv",
    "retro_ledger.csv": "retro_ledger.csv",
    "retro_roi_by_season.csv": "retro_roi_by_season.csv",
    "retro_roi_bands.csv": "retro_roi_bands.csv",
    "candidate_roi.csv": "candidate_roi.csv",
    "report_notes.csv": "report_notes.csv",
    "regraded_ledger.csv": "regraded_ledger.csv",
    "regraded_summary.csv": "regraded_summary.csv",
    "market_target_fit_audit.csv": "market_target_fit_audit.csv",
    "replacement_adjustments.csv": "replacement_adjustments.csv",
}
BOARD_COLS = ["game_id", "season", "week", "away", "home", "gameday", "gametime", "site",
              "result", "away_score", "home_score", "home won", "ready", "spread_line",
              "home_moneyline", "away_moneyline",
              "total_line", "margin__selected__mean", "total__selected__mean", "market_wp", "model_wp", "model_spread", "homefield_wp", "composite_log_odds",
              "offset_se", "model_wp_lo", "model_wp_hi", "recipe",
              "away_qb_expected", "away_qb_usual", "home_qb_expected", "home_qb_usual",
              "away_injury_report", "home_injury_report"]
TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers",
    "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos",
    "DET": "Lions", "GB": "Packers", "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars",
    "KC": "Chiefs", "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants", "NYJ": "Jets",
    "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks", "SF": "49ers", "TB": "Buccaneers",
    "TEN": "Titans", "WAS": "Commanders"}

# Team logos hotlinked from ESPN's CDN (nflverse code -> ESPN code where they differ).
# Readers' browsers fetch them; the build needs no network. A missing logo falls back to the code.
ESPN_CODES = {"LA": "lar", "WAS": "wsh"}
LOGO_URL = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/{variant}/{code}.png&h=80&w=80"


def logo_html(code):
    """Light- and dark-theme logo over the team code; CSS shows the one matching the theme."""
    if code not in TEAM_NAMES:
        return ""
    espn = ESPN_CODES.get(code, code.lower())
    return "".join(f"<img class='logo {cls}' src='{esc(LOGO_URL.format(variant=v, code=espn))}' alt='' "
                   "loading='lazy' decoding='async' referrerpolicy='no-referrer' "
                   "onload=\"this.parentNode.classList.add('has-logo')\" onerror='this.remove()'>"
                   for cls, v in (("lt", "500"), ("dk", "500-dark")))


def esc(x):
    return escape("" if x is None else str(x), quote=True)


def num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return math.nan
    return x


def pct(p, digits=0):
    p = num(p)
    return "—" if not math.isfinite(p) else f"{100 * p:.{digits}f}%"


# ---------------------------------------------------------------- model run + snapshot

def run_model():
    os.environ.setdefault("NFL_STATE_DIR", str(DATA))
    os.environ.setdefault("NFL_CACHE_DIR", ".nfl_cache")
    os.environ.setdefault("NFL_OUTPUT_ROOT", "runs")
    return Path(m.main())


def snapshot(outdir, latest=LATEST, projections=PROJECTIONS):
    """Copy the run's page inputs into data/latest and the week's board into data/projections."""
    outdir, latest = Path(outdir), Path(latest)
    man = json.loads((outdir / "run_manifest.json").read_text())
    season, week = int(man["season"]), int(man["week"])
    latest.mkdir(parents=True, exist_ok=True)
    for old in latest.glob("*"):
        old.unlink()
    for src, dst in SNAPSHOT.items():
        # An empty frame (e.g. no market blend under 20 games) is written by pandas
        # as a bare newline, which validate_data_files rejects; leave it out instead.
        if (outdir / src).exists() and read_csv_or_empty(outdir / src).shape[1]:
            shutil.copyfile(outdir / src, latest / dst)
    board = pd.read_csv(outdir / f"week{week}_board.csv")
    avail = [c for c in board.columns if c.startswith(("home__avail__", "away__avail__"))]
    evidence = [c for c in board.columns if c == 'availability_policy' or '_availability_evidence' in c]
    replacement=[c for c in board if c.startswith(('home_qb_','away_qb_','qb_replacement_'))]
    compact = board[list(dict.fromkeys([c for c in BOARD_COLS if c in board.columns] + avail + evidence + replacement))]
    compact.to_csv(latest / "board.csv", index=False, float_format="%.6g")
    Path(projections).mkdir(parents=True, exist_ok=True)
    for prior in outdir.glob("week*_board.csv"):
        full = pd.read_csv(prior)
        if full.empty:
            continue
        prior_week = int(prior.stem.removeprefix("week").removesuffix("_board"))
        fields = [c for c in BOARD_COLS if c in full] + [c for c in full if c.startswith(("home__avail__", "away__avail__"))
                  or c == 'availability_policy' or '_availability_evidence' in c]
        fields=list(dict.fromkeys(fields+[c for c in full if c.startswith(('home_qb_','away_qb_','qb_replacement_'))]))
        full[fields].to_csv(Path(projections) / f"{season}_week{prior_week:02d}.csv", index=False, float_format="%.6g")
    compact.to_csv(Path(projections) / f"{season}_week{week:02d}.csv", index=False, float_format="%.6g")
    html = outdir / f"week{week}_board.html"
    if html.exists():
        shutil.copyfile(html, latest / "board.html")
    keep = {k: man.get(k) for k in ("revision", "diagnostics", "generated_utc", "season", "week",
                                    "config_signature", "recipe", "market_blend_verdict",
                                    "limitations", "target", "fit_timing", "validation",
                                    "profile_decay", "fit_decay", "package_versions")}
    keep["availability_audit"] = [a for a in man.get("source_audit", [])
                                  if a.get("source") in ("availability_roster_membership", "roster_status_codes")]
    (latest / "manifest.json").write_text(json.dumps(keep, indent=2, allow_nan=False, default=str))
    if (outdir / "regraded_ledger_report.md").exists():
        shutil.copyfile(outdir / "regraded_ledger_report.md", latest / "regraded_ledger_report.md")
    return season, week


def read_csv_or_empty(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def load_latest(latest=LATEST):
    latest = Path(latest)
    if not (latest / "manifest.json").exists():
        return None
    out = {"manifest": json.loads((latest / "manifest.json").read_text())}
    for name in list(SNAPSHOT.values()) + ["board.csv"]:
        p = latest / name
        out[name[:-4]] = read_csv_or_empty(p)
    out['final_scores'] = score_updates.read(latest.parent)
    out['board'] = score_updates.overlay(out['board'], out['final_scores'])
    out["board_html"] = (latest / "board.html").exists()
    fixed_bands.prepare(out)
    season_ats.prepare_replacement_views(out,remapped=True)
    out['espn_archive'] = espn_spreads.read(latest.parent)
    return out


def load_ledger(data=DATA):
    p = Path(data) / grade_ledger.GRADED.name
    return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=grade_ledger.COLUMNS)


# ---------------------------------------------------------------- page shell

CSS = r"""
:root{
  --bg:#f4f6f9; --surface:#ffffff; --surface-2:#f0f3f7; --ink:#13202f;
  --muted:#4d5d6e; --faint:#647384; --line:#dce3ea; --line-2:#e9eef3;
  --accent:9,120,94; --accent-tx:6,102,79; --accent-on:#ffffff;
  --warm:198,84,44; --cool:52,116,168; --lean:176,124,16;
  --warm-tx:164,69,36; --cool-tx:46,103,149; --lean-tx:130,92,12;
  --good:25,121,62; --bad:184,60,40;
  --mono:"JetBrains Mono",ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
  --sans:"Archivo",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  --shadow:0 1px 2px rgba(19,32,47,.04),0 6px 20px -12px rgba(19,32,47,.18);
  --r:14px; --r-s:6px; --r-pill:999px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0c141d; --surface:#141e29; --surface-2:#18232f; --ink:#e6eef6;
  --muted:#a0b1c2; --faint:#8a9cb0; --line:#243241; --line-2:#1d2936;
  --accent:61,192,151; --accent-tx:110,218,184; --accent-on:#0c141d;
  --warm:236,122,72; --cool:96,158,208; --lean:244,196,96;
  --warm-tx:240,140,98; --cool-tx:120,176,222; --lean-tx:244,196,96;
  --good:88,194,125; --bad:239,127,98;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.8);
}
:root:not([data-theme="light"]) .logo.lt{display:none}:root:not([data-theme="light"]) .logo.dk{display:block}}
html[data-theme="dark"] .logo.lt{display:none}html[data-theme="dark"] .logo.dk{display:block}
html[data-theme="dark"]{
  --bg:#0c141d; --surface:#141e29; --surface-2:#18232f; --ink:#e6eef6;
  --muted:#a0b1c2; --faint:#8a9cb0; --line:#243241; --line-2:#1d2936;
  --accent:61,192,151; --accent-tx:110,218,184; --accent-on:#0c141d;
  --warm:236,122,72; --cool:96,158,208; --lean:244,196,96;
  --warm-tx:240,140,98; --cool-tx:120,176,222; --lean-tx:244,196,96;
  --good:88,194,125; --bad:239,127,98;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--sans);
  -webkit-font-smoothing:antialiased;padding:0 16px 56px}
.mx-wrap{max-width:1120px;margin:0 auto}
a{color:rgb(var(--accent-tx))}
.skip-link{position:absolute;left:16px;top:-80px;padding:10px 14px;background:var(--surface);
  border-radius:var(--r-s);z-index:10}
.skip-link:focus{top:10px}
:focus-visible{outline:3px solid rgb(var(--accent));outline-offset:3px}
/* header */
.topbar{display:flex;align-items:center;gap:16px;padding:18px 0;margin-bottom:22px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font:800 19px/1 var(--sans);letter-spacing:-.02em;
  color:var(--ink);text-decoration:none;white-space:nowrap}
.brand-mark{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;
  background:rgb(var(--accent));color:#fff;font:800 12px/1 var(--sans);letter-spacing:.03em}
.nav{display:flex;gap:4px;margin-left:auto;padding:4px;background:var(--surface);border:1px solid var(--line);border-radius:12px}
.nav a{padding:8px 16px;border-radius:8px;color:var(--muted);text-decoration:none;font:650 14px/1.2 var(--sans);white-space:nowrap}
.nav a:hover{color:var(--ink);background:var(--surface-2)}
.nav a[aria-current="page"]{background:var(--ink);color:var(--surface)}
.theme{appearance:none;display:grid;place-items:center;width:38px;height:38px;border:1px solid var(--line);
  background:var(--surface);color:var(--muted);border-radius:10px;cursor:pointer;padding:0}
.theme:hover{color:var(--ink)}
.theme svg{width:18px;height:18px}
.theme .moon{display:none}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .theme .sun{display:none}:root:not([data-theme="light"]) .theme .moon{display:block}}
html[data-theme="dark"] .theme .sun{display:none}html[data-theme="dark"] .theme .moon{display:block}
/* page heading */
.gr-head{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 24px;margin:6px 0 22px}
.eyebrow{font:700 12px/1.2 var(--sans);letter-spacing:.08em;text-transform:uppercase;color:rgb(var(--accent-tx));margin-bottom:8px}
.gr-h1{font:800 34px/1.08 var(--sans);letter-spacing:-.035em;margin:0 0 8px}
.gr-lead{color:var(--muted);font-size:15px;line-height:1.6;max-width:68ch}
.stamp{font-family:var(--mono);font-size:12.5px}
/* tiles */
.gr-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:0 0 18px}
.gr-stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--shadow);min-width:0}
.gr-stat .l{font:700 11.5px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
.gr-stat .v{font:800 28px/1.1 var(--mono);letter-spacing:-.02em;margin:8px 0 6px;font-variant-numeric:tabular-nums}
.gr-stat .v.model{color:rgb(var(--accent-tx))}.gr-stat .v.good{color:rgb(var(--good))}.gr-stat .v.bad{color:rgb(var(--bad))}
.gr-stat .s{font:500 13px/1.45 var(--sans);color:var(--muted)}
.meter{position:relative;height:6px;border-radius:var(--r-pill);background:var(--line-2);margin:10px 0 6px;overflow:visible}
.meter i{position:absolute;left:0;top:0;bottom:0;border-radius:var(--r-pill);background:rgb(var(--accent))}
.meter b{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink);border-radius:1px}
.gr-note{background:var(--surface-2);border:1px solid var(--line-2);border-radius:10px;
  padding:12px 15px;margin:0 0 16px;font-size:14px;line-height:1.6;color:var(--muted)}
.gr-note b{color:var(--ink)}
.flag-note{border-left:3px solid rgb(var(--lean));background:rgba(var(--lean),.09)}
h2.sec{font:800 19px/1.25 var(--sans);letter-spacing:-.02em;margin:36px 0 12px}
h3{font:750 15px/1.3 var(--sans);margin:22px 0 10px}
.sec-lead{color:var(--muted);font-size:14px;margin:-4px 0 14px;max-width:72ch}
/* tables */
.gr-tablewrap{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  box-shadow:var(--shadow);overflow-x:auto;margin-bottom:12px}
table.gr{width:100%;border-collapse:collapse;font-size:14px}
table.gr th{font:700 11.5px/1.2 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--faint);
  text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap;background:var(--surface-2)}
table.gr td{padding:11px 14px;border-bottom:1px solid var(--line-2);vertical-align:middle}
table.gr tr:last-child td{border-bottom:0}
table.gr tbody tr:hover{background:var(--surface-2)}
table.gr .n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.gr tr.total td{font-weight:700;border-top:2px solid var(--line)}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.mut{color:var(--muted)}.small{font-size:13px;line-height:1.55}
.pos-tx{color:rgb(var(--good))}.neg-tx{color:rgb(var(--bad))}
.badge{display:inline-flex;align-items:center;gap:5px;font:700 11px/1 var(--sans);letter-spacing:.04em;text-transform:uppercase;
  padding:5px 8px;border-radius:var(--r-pill);border:1px solid var(--line);color:var(--muted);white-space:nowrap;background:var(--surface)}
.badge.w{color:rgb(var(--good));border-color:rgba(var(--good),.4);background:rgba(var(--good),.09)}
.badge.l{color:rgb(var(--bad));border-color:rgba(var(--bad),.4);background:rgba(var(--bad),.09)}
.badge.lean,.badge.lock{color:rgb(var(--accent-tx));border-color:rgba(var(--accent),.45);background:rgba(var(--accent),.09)}
.badge.warn{color:rgb(var(--warm-tx));border-color:rgba(var(--warm),.45);background:rgba(var(--warm),.09)}
.badge .u{text-transform:none}
.badge.live::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.team-code{font:800 13px/1 var(--mono);letter-spacing:.02em}
/* filters */
.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin:26px 0 12px}
.toolbar h2.sec{margin:0}
.seg{display:inline-flex;gap:3px;padding:3px;background:var(--surface);border:1px solid var(--line);border-radius:10px}
.seg button{appearance:none;border:0;background:transparent;color:var(--muted);font:650 13px/1 var(--sans);
  padding:8px 12px;border-radius:7px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--surface-2);color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)}
.seg .ct{font-family:var(--mono);color:var(--faint);margin-left:4px}
/* game cards */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;align-items:start}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);overflow:clip}
.card.picked-card{border-color:rgba(var(--accent),.35)}
.game-summary{display:block;padding:14px 16px 14px;list-style:none;cursor:pointer}
.game-summary::-webkit-details-marker{display:none}
.game-summary::marker{content:""}
.game-summary:hover{background:var(--surface-2)}
.card[open]>.game-summary{border-bottom:1px solid var(--line-2)}
.g-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}
.g-meta .when{font:600 12.5px/1.2 var(--sans);color:var(--muted)}
.g-teams{display:flex;flex-direction:column;gap:4px}
.g-team{display:grid;grid-template-columns:34px minmax(0,1fr) auto auto;align-items:center;gap:10px;
  padding:6px 8px;margin:0 -8px;border-radius:9px}
.g-team.picked{background:rgba(var(--accent),.09)}
.g-team .nm{font:700 16px/1.2 var(--sans);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.g-team .nm small{font:600 11.5px/1 var(--mono);color:var(--faint);margin-left:6px}
.g-team .ln{font:600 13px/1 var(--mono);color:var(--muted);font-variant-numeric:tabular-nums}
.g-team .sc{font:800 18px/1 var(--mono);min-width:28px;text-align:right;font-variant-numeric:tabular-nums}
.g-team.picked .nm::after{content:"PICK";font:800 9.5px/1 var(--sans);letter-spacing:.08em;color:var(--accent-on);
  background:rgb(var(--accent));border-radius:4px;padding:3px 5px;margin-left:8px;vertical-align:2px}
.chip{display:grid;place-items:center;width:34px;height:34px;flex:none;border-radius:var(--r-pill);
  background:var(--surface-2);font:800 11px/1 var(--mono);position:relative}
.chip .logo{position:absolute;inset:3px;width:28px;height:28px;object-fit:contain}
.chip .logo.dk{display:none}
.chip.has-logo{background:transparent}
.chip.has-logo span{visibility:hidden}
.pick-lines{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 12px;
  margin-top:12px;padding-top:12px;border-top:1px dashed var(--line)}
.pick-lines .kind{font:700 11px/1 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--faint);width:100%}
.pick-lines .pk{font:800 20px/1.2 var(--mono);letter-spacing:-.01em}
.pick-lines .pk.na{font:600 14px/1.4 var(--sans);color:var(--muted)}
.pick-lines .edge{font:600 12.5px/1.3 var(--sans)}
.mk{font:500 12.5px/1.5 var(--mono);color:var(--muted);margin-top:6px}
.mk span{white-space:nowrap}
.flags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.g-note{font:500 12px/1.4 var(--sans);color:var(--faint);margin-top:8px}
.detail{padding:14px 16px 18px}
.detail h3{font:750 12px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--faint);margin:16px 0 8px}
.detail p{margin:8px 0;font-size:13.5px}
.detail .gr-tablewrap{box-shadow:none}
.detail table.gr{font-size:13px}.detail table.gr td,.detail table.gr th{padding:8px 11px}
/* folds */
.fold{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);margin:0 0 10px;overflow:clip}
.fold>summary{cursor:pointer;list-style:none;padding:14px 16px;font:700 14.5px/1.3 var(--sans);display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}
.fold>summary::-webkit-details-marker{display:none}
.fold>summary::before{content:"▸";color:var(--faint);transition:transform .15s}
.fold[open]>summary::before{transform:rotate(90deg)}
.fold>summary:hover{background:var(--surface-2)}
.fold .rt{margin-left:auto;font:600 13px/1 var(--mono);color:var(--muted)}
.fold .gr-tablewrap{box-shadow:none;border-width:1px 0 0;border-radius:0;margin:0}
.record{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:14px 18px;margin:0 0 16px;font-size:14px}
.rec-line{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r);padding:11px 16px;margin:0 0 8px;font-size:14px;box-shadow:var(--shadow)}
.rec-line .l{font:700 11.5px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
.rec-line b{font-size:16px}.rec-line a{margin-left:auto;font-weight:650;text-decoration:none}
details.how>summary{cursor:pointer;font-weight:650;color:var(--ink)}details.how p{margin:8px 0 0}
abbr[title]{text-decoration:underline dotted;cursor:help}
.tools{display:flex;flex-wrap:wrap;gap:8px}
.pick-lines .edge{border:1px solid rgba(var(--accent),.4);background:rgba(var(--accent),.09);color:rgb(var(--accent-tx));
  border-radius:var(--r-pill);padding:3px 8px;font-weight:700}
.pick-lines .edge.tie{border-color:var(--line);background:var(--surface-2);color:var(--muted)}
.pick-lines .px{font:600 13px/1 var(--mono);color:var(--muted);margin-left:8px;letter-spacing:0}
.moved{font:600 12px/1.4 var(--sans);color:rgb(var(--lean-tx));margin-top:4px}
.gr-head+.primer{margin-top:-8px}
.primer ul{margin:8px 0 0;padding-left:18px}.primer li{margin:4px 0}
.foot .disclaimer{flex-basis:100%}
.record .l{font:700 11.5px/1.2 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--faint);margin-bottom:6px}
/* chart */
.chart{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:16px 18px 10px;margin:0 0 12px}
.chart-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.chart-head .t{font:700 14px/1.3 var(--sans)}.chart-head .v{font:800 18px/1 var(--mono)}
.chart svg{display:block;width:100%;height:auto;margin-top:8px;overflow:visible}
.chart .grid-ln{stroke:var(--line-2);stroke-width:1}
.chart .zero{stroke:var(--faint);stroke-width:1;stroke-dasharray:3 3}
.chart .ln{fill:none;stroke:rgb(var(--accent));stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .area{fill:rgba(var(--accent),.08)}
.chart .ax{fill:var(--faint);font:500 13px var(--mono)}
.chart .pt{fill:rgb(var(--accent));stroke:var(--surface);stroke-width:2}
.chart .hit{fill:transparent;cursor:default}
.chart .hit:hover+.pt{r:6}
.chart svg.narrow{display:none}
.chart svg.narrow .ax{font-size:11px}
/* steps */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:0 0 12px;padding:0;list-style:none;counter-reset:s}
.steps li{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--shadow);
  font-size:14px;line-height:1.55;color:var(--muted);counter-increment:s}
.steps li b{display:block;color:var(--ink);font-size:15px;margin-bottom:4px}
.steps li::before{content:counter(s);display:grid;place-items:center;width:26px;height:26px;border-radius:50%;
  background:rgba(var(--accent),.12);color:rgb(var(--accent-tx));font:800 13px/1 var(--mono);margin-bottom:10px}
.empty{background:var(--surface);border:1px dashed var(--line);border-radius:var(--r);padding:22px;color:var(--muted);text-align:center}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px 18px;margin-top:44px;padding-top:16px;
  border-top:1px solid var(--line);color:var(--faint);font-size:12.5px;line-height:1.6}
.foot a{color:var(--muted)}
@media (max-width:720px){
  .topbar{flex-wrap:wrap;gap:12px;padding:14px 0;margin-bottom:16px}
  .nav{order:3;width:100%;margin-left:0}.nav a{flex:1;text-align:center;padding:9px 6px}
  .theme{margin-left:auto}
  .rec-line a{margin-left:0;width:100%}
  .gr-h1{font-size:28px}
  .gr-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
  .gr-stat{padding:13px 13px}.gr-stat .v{font-size:22px}
  .grid{grid-template-columns:minmax(0,1fr)}
  table.gr{font-size:13px}table.gr th,table.gr td{padding:9px 10px;white-space:nowrap}
  .detail table.gr td{white-space:normal}
  .fold .rt{margin-left:0;width:100%}
  .chart svg.wide{display:none}.chart svg.narrow{display:block}
  /* Results: each game becomes a two-line row so the result and units stay on screen. */
  table.games thead{display:none}
  table.games tr{display:grid;grid-template-columns:minmax(0,1fr) auto auto;grid-template-areas:"game result units" "pick odds final";
    gap:4px 12px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line-2)}
  table.games tr:last-child{border-bottom:0}
  table.games td{display:block;padding:0;border:0;white-space:normal}
  table.games td:nth-child(1){grid-area:game}table.games td:nth-child(2){grid-area:pick}
  table.games td:nth-child(3){grid-area:odds;text-align:right;font-family:var(--mono);font-size:12.5px}
  table.games td:nth-child(3) .small{display:inline;margin-left:4px;font-family:var(--sans)}
  table.games td:nth-child(4){display:none}
  table.games td:nth-child(5){grid-area:final;text-align:right}
  table.games td:nth-child(6){grid-area:result;text-align:right}table.games td:nth-child(7){grid-area:units;text-align:right}
  /* By week: the price-source and pending counts are secondary on a phone. */
  table.weekly th:nth-child(4),table.weekly td:nth-child(4),table.weekly th:nth-child(5),table.weekly td:nth-child(5){display:none}
  table.weekly th,table.weekly td{padding:9px 6px;font-size:12px}
  table.gr.weekly th,table.gr.weekly td{white-space:normal}table.gr.weekly td:first-child{white-space:nowrap}
  table.weekly td .small{font-size:11px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

THEME_JS = """<script>(function(){var k='nfl-theme',r=document.documentElement;
try{var s=localStorage.getItem(k);if(s)r.setAttribute('data-theme',s);}catch(e){}
window.toggleTheme=function(){var d=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
var n=d==='dark'?'light':'dark';r.setAttribute('data-theme',n);try{localStorage.setItem(k,n);}catch(e){}};})();</script>"""

# Show/hide game cards by state; without script every card stays visible.
FILTER_JS = """<script>(function(){var bar=document.querySelector('.seg[data-filter]');if(!bar)return;
bar.hidden=false;bar.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;
var f=b.getAttribute('data-show');bar.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
document.querySelectorAll('.card[data-state]').forEach(function(c){c.hidden=f!=='all'&&c.getAttribute('data-state')!==f;});});})();
(function(){var bar=document.querySelector('.seg[data-sort-bar]'),grid=document.querySelector('.grid');if(!bar||!grid)return;
var order=Array.from(grid.children);bar.hidden=false;bar.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;
var by=b.getAttribute('data-sort');bar.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
var cards=order.slice();if(by==='gap')cards.sort(function(a,c){var f=(a.dataset.state==='final')-(c.dataset.state==='final');
return f||parseFloat(c.dataset.gap)-parseFloat(a.dataset.gap);});cards.forEach(function(c){grid.appendChild(c);});});})();
(function(){function expire(){document.querySelectorAll('[data-provisional-cutoff]').forEach(function(c){
if(Date.now()<Date.parse(c.dataset.provisionalCutoff))return;
c.removeAttribute('data-provisional-cutoff');
c.querySelectorAll('.picked').forEach(function(t){t.classList.remove('picked');});
var p=c.querySelector('.pk');if(p)p.textContent='Refresh for saved selection';
var n=c.querySelector('.g-note');if(n)n.textContent='Lock time passed · provisional forecast expired';
var b=c.querySelector('.badge.live');if(b)b.textContent='Awaiting saved pick';
});}expire();setInterval(expire,1000);})();</script>"""

# Check saved publication state, including in tabs left open across T-60 or a
# final score. Never synthesize a lock or grade from the browser's clock/feed.
REFRESH_JS = """<script>(function(){
var meta=document.querySelector('meta[name="site-version"]');
if(!meta||! /^[a-f0-9]{64}$/.test(meta.content))return;
var key='nfl-view:'+location.pathname,busy=false;
try{var saved=JSON.parse(sessionStorage.getItem(key)||'null');sessionStorage.removeItem(key);
if(saved){(saved.open||[]).forEach(function(id){document.querySelectorAll('details[data-game-id]').forEach(function(c){if(c.dataset.gameId===id)c.open=true;});});
var filter=document.querySelector('.seg button[data-show="'+saved.filter+'"]');if(filter)filter.click();
window.addEventListener('load',function(){window.scrollTo(0,saved.scroll||0);},{once:true});}}catch(e){}
async function check(){if(document.hidden||busy)return;busy=true;
var controller=new AbortController(),timeout=setTimeout(function(){controller.abort();},10000);
try{var response=await fetch('site-state.json',{cache:'no-store',signal:controller.signal});
if(!response.ok)return;var state=await response.json();
if(!state||! /^[a-f0-9]{64}$/.test(state.version)||state.version===meta.content)return;
var selected=document.querySelector('.seg[data-filter] button[aria-pressed="true"]');
try{sessionStorage.setItem(key,JSON.stringify({open:Array.from(document.querySelectorAll('details[data-game-id][open]')).map(function(c){return c.dataset.gameId;}),
filter:selected?selected.dataset.show:'all',scroll:window.scrollY}));}catch(e){}
var url=new URL(location.href);url.searchParams.set('_v',state.version);location.replace(url.href);
}catch(e){}finally{clearTimeout(timeout);busy=false;}}
setInterval(check,60000);document.addEventListener('visibilitychange',check);
})();</script>"""

# Viewer-local times; the formatted Pacific text stays if Intl is unavailable.
LOCAL_TIME_JS = """<script>(function(){try{var o={weekday:'short',hour:'numeric',minute:'2-digit',timeZoneName:'short'},
f=new Intl.DateTimeFormat([],o),g=new Intl.DateTimeFormat([],Object.assign({month:'short',day:'numeric'},o));
document.querySelectorAll('time[data-local]').forEach(function(t){var d=new Date(t.getAttribute('datetime'));
if(!isNaN(d))t.textContent=(t.getAttribute('data-local')==='date'?g:f).format(d).replace(/,/g,'');});}catch(e){}})();</script>"""

THEME_ICON = ("<svg class='sun' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' aria-hidden='true'>"
              "<circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></svg>"
              "<svg class='moon' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' aria-hidden='true'>"
              "<path d='M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z'/></svg>")

PAGES = (("index.html", "Picks"), ("grades.html", "Results"),
         ("market-calibration.html", "Performance"),
         ("historical-calibration.html", "Calibration"))
PAGE_HELP = {"index.html": "This week's picks", "grades.html": "Every 2026 pick and how it graded",
             "market-calibration.html": "Running units, simple baselines and how picks work",
             "historical-calibration.html": "Advanced: 2023–2026 results by line size and win-probability band"}


def font_face_css(assets=ASSETS):
    out = []
    for family, fname, weight in (("Archivo", "archivo-subset.woff2", "100 900"),
                                  ("JetBrains Mono", "jetbrains-mono-subset.woff2", "400 800")):
        p = Path(assets) / fname
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            out.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                       f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2-variations')}}")
    return "".join(out)


DEFAULT_DESCRIPTION = 'NFL against-the-spread picks, locked 60 minutes before kickoff, with season results.'
DISCLAIMER = ('For information only; not betting advice. Must be 21+ and in a legal jurisdiction to bet. '
              'Gambling problem? Call 1-800-GAMBLER.')
# The brand mark as the browser-tab icon, embedded so it needs no extra file.
ICON = "data:image/svg+xml," + quote(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='16' fill='#09785e'/>"
    "<text x='32' y='42' font-family='Arial,sans-serif' font-size='26' font-weight='800' fill='#fff' "
    "text-anchor='middle'>NF</text></svg>", safe="/:=,'() ")  # '#' must be encoded in a data URI


def html_document(body, title, current, built, scripts="", extra_css="", description=DEFAULT_DESCRIPTION):
    nav = "".join(f"<a href='{href}'{' aria-current=\"page\"' if href == current else ''} title='{esc(PAGE_HELP.get(href, ''))}'>{label}</a>"
                  for href, label in PAGES)
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta name='site-version' content='__NFL_SITE_VERSION__'>"
            f"<title>{esc(title)}</title><meta name='description' content='{esc(description)}'>"
            f"<link rel='icon' type='image/svg+xml' href=\"{ICON}\">"
            f"<meta property='og:type' content='website'><meta property='og:site_name' content='{SITE_NAME}'>"
            f"<meta property='og:title' content='{esc(title)}'><meta property='og:description' content='{esc(description)}'>"
            "<meta name='twitter:card' content='summary'>"
            "<meta name='color-scheme' content='light dark'>"
            f"{THEME_JS}<style>{font_face_css()}{CSS}{extra_css}</style></head><body><a class='skip-link' href='#main-content'>Skip to content</a><div class='mx-wrap'>"
            f"<header class='topbar'><a class='brand' href='index.html'><span class='brand-mark' aria-hidden='true'>NF</span>{SITE_NAME}</a>"
            f"<nav class='nav' aria-label='Main navigation'>{nav}</nav>"
            f"<button class='theme' type='button' onclick='toggleTheme()' aria-label='Toggle colour theme' title='Toggle theme'>{THEME_ICON}</button></header>"
            f"<main id='main-content'>{body}</main>"
            f"<footer class='foot'><span>Updated <span class='stamp'>{esc(built)}</span> · model {esc(m.REVISION.rsplit('-', 1)[-1])}</span>"
            "<span>Flat 1-unit stakes. ESPN prices and assumed −110 prices are labelled; returns are estimates.</span>"
            f"<span class='disclaimer'>{DISCLAIMER}</span>"
            f"</footer></div>{scripts}{LOCAL_TIME_JS}{REFRESH_JS}</body></html>")


def head(title, lead, eyebrow="", aside=""):
    top = f"<div class='eyebrow'>{esc(eyebrow)}</div>" if eyebrow else ""
    return (f"<div class='gr-head'><div>{top}<h1 class='gr-h1'>{esc(title)}</h1>"
            f"<div class='gr-lead'>{lead}</div></div>{aside}</div>")


def stat(label, value, sub="", tone=""):
    return (f"<div class='gr-stat'><div class='l'>{esc(label)}</div>"
            f"<div class='v{(' ' + tone) if tone else ''}'>{value}</div>"
            f"{f'<div class=s>{sub}</div>' if sub else ''}</div>")


def table(heads, rows, num_cols=(), table_class=''):
    th = "".join(f"<th{' class=n' if i in num_cols else ''}>{h}</th>" for i, h in enumerate(heads))
    body = []
    for r in rows:
        cls = r.pop("_class", "") if isinstance(r, dict) else ""
        cells = r["cells"] if isinstance(r, dict) else r
        tds = "".join(f"<td{' class=n' if i in num_cols else ''}>{c}</td>" for i, c in enumerate(cells))
        body.append(f"<tr{f' class={cls}' if cls else ''}>{tds}</tr>")
    return f"<div class='gr-tablewrap'><table class='gr{(' ' + table_class) if table_class else ''}'><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


# ---------------------------------------------------------------- shared pieces
# Public pages carry W-L, win % and ROI only. Standard errors, no-vig q, excess,
# log loss and recipe details stay in data/ledger_report.txt and data/latest/.

def pt_text(when):
    return when.astimezone(PT).strftime("%a %-I:%M %p %Z")


def local_time(when):
    """A Pacific time that the page script rewrites into the viewer's own zone.
    Without script (and for crawlers) the Pacific text stands."""
    utc = pd.Timestamp(when).tz_convert('UTC')
    return f"<time datetime='{utc.strftime('%Y-%m-%dT%H:%M:%SZ')}' data-local>{esc(pt_text(utc))}</time>"


def kickoff_text(r):
    ko = m.kickoff_utc(r)
    return pt_text(ko) if ko else "TBD"


def kickoff_html(r):
    ko = m.kickoff_utc(r)
    return local_time(ko) if ko else "TBD"


def ml_text(ml):
    ml = num(ml)
    return "—" if not math.isfinite(ml) else f"{ml:+.0f}".replace("-", "−")


def spread_text(home_margin, home, digits=1):
    """A team's point spread from an expected home margin (positive = home favored):
    the home side gets -margin, the away side +margin. "PK" when it rounds to zero."""
    x = num(home_margin)
    if not math.isfinite(x):
        return "—"
    x = -x if home else x
    t = f"{x:+.{digits}f}"
    return "PK" if float(t) == 0 else t.replace("-", "−")


def favorite_spread_text(home_margin, home, away, digits=1):
    """The favorite and its spread, e.g. "DAL −4.6"; "PK" for a pick'em."""
    x = num(home_margin)
    if not math.isfinite(x):
        return "—"
    t = spread_text(x, x > 0, digits)
    return t if t == "PK" else f"{esc(home if x > 0 else away)} {t}"


def model_spread(r):
    """Model-implied home margin: the board's model_spread, or derived from model_wp
    for a board published before the column existed."""
    x = num(r.get("model_spread"))
    return x if math.isfinite(x) else float(m.implied_spread([r.get("model_wp")])[0])


def roi_short(roi):
    return "—" if not math.isfinite(num(roi)) else f"{100 * roi:+.1f}%".replace("-", "−")


UNIT_NAMES = {"OL": "Offensive line", "WRTE": "Receivers", "RB": "Running backs",
              "DL": "Defensive line", "LB": "Linebackers", "DB": "Secondary"}

PASS_CONTEXT_LABELS = {"pp": "Strong attack, vulnerable defense",
                       "pn": "Strong attack, strong defense",
                       "np": "Struggling attack, vulnerable defense",
                       "nn": "Struggling attack, strong defense"}
FACTOR_METRICS = {
    "net_pass_yards_per_pass_play": ("Passing efficiency", "Pass defense", "Net yards per pass play"),
    "rush_yards_per_attempt": ("Rushing efficiency", "Run defense", "Yards per rush"),
    "first_down_rate": ("Sustaining drives", "Stopping drives", "First-down rate"),
    "interception_pct": ("Interceptions thrown", "Interceptions forced", "Interceptions per pass attempt"),
    "fumbles_lost_per_game": ("Fumbles lost", "Fumble takeaways", "Fumbles lost per game"),
    "plays_per_game": ("Offensive pace", "Plays faced", "Plays per game"),
    "penalty_yards_per_game": ("Offensive penalties", "Opponent penalties", "Penalty yards per game"),
}


def result_badge(res):
    if res not in ("W", "L", "P"):
        return "—"
    return f"<span class='badge {'w' if res == 'W' else 'l' if res == 'L' else ''}'>{res}</span>"


def score_text(away, home):
    a, h = num(away), num(home)
    return f"{int(a)}–{int(h)}" if math.isfinite(a) and math.isfinite(h) else ""


def folded(summary, inner, open_=False):
    return (f"<details class='fold'{' open' if open_ else ''}><summary>{summary}</summary>{inner}</details>")


SMALL_SAMPLE = 30  # fewer games than this at a price: flag the rate as a small sample


# ---------------------------------------------------------------- pages

def ats_card_pick(spread, market, home, away, favorite_on_tie=True):
    if not math.isfinite(spread) or not math.isfinite(market):
        return 'Unavailable', math.nan
    side = fixed_bands.pick(spread, market, favorite_on_tie)
    if side == 0:
        return 'No bet · zero projected edge', 0.
    team = home if side > 0 else away
    return f'{esc(team)} {spread_text(market, side > 0)}', abs(spread - market)


def ats_card_state(latest, row, now):
    """One ATS-only display state shared by cards and the board download."""
    rev = latest['manifest']['revision']
    home, away = row['home'], row['away']
    ms, line = num(row.get('fixed_band_spread')), num(row.get('spread_line'))
    saved = ats_locks.public_records(latest.get('ats_locks', {}), rev).get((rev, row['game_id']))
    completed = None
    pooled_row = None
    display_row = dict(row)
    pool = public_ats(latest)
    if len(pool):
        matches = pool.loc[pool.game_id.eq(row['game_id'])]
        if len(matches) > 1:
            raise ValueError('Duplicate public ATS game')
        if len(matches):
            candidate = matches.iloc[0]
            pooled_row = candidate
            if candidate.ats_status == 'graded' and math.isfinite(num(candidate.get('result'))):
                display_row.update({name: candidate.get(name) for name in ('result', 'home_score', 'away_score')})
                if (saved is None and candidate.ats_basis in {'Historical replay', 'Replayed pregame forecast'}
                        and candidate.fixed_band_ats_result in {'W', 'L', 'P', 'S'}
                        and math.isfinite(num(candidate.fixed_band_spread))
                        and math.isfinite(num(candidate.spread_line))):
                    completed = candidate
    ko = m.kickoff_utc(row)
    cutoff = ats_locks.deadline(ko) if ko is not None else None
    source, status, note, note_at = 'Provisional', 'provisional', '', None
    if saved is not None:
        ms, line = num(saved['fixed_band_spread']), num(saved['market_spread'])
        status = 'locked'
        source = ('Owner-requested retro lock' if saved.get('retro_locked')
                  else 'Recovered saved forecast' if saved.get('recovered_after_kickoff')
                  else 'Earlier recorded pick' if saved.get('legacy_lock') else '60-minute lock')
        note_at = ats_locks.utc(saved['lock_at_utc'])
        note = f'ATS locked {pt_text(note_at)}'
    elif completed is not None:
        # The season pool already owns this completed selection. Never use a
        # refreshed postgame line/probability to recreate the public result.
        ms, line = num(completed.fixed_band_spread), num(completed.spread_line)
        status, source, note = 'graded', completed.ats_basis, 'Final ATS result'
    elif cutoff is not None and now >= cutoff:
        status, source, note = 'unavailable', 'No saved ATS selection', 'ATS lock unavailable'
    elif cutoff is not None:
        note_at = cutoff
        note = f'Locks {pt_text(note_at)}'
    else:
        note = 'Lock time pending · kickoff unconfirmed'
    if saved is not None and ats_locks.backfilled(saved):
        # Owner decision 2026-10-19: a saved skip is graded as a favorite bet.
        source = 'Backfilled recorded skip'
    pick, gap = ats_card_pick(ms, line, home, away)
    if status == 'unavailable':
        pick, gap = 'Unavailable · no saved pre-lock forecast', math.nan
    grade, units = '', math.nan
    if completed is not None:
        grade, units = completed.fixed_band_ats_result, num(completed.fixed_band_ats_units)
    elif status == 'locked' and math.isfinite(num(display_row.get('result'))):
        grades, returns = fixed_bands.grade(pd.DataFrame({
            'spread_line': [line], 'result': [num(display_row['result'])]}), [ms])
        grade, units = grades[0], returns[0]
        if len(pool):
            match = pool.loc[pool.game_id.eq(row['game_id'])]
            if len(match):
                grade, units = match.iloc[0].fixed_band_ats_result, num(match.iloc[0].fixed_band_ats_units)
    chosen = fixed_bands.pick(ms, line) if math.isfinite(ms-line) else 0.
    side = '' if status == 'unavailable' or chosen == 0 else ('home' if chosen > 0 else 'away')
    price_info = {}
    if len(pool):
        matches = pool.loc[pool.game_id.eq(row['game_id'])]
        if len(matches):
            price_info = {name: matches.iloc[0].get(name) for name in
                          ('ats_price', 'ats_price_basis', 'ats_book', 'ats_quote_utc')}
    return dict(model_spread=ms, spread_line=line, pick=pick, gap=gap, status=status,
                source=source, note=note, note_at=note_at, saved=saved, result=grade, units=units,
                display_row=display_row, **price_info,
                selected_side=side, selected_team=row[side] if side else '',
                handicap=(-line if side == 'home' else line) if side else math.nan)


def locked_line_html(row, state, final):
    """After lock, note when the market has moved off the saved handicap. Display only:
    the saved line and price stay the bet."""
    current, line = num(row.get('spread_line')), num(state.get('spread_line'))
    if (state.get('status') != 'locked' or final or not state.get('selected_side')
            or not math.isfinite(current) or not math.isfinite(line) or abs(current - line) <= fixed_bands.EPS):
        return ''
    return (f"<div class='moved'>Line now {esc(state['selected_team'])} "
            f"{spread_text(current, state['selected_side'] == 'home')} · graded at the locked line</div>")


def render_index(latest, ledger, built, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if latest is None or latest['board'].empty:
        return html_document(head('ATS picks', 'No model run has been published yet; the first build writes this page.'),
                             f'{SITE_NAME} picks', 'index.html', built)
    man, board = latest['manifest'], latest['board']
    season, week = int(man['season']), int(man['week'])
    has_avail = (man.get('recipe') or {}).get('family', '') in m.AVAIL_FAMILIES
    stamp = pd.to_datetime(man.get('generated_utc'), utc=True, errors='coerce')
    local = stamp.tz_convert(PT) if pd.notna(stamp) else None
    # A compact header: the season record lives on Results and the explanation in "How picks work".
    updated = (f"Updated <time datetime='{stamp.tz_convert('UTC').strftime('%Y-%m-%dT%H:%M:%SZ')}' data-local='date'>"
               f"{esc(local.strftime('%a %b %-d · %-I:%M %p %Z'))}</time> · " if local is not None else '')
    parts = [head(f'Week {week} picks', f"{updated}<a href='market-calibration.html#how'>How picks work</a>",
                  f'{season} regular season'), SPREAD_PRIMER]

    def pending(row):
        ko = m.kickoff_utc(row)
        return (has_avail and pd.isna(row.get('result')) and ko is not None and ko > now
                and not m.injury_reports_ready(row, ko, now))

    raw_rows = board.to_dict('records')
    states = {r['game_id']: ats_card_state(latest, r, now) for r in raw_rows}
    rows = [states[r['game_id']]['display_row'] for r in raw_rows]
    count = sum(pending(r) for r in rows)
    if count:
        parts.append(f"<div class='gr-note flag-note'>Injury reports aren't final for {count} "
                     f"game{'s' if count != 1 else ''} yet, so {'those numbers' if count != 1 else 'that number'} can still move.</div>")
    far = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    rows.sort(key=lambda r: (pd.notna(r.get('result')), m.kickoff_utc(r) or far, str(r['game_id'])))
    finals = sum(pd.notna(r.get('result')) for r in rows)
    seg = "".join(f"<button type='button' data-show='{k}' aria-pressed='{'true' if k == 'all' else 'false'}'>"
                  f"{label}<span class='ct'>{n}</span></button>"
                  for k, label, n in (('all', 'All', len(rows)), ('upcoming', 'Upcoming', len(rows) - finals),
                                      ('final', 'Final', finals)))
    sort = ("<button type='button' data-sort='time' aria-pressed='true'>Kickoff</button>"
            "<button type='button' data-sort='gap' aria-pressed='false'>Biggest gap</button>")
    parts.append(f"<div class='toolbar'><h2 class='sec'>This week’s games</h2><div class='tools'>"
                 f"<div class='seg' data-sort-bar role='group' aria-label='Sort games' hidden>{sort}</div>"
                 f"<div class='seg' data-filter role='group' aria-label='Filter games' hidden>{seg}</div></div></div>")
    cards = []
    for row in rows:
        home, away = row['home'], row['away']
        state = states[row['game_id']]
        ms, line = state['model_spread'], state['spread_line']
        final = pd.notna(row.get('result'))
        if final:
            status = f"<span class='badge'>Final {score_text(row.get('away_score'), row.get('home_score'))}</span>"
        elif state['status'] == 'locked':
            status = "<span class='badge lock'>Locked ✓</span>"
        elif state['status'] == 'unavailable':
            status = "<span class='badge'>No pick</span>"
        else:
            status = "<span class='badge live'>Can still change</span>"
        flags = []
        if state['result']:
            result = 'Skip' if state['result'] == 'S' else state['result']
            tone = 'w' if state['result'] == 'W' else 'l' if state['result'] == 'L' else ''
            units = f" · <span class='u'>{units_text(state['units'])}</span>" if math.isfinite(state['units']) else ''
            flags.append(f"<span class='badge {tone}'>ATS result · {esc(result)}{units}</span>")
        if not bool(row.get('ready', True)):
            flags.append("<span class='badge'>Limited history</span>")
        for side in ('away', 'home'):
            expected, usual = row.get(f'{side}_qb_expected'), row.get(f'{side}_qb_usual')
            if isinstance(expected, str) and isinstance(usual, str) and expected != usual:
                flags.append(f"<span class='badge warn'>{esc(row[side])} QB: {esc(expected)}</span>")
        gap = state['gap']
        if not state['selected_side'] or not math.isfinite(gap):
            edge = ''
        elif gap > fixed_bands.EPS:
            edge = (f"<span class='edge' title='Gap between the model spread and the market line. "
                    f"It describes the disagreement; it is not a win probability.'>Model differs by {gap:g} pt{'s' if gap != 1 else ''}</span>")
        else:
            edge = ("<span class='edge tie' title='The model matches the line exactly; ties take the market favorite.'>"
                    "Matches line · favorite</span>")
        price = num(state.get('ats_price'))
        price_html = (f"<span class='px' title='Spread price used for grading'>{ml_text(price)}</span>"
                      if state['status'] in ('locked', 'graded') and state['selected_side'] and math.isfinite(price) else '')
        moved = locked_line_html(row, state, final)
        pick = (f"<div class='pick-lines'><span class='kind'>ATS pick</span>"
                f"<span class='pk{'' if state['selected_side'] else ' na'}'>{state['pick']}{price_html}</span>{edge}</div>{moved}")
        spreads = (f"<span>Model {favorite_spread_text(ms, home, away)}</span>"
                   + (f" · <span>Market {favorite_spread_text(line, home, away)}</span>" if math.isfinite(line) else ''))

        def team(code, side):
            chip = f"<div class='chip'><span>{esc(code)}</span>{logo_html(code)}</div>"
            score = num(row.get(f'{side}_score'))
            sc = f"<span class='sc'>{int(score)}</span>" if final and math.isfinite(score) else "<span></span>"
            picked = ' picked' if state['selected_side'] == side else ''
            return (f"<div class='g-team{picked}'>{chip}<span class='nm'>{esc(TEAM_NAMES.get(code, code))}"
                    f"<small>{'@ ' if side == 'home' else ''}{esc(code)}</small></span>"
                    f"<span class='ln'>{spread_text(line, side == 'home')}</span>{sc}</div>")

        note_html = esc(state['note'])
        if state.get('note_at') is not None:
            note_html = note_html.replace(esc(pt_text(state['note_at'])), local_time(state['note_at']))
        summary = (f"<summary class='game-summary'><div class='g-meta'><span class='when'>{kickoff_html(row)}</span>{status}</div>"
                   f"<div class='g-teams'>{team(away, 'away')}{team(home, 'home')}</div>{pick}"
                   f"<div class='mk sp'>{spreads}</div>"
                   f"{f'<div class=flags>{chr(32).join(flags)}</div>' if flags else ''}"
                   f"<div class='g-note'>{note_html}{' · injury reports pending' if pending(row) else ''}</div></summary>")
        detail = ["<div class='detail'><h3>Spreads</h3>", table(['', esc(away), esc(home)], [
            ['Model spread', spread_text(ms, False), spread_text(ms, True)],
            ['Market spread', spread_text(line, False), spread_text(line, True)]], num_cols=(1, 2))]
        if state['saved'] is not None:
            forecast = ats_locks.utc(state['saved']['generated_utc']).astimezone(PT).strftime('%a %-I:%M %p %Z')
            detail.append(f"<p class='mut'>Saved ATS selection · forecast {esc(forecast)}. "
                          "The model spread, market handicap and selection shown above are fixed.</p>")
        elif state['status'] == 'unavailable':
            detail.append("<p class='mut'>No pick was saved before this game's lock time, so it is not graded.</p>")
        elif state['status'] == 'graded':
            detail.append("<p class='mut'>The ATS selection and listed handicap match the season results.</p>")
        if state['status'] in ('locked', 'graded'):
            label = {'closing_estimate': 'Closing estimate', 'assumed_minus110': 'Assumed −110'}.get(
                state.get('ats_price_basis'), 'Pre-lock price')
            detail.append(f"<p class='mut'>Spread odds {ml_text(state.get('ats_price'))} · "
                          f"{label if math.isfinite(num(state.get('ats_price'))) else 'Unpriced; excluded from ROI'}.</p>")
        if has_avail:
            detail.append(f"<h3>Quarterbacks</h3><p class='mut'>{esc(away)} {_qb(row, 'away')} · {esc(home)} {_qb(row, 'home')}</p>")
            detail.append(report_notes_html(latest.get('report_notes'), (away, home), int(row['week'])))
        detail.append('</div>')
        tone = ' picked-card' if state['selected_side'] else ''
        cutoff_attr = (f" data-provisional-cutoff='{ats_locks.deadline(m.kickoff_utc(row)).isoformat()}'"
                       if state['status'] == 'provisional' and m.kickoff_utc(row) is not None else '')
        gap_attr = f" data-gap='{state['gap']:g}'" if state['selected_side'] and math.isfinite(state['gap']) else " data-gap='-1'"
        cards.append(f"<details class='card{tone}' data-game-id='{esc(row['game_id'])}' data-state='{'final' if final else 'upcoming'}'{gap_attr}{cutoff_attr}>"
                     f"{summary}{''.join(detail)}</details>")
    parts.append(f"<div class='grid'>{''.join(cards)}</div>")
    parts.append(f"<p class='mut small'>Model and market spreads are shown from the favorite’s side; the highlighted team "
                 f"is the pick. Saved handicaps and selections stay fixed after lock.</p>"
                 + pricing_note(public_ats(latest)) +
                 "<p><a href='grades.html'>View ATS results →</a></p>")
    share = f'Week {week} against-the-spread picks, locked 60 minutes before kickoff.'
    pool = public_ats(latest)
    if len(pool):
        r = season_ats.summary(pool)
        if r['bets']:
            share += f" {season}: {r['wins']}–{r['losses']}–{r['pushes']}, {units_text(r['units'])}."
    return html_document(''.join(parts), f'{SITE_NAME} — week {week}', 'index.html', built, FILTER_JS,
                         description=share)

SPREAD_PRIMER = (
    "<details class='gr-note how primer'><summary>New to spread betting?</summary><ul>"
    "<li><b>The spread</b> evens out a game. ARI +16.5 wins if Arizona wins or loses by 16 or fewer; "
    "KC −16.5 wins only if Kansas City wins by 17 or more. A margin landing exactly on a whole-number line is a push and the stake is returned.</li>"
    "<li><b>Covered</b> means the pick won against the spread, whatever the final winner.</li>"
    "<li><b>−110</b> means risking 1.10 to win 1.00. At that price a pick needs to win about 52.4% of decided bets to break even.</li>"
    "<li><b>Units</b> are the profit or loss from staking 1 unit on every pick. ROI is that profit divided by the total staked.</li>"
    "</ul></details>")

STATE_TEXT = {
    "none": "Week {w} injury report is pending.",
    "practice": "Practice report available; final game status is pending.",
    "final": "Final injury report available.",
}


def report_notes_html(notes, teams, week):
    """Per-team injury-report notes: who is listed and how much the model counts them out."""
    if notes is None or notes.empty:
        return ""
    out = ["<h3>Injury report</h3>"]
    for t in teams:
        n = notes[notes.team == t]
        if n.empty:
            continue
        rows, reserve = [], []
        for x in n.itertuples(index=False):
            status = str(x.this_week)
            if '(left team)' in status:
                continue  # no longer on the roster; still counted by the model, but not news
            row = [f"{esc(x.player)} <span class='mut'>{esc(x.position)}</span>", esc(status)]
            (reserve if status.startswith('Reserve/') else rows).append(row)
        rows += reserve
        if not rows:
            continue
        out.append(f"<p class='mut'><b>{esc(t)}</b> · {esc(STATE_TEXT.get(n.report_state.iloc[0], '').format(w=week))}</p>"
                   + table(["Player", f"Week {week} status"], rows))
    return "".join(out) if len(out) > 1 else ""


def _qb(r, side):
    e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
    if not isinstance(e, str):
        return "—"
    return esc(e) + (f" (usual {esc(u)})" if isinstance(u, str) and u != e else "")


# Every public season surface uses the same deduplicated pool. Provenance stays
# in season_ats and the repository report rather than the customer interface.
PUBLIC_BASES = {'Historical replay', 'Replayed pregame forecast', '60-minute lock',
                'Recorded pregame', 'Recovered saved forecast', 'Owner-requested retro lock',
                'Backfilled recorded skip', 'Awaiting ATS lock'}
BREAK_EVEN = 110 / 210


def public_ats(latest):
    """All 2026 ATS rows from the season pool, including replay and pending games."""
    pooled = (latest or {}).get('pooled_ats', pd.DataFrame())
    if pooled is None or pooled.empty or 'ats_basis' not in pooled:
        return pd.DataFrame()
    return pooled.loc[pooled.ats_basis.isin(PUBLIC_BASES)].copy().reset_index(drop=True)


def units_text(u):
    u = num(u)
    return "—" if not math.isfinite(u) else f"{u:+.2f}u".replace("-", "−")


SE_HELP = ('Standard error: how far ROI could swing from luck alone. '
           'A range of about two standard errors that crosses 0 means the edge is not yet established.')


def roi_uncertainty(se):
    se = num(se)
    return (f"<abbr title='{SE_HELP}'>± {100 * se:.1f} pp SE</abbr>" if math.isfinite(se)
            else 'SE unavailable')


def record_tiles(frame, label):
    """Record, cover rate against break-even, units and ROI for the season pool."""
    if frame is None or frame.empty:
        return "<div class='empty'>No ATS results yet. Season results appear here as games are graded.</div>"
    r = season_ats.summary(frame)
    tone = lambda x: '' if not math.isfinite(num(x)) or num(x) == 0 else 'good' if num(x) > 0 else 'bad'
    rate = num(r['cover_rate'])
    meter = ''
    if math.isfinite(rate):
        meter = (f"<div class='meter' role='img' aria-label='Cover rate {pct(rate, 1)}, minus 110 reference {pct(BREAK_EVEN, 1)}'>"
                 f"<i style='width:{100 * rate:.1f}%'></i><b style='left:{100 * BREAK_EVEN:.1f}%'></b></div>")
    pending = f" · {r['pending']} pending" if r['pending'] else ''
    tiles = [stat(label, f"{r['wins']}–{r['losses']}–{r['pushes']}", f"W–L–P · {r['bets']} bets{pending}"),
             stat('Cover rate', pct(rate, 1), f"{meter}Break-even {pct(BREAK_EVEN, 1)} at −110 · pushes excluded",
                  '' if not math.isfinite(rate) else 'good' if rate > BREAK_EVEN else 'bad'),
             stat('Estimated units' if r['closing_estimates']+r['assumed_prices'] else 'Units', units_text(r['units']),
                  f"{r['priced_bets']} 1-unit stakes", tone(r['units'])),
             stat('Estimated ROI' if r['closing_estimates']+r['assumed_prices'] else 'ROI', roi_short(r['roi']),
                  f"Profit per unit staked · {roi_uncertainty(r['roi_se'])}", tone(r['roi']))]
    return f"<div class='gr-summary'>{''.join(tiles)}</div>" + pricing_note(frame)


def pricing_note(frame):
    if 'ats_price_basis' not in frame:
        return "<p class='mut small'>−110 reference pricing.</p>"
    r = season_ats.summary(frame)
    return (f"<details class='gr-note how'><summary>How returns are priced</summary>"
            f"<p>ESPN pricing: <b>{r['prelock_prices']} pre-lock</b> · "
            f"<b>{r['closing_estimates']} closing estimates</b> · <b>{r['assumed_prices']} assumed −110</b>. "
            "Prices must match the saved side and handicap. Closing estimates could differ from lock-time prices. "
            "Picks without a matching ESPN price are included at an assumed −110 in pooled units and ROI. "
            "Pushes count as stakes in ROI. The 52.4% break-even marker is a −110 reference; actual thresholds vary with price.</p></details>")


def record_line(frame, label, link=True):
    """One-line season summary for pages whose main content is not the record."""
    if frame is None or frame.empty:
        return ''
    r = season_ats.summary(frame)
    if not r['bets']:
        return (f"<p class='rec-line'><span class='l'>{esc(label)}</span>"
                f"<span class='mut'>No graded picks yet · break-even {pct(BREAK_EVEN, 1)} at −110</span></p>")
    rate = num(r['cover_rate'])
    tone = lambda x: '' if not math.isfinite(num(x)) or num(x) == 0 else 'pos-tx' if num(x) > 0 else 'neg-tx'
    more = " <a href='grades.html'>All results →</a>" if link else ''
    return (f"<p class='rec-line'><span class='l'>{esc(label)}</span>"
            f"<b class='mono'>{r['wins']}–{r['losses']}–{r['pushes']}</b>"
            f"<span>{pct(rate, 1)} covered <span class='mut'>(break-even {pct(BREAK_EVEN, 1)} at −110)</span></span>"
            f"<b class='mono {tone(r['units'])}'>{units_text(r['units'])}</b>"
            f"<span class='mut'>ROI {roi_short(r['roi'])}</span>{more}</p>")


def game_rows(group):
    rows = []
    for r in group.sort_values(['kickoff_utc', 'game_id'] if 'kickoff_utc' in group else 'game_id').to_dict('records'):
        grade = r.get('fixed_band_ats_result', '')
        side, team = r.get('fixed_band_ats_side', ''), r.get('fixed_band_ats_team', '')
        if grade == 'S':
            pick, badge = 'Skip', "<span class='badge'>Skip</span>"
        elif isinstance(team, str) and team:
            pick = f'<b>{esc(team)} {spread_text(num(r.get("spread_line")), side == "home")}</b>'
            badge = result_badge(grade) if grade else "<span class='badge'>Pending</span>"
        else:
            pick = 'Awaiting lock' if r.get('ats_status') == 'pending' else 'No saved pick'
            badge = f"<span class='badge'>{esc(str(r.get('ats_status', 'unavailable')).title())}</span>"
        final = score_text(r.get('away_score'), r.get('home_score')) if math.isfinite(num(r.get('result'))) else 'Pending'
        units = num(r.get('fixed_band_ats_units'))
        price = ml_text(r.get('ats_price'))
        # Closing estimates are the norm; label only the exceptions (explained under the tables).
        price_label = {'captured_prelock': 'pre-lock', 'historical_prelock': 'pre-lock',
                       'closing_estimate': '', 'assumed_minus110': 'assumed'}.get(r.get('ats_price_basis'), 'unpriced')
        tone = 'pos-tx' if units > 0 else 'neg-tx' if units < 0 else ''
        ko = pd.to_datetime(r.get('kickoff_utc'), utc=True, errors='coerce')
        when = f"<div class='mut small'>{local_time(ko)}</div>" if pd.notna(ko) else ''
        day = pd.to_datetime(r.get('gameday'), errors='coerce')
        if not when and pd.notna(day):
            when = f"<div class='mut small'>{esc(day.strftime('%a %b %-d'))}</div>"
        rows.append([f"<span class='team-code' data-game-id='{esc(r['game_id'])}'>{esc(r['away'])} @ {esc(r['home'])}</span>{when}",
                     pick, price + (f"<div class='mut small'>{price_label}</div>" if price_label else ''),
                     favorite_spread_text(r.get('fixed_band_spread'), r['home'], r['away']), final, badge,
                     f"<span class='{tone}'>{units_text(units)}</span>" if math.isfinite(units) else '—'])
    return rows


def render_ats_games(latest):
    games = public_ats(latest)
    if games.empty:
        return ''
    parts = ["<h2 class='sec'>Game-by-game ATS results</h2>"]
    groups = list(games.groupby(['season', 'week'], sort=True))
    for i, ((season, week), group) in enumerate(reversed(groups)):
        stats = season_ats.summary(group)
        skips = f' · {stats["skips"]} skip{"s" if stats["skips"] != 1 else ""}' if stats['skips'] else ''
        label = (f'{int(season)} week {int(week)} · {stats["wins"]}–{stats["losses"]}–{stats["pushes"]}{skips}'
                 f"<span class='rt'>{units_text(stats['units']) if stats['bets'] else '—'}</span>")
        parts.append(folded(label, table(['Game', 'ATS pick', 'Odds', 'Model', 'Final', 'Result', 'Units'],
                                         game_rows(group), num_cols=(4, 6), table_class='games'), i == 0))
    parts.append("<p class='mut small'>Odds are ESPN closing prices unless marked: <b>pre-lock</b> means the price "
                 "was captured before the pick locked; <b>assumed</b> means no matching price was found, so −110 is used.</p>")
    return ''.join(parts)


def has_public_saved_picks(latest):
    if not latest:return False
    records=latest.get('ats_locks',{})
    if season_ats.regrade_enabled(latest):
        return bool(ats_locks.public_records(records,latest['manifest']['revision']))
    return bool(records)


def render_grades(ledger, latest, built):
    season = int(latest['manifest']['season']) if latest is not None else None
    parts = [head('ATS results', 'All 2026 season results. Estimated returns use ESPN spread prices '
                  'where matched and assumed −110 otherwise, with 1-unit stakes.', f'{season} season' if season else '')]
    if latest is None:
        parts.append("<p class='mut'>No picks locked yet.</p>")
    else:
        parts.append(record_tiles(public_ats(latest), f'{season} record'))
        parts.append(render_ats_games(latest))
    return html_document(''.join(parts), f'{SITE_NAME} results', 'grades.html', built)


def ats_comparison_tiles(frame, basis='2026 season', title='Model vs simple baselines'):
    """Compare ATS sides on identical selected, completed, non-pick'em games."""
    d = frame.loc[frame.fixed_band_ats_result.isin(['W', 'L', 'P'])
                  & np.isfinite(frame.spread_line) & frame.spread_line.ne(0)
                  & np.isfinite(frame.result) & np.isfinite(frame.fixed_band_spread)]
    priced = 'ats_price_basis' in d
    if priced:
        d = d.loc[d.ats_home_odds.notna() & d.ats_away_odds.notna()]
    tiles = []
    for label, prediction in [('Model ATS', d.fixed_band_spread),
                              ('Market favorite ATS', d.spread_line + np.sign(d.spread_line)),
                              ('Home side ATS', d.spread_line + 1)]:
        results, returns = fixed_bands.grade(d, prediction)
        if priced:
            side = fixed_bands.pick(prediction, d.spread_line)
            odds = np.where(side > 0, d.ats_home_odds, d.ats_away_odds)
            returns = np.where(results == 'W', [espn_spreads.profit(p) for p in odds],
                               np.where(results == 'L', -1., 0.))
        wins, losses, pushes = [int((results == x).sum()) for x in ['W', 'L', 'P']]
        if len(d):
            rate = f'{100 * wins / (wins + losses):.1f}%' if wins + losses else '—'
            se = float(returns.std(ddof=1) / math.sqrt(len(returns))) if len(returns) > 1 else math.nan
            tiles.append(stat(label, f'{wins}–{losses}–{pushes}',
                              f'{rate} covered · {units_text(returns.sum())} · ROI {roi_short(returns.mean())} · {roi_uncertainty(se)}',
                              'model' if label == 'Model ATS' else ''))
        else:
            tiles.append(stat(label, '—', 'No compared games yet'))
    lead = (f"<p class='sec-lead'>On the <b>{len(d)}</b> {esc(basis)} games where both sides had ESPN prices, so all three "
            "records cover exactly the same games. That is why the model’s record here differs from the season record above.</p>"
            if priced else f"<p class='sec-lead'>On the same <b>{len(d)}</b> {esc(basis)} games.</p>")
    return (f"<h2 class='sec'>{esc(title)}</h2>{lead}<div class='gr-summary'>" + ''.join(tiles) + "</div>"
            "<p class='mut small'>Same completed games with a model ATS selection and a market favorite: the model’s pick, "
            "always taking the market favorite, and always taking the home side. "
            "Model skips and market pick’em games are excluded from all three records. "
            "Both sides must have matched ESPN prices to enter this comparison. "
            "Cover rates exclude pushes; ROI includes pushes. Closing-price estimates remain estimates.</p>")


def nice_step(span, ticks=4):
    raw = max(span, 1e-9) / ticks
    mag = 10 ** math.floor(math.log10(raw))
    return next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)


def units_chart(frame):
    """Running season units; order by week, then kickoff or game date when available."""
    if frame is None or frame.empty:
        return ''
    g = frame[frame.fixed_band_ats_result.isin(['W', 'L', 'P']) & frame.fixed_band_ats_units.notna()].copy()
    if len(g) < 2:
        return ''
    g['_ko'] = pd.to_datetime(g.get('kickoff_utc'), utc=True, errors='coerce')
    day = pd.to_datetime(g.get('gameday', pd.Series(index=g.index, dtype=str)), utc=True, errors='coerce')
    g['_ko'] = g['_ko'].fillna(day)
    g = g.sort_values(['week', '_ko', 'game_id'], na_position='last')
    run = np.concatenate([[0.], np.cumsum(g.fixed_band_ats_units.astype(float).to_numpy())])
    tone = 'pos-tx' if run[-1] > 0 else 'neg-tx' if run[-1] < 0 else ''
    # The wide drawing scales down on phones until its labels are unreadable, so
    # phones get their own drawing at roughly 1:1 scale (CSS picks one).
    wide = _units_svg(g, run, 1000, 240, 40, 'wide', tips=True)
    narrow = _units_svg(g, run, 340, 190, 34, 'narrow', tips=False)
    return (f"<div class='chart'><div class='chart-head'><span class='t'>Running units · 2026 season</span>"
            f"<span class='v {tone}'>{units_text(run[-1])}</span></div>{wide}{narrow}</div>")


def _units_svg(g, run, W, H, L, cls, tips):
    R, T, B = 12, 12, 26
    step = nice_step(max(run.max(), 0) - min(run.min(), 0))
    lo, hi = math.floor(min(run.min(), 0) / step) * step, math.ceil(max(run.max(), 0) / step) * step
    hi = hi if hi > lo else lo + step
    x = lambda i: L + (W - L - R) * i / (len(run) - 1)
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)
    out = [f"<svg class='{cls}' viewBox='0 0 {W} {H}' role='img' aria-label='Running units after each graded pick, ending at {units_text(run[-1])}'>"]
    v = lo
    while v <= hi + 1e-9:
        out.append(f"<line class='{'zero' if abs(v) < 1e-9 else 'grid-ln'}' x1='{L}' x2='{W - R}' y1='{y(v):.1f}' y2='{y(v):.1f}'/>"
                   f"<text class='ax' x='{L - 8}' y='{y(v) + 4:.1f}' text-anchor='end'>{'0' if abs(v) < 1e-9 else f'{v:+g}'.replace('-', '−')}</text>")
        v += step
    pts = ' '.join(f'{x(i):.1f},{y(u):.1f}' for i, u in enumerate(run))
    out.append(f"<polygon class='area' points='{x(0):.1f},{y(0):.1f} {pts} {x(len(run) - 1):.1f},{y(0):.1f}'/>")
    out.append(f"<polyline class='ln' points='{pts}'/>")
    for i, r in enumerate(g.to_dict('records') if tips else [], start=1):
        pick = f"{r.get('fixed_band_ats_team', '')} {spread_text(num(r.get('spread_line')), r.get('fixed_band_ats_side') == 'home')}"
        tip = (f"Week {int(r['week'])} · {r['away']} @ {r['home']} · {pick} · {r['fixed_band_ats_result']} "
               f"{units_text(r['fixed_band_ats_units'])} · running {units_text(run[i])}")
        out.append(f"<g><circle class='hit' cx='{x(i):.1f}' cy='{y(run[i]):.1f}' r='11'><title>{esc(tip)}</title></circle>"
                   f"<circle class='pt' cx='{x(i):.1f}' cy='{y(run[i]):.1f}' r='4'/></g>")
    out.append(f"<text class='ax' x='{L}' y='{H - 6}'>Start</text>"
               f"<text class='ax' x='{W - R}' y='{H - 6}' text-anchor='end'>Pick {len(run) - 1}</text></svg>")
    return ''.join(out)


MIN_ROI_BETS = 5  # a week's ROI from fewer bets is noise, not a rate


def weekly_table(frame):
    rows = []
    for week, group in frame.groupby('week', sort=True):
        v = season_ats.summary(group)
        rows.append([f'Week {int(week)}', f'{v["wins"]}–{v["losses"]}–{v["pushes"]}', pct(v['cover_rate'], 1),
                     f"{v['quoted_bets']} / {v['assumed_prices']}", str(v['pending']), units_text(v['units']) if v['bets'] else '—',
                     (f"{roi_short(v['roi'])}<div class='mut small'>{roi_uncertainty(v['roi_se'])}</div>"
                      if v['bets'] >= MIN_ROI_BETS else f"—<div class='mut small'>{v['bets']} bet{'s' if v['bets'] != 1 else ''} so far</div>")])
    return ("<h2 class='sec'>By week</h2>" +
            table(['Week', 'ATS W–L–P', 'Cover rate', 'ESPN / assumed', 'Pending', 'Units', 'ROI'], rows,
                  num_cols=(1, 2, 3, 4, 5, 6), table_class='weekly'))


HOW_IT_WORKS = (
    ("Project the spread", "The model turns each team’s recent box-score profile into a projected point spread."),
    ("Compare with the market", "The pick is the side the projection favors against the market handicap. "
                                "A projection equal to the line takes the market favorite."),
    ("Lock before kickoff", "The latest forecast 60 minutes before kickoff is saved. The handicap and pick never change after that."),
    ("Grade at the matched price", "Each priced pick risks 1 unit. A win pays the selected side’s spread odds; a loss costs 1u, "
                      "a push returns the stake. Historical closes are labelled estimates; missing prices use a labelled −110 assumption in pooled returns."),
)


def render_calibration(latest, ledger, built):
    # Keep the existing URL working while replacing its old probability view.
    season = int(latest['manifest']['season']) if latest is not None else None
    parts = [head('ATS performance', 'How all 2026 season picks are doing against the spread, beside simple '
                  'baselines on the same games. Pooled returns use ESPN prices where matched and assumed −110 otherwise.',
                  f'{season} season' if season else '')]
    frame = public_ats(latest)
    if latest is None or frame.empty:
        parts.append("<p class='mut'>No ATS results yet.</p>")
    else:
        parts.append(record_line(frame, f'{season} record'))
        parts.append(units_chart(frame))
        parts.append(ats_comparison_tiles(frame))
        parts.append(weekly_table(frame))
    parts.append("<h2 class='sec' id='how'>How picks work</h2><p class='sec-lead'>Against-the-spread picks from the "
                 "model’s projected spread. Picks can change until they lock 60 minutes before kickoff. On Picks, tap a "
                 "game for spreads, quarterbacks and injury reports.</p><ol class='steps'>" +
                 ''.join(f"<li><b>{esc(t)}</b>{esc(d)}</li>" for t, d in HOW_IT_WORKS) + "</ol>")
    return html_document(''.join(parts), f'{SITE_NAME} performance', 'market-calibration.html', built)

def render_historical_calibration(latest, built, pack=None):
    pack = historical_calibration.build(latest) if pack is None else pack
    current = pack['current_season']
    body = head('Market & model calibration',
        'How the model’s spread picks did by line size, how well favorite win probabilities matched actual win rates, '
        'and moneyline ROI against the market favorite.',
        f'2023–{current} · completed weeks')
    body += historical_calibration.render_body(pack)
    return html_document(body, f'{SITE_NAME} historical calibration',
        'historical-calibration.html', built, scripts=historical_calibration.SCRIPT,
        extra_css=historical_calibration.CSS)


# ---------------------------------------------------------------- driver

def render_all(out_dir, data=DATA, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    built = now.astimezone(PT).strftime("%Y-%m-%d %H:%M %Z")
    latest = load_latest(Path(data) / "latest")
    if latest is not None:
        latest['ats_locks'] = ats_locks.display_records(data)
    ledger = load_ledger(data)
    if latest is not None:
        ledger = score_updates.overlay(ledger, latest['final_scores'])
        latest['pooled_ats'] = season_ats.build(latest, ledger)
        season_ats.align_calibration_2026(latest,latest['pooled_ats'])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    season_results = public_ats(latest)
    if len(season_results):
        fields = ['game_id', 'season', 'week', 'home', 'away', 'ats_status',
                  'gameday', 'kickoff_utc', 'fixed_band_spread',
                  'spread_line', 'home_score', 'away_score', 'result', 'fixed_band_ats_side', 'fixed_band_ats_team',
                  'fixed_band_ats_handicap', 'fixed_band_ats_result', 'fixed_band_ats_units',
                  'ats_price', 'ats_price_basis', 'ats_match_status', 'ats_book', 'ats_quote_utc', 'ats_quote_age_minutes',
                  'ats_quote_url', 'ats_evidence_sha256', 'ats_priced_stake', 'ats_cumulative_units',
                  'ats_home_odds', 'ats_away_odds']
        season_results.reindex(columns=fields).rename(columns={'fixed_band_spread': 'model_spread'}).to_csv(
            out / 'ats_2026_results.csv', index=False)
        season_results.drop(columns=['espn_quote'], errors='ignore').to_csv(Path(data) / 'latest' / 'ats_pricing_results.csv', index=False)
    else:
        (out / 'ats_2026_results.csv').unlink(missing_ok=True)
    if latest is not None and latest['ats_locks']:
        locked_rows = []
        # Owner decision 2026-11-16: the public locked-picks file lists the current
        # revision's own saved locks; earlier revisions' games show its replay.
        saved_rows = (ats_locks.public_records(latest['ats_locks'], latest['manifest']['revision']).values()
                      if season_ats.regrade_enabled(latest) else latest['ats_locks'].values())
        for row in saved_rows:
            margin,market=row['fixed_band_spread'],row['market_spread']
            pricing = season_results.loc[season_results.game_id.eq(row['game_id'])]
            pricing = pricing.iloc[0] if len(pricing) else {}
            if season_ats.regrade_enabled(latest) and int(row['season'])==2026 and len(pricing):
                margin,market=pricing.get('fixed_band_spread',margin),pricing.get('spread_line',market)
            side = ats_locks.select(margin, market, True)
            locked_rows.append(dict(game_id=row['game_id'], season=row['season'],
                home=row['home'], away=row['away'], kickoff_utc=row['kickoff_utc'],
                forecast_utc=row['generated_utc'], lock_at_utc=row['lock_at_utc'],
                model_spread=margin, market_spread=market,
                selected_side=side, selected_team=row[side] if side else '',
                handicap=(-market if side == 'home' else market) if side else None,
                **{name: pricing.get(name) for name in ('ats_price', 'ats_price_basis', 'ats_book', 'ats_quote_utc')}))
        if locked_rows:pd.DataFrame(locked_rows).to_csv(out / 'ats_locked_picks.csv', index=False)
        else:(out / 'ats_locked_picks.csv').unlink(missing_ok=True)
    else:
        (out / 'ats_locked_picks.csv').unlink(missing_ok=True)
    if latest is not None and 'fixed_band_ledger' in latest:
        # The replayed ledger, per-season summary and median-map rules are research: data/latest only.
        (Path(data) / 'latest' / 'fixed_band_ledger.csv').parent.mkdir(parents=True, exist_ok=True)
        latest['fixed_band_ledger'].to_csv(Path(data) / 'latest' / 'fixed_band_ledger.csv', index=False)
        fixed_bands.summary(latest['fixed_band_ledger']).to_csv(Path(data) / 'latest' / 'fixed_band_summary.csv', index=False)
        latest['board'].to_csv(Path(data) / 'latest' / 'fixed_band_board.csv', index=False)
        (Path(data) / 'latest' / 'fixed_band_rules.json').write_text(
            json.dumps(latest['fixed_band_rules'], indent=2, allow_nan=False))
    if latest is not None and len(latest['board']):
        public_rows = []
        for row in latest['board'].to_dict('records'):
            state = ats_card_state(latest, row, now)
            item = {k: state['display_row'].get(k) for k in ('game_id', 'season', 'week', 'home', 'away',
                    'gameday', 'gametime', 'away_score', 'home_score', 'result')}
            item.update(model_spread=state['model_spread'], spread_line=state['spread_line'],
                ats_status=state['status'],
                selected_side=state['selected_side'], selected_team=state['selected_team'],
                handicap=state['handicap'], ats_result=state['result'], ats_units=state['units'])
            item.update({name: state.get(name) for name in ('ats_price', 'ats_price_basis', 'ats_book', 'ats_quote_utc')})
            public_rows.append(item)
        pd.DataFrame(public_rows).to_csv(out / 'fixed_band_board.csv', index=False)
    else:
        (out / 'fixed_band_board.csv').unlink(missing_ok=True)
    calibration_pack = historical_calibration.build(latest)
    historical_calibration.export(calibration_pack).to_csv(out / 'historical_calibration.csv', index=False)
    pages = {"index.html": render_index(latest, ledger, built, now),
             "grades.html": render_grades(ledger, latest, built),
             "market-calibration.html": render_calibration(latest, ledger, built),
             "historical-calibration.html": render_historical_calibration(latest, built, calibration_pack)}
    # Retrying an unchanged publication must not reload a reader's tab merely
    # because its footer timestamp advanced.
    content = ''.join(pages.values()).replace(f"<span class='stamp'>{esc(built)}</span>", '')
    version = hashlib.sha256(content.encode('utf-8')).hexdigest()
    for name, html in pages.items():
        (out / name).write_text(html.replace('__NFL_SITE_VERSION__', version), encoding="utf-8")
    (out / 'site-state.json').write_text(json.dumps({'version': version}), encoding='utf-8')
    # Repository-only analyst report. Do not publish a second research surface.
    report_path = Path(data) / 'ledger_report.txt'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(published_report(Path(data)), encoding='utf-8')
    for retired in ('ledger_report.txt', 'model.html', 'board.html', 'fixed_band_ledger.csv',
                    'fixed_band_summary.csv', 'fixed_band_rules.json'):
        (out / retired).unlink(missing_ok=True)
    # Root CSVs are generated public exports. Reused/pages-only output must not
    # retain an old private-probability download; unrelated assets stay intact.
    for obsolete in out.glob('*.csv'):
        if obsolete.name not in PUBLIC_CSV_EXPORTS:
            obsolete.unlink()
    (out / ".nojekyll").write_text("")
    return sorted(p.name for p in out.iterdir())


APPENDICES = (("regraded_ledger_report.md", "Appendix B: original snapshots replayed with the current model"),)
RESEARCH_MARKER = '\n\n' + '=' * 78 + '\nRepository analysis appendices\n' + '=' * 78 + '\n'


def published_report(data):
    """Consolidate research in the repo report, idempotently across page-only builds."""
    path = data / "ledger_report.txt"
    base = path.read_text().split(RESEARCH_MARKER, 1)[0] if path.exists() else "No ledger yet.\n"
    parts = [base, RESEARCH_MARKER]
    for name, title in APPENDICES:
        source = data / "latest" / name
        if source.exists():
            parts.append(f"\n\n{'=' * 78}\n{title} (from data/latest/{name})\n{'=' * 78}\n\n{source.read_text()}")
    parts.append('\n\nAppendix C: current production sanity checks\n\n' + production_sanity.report(data))
    parts.append('\n\nATS 60-minute capture policy\n\n' + ats_locks.report(data))
    latest = load_latest(data / 'latest')
    if latest is not None:
        latest['ats_locks'] = ats_locks.display_records(data)
        pool = season_ats.build(latest, load_ledger(data))
        parts.append('\n\n2026 pooled ATS results\n\n' + season_ats.report(pool))
        parts.append('\n\nATS same-row baselines\n\n' + season_ats.lock_baselines(latest, pool))
    return "".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages-only", action="store_true", help="render from committed data/ without running the model")
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "public"))
    args = ap.parse_args(argv)
    if args.pages_only and m.REVISION in ats_locks.REGRADE_REVISIONS:
        manifest=DATA/'latest'/'manifest.json'
        saved=json.loads(manifest.read_text()) if manifest.exists() else {}
        version=m.REVISION.rsplit('-',1)[-1]
        if saved.get('revision')!=m.REVISION:
            raise ValueError(f'{version} pages require a fresh {version} model snapshot; keep the last published site')
        if m.REVISION==season_ats.REPLACEMENT_REVISION and not (DATA/'latest'/'replacement_adjustments.csv').exists():
            raise ValueError(f'{version} pages require replacement classifications; keep the last published site')
    # A held job may pick up a repair while already running. Pages-only
    # finalization must apply the same explicit requests as a fresh workflow.
    import retro_lock
    print(f'Owner-requested ATS retro locks: {retro_lock.apply(DATA)}')
    if not args.pages_only:
        # Retain the previous rolling board before a model run can replace it.
        forecast_history.record(DATA, load_latest(DATA / 'latest'))
        # Finalize persisted inputs before the expensive model refresh. Even a
        # later model failure must not strand an eligible pre-cutoff candidate.
        if os.environ.get('NFL_LOCK_OWNER') != 'watcher':
            print(f"ATS saved capture: {ats_locks.record(DATA)}")
        espn_spreads.safe_refresh(DATA)
        outdir = run_model()
        season, week = snapshot(outdir)
        print(f"Pregame forecast refreshes saved: {forecast_history.record(DATA, load_latest(DATA / 'latest'))}")
        print(f"snapshot: {season} week {week} -> {LATEST}")
        espn_spreads.safe_refresh(DATA)
        if os.environ.get('NFL_LOCK_OWNER') != 'watcher':
            print(f"ATS timed capture: {ats_locks.record(DATA)}")
        else:
            # The watcher owns candidates and locks; the build only refreshes the
            # read-only status so it never describes an older board.
            try:
                ats_locks.write_capture_status(DATA)
            except Exception as exc:
                print(f'::warning::ATS capture status not refreshed: {exc}')
        grade_ledger.main([])
    files = render_all(args.out)
    if not args.pages_only:
        # Captures happen after rendering; include this build's new archive rows.
        (DATA / 'ledger_report.txt').write_text(published_report(DATA), encoding='utf-8')
    print(f"site: {len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
