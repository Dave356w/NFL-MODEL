"""Fixed three-arm simplification study; see SIMPLIFICATION.md. No network or production writes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m
import feature_importance as fi
import residual_trends as t
import model_updates as mu
import kalman_ratings as kr

OUT = ROOT/'research/simplification_results'
PROTOCOL_COMMIT = 'e4a7959ddacb3a0336e0ca282b8d1681dd3430f7'
ARMS = {'no_peaks': list(m.PEAK_FEATURES),
        'no_peaks_site': list(m.PEAK_FEATURES)+['site'],
        'no_pass_tails': [n for n in m.PRODUCT_CONTEXT_NAMES if n.startswith('pass_1sd_')]}
DIAGNOSTIC = '2026 wk1-5 (diagnostic)'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(prod, arm, basis, name):
    """Require identical forecast coverage; paired ROI uses the identical directional bets."""
    if prod.game_id.duplicated().any() or arm.game_id.duplicated().any():
        raise ValueError('Duplicate game IDs')
    if set(prod.game_id) != set(arm.game_id):
        raise ValueError('Forecast coverage mismatch')
    if not np.isfinite(arm.p).all():
        raise ValueError('Nonfinite challenger forecast')
    rows = kr.compare(prod, arm, basis, name)
    j = prod[['game_id', 'cluster', 'total_line', 'bet', 'units']].merge(
        arm[['game_id', 'units']], on='game_id', suffixes=('', '_arm'), validate='one_to_one')
    for r in rows:
        b = j[t.context_mask(j.total_line, r['context']) & j.bet & j.units_arm.notna()]
        gain, se = fi.cmean(b.units_arm-b.units, b.cluster)
        r.update(roi_gain=gain, roi_gain_cluster_se=se,
                 roi_gain_lo=gain-kr.Z*se, roi_gain_hi=gain+kr.Z*se)
        scored = arm[t.context_mask(arm.total_line, r['context']) & arm.y.notna()]
        r.update(log_loss=float(mu.ll(scored.y, scored.p).mean()),
                 market_log_loss=float(mu.ll(scored.y, scored.q).mean()),
                 brier=float(((scored.p-scored.y)**2).mean()))
    return rows


def run(out=OUT):
    out = Path(out)
    for protected in (ROOT/'data', ROOT/'public'):
        if out.resolve() == protected.resolve() or protected.resolve() in out.resolve().parents:
            raise ValueError('Research cannot write data/ or public/')
    out.mkdir(parents=True, exist_ok=True)
    ledger = ROOT/'data/forward_predictions.jsonl'
    before = sha(ledger), m.config_signature()[0]
    parts = {**fi.basis_parts(), DIAGNOSTIC: mu.extra_parts()[DIAGNOSTIC]}
    prod = {}; frames = {}; rows = []; annual = []
    for basis, p in parts.items():
        print(f'{basis}: production', flush=True)
        prod[basis] = fi.forecasts(p)
    reproduction = fi.reproduction({b: prod[b] for b in fi.BASES})
    for basis, p in parts.items():
        frames[basis, 'production'] = prod[basis]
        rows += compare(prod[basis], prod[basis], basis, 'production')
        for name, zero in ARMS.items():
            print(f'{basis}: {name}', flush=True)
            arm = fi.forecasts(p, zero)
            frames[basis, name] = arm
            rows += compare(prod[basis], arm, basis, name)
        for (b, name), d in list(frames.items()):
            if b != basis: continue
            for year, g in d.groupby('season'):
                pp = prod[basis][prod[basis].season == year]
                annual += [r for r in compare(pp, g, str(int(year)), name) if r['context'] == 'all']
    if before != (sha(ledger), m.config_signature()[0]):
        raise ValueError('Ledger or production identity changed')
    res = pd.DataFrame(rows)
    res.to_csv(out/'arms.csv', index=False, float_format='%.17g')
    pd.DataFrame(annual).to_csv(out/'annual.csv', index=False, float_format='%.17g')
    pd.concat([d[['game_id', 'season', 'week', 'y', 'q', 'p16', 'p', 'side', 'units', 'fav_units', 'null_ev']]
               .assign(basis=b, arm=a) for (b, a), d in frames.items()]).to_csv(
                   out/'predictions.csv.gz', index=False, float_format='%.17g', compression={'method': 'gzip', 'mtime': 0})
    info = {'protocol_commit': PROTOCOL_COMMIT, 'revision': m.REVISION, 'config_signature': before[1],
            'ledger_sha256': before[0], 'level': kr.LEVEL, 'removed': ARMS,
            'reproduction_max_error': reproduction,
            'verdicts': {a: kr.verdict(res[res.arm == a]) for a in ARMS}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__), ROOT/'research/SIMPLIFICATION.md', ROOT/'nfl_model.py',
               ROOT/'research/feature_importance.py', ROOT/'research/residual_trends.py',
               ROOT/'research/model_updates.py', ROOT/'research/kalman_ratings.py',
               t.OOS_PACK, t.T36_PACK, t.OOS_PRED, t.HELDOUT, t.RETRO, t.TOTALS]
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in sources}, indent=2)+'\n')
    report(info, res, out)
    return info, res


def report(info, res, out):
    lines = ['# Fixed model simplification results', '',
             f"Protocol committed before this run: `{PROTOCOL_COMMIT}`. All history was already exposed; development evidence only.", '',
             'Production v1.18, its v1.16 shadow lock and native snapshots are unchanged.', '',
             'Baseline reproduction maximum errors: '+', '.join(f'{b}: {v:.2e}' for b, v in info['reproduction_max_error'].items())+'.', '',
             '## Flat 1u returns (goal metric)', '',
             '| Basis | Arm | Bets | W-L-P | Units | ROI ± SE | Favorite units | Market-null ROI | Binary n | LL | Market LL | Brier |',
             '|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    allr = res[res.context == 'all']
    for r in allr.itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.w}-{r.l}-{r.p} | {r.units:+.2f} | '
                     f'{100*r.roi:+.2f}% ± {100*r.roi_se:.2f} | {r.fav_units:+.2f} | {100*r.null:+.2f}% | '
                     f'{r.n} | {r.log_loss:.6f} | {r.market_log_loss:.6f} | {r.brier:.6f} |')
    lines += ['', '## Paired comparisons with production', '',
              'Intervals are 98.33%, normal week-cluster intervals, adjusted for three arms within a basis. '
              'Annual and total-band slices are descriptive. No across-basis multiplicity claim.', '',
              '| Basis | Arm | LL gain ×1000 [interval] | Brier gain ×1000 | ROI gain pp [interval] | Units gain | Side flips |',
              '|---|---|---:|---:|---:|---:|---:|']
    for r in allr[allr.arm != 'production'].itertuples():
        lines.append(f'| {r.basis} | {r.arm} | {r.ll_gain_x1000:+.3f} [{r.lo_x1000:+.3f}, {r.hi_x1000:+.3f}] | '
                     f'{r.brier_gain_x1000:+.3f} | {100*r.roi_gain:+.2f} [{100*r.roi_gain_lo:+.2f}, {100*r.roi_gain_hi:+.2f}] | '
                     f'{r.units_vs_prod:+.2f} | {r.side_flips} |')
    lines += ['', '## Development screen', '']
    for a, v in info['verdicts'].items(): lines.append(f'- **{a}**: {v}.')
    lines += ['', 'Worth a forward shadow test requires positive LL gain on all three historical bases and a positive '
              'lower interval bound on at least one. Nonpositive gain on two bases means not supported; otherwise unresolved. '
              'This does not establish return superiority or automatically nominate/adopt an arm.', '',
              '## Limits and reproduction', '',
              'Historical schedule quotes have unknown capture times. Repeated design on these periods is not accounted for '
              'by the intervals. The 2026 reconstruction is diagnostic, not native forward evidence. Ties push in returns and '
              'are omitted from binary scores. Return SE is per-game; paired ROI-gain intervals cluster by week. '
              'Forecast coverage is checked before comparison; directional returns use paired eligible games.', '',
              'Per-game forecasts (17-digit precision), annual slices, total-band comparisons and source/input hashes are '
              'in `predictions.csv.gz`, `annual.csv`, `arms.csv`, and `provenance.json`.', '',
              'Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/simplification.py`.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    run(parser.parse_args().out)
