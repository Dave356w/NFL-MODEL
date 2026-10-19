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
  grades.html              pooled season results game by game, with downloads
  market-calibration.html  ATS performance: running units, same-game baselines, by week (legacy URL)

Data written (committed by build.yml through commit_data.py)
  data/forward_predictions.jsonl   append-only ledger (written by nfl_model.record_forward)
  data/frozen_recipe_<season>_<REVISION>.json frozen hyperparameters (nfl_model.frozen_recipe)
  data/kalshi_snapshots.jsonl      append-only Kalshi quotes captured for newly locked games (kalshi.py)
  data/h4_terms.jsonl              append-only pass-matchup terms for newly locked games (matchup.py, H4)
  data/h5_totals.jsonl             append-only totals and moneylines for newly locked games (totals.py, H5)
  data/forward_ledger.csv, data/ledger_report.txt   graded view (grade_ledger.py)
  data/latest/                     the newest run's page inputs, so --pages-only needs no model run
  data/projections/<season>_week<NN>.csv   the latest board of each week, overwritten through the week

A model failure exits non-zero before any page is written, so the workflow
never uploads an artifact and the last good site stays live.
"""

import argparse
import base64
import datetime as dt
import json
import math
import os
import shutil
import sys
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import grade_ledger
import kalshi
import matchup
import nfl_model as m
import totals
import fixed_bands
import ats_locks
import season_ats
from research import version_report
from research import ats_forward_shadow
from research import production_sanity

DATA = Path("data")
LATEST = DATA / "latest"
PROJECTIONS = DATA / "projections"
ASSETS = Path("assets/fonts")
PT = ZoneInfo("America/Los_Angeles")
SITE_NAME = "NFL ATS"
PUBLIC_CSV_EXPORTS = {'ats_2026_results.csv', 'ats_locked_picks.csv', 'fixed_band_board.csv'}

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
    "version_historical.csv": "version_historical.csv",
    "version_archived.csv": "version_archived.csv",
    "version_native.csv": "version_native.csv",
    "market_target_fit_audit.csv": "market_target_fit_audit.csv",
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
    compact = board[[c for c in BOARD_COLS if c in board.columns] + avail]
    compact.to_csv(latest / "board.csv", index=False, float_format="%.6g")
    Path(projections).mkdir(parents=True, exist_ok=True)
    for prior in outdir.glob("week*_board.csv"):
        full = pd.read_csv(prior)
        if full.empty:
            continue
        prior_week = int(prior.stem.removeprefix("week").removesuffix("_board"))
        fields = [c for c in BOARD_COLS if c in full] + [c for c in full if c.startswith(("home__avail__", "away__avail__"))]
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
    out["board_html"] = (latest / "board.html").exists()
    fixed_bands.prepare(out)
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
.brand-version{font:600 11px/1 var(--mono);color:var(--muted);border:1px solid var(--line);padding:4px 6px;border-radius:6px}
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
.pick-lines .edge{font:600 12.5px/1.3 var(--sans);color:var(--muted)}
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
/* steps */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:0 0 12px;padding:0;list-style:none;counter-reset:s}
.steps li{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;box-shadow:var(--shadow);
  font-size:14px;line-height:1.55;color:var(--muted);counter-increment:s}
.steps li b{display:block;color:var(--ink);font-size:15px;margin-bottom:4px}
.steps li::before{content:counter(s);display:grid;place-items:center;width:26px;height:26px;border-radius:50%;
  background:rgba(var(--accent),.12);color:rgb(var(--accent-tx));font:800 13px/1 var(--mono);margin-bottom:10px}
.downloads{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 12px}
.downloads a{display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border:1px solid var(--line);border-radius:9px;
  background:var(--surface);color:var(--ink);text-decoration:none;font:600 13px/1 var(--sans)}
.downloads a:hover{border-color:rgb(var(--accent))}
.downloads a::before{content:"↓";color:rgb(var(--accent-tx));font-weight:800}
.empty{background:var(--surface);border:1px dashed var(--line);border-radius:var(--r);padding:22px;color:var(--muted);text-align:center}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px 18px;margin-top:44px;padding-top:16px;
  border-top:1px solid var(--line);color:var(--faint);font-size:12.5px;line-height:1.6}
.foot a{color:var(--muted)}
@media (max-width:720px){
  .topbar{flex-wrap:wrap;gap:12px;padding:14px 0;margin-bottom:16px}
  .nav{order:3;width:100%;margin-left:0}.nav a{flex:1;text-align:center;padding:9px 6px}
  .theme{margin-left:auto}.brand-version{display:none}
  .gr-h1{font-size:28px}
  .gr-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
  .gr-stat{padding:13px 13px}.gr-stat .v{font-size:22px}
  .grid{grid-template-columns:minmax(0,1fr)}
  table.gr{font-size:13px}table.gr th,table.gr td{padding:9px 10px;white-space:nowrap}
  .detail table.gr td{white-space:normal}
  .fold .rt{margin-left:0;width:100%}
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
document.querySelectorAll('.card[data-state]').forEach(function(c){c.hidden=f!=='all'&&c.getAttribute('data-state')!==f;});});})();</script>"""

THEME_ICON = ("<svg class='sun' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' aria-hidden='true'>"
              "<circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></svg>"
              "<svg class='moon' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' aria-hidden='true'>"
              "<path d='M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z'/></svg>")

PAGES = (("index.html", "Picks"), ("grades.html", "Results"),
         ("market-calibration.html", "Performance"))


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


def html_document(body, title, current, built, scripts=""):
    nav = "".join(f"<a href='{href}'{' aria-current=\"page\"' if href == current else ''}>{label}</a>"
                  for href, label in PAGES)
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><meta name='description' content='NFL ATS picks, locked handicaps and season results'>"
            "<meta name='color-scheme' content='light dark'>"
            f"{THEME_JS}<style>{font_face_css()}{CSS}</style></head><body><a class='skip-link' href='#main-content'>Skip to content</a><div class='mx-wrap'>"
            f"<header class='topbar'><a class='brand' href='index.html'><span class='brand-mark' aria-hidden='true'>NF</span>{SITE_NAME}"
            f"<span class='brand-version'>{esc(m.REVISION.rsplit('-', 1)[-1])}</span></a>"
            f"<nav class='nav' aria-label='Main navigation'>{nav}</nav>"
            f"<button class='theme' type='button' onclick='toggleTheme()' aria-label='Toggle colour theme' title='Toggle theme'>{THEME_ICON}</button></header>"
            f"<main id='main-content'>{body}</main>"
            f"<footer class='foot'><span>Updated <span class='stamp'>{esc(built)}</span></span>"
            "<span>Flat 1-unit stakes at −110. For information only; past results do not guarantee future results.</span>"
            f"</footer></div>{scripts}</body></html>")


def head(title, lead, eyebrow="", aside=""):
    top = f"<div class='eyebrow'>{esc(eyebrow)}</div>" if eyebrow else ""
    return (f"<div class='gr-head'><div>{top}<h1 class='gr-h1'>{esc(title)}</h1>"
            f"<div class='gr-lead'>{lead}</div></div>{aside}</div>")


def stat(label, value, sub="", tone=""):
    return (f"<div class='gr-stat'><div class='l'>{esc(label)}</div>"
            f"<div class='v{(' ' + tone) if tone else ''}'>{value}</div>"
            f"{f'<div class=s>{sub}</div>' if sub else ''}</div>")


def table(heads, rows, num_cols=()):
    th = "".join(f"<th{' class=n' if i in num_cols else ''}>{h}</th>" for i, h in enumerate(heads))
    body = []
    for r in rows:
        cls = r.pop("_class", "") if isinstance(r, dict) else ""
        cells = r["cells"] if isinstance(r, dict) else r
        tds = "".join(f"<td{' class=n' if i in num_cols else ''}>{c}</td>" for i, c in enumerate(cells))
        body.append(f"<tr{f' class={cls}' if cls else ''}>{tds}</tr>")
    return f"<div class='gr-tablewrap'><table class='gr'><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


# ---------------------------------------------------------------- shared pieces
# Public pages carry W-L, win % and ROI only. Standard errors, no-vig q, excess,
# log loss and recipe details stay in data/ledger_report.txt and data/latest/.

def kickoff_text(r):
    ko = m.kickoff_utc(r)
    return ko.astimezone(PT).strftime("%a %-I:%M %p %Z") if ko else "TBD"


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


def wl_text(r):
    return f"{int(r['wins'])}-{int(r['losses'])}" + (f"-{int(r['pushes'])}" if r.get("pushes") else "")


def roi_short(roi):
    return "—" if not math.isfinite(num(roi)) else f"{100 * roi:+.1f}%".replace("-", "−")


def control_records(df):
    """Flat 1u records for the model, always-the-favorite and always-home on the same graded, priced rows."""
    if df is None or df.empty or "home won" not in df:
        return None
    d = df[pd.to_numeric(df["home won"], errors="coerce").isin([0., .5, 1.])].copy()
    if d.empty:
        return None
    d["_fav"] = m.market_ml_wp(d)
    d["_home"] = .99
    bets = {k: m.flat_bets(d, c) for k, c in (("model", "model_wp"), ("favorite", "_fav"), ("home", "_home"))}
    keep = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    if not keep.any():
        return None
    return {k: m.roi_summary(b[keep]) for k, b in bets.items()}


def disagreement_note(df, where):
    """The games that separate the model from always betting the favorite (v1.14.2):
    on every other game the two make the same bet."""
    if df is None or df.empty or "home won" not in df:
        return ""
    d = df[pd.to_numeric(df["home won"], errors="coerce").isin([0., .5, 1.])]
    t = m.disagreement_table(d, by="season") if len(d) else None
    if t is None or t.empty:
        return ""
    t = t[t.group == "All games"].set_index("source")
    r, f = t.loc["model"], t.loc["market favorite"]
    if not r.bets:
        return (f"<p class='mut small'>{where}: the model has not yet picked against the market favorite, "
                "so its record equals always betting the favorite.</p>")
    units = lambda u: f"{u:+.1f}u".replace("-", "−")
    return (f"<p class='mut small'>{where}: the model picked against the market favorite in {int(r.bets)} game{'s' if r.bets != 1 else ''}, "
            f"the only games where its bets differ from always betting the favorite. There it went "
            f"{int(r.wins)}-{int(r.losses)}, {units(r.units)} (ROI {roi_short(r.roi)}), against "
            f"{units(f.units)} for the favorite: a difference of {units(r.units - f.units)}.</p>")


def control_tiles(ctrl, first_label, first_value, first_sub):
    """Four same-shape tiles: a count, then the model and two do-nothing controls."""
    tiles = [stat(first_label, first_value, first_sub)]
    for key, label in (("model", "Model"), ("favorite", "Always favorite"), ("home", "Always home")):
        r = (ctrl or {}).get(key)
        if r and r["bets"]:
            tiles.append(stat(label, wl_text(r), f"{100 * r['win_pct']:.1f}% · ROI {roi_short(r['roi'])}",
                              "model" if key == "model" else ""))
        else:
            tiles.append(stat(label, "—", "no graded picks yet"))
    return f"<div class='gr-summary'>{''.join(tiles)}</div>"


def spread_record(latest, season=None):
    d = (latest or {}).get('fixed_band_ledger', pd.DataFrame())
    if d.empty:
        return None
    s = fixed_bands.summary(d)
    r = s[(s.method == 'Fixed bands') & (s.season == ('All' if season is None else str(season)))]
    return r.iloc[0] if len(r) and r.iloc[0].games else None


def spread_record_text(r):
    return (f"ATS {int(r.wins)}–{int(r.losses)}–{int(r.pushes)} · {int(r.skips)} skips · "
            f"{r.units:+.2f}u · ROI {roi_short(r.roi)}")


def spread_headline(latest, season=None):
    pooled = (latest or {}).get('pooled_ats', pd.DataFrame())
    if season == 2026 and len(pooled):
        record = season_ats.summary(pooled)
        if record['opportunities']:
            r = pd.Series(record)
            basis = pooled_basis_text(pooled)
            return (f"<div class='record'><div class='l'>Spread results · 2026</div>"
                    f"<div class='mono'>{spread_record_text(r)}<div class='mut small'>"
                    f"Season total · {esc(basis)} · −110 pricing · 1-unit stakes</div></div></div>")
    r = spread_record(latest, season)
    label = f'Spread results · {season}' if season is not None else 'Spread results · historical replay'
    text = spread_record_text(r) if r is not None else 'No eligible graded spread results yet.'
    basis = 'Historical replay'
    data=(latest or {}).get('fixed_band_ledger',pd.DataFrame())
    if len(data) and season is not None:
        covered=data[(data.season==season)&data.fixed_band_spread.notna()&data.result.notna()&data.spread_line.notna()]
        if len(covered):basis+=f' · through week {int(covered.week.max())}'
    if r is not None:
        basis += f' · {int(r.selected)} selections from {int(r.opportunities)} games'
    return (f"<div class='record'><div class='l'>{esc(label)}</div><div class='mono'>{text}"
            f"<div class='mut small'>{basis} · −110 pricing · 1-unit stakes</div>"
            "</div></div>")


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


def factor_label(name):
    """Plain name for a model input on the public card."""
    if name == "market_log_odds":
        return "Market starting point"
    if name == "pass_product":
        return "Passing matchup balance"
    if name.startswith("pass_1sd_"):
        return PASS_CONTEXT_LABELS.get(name[-2:], "Passing matchup pattern")
    if name == "site":
        return "Home field"
    if name == m.MARGIN_FEATURE:
        return "Point margin"
    if name in m.PEAK_FEATURES:
        return "Largest lead" if name == "d__max_lead" else "Largest deficit"
    if name.startswith("d__avail__"):
        c = name[len("d__avail__"):]
        return "Quarterback" if c == "qb_delta" else f"{UNIT_NAMES.get(c.split('_')[0], c)} availability"
    pieces = name.split("__", 3)
    if len(pieces) == 4 and pieces[-1] in FACTOR_METRICS:
        offense, defense, _ = FACTOR_METRICS[pieces[-1]]
        return offense if pieces[1] == "for" else defense
    try:
        return m.feature_label(name)
    except (ValueError, KeyError):
        return "Other team profile"


def factor_description(name, raw_input, away, home):
    """Short, game-specific labels; strength describes inputs, not guaranteed effects."""
    label, note = factor_label(name), ""
    if name.startswith("pass_1sd_"):
        if math.isfinite(num(raw_input)) and abs(num(raw_input)) > 1e-12:
            attack, defense = (home, away) if num(raw_input) > 0 else (away, home)
            note = label
            label = f"{attack} passing vs {defense} defense"
        else:
            note = "Historical passing matchup pattern"
    elif name in m.PASS_TOTAL_NAMES:
        note = {"margin_edge":"Expected margin relative to the spread", "total_homefield":"Home-field effect at the expected combined score", "pass_total_interaction":"Passing matchup effect at the expected combined score"}[name]
    elif name == "pass_product":
        note = "Each passing attack matched with the opposing pass defense"
    elif name == "market_log_odds":
        note = "Starting probability from the moneyline prices"
    elif name == "site":
        note = "Home-field term in the fitted model"
    elif name == m.MARGIN_FEATURE:
        note = "Recent scoring margins"
    elif name in m.PEAK_FEATURES:
        note = "How far teams led or trailed during recent games"
    elif name.startswith("d__avail__"):
        note = ("Expected starter compared with recent quarterback play" if name.endswith("qb_delta")
                else "Expected absences among recent contributors")
    else:
        pieces = name.split("__", 3)
        if len(pieces) == 4 and pieces[-1] in FACTOR_METRICS:
            note = FACTOR_METRICS[pieces[-1]][2]
            if pieces[1] == "allowed":
                note = "Opponents’ " + note[0].lower() + note[1:]
    return label, note


def factor_cells(c, away, home, cmax):
    v = num(c.get("log-odds contribution"))
    if not math.isfinite(v):
        return None
    label, note = factor_description(c["feature"], c.get("home-minus-away input"), away, home)
    tone = "pos" if v > 0 else "neg" if v < 0 else ""
    toward = f"Toward {home if v > 0 else away}" if v else "Neutral"
    w = min(50., 50 * abs(v) / max(cmax, 1e-9))
    style = f"left:50%;width:{w:.1f}%" if v >= 0 else f"right:50%;width:{w:.1f}%"
    return [f"<div class='factor-name'>{esc(label)}</div><div class='factor-note'>{esc(note)}</div>",
            f"<div class='factor-impact'><div class='factor-toward {tone}'>{esc(toward)}</div>"
            f"<div class='cbar' role='img' aria-label='{esc(toward)}'><i class='{tone}' style='{style}'></i></div></div>"]


def result_badge(res):
    if res not in ("W", "L", "P"):
        return "—"
    return f"<span class='badge {'w' if res == 'W' else 'l' if res == 'L' else ''}'>{res}</span>"


def pick_text(team, price):
    return f"{esc(team)} {ml_text(price)}" if isinstance(team, str) and team else "—"


def score_text(away, home):
    a, h = num(away), num(home)
    return f"{int(a)}–{int(h)}" if math.isfinite(a) and math.isfinite(h) else ""


def folded(summary, inner, open_=False):
    return (f"<details class='fold'{' open' if open_ else ''}><summary>{summary}</summary>{inner}</details>")


def margin_text(margin, spread):
    """Average realized margin of a pick, beside the average market spread for it."""
    mg, sp = num(margin), num(spread)
    if not math.isfinite(mg):
        return "—"
    tone = "up" if math.isfinite(sp) and mg > sp else "dn" if math.isfinite(sp) else ""
    out = f"<span class='{tone}'>{mg:+.1f}</span>".replace("-", "−")
    return out + (f" vs {sp:+.1f}".replace("-", "−") if math.isfinite(sp) else "")


def records_table(recs):
    """When the model said X%, how often its pick won, and by how much on average."""
    rows = []
    margins = "avg pick margin" in recs
    for _, r in recs[recs.source == "model"].sort_values("band_index").iterrows():
        if not r.games:
            continue
        cells = [esc(r.band), f"<b>{esc(r.record)}</b>", f"{r['realized pick win %']:.1f}%", f"{r['avg pick prob %']:.1f}%"]
        if margins:
            cells.append(margin_text(r["avg pick margin"], r.get("avg pick spread")))
        rows.append({"cells": cells, "_class": "total" if r.band == "All picks" else ""})
    heads = ["Model said", "Picks", "Won", "Average forecast"] + (["Avg margin"] if margins else [])
    return table(heads, rows, num_cols=tuple(range(1, len(heads))))


def market_band_stats(retro):
    """Per moneyline band: sides, realized win rate and mean no-vig implied probability."""
    s = market_sides(retro)
    return {b: (len(g), float(g.won.mean()), float(g.q.mean())) for b, g in s.groupby("band")}


def heldout_seasons(latest):
    """Seasons scored out of sample (each season's recipe chosen on earlier seasons only)."""
    t = latest.get("roi_by_season") if latest else None
    if t is None or t.empty or "group" not in t:
        return []
    return sorted(int(float(g)) for g in t.group.unique() if str(g).replace(".", "").isdigit())


def band_windows(latest, forward):
    """Market and model records per moneyline band on the SAME games: the held-out seasons
    plus graded forward picks of the current revision. Returns (market, model, seasons, n_forward)."""
    years = heldout_seasons(latest)
    retro = latest.get("retro_ledger") if latest else None
    cols = ["season", "home won", "home_moneyline", "away_moneyline", "model_wp"]
    base = retro[retro.season.isin(years)][cols] if retro is not None and len(retro) and years else pd.DataFrame(columns=cols)
    fwd = forward[cols] if forward is not None and len(forward) else pd.DataFrame(columns=cols)
    mkt = market_band_stats(pd.concat([base, fwd], ignore_index=True)) if len(base) + len(fwd) else {}
    mdl = {}
    t = latest.get("roi_bands") if latest else None
    if t is not None and len(t) and "source" in t:
        for r in t[(t.source == "model") & (t.group != "All games")].itertuples(index=False):
            if r.bets:
                mdl[str(r.group)] = {"wins": int(r.wins), "losses": int(r.losses), "bets": int(r.bets),
                                     "qsum": float(r.mean_q) * int(r.bets)}
    if len(fwd):
        fb = m.flat_bets(fwd.assign(**{"home won": pd.to_numeric(fwd["home won"], errors="coerce")}), "model_wp")
        for band, g in fb[fb.units.notna()].groupby("band"):
            d = mdl.setdefault(band, {"wins": 0, "losses": 0, "bets": 0, "qsum": 0.})
            d["wins"] += int((g.result == "W").sum()); d["losses"] += int((g.result == "L").sum())
            d["bets"] += len(g); d["qsum"] += float(g.q.sum())
    return mkt, mdl, years, len(fwd)


SMALL_SAMPLE = 30  # fewer games than this at a price: flag the rate as a small sample


def price_band_html(team, price, q_pick, mkt, mdl, years, n_forward):
    """How sides at the pick's moneyline have done for the market and the model, on the same games."""
    band = m.ml_band(price)
    k, md = mkt.get(band), mdl.get(band)
    dec = (md["wins"] + md["losses"]) if md else 0
    small = lambda n: " · small sample" if n < SMALL_SAMPLE else ""
    tiles = [stat("This game", pct(q_pick, 1), f"market's chance for {esc(team)} {ml_text(price)}"),
             stat("All teams at this price", f"won {pct(k[1], 1)}" if k else "—",
                  f"vs {pct(k[2], 1)} implied · {k[0]} teams{small(k[0])}" if k else "no games at this price yet"),
             stat("Model picks at this price", f"won {pct(md['wins'] / dec, 1)}" if dec else "—",
                  f"vs {pct(md['qsum'] / md['bets'], 1)} implied · {md['bets']} picks{small(md['bets'])}"
                  if md else "no picks at this price yet"),
             stat("Model record", f"{md['wins']}-{md['losses']}" if md else "—", "at this price")]
    span = f"{years[0]}–{years[-1]}" if len(years) > 1 else f"{years[0]}" if years else "past seasons"
    fwd = f" plus {n_forward} locked pick{'s' if n_forward != 1 else ''} this season" if n_forward else ""
    return (f"<h3>At this price · {esc(team)} {ml_text(price)} is in the {esc(band)} range</h3>"
            f"<div class='gr-summary band'>{''.join(tiles)}</div>"
            f"<p class='mut small'>Implied is the market's chance with the bookmaker's margin removed. "
            f"Same games for both: {span}, each game reconstructed using earlier weeks; the current formula was chosen after historical review{fwd}.</p>")


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
    saved = latest.get('ats_locks', {}).get((rev, row['game_id']))
    completed = None
    display_row = dict(row)
    pool = public_ats(latest)
    if len(pool):
        matches = pool.loc[pool.game_id.eq(row['game_id'])]
        if len(matches) > 1:
            raise ValueError('Duplicate public ATS game')
        if len(matches):
            candidate = matches.iloc[0]
            if candidate.ats_status == 'graded' and math.isfinite(num(candidate.get('result'))):
                display_row.update({name: candidate.get(name) for name in ('result', 'home_score', 'away_score')})
                if (saved is None and candidate.ats_basis in {'Historical replay', 'Replayed pregame forecast'}
                        and candidate.fixed_band_ats_result in {'W', 'L', 'P', 'S'}
                        and math.isfinite(num(candidate.fixed_band_spread))
                        and math.isfinite(num(candidate.spread_line))):
                    completed = candidate
    ko = m.kickoff_utc(row)
    cutoff = ats_locks.deadline(ko) if ko is not None else None
    source, status, note = 'Provisional', 'provisional', ''
    if saved is not None:
        ms, line = num(saved['fixed_band_spread']), num(saved['market_spread'])
        status = 'locked'
        source = 'Earlier recorded pick' if saved.get('legacy_lock') else '60-minute lock'
        when = ats_locks.utc(saved['lock_at_utc']).astimezone(PT).strftime('%a %-I:%M %p %Z')
        note = f'ATS locked {when}'
    elif completed is not None:
        # The season pool already owns this completed selection. Never use a
        # refreshed postgame line/probability to recreate the public result.
        ms, line = num(completed.fixed_band_spread), num(completed.spread_line)
        status, source, note = 'graded', completed.ats_basis, 'Final ATS result'
    elif cutoff is not None and now >= cutoff:
        status, source, note = 'unavailable', 'No saved ATS selection', 'ATS lock unavailable'
    elif cutoff is not None:
        when = cutoff.astimezone(PT).strftime('%a %-I:%M %p %Z')
        note = f'ATS provisional · locks {when}'
    else:
        note = 'ATS provisional · kickoff unconfirmed'
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
    chosen = fixed_bands.pick(ms, line) if math.isfinite(ms-line) else 0.
    side = '' if status == 'unavailable' or chosen == 0 else ('home' if chosen > 0 else 'away')
    return dict(model_spread=ms, spread_line=line, pick=pick, gap=gap, status=status,
                source=source, note=note, saved=saved, result=grade, units=units,
                display_row=display_row,
                selected_side=side, selected_team=row[side] if side else '',
                handicap=(-line if side == 'home' else line) if side else math.nan)


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
    updated = (f"<div class='record'><div class='l'>Forecast updated</div><div class='mono'>"
               f"{esc(local.strftime('%a %b %-d · %-I:%M %p %Z'))}</div></div>" if local is not None else '')
    parts = [head(f'Week {week} picks',
                  'Against-the-spread picks from the model’s projected spread. Each pick locks 60 minutes '
                  'before kickoff. Open a game for spreads, quarterbacks and injury reports.',
                  f'{season} regular season', updated)]
    parts.append(record_tiles(public_ats(latest), f'{season} record'))

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
    parts.append(f"<div class='toolbar'><h2 class='sec'>This week’s games</h2>"
                 f"<div class='seg' data-filter role='group' aria-label='Filter games' hidden>{seg}</div></div>")
    cards = []
    for row in rows:
        home, away = row['home'], row['away']
        state = states[row['game_id']]
        ms, line = state['model_spread'], state['spread_line']
        final = pd.notna(row.get('result'))
        if final:
            status = f"<span class='badge'>Final {score_text(row.get('away_score'), row.get('home_score'))}</span>"
        elif state['status'] == 'locked':
            status = "<span class='badge lock'>Locked</span>"
        elif state['status'] == 'unavailable':
            status = "<span class='badge'>No pick</span>"
        else:
            status = "<span class='badge live'>Not locked</span>"
        flags = []
        if state['result']:
            result = 'Skip' if state['result'] == 'S' else state['result']
            tone = 'w' if state['result'] == 'W' else 'l' if state['result'] == 'L' else ''
            units = f" · <span class='u'>{units_text(state['units'])}</span>" if math.isfinite(state['units']) else ''
            flags.append(f"<span class='badge {tone}'>ATS result · {esc(result)}{units}</span>")
        if pending(row):
            flags.append("<span class='badge warn'>Report pending</span>")
        if not bool(row.get('ready', True)):
            flags.append("<span class='badge'>Limited history</span>")
        for side in ('away', 'home'):
            expected, usual = row.get(f'{side}_qb_expected'), row.get(f'{side}_qb_usual')
            if isinstance(expected, str) and isinstance(usual, str) and expected != usual:
                flags.append(f"<span class='badge warn'>{esc(row[side])} QB: {esc(expected)}</span>")
        edge = (f"<span class='edge'>{state['gap']:g}-point difference from market</span>"
                if math.isfinite(state['gap']) and state['gap'] > fixed_bands.EPS else '')
        pick = (f"<div class='pick-lines'><span class='kind'>ATS pick</span>"
                f"<span class='pk{'' if state['selected_side'] else ' na'}'>{state['pick']}</span>{edge}</div>")
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

        summary = (f"<summary class='game-summary'><div class='g-meta'><span class='when'>{esc(kickoff_text(row))}</span>{status}</div>"
                   f"<div class='g-teams'>{team(away, 'away')}{team(home, 'home')}</div>{pick}"
                   f"<div class='mk sp'>{spreads}</div>"
                   f"{f'<div class=flags>{chr(32).join(flags)}</div>' if flags else ''}"
                   f"<div class='g-note'>{esc(state['note'])}</div></summary>")
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
        if has_avail:
            detail.append(f"<h3>Quarterbacks</h3><p class='mut'>{esc(away)} {_qb(row, 'away')} · {esc(home)} {_qb(row, 'home')}</p>")
            detail.append(report_notes_html(latest.get('report_notes'), (away, home), int(row['week'])))
        detail.append('</div>')
        tone = ' picked-card' if state['selected_side'] else ''
        cards.append(f"<details class='card{tone}' data-state='{'final' if final else 'upcoming'}'>"
                     f"{summary}{''.join(detail)}</details>")
    parts.append(f"<div class='grid'>{''.join(cards)}</div>")
    links = "<a href='ats_locked_picks.csv'>Saved spread picks</a>" if latest.get('ats_locks') else ''
    parts.append(f"<p class='mut small'>Model and market spreads are shown from the favorite’s side; the highlighted team "
                 f"is the pick. Saved handicaps and selections stay fixed after lock. {links}</p>"
                 "<p><a href='grades.html'>View ATS results →</a></p>")
    return html_document(''.join(parts), f'{SITE_NAME} — week {week}', 'index.html', built, FILTER_JS)

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
        rows = []
        for x in n.itertuples(index=False):
            rows.append([f"{esc(x.player)} <span class='mut'>{esc(x.position)}</span>", esc(x.this_week)])
        out.append(f"<p class='mut'><b>{esc(t)}</b> · {esc(STATE_TEXT.get(n.report_state.iloc[0], '').format(w=week))}</p>"
                   + table(["Player", f"Week {week} status"], rows))
    return "".join(out) if len(out) > 1 else ""


def _qb(r, side):
    e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
    if not isinstance(e, str):
        return "—"
    return esc(e) + (f" (usual {esc(u)})" if isinstance(u, str) and u != e else "")


def pooled_2026_v118_rows(latest, ledger):
    """One 2026 row per game: native v1.18 lock wins over any historical replay."""
    if latest is None:
        return None
    man = latest.get("manifest", {})
    if man.get("revision") != "boxscore-composite-v1.18" or int(man.get("season", 0)) != 2026:
        return None

    replay = latest.get("retro_ledger", pd.DataFrame())
    required = {"game_id", "season", "week", "basis", "bet_result", "units"}
    if replay is None or not required.issubset(replay.columns):
        replay = pd.DataFrame(columns=list(required))
    replay = replay.loc[(pd.to_numeric(replay["season"], errors="coerce") == 2026)
                        & replay["basis"].eq("current season walk-forward")].copy()
    replay = replay.dropna(subset=["game_id"]).drop_duplicates("game_id", keep="last")

    native = ledger.loc[(ledger["revision"].eq("boxscore-composite-v1.18"))
                        & (pd.to_numeric(ledger["season"], errors="coerce") == 2026)].copy()
    native = native.dropna(subset=["game_id"]).drop_duplicates("game_id", keep="first")
    # Block every native game from replay, including games still pending.
    replay = replay.loc[~replay["game_id"].isin(native["game_id"])]
    pending = int(native["status"].eq("pending").sum())
    native = native.loc[native["status"].isin(["graded", "tie"])]

    def valid(df):
        if df.empty:
            return df
        units = pd.to_numeric(df["units"], errors="coerce")
        return df.loc[df["bet_result"].isin(["W", "L", "P"]) & np.isfinite(units)].copy()

    replay, native = valid(replay), valid(native)
    replay["_basis"] = "replayed"
    native["_basis"] = "native"
    rows = pd.concat([replay, native], ignore_index=True, sort=False)
    return rows, len(replay), len(native), pending


def pooled_2026_v118_header(latest, ledger):
    """One pooled moneyline scorecard, with a transparent mixed-price basis."""
    data = pooled_2026_v118_rows(latest, ledger)
    if data is None:
        return ""
    rows, replay_count, native_count, pending = data
    ctrl = control_records(rows)
    model = (ctrl or {}).get("model")
    eligible = int(model["bets"]) if model else 0
    sub = f"{replay_count} historical replay · {native_count} recorded · {pending} pending"
    parts = ["<h2 class='sec'>Moneyline · 2026 season overview</h2>",
             control_tiles(ctrl, "Graded", str(eligible), sub)]
    if model and eligible:
        parts.append(f"<p class='mut small'>Season moneyline: {wl_text(model)} · "
                     f"{model['units']:+.2f}u · ROI {roi_short(model['roi'])}. "
                     "Includes historical replay and recorded forecasts, with one result per game. "
                     "Recorded forecasts use their saved pregame prices and replace any replay of the same game.</p>")
        weekly = []
        for week, group in rows.groupby("week", sort=True):
            summary = control_records(group)
            r = (summary or {}).get("model")
            if r and r["bets"]:
                weekly.append(f"W{int(week)} {wl_text(r)}")
        if weekly:
            parts.append(f"<p class='mut small'>By week: {esc(' · '.join(weekly))}</p>")
    else:
        parts.append("<p class='mut small'>No graded 2026 v1.18 picks yet.</p>")
    return "".join(parts)


# Every public season surface uses the same deduplicated pool. Provenance stays
# in season_ats and the repository report rather than the customer interface.
PUBLIC_BASES = {'Historical replay', 'Replayed pregame forecast', '60-minute lock',
                'Recorded pregame', 'Backfilled recorded skip', 'Awaiting ATS lock'}
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


def roi_uncertainty(se):
    se = num(se)
    return f'± {100 * se:.1f} pp SE' if math.isfinite(se) else 'SE unavailable'


def record_tiles(frame, label):
    """Record, cover rate against break-even, units and ROI for the season pool."""
    if frame is None or frame.empty:
        return "<div class='empty'>No ATS results yet. Season results appear here as games are graded.</div>"
    r = season_ats.summary(frame)
    tone = lambda x: '' if not math.isfinite(num(x)) or num(x) == 0 else 'good' if num(x) > 0 else 'bad'
    rate = num(r['cover_rate'])
    meter = ''
    if math.isfinite(rate):
        meter = (f"<div class='meter' role='img' aria-label='Cover rate {pct(rate, 1)}, break-even {pct(BREAK_EVEN, 1)}'>"
                 f"<i style='width:{100 * rate:.1f}%'></i><b style='left:{100 * BREAK_EVEN:.1f}%'></b></div>")
    pending = f" · {r['pending']} pending" if r['pending'] else ''
    tiles = [stat(label, f"{r['wins']}–{r['losses']}–{r['pushes']}", f"W–L–P · {r['bets']} bets{pending}"),
             stat('Cover rate', pct(rate, 1), f"{meter}Break-even {pct(BREAK_EVEN, 1)} · pushes excluded",
                  '' if not math.isfinite(rate) else 'good' if rate > BREAK_EVEN else 'bad'),
             stat('Units', units_text(r['units']), 'Flat 1 unit per pick at −110', tone(r['units'])),
             stat('ROI', roi_short(r['roi']), f"{roi_uncertainty(r['roi_se'])} · per unit staked · pushes included", tone(r['roi']))]
    return f"<div class='gr-summary'>{''.join(tiles)}</div>"


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
        tone = 'pos-tx' if units > 0 else 'neg-tx' if units < 0 else ''
        ko = pd.to_datetime(r.get('kickoff_utc'), utc=True, errors='coerce')
        when = f"<div class='mut small'>{esc(ko.tz_convert(PT).strftime('%a %-I:%M %p %Z'))}</div>" if pd.notna(ko) else ''
        day = pd.to_datetime(r.get('gameday'), errors='coerce')
        if not when and pd.notna(day):
            when = f"<div class='mut small'>{esc(day.strftime('%a %b %-d'))}</div>"
        rows.append([f"<span class='team-code' data-game-id='{esc(r['game_id'])}'>{esc(r['away'])} @ {esc(r['home'])}</span>{when}",
                     pick, favorite_spread_text(r.get('fixed_band_spread'), r['home'], r['away']), final, badge,
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
        label = (f'{int(season)} week {int(week)} · {stats["wins"]}–{stats["losses"]}–{stats["pushes"]} · {stats["skips"]} skips'
                 f"<span class='rt'>{units_text(stats['units']) if stats['bets'] else '—'}</span>")
        parts.append(folded(label, table(['Game', 'ATS pick', 'Model', 'Final', 'Result', 'Units'],
                                         game_rows(group), num_cols=(3, 5)), i == 0))
    return ''.join(parts)


def downloads(latest):
    links = []
    if len(public_ats(latest)):
        links.append("<a href='ats_2026_results.csv'>2026 per-game results (CSV)</a>")
    if (latest or {}).get('ats_locks'):
        links.append("<a href='ats_locked_picks.csv'>Saved spread picks (CSV)</a>")
    if (latest or {}).get('board') is not None and len(latest['board']):
        links.append("<a href='fixed_band_board.csv'>This week’s board (CSV)</a>")
    return f"<h2 class='sec'>Downloads</h2><div class='downloads'>{''.join(links)}</div>" if links else ''


def render_grades(ledger, latest, built):
    season = int(latest['manifest']['season']) if latest is not None else None
    parts = [head('ATS results', 'All 2026 season results. Returns use −110 pricing '
                  'and 1-unit stakes; pushes return the stake.', f'{season} season' if season else '')]
    if latest is None:
        parts.append("<p class='mut'>No picks locked yet.</p>")
    else:
        parts.append(record_tiles(public_ats(latest), f'{season} record'))
        parts.append(render_ats_games(latest))
        parts.append(downloads(latest))
    return html_document(''.join(parts), f'{SITE_NAME} results', 'grades.html', built)


def pooled_basis_text(frame):
    graded = frame[frame.ats_status.eq('graded')]
    replay = int(graded.ats_basis.isin(['Historical replay', 'Replayed pregame forecast']).sum())
    backfill = int(graded.ats_basis.eq('Backfilled recorded skip').sum())
    recorded = len(graded) - replay - backfill
    r = season_ats.summary(frame)
    text = f'{replay} replayed · ' + (f'{backfill} backfilled · ' if backfill else '')
    text += f'{recorded} recorded · {r["pending"]} pending'
    if r['unavailable']:
        text += f' · {r["unavailable"]} unavailable'
    return text


def ats_comparison_tiles(frame, basis='2026 season', title='Model vs simple baselines'):
    """Compare ATS sides on identical selected, completed, non-pick'em games."""
    d = frame.loc[frame.fixed_band_ats_result.isin(['W', 'L', 'P'])
                  & np.isfinite(frame.spread_line) & frame.spread_line.ne(0)
                  & np.isfinite(frame.result) & np.isfinite(frame.fixed_band_spread)]
    tiles = [stat('Compared games', str(len(d)), f'{basis} · same games')]
    for label, prediction in [('Model ATS', d.fixed_band_spread),
                              ('Market favorite ATS', d.spread_line + np.sign(d.spread_line)),
                              ('Home side ATS', d.spread_line + 1)]:
        results, returns = fixed_bands.grade(d, prediction)
        wins, losses, pushes = [int((results == x).sum()) for x in ['W', 'L', 'P']]
        if len(d):
            rate = f'{100 * wins / (wins + losses):.1f}%' if wins + losses else '—'
            se = float(returns.std(ddof=1) / math.sqrt(len(returns))) if len(returns) > 1 else math.nan
            tiles.append(stat(label, f'{wins}–{losses}–{pushes}',
                              f'{rate} covered · {returns.sum():+.2f}u · ROI {roi_short(returns.mean())} · {roi_uncertainty(se)}',
                              'model' if label == 'Model ATS' else ''))
        else:
            tiles.append(stat(label, '—', 'No compared games yet'))
    return (f"<h2 class='sec'>{esc(title)}</h2><div class='gr-summary'>" + ''.join(tiles) + "</div>"
            "<p class='mut small'>Same completed games with a model ATS selection and a market favorite: the model’s pick, "
            "always taking the market favorite, and always taking the home side. "
            "Model skips and market pick’em games are excluded from all three records. "
            "Cover rates exclude pushes; ROI includes pushes.</p>")


def nice_step(span, ticks=4):
    raw = max(span, 1e-9) / ticks
    mag = 10 ** math.floor(math.log10(raw))
    return next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)


def units_chart(frame):
    """Running season units; order by week, then kickoff or game date when available."""
    if frame is None or frame.empty:
        return ''
    g = frame[frame.fixed_band_ats_result.isin(['W', 'L', 'P'])].copy()
    if len(g) < 2:
        return ''
    g['_ko'] = pd.to_datetime(g.get('kickoff_utc'), utc=True, errors='coerce')
    day = pd.to_datetime(g.get('gameday', pd.Series(index=g.index, dtype=str)), utc=True, errors='coerce')
    g['_ko'] = g['_ko'].fillna(day)
    g = g.sort_values(['week', '_ko', 'game_id'], na_position='last')
    run = np.concatenate([[0.], np.cumsum(g.fixed_band_ats_units.astype(float).to_numpy())])
    W, H, L, R, T, B = 1000, 240, 40, 12, 12, 26
    step = nice_step(max(run.max(), 0) - min(run.min(), 0))
    lo, hi = math.floor(min(run.min(), 0) / step) * step, math.ceil(max(run.max(), 0) / step) * step
    hi = hi if hi > lo else lo + step
    x = lambda i: L + (W - L - R) * i / (len(run) - 1)
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)
    out = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='Running units after each graded pick, ending at {units_text(run[-1])}'>"]
    v = lo
    while v <= hi + 1e-9:
        out.append(f"<line class='{'zero' if abs(v) < 1e-9 else 'grid-ln'}' x1='{L}' x2='{W - R}' y1='{y(v):.1f}' y2='{y(v):.1f}'/>"
                   f"<text class='ax' x='{L - 8}' y='{y(v) + 4:.1f}' text-anchor='end'>{'0' if abs(v) < 1e-9 else f'{v:+g}'.replace('-', '−')}</text>")
        v += step
    pts = ' '.join(f'{x(i):.1f},{y(u):.1f}' for i, u in enumerate(run))
    out.append(f"<polygon class='area' points='{x(0):.1f},{y(0):.1f} {pts} {x(len(run) - 1):.1f},{y(0):.1f}'/>")
    out.append(f"<polyline class='ln' points='{pts}'/>")
    for i, r in enumerate(g.to_dict('records'), start=1):
        pick = f"{r.get('fixed_band_ats_team', '')} {spread_text(num(r.get('spread_line')), r.get('fixed_band_ats_side') == 'home')}"
        tip = (f"Week {int(r['week'])} · {r['away']} @ {r['home']} · {pick} · {r['fixed_band_ats_result']} "
               f"{units_text(r['fixed_band_ats_units'])} · running {units_text(run[i])}")
        out.append(f"<g><circle class='hit' cx='{x(i):.1f}' cy='{y(run[i]):.1f}' r='11'><title>{esc(tip)}</title></circle>"
                   f"<circle class='pt' cx='{x(i):.1f}' cy='{y(run[i]):.1f}' r='4'/></g>")
    out.append(f"<text class='ax' x='{L}' y='{H - 6}'>Start</text>"
               f"<text class='ax' x='{W - R}' y='{H - 6}' text-anchor='end'>Pick {len(run) - 1}</text></svg>")
    tone = 'pos-tx' if run[-1] > 0 else 'neg-tx' if run[-1] < 0 else ''
    return (f"<div class='chart'><div class='chart-head'><span class='t'>Running units · 2026 season</span>"
            f"<span class='v {tone}'>{units_text(run[-1])}</span></div>{''.join(out)}</div>")


def weekly_table(frame):
    rows = []
    for week, group in frame.groupby('week', sort=True):
        v = season_ats.summary(group)
        rows.append([f'Week {int(week)}', f'{v["wins"]}–{v["losses"]}–{v["pushes"]}', pct(v['cover_rate'], 1),
                     str(v['skips']), str(v['pending']), units_text(v['units']) if v['bets'] else '—',
                     f"{roi_short(v['roi'])}<div class='mut small'>{roi_uncertainty(v['roi_se'])}</div>"])
    return ("<h2 class='sec'>By week</h2>" +
            table(['Week', 'ATS W–L–P', 'Cover rate', 'Skips', 'Pending', 'Units', 'ROI'], rows, num_cols=(1, 2, 3, 4, 5, 6)))


HOW_IT_WORKS = (
    ("Project the spread", "The model turns each team’s recent box-score profile into a projected point spread."),
    ("Compare with the market", "The pick is the side the projection favors against the market handicap. "
                                "A projection equal to the line takes the market favorite."),
    ("Lock before kickoff", "The latest forecast 60 minutes before kickoff is saved. The handicap and pick never change after that."),
    ("Grade at −110", "Each pick is a flat 1-unit bet at −110. A win returns 0.91u, a loss costs 1u, a push returns the stake. "
                      "Break-even is a 52.4% cover rate."),
)


def market_sides(df):
    """One row per side of every priced, decided game: its moneyline, no-vig implied probability and result,
    plus that side's realized margin and the market spread for it (positive = the side favored/won by)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["side", "price", "q", "won", "band", "margin", "spread"])
    d = df[pd.to_numeric(df["home won"], errors="coerce").isin([0., 1.])].copy()
    q = m.market_ml_wp(d)
    ok = np.isfinite(q)
    d, q = d[ok], q[ok]
    hw = d["home won"].to_numpy(float)
    res = pd.to_numeric(d.get("result", pd.Series(np.nan, index=d.index)), errors="coerce").to_numpy(float)
    spr = pd.to_numeric(d.get("spread_line", pd.Series(np.nan, index=d.index)), errors="coerce").to_numpy(float)
    sides = pd.concat([pd.DataFrame({"side": "home", "price": d.home_moneyline.to_numpy(float), "q": q, "won": hw,
                                     "margin": res, "spread": spr}),
                       pd.DataFrame({"side": "away", "price": d.away_moneyline.to_numpy(float), "q": 1 - q, "won": 1 - hw,
                                     "margin": -res, "spread": -spr})],
                      ignore_index=True)
    sides["band"] = [m.ml_band(p) for p in sides.price]
    return sides


def render_calibration(latest, ledger, built):
    # Keep the existing URL working while replacing its old probability view.
    season = int(latest['manifest']['season']) if latest is not None else None
    parts = [head('ATS performance', 'How all 2026 season picks are doing against the spread, beside simple '
                  'baselines on the same games. Results use −110 pricing and 1-unit stakes.',
                  f'{season} season' if season else '')]
    frame = public_ats(latest)
    if latest is None or frame.empty:
        parts.append("<p class='mut'>No ATS results yet.</p>")
    else:
        parts.append(record_tiles(frame, f'{season} record'))
        parts.append(units_chart(frame))
        parts.append(ats_comparison_tiles(frame))
        parts.append(weekly_table(frame))
    parts.append("<h2 class='sec'>How picks work</h2><ol class='steps'>" +
                 ''.join(f"<li><b>{esc(t)}</b>{esc(d)}</li>" for t, d in HOW_IT_WORKS) + "</ol>")
    return html_document(''.join(parts), f'{SITE_NAME} performance', 'market-calibration.html', built)

# ---------------------------------------------------------------- driver

def render_all(out_dir, data=DATA, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    built = now.astimezone(PT).strftime("%Y-%m-%d %H:%M %Z")
    latest = load_latest(Path(data) / "latest")
    if latest is not None:
        latest['ats_locks'] = ats_locks.display_records(data)
    ledger = load_ledger(data)
    if latest is not None:
        latest['pooled_ats'] = season_ats.build(latest, ledger)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    season_results = public_ats(latest)
    if len(season_results):
        fields = ['game_id', 'season', 'week', 'home', 'away', 'ats_status',
                  'gameday', 'kickoff_utc', 'fixed_band_spread',
                  'spread_line', 'home_score', 'away_score', 'result', 'fixed_band_ats_side', 'fixed_band_ats_team',
                  'fixed_band_ats_handicap', 'fixed_band_ats_result', 'fixed_band_ats_units']
        season_results.reindex(columns=fields).rename(columns={'fixed_band_spread': 'model_spread'}).to_csv(
            out / 'ats_2026_results.csv', index=False)
    else:
        (out / 'ats_2026_results.csv').unlink(missing_ok=True)
    if latest is not None and latest['ats_locks']:
        locked_rows = []
        for row in latest['ats_locks'].values():
            side = ats_locks.select(row['fixed_band_spread'], row['market_spread'], True)
            locked_rows.append(dict(game_id=row['game_id'], season=row['season'],
                home=row['home'], away=row['away'], kickoff_utc=row['kickoff_utc'],
                forecast_utc=row['generated_utc'], lock_at_utc=row['lock_at_utc'],
                model_spread=row['fixed_band_spread'], market_spread=row['market_spread'],
                selected_side=side, selected_team=row[side] if side else '',
                handicap=(-row['market_spread'] if side == 'home' else row['market_spread']) if side else None))
        pd.DataFrame(locked_rows).to_csv(out / 'ats_locked_picks.csv', index=False)
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
            public_rows.append(item)
        pd.DataFrame(public_rows).to_csv(out / 'fixed_band_board.csv', index=False)
    else:
        (out / 'fixed_band_board.csv').unlink(missing_ok=True)
    pages = {"index.html": render_index(latest, ledger, built, now),
             "grades.html": render_grades(ledger, latest, built),
             "market-calibration.html": render_calibration(latest, ledger, built)}
    for name, html in pages.items():
        (out / name).write_text(html, encoding="utf-8")
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


APPENDICES = (("version_report.md", "Appendix A: competing model versions and research arms"),
              ("regraded_ledger_report.md", "Appendix B: original snapshots replayed with the current model"))
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
        parts.append('\n\n2026 pooled ATS results\n\n' + season_ats.report(season_ats.build(latest, load_ledger(data))))
    calibration = Path(__file__).parent / 'research/wp_probability_calibration_results/REPORT.md'
    if calibration.exists():
        parts.append('\n\nAppendix D: win-probability calibration theory (frozen research)\n\n' + calibration.read_text())
    return "".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages-only", action="store_true", help="render from committed data/ without running the model")
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "public"))
    args = ap.parse_args(argv)
    if not args.pages_only:
        outdir = run_model()
        season, week = snapshot(outdir)
        print(f"snapshot: {season} week {week} -> {LATEST}")
        print(f"ATS timed capture: {ats_locks.record(DATA)}")
        kalshi.safe_record(DATA)  # secondary quotes for newly locked games; never fails the build
        matchup.safe_record(outdir, DATA)  # pre-registered H4 term for newly locked games; never fails the build
        totals.safe_record(DATA)  # pre-registered H5 total and moneylines for newly locked games; never fails the build
        grade_ledger.main([])
        version_report.run(DATA,LATEST)
    files = render_all(args.out)
    if not args.pages_only:
        count = ats_forward_shadow.record(DATA)
        print(f"ATS research: {count} new immutable shadow locks")
        # Captures happen after rendering; include this build's new archive rows.
        (DATA / 'ledger_report.txt').write_text(published_report(DATA), encoding='utf-8')
    print(f"site: {len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
