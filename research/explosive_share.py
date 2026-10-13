"""Test 34: explosive share of offensive yardage added to v1.16, 2017-2020 (protocol EXPLOSIVE_SHARE.md).

    python research/explosive_share.py [--output-dir DIR]     # ~25 min cold (2010-2020 play-by-play)

Research only: reads the frozen 2013-2020 v1.16 pack and nflverse play-by-play; never writes
data/ or public/. The feature, arms and decision rules are fixed in the protocol, which was
pushed before this script existed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import explosive_plays as e

m, p, s, ROOT = e.m, e.p, e.s, e.ROOT
OOS = ROOT / 'research/out_of_sample_results'
PACK, REFERENCE = OOS / 'frozen_features_2013_2020.csv.gz', OOS / 'predictions.csv'
PROTOCOL = ROOT / 'research/EXPLOSIVE_SHARE.md'
FEATURE = 'd__for__explosive__share_of_net_yards'
ARMS = {'production': [], 'explosive_share': [FEATURE]}
LEVEL, SEED = .95, 20261013


def team_games(p_, year):
    """Explosive and net yards per team-game, with the box-score play filters."""
    p_ = p_[(p_.season_type == 'REG') & (m.numeric(p_, 'two_point_attempt') != 1)].copy()
    if 'play_deleted' in p_: p_ = p_[m.numeric(p_, 'play_deleted') != 1]
    p_ = p_[p_.play_type.ne('no_play') & p_.posteam.notna()]
    y = m.numeric(p_, 'yards_gained')
    passplay = (m.numeric(p_, 'pass_attempt') == 1) | (m.numeric(p_, 'sack') == 1)
    runplay = (m.numeric(p_, 'rush_attempt') == 1) & ~passplay
    snap = passplay | runplay
    big = (passplay & (y >= e.PASS_MIN)) | (runplay & (y >= e.RUSH_MIN))
    d = pd.DataFrame({'game_id': p_.game_id, 'team': p_.posteam, 'week': p_.week.astype(int),
                      'net_yards': y.where(snap, 0.).fillna(0.), 'explosive_yards': y.where(big, 0.).fillna(0.)})
    g = d.groupby(['game_id', 'team', 'week'], as_index=False)[['net_yards', 'explosive_yards']].sum()
    if (g.groupby('game_id').size() != 2).any(): raise ValueError(f'{year}: a game without exactly two offenses')
    g['season'] = int(year)
    return g


def load_team_games(cache):
    if cache.exists(): return pd.read_csv(cache)
    import nflreadpy as nfl
    cols = ['game_id', 'play_id', 'season_type', 'week', 'posteam', 'play_type', 'yards_gained',
            'pass_attempt', 'rush_attempt', 'sack', 'two_point_attempt', 'play_deleted']
    parts = []
    for year in range(2010, 2021):
        raw = m.fetch_upstream(lambda: nfl.load_pbp(year), f'play-by-play {year}')
        parts.append(team_games(m.normalize_teams(raw.select([c for c in cols if c in raw.columns]).to_pandas()), year))
        print(f'  play-by-play {year}: {len(parts[-1])} team-games', flush=True)
    g = pd.concat(parts, ignore_index=True)
    g.to_csv(cache, index=False, compression={'method': 'gzip', 'mtime': 0})
    return g


def profiles(f, g):
    rows = []
    for (year, week), games in f.groupby(['season', 'week'], sort=True):
        hist = g[m.before(g, year, week) & (g.season >= year - m.MAX_HISTORY_SEASONS)]
        ln, ld = float(hist.explosive_yards.mean()), float(hist.net_yards.mean())
        prof = {}
        for team in set(games.home) | set(games.away):
            h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
            age = np.arange(len(h) - 1, -1, -1, dtype=float)
            w = np.exp2(-age / e.HALF_LIFE) * np.power(m.OFFSEASON_RETENTION, year - h.season.to_numpy(float))
            prof[team] = ((w @ h.explosive_yards.to_numpy(float) + m.PRIOR_EQUIVALENT_GAMES * ln)
                          / (w @ h.net_yards.to_numpy(float) + m.PRIOR_EQUIVALENT_GAMES * ld))
        last = hist[hist.season == hist.season.max()]
        for r in games.itertuples():
            rows.append({'game_id': r.game_id, 'home_share': prof[r.home], 'away_share': prof[r.away],
                         FEATURE: prof[r.home] - prof[r.away],
                         'source_max_season': int(last.season.max()), 'source_max_week': int(last.week.max())})
    return pd.DataFrame(rows)


def run(out):
    out = out.resolve()
    if any(out == x or x in out.parents for x in (ROOT / 'data', ROOT / 'public')): raise ValueError('Protected output')
    out.mkdir(parents=True, exist_ok=True)
    p.SEED = SEED
    f = pd.read_csv(PACK)
    g = load_team_games(out / 'explosive_share_team_games.csv.gz')
    ex = profiles(f, g)
    cut = ex.merge(f[['game_id', 'season', 'week']], on='game_id', validate='one_to_one')
    if not ((cut.source_max_season < cut.season) | ((cut.source_max_season == cut.season) & (cut.source_max_week < cut.week))).all():
        raise ValueError('Lookahead: a profile uses the game week or later')
    f = f.merge(ex[['game_id', FEATURE]], on='game_id', validate='one_to_one')
    if not np.isfinite(f[FEATURE]).all(): raise ValueError('Missing explosive-share feature')
    eligible = (f.ready.astype(bool) & f['home won'].isin([0., 1.]) & np.isfinite(f.q) & np.isfinite(f[e.CONTEXTS]).all(axis=1)).to_numpy()
    scored = (f.season.between(2017, 2020) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q)
              & np.isfinite(f[e.CONTEXTS]).all(axis=1)).to_numpy()
    pred = f.loc[scored, ['game_id', 'season', 'week', 'home', 'away', 'home won', 'home_moneyline', 'away_moneyline', 'q']].copy()
    coefs = []
    for (year, week), rows in pred.groupby(['season', 'week'], sort=True):
        train = f[eligible & m.before(f, year, week).to_numpy()]
        for a, extra in ARMS.items():
            fitted = e.fit(train, int(year), int(week), extra)
            if (fitted['training_max_season'], fitted['training_max_week']) >= (year, week): raise ValueError('Fit lookahead')
            pred.loc[rows.index, a] = m.apply_fit(f.loc[rows.index], fitted)
            if extra: coefs.append({'season': int(year), 'week': int(week), FEATURE: float(fitted['beta'][len(e.BASE)])})
        if week == 1: print(f'Scoring season {year}', flush=True)
    if not np.isfinite(pred[list(ARMS)]).all().all(): raise ValueError('Incomplete probabilities')
    ref = pd.read_csv(REFERENCE).set_index('game_id')
    if len(ref) != len(pred): raise ValueError('Scored rows differ from the 2017-20 test')
    repro = float(abs(pred.production.to_numpy() - ref.loc[pred.game_id, 'production'].to_numpy()).max())
    if repro > 1e-7: raise ValueError(f'v1.16 reproduction failed ({repro:.3g})')
    c = pd.DataFrame(coefs)
    neg = float((c[FEATURE] < 0).mean())
    summ = e.summarize(pred, list(ARMS))
    pr = summ['pairs']['explosive_share']
    if pr['ll_gain'] <= 0 or neg < .5: verdict = 'falsified'
    elif pr['ll_gain_ci'][0] > 0 and pr['roi_delta_ci'][1] >= 0: verdict = 'candidate (owner decision; forward test required)'
    else: verdict = 'unresolved'
    by = {}
    for yr in range(2017, 2021):
        b = e.summarize(pred[pred.season == yr], list(ARMS))
        by[yr] = {'bets': b['bets'], 'production_units': b['arms']['production']['units'],
                  'explosive_share_units': b['arms']['explosive_share']['units'],
                  'favorite_units': b['arms']['market']['units'], 'll_gain': b['pairs']['explosive_share']['ll_gain']}
    pack_rows = f[f.season.between(2017, 2020)]
    info = {'basis': 'One-time 2017-2020 out-of-sample reconstruction (exposure disclosed in EXPLOSIVE_SHARE.md); not forward evidence',
            'revision_compared': m.SHADOW_REVISION, 'production_revision': m.REVISION, 'reproduction_max_error': repro,
            'verdict': verdict, 'coefficient': {'median': float(c[FEATURE].median()), 'share_negative': neg, 'fits': len(c)},
            'feature_corr_with_net_pass_ypp': float(pack_rows[FEATURE].corr(pack_rows['d__for__rates_core__net_pass_yards_per_pass_play'])),
            'league_share_2017_20': float(g[g.season.between(2017, 2020)].explosive_yards.sum() / g[g.season.between(2017, 2020)].net_yards.sum()),
            'summary': summ, 'by_season': by}
    pred.to_csv(out / 'predictions.csv', index=False); c.to_csv(out / 'coefficients.csv', index=False)
    (out / 'results.json').write_text(json.dumps(info, indent=2, allow_nan=False) + '\n')
    src = [Path(__file__), Path(e.__file__), PROTOCOL, ROOT / 'nfl_model.py', PACK, REFERENCE, out / 'explosive_share_team_games.csv.gz']
    (out / 'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in src}, indent=2) + '\n')
    A = summ['arms']; lo, hi = pr['ll_gain_ci']; rl, rh = pr['roi_delta_ci']
    lines = ['# Test 34: explosive share of offensive yardage, 2017–2020', '',
             f'Protocol: [EXPLOSIVE_SHARE.md](../EXPLOSIVE_SHARE.md), pushed before any number existed. Basis: {info["basis"]}.',
             f'v1.16 reproduction error {repro:.2g}. **Verdict: {verdict}.**', '',
             f"{summ['bets']} common priced flat 1u bets; {summ['binary_games']} binary games.", '',
             '| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | Brier |', '|---|---|---:|---:|---:|---:|---:|']
    for a in [*ARMS, 'market']:
        r = A[a]
        lines.append(f"| {a if a != 'market' else 'market favorite (same rows)'} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | "
                     f"{100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} | {100 * r['null_roi']:+.1f}% | {r['log_loss']:.5f} | {r['brier']:.5f} |")
    lines += ['', f"explosive_share − production: LL gain {pr['ll_gain']:+.5f} ± {pr['ll_gain_se']:.5f} (95% week-clustered [{lo:+.5f}, {hi:+.5f}]); "
              f"ROI {100 * pr['roi_delta']:+.2f} pts ± {100 * pr['roi_delta_se']:.2f} [{100 * rl:+.2f}, {100 * rh:+.2f}]; sides flipped {pr['side_flips']}.", '',
              f"Coefficient: median {info['coefficient']['median']:+.4f}, negative in {100 * neg:.0f}% of {len(c)} weekly fits. "
              f"Correlation with the offense net-yards-per-pass-play difference {info['feature_corr_with_net_pass_ypp']:+.2f}; "
              f"league explosive share of net yards {100 * info['league_share_2017_20']:.1f}%.", '',
              '| Season | Bets | v1.16 units | + share units | Favorite units | LL gain |', '|---|---:|---:|---:|---:|---:|']
    lines += [f"| {yr} | {b['bets']} | {b['production_units']:+.2f} | {b['explosive_share_units']:+.2f} | {b['favorite_units']:+.2f} | {b['ll_gain']:+.5f} |"
              for yr, b in by.items()]
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'research/explosive_share_results')
    run(ap.parse_args().output_dir)
