#!/usr/bin/env python3
"""Build the NFL model site: run the model, snapshot its outputs into data/,
grade the forward ledger, and render static pages into public/.

    python build_site.py               # full build (what build.yml runs)
    python build_site.py --pages-only  # re-render from committed data/ only

Pages (public: W-L, win % and ROI only; standard errors, log loss and model
internals stay in data/ledger_report.txt and data/latest/)
  index.html               this week's games: model vs market, pick, biggest factors, injury reports
  grades.html              locked picks graded, beside always-favorite and always-home; rebuilt history
  market-calibration.html  the moneyline graded by price; model confidence vs results

Data written (committed by build.yml through commit_data.py)
  data/forward_predictions.jsonl   append-only ledger (written by nfl_model.record_forward)
  data/frozen_recipe_<season>_<REVISION>.json frozen hyperparameters (nfl_model.frozen_recipe)
  data/kalshi_snapshots.jsonl      append-only Kalshi quotes captured for newly locked games (kalshi.py)
  data/h4_terms.jsonl              append-only pass-matchup terms for newly locked games (matchup.py, H4)
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
              "market_wp", "model_wp", "model_spread", "homefield_wp", "composite_log_odds", "recipe",
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

PAGES = (("index.html", "Projections"), ("grades.html", "Ledger"),
         ("market-calibration.html", "Market calibration"))


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
            f"<title>{esc(title)}</title><meta name='description' content='NFL box-score composite win probabilities, forward ledger and market calibration'>"
            f"{THEME_JS}<style>{font_face_css()}{CSS}</style></head><body><div class='mx-wrap'>"
            f"<div class='topbar'><a class='brand' href='index.html'>{SITE_NAME}</a>"
            "<button class='theme' type='button' onclick='toggleTheme()' aria-label='Toggle colour theme'>Theme</button></div>"
            f"<nav class='nav'>{nav}</nav>{body}"
            f"<div class='foot'>Built <span class='stamp'>{esc(built)}</span>. Win probabilities from each team's "
            "earlier games and this week's injury reports. Not betting advice.</div></div></body></html>")


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
    return ko.astimezone(ET).strftime("%a %-I:%M %p ET") if ko else "TBD"


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


UNIT_NAMES = {"OL": "Offensive line", "WRTE": "Receivers", "RB": "Running backs",
              "DL": "Defensive line", "LB": "Linebackers", "DB": "Secondary"}


def factor_label(name):
    """Plain name for a model input on the public card."""
    if name == "site":
        return "Home field"
    if name == m.MARGIN_FEATURE:
        return "Point margin"
    if name.startswith("d__avail__"):
        c = name[len("d__avail__"):]
        return "Quarterback" if c == "qb_delta" else f"{UNIT_NAMES.get(c.split('_')[0], c)} availability"
    return m.feature_label(name)


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


def records_table(recs):
    """When the model said X%, how often its pick won."""
    rows = []
    for _, r in recs[recs.source == "model"].sort_values("band_index").iterrows():
        if not r.games:
            continue
        rows.append({"cells": [esc(r.band), f"<b>{esc(r.record)}</b>", f"{r['realized pick win %']:.1f}%",
                               f"{r['avg pick prob %']:.1f}%"],
                     "_class": "total" if r.band == "All picks" else ""})
    return table(["Model said", "Picks", "Won", "Average forecast"], rows, num_cols=(1, 2, 3))


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
            f"Same games for both: {span}, each season predicted by a model chosen on earlier seasons only{fwd}.</p>")


# ---------------------------------------------------------------- pages

def render_index(latest, ledger, built, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if latest is None or latest["board"].empty:
        body = head("Projections", "No model run has been published yet; the first build writes this page.")
        return html_document(body, f"{SITE_NAME} projections", "index.html", built)
    man, board = latest["manifest"], latest["board"].copy()
    rev, season, week = man["revision"], int(man["season"]), int(man["week"])
    has_avail = (man.get("recipe") or {}).get("family", "") in m.AVAIL_FAMILIES
    cur = ledger[ledger.revision == rev] if len(ledger) else ledger
    recorded = {r.game_id: r for r in cur.itertuples(index=False)}
    parts = [head(f"Week {week}", f"Model win probabilities for every {season} week-{week} game. Tap a game for details.")]

    def pending(r):
        ko = m.kickoff_utc(r)
        return (has_avail and pd.isna(r.get("result")) and ko is not None and ko > now
                and not m.injury_reports_ready(r, ko, now))

    rows = board.to_dict("records")
    n_pend = sum(1 for r in rows if pending(r))
    if n_pend:
        parts.append(f"<div class='gr-note flag-note'>Injury reports aren't final for {n_pend} "
                     f"game{'s' if n_pend != 1 else ''} yet, so {'those numbers' if n_pend != 1 else 'that number'} can still move.</div>")
    far = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    rows.sort(key=lambda r: (pd.notna(r.get("result")), m.kickoff_utc(r) or far, str(r["game_id"])))
    contrib = latest["contributions"]
    cmax = float(contrib["log-odds contribution"].abs().max()) if len(contrib) else 1.
    graded = cur[cur.status == "graded"] if len(cur) else cur
    mkt_bands, mdl_bands, band_years, n_fwd = band_windows(latest, graded)
    cards = []
    for r in rows:
        p = num(r["model_wp"])
        home, away = r["home"], r["away"]
        fav_home = p > .5
        q = num(m.market_ml_wp(pd.DataFrame([r]))[0])
        bet = m.flat_bets(pd.DataFrame([r]), "model_wp").iloc[0]
        team = home if bet.side == "home" else away if bet.side == "away" else ""
        flags = []
        if pd.notna(r.get("result")):
            flags.append(f"<span class='badge'>Final {score_text(r.get('away_score'), r.get('home_score'))}</span>")
            if team and bet.result in ("W", "L", "P"):
                flags.append(f"<span class='badge {'w' if bet.result == 'W' else 'l' if bet.result == 'L' else ''}'>"
                             f"Pick {esc(team)} · {bet.result}</span>")
        else:
            if team and math.isfinite(num(bet.price)):
                flags.append(f"<span class='badge lean'>Pick {esc(team)} {ml_text(bet.price)}</span>")
            if r["game_id"] in recorded:
                flags.append("<span class='badge'>Locked</span>")
            elif pending(r):
                flags.append("<span class='badge warn'>Report pending</span>")
            if not bool(r.get("ready", True)):
                flags.append("<span class='badge'>Limited history</span>")
        for side in ("away", "home"):
            e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
            if isinstance(e, str) and isinstance(u, str) and e != u:
                flags.append(f"<span class='badge warn'>{esc(r[side])} QB: {esc(e)}</span>")
        hm, am = num(r.get("home_moneyline")), num(r.get("away_moneyline"))
        mk = f"{esc(away)} {ml_text(am)} · {esc(home)} {ml_text(hm)}" if math.isfinite(hm) and math.isfinite(am) else "No line yet"
        ms, ks = model_spread(r), num(r.get("spread_line"))
        sp = (f"<span>Model {favorite_spread_text(ms, home, away)}</span>"
              + (f" · <span>Market {favorite_spread_text(ks, home, away)}</span>" if math.isfinite(ks) else ""))

        def side_html(code, wp, fav, cls):
            club = (f"<div class='club'><div class='nm'>{esc(TEAM_NAMES.get(code, code))}</div>"
                    f"<div class='wp{' fav' if fav else ''}'>{pct(wp)}</div></div>")
            chip = f"<div class='chip'><span>{esc(code)}</span>{logo_html(code)}</div>"
            return f"<div class='side {cls}'>{chip + club if cls == 'away' else club + chip}</div>"

        summary = (f"<summary class='game-summary'><div class='teams'>"
                   f"{side_html(away, 1 - p, not fav_home and not math.isclose(p, .5), 'away')}"
                   f"<div class='mid'><div class='t'>{esc(kickoff_text(r))}</div><div class='mk'>{mk}</div>"
                   f"<div class='mk sp'>{sp}</div></div>"
                   f"{side_html(home, p, fav_home, 'home')}</div>"
                   f"<div class='probbar' aria-hidden='true'><i class='a' style='width:{100 * (1 - p):.1f}%'></i>"
                   f"<i class='h' style='width:{100 * p:.1f}%'></i></div>"
                   f"{f'<div class=flags>{chr(10).join(flags)}</div>' if flags else ''}<span class='chev'>⌄</span></summary>")
        det = ["<div class='detail'>", table(["", esc(away), esc(home)], [
            ["Model", pct(1 - p), pct(p)],
            ["Market", pct(1 - q) if math.isfinite(q) else "—", pct(q) if math.isfinite(q) else "—"],
            ["Moneyline", ml_text(am), ml_text(hm)],
            ["Model spread", spread_text(ms, False), spread_text(ms, True)],
            ["Market spread", spread_text(ks, False), spread_text(ks, True)]], num_cols=(1, 2))]
        if team and math.isfinite(num(bet.price)) and math.isfinite(q):
            det.append(price_band_html(team, bet.price, q if bet.side == "home" else 1 - q,
                                       mkt_bands, mdl_bands, band_years, n_fwd))
        rec = recorded.get(r["game_id"])
        if rec is not None:
            det.append(f"<p class='mut'>Pick locked {esc(pd.to_datetime(rec.generated_utc, utc=True).tz_convert(ET).strftime('%a %-I:%M %p ET'))} "
                       f"at {pct(rec.model_wp)} {esc(home)}.</p>")
        t = contrib[contrib.game_id == r["game_id"]] if len(contrib) else contrib
        if len(t):
            t = t.loc[t["log-odds contribution"].abs().sort_values(ascending=False).index].head(4)
            trs = []
            for c in t.to_dict("records"):
                v = float(c["log-odds contribution"]); w = 50 * abs(v) / max(cmax, 1e-9)
                style = f"left:50%;width:{w:.1f}%" if v > 0 else f"right:50%;width:{w:.1f}%"
                trs.append([esc(factor_label(c["feature"])),
                            f"<div class='cbar'><i class='{'pos' if v > 0 else 'neg'}' style='{style}'></i></div>"])
            det.append("<h3>Biggest factors</h3>" + table(["", f"← {esc(away)} · {esc(home)} →"], trs))
        if has_avail:
            det.append(f"<p class='mut'>Projected QBs: {esc(away)} {_qb(r, 'away')} · {esc(home)} {_qb(r, 'home')}</p>")
            det.append(report_notes_html(latest.get("report_notes"), (away, home), int(r["week"])))
        det.append("</div>")
        cards.append(f"<details class='card'>{summary}{''.join(det)}</details>")
    parts.append(f"<div class='grid'>{''.join(cards)}</div>")
    graded = cur[cur.status == "graded"] if len(cur) else cur
    ctrl = control_records(graded)
    if ctrl and ctrl["model"]["bets"]:
        r, f = ctrl["model"], ctrl["favorite"]
        line = (f"Model {wl_text(r)} ({100 * r['win_pct']:.1f}%) · ROI {roi_short(r['roi'])}"
                f"<span class='mut'> · always favorite {wl_text(f)} · ROI {roi_short(f['roi'])}</span>")
    else:
        line = "<span class='mut'>No graded picks yet. The record starts with the first locked pick.</span>"
    parts.append(f"<div class='record'><div class='l'>Model record</div><div class='mono'>{line}</div>"
                 "<div class='go'><a href='grades.html'>Ledger →</a></div></div>")
    return html_document("".join(parts), f"{SITE_NAME} — week {week}", "index.html", built)


STATE_TEXT = {
    "none": "Week {w} report not out yet; players listed last week count as available until it is.",
    "practice": "Practice report only so far; listed players still count as available.",
    "final": "Final report: Out and Doubtful count fully, Questionable a quarter.",
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
            counted = num(x.counted)
            rows.append([f"{esc(x.player)} <span class='mut'>{esc(x.position)}</span>", esc(x.this_week),
                         f"{100 * counted:.0f}%" if math.isfinite(counted) else "—"])
        out.append(f"<p class='mut'><b>{esc(t)}</b> · {esc(STATE_TEXT.get(n.report_state.iloc[0], '').format(w=week))}</p>"
                   + table(["Player", f"Week {week}", "Counted out"], rows, num_cols=(2,)))
    return "".join(out) if len(out) > 1 else ""


def _qb(r, side):
    e, u = r.get(f"{side}_qb_expected"), r.get(f"{side}_qb_usual")
    if not isinstance(e, str):
        return "—"
    return esc(e) + (f" (usual {esc(u)})" if isinstance(u, str) and u != e else "")


def render_grades(ledger, latest, built):
    rev = latest["manifest"]["revision"] if latest else (ledger.revision.iloc[0] if len(ledger) else m.REVISION)
    parts = [head("Ledger", "Every pick is locked before kickoff, once both teams' injury reports are final, "
                            "and graded at the moneyline it was locked at. One unit per game.")]
    cur = ledger[ledger.revision == rev] if len(ledger) else ledger
    graded = cur[cur.status == "graded"] if len(cur) else cur
    n_pend = len(cur) - len(graded)
    parts.append(control_tiles(control_records(graded), "Graded", f"{len(graded)}", f"{n_pend} pending"))
    if cur.empty:
        parts.append("<div class='gr-note'>No picks locked yet. The first one locks once a week's final injury "
                     "reports are out.</div>")
    else:
        weeks = sorted({(int(s), int(w)) for s, w in zip(cur.season, cur.week)}, reverse=True)
        for i, (s, w) in enumerate(weeks):
            g = cur[(cur.season == s) & (cur.week == w)].sort_values("kickoff_utc")
            rows, wins, losses = [], 0, 0
            for r in g.itertuples(index=False):
                ko = pd.to_datetime(r.kickoff_utc, utc=True).tz_convert(ET).strftime("%a %-I:%M %p")
                res = getattr(r, "bet_result", "")
                wins += res == "W"; losses += res == "L"
                final = (score_text(r.away_score, r.home_score) if r.status == "graded"
                         else f"<span class='badge'>{esc(r.status)}</span>")
                rows.append([f"<span class='team-code'>{esc(r.away)} @ {esc(r.home)}</span> <span class='mut'>{esc(ko)}</span>",
                             pick_text(getattr(r, "bet_team", ""), getattr(r, "bet_price", math.nan)), final, result_badge(res)])
            parts.append(folded(f"{s} week {w} · {len(g)} picks <span class='rt'>{wins}-{losses}</span>",
                                table(["Game", "Pick", "Final", "Result"], rows, num_cols=(2,)), i == 0))
    if latest is not None:
        parts.append(render_retro(latest))
    parts.append("<p class='mut small'>Full statistics, including standard errors: "
                 "<a href='ledger_report.txt'>ledger_report.txt</a>.</p>")
    return html_document("".join(parts), f"{SITE_NAME} ledger", "grades.html", built)


def render_retro(latest):
    """The current model replayed on past seasons: hindsight, labelled as such."""
    retro = latest.get("retro_ledger")
    if retro is None or retro.empty:
        return ""
    seasons = sorted(int(x) for x in retro.season.unique())
    out = ["<h2 class='sec'>Rebuilt history</h2>",
           f"<div class='gr-note flag-note'>The current model replayed on every game since {seasons[0]}, each week "
           "predicted from earlier games only. <b>Hindsight, not a track record:</b> the model was designed after "
           "these games were played.</div>"]
    played = retro[pd.to_numeric(retro["home won"], errors="coerce").isin([0., .5, 1.])]
    out.append(control_tiles(control_records(played), "Games", f"{len(played)}", f"{seasons[0]}–{seasons[-1]}"))
    for yr in reversed(seasons):
        g = retro[retro.season == yr].sort_values(["week", "game_id"], ascending=[False, True])
        units = g.units.dropna()
        rows = [[f"<span class='mono'>W{int(x.week)}</span>", f"<span class='team-code'>{esc(x.away)} @ {esc(x.home)}</span>",
                 pick_text(x.bet_team, x.bet_price), score_text(getattr(x, "away_score", math.nan), getattr(x, "home_score", math.nan)),
                 result_badge(x.bet_result if isinstance(x.bet_result, str) else "")] for x in g.itertuples(index=False)]
        w, l = int((g.bet_result == "W").sum()), int((g.bet_result == "L").sum())
        summ = (f"{yr} · {w}-{l} <span class='rt'>ROI {roi_short(units.mean())}</span>" if len(units) else f"{yr} · no priced picks")
        out.append(folded(summ, table(["Week", "Game", "Pick", "Final", "Result"], rows, num_cols=(3,))))
    return "".join(out)


def market_sides(df):
    """One row per side of every priced, decided game: its moneyline, no-vig implied probability and result."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["side", "price", "q", "won", "band"])
    d = df[pd.to_numeric(df["home won"], errors="coerce").isin([0., 1.])].copy()
    q = m.market_ml_wp(d)
    ok = np.isfinite(q)
    d, q = d[ok], q[ok]
    hw = d["home won"].to_numpy(float)
    sides = pd.concat([pd.DataFrame({"side": "home", "price": d.home_moneyline.to_numpy(float), "q": q, "won": hw}),
                       pd.DataFrame({"side": "away", "price": d.away_moneyline.to_numpy(float), "q": 1 - q, "won": 1 - hw})],
                      ignore_index=True)
    sides["band"] = [m.ml_band(p) for p in sides.price]
    return sides


def render_calibration(latest, ledger, built):
    parts = [head("Market calibration", "What the moneyline implied against what happened, by price. "
                                        "This grades the <i>market</i>, not the model.")]
    retro = latest.get("retro_ledger") if latest else None
    sides = market_sides(retro)
    if len(sides):
        seasons = sorted(int(x) for x in retro.season.unique())
        fav = sides[sides.q > .5]
        home = sides[sides.side == "home"]
        parts.append("<div class='gr-summary'>"
                     + stat("Favorites won", f"{100 * fav.won.mean():.1f}%", f"vs {100 * fav.q.mean():.1f}% implied · {len(fav)} games")
                     + stat("Home teams won", f"{100 * home.won.mean():.1f}%", f"vs {100 * home.q.mean():.1f}% implied · {len(home)} games")
                     + "</div>")

        def cell(s):
            if s.empty:
                return "—"
            tone = "up" if s.won.mean() > s.q.mean() else "dn"
            return (f"<span class='{tone}'>{100 * s.won.mean():.1f}%</span> vs {100 * s.q.mean():.1f}% "
                    f"<span class='mut'>· {len(s)}</span>")
        rows = [[esc(b), cell(sides[(sides.band == b) & (sides.side == "home")]),
                 cell(sides[(sides.band == b) & (sides.side == "away")]), cell(sides[sides.band == b])]
                for b in m.ML_BANDS if (sides.band == b).any()]
        parts.append(table(["Moneyline", "Home side", "Away side", "Both"], rows, num_cols=(1, 2, 3)))
        parts.append(f"<p class='mut small'>Won % vs the price's implied % with the bookmaker's margin removed, then games. "
                     f"Regular season {seasons[0]}–{seasons[-1]}, closing lines.</p>")
    rev = latest["manifest"]["revision"] if latest else m.REVISION
    s = grade_ledger.scored_frame(ledger[ledger.revision == rev]) if len(ledger) else pd.DataFrame()
    parts.append("<h2 class='sec'>Model confidence</h2>")
    if len(s):
        parts.append("<p class='mut small'>Locked picks.</p>" + records_table(m.band_records(s)))
    if latest is not None and len(latest["band_records"]):
        parts.append("<p class='mut small'>Past games, each predicted from earlier games only (reconstructed).</p>"
                     + records_table(latest["band_records"]))
    elif not len(s):
        parts.append("<div class='gr-note'>No graded picks yet.</div>")
    return html_document("".join(parts), f"{SITE_NAME} market calibration", "market-calibration.html", built)


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
             "market-calibration.html": render_calibration(latest, ledger, built)}
    for name, html in pages.items():
        (out / name).write_text(html, encoding="utf-8")
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
        kalshi.safe_record(DATA)  # secondary quotes for newly locked games; never fails the build
        matchup.safe_record(outdir, DATA)  # pre-registered H4 term for newly locked games; never fails the build
        grade_ledger.main([])
    files = render_all(args.out)
    print(f"site: {len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
