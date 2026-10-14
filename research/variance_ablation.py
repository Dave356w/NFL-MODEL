"""Variance-aware shrinkage and chronological group pruning; see VARIANCE_ABLATION.md."""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Pin SIMD/BLAS kernels before numpy loads: AVX-512 and AVX2 paths differ in the last ulp,
# which moves one L-BFGS-B stop (gtol 1e-8) by ~5e-7 and breaks the 1e-8 replay check.
os.environ.setdefault('NPY_DISABLE_CPU_FEATURES', 'AVX512F AVX512CD AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL AVX512_SPR')
os.environ.setdefault('OPENBLAS_CORETYPE', 'Haswell')

import numpy as np
import pandas as pd
from scipy.special import logit, expit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m
import feature_importance as fi
import residual_trends as t
import kalman_ratings as kr
import simplification as simple
import variance_inputs as vi

OUT = ROOT/'research/variance_ablation_results'
PRIMARY = ('reliability', 'chronological_prune')
GROUPS = {'drop_'+re.sub('[^a-z0-9]+', '_', k.lower()).strip('_'): v for k, v in fi.GROUPS.items()}
BASES = {'2015-16': (2015, 2016), '2017-22': tuple(range(2017, 2023)), '2023-25': (2023, 2024, 2025)}
Z_PRIMARY = float(norm.ppf(1-.05/2/2))
Z_GROUP = float(norm.ppf(1-.05/8/2))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_compressed(table, path):
    """Validate a complete gzip payload before atomically publishing a large audit export."""
    path = Path(path)
    payload = gzip.compress(table.to_csv(index=False, float_format='%.17g').encode(), mtime=0)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_bytes(payload)
    gzip.decompress(temporary.read_bytes())
    temporary.replace(path)


def weekly(pack, games, name, independent=False):
    """Fixed weekly refits. Dropping uses zero columns to preserve production penalty positions."""
    zero = GROUPS.get(name, [])
    if zero:
        pack = pack.assign(**{c: 0. for c in zero})
        games = games.assign(**{c: 0. for c in zero})
    rows = []; audit = []
    for (year, week), g in games.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        tr = pack[m.before(pack, year, week)]
        fit = m.fit_composite(tr, m.LEGACY_PRODUCT_RECIPE, year, week)
        pred = m.apply_fit(g, fit)
        error = 0.
        if independent:
            reference = kr.fit(tr, fit['names'], year, week)
            error = float(np.max(np.abs(pred-kr.predict(g, reference))))
            if error > 1e-9: raise ValueError('Independent fit mismatch')
        rows.append(g.assign(p16=pred))
        audit.append({'season': year, 'week': week, 'arm': name, 'training_games': fit['training_games'],
                      'training_max_season': fit['training_max_season'],
                      'training_max_week': fit['training_max_week_in_latest_season'],
                      'independent_max_error': error, **dict(zip(fit['names'], fit['beta']))})
    frame = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(frame), pd.DataFrame(audit)


def select_group(grid, year):
    """Choose solely from up to three completed seasons; never from the evaluation year's scores."""
    base = grid['production']
    base = base[base.season.between(year-3, year-1)&base.y.notna()]
    history = sorted(map(int, base.season.unique()))
    info = {'season': int(year), 'selection_max_season': max(history) if history else 0,
            'selection_seasons': ','.join(map(str, history)), 'selected': 'production', 'selection_games': len(base)}
    if len(history) < 2: return 'production', info, []
    rows = []
    losses = {}
    for name in ('production', *GROUPS):
        candidate = grid[name][['game_id', 'p']]
        j = base[['game_id', 'y', 'p', 'cluster']].merge(candidate, on='game_id', suffixes=('_base', ''), validate='one_to_one')
        if len(j) != len(base): raise ValueError('Earlier-season candidate coverage mismatch')
        loss = fi.ll(j.y, j.p).to_numpy()
        baseline_loss = fi.ll(j.y, j.p_base).to_numpy()
        gain, se = fi.cmean(baseline_loss-loss, j.cluster)
        losses[name] = pd.Series(loss, index=j.game_id)
        rows.append({'season': int(year), 'arm': name, 'mean_log_loss': float(loss.mean()),
                     'gain_vs_production': gain, 'paired_se': se, 'eligible': bool(name != 'production' and gain > se),
                     'removed_terms': len(GROUPS.get(name, [])), 'selection_max_season': max(history)})
    eligible = [r for r in rows if r['eligible']]
    if not eligible: return 'production', info, rows
    best = min(eligible, key=lambda r: (r['mean_log_loss'], r['arm']))['arm']
    choices = []
    for r in eligible:
        diff = losses[r['arm']]-losses[best]
        _, se = fi.cmean(diff.to_numpy(), base.set_index('game_id').loc[diff.index, 'cluster'])
        r['gap_from_best'] = float(diff.mean()); r['gap_se'] = se
        if diff.mean() <= se+1e-15: choices.append(r)
    chosen = sorted(choices, key=lambda r: (-r['removed_terms'], r['arm']))[0]['arm']
    info['selected'] = chosen
    return chosen, info, rows


def compare(base, arm, basis, name):
    rows = simple.compare(base, arm, basis, name)
    z = Z_PRIMARY if name in PRIMARY else Z_GROUP
    for r in rows:
        r.update(lo_x1000=r['ll_gain_x1000']-z*r['se_x1000'], hi_x1000=r['ll_gain_x1000']+z*r['se_x1000'],
                 roi_gain_lo=r['roi_gain']-z*r['roi_gain_cluster_se'], roi_gain_hi=r['roi_gain']+z*r['roi_gain_cluster_se'])
    return rows


def calibration(y, p):
    """Descriptive held-out calibration only; never changes forecasts or selections."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    x = logit(np.clip(p, 1e-8, 1-1e-8))
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.array([0., 1.])
    for _ in range(50):
        probability = expit(X@beta)
        gradient = X.T@(probability-y)/len(y)
        hessian = X.T@((probability*(1-probability))[:, None]*X)/len(y)
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-11: return float(beta[0]), float(beta[1])
    raise ValueError('Descriptive calibration did not converge')


def forecast_summary(frame, basis, arm):
    b = frame[frame.y.notna()]
    intercept, slope = calibration(b.y, b.p)
    delta = logit(np.clip(b.p, 1e-8, 1-1e-8))-logit(np.clip(b.q, 1e-8, 1-1e-8))
    return {'basis': basis, 'arm': arm, 'games': len(b), 'calibration_intercept': intercept,
            'calibration_slope': slope, 'departure_variance': float(delta.var(ddof=1)),
            'departure_abs_p95': float(np.quantile(np.abs(delta), .95)),
            'departure_abs_max': float(np.abs(delta).max())}


def nominate(scores, name):
    r = scores[(scores.arm == name)&(scores.context == 'all')].set_index('basis').reindex(BASES)
    if (r.ll_gain_x1000 > 0).all() and (r.lo_x1000 > 0).any():
        return 'Development nomination for a prospective test only'
    return 'No nomination; improvement unresolved'


def run(out=OUT):
    out = Path(out)
    for protected in (ROOT/'data', ROOT/'public', vi.INPUTS):
        if out.resolve() == protected.resolve() or protected.resolve() in out.resolve().parents:
            raise ValueError('Research cannot overwrite protected state/inputs')
    ledger = ROOT/'data/forward_predictions.jsonl'
    integrity = sha(ledger), m.config_signature()[0]
    noise = vi.load()
    grids = {}; audit_rows = []; reliability_rows = []; independent = []
    for pack_name, path in vi.PACKS.items():
        pack = pd.read_csv(path)
        shrunk, rel = vi.reliability(pack, noise[noise.pack == pack_name].drop(columns='pack'))
        reliability_rows.append(rel.assign(pack=pack_name))
        years = range(2014, 2021) if pack_name == 'oos' else range(2021, 2026)
        games = pack[pack.season.isin(years)]
        for name in ('production', 'reliability', *GROUPS):
            print(f'{pack_name}: {name}', flush=True)
            source = shrunk if name == 'reliability' else pack
            selected = source[source.game_id.isin(games.game_id)]
            d, a = weekly(source, selected, name, independent=name == 'production')
            grids.setdefault(name, []).append(d)
            audit_rows.append(a.assign(pack=pack_name))
            if name == 'production': independent.append(float(a.independent_max_error.max()))
    grid = {a: pd.concat(parts, ignore_index=True) for a, parts in grids.items()}
    reference = pd.read_csv(vi.REFERENCE)
    baseline = grid['production']
    j = reference.merge(baseline[['game_id', 'p', 'p16']], on='game_id', how='left', validate='one_to_one')
    if j.p.isna().any(): raise ValueError('Archived reference coverage mismatch')
    error = float(np.max(np.abs(np.where(j.version == 'p16', j.p16, j.p)-j.reference)))
    if error > 1e-9: raise ValueError('Archived baseline reproduction failed')
    choices = []; selection_rows = []; parts = []
    for year in range(2015, 2026):
        chosen, info, rows = select_group(grid, year)
        choices.append(info); selection_rows += rows
        parts.append(grid[chosen][grid[chosen].season == year])
    grid['chronological_prune'] = pd.concat(parts, ignore_index=True)
    scores = []; yearly = []; dispersion = []; variance = []
    rel = pd.concat(reliability_rows, ignore_index=True)
    all_predictions = []
    for basis, years in BASES.items():
        prod = baseline[baseline.season.isin(years)]
        for arm, data in grid.items():
            d = data[data.season.isin(years)]
            scores += compare(prod, d, basis, arm)
            dispersion.append(forecast_summary(d, basis, arm))
            all_predictions.append(d[['game_id', 'season', 'week', 'y', 'q', 'p16', 'p', 'units', 'side', 'fav_units', 'null_ev']].assign(basis=basis, arm=arm))
            for year, g in d.groupby('season'):
                yearly += [r for r in compare(prod[prod.season == year], g, str(int(year)), arm) if r['context'] == 'all']
        # Use the same source pack as the evaluated forecasts; no duplicate 2019-20 profiles.
        rows = rel[rel.season.isin(years)&((rel.pack == 'oos')&(rel.season <= 2020)|(rel.pack == 'modern')&(rel.season >= 2021))]
        rows = rows[rows.game_id.isin(prod.game_id)]
        raw = prod.set_index('game_id')
        shr = grid['reliability'].set_index('game_id')
        for feature, g in rows.groupby('feature'):
            ids = g.game_id
            variance.append({'basis': basis, 'feature': feature, 'games': len(g),
                             'raw_input_variance': float(raw.loc[ids, feature].var(ddof=1)),
                             'shrunk_input_variance': float(shr.loc[ids, feature].var(ddof=1)),
                             'sampling_variance_mean': float(g.row_sampling_variance.mean()),
                             'prior_signal_variance_mean': float(g.signal_variance.mean()),
                             'reliability_p10': float(g.reliability.quantile(.1)),
                             'reliability_median': float(g.reliability.median()),
                             'reliability_p90': float(g.reliability.quantile(.9)),
                             'share_reliability_zero': float((g.reliability == 0.).mean()),
                             'finite_noise_share': float(np.isfinite(g.row_sampling_variance).mean())})
    result = pd.DataFrame(scores)
    info = {'protocol_commit': vi.PROTOCOL_COMMIT, 'revision': m.REVISION, 'config_signature': integrity[1],
            'archived_max_error': error, 'independent_max_error': max(independent),
            'sampling_fidelity_max_error': float(pd.read_csv(vi.INPUTS/'fidelity.csv').max_abs_error.max()),
            'shrinkage_features': vi.MAIN, 'primary': PRIMARY,
            'verdicts': {a: nominate(result, a) for a in PRIMARY}}
    if integrity != (sha(ledger), m.config_signature()[0]): raise ValueError('Ledger/production identity changed')
    out.mkdir(parents=True, exist_ok=True)
    for name, table in [('arms', result), ('annual', pd.DataFrame(yearly)), ('forecast_variance', pd.DataFrame(dispersion)),
                        ('feature_variance', pd.DataFrame(variance)), ('pruning_choices', pd.DataFrame(choices)),
                        ('pruning_candidates', pd.DataFrame(selection_rows))]:
        table.to_csv(out/(name+'.csv'), index=False, float_format='%.17g')
    for name, table in [('predictions', pd.concat(all_predictions, ignore_index=True)),
                        ('fit_audit', pd.concat(audit_rows, ignore_index=True)), ('reliability_audit', rel)]:
        write_compressed(table, out/(name+'.csv.gz'))
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__), ROOT/'research/variance_inputs.py', ROOT/'research/VARIANCE_ABLATION.md',
               ROOT/'nfl_model.py', *[ROOT/'research'/f'{n}.py' for n in ('feature_importance', 'model_updates',
               'kalman_ratings', 'residual_trends', 'simplification')], vi.INPUTS/'manifest.json']
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in sources}, indent=2)+'\n')
    report(info, result, pd.DataFrame(variance), pd.DataFrame(dispersion), choices, out)
    return info, result


def report(info, result, variance, dispersion, choices, out):
    lines = ['# Variance-aware shrinkage and chronological ablation', '',
             'Fixed protocol `'+vi.PROTOCOL_COMMIT+'` pushed before execution. Exposed historical development; not native forward evidence.', '',
             '## Flat 1u returns and proper scores', '',
             '| Basis | Arm | Bets | Units | ROI ± SE | Favorite units | Market null | LL | Market LL | Brier |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    allr = result[result.context == 'all']
    for r in allr[allr.arm.isin(('production', *PRIMARY))].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.units:+.2f} | {100*r.roi:+.2f}% ± {100*r.roi_se:.2f} | '
                     f'{r.fav_units:+.2f} | {100*r.null:+.2f}% | {r.log_loss:.6f} | {r.market_log_loss:.6f} | {r.brier:.6f} |')
    lines += ['', '## Primary paired changes versus production', '',
              '97.5% normal week-cluster intervals, two primary comparisons per basis. Positive gain favors the challenger.', '',
              '| Basis | Arm | LL gain ×1000 [interval] | ROI gain pp [interval] | Units gain | Side flips |',
              '|---|---|---:|---:|---:|---:|']
    for r in allr[allr.arm.isin(PRIMARY)].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.ll_gain_x1000:+.3f} [{r.lo_x1000:+.3f}, {r.hi_x1000:+.3f}] | '
                     f'{100*r.roi_gain:+.2f} [{100*r.roi_gain_lo:+.2f}, {100*r.roi_gain_hi:+.2f}] | {r.units_vs_prod:+.2f} | {r.side_flips} |')
    lines += ['', '## Feature sampling variability and shrinkage', '',
              'Whole prior games are resampled together. Estimates hold the league prior fixed and are conditional on observed '
              'opponents/personnel. They do not isolate coaching or distinguish all genuine form changes from sampling noise. '
              'Raw variances have different units and must not be ranked across different statistics.', '',
              '| Feature | Median reliability 2015-16 | 2017-22 | 2023-25 |', '|---|---:|---:|---:|']
    for feature in vi.MAIN:
        r = variance[variance.feature == feature].set_index('basis')
        lines.append('| '+fi.short(feature)+' | '+' | '.join(f'{r.loc[b, "reliability_median"]:.3f}' for b in BASES)+' |')
    lines += ['', 'Availability, QB, site and pass interactions are not assigned fabricated bootstrap measurement variances. '
              'Their grouped refit ablations are included below. Coefficient trajectories are in fit_audit.csv.gz; '
              'temporal coefficient movement includes actual model adaptation, not just uncertainty.', '',
              '## Fixed group-drop diagnostics', '',
              'Each cell: LL gain ×1000 on removing/refitting the group [99.375% interval]; units change. '
              'These exposed diagnostic arms do not choose the pruning challenger on evaluation results.', '',
              '| Group removed | 2015-16 | 2017-22 | 2023-25 |', '|---|---:|---:|---:|']
    for arm in GROUPS:
        r = allr[allr.arm == arm].set_index('basis')
        lines.append('| '+arm.removeprefix('drop_')+' | '+' | '.join(
            f'{r.loc[b, "ll_gain_x1000"]:+.3f} [{r.loc[b, "lo_x1000"]:+.3f}, {r.loc[b, "hi_x1000"]:+.3f}]; {r.loc[b, "units_vs_prod"]:+.2f}u' for b in BASES)+' |')
    lines += ['', '## Chronological pruning choices', '',
              'At most one group removed, based on up to three earlier completed OOF seasons; a minimum of two is required. '
              'The earlier-season paired one-SE benefit gate precedes the within-one-SE simplicity choice.', '',
              '| Evaluation season | Earlier seasons | Selected |', '|---|---|---|']
    for r in choices: lines.append(f'| {r["season"]} | {r["selection_seasons"]} | {r["selected"]} |')
    lines += ['', '## Forecast dispersion and calibration', '',
              'Departure variance is variance of final model-minus-market log odds. Lower dispersion is not itself better forecasting. '
              'Calibration fits are descriptive and never adjust these predictions.', '',
              '| Basis | Arm | Departure variance | Calibration intercept | Calibration slope |', '|---|---|---:|---:|---:|']
    for r in dispersion[dispersion.arm.isin(('production', *PRIMARY))].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.departure_variance:.5f} | {r.calibration_intercept:+.3f} | {r.calibration_slope:.3f} |')
    lines += ['', '## Decisions and limits', '']
    for a, v in info['verdicts'].items(): lines.append(f'- **{a}**: {v}.')
    lines += ['', 'Archived baseline maximum error '+f'{info["archived_max_error"]:.2e}'+', independent fit maximum error '+
              f'{info["independent_max_error"]:.2e}'+', reconstructed main-input maximum error '+f'{info["sampling_fidelity_max_error"]:.2e}'+'.', '',
              'Only main raw h8 box/peak inputs receive reliability shrinkage. The existing four pseudo-games and fit standardization '
              'remain; constant per-feature scaling would cancel, so point-in-time factors vary across rows. '
              '128 multiplier-bootstrap draws are a fixed approximation. Selection and source/design uncertainty are not fully reflected '
              'in score intervals. Historical quotes have unknown capture times. Return SE is per-game; paired intervals cluster by week. '
              'Ties push in returns and are omitted from binary scores. Market pick-ems follow existing paired directional conventions. '
              'No current-season or native-forward result is claimed. No production recipe, forecast, signature or native ledger changed.', '',
              'Full tables include annual results, all group ablations, weekly coefficients/cutoffs, variance components and per-game forecasts. '
              'Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/variance_ablation.py`.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    run(parser.parse_args().out)
