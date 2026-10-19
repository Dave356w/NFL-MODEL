"""Paired week-block uncertainty for the fixed market-modulation experiment.

Inference conditions on the already fitted forecasts. It does not refit any
model, undo exposed model development, or turn the partial 2026 season into an
independent test. All contrasts share the same resampled weeks within a season.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT/'research/season_rule_retest_results'
DEFAULT_OUTPUT = ROOT/'research/season_rule_retest_uncertainty'
PATHS = ('raw', 'own_median', 'shared_median')
YEARS = tuple(range(2021, 2027))
EPS = 1e-12
PROPER_TOL = 1e-12
ROI_TOL = 1e-10


def prepare_pack(left, right, weeks, metadata, season):
    """Aggregate both numerators and stake counts before paired resampling.

    A finite element is an observation/stake; NaN is unavailable or a skipped
    stake. Each side keeps its own denominator. This also handles ROI policies
    with different skips without treating unplaced bets as zero-return stakes.
    """
    left, right = np.asarray(left, float), np.asarray(right, float)
    if left.shape != right.shape or left.ndim != 2 or left.shape[1] != len(metadata):
        raise ValueError('Contrast arrays and metadata do not align')
    weeks = np.asarray(weeks)
    groups = sorted(set(weeks.tolist()))
    if len(weeks) != len(left):
        raise ValueError('Week groups do not align with game rows')
    def aggregate(values):
        return (np.vstack([np.nansum(values[weeks == g], axis=0) for g in groups]),
                np.vstack([np.isfinite(values[weeks == g]).sum(axis=0) for g in groups]))
    lsum, ln = aggregate(left); rsum, rn = aggregate(right)
    nl, nr = ln.sum(axis=0), rn.sum(axis=0)
    ml = np.divide(lsum.sum(axis=0), nl, out=np.full(len(nl), np.nan), where=nl > 0)
    mr = np.divide(rsum.sum(axis=0), nr, out=np.full(len(nr), np.nan), where=nr > 0)
    influence = np.divide(lsum-ml*ln, nl, out=np.full_like(lsum, np.nan), where=nl > 0)
    influence -= np.divide(rsum-mr*rn, nr, out=np.full_like(rsum, np.nan), where=nr > 0)
    ng = len(groups)
    se = np.sqrt(ng/(ng-1)*np.sum(influence**2, axis=0)) if ng > 1 else np.full(len(nl), np.nan)
    rows = pd.DataFrame(metadata).assign(season=int(season), weeks=ng,
        candidate_stakes=nl, benchmark_stakes=nr,
        common_stakes=np.sum(np.isfinite(left) & np.isfinite(right), axis=0),
        candidate_value=ml, benchmark_value=mr, gain=ml-mr, cluster_se=se)
    rows['available'] = (nl > 0) & (nr > 0)
    if 'full_coverage' not in rows:
        rows['full_coverage'] = True
    rows['inference_available'] = rows.available & np.isfinite(se) & (se > EPS) & (ng > 1)
    critical = t.ppf(.975, ng-1) if ng > 1 else np.nan
    rows['pointwise_95_lower'] = rows.gain-critical*se
    rows['pointwise_95_upper'] = rows.gain+critical*se
    rows.loc[~rows.inference_available, ['pointwise_95_lower', 'pointwise_95_upper']] = np.nan
    return dict(rows=rows, lsum=lsum, ln=ln, rsum=rsum, rn=rn,
                groups=groups, season=int(season))


def simultaneous_intervals(packs, repetitions=9999, seed=20261019, batch_size=128):
    """One max-standardized-deviation critical value over every available test.

    Resample whole weeks with replacement within each season. Recalculate each
    mean/ROI ratio from the sampled numerator and denominator, then standardize
    by the original paired week-cluster SE. This is a fixed-forecast cluster
    bootstrap simultaneous band, not a refitted-model or exact small-sample CI.
    """
    if repetitions < 99 or batch_size < 1:
        raise ValueError('Use at least 99 repetitions and a positive batch size')
    rng = np.random.default_rng(seed)
    maxima = np.zeros(repetitions)
    unavailable_replicates = 0
    family = 0
    for pack in packs:
        rows = pack['rows']; keep = rows.inference_available.to_numpy()
        family += int(keep.sum())
        if not keep.any():
            continue
        groups = len(pack['groups'])
        observed = rows.gain.to_numpy()[keep]
        se = rows.cluster_se.to_numpy()[keep]
        ls, ln, rs, rn = [pack[k][:, keep] for k in ('lsum', 'ln', 'rsum', 'rn')]
        for start in range(0, repetitions, batch_size):
            stop = min(start+batch_size, repetitions)
            weights = rng.multinomial(groups, np.full(groups, 1/groups), size=stop-start)
            ld, rd = weights@ln, weights@rn
            lmean = np.divide(weights@ls, ld, out=np.full(ld.shape, np.nan), where=ld > 0)
            rmean = np.divide(weights@rs, rd, out=np.full(rd.shape, np.nan), where=rd > 0)
            z = abs((lmean-rmean-observed)/se)
            unavailable_replicates += int((~np.isfinite(z)).sum())
            # A vanished stake denominator is not evidence of a bounded error.
            # Infinite maxima make the resulting band conservative in that case.
            z = np.where(np.isfinite(z), z, np.inf)
            maxima[start:stop] = np.maximum(maxima[start:stop], z.max(axis=1))
    critical = float(np.quantile(maxima, .95, method='higher')) if family else np.nan
    frame = pd.concat([p['rows'] for p in packs], ignore_index=True)
    frame['simultaneous_95_lower'] = frame.gain-critical*frame.cluster_se
    frame['simultaneous_95_upper'] = frame.gain+critical*frame.cluster_se
    frame.loc[~frame.inference_available, ['simultaneous_95_lower', 'simultaneous_95_upper']] = np.nan
    return frame, dict(method='paired whole-week bootstrap max standardized deviation',
        repetitions=int(repetitions), seed=int(seed), family_contrasts=family,
        planned_contrasts=len(frame), simultaneous_critical=critical,
        vanished_denominator_contrast_replicates=unavailable_replicates,
        conditional_on_frozen_forecasts=True, model_refits=False,
        partial_2026=True, small_sample_exact=False)


def _settle(margin, line, side):
    valid = np.isfinite(margin) & np.isfinite(line) & (side != 0)
    edge = side*(margin-line)
    return np.where(valid, np.where(abs(edge) <= 1e-10, 0., np.where(edge > 0, 1/1.1, -1.)), np.nan)


def load_packs(source):
    source = Path(source)
    games = pd.read_csv(source/'games.csv')
    variants = pd.read_csv(source/'variants.csv')
    if games.game_id.duplicated().any() or variants.id.duplicated().any():
        raise ValueError('Games or variants repeat an identity')
    arrays = np.load(source/'predictions.npz', allow_pickle=False)
    ids = arrays['variant_ids'].astype(str).tolist()
    if variants.id.tolist() != ids:
        raise ValueError('Variant metadata does not match prediction columns')
    if 'game_ids' in arrays and arrays['game_ids'].astype(str).tolist() != games.game_id.astype(str).tolist():
        raise ValueError('Game metadata does not match prediction rows')
    p = np.asarray(arrays['probabilities'], float)
    if p.shape != (len(games), len(variants)) or np.any(np.isfinite(p) & ((p < 0) | (p > 1))):
        raise ValueError('Invalid probability matrix')
    index = {name: i for i, name in enumerate(ids)}
    controls = {name: index['market:'+name] for name in ('moneyline', 'spread_total')}
    is_control = variants.is_control.astype(str).str.lower().isin(['true', '1'])
    selected = np.flatnonzero(~is_control.to_numpy())
    chosen = variants.iloc[selected]
    own = np.array([index[v] for v in chosen.own_anchor_control_id])
    margin, line = [games[c].to_numpy(float) for c in ('result', 'spread_line')]
    y = np.where(margin == 0, np.nan, (margin > 0).astype(float))
    scored = np.isfinite(margin) & (margin != 0)
    pp = np.clip(p, 1e-12, 1-1e-12)
    ll = -(y[:, None]*np.log(pp)+(1-y[:, None])*np.log1p(-pp))
    brier = (p-y[:, None])**2
    favorite = np.asarray(arrays['favorite_units'], float) if 'favorite_units' in arrays else _settle(margin, line, np.sign(line))
    favorite = np.where(np.sign(line) != 0, favorite, np.nan)
    home = np.asarray(arrays['home_units'], float) if 'home_units' in arrays else _settle(margin, line, np.ones(len(games)))
    packs = []
    for season in YEARS:
        mask = games.season.eq(season).to_numpy()
        if not mask.any():
            raise ValueError(f'Missing required season {season}')
        lhs, rhs, metadata = [], [], []
        def append(left, right, metric, path, benchmark, gate=True, paired=False, opportunities=None):
            left, right = np.asarray(left, float).copy(), np.asarray(right, float).copy()
            if left.shape != (len(games), len(selected)) or right.shape != left.shape:
                raise ValueError('Metric arrays do not align')
            if paired:
                valid = scored[:, None] & np.isfinite(left) & np.isfinite(right)
                left[~valid] = np.nan; right[~valid] = np.nan
                opportunities = valid
            if opportunities is None:
                opportunities = np.isfinite(left) | np.isfinite(right)
            lhs.append(left[mask]); rhs.append(right[mask])
            metadata.extend(dict(variant_id=v, metric=metric, path=path,
                benchmark=benchmark, gate=gate,
                paired_opportunities=int(opportunities[mask, j].sum()),
                full_coverage=bool(opportunities[mask, j].sum() == (scored[mask].sum() if paired else mask.sum())))
                for j, v in enumerate(chosen.id))
        for metric, losses in (('log_loss', ll), ('brier', brier)):
            for name, baseline in controls.items():
                # Positive gain always means the feature variant is better.
                # Negating both losses preserves that convention and the
                # candidate/benchmark value and stake column definitions.
                base = np.broadcast_to(losses[:, baseline, None], (len(games), len(selected)))
                append(-losses[:, selected], -base, metric, 'probability', name, paired=True)
        for path in PATHS:
            units = np.asarray(arrays['units_'+path], float)
            sides = np.asarray(arrays['sides_'+path], float)
            if units.shape != p.shape:
                raise ValueError(f'Invalid {path} units matrix')
            if sides.shape != p.shape:
                raise ValueError(f'Invalid {path} side matrix')
            availability = np.isfinite(units)
            selected_units = np.where((sides != 0) & np.isfinite(sides), units, np.nan)
            candidate = selected_units[:, selected]
            active = availability[:, selected]
            common = active & availability[:, own]
            append(candidate, np.where(np.isfinite(candidate), 0., np.nan), 'ats_roi', path, 'zero', opportunities=active)
            append(np.where(common, candidate, np.nan), np.where(common, selected_units[:, own], np.nan),
                'ats_roi', path, 'own_anchor', opportunities=common)
            append(candidate, np.where(active, np.broadcast_to(favorite[:, None], candidate.shape), np.nan),
                'ats_roi', path, 'market_favorite', opportunities=active)
            append(candidate, np.where(active, np.broadcast_to(home[:, None], candidate.shape), np.nan),
                'ats_roi', path, 'always_home', gate=False, opportunities=active)
        pack = prepare_pack(np.concatenate(lhs, axis=1), np.concatenate(rhs, axis=1),
            games.loc[mask, 'week'].to_numpy(), metadata, season)
        proper = pack['rows'].metric.isin(['log_loss', 'brier'])
        pack['rows'].loc[proper, ['candidate_value', 'benchmark_value']] *= -1
        packs.append(pack)
    return packs, variants, games


def candidate_evidence(frame, variants):
    """Count failures without selecting a winner from the least bad year."""
    rows = []
    chosen = variants.loc[~variants.is_control.astype(str).str.lower().isin(['true', '1'])]
    for v in chosen.itertuples(index=False):
        for path in PATHS:
            for scope, years in [('2021-2026 including partial 2026', YEARS),
                                 ('completed 2021-2025', YEARS[:-1]),
                                 ('common 2023-2026 including partial 2026', YEARS[2:])]:
                d = frame.loc[frame.variant_id.eq(v.id) & frame.season.isin(years)
                    & frame.gate & frame.path.isin(['probability', path])]
                required = len(years)*7  # four proper-score and three ATS requirements/year
                eligible = d.available & d.full_coverage
                threshold = np.where(d.metric.eq('ats_roi'), ROI_TOL, PROPER_TOL)
                missing = required-int(eligible.sum())
                fails = int((eligible & (d.gain <= threshold)).sum())
                positive_lower = int((eligible & (d.simultaneous_95_lower > threshold)).sum())
                proper = d.metric.ne('ats_roi')
                ats = ~proper
                rows.append(dict(variant_id=v.id, path=path, scope=scope,
                    required_comparisons=required, unavailable_comparisons=missing,
                    nonpositive_point_comparisons=fails,
                    point_gate_pass=missing == 0 and fails == 0,
                    probability_point_gate_pass=int((eligible & proper).sum()) == 4*len(years)
                        and bool((d.loc[proper, 'gain'] > PROPER_TOL).all()),
                    ats_point_gate_pass=int((eligible & ats).sum()) == 3*len(years)
                        and bool((d.loc[ats, 'gain'] > ROI_TOL).all()),
                    simultaneous_positive_comparisons=positive_lower,
                    simultaneous_gate_pass=missing == 0 and positive_lower == required,
                    limited_week_seasons=','.join(str(y) for y in sorted(d.loc[d.weeks < 10, 'season'].unique()))))
    return pd.DataFrame(rows)


def verify_annual_points(frame, annual_path):
    """Independently derived estimands must match the main annual calculation."""
    annual = pd.read_csv(annual_path)
    scored = annual.loc[annual.path.eq('raw')].set_index(['variant_id', 'season'])
    by_path = annual.set_index(['variant_id', 'path', 'season'])
    errors = []; stake_errors = []
    for row in frame.itertuples(index=False):
        if row.path == 'probability':
            ref = scored.loc[(row.variant_id, row.season)]
            expected = ref[row.metric+'_gain_'+('ml' if row.benchmark == 'moneyline' else 'spread_total')]
            actual_value = ref[row.metric]
        else:
            ref = by_path.loc[(row.variant_id, row.path, row.season)]
            expected = (ref.roi if row.benchmark == 'zero' else
                ref.roi_gain_own if row.benchmark == 'own_anchor' else
                ref.roi_gain_favorite if row.benchmark == 'market_favorite' else ref.roi-ref.home_roi)
            actual_value = ref.roi
            stake_errors.append(int(row.candidate_stakes) != int(ref.bets))
            if row.benchmark in ('own_anchor', 'market_favorite'):
                expected_stakes = ref.own_control_bets if row.benchmark == 'own_anchor' else ref.favorite_bets
                stake_errors.append(int(row.benchmark_stakes) != int(expected_stakes))
        for observed, target in [(row.gain, expected), (row.candidate_value, actual_value)]:
            if np.isfinite(observed) != np.isfinite(target):
                raise ValueError('Independent annual calculation has different availability')
            if np.isfinite(observed):
                errors.append(abs(observed-target))
    maximum = float(max(errors, default=0.))
    if maximum > 1e-12 or any(stake_errors):
        raise ValueError(f'Independent annual calculation disagrees: max error {maximum:g}, stakes {sum(stake_errors)}')
    return dict(contrasts=len(frame), compared_numbers=len(errors), max_absolute_error=maximum,
                stake_checks=len(stake_errors), stake_mismatches=int(sum(stake_errors)))


def run(source=DEFAULT_INPUT, output=DEFAULT_OUTPUT, repetitions=9999, seed=20261019):
    source, output = Path(source), Path(output)
    packs, variants, games = load_packs(source)
    frame, info = simultaneous_intervals(packs, repetitions=repetitions, seed=seed)
    info['independent_annual_verification'] = verify_annual_points(frame, source/'annual_scores.csv')
    evidence = candidate_evidence(frame, variants)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output/'contrasts.csv', index=False)
    evidence.to_csv(output/'candidate_evidence.csv', index=False)
    info.update(source=str(source), games=len(games), variants=len(variants),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        weeks_by_season={str(p['season']):len(p['groups']) for p in packs},
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source/'games.csv', source/'variants.csv', source/'predictions.npz')},
        stake_definition='1u risk at assumed -110; pushes count, skips and missing policies do not',
        effect_definition='benchmark loss minus candidate loss; candidate ROI minus benchmark ROI',
        strict_positive_tolerances=dict(proper=PROPER_TOL, roi=ROI_TOL),
        evidence_basis='exposed historical research, conditional on frozen forecast paths')
    (output/'audit.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    full = evidence.loc[evidence.scope.eq('2021-2026 including partial 2026')]
    complete = evidence.loc[evidence.scope.eq('completed 2021-2025')]
    common = evidence.loc[evidence.scope.eq('common 2023-2026 including partial 2026')]
    lines = ['# Seasonal rule uncertainty', '',
        f"{len(games)} games; {info['planned_contrasts']} planned contrasts, {info['family_contrasts']} nondegenerate available contrasts.",
        f"{repetitions:,} paired whole-week resamples within season; simultaneous 95% max-standardized-deviation critical value {info['simultaneous_critical']:.3f}.", '',
        f"Full 2021–2026 rule, including partial 2026: {int(full.point_gate_pass.sum())} point-estimate passes and {int(full.simultaneous_gate_pass.sum())} simultaneous-evidence passes across feature/policy combinations.",
        f"Completed 2021–2025 only: {int(complete.point_gate_pass.sum())} point-estimate passes and {int(complete.simultaneous_gate_pass.sum())} simultaneous-evidence passes.", '',
        f"The narrower common 2023–2026 window has {int(common.ats_point_gate_pass.sum())} ATS-only point-estimate pass; {int(common.point_gate_pass.sum())} joint passes. It is a secondary diagnostic, not the six-season promotion rule.", '',
        'Positive gains mean lower loss or higher ROI. LL and Brier each compare with both moneyline and spread/total probabilities. ATS compares positive ROI, the same-path anchor policy, and the favorite; always-home is diagnostic only.',
        'Each ROI ratio resamples its own return numerator and stake denominator. Pushes count as stakes; skips do not. Candidate, comparator and common-stake counts are retained for every contrast. Missing early median policies remain unavailable.',
        'Median unavailability in 2021–2022 is a coverage limitation, not evidence of losses: this experiment starts candidate forecast history in 2021. Earlier chronological forecasts would be needed to fit candidate maps for those early years.',
        'The simultaneous family includes all available feature, season, metric, comparator and ATS-path contrasts, including home diagnostics. A zero empirical SE receives no positive-evidence verdict.', '',
        'These intervals condition on already fitted, historically exposed forecasts. They do not include model-refitting uncertainty, undo earlier design selection, or establish a future betting edge. The partial 2026 season has few independent week clusters; this bootstrap is approximate and is not exact small-sample inference.',
        'Requiring improvement in every season is an intersection rule. One small or noisy season can prevent certification even when average performance improves. Ranking variants by their weakest year and then treating that selected minimum as fresh evidence would add selection bias. No candidate is nominated by this uncertainty module.', '',
        'Files: `contrasts.csv`, `candidate_evidence.csv`, and `audit.json`.', '']
    (output/'REPORT.md').write_text('\n'.join(lines))
    survivors = common.loc[common.ats_point_gate_pass, ['variant_id', 'path']]
    focused = frame.merge(survivors, on=['variant_id', 'path'], how='inner')
    focused = focused.loc[focused.season.ge(2023) & focused.gate]
    focused.to_csv(output/'focused_ats_comparisons.csv', index=False)
    detail = ['# Narrower-window ATS point-estimate survivors', '',
        'These are descriptive survivors of an exposed search. They do not pass the six-season rule or the probability rule. No candidate is nominated. All intervals below use the original full-family adjustment.', '',
        '| Variant / policy | Season | Comparator | Candidate stakes / comparator stakes | ROI gain | Ordinary 95% interval | Simultaneous 95% interval |',
        '|---|---:|---|---:|---:|---:|---:|']
    for r in focused.itertuples(index=False):
        detail.append(f'| {r.variant_id} / {r.path} | {r.season} | {r.benchmark} | {r.candidate_stakes}/{r.benchmark_stakes} | '
            f'{100*r.gain:+.2f} pp | [{100*r.pointwise_95_lower:+.2f}, {100*r.pointwise_95_upper:+.2f}] | '
            f'[{100*r.simultaneous_95_lower:+.2f}, {100*r.simultaneous_95_upper:+.2f}] |')
    (output/'FOCUSED_COMPARISONS.md').write_text('\n'.join(detail)+'\n')
    return frame, evidence, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--repetitions', type=int, default=9999)
    parser.add_argument('--seed', type=int, default=20261019)
    args = parser.parse_args()
    _, _, info = run(args.input_dir, args.output_dir, args.repetitions, args.seed)
    print(json.dumps(info, sort_keys=True))


if __name__ == '__main__':
    main()
