"""H15: do the model's small favorites beat their moneyline? Research, never production.

Protocol: research/PREREGISTRATION.md (2026-10-28, H15). Moneyline is legacy research;
nothing here is published.

    python -m research.h15_small_favorites
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import kalshi as k
import nfl_model as m
from research import soft_band_distributions as sb

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/forward_ledger.csv'
OUTPUT = ROOT / 'research/h15_results'
REVISION = 'boxscore-composite-v1.18'
CUTOFF = pd.Timestamp('2026-10-29T00:00:00Z')
SMALL = 3.
DECISION_N = 150


def payout(odds):
    odds = float(odds)
    return odds / 100 if odds > 0 else 100 / -odds


def rows(ledger, fit):
    d = ledger[(ledger.revision == REVISION) & (ledger.status == 'graded')]
    d = d.sort_values('generated_utc', kind='stable').drop_duplicates('game_id')
    out = []
    for r in d.itertuples(index=False):
        if pd.isna(r.home_moneyline) or pd.isna(r.away_moneyline) or pd.isna(r.result) or r.result == 0:
            continue
        raw = float(m.implied_spread([r.model_wp])[0])
        if not 0 < abs(raw) < SMALL:
            continue
        ih, ia = k.ml_implied(r.home_moneyline), k.ml_implied(r.away_moneyline)
        q_home = ih / (ih + ia)
        home = r.model_wp > .5
        won = float((r.result > 0) == home)
        bands = {}
        for name, soft in (('soft', True), ('hard', False)):
            p, _ = sb.forecast(raw, fit, soft=soft)
            win = p[sb.GRID > 0].sum() + p[sb.GRID == 0].sum() / 2
            bands[name] = float(win if home else 1 - win)
        q = q_home if home else 1 - q_home
        odds = r.home_moneyline if home else r.away_moneyline
        fav_home = q_home >= .5
        fav_odds = r.home_moneyline if fav_home else r.away_moneyline
        fav_won = float((r.result > 0) == fav_home)
        out.append(dict(game_id=r.game_id, generated_utc=r.generated_utc, raw=raw, side='home' if home else 'away',
                        y=won, q=q, model=float(r.model_wp if home else 1 - r.model_wp), soft=bands['soft'],
                        hard=bands['hard'], units=payout(odds) if won else -1., null=q * (1 + payout(odds)) - 1,
                        fav_units=payout(fav_odds) if fav_won else -1.))
    return pd.DataFrame(out, columns=['game_id', 'generated_utc', 'raw', 'side', 'y', 'q', 'model', 'soft', 'hard',
                                      'units', 'null', 'fav_units'])


def summary(d):
    n = len(d)
    out = dict(n=n)
    if not n:
        return out
    e = d.y - d.q
    out.update(excess=float(e.mean()), se=float(e.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
               win_rate=float(d.y.mean()), mean_q=float(d.q.mean()), mean_model=float(d.model.mean()),
               model_excess=float((d.y - d.model).mean()),
               units=float(d.units.sum()), roi=float(d.units.mean()),
               roi_se=float(d.units.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
               null_roi=float(d.null.mean()), fav_units=float(d.fav_units.sum()), fav_roi=float(d.fav_units.mean()))
    for c in ('q', 'model', 'soft', 'hard'):
        p = np.clip(d[c].to_numpy(float), 1e-6, 1 - 1e-6)
        y = d.y.to_numpy(float)
        out[f'{c}_ll'] = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        out[f'{c}_brier'] = float(np.mean((p - y) ** 2))
    return out


def verdict(r, final=False):
    if r['n'] < DECISION_N and not final:
        return f"interim (n = {r['n']} < {DECISION_N} games): no verdict"
    if r['excess'] <= 0:
        return 'falsified'
    if r['excess'] - 2 * r['se'] > 0:
        return 'supported: an owner decision on small-favorite recalibration in research reports is justified'
    return 'unresolved'


def fmt(r):
    if not r['n']:
        return 'no graded rows'
    se = f" +/- {r['se']:.3f}" if np.isfinite(r['se']) else ''
    rse = f" +/- {100 * r['roi_se']:.1f}" if np.isfinite(r['roi_se']) else ''
    return (f"n = {r['n']}; won {100 * r['win_rate']:.1f}% vs moneyline {100 * r['mean_q']:.1f}% and model "
            f"{100 * r['mean_model']:.1f}%; excess {r['excess']:+.3f}{se} (1 SE). Win log loss: moneyline "
            f"{r['q_ll']:.4f}, model {r['model_ll']:.4f}, soft band {r['soft_ll']:.4f}, hard band {r['hard_ll']:.4f}. "
            f"1u on the model's side {r['units']:+.2f}u, ROI {100 * r['roi']:+.1f}%{rse} (null {100 * r['null_roi']:+.1f}%; "
            f"same-row market favorite {r['fav_units']:+.2f}u)")


def run(output=OUTPUT):
    games = pd.read_csv(sb.INPUT)
    fit = sb.fit_prior(sb.clean(games)[lambda g: g.season < 2026], 2026)
    d = rows(pd.read_csv(LEDGER), fit)
    t = pd.to_datetime(d.generated_utc, utc=True) if len(d) else pd.Series(dtype='datetime64[ns, UTC]')
    fwd, early = d[t >= CUTOFF], d[t < CUTOFF]
    res = dict(primary=summary(fwd), early=summary(early), fit_sha256=fit['fit_sha256'])
    res['verdict'] = verdict(res['primary'])
    output.mkdir(parents=True, exist_ok=True)
    d.to_csv(output / 'rows.csv', index=False, float_format='%.6g')
    (output / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    md = ['# H15: do the model\'s small favorites beat their moneyline?', '',
          'Pre-registered in research/PREREGISTRATION.md (2026-10-28). Legacy moneyline research; nothing is '
          'published. Rows: first v1.18 pregame snapshots with |raw spread| < 3, decided games only.', '',
          f"**Primary (snapshots from {CUTOFF:%Y-%m-%d %H:%M} UTC): {res['verdict']}.**", '',
          f"- {fmt(res['primary'])}", '',
          'Diagnostic, exposed and never pooled with H15:', '',
          f"- 2026 snapshots before the cutoff: {fmt(res['early'])}", '',
          'Reproduce: `python -m research.h15_small_favorites`', '']
    (output / 'REPORT.md').write_text('\n'.join(md))
    return res


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
    print((OUTPUT / 'REPORT.md').read_text())


if __name__ == '__main__':
    main()
