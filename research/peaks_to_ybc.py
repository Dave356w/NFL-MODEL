"""Fixed lead/deficit-to-YBC replacement; see PEAKS_TO_YBC.md. Offline research only."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m
import feature_importance as fi
import residual_trends as t
import kalman_ratings as kr
import yards_before_contact as ybc
import simplification as simple

INPUTS = ROOT/'research/peaks_to_ybc_inputs'
REFERENCE = INPUTS/'production_reference.csv'
OUT = ROOT/'research/peaks_to_ybc_results'
PROTOCOL_COMMIT = 'e5538ef06d0e315adb7bffd51105db55cace41c5'
PRODUCTION = list(ybc.PRODUCTION)
YBC = ['d_ybc_off', 'd_ybc_def']
NO_PEAKS = [n for n in PRODUCTION if n not in m.PEAK_FEATURES]
ARMS = {'production': PRODUCTION, 'no_peaks': NO_PEAKS, 'peaks_to_ybc': NO_PEAKS+YBC}
BASES = ('2021-22', '2023-25')
DIAG = '2026 wk1-5 (diagnostic)'
LEVEL = 1-.05/2
Z = float(norm.ppf((1+LEVEL)/2))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze_reference():
    """One-time capture of existing production references, not challenger outcomes."""
    if REFERENCE.exists(): raise ValueError('Reference already frozen; refusing overwrite')
    INPUTS.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(t.RETRO)
    d = d[d.season.between(2021, 2025)][['game_id', 'season', 'week', 'model_wp']]
    if d.game_id.duplicated().any(): raise ValueError('Duplicate archived reference')
    d.to_csv(REFERENCE, index=False, float_format='%.17g')
    (INPUTS/'provenance.json').write_text(json.dumps({
        'source': str(t.RETRO.relative_to(ROOT)), 'source_sha256': sha(t.RETRO),
        'reference_sha256': sha(REFERENCE), 'protocol_commit': PROTOCOL_COMMIT,
        'note': 'Snapshot of archived production probabilities before the new replacement was scored.'}, indent=2)+'\n')


def frame(pack, games, profiles, names, verify_production=False):
    if games.game_id.duplicated().any(): raise ValueError('Duplicate evaluation game')
    pk = pack.merge(profiles, on='game_id', how='left', validate='one_to_one')
    gm = games.merge(profiles, on='game_id', how='left', validate='one_to_one')
    if not np.isfinite(gm[YBC].to_numpy(float)).all():
        raise ValueError('Missing evaluation YBC profile')
    rows = []; audits = []; errors = []
    for (year, week), g in gm.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        train = pk[m.before(pk, year, week)]
        fit = kr.fit(train, names, year, week)
        p16 = kr.predict(g, fit)
        eligible = train[kr.eligible(train)]
        if not np.isfinite(eligible[YBC].to_numpy(float)).all():
            raise ValueError('Missing training YBC profile on an eligible row')
        error = 0.
        if verify_production:
            independent = m.fit_composite(train, m.LEGACY_PRODUCT_RECIPE, year, week)
            error = float(np.max(np.abs(p16-m.apply_fit(g, independent))))
            if error > 1e-9: raise ValueError('Independent production fit mismatch')
        errors.append(error)
        audit = {'season': year, 'week': week, 'training_games': len(eligible),
                 'training_max_season': int(eligible.season.max()),
                 'training_max_week': int(eligible[eligible.season == eligible.season.max()].week.max()),
                 'evaluation_games': len(g), 'independent_fit_max_error': error}
        for n in YBC:
            if n in names: audit[n+'_beta_per_sd'] = float(fit['beta'][names.index(n)])
        audits.append(audit)
        rows.append(g.assign(p16=p16))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d), pd.DataFrame(audits), max(errors)


def compare(control, challenger, basis, name):
    rows = simple.compare(control, challenger, basis, name)
    for r in rows:
        r.update(lo_x1000=r['ll_gain_x1000']-Z*r['se_x1000'],
                 hi_x1000=r['ll_gain_x1000']+Z*r['se_x1000'],
                 roi_gain_lo=r['roi_gain']-Z*r['roi_gain_cluster_se'],
                 roi_gain_hi=r['roi_gain']+Z*r['roi_gain_cluster_se'])
    return rows


def screen(comparisons):
    for control in ('production', 'no_peaks'):
        a = comparisons[(comparisons.arm == control) & (comparisons.context == 'all')].set_index('basis').reindex(BASES)
        if not ((a.ll_gain_x1000 > 0).all() and (a.lo_x1000 > 0).any()):
            return 'No nomination: development support unresolved'
    return 'Worth a prospective shadow test only; no production adoption'


def run(out=OUT):
    out = Path(out)
    for protected in (ROOT/'data', ROOT/'public'):
        if out.resolve() == protected.resolve() or protected.resolve() in out.resolve().parents:
            raise ValueError('Research cannot write data/ or public/')
    frozen = json.loads((INPUTS/'provenance.json').read_text())
    if sha(REFERENCE) != frozen['reference_sha256']: raise ValueError('Frozen reference hash changed')
    ledger = ROOT/'data/forward_predictions.jsonl'
    integrity = sha(ledger), m.config_signature()[0]
    pack = pd.read_csv(t.T36_PACK)
    prof = ybc.profiles(pd.read_csv(ybc.TEAM_GAMES), pack[['game_id', 'season', 'week', 'home', 'away']],
                        specs={'ybc': ('ybc', 'carries')})
    parts = {BASES[0]: pack[pack.season.isin([2021, 2022])],
             BASES[1]: pack[pack.season.between(2023, 2025)],
             DIAG: pack[(pack.season == 2026) & pack.week.between(1, 5) & pack['home won'].notna()]}
    reference = pd.read_csv(REFERENCE)
    frames = {}; audits = []; rows = []; comparisons = []; annual = []; repro = {}
    for basis, games in parts.items():
        for name, names in ARMS.items():
            print(f'{basis}: {name}', flush=True)
            d, audit, error = frame(pack, games, prof, names, verify_production=name == 'production')
            frames[basis, name] = d
            audits.append(audit.assign(basis=basis, arm=name))
            if name == 'production':
                repro[basis+' independent'] = error
                if basis in BASES:
                    j = d.merge(reference[['game_id', 'model_wp']], on='game_id', how='left', validate='one_to_one')
                    if j.model_wp.isna().any(): raise ValueError('Archived production coverage mismatch')
                    repro[basis+' archived'] = float(np.max(np.abs(j.p-j.model_wp)))
                    if repro[basis+' archived'] > 1e-9: raise ValueError('Archived production mismatch')
        production = frames[basis, 'production']
        for name in ARMS:
            d = frames[basis, name]
            rows += compare(production, d, basis, name)
            for year, g in d.groupby('season'):
                annual += [r for r in compare(production[production.season == year], g, str(int(year)), name) if r['context'] == 'all']
        for control in ('production', 'no_peaks'):
            comparisons += compare(frames[basis, control], frames[basis, 'peaks_to_ybc'], basis, control)
    if integrity != (sha(ledger), m.config_signature()[0]): raise ValueError('Production identity or ledger changed')
    result, contrasts = pd.DataFrame(rows), pd.DataFrame(comparisons)
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out/'arms.csv', index=False, float_format='%.17g')
    contrasts.to_csv(out/'contrasts.csv', index=False, float_format='%.17g')
    pd.DataFrame(annual).to_csv(out/'annual.csv', index=False, float_format='%.17g')
    pd.concat(audits, ignore_index=True).to_csv(out/'fit_audit.csv', index=False, float_format='%.17g')
    pd.concat([d[['game_id', 'season', 'week', 'y', 'q', 'p16', 'p', 'units', 'side', 'fav_units', 'null_ev']]
               .assign(basis=b, arm=a) for (b, a), d in frames.items()]).to_csv(
                   out/'predictions.csv.gz', index=False, float_format='%.17g', compression={'method': 'gzip', 'mtime': 0})
    prof.to_csv(out/'profiles.csv.gz', index=False, float_format='%.17g', compression={'method': 'gzip', 'mtime': 0})
    info = {'revision': m.REVISION, 'config_signature': integrity[1], 'protocol_commit': PROTOCOL_COMMIT,
            'level': LEVEL, 'terms': {k: len(v) for k, v in ARMS.items()}, 'reproduction': repro,
            'coverage': {b: {'games': len(g), 'with_finite_ybc': len(g)} for b, g in parts.items()},
            'verdict': screen(contrasts)}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__), ROOT/'research/PEAKS_TO_YBC.md', ROOT/'nfl_model.py',
               *[ROOT/'research'/f'{n}.py' for n in ('yards_before_contact', 'form_windows', 'feature_importance',
                   'residual_trends', 'kalman_ratings', 'model_updates', 'simplification')],
               t.T36_PACK, ybc.TEAM_GAMES, t.TOTALS, REFERENCE, INPUTS/'provenance.json']
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in sources}, indent=2)+'\n')
    report(info, result, contrasts, out)
    return info, result, contrasts


def report(info, result, contrasts, out):
    lines = ['# Replace lead/deficit peaks with yards before contact', '',
             f'Protocol `{PROTOCOL_COMMIT}` pushed before this replacement was scored. All history already exposed; development evidence only.', '',
             '29-term production vs 27-term no-peaks control vs 29-term replacement with offensive and defensive-allowed YBC/carry. '
             'Rush efficiency and every other production input remain in the replacement.', '',
             '## Flat 1u returns and probability scores', '',
             '| Basis | Arm | Bets | W-L-P | Units | ROI ± SE | Favorite units | Market-null ROI | Binary n | LL | Market LL | Brier |',
             '|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in result[result.context == 'all'].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.w}-{r.l}-{r.p} | {r.units:+.2f} | '
                     f'{100*r.roi:+.2f}% ± {100*r.roi_se:.2f} | {r.fav_units:+.2f} | {100*r.null:+.2f}% | '
                     f'{r.n} | {r.log_loss:.6f} | {r.market_log_loss:.6f} | {r.brier:.6f} |')
    lines += ['', '## Replacement minus each control', '',
              'Positive gains favor replacement. Intervals: 97.5%, normal week-cluster, two contrasts within each basis. '
              'No across-era/metric confirmation claim; annual and total-band slices are descriptive.', '',
              '| Basis | Control | LL gain ×1000 [interval] | Brier gain ×1000 | ROI gain pp [interval] | Units gain | Side flips |',
              '|---|---|---:|---:|---:|---:|---:|']
    for r in contrasts[contrasts.context == 'all'].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.ll_gain_x1000:+.3f} [{r.lo_x1000:+.3f}, {r.hi_x1000:+.3f}] | '
                     f'{r.brier_gain_x1000:+.3f} | {100*r.roi_gain:+.2f} [{100*r.roi_gain_lo:+.2f}, {100*r.roi_gain_hi:+.2f}] | '
                     f'{r.units_vs_prod:+.2f} | {r.side_flips} |')
    lines += ['', '## Verdict and checks', '', info['verdict']+'.', '',
              'A nomination requires positive LL gains on both historical bases against each comparator, with a positive '
              'lower bound on at least one historical basis for each comparator. No automatic production adoption.', '',
              'Reproduction maximum errors: '+', '.join(f'{k}: {v:.2e}' for k, v in info['reproduction'].items())+'.', '',
              'All evaluation and eligible training rows have finite YBC. Profiles use only earlier weeks. '
              'Per-game forecasts, full-precision profiles, weekly fit cutoff/coefficient audits, annual slices, '
              'contrasts by total band and source/input hashes accompany this report.', '',
              '## Limits', '',
              'PFR charting begins in 2018; no invented pre-2021 test. Charts are retrospective source snapshots with no '
              'independent publication timestamps. Historical moneylines are the frozen schedule quotes with unknown capture times. '
              '2026 weeks 1-5 are reconstructed diagnostics, not native forward evidence. Repeated historical design is not '
              'accounted for by the intervals. Ties push in returns and are omitted from binary scores. '
              'Paired directional bets follow repository conventions, including excluding a market pick-em comparator. '
              'No recipe, production forecast or ledger was changed.', '',
              'Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/peaks_to_ybc.py`.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-reference', action='store_true')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    if args.freeze_reference: freeze_reference()
    else: run(args.out)
