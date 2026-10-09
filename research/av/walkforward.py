"""Chronological walk-forward for A (exact v1.15), B1/B2, C1-C3 and D1/D2 on identical games.

    python research/av/walkforward.py [CACHE_DIR]      # ~60 min cold (A+C grid ~50 min), minutes warm

Conventions are production's (research/_common.py): features from 2019 (two warm-up seasons), weekly
refits on earlier games only, out-of-fold predictions for 2021-2025 on the rows production scores
(labeled, both teams with >= MIN_TRAIN_GAMES history), and for each held-out season 2023-2025 the
recipe with the lowest mean walk-forward log loss on EARLIER seasons. Nothing is selected on ROI.

Writes (research/av/output/): heldout_predictions.csv (every variant, every held-out game),
selection.json (each season's pick per variant), av_team_week_features.csv.gz (feature audit) and
control_check.json (the v1.15 control against research Test 29). Large intermediates stay in
CACHE_DIR/av (git-ignored .nfl_cache).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from _common import LAST, OUTER, _ll, availability, cache_dir_from_argv, load_inputs, log, m  # noqa: E402
import aggregation as ag  # noqa: E402
import availability as av  # noqa: E402
import models as md  # noqa: E402
import player_value as pv  # noqa: E402
from prepare_data import prepare  # noqa: E402

OUT = HERE / 'output'
PROD = tuple(m.FEATURE_FAMILIES)  # v1.15 production families, captured before any research change
# Research Test 29 (2026-10-09), v1.15 arm: the control this run must reproduce.
CONTROL = {'bets': 811, 'units': 16.30, 'll': .6316, 'pick': 'rates_core_adj_avail_cs_peaks_nosacks_h16_r0.1'}


def build_av(inp, cache):
    c = Path(cache) / 'av'
    p = c / 'av_features.parquet'
    if p.exists(): return pd.read_parquet(p)
    d = prepare(cache)
    pgv = pv.game_rav(d['pg'], d['tg']); pgv.to_parquet(c / 'pgv.parquet', index=False)
    seasons = pv.season_table(pgv)
    est = pv.Estimator(pgv, seasons, d['draft'], d['rookie_season'])
    part = av.Participation(pgv, inp['a']['inj'], inp['a']['rost'], availability(inp), inp['qb'], inp['a'].get('depth'))
    audit = []
    f = ag.build(part, est, inp['targets'], audit, log)
    pd.concat(audit, ignore_index=True).to_parquet(c / 'av_player_audit.parquet', index=False)
    f.to_parquet(p, index=False)
    return f


def features(inp, avail15, avf):
    return {h: md.attach_av(m.lagged_features(inp['box'], inp['sched'], h, avail15), avf) for h in m.TEAM_HALF_LIVES}


def grid_ac(inp, feats, cache):
    p = Path(cache) / 'av' / 'oof_ac.parquet'
    if p.exists(): return pd.read_parquet(p)
    md.install_c()
    m.FEATURE_FAMILIES = PROD + tuple(f'{f}__{v}' for v in md.C_VARIANTS for f in PROD)
    try:
        oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), inp['sched'])
    finally:
        m.FEATURE_FAMILIES = PROD
    oof.to_parquet(p, index=False)
    return oof


def b_and_d(f, cache):
    p = Path(cache) / 'av' / 'bd_predictions.parquet'
    if p.exists(): return pd.read_parquet(p)
    f = f.sort_values(['season', 'week', 'game_id'])
    out = f[['game_id']].copy()
    for spec, kind in md.B_SPECS.items():
        for mode in ag.MODES:
            for lam in md.B_RIDGE:
                key = f'{spec}_{mode}_r{lam:g}'
                mu, sg = md.walk_forward_margin(f, md.b_columns(kind, mode), lam)
                out['mu__' + key], out['p__' + key] = mu, md.wp(mu, sg)
        log(f'  B {spec} done')
    for key in [k[4:] for k in out.columns if k.startswith('mu__B2_')]:
        mu = out['mu__' + key]
        for adj, name in ((False, 'D1'), (True, 'D2')):
            for lam in md.D_LAMBDA:
                for gam in md.D_GAMMA:
                    ah, aa = md.team_residual_states(f, mu, lam, gam, opponent_adjust=adj)
                    mud = mu + ah - aa
                    k = f'{name}_{key}_l{lam:g}_g{gam:g}'
                    out['mu__' + k], out['p__' + k] = mud, md.wp(mud, md.walk_forward_sigma(f, mud))
        log(f'  D on {key} done')
    out.to_parquet(p, index=False)
    return out


def select(oof, cols):
    """For each held-out season: the candidate with min mean log loss on earlier OOF seasons."""
    y = oof['home won'].to_numpy(float); picks = {}; wpcol = pd.Series(np.nan, index=oof.index)
    for yr in OUTER:
        tr = (oof.season < yr).to_numpy()
        ok = [c for c in cols if oof.loc[tr, c].notna().all()]
        best = min(ok, key=lambda c: _ll(y[tr], oof[c].to_numpy()[tr]).mean())
        te = oof.season == yr
        wpcol[te] = oof.loc[te, best]; picks[yr] = best[3:]
    return wpcol, picks


VARIANTS = {
    'A': lambda c: [x for x in c if x.startswith('p__') and '__C' not in x[3:] and any(x[3:].startswith(f + '_h') for f in PROD)],
    'B1': lambda c: [x for x in c if x.startswith('p__B1_')],
    'B2': lambda c: [x for x in c if x.startswith('p__B2_')],
    'C1': lambda c: [x for x in c if x.endswith(tuple(f'__C1_h{h:g}_r{r:g}' for h in m.TEAM_HALF_LIVES for r in m.RIDGE_GRID))],
    'C2': lambda c: [x for x in c if x.endswith(tuple(f'__C2_h{h:g}_r{r:g}' for h in m.TEAM_HALF_LIVES for r in m.RIDGE_GRID))],
    'D1': lambda c: [x for x in c if x.startswith('p__D1_')],
    'D2': lambda c: [x for x in c if x.startswith('p__D2_')],
    # ablations (not primary variants)
    'C3 QB rAV for QB efficiency': lambda c: [x for x in c if '__C3_h' in x],
    'B2 prior-only rates': lambda c: [x for x in c if x.startswith('p__B2_prior_')],
    'B2 blended rates': lambda c: [x for x in c if x.startswith('p__B2_blend_')],
    'B replacement-relative, linear': lambda c: [x for x in c if x.startswith('p__B2rel_')],
    'B replacement-relative, min starter': lambda c: [x for x in c if x.startswith('p__B2min_')],
}
PRIMARY = ('A', 'B1', 'B2', 'C1', 'C2', 'D1', 'D2')


def assemble(oof, bd, feats):
    f = feats[m.TEAM_HALF_LIVES[0]]
    keep = ['game_id', 'home_qb_expected', 'home_qb_usual', 'away_qb_expected', 'away_qb_usual',
            'home_starters_out', 'away_starters_out', 'home_continuity', 'away_continuity']
    o = oof.merge(bd, on='game_id', how='left', validate='one_to_one').merge(f[keep], on='game_id', how='left')
    held = o[o.season.isin(OUTER)].copy()
    sel = {}
    for name, fn in VARIANTS.items():
        cols = fn(o.columns)
        if not cols: raise ValueError(f'no candidates for {name}')
        wpcol, picks = select(o, cols)
        held[f'wp__{name}'] = wpcol[held.index]
        mu = []
        for yr in OUTER:
            k = picks[yr]; te = held.season == yr
            mu.append(held.loc[te, 'mu__' + k] if 'mu__' + k in held else
                      pd.Series(m.implied_spread(held.loc[te, 'p__' + k]), index=held.index[te]))
        held[f'mu__{name}'] = pd.concat(mu)
        sel[name] = {int(k): v for k, v in picks.items()}
    return held, sel, o


def control_check(held, sel):
    from _common import score
    d = held.assign(model_wp=held['wp__A'])
    s = score(d)
    res = {'bets': int(s['bets']), 'units': round(float(s['units']), 2), 'll': round(float(s['ll']), 4),
           'picks': sel['A'], 'reference': CONTROL}
    res['reproduced'] = bool(res['bets'] == CONTROL['bets'] and abs(res['units'] - CONTROL['units']) < .015
                             and abs(res['ll'] - CONTROL['ll']) < 6e-5 and all(v == CONTROL['pick'] for v in sel['A'].values()))
    return res


def main():
    cache = cache_dir_from_argv()
    OUT.mkdir(parents=True, exist_ok=True)
    inp = load_inputs(cache)
    a15 = availability(inp)
    avf = build_av(inp, cache); log(f'AV team-week features: {len(avf)}')
    avf.round(5).to_csv(OUT / 'av_team_week_features.csv.gz', index=False)
    feats = features(inp, a15, avf); log('feature frames built')
    bd = b_and_d(feats[m.TEAM_HALF_LIVES[0]], cache); log('B + D done')
    oof = grid_ac(inp, feats, cache); log('A + C grid done')
    held, sel, _ = assemble(oof, bd, feats)
    cc = control_check(held, sel)
    (OUT / 'control_check.json').write_text(json.dumps(cc, indent=2))
    log(f'control: {cc}')
    (OUT / 'selection.json').write_text(json.dumps(sel, indent=2))
    cols = (['game_id', 'season', 'week', 'home', 'away', 'home won', 'result', 'spread_line', 'home_moneyline',
             'away_moneyline', 'home_qb_expected', 'home_qb_usual', 'away_qb_expected', 'away_qb_usual',
             'home_starters_out', 'away_starters_out', 'home_continuity', 'away_continuity']
            + [c for c in held if c.startswith(('wp__', 'mu__')) and c[4:] in VARIANTS])
    held[cols].round(6).to_csv(OUT / 'heldout_predictions.csv', index=False)
    log('done')


if __name__ == '__main__':
    main()
