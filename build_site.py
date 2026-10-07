#!/usr/bin/env python3
"""Build the NFL model site: run the model, snapshot its outputs into data/,
grade the forward ledger, and render static pages into public/.

    python build_site.py               # full build (what build.yml runs)
    python build_site.py --pages-only  # re-render from committed data/ only

Pages
  index.html               this week's projections (model vs market, flags, drivers)
  grades.html              forward ledger: first pregame snapshots, graded
  market-calibration.html  model vs market calibration and pick records in matched bands
  model.html               recipe, held-out scorecards, coefficients, limitations
  board.html               the model's own detailed board for the week

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
import nfl_model as m

DATA = Path("data")
LATEST = DATA / "latest"
PROJECTIONS = DATA / "projections"
ASSETS = Path("assets/fonts")
ET = ZoneInfo("America/New_York")
SITE_NAME = "NFL Box-Score Composite"

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
    "season_roi.csv": "season_roi.csv",
    "retro_ledger.csv": "retro_ledger.csv",
    "retro_roi_by_season.csv": "retro_roi_by_season.csv",
    "retro_roi_bands.csv": "retro_roi_bands.csv",
    "candidate_roi.csv": "candidate_roi.csv",
    "report_notes.csv": "report_notes.csv",
}
BOARD_COLS = ["game_id", "season", "week", "away", "home", "gameday", "gametime", "site",
              "result", "away_score", "home_score", "home won", "ready", "spread_line",
              "home_moneyline", "away_moneyline",
              "market_wp", "model_wp", "homefield_wp", "composite_log_odds", "recipe",
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
}}
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
.gr-stat .v.good{color:rgb(var(--good))}.gr-stat .v.bad{color:rgb(var(--bad))}
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
  border:1px solid var(--line);background:var(--surface-2);font:800 13px/1 var(--mono)}
.club{min-width:0}
.club .nm{font:750 16.5px/1.15 var(--sans);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.club .wp{font:800 22px/1.1 var(--mono);font-variant-numeric:tabular-nums}
.club .wp.fav{color:rgb(var(--lean-tx))}
.mid{display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center}
.mid .t{font:800 15px/1 var(--mono)}
.mid .mk{font:600 12.5px/1.2 var(--mono);color:var(--muted)}
.chev{position:absolute;right:14px;top:50%;transform:translateY(-50%);color:var(--faint);font:800 18px/1 var(--sans)}
.card[open] .chev{transform:translateY(-50%) rotate(180deg);color:var(--ink)}
.flags{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:9px}
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
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted);margin:2px 2px 10px}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:var(--r-s);margin-right:6px;vertical-align:-1px}
.chart{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:10px;margin-bottom:12px}
.chart svg{display:block;width:100%;height:auto;max-width:560px;margin:0 auto}
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

PAGES = (("index.html", "Projections"), ("grades.html", "Ledger"),
         ("market-calibration.html", "Market calibration"), ("model.html", "Model"),
         ("board.html", "Full board"))


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


def html_document(body, title, current, built, has_board=True):
    nav = "".join(f"<a href='{href}'{' aria-current=\"page\"' if href == current else ''}>{label}</a>"
                  for href, label in PAGES if has_board or href != "board.html")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><meta name='description' content='NFL box-score composite win probabilities, forward ledger and market calibration'>"
            f"{THEME_JS}<style>{font_face_css()}{CSS}</style></head><body><div class='mx-wrap'>"
            f"<div class='topbar'><a class='brand' href='index.html'>{SITE_NAME}</a>"
            "<button class='theme' type='button' onclick='toggleTheme()' aria-label='Toggle colour theme'>Theme</button></div>"
            f"<nav class='nav'>{nav}</nav>{body}"
            f"<div class='foot'>Built <span class='stamp'>{esc(built)}</span>. Win probabilities from prior-game "
            "box-score profiles and player availability; the market is a benchmark only and never enters the model. "
            "Not betting advice.</div></div></body></html>")


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

def kickoff_text(r):
    ko = m.kickoff_utc(r)
    return ko.astimezone(ET).strftime("%a %-I:%M %p ET") if ko else "TBD"


def ledger_summary(ledger, revision=None):
    g = ledger if revision is None else ledger[ledger.revision == revision]
    return grade_ledger.summary(g) if len(g) else grade_ledger.summary(pd.DataFrame(columns=grade_ledger.COLUMNS))


def ml_text(ml):
    ml = num(ml)
    return "—" if not math.isfinite(ml) else f"{ml:+.0f}".replace("-", "−")


def roi_text(roi, se=math.nan):
    if not math.isfinite(num(roi)):
        return "—"
    out = f"{100 * roi:+.1f}%"
    return out + (f" ± {100 * se:.1f}" if math.isfinite(num(se)) else "")


def roi_tile(label, r, basis):
    """Headline tile: 1u flat ROI on the model's side, market favorite on the same rows."""
    if not r or not r.get("bets"):
        return stat(label, "—", f"no graded bets yet · {basis}")
    tone = "good" if r["roi"] > 0 else "bad"
    se = num(r.get("roi_se"))
    sub = (f"{r['units']:+.2f}u · {int(r['wins'])}-{int(r['losses'])}{'-' + str(int(r['pushes'])) if r['pushes'] else ''}"
           f"{f' · ± {100 * se:.1f} SE' if math.isfinite(se) else ''}<br>market fav {roi_text(r.get('fav_roi'))} · {basis}")
    return stat(label, f"{100 * r['roi']:+.1f}%", sub, tone)


def roi_from_table(t, group="All games"):
    """Model row of a roi_table frame with the market-favorite ROI attached."""
    if t is None or t.empty or "group" not in t:
        return None
    g = t[t.group.astype(str) == group]
    if g.empty:
        return None
    r = g[g.source == "model"].iloc[0].to_dict()
    k = g[g.source == "market favorite"]
    r["fav_roi"] = float(k.roi.iloc[0]) if len(k) else math.nan
    return r


def roi_band_table(t, by_label="Picked price"):
    """Rows of a roi_table frame: model and same-row market favorite side by side."""
    rows = []
    for gi, g in t.groupby("group_index"):
        m_ = g[g.source == "model"].iloc[0]
        k_ = g[g.source == "market favorite"].iloc[0]
        if not m_.bets and m_.group != "All games":
            continue
        rows.append({"cells": [esc(m_.group), f"{int(m_.bets)}",
                               f"{int(m_.wins)}-{int(m_.losses)}{'-' + str(int(m_.pushes)) if m_.pushes else ''}",
                               f"{m_.units:+.2f}" if m_.bets else "—", roi_text(m_.roi, m_.roi_se),
                               pct(m_.mean_q, 1), f"{m_.excess_pp:+.1f}" if math.isfinite(num(m_.excess_pp)) else "—",
                               roi_text(m_.null_roi), f"{k_.units:+.2f}" if k_.bets else "—", roi_text(k_.roi)],
                     "_class": "total" if m_.group == "All games" else ""})
    return table([by_label, "Bets", "W-L", "Units", "ROI ± SE", "No-vig q", "Excess pp", "Mkt null", "Fav units", "Fav ROI"],
                 rows, num_cols=(1, 2, 3, 4, 5, 6, 7, 8, 9))


ROI_NOTE = ("<div class='gr-note'><b>Flat 1u.</b> One unit on the side the model makes the favorite, every game it decides, "
            "at that side's posted moneyline. <b>No-vig q</b> is the market's probability for the picked side with the hold "
            "removed; <b>excess</b> is the win rate minus q. <b>Mkt null</b> is the ROI expected if the market were exactly "
            "right — negative by the hold, so beating it is the bar, not zero. <b>Fav</b> bets the market favorite on the "
            "same games. ± is one standard error; bands are descriptive, not a betting filter.</div>")


def ledger_tiles(ledger, revision):
    sm = ledger_summary(ledger, revision)
    tiles = [roi_tile("Flat 1u ROI · forward", sm["roi"], "locked snapshots")]
    if sm["scored"]:
        tone = "good" if sm["ll_gain"] > 0 else "bad"
        se = sm["ll_gain_se"]
        tiles.append(stat("Log loss vs market", f"{sm['ll_gain']:+.3f}",
                          f"± {se:.3f} SE · model {sm['model_log_loss']:.3f} / mkt {sm['market_log_loss']:.3f}"
                          if math.isfinite(se) else f"model {sm['model_log_loss']:.3f} / mkt {sm['market_log_loss']:.3f}", tone))
    tiles.append(stat("Forward snapshots", f"{sm['snapshots']}",
                      f"{sm['graded']} graded · {sm['pending']} pending · {sm['ties']} ties"))
    return tiles, sm


def reliability_svg(cal, title):
    """Mean forecast (x) vs realized home-win rate (y) per band, one series per source."""
    if cal is None or cal.empty:
        return ""
    W, H, P = 520, 360, 46
    x = lambda v: P + (W - 2 * P) * v / 100
    y = lambda v: H - P - (H - 2 * P) * v / 100
    parts = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='{esc(title)}'>",
             f"<rect x='{P}' y='{P}' width='{W - 2 * P}' height='{H - 2 * P}' fill='none' stroke='var(--line)'/>"]
    for t in (0, 25, 50, 75, 100):
        parts.append(f"<line x1='{x(t)}' y1='{y(0)}' x2='{x(t)}' y2='{y(100)}' stroke='var(--line-2)'/>"
                     f"<line x1='{x(0)}' y1='{y(t)}' x2='{x(100)}' y2='{y(t)}' stroke='var(--line-2)'/>"
                     f"<text x='{x(t)}' y='{H - P + 16}' text-anchor='middle' font-size='11' fill='var(--faint)' font-family='var(--mono)'>{t}</text>"
                     f"<text x='{P - 8}' y='{y(t) + 4}' text-anchor='end' font-size='11' fill='var(--faint)' font-family='var(--mono)'>{t}</text>")
    parts.append(f"<line x1='{x(0)}' y1='{y(0)}' x2='{x(100)}' y2='{y(100)}' stroke='var(--faint)' stroke-dasharray='4 4'/>")
    for src, color, dx in (("market", "rgb(var(--warm))", 3), ("model", "rgb(var(--cool))", -3)):
        s = cal[(cal.source == src) & (cal.games > 0)].sort_values("band_index")
        pts = [(x(float(r["mean forecast %"])) + dx, y(float(r["realized home win %"]))) for _, r in s.iterrows()]
        if len(pts) > 1:
            parts.append(f"<polyline points='{' '.join(f'{a:.1f},{b:.1f}' for a, b in pts)}' fill='none' stroke='{color}' stroke-width='1.5' opacity='.6'/>")
        for (_, r), (a, b) in zip(s.iterrows(), pts):
            lo, hi = y(float(r["realized CI low %"])), y(float(r["realized CI high %"]))
            rad = 3 + min(6, math.sqrt(float(r["games"])) / 3)
            parts.append(f"<line x1='{a:.1f}' y1='{lo:.1f}' x2='{a:.1f}' y2='{hi:.1f}' stroke='{color}' opacity='.45'/>"
                         f"<circle cx='{a:.1f}' cy='{b:.1f}' r='{rad:.1f}' fill='{color}'><title>{esc(src)} {esc(r['band'])}: "
                         f"{int(r['games'])} games, forecast {float(r['mean forecast %']):.1f}%, realized {float(r['realized home win %']):.1f}%</title></circle>")
    parts.append(f"<text x='{W / 2}' y='{H - 8}' text-anchor='middle' font-size='12' fill='var(--muted)'>Mean forecast home win %</text>"
                 f"<text x='14' y='{H / 2}' text-anchor='middle' font-size='12' fill='var(--muted)' transform='rotate(-90 14 {H / 2})'>Realized home win %</text></svg>")
    legend = ("<div class='legend'><span><i class='sw' style='background:rgb(var(--cool))'></i>Model</span>"
              "<span><i class='sw' style='background:rgb(var(--warm))'></i>Market (spread-implied)</span>"
              "<span>Dashed: perfect calibration · bars: Wilson 95% · dot size: games</span></div>")
    return legend + f"<div class='chart'>{''.join(parts)}</div>"


def calibration_table(cal):
    rows = []
    for i, g in cal.groupby("band_index"):
        cells = [f"<span class='team-code'>{esc(g.band.iloc[0])}</span>"]
        for src in ("model", "market"):
            r = g[g.source == src].iloc[0]
            if r.games:
                off = " <span class='badge warn'>off</span>" if bool(r["forecast outside CI"]) else ""
                cells += [f"{int(r.games)}", f"{r['mean forecast %']:.1f}%",
                          f"{r['realized home win %']:.1f}% <span class='mut'>({r['realized CI low %']:.0f}–{r['realized CI high %']:.0f})</span>{off}"]
            else:
                cells += ["0", "—", "—"]
        rows.append(cells)
    return table(["Home-win band", "Model n", "Model fcst", "Realized", "Market n", "Market fcst", "Realized"],
                 rows, num_cols=(1, 2, 3, 4, 5, 6))


def records_table(recs):
    rows = []
    for i, g in recs.groupby("band_index"):
        cells = [esc(g.band.iloc[0])]
        for src in ("model", "market"):
            r = g[g.source == src].iloc[0]
            if r.games:
                cells += [f"<b>{esc(r.record)}</b>", f"{r['avg pick prob %']:.1f}%",
                          f"{r['realized pick win %']:.1f}% <span class='mut'>({r['CI low %']:.0f}–{r['CI high %']:.0f})</span>"]
            else:
                cells += ["0-0", "—", "—"]
        rows.append({"cells": cells, "_class": "total" if g.band.iloc[0] == "All picks" else ""})
    return table(["Pick confidence", "Model W-L", "Avg prob", "Won", "Market W-L", "Avg prob", "Won"],
                 rows, num_cols=(1, 2, 3, 4, 5, 6))


# ---------------------------------------------------------------- pages

def render_index(latest, ledger, built, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if latest is None or latest["board"].empty:
        body = head("Projections", "No model run has been published yet; the first build writes this page.")
        return html_document(body, f"{SITE_NAME} projections", "index.html", built, has_board=False)
    man, board = latest["manifest"], latest["board"].copy()
    rev, season, week = man["revision"], int(man["season"]), int(man["week"])
    recipe = man.get("recipe") or {}
    fam = recipe.get("family", "")
    has_avail = fam in m.AVAIL_FAMILIES
    recorded = {}
    cur = ledger[ledger.revision == rev] if len(ledger) else ledger
    for r in cur.itertuples(index=False):
        recorded[r.game_id] = r
    generated = man.get("generated_utc", "")
    lead = (f"Week {week}, {season}. Home-win probabilities from the frozen recipe "
            f"<span class='mono'>{esc(m.recipe_key(recipe)) if recipe else ''}</span>, refit on every earlier game. "
            f"Model run <span class='stamp'>{esc(generated[:16].replace('T', ' '))} UTC</span>.")
    tiles, _ = ledger_tiles(ledger, rev)
    tiles.insert(1, roi_tile("Flat 1u ROI · held-out", roi_from_table(latest["roi_bands"]), "reconstructed seasons"))
    tiles.insert(2, roi_tile("Flat 1u ROI · rebuilt history", roi_from_table(latest["retro_roi_bands"]),
                             "chosen recipe, hindsight"))
    parts = [head(f"Week {week} projections", lead), f"<div class='gr-summary'>{''.join(tiles)}</div>"]

    def pending(r):
        ko = m.kickoff_utc(r)
        return (has_avail and pd.isna(r.get("result")) and ko is not None and ko > now
                and not m.injury_reports_ready(r, ko, now))

    rows = board.to_dict("records")
    n_pend = sum(1 for r in rows if pending(r))
    if n_pend:
        parts.append(f"<div class='gr-note flag-note'><b>Injury reports not final for {n_pend} upcoming "
                     f"game{'s' if n_pend != 1 else ''}.</b> Game statuses publish Friday (Wednesday for Thursday games). "
                     "Until then unlisted players count as healthy, and those games wait out of the forward ledger.</div>")
    far = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    rows.sort(key=lambda r: (pd.notna(r.get("result")), m.kickoff_utc(r) or far, str(r["game_id"])))
    contrib = latest["contributions"]
    cmax = float(contrib["log-odds contribution"].abs().max()) if len(contrib) else 1.
    cards = []
    for r in rows:
        p, q = num(r["model_wp"]), num(r.get("market_wp"))
        home, away = r["home"], r["away"]
        fav_home = p > .5
        gap = 100 * (p - q) if math.isfinite(q) else math.nan
        flags = []
        if pd.notna(r.get("result")):
            y = m.won(r["result"])
            hit = None if y == .5 or math.isclose(p, .5) else ((p > .5) == (y == 1))
            flags.append(f"<span class='badge'>Final {int(num(r.get('away_score')))}–{int(num(r.get('home_score')))}</span>")
            if hit is not None:
                flags.append(f"<span class='badge {'w' if hit else 'l'}'>Model {'hit' if hit else 'miss'}</span>")
        else:
            if math.isfinite(gap) and abs(gap) >= m.FLAG_GAP_PP:
                flags.append(f"<span class='badge lean'>{abs(gap):.0f} pts off market</span>")
            if pending(r):
                flags.append("<span class='badge warn'>Report pending</span>")
            if r["game_id"] in recorded:
                flags.append("<span class='badge'>In ledger</span>")
            if not bool(r.get("ready", True)):
                flags.append("<span class='badge'>Limited history</span>")
        for side in ("away", "home"):
            e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
            if isinstance(e, str) and isinstance(u, str) and e != u:
                flags.append(f"<span class='badge warn'>{esc(r[side])} QB: {esc(e)}</span>")
        hm, am = num(r.get("home_moneyline")), num(r.get("away_moneyline"))
        if math.isfinite(hm) and math.isfinite(am):
            mk = f"{esc(away)} {ml_text(am)} · {esc(home)} {ml_text(hm)}"
        else:
            mk = f"Market {pct(q)} home" if math.isfinite(q) else "No market line"
        bet = m.flat_bets(pd.DataFrame([r]), "model_wp").iloc[0]
        if bet.side and math.isfinite(num(bet.price)):
            team = home if bet.side == "home" else away
            if pd.isna(r.get("result")):
                flags.insert(0, f"<span class='badge lean'>Bet {esc(team)} {ml_text(bet.price)}</span>")
            elif bet.result in ("W", "L", "P"):
                flags.insert(2, f"<span class='badge {'w' if bet.result == 'W' else 'l' if bet.result == 'L' else ''}'>"
                                f"{esc(team)} {ml_text(bet.price)} {bet.units:+.2f}u</span>")

        def side_html(code, wp, fav, cls):
            name = TEAM_NAMES.get(code, code)
            club = (f"<div class='club'><div class='nm'>{esc(name)}</div>"
                    f"<div class='wp{' fav' if fav else ''}'>{pct(wp)}</div></div>")
            chip = f"<div class='chip'>{esc(code)}</div>"
            return f"<div class='side {cls}'>{chip + club if cls == 'away' else club + chip}</div>"

        summary = (f"<summary class='game-summary'><div class='teams'>"
                   f"{side_html(away, 1 - p, not fav_home and not math.isclose(p, .5), 'away')}"
                   f"<div class='mid'><div class='t'>{esc(kickoff_text(r))}</div><div class='mk'>{mk}</div></div>"
                   f"{side_html(home, p, fav_home, 'home')}</div>"
                   f"<div class='probbar' aria-hidden='true'><i class='a' style='width:{100 * (1 - p):.1f}%'></i>"
                   f"<i class='h' style='width:{100 * p:.1f}%'></i></div>"
                   f"{f'<div class=flags>{chr(10).join(flags)}</div>' if flags else ''}<span class='chev'>⌄</span></summary>")
        det = ["<div class='detail'>"]
        det.append(table(["", esc(away), esc(home)], [
            ["Model", pct(1 - p, 1), pct(p, 1)],
            ["Market (spread-implied)", pct(1 - q, 1) if math.isfinite(q) else "—", pct(q, 1) if math.isfinite(q) else "—"],
            ["Home-field baseline", pct(1 - num(r.get("homefield_wp")), 1), pct(num(r.get("homefield_wp")), 1)],
            ["Moneyline", ml_text(r.get("away_moneyline")), ml_text(r.get("home_moneyline"))],
            ["No-vig market (moneyline)", pct(1 - num(m.market_ml_wp(pd.DataFrame([r]))[0]), 1),
             pct(num(m.market_ml_wp(pd.DataFrame([r]))[0]), 1)],
        ], num_cols=(1, 2)))
        rec = recorded.get(r["game_id"])
        if rec is not None:
            det.append(f"<p class='mut'>Ledger snapshot {esc(str(rec.generated_utc)[:16].replace('T', ' '))} UTC "
                       f"({num(rec.lead_hours):.0f}h before kickoff): model {pct(rec.model_wp, 1)} home.</p>")
        t = contrib[contrib.game_id == r["game_id"]] if len(contrib) else contrib
        if len(t):
            t = t.loc[t["log-odds contribution"].abs().sort_values(ascending=False).index].head(6)
            det.append("<h3>Largest drivers</h3>")
            trs = []
            for c in t.to_dict("records"):
                v = float(c["log-odds contribution"]); w = 50 * abs(v) / max(cmax, 1e-9)
                style = f"left:50%;width:{w:.1f}%" if v > 0 else f"right:50%;width:{w:.1f}%"
                trs.append([esc(m.feature_label(c["feature"])),
                            f"<div class='cbar'><i class='{'pos' if v > 0 else 'neg'}' style='{style}'></i></div>",
                            f"{v:+.3f}", esc(home if v > 0 else away if v < 0 else "—")])
            det.append(table(["Feature", f"← {esc(away)} · {esc(home)} →", "Log-odds", "Toward"], trs, num_cols=(2,)))
        if has_avail:
            cols = m.AVAIL_FAMILY_COLS.get(fam, ())
            arows = [[esc(m.AVAIL_LABEL.get(c, c)),
                      _fmt_avail(c, r.get(f"away__avail__{c}")), _fmt_avail(c, r.get(f"home__avail__{c}"))] for c in cols]
            arows.insert(0, ["Projected QB (usual)", _qb(r, "away"), _qb(r, "home")])
            arows.insert(1, ["Injury report", esc(r.get("away_injury_report") or "none"), esc(r.get("home_injury_report") or "none")])
            det.append("<h3>Availability</h3>" + table(["", esc(away), esc(home)], arows, num_cols=(1, 2)))
            det.append(report_notes_html(latest.get("report_notes"), (away, home), int(r["week"])))
        det.append("</div>")
        cards.append(f"<details class='card'>{summary}{''.join(det)}</details>")
    parts.append(f"<div class='grid'>{''.join(cards)}</div>")
    return html_document("".join(parts), f"{SITE_NAME} — week {week}", "index.html", built, latest.get("board_html", False))


STATE_TEXT = {
    "none": "Week {w} report not published yet. Players listed last week are counted as available until it is "
            "(final statuses come Friday; Wednesday for Thursday games). Roster moves (IR, PUP, cut, traded) count in full now.",
    "practice": "Week {w} practice report only: no game statuses yet, so listed players are still counted as available. "
                "Roster moves (IR, PUP, cut, traded) count in full.",
    "final": "Week {w} final report: the statuses below are what the model counts (Out/Doubtful 100%, Questionable 25%).",
}


def report_notes_html(notes, teams, week):
    """Per-team injury-report notes: what the reports say and what the model counts now."""
    if notes is None or notes.empty:
        return ""
    out = ["<h3>Injury report notes</h3>"]
    for t in teams:
        n = notes[notes.team == t]
        state = n.report_state.iloc[0] if len(n) else None
        if n.empty:
            continue
        rows = []
        for x in n.itertuples(index=False):
            prev = ""
            if isinstance(x.prev_status, str) and x.prev_status:
                inj = f" ({esc(x.prev_injury)})" if isinstance(x.prev_injury, str) and x.prev_injury else ""
                prev = f"{esc(x.prev_status)}{inj} · wk {int(num(x.prev_week))}"
            counted = num(x.counted)
            rows.append([f"{esc(x.player)} <span class='mut'>{esc(x.position)}</span>",
                         f"{100 * num(x.snap_share):.0f}% <span class='mut'>{esc(x.unit)}</span>",
                         prev or "—", esc(x.this_week),
                         f"{100 * counted:.0f}%" if math.isfinite(counted) else "—"])
        out.append(f"<p class='mut'><b>{esc(t)}</b> · {esc(STATE_TEXT.get(state, '').format(w=week))}</p>"
                   + table(["Player", "Share of unit snaps", "Last report", f"Week {week}", "Counted out"], rows,
                           num_cols=(1, 4)))
    return "".join(out) if len(out) > 1 else ""


def _fmt_avail(c, v):
    v = num(v)
    if not math.isfinite(v):
        return "—"
    return f"{v:+.2f}" if c == "qb_delta" else f"{100 * v:.0f}%"


def _qb(r, side):
    e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
    if not isinstance(e, str):
        return "—"
    return esc(e) + (f" <span class='mut'>({esc(u)})</span>" if isinstance(u, str) and u != e else "")


def render_grades(ledger, latest, built):
    rev = latest["manifest"]["revision"] if latest else (ledger.revision.iloc[0] if len(ledger) else m.REVISION)
    lead = ("Each game's <b>first</b> pregame snapshot, written before kickoff once both teams' injury reports "
            "carry game statuses, then graded against the final score. Snapshots are never revised; a new model "
            "revision starts a new experiment. Native forward observations only — no reconstructed rows.")
    parts = [head("Forward ledger", lead)]
    tiles, sm = ledger_tiles(ledger, rev)
    parts.append(f"<div class='gr-summary'>{''.join(tiles)}</div>")
    parts.append(f"<div class='gr-note'>Tiles score <b>{esc(rev)}</b>. <b>ROI</b> grades 1u on the model's side at the "
                 "moneyline saved in the snapshot (the line at lock time, not necessarily the close). Log loss gain is "
                 "market minus model per game on graded games (positive: model better), against the spread-implied "
                 "probability from the same snapshot. ± is one standard error.</div>")
    if ledger.empty:
        parts.append("<div class='gr-note'>No snapshots yet. The first lands on the first build after "
                     "a week's final injury reports publish.</div>")
    else:
        cur = ledger[ledger.revision == rev]
        bands = grade_ledger.roi_bands(cur)
        if int(bands.bets.iloc[-1]):
            t = pd.concat([bands.assign(source="model"),
                           bands.assign(source="market favorite", units=bands.fav_units, roi=bands.fav_roi,
                                        bets=bands.bets)], ignore_index=True)
            t["group_index"] = t.groupby("source").cumcount()
            parts.append("<h2 class='sec'>Flat 1u ROI by price band</h2>" + roi_band_table(t) + ROI_NOTE)
        s = grade_ledger.scored_frame(cur)
        if len(s):
            parts.append("<h2 class='sec'>Pick records by confidence</h2>" + records_table(m.band_records(s)))
        rows = []
        for r in ledger.itertuples(index=False):
            ko = pd.to_datetime(r.kickoff_utc, utc=True).tz_convert(ET).strftime("%a %b %-d %-I:%M %p")
            if r.status == "graded":
                res = f"{int(r.away_score)}–{int(r.home_score)}"
                mh = f"<span class='badge {'w' if r.model_hit == 1 else 'l'}'>{'W' if r.model_hit == 1 else 'L'}</span>" if pd.notna(r.model_hit) else "—"
                kh = f"<span class='badge {'w' if r.market_hit == 1 else 'l'}'>{'W' if r.market_hit == 1 else 'L'}</span>" if pd.notna(r.market_hit) else "—"
                d = num(r.market_log_loss) - num(r.model_log_loss)
                dl = f"{d:+.3f}" if math.isfinite(d) else "—"
            else:
                res, mh, kh, dl = f"<span class='badge'>{esc(r.status)}</span>", "", "", ""
            units = num(getattr(r, "units", math.nan))
            ut = f"{units:+.2f}" if math.isfinite(units) else ""
            bt = f"{esc(r.bet_team)} {ml_text(r.bet_price)}" if isinstance(getattr(r, "bet_team", None), str) and r.bet_team else "—"
            rows.append([f"<span class='mono'>{int(r.season)} W{int(r.week)}</span>",
                         f"<span class='team-code'>{esc(r.away)} @ {esc(r.home)}</span><div class='mut' style='font-size:12px'>{esc(ko)} ET</div>",
                         f"{num(r.lead_hours):.0f}h", pct(r.model_wp, 1), pct(r.market_wp, 1), bt,
                         res, mh, ut, kh, dl, f"<span class='mut' style='font-size:12px'>{esc(str(r.revision).replace('boxscore-composite-', ''))}</span>"])
        parts.append("<h2 class='sec'>All snapshots</h2>" + table(
            ["Week", "Game", "Lead", "Model home", "Market home", "Bet (1u)", "Final", "Model", "Units", "Market", "LL gain", "Rev"],
            rows, num_cols=(2, 3, 4, 8, 10)))
    if latest is not None:
        parts.append(render_retro(latest))
    return html_document("".join(parts), f"{SITE_NAME} ledger", "grades.html", built, bool(latest and latest.get("board_html")))


def render_retro(latest):
    """The chosen recipe graded on every backtest game: the MLB site's rebuilt history."""
    retro = latest.get("retro_ledger")
    if retro is None or retro.empty:
        return ""
    key = m.recipe_key(latest["manifest"].get("recipe") or {}) if latest["manifest"].get("recipe") else ""
    seasons = sorted(int(x) for x in retro.season.unique())
    out = [f"<h2 class='sec'>Rebuilt history · chosen recipe · reconstructed</h2>",
           f"<div class='gr-note flag-note'><b>Hindsight, not a track record.</b> The current recipe "
           f"<span class='mono'>{esc(key)}</span> graded as flat 1u moneyline bets on every game since {seasons[0]}. "
           "Each prediction comes from coefficients refit before its week on earlier games only, but the recipe "
           "was chosen using these same seasons, and features use today's upstream data. The forward ledger above "
           "is the native record; the held-out seasons (Model page) choose each season's recipe from earlier seasons only. "
           "Prices are the nflverse schedule moneylines.</div>"]
    r = roi_from_table(latest["retro_roi_bands"])
    tiles = [roi_tile("Flat 1u ROI · rebuilt", r, f"{seasons[0]}–{seasons[-1]}")]
    if r and r.get("bets"):
        tiles.append(stat("Win rate vs market", f"{100 * r['win_pct']:.1f}%",
                          f"no-vig q {100 * r['mean_q']:.1f}% · excess {r['excess_pp']:+.1f}pp"))
        tiles.append(stat("Market-correct null", roi_text(r["null_roi"]), "expected ROI if the market were right"))
    out.append(f"<div class='gr-summary'>{''.join(tiles)}</div>")
    if len(latest["retro_roi_by_season"]):
        out.append("<h2 class='sec'>Rebuilt history by season</h2>" + roi_band_table(latest["retro_roi_by_season"], "Season"))
    if len(latest["retro_roi_bands"]):
        out.append("<h2 class='sec'>Rebuilt history by price band</h2>" + roi_band_table(latest["retro_roi_bands"]) + ROI_NOTE)
    out.append("<h2 class='sec'>Rebuilt games</h2>")
    for i, yr in enumerate(reversed(seasons)):
        g = retro[retro.season == yr].sort_values(["week", "game_id"], ascending=[False, True])
        units = g.units.dropna()
        rows = []
        for x in g.itertuples(index=False):
            res = x.bet_result if isinstance(x.bet_result, str) and x.bet_result else ""
            badge = (f"<span class='badge {'w' if res == 'W' else 'l' if res == 'L' else ''}'>{res}</span>" if res else "—")
            sc = (f"{int(x.away_score)}–{int(x.home_score)}" if math.isfinite(num(getattr(x, "away_score", math.nan)))
                  and math.isfinite(num(getattr(x, "home_score", math.nan))) else "")
            rows.append([f"<span class='mono'>W{int(x.week)}</span>",
                         f"<span class='team-code'>{esc(x.away)} @ {esc(x.home)}</span>", pct(x.model_wp, 1),
                         pct(getattr(x, "market_ml_wp", math.nan), 1),
                         f"{esc(x.bet_team)} {ml_text(x.bet_price)}" if isinstance(x.bet_team, str) and x.bet_team else "—",
                         sc, badge, f"{num(x.units):+.2f}" if math.isfinite(num(x.units)) else "—"])
        summ = (f"{yr} · {len(units)} bets · {units.sum():+.2f}u · ROI {roi_text(units.mean())}"
                if len(units) else f"{yr} · no priced bets")
        out.append(f"<details{' open' if i == 0 else ''} style='margin-bottom:10px'><summary style='cursor:pointer;"
                   f"font:700 14px/1.4 var(--sans);padding:6px 2px'>{esc(summ)}</summary>"
                   + table(["Week", "Game", "Model home", "Market home (no-vig)", "Bet (1u)", "Final", "Result", "Units"],
                           rows, num_cols=(2, 3, 7)) + "</details>")
    return "".join(out)


def render_calibration(latest, ledger, built):
    lead = ("Flat 1u ROI at the moneyline by price band, then model and market binned on the <b>same</b> home-win "
            "probability bands and compared with what happened. "
            "Each source's picks are also binned on the same confidence bands. Two bases, never pooled: native "
            "forward snapshots, and held-out walk-forward reconstructions.")
    parts = [head("Model–market calibration", lead)]
    rev = latest["manifest"]["revision"] if latest else m.REVISION
    s = grade_ledger.scored_frame(ledger[ledger.revision == rev]) if len(ledger) else pd.DataFrame()
    parts.append(f"<h2 class='sec'>Forward ledger · {esc(rev)}</h2>")
    if len(s):
        cal = m.calibration_bands(s)
        parts.append(reliability_svg(cal, "Forward ledger calibration") + calibration_table(cal))
    else:
        parts.append("<div class='gr-note'>No graded forward snapshots yet for this revision.</div>")
    if latest is not None and len(latest["calibration_bands"]):
        n = int(latest["calibration_bands"].query("source=='model'").games.sum())
        parts.append(f"<h2 class='sec'>Held-out seasons · reconstructed ({n} games)</h2>")
        parts.append("<div class='gr-note'>Walk-forward predictions for seasons whose recipe was chosen only from "
                     "earlier seasons. Useful for calibration shape; not forward evidence — the design was revised "
                     "after these seasons were seen.</div>")
        if len(latest["roi_bands"]):
            parts.append("<h2 class='sec'>Flat 1u ROI by price band · reconstructed</h2>" + roi_band_table(latest["roi_bands"]) + ROI_NOTE)
        parts.append("<h2 class='sec'>Calibration · reconstructed</h2>"
                     + reliability_svg(latest["calibration_bands"], "Held-out calibration") + calibration_table(latest["calibration_bands"]))
        if len(latest["band_records"]):
            parts.append("<h2 class='sec'>Pick records by confidence · reconstructed</h2>" + records_table(latest["band_records"]))
        verdict = latest["manifest"].get("market_blend_verdict")
        if verdict:
            parts.append(f"<div class='gr-note'><b>Market blend check.</b> {esc(verdict)}</div>")
    parts.append("<div class='gr-note'><b>Reading the bands.</b> A realized rate inside the Wilson 95% interval is "
                 "consistent with the forecast; <span class='badge warn'>off</span> marks a band whose mean forecast "
                 "falls outside it. Thin bands are noisy — a gap under about two standard errors is not evidence "
                 "of miscalibration.</div>")
    return html_document("".join(parts), f"{SITE_NAME} market calibration", "market-calibration.html", built,
                         bool(latest and latest.get("board_html")))


def render_model(latest, built):
    if latest is None:
        body = head("Model", "No model run has been published yet.")
        return html_document(body, f"{SITE_NAME} model", "model.html", built, has_board=False)
    man = latest["manifest"]
    recipe = man.get("recipe") or {}
    lead = ("Goal: flat 1u ROI at the moneyline on the model's side. "
            f"<span class='mono'>{esc(man['revision'])}</span> · recipe <span class='mono'>{esc(m.recipe_key(recipe))}</span>: "
            f"{esc(recipe.get('family'))} features, {num(recipe.get('half_life')):g}-game team half-life, ridge {num(recipe.get('ridge')):g}. "
            "Coefficients are fit by (ridge) log loss and refit before every week; the recipe is frozen for the season from earlier seasons' walk-forward log loss.")
    parts = [head("Model", lead)]
    sc = latest["season_scorecard"]
    oc = latest["outer_scorecard"]

    def card_rows(df):
        rows = []
        for r in df.to_dict("records"):
            rows.append([esc(r["source"]), f"{r['log loss']:.4f}", f"{r['brier']:.4f}", f"{r['LL gain vs market']:+.4f}",
                         f"{int(r['games scored'])}", f"{num(r['picked winner %']):.1f}%"])
        return rows

    heads = ["Source", "Log loss", "Brier", "LL gain vs mkt", "Games", "Picked winner"]
    if len(latest["roi_by_season"]):
        parts.append("<h2 class='sec'>Flat 1u ROI by season · reconstructed</h2>"
                     + roi_band_table(latest["roi_by_season"], "Season") + ROI_NOTE)
    if len(latest["season_roi"]) and int(num(latest["season_roi"].query("group=='All games' and source=='model'").bets.sum())):
        parts.append(f"<h2 class='sec'>{int(man['season'])} so far · flat 1u ROI · weekly walk-forward</h2>"
                     + roi_band_table(latest["season_roi"]))
    if len(oc):
        parts.append("<h2 class='sec'>Held-out seasons, pooled · log loss · reconstructed</h2>" + table(heads, card_rows(oc), (1, 2, 3, 4, 5)))
    by = latest["outer_by_season"]
    if len(by):
        rows = []
        for yr, g in by.groupby("season"):
            c, k = g[g.source == "box-score composite"].iloc[0], g[g.source == "raw spread-derived market"].iloc[0]
            rows.append([f"{int(yr)}", f"{c['log loss']:.4f}", f"{k['log loss']:.4f}", f"{c['LL gain vs market']:+.4f}",
                         f"{int(c['games scored'])}", f"{c['picked winner %']:.1f}%", f"{k['picked winner %']:.1f}%"])
        parts.append("<h2 class='sec'>Held-out by season</h2>" + table(
            ["Season", "Model LL", "Market LL", "Gain", "Games", "Model picks", "Market picks"], rows, (1, 2, 3, 4, 5, 6)))
    if len(sc):
        parts.append(f"<h2 class='sec'>{int(man['season'])} so far · weekly walk-forward</h2>" + table(heads, card_rows(sc), (1, 2, 3, 4, 5)))
    sel = latest["recipe_selection"]
    if len(sel):
        cr = latest["candidate_roi"]
        if len(cr) and "key" in sel:
            sel = sel.merge(cr[["key", "bets", "units", "roi", "roi_se"]], on="key", how="left")
        best_roi = sel.loc[sel.roi.idxmax(), "key"] if "roi" in sel and sel.roi.notna().any() else None
        rows = []
        for r in sel.to_dict("records"):
            tags = (" <span class=\"badge lean\">selected</span>" if r.get("selected") else "") + \
                   (" <span class=\"badge\">best ROI</span>" if r.get("key") == best_roi else "")
            rows.append([f"<span class='mono'>{esc(m.recipe_key(r))}</span>{tags}", f"{r['log loss']:.5f}",
                         roi_text(r.get("roi"), r.get("roi_se")) if "roi" in r else "—",
                         f"{num(r.get('units')):+.2f}" if math.isfinite(num(r.get("units"))) else "—",
                         f"{num(r.get('games', math.nan)):.0f}"])
        parts.append("<h2 class='sec'>Recipe selection · all candidates</h2><div class='gr-note'>The recipe is chosen by "
                     "<b>lowest walk-forward log loss</b> over the earlier seasons and frozen for the season. Flat 1u ROI on "
                     "the same games is shown for comparison only: it does not choose the recipe. With ROI standard errors "
                     "near ±2.5 points, most candidates cannot be told apart by ROI.</div>"
                     + table(["Recipe", "Walk-forward LL", "Flat 1u ROI ± SE", "Units", "Games"], rows, (1, 2, 3, 4)))
    w = latest["weights"]
    if len(w):
        w = w.reindex(w["coefficient per scaled unit"].abs().sort_values(ascending=False).index)
        rows = [[esc(r["label"]), f"{r['coefficient per scaled unit']:+.3f}", f"{num(r['training missing fraction']):.0%}"]
                for r in w.to_dict("records")]
        parts.append("<h2 class='sec'>Current coefficients</h2><div class='gr-note'>Per training standard deviation of the "
                     "home-minus-away input; features overlap, so read these as the model's bookkeeping, not causes.</div>"
                     + table(["Feature", "Coefficient", "Missing in training"], rows, (1, 2)))
    lim = man.get("limitations") or []
    if lim:
        parts.append("<h2 class='sec'>Limitations</h2><div class='gr-note'><ul style='margin:0;padding-left:18px'>"
                     + "".join(f"<li>{esc(x)}</li>" for x in lim) + "</ul></div>")
    for a in man.get("availability_audit") or []:
        if a.get("source") == "availability_roster_membership":
            parts.append("<h2 class='sec'>Availability audit</h2><div class='gr-note mono' style='font-size:12.5px'>"
                         + esc(", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                                         for k, v in a.items() if k not in ("source", "rule", "qb_rule"))) + "</div>")
    return html_document("".join(parts), f"{SITE_NAME} model", "model.html", built, latest.get("board_html", False))


# ---------------------------------------------------------------- driver

def render_all(out_dir, data=DATA, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    built = now.astimezone(ET).strftime("%Y-%m-%d %H:%M ET")
    latest = load_latest(Path(data) / "latest")
    ledger = load_ledger(data)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pages = {"index.html": render_index(latest, ledger, built, now),
             "grades.html": render_grades(ledger, latest, built),
             "market-calibration.html": render_calibration(latest, ledger, built),
             "model.html": render_model(latest, built)}
    for name, html in pages.items():
        (out / name).write_text(html, encoding="utf-8")
    board = Path(data) / "latest" / "board.html"
    if board.exists():
        shutil.copyfile(board, out / "board.html")
    (out / "ledger_report.txt").write_text((Path(data) / "ledger_report.txt").read_text()
                                           if (Path(data) / "ledger_report.txt").exists() else "No ledger yet.\n")
    (out / ".nojekyll").write_text("")
    return sorted(p.name for p in out.iterdir())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages-only", action="store_true", help="render from committed data/ without running the model")
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "public"))
    args = ap.parse_args(argv)
    if not args.pages_only:
        outdir = run_model()
        season, week = snapshot(outdir)
        print(f"snapshot: {season} week {week} -> {LATEST}")
        grade_ledger.main([])
    files = render_all(args.out)
    print(f"site: {len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
