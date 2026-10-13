"""Availability weighting candidates (research/AVAILABILITY_WEIGHTS.md). Research only.

    python research/availability_weights.py --prepare   # downloads raw inputs, freezes rebuilt columns
    python research/availability_weights.py             # replays both bases from the frozen columns

Candidate A weights a Questionable player by his final practice participation (Test 28's 2019-22
calibration); candidate B splits WR/TE and CB/S into separate units. Only the availability unit
columns are rebuilt, with production's availability_table; every other input is the frozen value.
Production v1.16, its recipe and the forward ledger are unchanged.
"""
import argparse
import hashlib
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'research')]
import nfl_model as m  # noqa: E402

OUT = ROOT/'research/availability_weights_results'
CACHE = ROOT/'.nfl_cache/availability_weights_inputs'
OOS_CACHE = ROOT/'.nfl_cache/oos_2017_2020_inputs/cache'
REBUILT = 'rebuilt_columns.csv.gz'
SEED, BOOT, LEVEL = 20261013, 4000, .975
R = m.LEGACY_PRODUCT_RECIPE
FAMILY = R['family']
CONTEXTS = list(m.PRODUCT_CONTEXT_NAMES)
# Test 28, weights calibrated on 2019-22 snaps (snap loss beyond healthy regulars, Out = 1).
Q_PRACTICE = {'Q/Full': .06, 'Q/Lim': .26, 'Q/DNP': .55}
SPLIT_POS = {'WR': 'WR', 'TE': 'TE', 'CB': 'CB', 'DB': 'CB', 'S': 'S', 'FS': 'S', 'SS': 'S', 'SAF': 'S'}
SPLIT_GROUPS = (('OL', 'WR', 'TE', 'RB'), ('DL', 'LB', 'CB', 'S'))
ARMS = ('control', 'A_practice', 'B_split')
BASES = {'2017-2020': {'pack': ROOT/'research/out_of_sample_results/frozen_features_2013_2020.csv.gz',
                       'inputs': (2013, 2020), 'scored': (2017, 2020),
                       'reference': (ROOT/'research/out_of_sample_results/predictions.csv', 'production')},
         '2023-2025': {'pack': ROOT/'research/shrinkage_results/frozen_training_features.csv.gz',
                       'inputs': (2019, 2025), 'scored': (2023, 2025),
                       'reference': (ROOT/'research/restore_v116_results/historical_reproduction.csv', 'model_wp')}}


def protect(path):
    path = Path(path).resolve()
    if any(path == p or p in path.parents for p in (ROOT/'data', ROOT/'public')):
        raise ValueError('Research cannot write production outputs')
    return path


def unit_names(split):
    groups = SPLIT_GROUPS[0]+SPLIT_GROUPS[1] if split else m.OFFENSE_GROUPS+m.DEFENSE_GROUPS
    return [f'd__avail__{g}_out_cs' for g in groups]


@contextmanager
def unit_groups(split):
    """Production's position groups, or candidate B's split units, for availability_table and
    feature_names inside the block; module state is always restored."""
    saved = m.POS_GROUP, m.OFFENSE_GROUPS, m.DEFENSE_GROUPS, m.AVAIL_FAMILY_COLS[FAMILY]
    if split:
        m.POS_GROUP = {**m.POS_GROUP, **SPLIT_POS}
        m.OFFENSE_GROUPS, m.DEFENSE_GROUPS = SPLIT_GROUPS
        m.AVAIL_FAMILY_COLS[FAMILY] = ('qb_delta',)+tuple(f'{g}_out_cs' for g in SPLIT_GROUPS[0]+SPLIT_GROUPS[1])
    try:
        yield
    finally:
        m.POS_GROUP, m.OFFENSE_GROUPS, m.DEFENSE_GROUPS, m.AVAIL_FAMILY_COLS[FAMILY] = saved


def practice_weight(report_status, practice_status):
    """Candidate A's unavailable weight for one injury-report row."""
    from availability_audit import practice_label
    status = report_status if isinstance(report_status, str) else None
    if status in ('Out', 'Doubtful'): return 1.
    if status == 'Questionable':
        return Q_PRACTICE.get(practice_label(status, practice_status), m.STATUS_WEIGHT['Questionable'])
    return 0.


def practice_injuries(inj, detail):
    """Production's injury rows with candidate A's weight (availability_table keeps a given weight)."""
    key = ['season', 'week', 'team', 'gsis_id']
    ps = detail.drop_duplicates(key)[key+['practice_status']]
    d = inj.merge(ps, on=key, how='left', validate='many_to_one')
    d['weight'] = [practice_weight(s, p) for s, p in zip(d.report_status, d.practice_status)]
    return d.drop(columns='practice_status')


def unit_table(targets, snaps, inj, rost, split=False):
    with unit_groups(split):
        t = m.availability_table(targets, None, snaps, inj, rost)
        cols = [c[len('d__avail__'):] for c in unit_names(split)]
    return t.set_index(['season', 'week', 'team'])[cols]


def differences(pack, table, names):
    """Home minus away per game row, as lagged_features forms d__avail__ columns."""
    out = pd.DataFrame(index=pack.index)
    for c in names:
        col = c[len('d__avail__'):]
        side = {s: [table[col].get((int(y), int(w), t), np.nan) for y, w, t in zip(pack.season, pack.week, pack[s])]
                for s in ('home', 'away')}
        out[c] = np.asarray(side['home'], float)-np.asarray(side['away'], float)
    return out


def load_raw():
    """Raw availability inputs 2013-2025 with practice status, sharing the 2013-20 pack's cache."""
    from availability_audit import load_injury_detail
    cache = CACHE/'cache'; cache.mkdir(parents=True, exist_ok=True)
    for src in list(OOS_CACHE.glob('avail_*_20*.csv'))+[OOS_CACHE/'players_pfr_gsis.csv']:
        if src.exists() and not (cache/src.name).exists(): shutil.copy2(src, cache/src.name)
    m.CACHE_DIR = str(cache); m.OUTPUT_ROOT = CACHE; m.UPSTREAM_RETRIES = 2
    years = list(range(2013, 2026))
    a = m.load_availability(years, 2026)
    return a, load_injury_detail(years)


def prepare(out=OUT):
    out = protect(out); out.mkdir(parents=True, exist_ok=True)
    a, detail = load_raw()
    frames, check = [], {}
    for basis, spec in BASES.items():
        pack = pd.read_csv(spec['pack'])
        lo, hi = spec['inputs']; pack = pack[pack.season.between(lo, hi)].reset_index(drop=True)
        keep = lambda d: d[d.season.between(lo, hi)].copy()
        snaps, inj, rost = keep(a['snaps']), keep(a['inj']), keep(a['rost'])
        targets = pd.concat([pack[['season', 'week', 'home']].rename(columns={'home': 'team'}),
                             pack[['season', 'week', 'away']].rename(columns={'away': 'team'})]).drop_duplicates()
        cols = {'control': differences(pack, unit_table(targets, snaps, inj, rost), unit_names(False)),
                'A_practice': differences(pack, unit_table(targets, snaps, practice_injuries(inj, detail), rost), unit_names(False)),
                'B_split': differences(pack, unit_table(targets, snaps, inj, rost, split=True), unit_names(True))}
        frozen = pack[unit_names(False)].to_numpy(float); rebuilt = cols['control'].to_numpy(float)
        same_nan = np.isnan(frozen) == np.isnan(rebuilt)
        diff = np.where(np.isnan(frozen) & np.isnan(rebuilt), 0., np.abs(frozen-rebuilt))
        check[basis] = {'games': int(len(pack)), 'input_seasons': [lo, hi],
                        'missingness_identical': bool(same_nan.all()),
                        'max_abs_difference': float(np.nanmax(np.where(same_nan, diff, np.inf))),
                        'rows_differing': int((~same_nan | (diff > 1e-12)).any(axis=1).sum()),
                        'questionable_rows': int(inj.report_status.eq('Questionable').sum()),
                        'questionable_practice_labels': {k: int(v) for k, v in practice_injuries(inj, detail)
                                                         .loc[lambda d: d.report_status.eq('Questionable')].weight.round(2)
                                                         .value_counts().sort_index().items()}}
        check[basis]['exact'] = check[basis]['missingness_identical'] and check[basis]['max_abs_difference'] < 1e-12
        frame = pd.concat([pack[['game_id']].assign(basis=basis)]+[c.add_prefix(f'{arm}:') for arm, c in cols.items()], axis=1)
        frames.append(frame)
        print(json.dumps({basis: check[basis]}, indent=1), flush=True)
    pd.concat(frames, ignore_index=True).to_csv(out/REBUILT, index=False, float_format='%.17g',
                                                 compression={'method': 'gzip', 'mtime': 0})
    (out/'pipeline_check.json').write_text(json.dumps(check, indent=2, allow_nan=False)+'\n')
    return check


def arm_frame(pack, rebuilt, arm, exact):
    """The basis pack with an arm's unit columns. The control keeps the frozen columns when the
    rebuild reproduced them exactly, otherwise uses the rebuilt control."""
    f = pack.copy()
    if arm == 'control' and exact: return f
    cols = rebuilt.filter(like=f'{arm}:').rename(columns=lambda c: c.split(':', 1)[1])
    return f.assign(**{c: cols[c].to_numpy(float) for c in cols})


def eligible(f):
    return (f.ready.astype(bool) & f['home won'].isin([0., 1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1)).to_numpy()


def scored_rows(f, years):
    return (f.season.between(*years) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q)
            & f.home_moneyline.notna() & f.away_moneyline.notna() & np.isfinite(f[CONTEXTS]).all(axis=1)).to_numpy()


def walk(frames, years):
    base = frames['control']; scored = scored_rows(base, years); train_ok = eligible(base)
    out = base.loc[scored, ['game_id', 'season', 'week', 'home', 'away', 'home won', 'home_moneyline', 'away_moneyline', 'q']].copy()
    for (year, week), rows in out.groupby(['season', 'week'], sort=True):
        train = train_ok & m.before(base, year, week).to_numpy()
        for arm, f in frames.items():
            with unit_groups(arm == 'B_split'):
                fit = m.fit_composite(f[train], R, int(year), int(week))
                if fit['training_games'] != int(train.sum()): raise ValueError('Training rows differ from eligible rows')
                out.loc[rows.index, arm] = m.apply_fit(f.loc[rows.index], fit)
    if not np.isfinite(out[list(frames)]).all().all(): raise ValueError('Incomplete predictions')
    return out.reset_index(drop=True)


def ll(y, p):
    return -(y*np.log(p)+(1-y)*np.log(1-p))


def interval(gain, clusters, rng):
    keys, inv = np.unique(clusters, return_inverse=True)
    s, n = np.bincount(inv, gain), np.bincount(inv)
    pick = rng.integers(0, len(keys), (BOOT, len(keys)))
    boot = s[pick].sum(1)/n[pick].sum(1)
    return [float(np.quantile(boot, (1-LEVEL)/2)), float(np.quantile(boot, 1-(1-LEVEL)/2))]


def flat(held, col):
    b = m.flat_bets(held.assign(model_wp=held[col].to_numpy()))
    return b, m.roi_summary(b[b.units.notna()])


def arm_summary(held, col):
    """Flat 1u on the arm's side and on the market favorite, on the same rows (both bet)."""
    b, _ = flat(held, col)
    fav = m.flat_bets(held.assign(fav=m.market_ml_wp(held)), 'fav')
    keep = (b.units.notna() & fav.units.notna()).to_numpy()
    r = m.roi_summary(b[keep])
    y = held['home won'].to_numpy(float); binary = np.isin(y, [0., 1.])
    return {'bets': r['bets'], 'wins': r['wins'], 'losses': r['losses'], 'pushes': r['pushes'],
            'units': r['units'], 'roi': r['roi'], 'roi_se': r['roi_se'], 'null_roi': r['null_roi'],
            'favorite_units': float(fav.units[keep].sum()), 'favorite_roi': float(fav.units[keep].mean()),
            'binary_games': int(binary.sum()), 'log_loss': float(ll(y[binary], held[col].to_numpy()[binary]).mean())}


def compare(held, arm, rng):
    y = held['home won'].to_numpy(float); binary = np.isin(y, [0., 1.])
    gain = (ll(y, held.control.to_numpy())-ll(y, held[arm].to_numpy()))[binary]
    clusters = (held.basis+'_'+held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()[binary]
    bc, _ = flat(held, 'control'); ba, _ = flat(held, arm)
    return {'games': int(binary.sum()), 'll_gain': float(gain.mean()), 'll_interval': interval(gain, clusters, rng),
            'units_vs_control': float(np.nansum(ba.units)-np.nansum(bc.units)),
            'side_flips': int(((held[arm] > .5) != (held.control > .5)).sum())}


def verdict(per_basis, pooled):
    if pooled['ll_gain'] <= 0: return 'falsified'
    if all(b['ll_gain'] > 0 for b in per_basis) and pooled['ll_interval'][0] > 0: return 'supported'
    return 'unresolved'


def run(out=OUT):
    out = protect(out)
    check = json.loads((out/'pipeline_check.json').read_text())
    rebuilt = pd.read_csv(out/REBUILT)
    rng = np.random.default_rng(SEED); held_all, info = [], {'protocol': 'research/AVAILABILITY_WEIGHTS.md',
                                                              'revision': 'boxscore-composite-v1.16', 'recipe': R,
                                                              'questionable_practice_weights': Q_PRACTICE,
                                                              'confidence_level': LEVEL, 'bases': {}}
    for basis, spec in BASES.items():
        pack = pd.read_csv(spec['pack']); lo, hi = spec['inputs']
        pack = pack[pack.season.between(lo, hi)].reset_index(drop=True)
        cols = rebuilt[rebuilt.basis == basis].reset_index(drop=True)
        if not cols.game_id.equals(pack.game_id): raise ValueError(f'{basis}: rebuilt columns do not align with the pack')
        frames = {arm: arm_frame(pack, cols, arm, check[basis]['exact']) for arm in ARMS}
        held = walk(frames, spec['scored']).assign(basis=basis)
        path, col = spec['reference']
        ref = pd.read_csv(path).set_index('game_id')[col].reindex(held.game_id).to_numpy()
        info['bases'][basis] = {'pipeline_check': check[basis],
                                'control_vs_committed_v116_max_abs': float(np.nanmax(np.abs(held.control.to_numpy()-ref))),
                                'arms': {arm: arm_summary(held, arm) for arm in ARMS},
                                'paired': {arm: compare(held, arm, rng) for arm in ARMS[1:]}}
        held_all.append(held)
        print(f'{basis} done', flush=True)
    held = pd.concat(held_all, ignore_index=True)
    info['pooled'] = {arm: compare(held, arm, rng) for arm in ARMS[1:]}
    info['verdicts'] = {arm: verdict([info['bases'][b]['paired'][arm] for b in BASES], info['pooled'][arm]) for arm in ARMS[1:]}
    out.mkdir(parents=True, exist_ok=True)
    held.to_csv(out/'predictions.csv', index=False)
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__).resolve(), ROOT/'research/AVAILABILITY_WEIGHTS.md', ROOT/'nfl_model.py',
               ROOT/'research/availability_audit.py', out/REBUILT, out/'pipeline_check.json']+[s['pack'] for s in BASES.values()]
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in sources}, indent=2)+'\n')
    write_report(info, out)
    print(json.dumps(info['verdicts'], indent=2), flush=True)
    return info


def write_report(info, out):
    label = {'A_practice': 'A, Questionable by practice', 'B_split': 'B, split units'}
    lines = ['# Availability weighting candidates', '',
             'Protocol: [AVAILABILITY_WEIGHTS.md](../AVAILABILITY_WEIGHTS.md), committed before any candidate forecast. '
             'Production v1.16 and its ledger are unchanged. Historical development, not forward evidence.', '']
    for arm in ARMS[1:]:
        p = info['pooled'][arm]; lo, hi = p['ll_interval']
        lines.append(f"**{label[arm]}: {info['verdicts'][arm]}.** Pooled log-loss gain over v1.16 {p['ll_gain']:+.6f} "
                     f"[{lo:+.6f}, {hi:+.6f}] ({100*LEVEL:.1f}%), {p['games']} games; {p['side_flips']} side flips worth "
                     f"{p['units_vs_control']:+.2f}u against v1.16.")
        lines.append('')
    for basis, b in info['bases'].items():
        pc = b['pipeline_check']
        lines += [f'## {basis}', '',
                  f"Rebuilt production columns {'reproduce the frozen columns exactly' if pc['exact'] else 'differ from the frozen columns'} "
                  f"({pc['rows_differing']} of {pc['games']} rows differ; max {pc['max_abs_difference']:.3g}). "
                  f"Control against the committed v1.16 forecasts: max difference {b['control_vs_committed_v116_max_abs']:.3g}.", '',
                  f"{b['arms']['control']['bets']} flat 1u bets where the market has a favorite (same rows for every arm and the "
                  f"favorite); {b['arms']['control']['binary_games']} binary games for log loss.", '',
                  '| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Same-row favorite | Log loss |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for arm, s in b['arms'].items():
            lines.append(f"| {arm} | {s['wins']}-{s['losses']}-{s['pushes']} | {s['units']:+.2f} | {100*s['roi']:+.2f}% ± "
                         f"{100*s['roi_se']:.2f} | {100*s['null_roi']:+.2f}% | {s['favorite_units']:+.2f}u ({100*s['favorite_roi']:+.2f}%) | "
                         f"{s['log_loss']:.6f} |")
        lines += ['', f'| Candidate vs v1.16 | Log-loss gain [{100*LEVEL:.1f}%] | Units vs v1.16 | Side flips |', '|---|---:|---:|---:|']
        for arm, p in b['paired'].items():
            lo, hi = p['ll_interval']
            lines.append(f"| {label[arm]} | {p['ll_gain']:+.6f} [{lo:+.6f}, {hi:+.6f}] | {p['units_vs_control']:+.2f} | {p['side_flips']} |")
        lines.append('')
    lines += ['Week-cluster bootstrap intervals; positive gains favor the candidate. Log loss decides; ROI is reported, '
              'not optimized. Supported needs a positive gain on both bases and a pooled interval above zero; a pooled '
              'gain at or below zero falsifies.', '',
              'Run: `python research/availability_weights.py --prepare` (downloads), then `python research/availability_weights.py`.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--prepare', action='store_true', help='download raw inputs and freeze the rebuilt columns')
    ap.add_argument('--output-dir', type=Path, default=OUT)
    args = ap.parse_args()
    if args.prepare: prepare(args.output_dir)
    else: run(args.output_dir)
