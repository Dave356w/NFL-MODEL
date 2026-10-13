"""Margin-likelihood v1.16 on 2017-2020 out of sample; see MARGIN_LIKELIHOOD.md.

Same features, rows, scaling, decay and penalties as v1.16, fit to the integer
final margin under a key-number-aware distribution instead of the binary result.
Reads the frozen out-of-sample pack; no network access, no production writes.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr
import out_of_sample_2017_2020 as o

m, p, s, ROOT = o.m, o.p, o.s, o.ROOT
RECIPE, FEATURES, CONTEXTS = o.RECIPE, o.FEATURES, o.CONTEXTS
SCORED, LEVEL = o.SCORED, o.LEVEL
OUT = ROOT/'research/margin_likelihood_results'
PACK = o.OUT/o.PACK
SUPPORT = np.arange(-70, 71)
KEY_MAX, KEY_PSEUDO = 40, 5.
ARMS = ('production', 'margin_likelihood')
NAMES = FEATURES+CONTEXTS


def cell_mass(mu, sigma):
    """Integer-bin normal mass, games x SUPPORT."""
    mu = np.asarray(mu, float)[:, None]
    return ndtr((SUPPORT+.5-mu)/sigma)-ndtr((SUPPORT-.5-mu)/sigma)


def pmf(mu, sigma, w):
    raw = cell_mass(mu, sigma)*w[np.abs(SUPPORT)]
    return raw/raw.sum(1, keepdims=True)


def win_prob(mu, sigma, w):
    """P(home margin > 0 | margin != 0)."""
    pr = pmf(mu, sigma, w)
    return pr[:, SUPPORT > 0].sum(1)/(1-pr[:, SUPPORT == 0][:, 0])


def market_location(q, sigma, w, tol=1e-10):
    """Location whose conditional home-win probability equals q (bisection; monotone in mu)."""
    q = np.clip(np.asarray(q, float), 1e-6, 1-1e-6)
    lo, hi = np.full(len(q), -60.), np.full(len(q), 60.)
    for _ in range(80):
        mid = (lo+hi)/2; up = win_prob(mid, sigma, w) < q
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
        if np.max(hi-lo) < tol: break
    return (lo+hi)/2


def dispersion(rows):
    return float(np.sqrt(np.mean((rows.result.to_numpy(float)-rows.spread_line.to_numpy(float))**2)))


def key_weights(rows, sigma):
    """Observed |margin| counts over the market-centered integer-normal's, +5 pseudo-counts, |k| <= 40."""
    mass = cell_mass(rows.spread_line.to_numpy(float), sigma)
    expected = np.zeros(SUPPORT.max()+1); np.add.at(expected, np.abs(SUPPORT), mass.sum(0))
    observed = np.bincount(np.abs(rows.result.to_numpy(int)), minlength=len(expected))[:len(expected)]
    w = np.ones(len(expected))
    k = np.arange(KEY_MAX+1)
    w[k] = (observed[k]+KEY_PSEUDO)/(expected[k]+KEY_PSEUDO)
    return w


def season_shape(train, year):
    """sigma and key multipliers from strictly earlier seasons' training rows."""
    rows = train[train.season < year]
    if rows.empty or not (rows.season < year).all(): raise ValueError('Shape needs strictly earlier seasons')
    sigma = dispersion(rows)
    return sigma, key_weights(rows, sigma)


def fit_margin(train, year, week, sigma, w):
    """v1.16's design, scaling, decay and penalties; integer-margin likelihood around the market location."""
    if not m.before(train, year, week).all(): raise ValueError('Training includes current/future week')
    t = train[o.eligible(train)].copy()
    if len(t) < m.MIN_TRAIN_GAMES: raise ValueError('Too few training games')
    raw = t[NAMES].to_numpy(float); X = np.where(np.isfinite(raw), raw, 0.)
    age = ((year-t.season.to_numpy())*19+(week-t.week.to_numpy()))/(19*m.FIT_HALF_LIFE_SEASONS)
    weights = np.exp2(-age); weights /= weights.sum()
    mean = np.sum(weights[:, None]*X, axis=0)
    scale = np.sqrt(np.sum(weights[:, None]*(X-mean)**2, axis=0)); scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X/scale
    penalty = np.full(len(NAMES), float(RECIPE['ridge'])); penalty[0] *= .1
    penalty[len(FEATURES):] = float(RECIPE['interaction_ridge'])
    mu0 = market_location(t.q.to_numpy(float), sigma, w)
    c = sigma*np.sqrt(3)/np.pi
    y = np.searchsorted(SUPPORT, np.clip(t.result.to_numpy(int), SUPPORT[0], SUPPORT[-1]))
    wk = w[np.abs(SUPPORT)]; rows = np.arange(len(t))

    def obj(beta):
        mu = (mu0+c*(Z@beta))[:, None]
        a, b = (SUPPORT-.5-mu)/sigma, (SUPPORT+.5-mu)/sigma
        B = ndtr(b)-ndtr(a)
        dB = -(np.exp(-b*b/2)-np.exp(-a*a/2))/np.sqrt(2*np.pi)/sigma      # dB/dmu
        tot = (wk*B).sum(1); dtot = (wk*dB).sum(1)
        By = np.maximum(B[rows, y], 1e-300)
        nll = -(np.log(wk[y])+np.log(By)-np.log(tot))
        g_mu = -(dB[rows, y]/By-dtot/tot)
        loss = np.sum(weights*nll)+.5*np.sum(penalty*beta*beta)
        return loss, c*(Z.T@(weights*g_mu))+penalty*beta

    beta = m.checked_optimize(obj, len(NAMES))
    return {'names': NAMES, 'scale': scale.tolist(), 'beta': beta.tolist(), 'sigma': sigma, 'c': c,
            'training_games': len(t), 'training_max_season': int(t.season.max()),
            'training_max_week_in_latest_season': int(t.loc[t.season == t.season.max(), 'week'].max()),
            'effective_training_games': float(1/np.sum(weights*weights))}


def apply_margin(test, fitted, w):
    raw = test[fitted['names']].to_numpy(float)
    Z = np.where(np.isfinite(raw), raw, 0.)/np.asarray(fitted['scale'])
    mu0 = market_location(test.q.to_numpy(float), fitted['sigma'], w)
    return win_prob(mu0+fitted['c']*(Z@np.asarray(fitted['beta'])), fitted['sigma'], w)


def compare(held):
    held = held.assign(market=held.q)
    arms = [*ARMS, 'market']
    bets = {a: o.flat_units(held, a) for a in arms}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = held['home won'].isin([0., 1.]).to_numpy()
    groups = (held.season.astype(int).astype(str)+'_'+held.week.astype(int).astype(str)).to_numpy()
    y = held['home won'].to_numpy(float)
    losses = {a: s.loss(y, held[a].to_numpy(float)) for a in arms}
    vs_fav = {a: (bets[a].units-bets['market'].units).to_numpy() for a in ARMS}
    rows = []
    for a in arms:
        dog = (held[a] > .5).to_numpy() != (held.q > .5).to_numpy()
        rows.append({'arm': a, **m.roi_summary(bets[a].loc[common]), 'log_loss': float(losses[a][proper].mean()),
                     'brier': float(((held[a]-held['home won'])**2).to_numpy()[proper].mean()),
                     'units_vs_favorite': float(vs_fav[a][common].sum()) if a in ARMS else 0.,
                     'underdog_picks': int((common & dog).sum()),
                     'underdog_pick_units': float(bets[a].units.to_numpy()[common & dog].sum())})
    dl = losses['production']-losses['margin_likelihood']
    du = vs_fav['margin_likelihood']-vs_fav['production']
    dm = losses['market']-losses['margin_likelihood']
    stats = {'L_ll_gain_vs_v116': {'mean': float(dl[proper].mean()),
                                   'interval': p.cluster_interval(dl[proper], groups[proper], LEVEL)},
             'U_units_vs_favorite_change': {'units': float(du[common].sum()), 'per_bet': float(du[common].mean()),
                                            'interval_per_bet': p.cluster_interval(du[common], groups[common], LEVEL)},
             'll_gain_vs_market': {'mean': float(dm[proper].mean()),
                                   'interval': p.cluster_interval(dm[proper], groups[proper], LEVEL)}}
    return {'results': rows, 'statistics': stats, 'bets': int(common.sum()), 'proper_games': int(proper.sum())}


def verdict(st):
    L, U = st['L_ll_gain_vs_v116'], st['U_units_vs_favorite_change']
    if L['mean'] <= 0 or U['units'] < 0: return 'falsified'
    return 'supported' if L['interval'][0] > 0 else 'favored, unresolved'


def run(out=OUT):
    out = o.protect(out); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv(PACK)
    train_mask = o.eligible(f)
    scored = f.season.between(*SCORED) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q) \
        & f.home_moneyline.notna() & f.away_moneyline.notna() & np.isfinite(f[CONTEXTS]).all(axis=1)
    held = f.loc[scored, p.BASE_COLS].copy(); audit = []; shapes = {}
    for (year, week), rows in held.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        train = f[train_mask & m.before(f, year, week)]; test = f.loc[rows.index]
        if year not in shapes:
            sigma, w = season_shape(train, year)
            shapes[year] = {'sigma': sigma, 'w': w}
            print(f'Season {year}: sigma {sigma:.3f}, w3 {w[3]:.2f} w7 {w[7]:.2f} w10 {w[10]:.2f}', flush=True)
        sigma, w = shapes[year]['sigma'], shapes[year]['w']
        prod = o.fit_arm(train, year, week, 'production')
        marg = fit_margin(train, year, week, sigma, w)
        if prod['training_games'] != marg['training_games']: raise ValueError('Arms trained on different rows')
        held.loc[rows.index, 'production'] = m.apply_fit(test, prod)
        held.loc[rows.index, 'margin_likelihood'] = apply_margin(test, marg, w)
        for arm, fitted in (('production', prod), ('margin_likelihood', marg)):
            audit.append({'season': year, 'week': week, 'arm': arm, 'training_games': fitted['training_games'],
                          'training_max_season': fitted['training_max_season'],
                          'training_max_week': fitted['training_max_week_in_latest_season'],
                          'effective_training_games': fitted['effective_training_games']})
    if not np.isfinite(held[list(ARMS)]).all().all(): raise ValueError('Incomplete predictions')
    audit = pd.DataFrame(audit)
    prior = (audit.training_max_season < audit.season) | ((audit.training_max_season == audit.season) & (audit.training_max_week < audit.week))
    if not prior.all(): raise ValueError('Training cutoff is not strictly prior')
    held = held.reset_index(drop=True)
    committed = pd.read_csv(o.OUT/'predictions.csv').set_index('game_id').production
    reproduction = float(np.max(np.abs(held.set_index('game_id').production-committed.reindex(held.game_id).to_numpy())))
    primary = compare(held)
    info = {'protocol': 'research/MARGIN_LIKELIHOOD.md', 'model_revision_at_run': m.REVISION, 'recipe': RECIPE,
            'confidence_level': LEVEL, 'primary': primary, 'verdict': verdict(primary['statistics']),
            'production_reproduction_max_abs_error': reproduction,
            'shapes': {str(y): {'sigma': v['sigma'], 'w3': float(v['w'][3]), 'w7': float(v['w'][7]),
                                'w10': float(v['w'][10]), 'w0': float(v['w'][0])} for y, v in shapes.items()},
            'by_season': [{'season': int(y), **{k: v for k, v in compare(held[held.season == y].reset_index(drop=True)).items()
                                                 if k in ('results', 'statistics')}} for y in sorted(held.season.unique())],
            'fits': len(audit), 'all_training_cutoffs_prior': bool(prior.all())}
    held.to_csv(out/'predictions.csv', index=False)
    audit.to_csv(out/'fit_audit.csv', index=False)
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__).resolve(), ROOT/'research/MARGIN_LIKELIHOOD.md', ROOT/'research/out_of_sample_2017_2020.py',
               ROOT/'nfl_model.py', PACK]
    (out/'provenance.json').write_text(json.dumps(
        {str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}, indent=2)+'\n')
    write_report(info, out)
    print(json.dumps({'verdict': info['verdict'], 'statistics': primary['statistics']}, indent=2), flush=True)
    return info


def write_report(info, out):
    pr = info['primary']; st = pr['statistics']
    L, U, M = st['L_ll_gain_vs_v116'], st['U_units_vs_favorite_change'], st['ll_gain_vs_market']
    lines = ['# Margin-likelihood v1.16: 2017–2020 out of sample', '',
             'Protocol: `research/MARGIN_LIKELIHOOD.md` (committed before this run). Held-out reconstruction; '
             '2017–2020 were scored once before for v1.16, so this is not forward evidence.', '',
             f"**Verdict: {info['verdict']}.** Log-loss gain over v1.16 {L['mean']:+.6f} "
             f"[{L['interval'][0]:+.6f}, {L['interval'][1]:+.6f}]; change in units vs the favorite "
             f"{U['units']:+.2f}u.", '',
             f"{pr['bets']} flat 1u bets; {pr['proper_games']} binary games. v1.16 reproduction max error "
             f"{info['production_reproduction_max_abs_error']:.2e}.", '',
             '| Arm | W-L-P | Units | ROI ± SE | Null | Units vs favorite | Underdog picks | Their units | Log loss | Brier |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in pr['results']:
        lines.append(f"| {r['arm']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | "
                     f"{100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null_roi']:+.2f}% | "
                     f"{r['units_vs_favorite']:+.2f} | {r['underdog_picks']} | {r['underdog_pick_units']:+.2f} | "
                     f"{r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines += ['', f"Challenger log-loss gain vs market: {M['mean']:+.6f} [{M['interval'][0]:+.6f}, {M['interval'][1]:+.6f}].",
              '', '## By season', '', '| Season | LL gain vs v1.16 | Units vs favorite change | Challenger ROI | v1.16 ROI |',
              '|---|---:|---:|---:|---:|']
    for b in info['by_season']:
        r = {x['arm']: x for x in b['results']}
        lines.append(f"| {b['season']} | {b['statistics']['L_ll_gain_vs_v116']['mean']:+.6f} | "
                     f"{b['statistics']['U_units_vs_favorite_change']['units']:+.2f} | "
                     f"{100*r['margin_likelihood']['roi']:+.2f}% | {100*r['production']['roi']:+.2f}% |")
    lines += ['', '## Fitted shape (strictly earlier seasons)', '', '| Season | σ | w(0) | w(3) | w(7) | w(10) |', '|---|---:|---:|---:|---:|---:|']
    for y, v in info['shapes'].items():
        lines.append(f"| {y} | {v['sigma']:.2f} | {v['w0']:.2f} | {v['w3']:.2f} | {v['w7']:.2f} | {v['w10']:.2f} |")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    run()
