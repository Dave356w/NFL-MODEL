"""Frozen game-block bootstrap uncertainty for VARIANCE_ABLATION.md; no model adoption."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m
import feature_importance as fi
import residual_trends as t
import form_windows as fw

INPUTS = ROOT/'research/variance_ablation_inputs'
NOISE = INPUTS/'sampling_variance.csv.gz'
REFERENCE = INPUTS/'production_reference.csv'
PROTOCOL_COMMIT = '410bbd2bb30fbc9fb3db19f90e98fead9a5be9a8'
BOOTSTRAPS = 128
SEED = 20261014
MAIN = fi.GROUPS['offense box rates']+fi.GROUPS['defense box rates']+fi.GROUPS['lead/deficit peaks']
PACKS = {'oos': t.OOS_PACK, 'modern': t.T36_PACK}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_files():
    return [Path(__file__), ROOT/'research/VARIANCE_ABLATION.md', ROOT/'nfl_model.py',
            ROOT/'research/form_windows.py', ROOT/'research/feature_importance.py', fw.BOXES, *PACKS.values()]


def team_draws(h, league, jitter):
    """First row is the original profile; remaining rows share whole-game multipliers.
    League pseudo-game means are fixed, so this is conditional sampling sensitivity."""
    n = len(h)
    w = np.exp2(-np.arange(n-1, -1, -1, dtype=float)/8.)
    if n: w *= np.power(m.OFFSEASON_RETENTION, int(h.attrs['target_year'])-h.season.to_numpy(float))
    W = jitter*w[None, :]
    vals = []
    for name in MAIN:
        if name in m.PEAK_FEATURES:
            a = h[name.removeprefix('d__')].to_numpy(float)
            val = (W@a)/(W.sum(axis=1)+m.PRIOR_EQUIVALENT_GAMES)
        else:
            _, role, _, metric = name.split('__')
            num, den, mult = m.RATES_CORE[metric]
            prefix = 'opp_' if role == 'allowed' else ''
            a = h[prefix+num].to_numpy(float)
            b = np.ones(n) if den is None else h[prefix+den].to_numpy(float)
            la = league[num].to_numpy(float)
            lb = np.ones(len(league)) if den is None else league[den].to_numpy(float)
            lok = np.isfinite(la)&np.isfinite(lb)&(lb > 0)
            if not lok.any(): val = np.full(len(W), np.nan)
            else:
                ok = np.isfinite(a)&np.isfinite(b)&(b > 0)
                A = W[:, ok]@a[ok]+m.PRIOR_EQUIVALENT_GAMES*la[lok].mean()
                D = W[:, ok]@b[ok]+m.PRIOR_EQUIVALENT_GAMES*lb[lok].mean()
                val = mult*A/D
        vals.append(val)
    return np.column_stack(vals)


def bootstrap_pack(box, pack, draws=BOOTSTRAPS):
    """Build uncertainty using strictly prior weeks and the pack's actual history universe."""
    box = box[box.game_id.isin(pack.game_id)].copy()
    opponent = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    both = box.merge(opponent, on=['game_id', 'opponent'], how='left', validate='one_to_one')
    rows = []; audit = []
    for (year, week), games in pack[pack.season <= 2025].groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        hist = both[m.before(both, year, week)&(both.season >= year-m.MAX_HISTORY_SEASONS)]
        gids = sorted(hist.game_id.unique()); lookup = {g: i for i, g in enumerate(gids)}
        rng = np.random.default_rng(SEED+year*100+week)
        multipliers = np.vstack([np.ones(len(gids)), rng.poisson(1., size=(draws, len(gids)))])
        team = {}
        for name in sorted(set(games.home)|set(games.away)):
            h = hist[hist.team == name].sort_values(['season', 'week', 'game_id']).copy()
            h.attrs['target_year'] = year
            team[name] = team_draws(h, hist, multipliers[:, [lookup[g] for g in h.game_id]])
        max_error = 0.; missing_mismatch = 0
        for g in games.to_dict('records'):
            d = team[g['home']]-team[g['away']]
            ref = np.array([g[c] for c in MAIN], float)
            finite = np.isfinite(ref)&np.isfinite(d[0])
            missing_mismatch += int(np.count_nonzero(np.isfinite(ref) != np.isfinite(d[0])))
            if finite.any(): max_error = max(max_error, float(np.max(np.abs(ref[finite]-d[0, finite]))))
            var = np.var(d[1:], axis=0, ddof=1)
            rows.append({'game_id': g['game_id'], **dict(zip(MAIN, var))})
        audit.append({'season': year, 'week': week, 'games': len(games), 'history_games': len(gids),
                      'max_abs_error': max_error, 'missing_mismatch': missing_mismatch,
                      'history_max_season': int(hist.season.max()) if len(hist) else 0,
                      'history_max_week': int(hist[hist.season == hist.season.max()].week.max()) if len(hist) else 0})
        if year >= 2014 and (max_error > 1e-8 or missing_mismatch):
            raise ValueError(f'Frozen feature fidelity failed at {year}/{week}: {max_error:g}, missing {missing_mismatch}')
    return pd.DataFrame(rows), pd.DataFrame(audit)


def prepare():
    if NOISE.exists(): raise ValueError('Uncertainty already frozen; refusing overwrite')
    INPUTS.mkdir(parents=True, exist_ok=True)
    box = pd.read_csv(fw.BOXES)
    noise = []; audits = []
    for name, path in PACKS.items():
        print('Bootstrap '+name, flush=True)
        n, a = bootstrap_pack(box, pd.read_csv(path))
        noise.append(n.assign(pack=name)); audits.append(a.assign(pack=name))
    pd.concat(noise, ignore_index=True).to_csv(NOISE, index=False, float_format='%.17g', compression={'method': 'gzip', 'mtime': 0})
    pd.concat(audits, ignore_index=True).to_csv(INPUTS/'fidelity.csv', index=False, float_format='%.17g')
    old = pd.read_csv(t.OOS_PRED)
    recent = pd.read_csv(t.RETRO)
    held = pd.read_csv(t.HELDOUT)
    refs = [old[['game_id', 'production']].rename(columns={'production': 'reference'}).assign(version='p16'),
            recent[recent.season.isin([2021, 2022])][['game_id', 'model_wp']].rename(columns={'model_wp': 'reference'}).assign(version='p18'),
            held[['game_id', 'model_wp']].rename(columns={'model_wp': 'reference'}).assign(version='p16')]
    pd.concat(refs, ignore_index=True).to_csv(REFERENCE, index=False, float_format='%.17g')
    manifest = {'protocol_commit': PROTOCOL_COMMIT, 'draws': BOOTSTRAPS, 'seed': SEED,
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in source_files()},
                'frozen': {str(p.relative_to(ROOT)): sha(p) for p in (NOISE, INPUTS/'fidelity.csv', REFERENCE)},
                'reference_origins': {str(p.relative_to(ROOT)): sha(p) for p in (t.OOS_PRED, t.RETRO, t.HELDOUT)}}
    (INPUTS/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


def load():
    manifest = json.loads((INPUTS/'manifest.json').read_text())
    for path, digest in {**manifest['sources'], **manifest['frozen']}.items():
        if sha(ROOT/path) != digest: raise ValueError('Frozen uncertainty source/hash changed: '+path)
    return pd.read_csv(NOISE)


def reliability(pack, noise, minimum=64):
    """Every row's shrinkage uses only its own earlier reference weeks, never the fit cutoff."""
    merged = pack.merge(noise, on='game_id', how='left', suffixes=('', '__noise'), validate='one_to_one')
    out = pack.copy(); records = []
    for (year, week), games in merged.groupby(['season', 'week'], sort=True):
        ref = merged[m.before(merged, int(year), int(week))&(merged.season >= year-3)&merged.ready.astype(bool)
                     &np.isfinite(merged.q)&np.isfinite(merged[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1)]
        for col in MAIN:
            noise_col = col+'__noise'
            ok = np.isfinite(ref[col])&np.isfinite(ref[noise_col])
            current_noise = games[noise_col].to_numpy(float)
            V = float(ref.loc[ok, col].var(ddof=1)) if ok.sum() > 1 else np.nan
            N = float(ref.loc[ok, noise_col].mean()) if ok.any() else np.nan
            S = max(V-N, 0.) if np.isfinite(V) and np.isfinite(N) else np.nan
            r = np.ones(len(games))
            if ok.sum() >= minimum:
                valid = np.isfinite(current_noise)
                r[valid] = np.divide(S, S+current_noise[valid], out=np.zeros(valid.sum()), where=S+current_noise[valid] > 0)
            out.loc[games.index, col] = games[col].to_numpy(float)*r
            for idx, gid in enumerate(games.game_id):
                records.append({'game_id': gid, 'season': int(year), 'week': int(week), 'feature': col,
                                'reference_n': int(ok.sum()), 'reference_max_season': int(ref.season.max()) if len(ref) else 0,
                                'reference_max_week': int(ref[ref.season == ref.season.max()].week.max()) if len(ref) else 0,
                                'observed_variance': V, 'mean_sampling_variance': N, 'signal_variance': S,
                                'row_sampling_variance': float(current_noise[idx]), 'reliability': float(r[idx])})
    return out, pd.DataFrame(records)


if __name__ == '__main__':
    prepare()
