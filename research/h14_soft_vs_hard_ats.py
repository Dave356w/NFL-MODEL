"""H14: soft vs hard band ATS cover probabilities on the same locks; research, never production.

Protocol: research/PREREGISTRATION.md (2026-10-28, H14). Reporting only: no lock, pick
or page changes. Also reports two exposed diagnostics that are never pooled with H14.

    python -m research.h14_soft_vs_hard_ats
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fixed_bands
import nfl_model as m
from research import band_ladder_score as h10
from research import soft_band_distributions as sb

ROOT = Path(__file__).resolve().parents[1]
LOCKS = ROOT / 'data/ats_locks.jsonl'
HISTORY = ROOT / 'data/latest/fixed_band_ledger.csv'
OUTPUT = ROOT / 'research/h14_results'
REVISION = 'boxscore-composite-v1.18'
CUTOFF = pd.Timestamp('2026-10-29T00:00:00Z')
SEASON = 2026
DECISION_N = 100


def covers(raw, line, fit):
    """(hard, soft) arrays of [home cover, push, away cover] at the home-sign line."""
    return tuple(sb.event(sb.forecast(raw, fit, soft=s)[0], line) for s in (False, True))


def conditional(c):
    return c[0] / (c[0] + c[2])


def row(game_id, week, raw, line, mapped, result, fit, **extra):
    hard, soft = covers(raw, line, fit)
    margin = result - line if np.isfinite(result) else np.nan
    soft_side = np.sign(soft[0] - soft[2]) or np.sign(line)
    return dict(game_id=game_id, week=week, raw=raw, line=line, hard_p=conditional(hard), soft_p=conditional(soft),
                hard_side=float(fixed_bands.pick([mapped], [line])[0]), soft_side=float(soft_side),
                margin=margin, y=np.nan if not np.isfinite(margin) or margin == 0 else float(margin > 0), **extra)


def forward_rows(locks, outcomes, fit):
    rows = []
    for s in locks:
        if (s.get('revision') != REVISION or int(s['season']) != SEASON
                or pd.Timestamp(s['lock_at_utc']) < CUTOFF):
            continue
        rows.append(row(s['game_id'], int(s['week']), float(s['raw_spread']), float(s['market_spread']),
                        float(s['fixed_band_spread']), outcomes.get(s['game_id'], np.nan), fit,
                        recovered=bool(s.get('recovered_after_kickoff', False))))
    return pd.DataFrame(rows)


def early_lock_rows(locks, outcomes, fit):
    rows = [row(s['game_id'], int(s['week']), float(s['raw_spread']), float(s['market_spread']),
                float(s['fixed_band_spread']), outcomes.get(s['game_id'], np.nan), fit)
            for s in locks if s.get('revision') == REVISION and pd.Timestamp(s['lock_at_utc']) < CUTOFF
            and not s.get('recovered_after_kickoff')]
    return pd.DataFrame(rows)


def replay_rows(hist, fit):
    rows = []
    for r in hist[(hist.season == SEASON) & hist.model_wp.notna() & hist.spread_line.notna()
                  & hist.fixed_band_spread.notna()].itertuples(index=False):
        raw = float(m.implied_spread([r.model_wp])[0])
        if raw == 0:
            continue
        rows.append(row(r.game_id, int(r.week), raw, float(r.spread_line), float(r.fixed_band_spread),
                        float(r.result) if pd.notna(r.result) else np.nan, fit))
    return pd.DataFrame(rows)


def score(rows):
    """Log loss gain (hard - soft; positive = soft better), Brier, and the 0.5 baseline."""
    d = rows[rows.y.notna()] if len(rows) else rows
    out = dict(n=len(d))
    if not len(d):
        return out
    hl, sl = h10.log_loss(d.hard_p, d.y), h10.log_loss(d.soft_p, d.y)
    g = hl - sl
    n = len(d)
    out.update(gain=float(g.mean()), se=float(g.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
               sd=float(g.std(ddof=1)) if n > 1 else np.nan,
               hard_loss=float(hl.mean()), soft_loss=float(sl.mean()), coin_loss=float(np.log(2)),
               hard_brier=float(((d.hard_p - d.y) ** 2).mean()), soft_brier=float(((d.soft_p - d.y) ** 2).mean()))
    return out


def paired(rows):
    """ATS units at -110 where the production and soft sides differ."""
    d = rows[rows.margin.notna() & (rows.hard_side != rows.soft_side)] if len(rows) else rows
    out = dict(n=len(d))
    if len(d):
        for arm in ('hard', 'soft'):
            e = d[f'{arm}_side'].to_numpy() * d.margin.to_numpy()
            r = np.where(e > 0, 1 / 1.1, np.where(e < 0, -1., 0.))
            out[arm] = dict(wins=int((r > 0).sum()), losses=int((r < 0).sum()), pushes=int((r == 0).sum()),
                            units=float(r.sum()))
    return out


def verdict(r, season_over=False):
    if r['n'] < DECISION_N and not season_over:
        return f"interim (n = {r['n']} < {DECISION_N} scored locks): no verdict"
    if r['gain'] <= 0:
        return 'falsified'
    if r['gain'] - 2 * r['se'] > 0:
        return 'supported: an owner decision on a soft-band ATS policy version is justified'
    return 'unresolved'


def fmt(r):
    if not r['n']:
        return 'no scored rows'
    se = f" +/- {r['se']:.4f}" if np.isfinite(r.get('se', np.nan)) else ''
    return (f"gain {r['gain']:+.4f}{se} (1 SE; positive = soft better), n = {r['n']}; log loss hard "
            f"{r['hard_loss']:.4f}, soft {r['soft_loss']:.4f}, coin {r['coin_loss']:.4f}; Brier hard "
            f"{r['hard_brier']:.4f}, soft {r['soft_brier']:.4f}")


def fmt_paired(p):
    if not p['n']:
        return 'no differing sides graded'
    h, s = p['hard'], p['soft']
    return (f"{p['n']} locks; production {h['wins']}-{h['losses']}-{h['pushes']} {h['units']:+.2f}u, "
            f"soft {s['wins']}-{s['losses']}-{s['pushes']} {s['units']:+.2f}u")


def run(output=OUTPUT):
    games = pd.read_csv(sb.INPUT)
    fit = sb.fit_prior(sb.clean(games)[lambda g: g.season < SEASON], SEASON)
    hist = pd.read_csv(HISTORY)
    outcomes = {r.game_id: float(r.result) for r in hist.itertuples(index=False) if pd.notna(r.result)}
    locks = [json.loads(line) for line in LOCKS.read_text().splitlines() if line.strip()]
    fwd = forward_rows(locks, outcomes, fit)
    pre = fwd[~fwd.recovered.astype(bool)] if len(fwd) else fwd
    rec = fwd[fwd.recovered.astype(bool)] if len(fwd) else fwd
    early, rep = early_lock_rows(locks, outcomes, fit), replay_rows(hist, fit)
    res = dict(primary=score(pre), paired=paired(pre), recovered=score(rec), early_locks=score(early),
               early_paired=paired(early), replay=score(rep), replay_paired=paired(rep),
               forward_locks=len(fwd), forward_pending=int(pre.margin.isna().sum()) if len(pre) else 0,
               fit_sha256=fit['fit_sha256'])
    res['verdict'] = verdict(res['primary'])
    output.mkdir(parents=True, exist_ok=True)
    for name, d in (('forward_rows', fwd), ('early_lock_rows', early), ('replay_rows', rep)):
        d.to_csv(output / f'{name}.csv', index=False, float_format='%.6g')
    (output / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    md = ['# H14: soft vs hard band ATS cover probabilities on the same locks', '',
          'Pre-registered in research/PREREGISTRATION.md (2026-10-28). Reporting only; production, '
          'the median map and the archives are unchanged. Pushes at the lock line are excluded.', '',
          f"**Primary ({REVISION} locks from {CUTOFF:%Y-%m-%d %H:%M} UTC, {SEASON}): {res['verdict']}.** "
          f"{len(fwd)} locks, {res['forward_pending']} pending.", '',
          f"- Conditional cover log loss: {fmt(res['primary'])}",
          f"- (a) Paired ATS where sides differ: {fmt_paired(res['paired'])}", '',
          'Diagnostics, exposed and never pooled with H14:', '',
          f"- Pre-cutoff 2026 locks: {fmt(res['early_locks'])}",
          f"  - Paired where sides differ: {fmt_paired(res['early_paired'])}",
          f"- 2026 weeks 1-7 replay (fixed_band_ledger): {fmt(res['replay'])}",
          f"  - Paired where sides differ: {fmt_paired(res['replay_paired'])}",
          '', 'Reproduce: `python -m research.h14_soft_vs_hard_ats`', '']
    (output / 'REPORT.md').write_text('\n'.join(md))
    return res


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
    print((OUTPUT / 'REPORT.md').read_text())


if __name__ == '__main__':
    main()
