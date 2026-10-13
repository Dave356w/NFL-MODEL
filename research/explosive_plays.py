"""Test 31: explosive-play rates added to v1.16, walk-forward development comparison.

    python research/explosive_plays.py [--output-dir DIR]     # ~25 min cold (play-by-play download)

Research only: reads the frozen v1.16 training pack (research/shrinkage_results) and nflverse
play-by-play; never writes data/ or public/ and changes no production setting.

Rule fixed in this script before the first run (2026-10-13); nothing below was tuned on results:
  explosive pass = a pass play (pass attempt or sack, as in the box scores) gaining >= 20 yards
  explosive rush = a rush attempt (not a pass play) gaining >= 10 yards
  plays: regular season, no two-point tries, no deleted or no_play rows (the box-score filters)
Profiles use production's main-profile rule: games strictly before the game week, last three
seasons, 2^(-age/8) by team game, halved at each season boundary, ratio of decayed counts with
four league-average pseudo-games. Four features enter as home-minus-away differences:
explosive pass rate and explosive rush rate, for (offense) and allowed (defense).

Arms (fixed v1.16 recipe: market offset, main ridge .1, Product + 1 SD contexts ridge .1):
  production   v1.16 as frozen
  explosive    v1.16 + the four explosive-rate differences (ridge .1, like the main features)
Each is refit before every week 2021-2025 on strictly earlier games and scored on the same rows.

Decision rule: the arm is a candidate for a new REVISION only if its log-loss gain over production
on held-out 2023-2025 is positive with a 95% week-clustered bootstrap interval excluding zero.
Flat 1u moneyline ROI on the model's side is reported with the market-correct null and the
same-row market favorite; it is not the gate (selection stays on log loss). 2021-22 and 2026
weeks so far are reported as diagnostics. v1.18 (favorite penalty 0.2) changes no pick, so its
ROI equals v1.16's; its log loss is reported for both arms.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

import context_shrinkage as s

m, p, ROOT = s.m, s.p, s.ROOT
PACK = ROOT / 'research/shrinkage_results/frozen_training_features.csv.gz'
REFERENCE = ROOT / 'research/production_adoption_results/historical_reproduction.csv'
HALF_LIFE, PASS_MIN, RUSH_MIN, LEVEL, SEED = 8., 20., 10., .95, 20261013
COUNTS = ('pass_plays', 'explosive_pass', 'rush_attempts', 'explosive_rush')
RATES = {'explosive_pass_rate': ('explosive_pass', 'pass_plays'),
         'explosive_rush_rate': ('explosive_rush', 'rush_attempts')}
EXTRA = [f'd__{role}__explosive__{r}' for role in ('for', 'allowed') for r in RATES]
CONTEXTS = list(m.PRODUCT_CONTEXT_NAMES)
BASE = m.feature_names(m.LEGACY_PRODUCT_RECIPE['family'])
ARMS = {'production': [], 'explosive': EXTRA}


def team_games(p, year):
    """Per team-game counts from one season's play-by-play, with the box-score play filters."""
    p = p[(p.season_type == 'REG') & (m.numeric(p, 'two_point_attempt') != 1)].copy()
    if 'play_deleted' in p: p = p[m.numeric(p, 'play_deleted') != 1]
    p = p[p.play_type.ne('no_play') & p.posteam.notna()]
    yards = m.numeric(p, 'yards_gained')
    passplay = (m.numeric(p, 'pass_attempt') == 1) | (m.numeric(p, 'sack') == 1)
    runplay = (m.numeric(p, 'rush_attempt') == 1) & ~passplay
    d = pd.DataFrame({'game_id': p.game_id, 'team': p.posteam, 'week': p.week.astype(int),
                      'pass_plays': passplay.astype(float), 'explosive_pass': (passplay & (yards >= PASS_MIN)).astype(float),
                      'rush_attempts': runplay.astype(float), 'explosive_rush': (runplay & (yards >= RUSH_MIN)).astype(float)})
    g = d.groupby(['game_id', 'team', 'week'], as_index=False)[list(COUNTS)].sum()
    teams = p.groupby('game_id').posteam.unique()
    if (teams.map(len) != 2).any(): raise ValueError(f'{year}: a game without exactly two offenses')
    g['opponent'] = [next(t for t in teams[gid] if t != tm) for gid, tm in zip(g.game_id, g.team)]
    g['season'] = int(year)
    return g


def load_team_games(cache):
    if cache.exists(): return pd.read_csv(cache)
    import nflreadpy as nfl
    cols = ['game_id', 'play_id', 'season_type', 'week', 'posteam', 'play_type', 'yards_gained',
            'pass_attempt', 'rush_attempt', 'sack', 'two_point_attempt', 'play_deleted']
    parts = []
    for year in range(2016, 2027):
        raw = m.fetch_upstream(lambda: nfl.load_pbp(year), f'play-by-play {year}')
        p = m.normalize_teams(raw.select([c for c in cols if c in raw.columns]).to_pandas())
        parts.append(team_games(p, year)); print(f'  play-by-play {year}: {len(parts[-1])} team-games', flush=True)
    g = pd.concat(parts, ignore_index=True)
    g.to_csv(cache, index=False, compression={'method': 'gzip', 'mtime': 0})
    return g


def profiles(f, g):
    """Explosive-rate differences for every pack game, from strictly earlier team-games."""
    opp = g[['game_id', 'team', *COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_' + c for c in COUNTS}})
    both = g.merge(opp, on=['game_id', 'opponent'], validate='one_to_one')
    rows = []
    for (year, week), games in f.groupby(['season', 'week'], sort=True):
        hist = both[m.before(both, year, week) & (both.season >= year - m.MAX_HISTORY_SEASONS)]
        league = {c: float(hist[c].mean()) for c in COUNTS}
        prof = {}
        for team in set(games.home) | set(games.away):
            h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
            age = np.arange(len(h) - 1, -1, -1, dtype=float)
            w = np.exp2(-age / HALF_LIFE) * np.power(m.OFFSEASON_RETENTION, year - h.season.to_numpy(float))
            for role, pre in (('for', ''), ('allowed', 'opp_')):
                for name, (num, den) in RATES.items():
                    prof[team, role, name] = ((w @ h[pre + num].to_numpy(float) + m.PRIOR_EQUIVALENT_GAMES * league[num])
                                              / (w @ h[pre + den].to_numpy(float) + m.PRIOR_EQUIVALENT_GAMES * league[den]))
        last = hist[hist.season == hist.season.max()]
        for r in games.itertuples():
            out = {'game_id': r.game_id, 'source_max_season': int(last.season.max()), 'source_max_week': int(last.week.max())}
            for role in ('for', 'allowed'):
                for name in RATES:
                    out[f'home__{role}__explosive__{name}'] = prof[r.home, role, name]
                    out[f'away__{role}__explosive__{name}'] = prof[r.away, role, name]
                    out[f'd__{role}__explosive__{name}'] = prof[r.home, role, name] - prof[r.away, role, name]
            rows.append(out)
    return pd.DataFrame(rows)


def fit(train, year, week, extra):
    """v1.16's market-offset fit (fit_composite, market_product_1sd) with optional extra main features."""
    if not m.before(train, year, week).all(): raise ValueError('Training includes current/future week')
    names = BASE + extra + CONTEXTS
    t = train[train.ready & train['home won'].isin([0., 1.]) & np.isfinite(train.q) & np.isfinite(train[CONTEXTS]).all(axis=1)]
    if len(t) < m.MIN_TRAIN_GAMES: raise ValueError('Insufficient eligible training')
    raw = np.nan_to_num(t[names].to_numpy(float), nan=0., posinf=0., neginf=0.)
    age = ((year - t.season.to_numpy()) * 19 + week - t.week.to_numpy()) / (19 * m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = w @ raw; scale = np.sqrt(w @ ((raw - mu) ** 2)); scale[scale <= 1e-8] = 1.; scale[0] = 1.
    X = raw / scale
    penalty = np.full(len(names), m.LEGACY_PRODUCT_RECIPE['ridge']); penalty[0] *= .1
    penalty[len(BASE) + len(extra):] = m.LEGACY_PRODUCT_RECIPE['interaction_ridge']
    base = logit(np.clip(t.q.to_numpy(), 1e-5, 1 - 1e-5)); y = t['home won'].to_numpy()

    def objective(beta):
        eta = base + X @ beta
        return (np.sum(w * (np.logaddexp(0, eta) - y * eta)) + .5 * np.sum(penalty * beta ** 2),
                X.T @ (w * (expit(eta) - y)) + penalty * beta)
    beta = m.checked_optimize(objective, len(names))
    return {'names': names, 'scale': scale.tolist(), 'beta': beta.tolist(), 'market_offset': True,
            'training_games': len(t), 'training_max_season': int(t.season.max()),
            'training_max_week': int(t.loc[t.season == t.season.max(), 'week'].max())}


def summarize(d, arms):
    """Same priced rows for every arm; flat 1u ROI, market null, favorite baseline, LL, Brier, pairs."""
    d = d.copy(); d['market'] = d.q
    bets = {a: m.flat_bets(d, a) for a in [*arms, 'market']}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = d['home won'].isin([0., 1.]).to_numpy(); y = d['home won'].to_numpy()
    groups = (d.season.astype(str) + '_' + d.week.astype(str)).to_numpy()
    out = {'bets': int(common.sum()), 'binary_games': int(proper.sum()), 'arms': {}, 'pairs': {}}
    for a in [*arms, 'market', *[f'{a}_v118' for a in arms]]:
        col = d[a] if a in d else pd.Series(m.favorite_penalized_wp(d[a[:-5]], d.q, .2), index=d.index)
        ll = s.loss(y, col.to_numpy())
        r = m.roi_summary(bets[a].loc[common]) if a in bets else {}
        out['arms'][a] = {**r, 'log_loss': float(ll[proper].mean()), 'brier': float(((col.to_numpy() - y) ** 2)[proper].mean()),
                          'll_vec': ll}
    for a in arms:
        if a == 'production': continue
        du = (bets[a].units - bets['production'].units).to_numpy()[common]
        dl = (out['arms']['production']['ll_vec'] - out['arms'][a]['ll_vec'])[proper]
        dl2 = (out['arms']['production_v118']['ll_vec'] - out['arms'][f'{a}_v118']['ll_vec'])[proper]
        out['pairs'][a] = {'roi_delta': float(du.mean()), 'roi_delta_se': float(du.std(ddof=1) / np.sqrt(len(du))),
                           'roi_delta_ci': p.cluster_interval(du, groups[common], LEVEL),
                           'll_gain': float(dl.mean()), 'll_gain_se': float(dl.std(ddof=1) / np.sqrt(len(dl))),
                           'll_gain_ci': p.cluster_interval(dl, groups[proper], LEVEL),
                           'll_gain_v118': float(dl2.mean()), 'll_gain_v118_ci': p.cluster_interval(dl2, groups[proper], LEVEL),
                           'side_flips': int(((d[a] > .5) != (d.production > .5)).to_numpy()[common].sum())}
    for a in out['arms'].values(): del a['ll_vec']
    return out


def run(out):
    out = out.resolve()
    if any(out == x or x in out.parents for x in (ROOT / 'data', ROOT / 'public')): raise ValueError('Protected output')
    out.mkdir(parents=True, exist_ok=True)
    p.SEED = SEED
    f = pd.read_csv(PACK)
    g = load_team_games(out / 'explosive_team_games.csv.gz')
    ex = profiles(f, g)
    cut = ex.merge(f[['game_id', 'season', 'week']], on='game_id', validate='one_to_one')
    if not ((cut.source_max_season < cut.season) | ((cut.source_max_season == cut.season) & (cut.source_max_week < cut.week))).all():
        raise ValueError('Lookahead: an explosive profile uses the game week or later')
    f = f.merge(ex[['game_id', *EXTRA]], on='game_id', validate='one_to_one')
    if not np.isfinite(f[EXTRA]).all().all(): raise ValueError('Missing explosive features')
    mask = (f.ready & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1)
            & (f.season >= 2021)).to_numpy()
    pred = f.loc[mask, ['game_id', 'season', 'week', 'home', 'away', 'home won', 'home_moneyline', 'away_moneyline', 'q']].copy()
    coefs = []
    for (year, week), rows in pred.groupby(['season', 'week'], sort=True):
        train = f[m.before(f, year, week)]
        for a, extra in ARMS.items():
            fitted = fit(train, int(year), int(week), extra)
            if (fitted['training_max_season'], fitted['training_max_week']) >= (year, week): raise ValueError('Fit lookahead')
            pred.loc[rows.index, a] = m.apply_fit(f.loc[rows.index], fitted)
            if a == 'explosive':
                k = len(BASE)
                coefs.append({'season': int(year), 'week': int(week),
                              **dict(zip(EXTRA, np.asarray(fitted['beta'][k:k + len(EXTRA)]).tolist()))})
        if week == 1: print(f'Completed season {year}', flush=True)
    if not np.isfinite(pred[list(ARMS)]).all().all(): raise ValueError('Incomplete probabilities')
    ref = pd.read_csv(REFERENCE).set_index('game_id')
    held = pred[pred.season.between(2023, 2025)]
    repro = float(abs(held.production.to_numpy() - ref.loc[held.game_id, 'production_probability'].to_numpy()).max())
    if len(held) != len(ref) or repro > 1e-7: raise ValueError(f'v1.16 reproduction failed ({repro:.3g})')
    blocks = {'held-out 2023-25': pred.season.between(2023, 2025), 'walk-forward 2021-22': pred.season.between(2021, 2022),
              '2026 so far (diagnostic)': pred.season == 2026}
    info = {'basis': 'Walk-forward development (fixed recipe); not forward evidence', 'revision_compared': m.SHADOW_REVISION,
            'production_revision': m.REVISION, 'rule': {'pass_min_yards': PASS_MIN, 'rush_min_yards': RUSH_MIN, 'half_life': HALF_LIFE},
            'reproduction_max_error': repro, 'level': LEVEL,
            'blocks': {k: summarize(pred[v.to_numpy()], list(ARMS)) for k, v in blocks.items() if v.any()}}
    c = pd.DataFrame(coefs)
    info['explosive_coefficients'] = {e: {'median': float(c[e].median()), 'share_positive': float((c[e] > 0).mean())} for e in EXTRA}
    ab = f.loc[mask & (f.season >= 2021).to_numpy()]
    info['correlations_with_main'] = {
        'for_pass_vs_net_pass_ypp': float(ab['d__for__explosive__explosive_pass_rate'].corr(ab['d__for__rates_core__net_pass_yards_per_pass_play'])),
        'for_rush_vs_rush_ypa': float(ab['d__for__explosive__explosive_rush_rate'].corr(ab['d__for__rates_core__rush_yards_per_attempt'])),
        'allowed_pass_vs_net_pass_ypp': float(ab['d__allowed__explosive__explosive_pass_rate'].corr(ab['d__allowed__rates_core__net_pass_yards_per_pass_play'])),
        'allowed_rush_vs_rush_ypa': float(ab['d__allowed__explosive__explosive_rush_rate'].corr(ab['d__allowed__rates_core__rush_yards_per_attempt']))}
    lg = g[g.season.between(2021, 2025)][list(COUNTS)].sum()
    info['league_rates_2021_25'] = {'explosive_pass_per_pass_play': float(lg.explosive_pass / lg.pass_plays),
                                    'explosive_rush_per_rush': float(lg.explosive_rush / lg.rush_attempts)}
    pred.to_csv(out / 'walk_forward_predictions.csv', index=False)
    c.to_csv(out / 'explosive_coefficients.csv', index=False)
    (out / 'results.json').write_text(json.dumps(info, indent=2, allow_nan=False) + '\n')
    src = [Path(__file__), ROOT / 'nfl_model.py', PACK, REFERENCE, out / 'explosive_team_games.csv.gz']
    (out / 'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in src}, indent=2) + '\n')
    lines = ['# Test 31: explosive-play rates added to v1.16', '', f"Basis: {info['basis']}. v1.16 reproduction error {repro:.2g}.", '']
    for k, b in info['blocks'].items():
        lines += [f'## {k}', '', f"{b['bets']} common priced flat 1u bets; {b['binary_games']} binary games.", '',
                  '| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | LL with v1.18 penalty | Brier |', '|---|---|---:|---:|---:|---:|---:|---:|']
        for a in [*ARMS, 'market']:
            r = b['arms'][a]; v = b['arms'].get(f'{a}_v118', {}).get('log_loss')
            lines.append(f"| {a if a != 'market' else 'market favorite (same rows)'} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | "
                         f"{100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} | {100 * r['null_roi']:+.1f}% | {r['log_loss']:.5f} | "
                         f"{'' if v is None else f'{v:.5f}'} | {r['brier']:.5f} |")
        for a, r in b['pairs'].items():
            lo, hi = r['ll_gain_ci']; rl, rh = r['roi_delta_ci']; vl, vh = r['ll_gain_v118_ci']
            lines += ['', f"{a} − production: LL gain {r['ll_gain']:+.5f} ± {r['ll_gain_se']:.5f} (95% week-clustered [{lo:+.5f}, {hi:+.5f}]); "
                      f"with the v1.18 penalty {r['ll_gain_v118']:+.5f} [{vl:+.5f}, {vh:+.5f}]; ROI {100 * r['roi_delta']:+.2f} pts "
                      f"± {100 * r['roi_delta_se']:.2f} [{100 * rl:+.2f}, {100 * rh:+.2f}]; sides flipped {r['side_flips']}.", '']
    lines += ['## Explosive coefficients (weekly refits 2021-26)', '', '| Feature | Median | Share positive |', '|---|---:|---:|']
    lines += [f"| {e} | {v['median']:+.4f} | {100 * v['share_positive']:.0f}% |" for e, v in info['explosive_coefficients'].items()]
    lines += ['', 'Correlation with the matching main feature (difference scale): ' +
              ', '.join(f'{k} {v:+.2f}' for k, v in info['correlations_with_main'].items()) + '.']
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'research/explosive_plays_results')
    run(ap.parse_args().output_dir)
