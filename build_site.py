#!/usr/bin/env python3
"""Build the NFL model site: run the model, snapshot its outputs into data/,
grade the forward ledger, and render static pages into public/.

    python build_site.py               # full build (what build.yml runs)
    python build_site.py --pages-only  # re-render from committed data/ only

Pages (public: the production model only; W-L, win % and ROI. Standard errors, log loss, model
internals, earlier revisions, the v1.16 shadow lock and every research arm stay in
the repository's data/ledger_report.txt and data/latest/)
  index.html               this week's games: model vs market, pick, biggest factors, injury reports
  grades.html              locked picks graded, beside always-favorite and always-home; rebuilt history
  market-calibration.html  ATS performance and same-game spread controls (legacy URL)

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
REPO_REPORT = "https://github.com/Dave356w/NFL-MODEL/blob/main/data/ledger_report.txt"

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
  --bg:#f3f5f7; --surface:#ffffff; --surface-2:#eef1f4; --ink:#161b20;
  --muted:#4f5a65; --faint:#636e7b; --line:#dde3e8; --line-2:#eceff2;
  --warm:198,84,44; --cool:52,116,168; --lean:176,124,16;
  --warm-tx:164,69,36; --cool-tx:46,103,149; --lean-tx:130,92,12;
  --good:29,122,60; --bad:180,68,42;
  --mono:"JetBrains Mono",ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
  --sans:"Archivo",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  --shadow:0 1px 2px rgba(16,18,29,.05),0 10px 26px -20px rgba(16,18,29,.28);
  --r:6px; --r-s:3px; --r-pill:999px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f1418; --surface:#171d24; --surface-2:#131920; --ink:#e7ecef;
  --muted:#96a2ad; --faint:#7f8b97; --line:#242e38; --line-2:#1c242c;
  --warm:236,122,72; --cool:96,158,208; --lean:244,196,96;
  --warm-tx:236,122,72; --cool-tx:96,158,208; --lean-tx:244,196,96;
  --good:88,194,125; --bad:239,127,98;
  --shadow:0 1px 2px rgba(0,0,0,.45),0 14px 32px -22px rgba(0,0,0,.8);
}
:root:not([data-theme="light"]) .logo.lt{display:none}:root:not([data-theme="light"]) .logo.dk{display:block}}
html[data-theme="dark"] .logo.lt{display:none}html[data-theme="dark"] .logo.dk{display:block}
html[data-theme="dark"]{
  --bg:#0f1418; --surface:#171d24; --surface-2:#131920; --ink:#e7ecef;
  --muted:#96a2ad; --faint:#7f8b97; --line:#242e38; --line-2:#1c242c;
  --warm:236,122,72; --cool:96,158,208; --lean:244,196,96;
  --warm-tx:236,122,72; --cool-tx:96,158,208; --lean-tx:244,196,96;
  --good:88,194,125; --bad:239,127,98;
  --shadow:0 1px 2px rgba(0,0,0,.45),0 14px 32px -22px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 var(--sans);
  -webkit-font-smoothing:antialiased;padding:20px 16px 60px}
.mx-wrap{max-width:1060px;margin:0 auto}
a{color:rgb(var(--lean-tx))}
.topbar{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:12px}
.brand{font:800 18px/1 var(--sans);letter-spacing:.13em;text-transform:uppercase;color:var(--ink);text-decoration:none}
.theme{appearance:none;border:1px solid var(--line);background:var(--surface);color:var(--muted);
  font:600 14px/1 var(--sans);padding:7px 11px;border-radius:var(--r);cursor:pointer}
.theme:hover{color:var(--ink)}
.nav{display:flex;flex-wrap:wrap;gap:6px 16px;margin:0 0 16px;font:600 14px/1.3 var(--sans)}
.nav a{color:var(--muted);text-decoration:none;padding-bottom:3px;border-bottom:2px solid transparent}
.nav a:hover{color:var(--ink)}
.nav a[aria-current="page"]{color:var(--ink);border-bottom-color:rgb(var(--lean))}
.gr-head{margin:4px 2px 14px}
.gr-h1{font:800 26px/1.1 var(--sans);margin:0 0 6px}
.gr-lead{color:var(--muted);font-size:14.5px;max-width:78ch}
.stamp{font-family:var(--mono);font-size:13px}
.gr-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:0 0 12px}
.gr-stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:11px 13px;box-shadow:var(--shadow)}
.gr-stat .l{font:650 12px/1.2 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.gr-stat .v{font:800 24px/1.15 var(--mono);margin:5px 0 3px;font-variant-numeric:tabular-nums}
.gr-stat .v.model{color:rgb(var(--cool-tx))}.gr-stat .v.good{color:rgb(var(--good))}.gr-stat .v.bad{color:rgb(var(--bad))}
.gr-stat .s{font:500 12.5px/1.35 var(--mono);color:var(--muted)}
.gr-note{background:var(--surface-2);border:1px solid var(--line-2);border-radius:var(--r);
  padding:10px 13px;margin:0 0 14px;font-size:13.5px;color:var(--muted);max-width:none}
.gr-note b{color:var(--ink)}
.flag-note{border-left:3px solid rgb(var(--lean));background:rgba(var(--lean),.08)}
h2.sec{font:800 15px/1.2 var(--sans);letter-spacing:.08em;text-transform:uppercase;margin:26px 2px 9px}
.gr-tablewrap{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  box-shadow:var(--shadow);overflow-x:auto;margin-bottom:12px}
table.gr{width:100%;border-collapse:collapse;font-size:14px}
table.gr th{font:650 11.5px/1.2 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--faint);
  text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;background:var(--surface-2)}
table.gr td{padding:8px 10px;border-bottom:1px solid var(--line-2);vertical-align:middle}
table.gr tr:last-child td{border-bottom:0}
table.gr .n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.gr tr.total td{font-weight:700;border-top:2px solid var(--line)}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.mut{color:var(--muted)}
.badge{display:inline-block;font:700 11px/1 var(--sans);letter-spacing:.05em;text-transform:uppercase;
  padding:4px 6px;border-radius:var(--r-s);border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.badge.w{color:rgb(var(--good));border-color:rgba(var(--good),.4);background:rgba(var(--good),.08)}
.badge.l{color:rgb(var(--bad));border-color:rgba(var(--bad),.4);background:rgba(var(--bad),.08)}
.badge.lean{color:rgb(var(--lean-tx));border-color:rgba(var(--lean),.5);background:rgba(var(--lean),.12)}
.badge.warn{color:rgb(var(--warm-tx));border-color:rgba(var(--warm),.45);background:rgba(var(--warm),.08)}
.team-code{font:800 13px/1 var(--mono);letter-spacing:.02em}
/* scoreboard */
.grid{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r);box-shadow:var(--shadow);overflow:clip}
.card + .card{border-top:1px solid var(--line)}
.game-summary{position:relative;display:block;padding:13px 40px 12px 16px;list-style:none;cursor:pointer}
.game-summary::-webkit-details-marker{display:none}
.game-summary::marker{content:""}
.game-summary:hover{background:var(--surface-2)}
.card[open]>.game-summary{background:var(--surface-2);border-bottom:1px solid var(--line-2)}
.teams{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.7fr) minmax(0,1fr);align-items:center;gap:12px}
.side{display:flex;align-items:center;gap:10px;min-width:0}
.side.home{justify-content:flex-end;text-align:right}
.chip{display:grid;place-items:center;width:44px;height:44px;flex:none;border-radius:var(--r-pill);
  border:1px solid var(--line);background:var(--surface-2);font:800 13px/1 var(--mono);position:relative}
.chip .logo{position:absolute;inset:5px;width:32px;height:32px;object-fit:contain}
.chip .logo.dk{display:none}
.chip.has-logo span{visibility:hidden}
.club{min-width:0}
.club .nm{font:750 16.5px/1.15 var(--sans);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.club .wp{font:800 22px/1.1 var(--mono);font-variant-numeric:tabular-nums}
.club .wp.fav{color:rgb(var(--lean-tx))}
.mid{display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center}
.mid .t{font:800 15px/1 var(--mono)}
.mid .mk{font:600 12.5px/1.2 var(--mono);color:var(--muted)}
.mid .mk span{white-space:nowrap}
.chev{position:absolute;right:14px;top:50%;transform:translateY(-50%);color:var(--faint);font:800 18px/1 var(--sans)}
.card[open] .chev{transform:translateY(-50%) rotate(180deg);color:var(--ink)}
.flags{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:9px}
.pick-lines{display:grid;grid-template-columns:85px 1fr;gap:5px 10px;margin-top:12px;font-size:13px;text-align:left}
.pick-lines .kind{color:var(--muted);font-weight:600}
.probbar{display:flex;height:8px;border-radius:var(--r-s);overflow:hidden;margin:10px 0 2px;background:var(--line-2)}
.probbar i{display:block;height:100%}
.probbar .a{background:rgb(var(--warm))}.probbar .h{background:rgb(var(--cool))}
.detail{padding:12px 16px 16px}
.detail h3{font:750 13px/1.2 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin:14px 0 6px}
.detail p{margin:6px 0;font-size:14px;max-width:78ch}
.cbar{position:relative;height:10px;background:var(--line-2);border-radius:var(--r-s)}
.cbar i{position:absolute;top:0;bottom:0;border-radius:var(--r-s)}
.cbar i.pos{background:rgb(var(--cool))}.cbar i.neg{background:rgb(var(--warm))}
.cbar::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--faint)}
.factor-name{font-weight:650;line-height:1.3}
.factor-note{color:var(--muted);font-size:12px;line-height:1.4;margin-top:3px}
.factor-impact{min-width:96px;max-width:145px;margin-left:auto}
.factor-toward{font:650 12px/1.3 var(--sans);text-align:right;margin-bottom:7px;white-space:nowrap}
.factor-toward.pos{color:rgb(var(--cool-tx))}.factor-toward.neg{color:rgb(var(--warm-tx))}
.factor-impact .cbar{height:6px}
.fold{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);margin:0 0 8px}
.fold>summary{cursor:pointer;list-style:none;padding:10px 13px;font:700 14px/1.3 var(--sans);display:flex;gap:8px}
.fold>summary::-webkit-details-marker{display:none}
.fold>summary::before{content:"▸";color:var(--faint)}.fold[open]>summary::before{content:"▾"}
.fold .rt{margin-left:auto;font-family:var(--mono)}
.fold .gr-tablewrap{box-shadow:none;border-width:1px 0 0;border-radius:0;margin:0}
.record{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:10px 14px;margin-top:10px;font-size:14px}
.record .l{font:650 12px/1.2 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin-bottom:4px}
.record .go{text-align:right;font:600 14px/1 var(--sans);margin-top:6px}
.small{font-size:13px}
.detail .gr-summary.band{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:0 0 4px}
.detail .band .gr-stat{box-shadow:none;padding:8px 10px}.detail .band .gr-stat .v{font-size:19px}
.up{color:rgb(var(--cool-tx));font-weight:700}.dn{color:rgb(var(--warm-tx));font-weight:700}
.foot{margin-top:28px;color:var(--faint);font-size:12.5px;border-top:1px solid var(--line);padding-top:10px}
@media (max-width:640px){
  .teams{grid-template-columns:minmax(0,1fr) 92px minmax(0,1fr);gap:6px}
  .chip{display:none}
  .club .nm{font-size:14px}.club .wp{font-size:19px}
  table.gr{font-size:13px}
}
"""

THEME_JS = """<script>(function(){var k='nfl-theme',r=document.documentElement;
try{var s=localStorage.getItem(k);if(s)r.setAttribute('data-theme',s);}catch(e){}
window.toggleTheme=function(){var d=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
var n=d==='dark'?'light':'dark';r.setAttribute('data-theme',n);try{localStorage.setItem(k,n);}catch(e){}};})();</script>"""

PAGES = (("index.html", "Picks"), ("grades.html", "Results"),
         ("market-calibration.html", "Performance"))

# Customer-facing presentation. Calculation and archival code remain independent.
CSS += r"""
:root{--bg:#f4f7fa;--ink:#14263c;--muted:#52677c;--faint:#627589;
 --lean:9,125,97;--lean-tx:7,107,83;--r:14px;--r-s:6px;
 --shadow:0 3px 16px -8px rgba(20,38,60,.16)}
body{padding:26px 24px 54px}.mx-wrap{max-width:1180px}
.topbar{align-items:center;border-bottom:0;margin-bottom:22px;padding:0}
.brand{display:flex;align-items:center;gap:12px;font-size:20px;letter-spacing:-.03em;text-transform:none}
.brand-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;
 background:rgb(var(--lean));color:white;font:800 13px/1 var(--sans);letter-spacing:.02em}
.brand-version{font:600 11px/1 var(--mono);color:var(--muted);border:1px solid var(--line);padding:5px 7px;border-radius:6px}
.nav{gap:5px;margin-bottom:30px;padding:5px;background:var(--surface);border:1px solid var(--line);
 border-radius:12px;width:fit-content;max-width:100%;overflow-x:auto;flex-wrap:nowrap}
.nav a{padding:10px 18px;border:0;border-radius:8px;white-space:nowrap}
.nav a[aria-current="page"]{background:var(--ink);color:var(--surface)}
.gr-head{margin:0 0 22px}.gr-h1{font-size:32px;letter-spacing:-.04em;margin-bottom:9px}
.gr-lead{font-size:15px;line-height:1.6}.gr-summary{gap:14px;margin-bottom:20px}
.gr-stat{padding:19px 20px}.gr-stat .l{font-size:11px;letter-spacing:.07em}
.gr-stat .v{font-size:27px;margin:9px 0 6px}.gr-stat .s{font-family:var(--sans);font-size:13px}
.gr-note{padding:13px 16px;line-height:1.6;border-radius:10px}
h2.sec{font-size:16px;letter-spacing:-.015em;text-transform:none;margin:32px 0 14px}
h3{font-size:14px}.record{padding:15px 18px;margin-bottom:18px;margin-top:0}
.record .l{margin-bottom:8px}.record .mono{font-size:13px;line-height:1.65}
.grid{border-radius:16px}.game-summary{padding:22px 45px 18px 22px}
.teams{grid-template-columns:minmax(0,1fr) minmax(190px,.9fr) minmax(0,1fr);gap:18px}
.chip{width:48px;height:48px;border:0;background:transparent}
.chip .logo{width:38px;height:38px}.club .nm{font-size:17px}.club .wp{font-size:28px;margin-top:5px}
.mid .t{font:650 12px/1.4 var(--sans);color:var(--muted)}.mid .mk{font-size:11px;line-height:1.6}
.probbar{height:4px;margin-top:17px}.pick-lines{grid-template-columns:78px 1fr;font-size:12px;line-height:1.5;margin-top:14px}
.detail{padding:20px 22px 24px}.detail .gr-tablewrap{box-shadow:none}.detail h3{letter-spacing:.04em}
table.gr th{padding:13px 15px}table.gr td{padding:12px 15px}
table.gr tbody tr:hover{background:var(--surface-2)}
.fold>summary{padding:16px 18px}.fold .rt{font-size:12px}.flags{justify-content:flex-start}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;line-height:1.6;padding-top:18px;margin-top:36px}
.foot a{color:var(--muted)}.skip-link{position:absolute;left:16px;top:-80px;padding:10px;background:var(--surface);z-index:10}
.skip-link:focus{top:10px}:focus-visible{outline:3px solid rgb(var(--lean));outline-offset:4px}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0d1724;--ink:#e7f0f8;--muted:#a2b3c5;--faint:#8fa2b7;--lean:61,192,151;--lean-tx:110,218,184}}
html[data-theme="dark"]{--bg:#0d1724;--ink:#e7f0f8;--muted:#a2b3c5;--faint:#8fa2b7;--lean:61,192,151;--lean-tx:110,218,184}
@media(max-width:640px){body{padding:18px 12px 34px}.topbar{margin-bottom:16px}.brand{font-size:18px;gap:8px}
 .brand-mark{width:32px;height:32px}.brand-version{display:none}.nav{width:100%;margin-bottom:24px}
 .nav a{flex:1;text-align:center;padding:10px 12px}.gr-h1{font-size:28px}
 .gr-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.gr-stat{padding:13px 12px}.gr-stat .v{font-size:22px}
 .teams{grid-template-columns:minmax(0,1fr) 112px minmax(0,1fr);gap:8px}
 .game-summary{padding:17px 29px 16px 14px}.club .nm{font-size:13px}.club .wp{font-size:23px}
 .mid .mk{font-size:10px}.mid .t{font-size:11px}.chev{right:10px}.detail{padding:15px 12px}
 table.gr th,table.gr td{padding:10px 11px}.pick-lines{grid-template-columns:68px 1fr;font-size:11.5px}
 .record .mono{font-family:var(--sans)}.fold>summary{flex-wrap:wrap}.fold .rt{margin-left:0}
 .week-summary{grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
 .week-summary .gr-stat{padding:12px 9px}.week-summary .l{font-size:10px}.week-summary .s{font-size:11px}
}
"""


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


def html_document(body, title, current, built):
    nav = "".join(f"<a href='{href}'{' aria-current=\"page\"' if href == current else ''}>{label}</a>"
                  for href, label in PAGES)
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><meta name='description' content='NFL ATS picks, projected spreads, locked handicaps and season results'>"
            f"{THEME_JS}<style>{font_face_css()}{CSS}</style></head><body><a class='skip-link' href='#main-content'>Skip to content</a><div class='mx-wrap'>"
            f"<div class='topbar'><a class='brand' href='index.html'><span class='brand-mark' aria-hidden='true'>NF</span>{SITE_NAME}"
            f"<span class='brand-version'>{esc(m.REVISION.rsplit('-', 1)[-1])}</span></a>"
            "<button class='theme' type='button' onclick='toggleTheme()' aria-label='Toggle colour theme'>Theme</button></div>"
            f"<nav class='nav' aria-label='Main navigation'>{nav}</nav><main id='main-content'>{body}</main>"
            f"<footer class='foot'><span>Updated <span class='stamp'>{esc(built)}</span></span>"
            f"<a href='{REPO_REPORT}'>Model documentation</a></footer></div></body></html>")


def head(title, lead):
    return f"<div class='gr-head'><h1 class='gr-h1'>{esc(title)}</h1><div class='gr-lead'>{lead}</div></div>"


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


def historical_pick_reference(latest, game, edge):
    d = latest.get('fixed_band_ledger', pd.DataFrame()).copy()
    if d.empty:
        return ''
    # Completed earlier dates only; never use this game's outcome or later games.
    day = pd.to_datetime(game.get('gameday'), errors='coerce', utc=True)
    if pd.notna(day) and 'gameday' in d:
        d = d[pd.to_datetime(d.gameday, errors='coerce', utc=True) < day]
    else:
        d = d[d.season < int(game['season'])]
    d = d[d.game_id != game['game_id']]
    rows = []
    def record(label, results, units, accuracy, price_note):
        w, l, p, s = [int((results == x).sum()) for x in ('W', 'L', 'P', 'S')]
        n = w + l + p
        rate = f'{100*w/(w+l):.1f}% {accuracy}' if w+l else '—'
        roi = roi_short(float(units.sum()) / n) if n else '—'
        sample = f'{n} bets · {s} skips' + (' · small sample' if w+l < 100 else '')
        return [label, f'{w}–{l}–{p}', rate, f'{roi} · {price_note}', sample]
    p = num(game.get('model_wp'))
    if math.isfinite(p) and not math.isclose(p, .5):
        confidence = max(p, 1-p)
        cuts = np.array([.50, .55, .65, .75, .85, 1.000001])
        i = min(int(np.searchsorted(cuts, confidence, side='right')-1), len(cuts)-2)
        c = np.maximum(d.model_wp, 1-d.model_wp)
        g = d[(c >= cuts[i]) & (c < cuts[i+1]) & d.bet_result.isin(['W','L','P'])]
        rows.append(record(f'Moneyline · {cuts[i]*100:.0f}–{min(cuts[i+1],1)*100:.0f}% model probability',
                           g.bet_result, g.units, 'win', 'recorded moneylines'))
    if math.isfinite(edge):
        e = (d.fixed_band_spread-d.spread_line).abs()
        if edge <= fixed_bands.EPS:
            g = d[(e <= fixed_bands.EPS) & d.fixed_band_spread.notna()]
            label = 'Spread · zero edge (no bet)'
        else:
            cuts = [0.,1.,3.,7.,math.inf]
            i = next(i for i in range(4) if edge <= cuts[i+1]+fixed_bands.EPS)
            g = d[(e > cuts[i]+fixed_bands.EPS) & (e <= cuts[i+1]+fixed_bands.EPS)]
            label = f'Spread · >{cuts[i]:g}–{cuts[i+1]:g}-point edge' if math.isfinite(cuts[i+1]) else 'Spread · >7-point edge'
        rows.append(record(label, g.fixed_band_ats_result, g.fixed_band_ats_units, 'cover', 'assumed −110'))
    if not rows:
        return ''
    return ("<h3>Historical reference · reconstructed</h3>" +
            table(['Similar picks', 'W–L–P', 'Accuracy', 'ROI', 'Sample'], rows, num_cols=(1,2,3,4)) +
            "<p class='mut small'>Earlier completed games only, excluding this game and later dates. "
            "Win and cover rates exclude pushes and skips; ROI includes pushed stakes. "
            "Records are reconstructed, not locked forward evidence or this game's cover probability. "
            "A zero edge skips; other edge bands contain bets, so their skip count is zero.</p>")

def ats_card_state(latest, row, now):
    """One ATS-only display state shared by cards and the board download."""
    rev = latest['manifest']['revision']
    home, away = row['home'], row['away']
    ms, line = num(row.get('fixed_band_spread')), num(row.get('spread_line'))
    saved = latest.get('ats_locks', {}).get((rev, row['game_id']))
    ko = m.kickoff_utc(row)
    cutoff = ats_locks.deadline(ko) if ko is not None else None
    source, status, note = 'Provisional', 'provisional', ''
    if saved is not None:
        ms, line = num(saved['fixed_band_spread']), num(saved['market_spread'])
        status = 'locked'
        source = 'Earlier recorded pick' if saved.get('legacy_lock') else '60-minute lock'
        when = ats_locks.utc(saved['lock_at_utc']).astimezone(PT).strftime('%a %-I:%M %p %Z')
        note = f'ATS locked {when}'
    elif cutoff is not None and now >= cutoff:
        status, source = 'unavailable', 'No saved ATS selection'
        pooled = latest.get('pooled_ats', pd.DataFrame())
        past = pooled[pooled.game_id.eq(row['game_id'])] if len(pooled) else pd.DataFrame()
        if len(past) and past.iloc[0].ats_status == 'graded':
            replay = past.iloc[0]
            ms, line = num(replay.fixed_band_spread), num(replay.spread_line)
            status, source, note = 'replay', replay.ats_basis, 'Replayed pick'
        else:
            note = 'ATS lock unavailable'
    elif cutoff is not None:
        when = cutoff.astimezone(PT).strftime('%a %-I:%M %p %Z')
        note = f'ATS provisional · locks {when}'
    else:
        note = 'ATS provisional · kickoff unconfirmed'
    if saved is not None and ats_locks.backfilled(saved):
        # Owner decision 2026-10-19: a saved skip is graded as a favorite bet.
        source, note = 'Backfilled recorded skip', note + ' · skip backfilled as favorite'
    pick, gap = ats_card_pick(ms, line, home, away)
    if status == 'unavailable':
        pick, gap = 'Unavailable · no saved pre-lock forecast', math.nan
    grade, units = '', math.nan
    if status in ('locked', 'replay') and math.isfinite(num(row.get('result'))):
        grades, returns = fixed_bands.grade(pd.DataFrame({
            'spread_line': [line], 'result': [num(row['result'])]}), [ms])
        grade, units = grades[0], returns[0]
    chosen = fixed_bands.pick(ms, line) if math.isfinite(ms-line) else 0.
    side = '' if status == 'unavailable' or chosen == 0 else ('home' if chosen > 0 else 'away')
    return dict(model_spread=ms, spread_line=line, pick=pick, gap=gap, status=status,
                source=source, note=note, saved=saved, result=grade, units=units,
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
    parts = [head(f'Week {week} ATS picks',
                  f'{season} regular season · Picks lock 60 minutes before kickoff. Open a game for spread and injury details.')]
    upcoming = int(board.result.isna().sum()) if 'result' in board else len(board)
    stamp = pd.to_datetime(man.get('generated_utc'), utc=True, errors='coerce')
    local = stamp.tz_convert(PT) if pd.notna(stamp) else None
    parts.append("<div class='gr-summary week-summary'>"
        + stat('Upcoming', str(upcoming), 'games on the schedule')
        + stat('Completed', str(len(board)-upcoming), 'games this week')
        + stat('Updated', local.strftime('%-I:%M') if local is not None else '—',
               local.strftime('%p %Z · %b %-d') if local is not None else 'Awaiting forecast') + '</div>')
    parts.append(spread_headline(latest, season))
    if latest.get('ats_locks'):
        parts.append("<p class='mut small'><a href='ats_locked_picks.csv'>Saved spread picks</a> · "
                     "Recorded handicaps and selections remain fixed after lock.</p>")

    def pending(row):
        ko = m.kickoff_utc(row)
        return (has_avail and pd.isna(row.get('result')) and ko is not None and ko > now
                and not m.injury_reports_ready(row, ko, now))

    rows = board.to_dict('records')
    count = sum(pending(r) for r in rows)
    if count:
        parts.append(f"<div class='gr-note flag-note'>Injury reports aren't final for {count} "
                     f"game{'s' if count != 1 else ''} yet, so {'those numbers' if count != 1 else 'that number'} can still move.</div>")
    far = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    rows.sort(key=lambda r: (pd.notna(r.get('result')), m.kickoff_utc(r) or far, str(r['game_id'])))
    cards = []
    for row in rows:
        home, away = row['home'], row['away']
        state = ats_card_state(latest, row, now)
        ms, line = state['model_spread'], state['spread_line']
        flags = []
        if pd.notna(row.get('result')):
            flags.append(f"<span class='badge'>Final {score_text(row.get('away_score'), row.get('home_score'))}</span>")
        elif pending(row):
            flags.append("<span class='badge warn'>Report pending</span>")
        if not bool(row.get('ready', True)):
            flags.append("<span class='badge'>Limited history</span>")
        flags.append(f"<span class='badge'>{esc(state['note'])}</span>")
        if state['result']:
            result = 'Skip' if state['result'] == 'S' else state['result']
            tone = 'w' if state['result'] == 'W' else 'l' if state['result'] == 'L' else ''
            flags.append(f"<span class='badge {tone}'>ATS result · {esc(result)}</span>")
        for side in ('away', 'home'):
            expected, usual = row.get(f'{side}_qb_expected'), row.get(f'{side}_qb_usual')
            if isinstance(expected, str) and isinstance(usual, str) and expected != usual:
                flags.append(f"<span class='badge warn'>{esc(row[side])} QB: {esc(expected)}</span>")
        difference = f" · {state['gap']:g}-point difference" if math.isfinite(state['gap']) and state['gap'] > fixed_bands.EPS else ''
        pick = (f"<div class='pick-lines'><span class='kind'>ATS pick</span>"
                f"<span>{state['pick']}{difference}</span></div>")
        spreads = (f"<span>Model {favorite_spread_text(ms, home, away)}</span>"
                   + (f" · <span>Market {favorite_spread_text(line, home, away)}</span>" if math.isfinite(line) else ''))

        def club(code, cls):
            chip = f"<div class='chip'><span>{esc(code)}</span>{logo_html(code)}</div>"
            name = f"<div class='club'><div class='nm'>{esc(TEAM_NAMES.get(code, code))}</div></div>"
            return f"<div class='side {cls}'>{chip + name if cls == 'away' else name + chip}</div>"

        summary = (f"<summary class='game-summary'><div class='teams'>{club(away, 'away')}"
                   f"<div class='mid'><div class='t'>{esc(kickoff_text(row))}</div><div class='mk sp'>{spreads}</div></div>"
                   f"{club(home, 'home')}</div>{pick}<div class='flags'>{''.join(flags)}</div><span class='chev'>⌄</span></summary>")
        detail = ["<div class='detail'>", table(['', esc(away), esc(home)], [
            ['Model spread', spread_text(ms, False), spread_text(ms, True)],
            ['Market spread', spread_text(line, False), spread_text(line, True)]], num_cols=(1, 2))]
        if state['saved'] is not None:
            forecast = ats_locks.utc(state['saved']['generated_utc']).astimezone(PT).strftime('%a %-I:%M %p %Z')
            detail.append(f"<p class='mut'>Saved ATS selection · forecast {esc(forecast)}. "
                          "The model spread, market handicap and selection shown above are fixed.</p>")
        elif state['status'] == 'replay':
            detail.append("<p class='mut'>Historical replay of the saved pregame forecast. This is not a recorded ATS pick.</p>")
        if has_avail:
            detail.append(f"<p class='mut'>Projected QBs: {esc(away)} {_qb(row, 'away')} · {esc(home)} {_qb(row, 'home')}</p>")
            detail.append(report_notes_html(latest.get('report_notes'), (away, home), int(row['week'])))
        detail.append('</div>')
        cards.append(f"<details class='card'>{summary}{''.join(detail)}</details>")
    parts.append(f"<div class='grid'>{''.join(cards)}</div>")
    parts.append("<p class='mut small'>The point difference compares the projected spread with the market handicap. "
                 "<a href='grades.html'>View ATS results →</a></p>")
    return html_document(''.join(parts), f'{SITE_NAME} — week {week}', 'index.html', built)

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


def render_ats_basis(latest):
    pooled = (latest or {}).get('pooled_ats', pd.DataFrame())
    parts = ["<h2 class='sec'>Recorded and replayed results</h2>"]
    if pooled.empty:
        return ''.join(parts) + "<p class='mut'>No recorded ATS picks yet.</p>"
    labels = [('Recorded pregame', 'Earlier recorded picks'), ('60-minute lock', '60-minute locks'),
              ('Historical replay', 'Historical replay'), ('Replayed pregame forecast', 'Replayed pregame forecasts'),
              ('Backfilled recorded skip', 'Recorded skips backfilled as favorite bets')]
    rows = []
    for basis, label in labels:
        group = pooled[pooled.ats_basis.eq(basis)]
        if group.empty and basis != '60-minute lock':
            continue
        r = season_ats.summary(group)
        rate = pct(r['cover_rate'], 1)
        record = f'{r["wins"]}–{r["losses"]}–{r["pushes"]}' if r['opportunities'] else '—'
        rows.append([label, record, rate, str(r['skips']), str(r['pending']),
                     f'{r["units"]:+.2f}', roi_short(r['roi'])])
    parts.append(table(['Source', 'ATS W–L–P', 'Cover rate', 'Skips', 'Pending', 'Units', 'ROI'],
                       rows, num_cols=(1, 2, 3, 4, 5, 6)))
    parts.append("<p class='mut small'>Recorded picks use saved pregame handicaps. Earlier recordings retain their "
                 "original capture times; the 60-minute record starts with the new lock policy. "
                 "Replay is shown separately and is identified in the per-game download. "
                 "Backfilled rows were recorded as skips and are graded as favorite bets after the result; "
                 "they are not recorded picks.</p>")
    return ''.join(parts)


def render_ats_games(latest):
    if latest is None:
        return ''
    pooled = latest.get('pooled_ats', pd.DataFrame())
    history = latest.get('fixed_band_ledger', pd.DataFrame())
    frames = [pooled] if len(pooled) else []
    if len(history):
        historical = history[~history.season.eq(2026)].copy() if len(pooled) else history.copy()
        historical = historical[historical.fixed_band_ats_result.isin(['W', 'L', 'P', 'S'])]
        if len(historical):
            historical['ats_basis'] = 'Historical replay'
            historical['ats_status'] = np.where(historical.result.notna(), 'graded', 'pending')
            frames.append(historical)
    if not frames:
        return "<p class='mut'>No game results yet.</p>"
    games = pd.concat(frames, ignore_index=True, sort=False)
    parts = ["<h2 class='sec'>Game-by-game ATS results</h2>"]
    groups = list(games.groupby(['season', 'week'], sort=True))
    for i, ((season, week), group) in enumerate(reversed(groups)):
        rows = []
        for r in group.sort_values('game_id').to_dict('records'):
            grade = r.get('fixed_band_ats_result', '')
            side, team = r.get('fixed_band_ats_side', ''), r.get('fixed_band_ats_team', '')
            if grade == 'S':
                pick, badge = 'Skip', "<span class='badge'>Skip</span>"
            elif team:
                pick = f'{esc(team)} {spread_text(num(r.get("spread_line")), side == "home")}'
                badge = result_badge(grade) if grade else "<span class='badge'>Pending</span>"
            else:
                pick = 'Awaiting lock' if r.get('ats_status') == 'pending' else 'Unavailable'
                badge = f"<span class='badge'>{esc(r.get('ats_status', 'unavailable').title())}</span>"
            final = score_text(r.get('away_score'), r.get('home_score')) if math.isfinite(num(r.get('result'))) else 'Pending'
            units = num(r.get('fixed_band_ats_units'))
            ko = pd.to_datetime(r.get('kickoff_utc'), utc=True, errors='coerce')
            when = f" <span class='mut'>{esc(ko.tz_convert(PT).strftime('%a %-I:%M %p %Z'))}</span>" if pd.notna(ko) else ''
            rows.append([f"<span class='team-code' data-game-id='{esc(r['game_id'])}'>{esc(r['away'])} @ {esc(r['home'])}</span>{when}",
                         pick, final, badge, f'{units:+.2f}' if math.isfinite(units) else '—',
                         esc(r.get('ats_basis', 'Historical replay'))])
        stats = season_ats.summary(group)
        label = f'{int(season)} week {int(week)} · {stats["wins"]}–{stats["losses"]}–{stats["pushes"]} · {stats["skips"]} skips'
        parts.append(folded(label, table(['Game', 'ATS pick', 'Final', 'ATS result', 'Units', 'Source'],
                                         rows, num_cols=(2, 4)), i == 0))
    return ''.join(parts)


def render_grades(ledger, latest, built):
    parts = [head('ATS results', 'Season records, cover rates and returns at −110 with 1-unit stakes. '
                  'Pushes return the stake; matching projected and market lines are skipped.')]
    if latest is None:
        parts.append("<p class='mut'>No picks locked yet.</p>")
    else:
        parts.append(spread_headline(latest, int(latest['manifest']['season'])))
        parts.append(render_ats_basis(latest))
        parts.append(render_fixed_bands(latest))
        parts.append(render_ats_games(latest))
    return html_document(''.join(parts), f'{SITE_NAME} results', 'grades.html', built)

def render_retro(latest):
    """The current model replayed on past seasons: hindsight, labelled as such."""
    retro = latest.get("retro_ledger")
    if retro is None or retro.empty:
        return ""
    seasons = sorted(int(x) for x in retro.season.unique())
    out = ["<h2 class='sec'>Historical replay</h2>",
           f"<div class='gr-note'>Results calculated with the current model for {seasons[0]}–{seasons[-1]}. "
           "Recorded forecasts are shown separately above.</div>"]
    played = retro[pd.to_numeric(retro["home won"], errors="coerce").isin([0., .5, 1.])]
    controls=control_records(played)
    compared=(controls or {}).get('model',{}).get('bets',0)
    out.append(control_tiles(controls, "Compared games", str(compared), f"{seasons[0]}–{seasons[-1]}"))
    out.append("<p class='mut small'>Benchmarks use games with a priced model selection and a market favorite.</p>")
    out.append(spread_headline(latest))
    for yr in reversed(seasons):
        g = retro[retro.season == yr].sort_values(["week", "game_id"], ascending=[False, True])
        units = g.units.dropna()
        rows = [[f"<span class='mono'>W{int(x.week)}</span>", f"<span class='team-code'>{esc(x.away)} @ {esc(x.home)}</span>",
                 pick_text(x.bet_team, x.bet_price), score_text(getattr(x, "away_score", math.nan), getattr(x, "home_score", math.nan)),
                 result_badge(x.bet_result if isinstance(x.bet_result, str) else "")] for x in g.itertuples(index=False)]
        w, l = int((g.bet_result == "W").sum()), int((g.bet_result == "L").sum())
        summ = (f"{yr} · {w}-{l} <span class='rt'>ROI {roi_short(units.mean())}</span>" if len(units) else f"{yr} · no priced picks")
        spread = spread_record(latest, yr)
        if spread is not None:
            summ += f"<br><span class='mut'>Model spread · {spread_record_text(spread)}</span>"
        spread_data = latest.get('fixed_band_ledger', pd.DataFrame())
        lookup = ({r.game_id: r for r in spread_data[spread_data.season == yr].itertuples(index=False)}
                  if len(spread_data) else {})
        for cells, game in zip(rows, g.itertuples(index=False)):
            sr = lookup.get(game.game_id)
            if sr is not None and math.isfinite(num(sr.fixed_band_spread)):
                pick = (f'{esc(sr.fixed_band_ats_team)} {spread_text(sr.spread_line, sr.fixed_band_ats_side == "home")}'
                        if sr.fixed_band_ats_team else 'Skip')
                result = 'Skip' if sr.fixed_band_ats_result == 'S' else result_badge(sr.fixed_band_ats_result)
                cells.extend([pick, result, f'{sr.fixed_band_ats_units:+.2f}'])
            else:
                cells.extend(['—', '—', '—'])
        out.append(folded(summ, table(["Week", "Game", "Moneyline pick", "Final", "ML result",
                                       "Spread pick", "ATS result", "ATS units"], rows, num_cols=(3, 7))))
    return "".join(out)


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


def ats_comparison_tiles(frame, basis='Historical replay', title='ATS comparison'):
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
            tiles.append(stat(label, f'{wins}–{losses}–{pushes}',
                              f'{rate} covered · {returns.sum():+.2f}u · ROI {roi_short(returns.mean())}',
                              'model' if label == 'Model ATS' else ''))
        else:
            tiles.append(stat(label, '—', 'No compared games yet'))
    totals_note = ('The season total above includes pick’em games.' if basis == '2026 season total'
                   else 'All-season totals below include pick’em games.')
    return (f"<h3>{esc(title)}</h3><div class='gr-summary'>" + ''.join(tiles) + "</div>"
            "<p class='mut small'>Same completed games with a model ATS selection and a market favorite. "
            "Model skips and market pick’em games are excluded from all three records. "
            f"Cover rates exclude pushes; ROI includes pushes. {totals_note}</p>")


def render_fixed_bands(latest, details=False):
    d = latest.get('fixed_band_ledger', pd.DataFrame())
    pooled = latest.get('pooled_ats', pd.DataFrame())
    if d.empty and pooled.empty:
        return ''
    eligible = d[d.fixed_band_spread.notna() & d.result.notna() & d.spread_line.notna()] if len(d) else d
    current_season = int(latest['manifest']['season'])
    out = ["<h2 class='sec'>Spread performance</h2>"]
    if len(pooled) and season_ats.summary(pooled)['opportunities']:
        r = season_ats.summary(pooled)
        out.append("<h3>2026 graded results</h3><p class='mut small'>Season total: historical replay and recorded "
                   "ATS selections, with one result per game. Saved selections replace replay, including skips. "
                   f"{esc(pooled_basis_text(pooled))}. Returns use −110 pricing and 1-unit stakes.</p>")
        out.append(table(['Season', 'ATS W–L–P', 'Skips', 'Units', 'ROI'],
            [['2026', f'{r["wins"]}–{r["losses"]}–{r["pushes"]}', str(r['skips']),
              f'{r["units"]:+.2f}', roi_short(r['roi'])]], num_cols=(1, 2, 3, 4)))
        out.append(ats_comparison_tiles(pooled, '2026 season total', '2026 ATS comparison'))
        weeks = []
        for week, group in pooled.groupby('week', sort=True):
            v = season_ats.summary(group)
            weeks.append([f'W{int(week)}', f'{v["wins"]}–{v["losses"]}–{v["pushes"]}',
                          str(v['skips']), str(v['pending']), f'{v["units"]:+.2f}', roi_short(v['roi'])])
        out.append(folded('2026 · by week', table(['Week', 'ATS W–L–P', 'Skips', 'Pending', 'Units', 'ROI'],
                                                weeks, num_cols=(1, 2, 3, 4, 5)), True))
        out.append("<p class='mut small'><a href='ats_2026_results.csv'>2026 per-game ATS results</a>. "
                   "The download identifies replayed and recorded selections. A model spread equal to the line "
                   "takes the market favorite. Earlier recorded skips are backfilled as favorite bets and shown separately. "
                   "Cover rates exclude pushes; ROI includes pushed stakes and excludes skips.</p>")
    out.append("<h3>Historical replay</h3><div class='gr-note'>Returns use −110 pricing and fixed 1-unit stakes. "
               "A model spread equal to the market line takes the market favorite. Pushes return the stake.</div>")
    if eligible.empty:
        return ''.join(out) + "<p class='mut'>Historical spread results will appear when enough games are available.</p>"
    out.append(ats_comparison_tiles(eligible, title='Historical ATS comparison'))
    results = fixed_bands.summary(d).query("method == 'Fixed bands'")
    def result_rows(frame):
        return [[esc('All seasons' if r.season == 'All' else r.season),
                 f'{r.wins}–{r.losses}–{r.pushes}', str(r.skips), f'{r.units:+.2f}', roi_short(r.roi)]
                for r in frame.itertuples(index=False)]
    headers = ['Season', 'ATS W–L–P', 'Skips', 'Units', 'ROI']
    current = results[results.season == str(current_season)]
    if len(current) and pooled.empty:
        last_week=int(eligible.loc[eligible.season==current_season,'week'].max())
        out.append(f"<h3>{current_season} graded results</h3>"
                   f"<p class='mut small'>Historical replay of completed games this season, through week {last_week}.</p>")
        out.append(table(headers, result_rows(current), num_cols=(1, 2, 3, 4)))
    out.append("<h3>Per-season results · historical replay</h3>")
    out.append(table(headers, result_rows(results), num_cols=(1, 2, 3, 4)))
    out.append("<p class='mut small'><a href='fixed_band_ledger.csv'>Per-game ATS data</a> · "
               "<a href='fixed_band_summary.csv'>Season results</a>. "
               "Win and cover rates exclude pushes; ROI includes pushed stakes and excludes skipped games.</p>")
    if details:
        for year, g in eligible.groupby('season', sort=False):
            rows = []
            for r in g.sort_values(['week', 'game_id'], ascending=False).itertuples(index=False):
                rows.append([f'W{int(r.week)} · {esc(r.away)} @ {esc(r.home)}',
                             favorite_spread_text(r.fixed_band_spread, r.home, r.away),
                             favorite_spread_text(r.spread_line, r.home, r.away),
                             (f'{esc(r.fixed_band_ats_team)} {spread_text(r.spread_line, r.fixed_band_ats_side == "home")}'
                              if r.fixed_band_ats_team else 'Skip'),
                             'Skip' if r.fixed_band_ats_result == 'S' else result_badge(r.fixed_band_ats_result),
                             f'{r.fixed_band_ats_units:+.2f}'])
            label = 'graded results' if int(year) == current_season else 'retrospective results'
            out.append(folded(f'{int(year)} · model spread · {label}',
                             table(['Game', 'Model spread', 'Market', 'ATS pick', 'ATS result', 'Units'], rows),
                             int(year) == current_season))
    return ''.join(out)


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
    parts = [head('ATS performance', 'Compare ATS cover rates and returns on the same games. '
                  'Results use −110 pricing and 1-unit stakes.')]
    if latest is None:
        parts.append("<p class='mut'>No ATS results yet.</p>")
    else:
        parts.append(spread_headline(latest, int(latest['manifest']['season'])))
        parts.append(render_ats_basis(latest))
        parts.append(render_fixed_bands(latest))
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
    if latest is not None and len(latest['pooled_ats']):
        pooled = latest['pooled_ats']
        fields = ['game_id', 'season', 'week', 'home', 'away', 'ats_basis', 'ats_status',
                  'generated_utc', 'lock_at_utc', 'policy_version', 'fixed_band_spread',
                  'spread_line', 'result', 'fixed_band_ats_side', 'fixed_band_ats_team',
                  'fixed_band_ats_handicap', 'fixed_band_ats_result', 'fixed_band_ats_units']
        pooled.reindex(columns=fields).rename(columns={'fixed_band_spread': 'model_spread'}).to_csv(
            out / 'ats_2026_results.csv', index=False)
    else:
        (out / 'ats_2026_results.csv').unlink(missing_ok=True)
    if latest is not None and latest['ats_locks']:
        locked_rows = []
        for row in latest['ats_locks'].values():
            side = row['selected_side']
            locked_rows.append(dict(game_id=row['game_id'], season=row['season'],
                home=row['home'], away=row['away'], kickoff_utc=row['kickoff_utc'],
                forecast_utc=row['generated_utc'], lock_at_utc=row['lock_at_utc'],
                timing_policy='earlier archive' if row.get('legacy_lock') else '60 minutes before kickoff',
                model_spread=row['fixed_band_spread'], market_spread=row['market_spread'],
                selected_side=side, selected_team=row[side] if side else '',
                handicap=(-row['market_spread'] if side == 'home' else row['market_spread']) if side else None,
                skip_reason=row['skip_reason'], backfilled_favorite=ats_locks.backfilled(row)))
        pd.DataFrame(locked_rows).to_csv(out / 'ats_locked_picks.csv', index=False)
    else:
        (out / 'ats_locked_picks.csv').unlink(missing_ok=True)
    if latest is not None and 'fixed_band_ledger' in latest:
        exports = {'fixed_band_ledger.csv': latest['fixed_band_ledger'],
                   'fixed_band_summary.csv': fixed_bands.summary(latest['fixed_band_ledger']),
                   'fixed_band_board.csv': latest['board']}
        for name, frame in exports.items():
            frame.to_csv(Path(data) / 'latest' / name, index=False)
            if name == 'fixed_band_summary.csv':
                public = frame[frame.method == 'Fixed bands'].assign(method='Model spread')
            elif name == 'fixed_band_board.csv':
                public_rows = []
                for row in frame.to_dict('records'):
                    state = ats_card_state(latest, row, now)
                    item = {k: row.get(k) for k in ('game_id', 'season', 'week', 'home', 'away',
                            'gameday', 'gametime', 'away_score', 'home_score', 'result')}
                    item.update(model_spread=state['model_spread'], spread_line=state['spread_line'],
                        ats_status=state['status'], ats_source=state['source'],
                        selected_side=state['selected_side'], selected_team=state['selected_team'],
                        handicap=state['handicap'], ats_result=state['result'], ats_units=state['units'])
                    public_rows.append(item)
                public = pd.DataFrame(public_rows)
            else:
                fields = ['game_id', 'season', 'week', 'home', 'away', 'gameday', 'away_score', 'home_score',
                          'result', 'spread_line', 'fixed_band_spread', 'fixed_band_ats_side',
                          'fixed_band_ats_team', 'fixed_band_ats_handicap', 'fixed_band_ats_result',
                          'fixed_band_ats_units']
                public = frame.reindex(columns=fields)
                public = public.rename(columns={'fixed_band_spread': 'model_spread'})
            public.to_csv(out / name, index=False)
        rules = json.dumps(latest['fixed_band_rules'], indent=2, allow_nan=False)
        (Path(data) / 'latest' / 'fixed_band_rules.json').write_text(rules)
        (out / 'fixed_band_rules.json').write_text(rules)
    pages = {"index.html": render_index(latest, ledger, built, now),
             "grades.html": render_grades(ledger, latest, built),
             "market-calibration.html": render_calibration(latest, ledger, built)}
    for name, html in pages.items():
        (out / name).write_text(html, encoding="utf-8")
    # Repository-only analyst report. Do not publish a second research surface.
    report_path = Path(data) / 'ledger_report.txt'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(published_report(Path(data)), encoding='utf-8')
    for retired in ('ledger_report.txt', 'model.html', 'board.html'):
        (out / retired).unlink(missing_ok=True)
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
