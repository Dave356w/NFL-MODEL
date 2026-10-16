"""Research-only coherent score distributions; see JOINT_MARKET_RESIDUALS.md.

python research/joint_market_residuals.py
python research/joint_market_residuals_report.py
No network access; no production imports or writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAP = 80
ALPHA = .4
RIDGE = .1
EMPIRICAL_MIX = .15
INFOS = ('A_market', 'B_residual', 'C_absolute', 'C_squared')
SHAPES = ('smooth', 'empirical')
BASE = ('m10', 't10', 'mt', 'm2', 't2')
MEAN_HISTORY = ('home_scored', 'home_allowed', 'away_scored', 'away_allowed')
ABS_HISTORY = tuple(c + '_abs' for c in MEAN_HISTORY)
SQ_HISTORY = tuple(c + '_sq' for c in MEAN_HISTORY)
SCORE_SUPPORT = np.arange(CAP + 1)
MOV_SUPPORT = np.arange(-CAP, CAP + 1)
TOTAL_SUPPORT = np.arange(2 * CAP + 1)
HH, AA = np.meshgrid(SCORE_SUPPORT, SCORE_SUPPORT, indexing='ij')
MOV_INDEX = (HH - AA + CAP).ravel()
TOTAL_INDEX = (HH + AA).ravel()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guard_output(out):
    out = Path(out).resolve()
    for protected in (ROOT / 'data', ROOT / 'public'):
        if out == protected or protected in out.parents:
            raise ValueError('Research output cannot overwrite production data or site')
    return out


def before(f, year, week):
    return (f.season < year) | ((f.season == year) & (f.week < week))


def fair_moneyline(home, away):
    def raw(odds):
        odds = np.asarray(odds, float)
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where(odds > 0, 100 / (100 + odds), -odds / (100 - odds))
    h, a = raw(home), raw(away)
    valid = np.isfinite(home) & np.isfinite(away) & (np.abs(home) >= 100) & (np.abs(away) >= 100)
    return np.where(valid, h / (h + a), np.nan)


def prepare_inputs(out):
    path = out / 'frozen_inputs.csv.gz'
    if path.exists():
        return pd.read_csv(path)
    schedule = ROOT / 'research/form_windows_inputs/schedule.csv'
    totals = ROOT / 'research/residual_trends_inputs/schedule_totals.csv'
    f = pd.read_csv(schedule).merge(pd.read_csv(totals), on=['game_id', 'season', 'week'],
                                  validate='one_to_one')
    f = f.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    if f.game_id.duplicated().any():
        raise ValueError('Duplicate game ID')
    f.to_csv(path, index=False, compression={'method': 'gzip', 'mtime': 0})
    sources = {str(p.relative_to(ROOT)): sha256(p) for p in (schedule, totals)}
    (out / 'input_sources.json').write_text(json.dumps(sources, indent=2) + '\n')
    return f


def add_histories(frame):
    """Team histories update only after an entire season/week is forecast."""
    f = frame.copy().sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    f['implied_home'] = (f.total_line + f.spread_line) / 2
    f['implied_away'] = (f.total_line - f.spread_line) / 2
    f['q'] = fair_moneyline(f.home_moneyline, f.away_moneyline)
    f['m10'] = f.spread_line / 10
    f['t10'] = (f.total_line - 45) / 10
    f['mt'], f['m2'], f['t2'] = f.m10 * f.t10, f.m10 ** 2, f.t10 ** 2
    for c in (*MEAN_HISTORY, *ABS_HISTORY, *SQ_HISTORY):
        f[c] = 0.
    states, audits = {}, []
    for (year, week), group in f.groupby(['season', 'week'], sort=True):
        teams = list(group.home_team) + list(group.away_team)
        if len(teams) != len(set(teams)):
            raise ValueError('Team appears more than once in a week')
        updates = []
        for ix, row in group.iterrows():
            finite = np.isfinite([row.home_score, row.away_score, row.spread_line, row.total_line]).all()
            rh, ra = row.home_score - row.implied_home, row.away_score - row.implied_away
            for side, team, rs, rd in [('home', row.home_team, rh, ra), ('away', row.away_team, ra, rh)]:
                old = states.get(team)
                if old is None:
                    values, mass, sumsq, n, sy, sw = np.zeros(6), 0., 0., 0, -1, -1
                else:
                    values, mass, sumsq, n, sy, sw = old
                    retention = .5 ** (int(year) - sy)
                    values, mass, sumsq = values * retention, mass * retention, sumsq * retention ** 2
                names = (side + '_scored', side + '_allowed', side + '_scored_abs',
                         side + '_allowed_abs', side + '_scored_sq', side + '_allowed_sq')
                f.loc[ix, list(names)] = values
                audits.append(dict(game_id=row.game_id, season=int(year), week=int(week), side=side,
                                   source_season=sy, source_week=sw, previous_games=n,
                                   decayed_mass=mass, effective_games=mass ** 2 / sumsq if sumsq > 0 else 0.))
                if finite:
                    residual = np.array([rs, rd, abs(rs), abs(rd), rs ** 2, rd ** 2])
                    updates.append((team, ((1 - ALPHA) * values + ALPHA * residual,
                                          (1 - ALPHA) * mass + ALPHA,
                                          (1 - ALPHA) ** 2 * sumsq + ALPHA ** 2,
                                          n + 1, int(year), int(week))))
        for team, state in updates:
            states[team] = state
    for side in ('home', 'away'):
        f[side + '_total_residual'] = f[side + '_scored'] + f[side + '_allowed']
    return f, pd.DataFrame(audits)


def time_weights(train, year):
    return np.exp2(-(float(year) - train.season.to_numpy(float)) / 2)


def ridge_fit(x, y, weights, penalty=RIDGE):
    """Normalized weighted squared error + L2; intercept is unpenalized."""
    x, y, weights = np.asarray(x, float), np.asarray(y, float), np.asarray(weights, float)
    if y.ndim == 1:
        y = y[:, None]
    if len(x) == 0 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Nonfinite or empty regression input')
    w = weights / weights.sum()
    center = w @ x
    scale = np.sqrt(w @ ((x - center) ** 2))
    scale = np.where(scale > 1e-8, scale, 1.)
    z = np.column_stack([np.ones(len(x)), (x - center) / scale])
    reg = np.eye(z.shape[1]) * penalty
    reg[0, 0] = 0.
    coef = np.linalg.solve(z.T @ (w[:, None] * z) + reg, z.T @ (w[:, None] * y))
    return dict(center=center, scale=scale, coef=coef)


def ridge_predict(fit, x):
    x = np.asarray(x, float)
    return np.column_stack([np.ones(len(x)), (x - fit['center']) / fit['scale']]) @ fit['coef']


def mean_names(info):
    return BASE if info == 'A_market' else BASE + MEAN_HISTORY


def covariance_names(info):
    return BASE + (ABS_HISTORY if info == 'C_absolute' else SQ_HISTORY if info == 'C_squared' else ())


def empirical_names(info):
    return (() if info == 'A_market' else MEAN_HISTORY) + (
        ABS_HISTORY if info == 'C_absolute' else SQ_HISTORY if info == 'C_squared' else ())


def stable_covariance(prediction):
    v = np.asarray(prediction, float).copy()
    raw = v.copy()
    v[:, :2] = np.clip(v[:, :2], 16., 400.)
    rho = np.clip(v[:, 2] / np.sqrt(v[:, 0] * v[:, 1]), -.6, .6)
    v[:, 2] = rho * np.sqrt(v[:, 0] * v[:, 1])
    clipped = np.any(np.abs(raw - v) > 1e-8, axis=1)
    return v, clipped


def smooth_joint(mean, covariance):
    vh, va, cross = covariance
    det = vh * va - cross ** 2
    if det <= 0 or not np.isfinite(mean).all():
        raise ValueError('Invalid predictive parameters')
    dh, da = HH - mean[0], AA - mean[1]
    logp = -.5 * (va * dh ** 2 + vh * da ** 2 - 2 * cross * dh * da) / det
    prob = np.exp(logp - logp.max())
    return prob / prob.sum()


def empirical_joint(smooth, train, row, weights, names):
    distance = ((train.spread_line.to_numpy() - row.spread_line) / 6) ** 2
    distance += ((train.total_line.to_numpy() - row.total_line) / 7) ** 2
    if names:
        x = train[list(names)].to_numpy(float)
        w = weights / weights.sum()
        scale = np.sqrt(w @ ((x - w @ x) ** 2))
        scale = np.where(scale > 1e-8, scale, 1.)
        distance += np.sum(((x - row[list(names)].to_numpy(float)) / (1.5 * scale)) ** 2, axis=1)
    kernel = weights * np.exp(-.5 * distance)
    mass = kernel.sum()
    ids = train.home_score.to_numpy(int) * (CAP + 1) + train.away_score.to_numpy(int)
    histogram = np.bincount(ids, weights=kernel, minlength=(CAP + 1) ** 2).reshape(smooth.shape)
    empirical = (histogram + .5 * smooth) / (mass + .5)
    prob = (1 - EMPIRICAL_MIX) * smooth + EMPIRICAL_MIX * empirical
    effective = mass ** 2 / np.sum(kernel ** 2) if np.sum(kernel ** 2) > 0 else 0.
    return prob, effective


def marginals(joint):
    flat = joint.ravel()
    return dict(home=joint.sum(axis=1), away=joint.sum(axis=0),
                margin=np.bincount(MOV_INDEX, weights=flat, minlength=2 * CAP + 1),
                total=np.bincount(TOTAL_INDEX, weights=flat, minlength=2 * CAP + 1))


def discrete_crps(pmf, support, actual):
    return float(np.sum((np.cumsum(pmf) - (support >= actual)) ** 2))


def event_probabilities(pmf, support, line):
    win, push, lose = float(pmf[support > line].sum()), float(pmf[support == line].sum()), float(pmf[support < line].sum())
    return win, push, lose


def quantile(pmf, support, q):
    return int(support[min(np.searchsorted(np.cumsum(pmf), q), len(support) - 1)])


def summarize_joint(joint, row):
    pmfs = marginals(joint)
    hs, aws = int(row.home_score), int(row.away_score)
    result = dict(joint_nll=-np.log(max(joint[hs, aws], 1e-300)))
    for target, actual, support in [('home', hs, SCORE_SUPPORT), ('away', aws, SCORE_SUPPORT),
                                     ('margin', hs - aws, MOV_SUPPORT), ('total', hs + aws, TOTAL_SUPPORT)]:
        p = pmfs[target]
        result[target + '_nll'] = -np.log(max(p[actual - support[0]], 1e-300))
        result[target + '_crps'] = discrete_crps(p, support, actual)
        result[target + '_mean'] = float(p @ support)
        result[target + '_abs_error'] = abs(result[target + '_mean'] - actual)
        result[target + '_sq_error'] = (result[target + '_mean'] - actual) ** 2
        for level in (.5, .8, .9):
            lo, hi = quantile(p, support, (1 - level) / 2), quantile(p, support, (1 + level) / 2)
            label = str(int(level * 100))
            result[target + '_lo' + label], result[target + '_hi' + label] = lo, hi
            result[target + '_coverage' + label] = float(lo <= actual <= hi)
            result[target + '_width' + label] = hi - lo
        result[target + '_median'] = quantile(p, support, .5)
    home, tie, away = event_probabilities(pmfs['margin'], MOV_SUPPORT, 0)
    result.update(p_home=home, p_tie=tie, p_away=away, p_home_non_tie=home / max(home + away, 1e-15))
    for prefix, target, support, line in [('cover', 'margin', MOV_SUPPORT, row.spread_line),
                                          ('over', 'total', TOTAL_SUPPORT, row.total_line)]:
        win, push, lose = event_probabilities(pmfs[target], support, line)
        result.update({prefix + '_win': win, prefix + '_push': push, prefix + '_lose': lose,
                       prefix + '_conditional': win / max(win + lose, 1e-15)})
    result['team_crps'] = (result['home_crps'] + result['away_crps']) / 2
    result['team_nll'] = (result['home_nll'] + result['away_nll']) / 2
    return result, pmfs


def binary_loss(y, prob):
    p = np.clip(np.asarray(prob, float), 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def add_binary_and_bet_scores(frame):
    f = frame.copy()
    margin = f.home_score - f.away_score
    y = (margin > 0).to_numpy(float)
    proper = margin != 0
    f['win_ll'] = np.where(proper, binary_loss(y, f.p_home_non_tie), np.nan)
    f['win_brier'] = np.where(proper, (y - f.p_home_non_tie) ** 2, np.nan)
    f['market_win_ll'] = np.where(proper, binary_loss(y, f.q), np.nan)
    f['market_win_brier'] = np.where(proper, (y - f.q) ** 2, np.nan)
    for prefix, outcome, line in [('cover', margin, f.spread_line), ('over', f.home_score + f.away_score, f.total_line)]:
        lab = (outcome > line).to_numpy(float)
        f[prefix + '_ll'] = np.where(outcome != line, binary_loss(lab, f[prefix + '_conditional']), np.nan)
        f[prefix + '_brier'] = np.where(outcome != line, (lab - f[prefix + '_conditional']) ** 2, np.nan)
    priced = np.isfinite(f.q) & (np.abs(f.q - .5) > 1e-12)
    for name, prob in [('model', f.p_home_non_tie), ('favorite', f.q), ('underdog', 1 - f.q)]:
        home = prob > .5
        odds = np.where(home, f.home_moneyline, f.away_moneyline).astype(float)
        with np.errstate(invalid='ignore', divide='ignore'):
            profit = np.where(odds > 0, odds / 100, 100 / -odds)
        won = np.where(home, margin > 0, margin < 0)
        units = np.where(margin == 0, 0., np.where(won, profit, -1.))
        choiceq = np.where(home, f.q, 1 - f.q)
        # Conditional decisive-game quote null, matching the repository convention.
        null = choiceq * profit - (1 - choiceq)
        valid = priced & (np.abs(prob - .5) > 1e-12)
        f[name + '_units'] = np.where(valid, units, np.nan)
        f[name + '_null'] = np.where(valid, null, np.nan)
        f[name + '_home_pick'] = home
    return f


def fit_and_forecast(frame, out, end_year=2026):
    f, history_audit = add_histories(frame)
    valid = np.isfinite(f[['home_score', 'away_score', 'spread_line', 'total_line']]).all(axis=1)
    completed = f.loc[valid].copy()
    scores = completed[['home_score', 'away_score']].to_numpy()
    if (scores < 0).any() or (scores >= CAP).any() or not np.equal(scores, np.floor(scores)).all():
        raise ValueError('Outcomes must be nonnegative integer scores strictly below the support cap')
    oof_errors = {k: np.full((len(f), 2), np.nan) for k in ('A_market', 'B_residual')}
    records, audits, coefficients, pmf_ids = [], [], [], []
    pmf_values = {arm: {target: [] for target in ('home', 'away', 'margin', 'total')}
                  for arm in (s + '__' + i for s in SHAPES for i in INFOS)}
    examples = {}
    evaluate = completed[completed.season.between(2015, end_year)]
    started = time.monotonic()
    for (year, week), test in evaluate.groupby(['season', 'week'], sort=True):
        train = completed[before(completed, year, week) & (completed.season >= year - 5)]
        weights = time_weights(train, year)
        if len(train) < 100:
            continue
        maxyear = int(train.season.max())
        maxweek = int(train.loc[train.season == maxyear, 'week'].max())
        if (maxyear, maxweek) >= (year, week):
            raise ValueError('Forecast timing violation')
        mean_fits, test_means = {}, {}
        target = (train[['home_score', 'away_score']].to_numpy() -
                  train[['implied_home', 'implied_away']].to_numpy()) / 10
        for info in ('A_market', 'B_residual'):
            names = mean_names(info)
            fit = ridge_fit(train[list(names)], target, weights)
            test_means[info] = test[['implied_home', 'implied_away']].to_numpy() + 10 * ridge_predict(fit, test[list(names)])
            mean_fits[info] = fit
            coefficients.append(dict(season=int(year), week=int(week), stage='mean', info=info,
                                     names=list(names), **{k: v.tolist() for k, v in fit.items()}))
        cov_predictions, clipped_flags = {}, {}
        for info in INFOS:
            meaninfo = 'A_market' if info == 'A_market' else 'B_residual'
            errors = oof_errors[meaninfo][train.index]
            eligible = np.isfinite(errors).all(axis=1)
            fallback = eligible.sum() < 100
            if fallback:
                corpus, err, cw = train, train[['home_score', 'away_score']].to_numpy() - (
                    train[['implied_home', 'implied_away']].to_numpy() +
                    10 * ridge_predict(mean_fits[meaninfo], train[list(mean_names(meaninfo))])), weights
            else:
                corpus, err, cw = train.loc[eligible], errors[eligible], weights[eligible]
            crossproducts = np.column_stack([err[:, 0] ** 2, err[:, 1] ** 2, err[:, 0] * err[:, 1]]) / 100
            names = covariance_names(info)
            fit = ridge_fit(corpus[list(names)], crossproducts, cw)
            cov_predictions[info], clipped_flags[info] = stable_covariance(100 * ridge_predict(fit, test[list(names)]))
            coefficients.append(dict(season=int(year), week=int(week), stage='covariance', info=info,
                                     names=list(names), **{k: v.tolist() for k, v in fit.items()}))
            audits.append(dict(season=int(year), week=int(week), info=info, training_games=len(train),
                               covariance_games=len(corpus), covariance_fallback=fallback,
                               training_max_season=maxyear, training_max_week=maxweek,
                               covariance_max_season=int(corpus.season.max()),
                               covariance_max_week=int(corpus.loc[corpus.season == corpus.season.max(), 'week'].max()),
                               covariance_clipped_games=int(clipped_flags[info].sum())))
        for pos, (ix, row) in enumerate(test.iterrows()):
            retain = int(year) >= 2017
            if retain:
                pmf_ids.append(row.game_id)
            for info in INFOS:
                meaninfo = 'A_market' if info == 'A_market' else 'B_residual'
                smooth = smooth_joint(test_means[meaninfo][pos], cov_predictions[info][pos])
                empirical, ess = empirical_joint(smooth, train, row, weights, empirical_names(info))
                for shape, joint in [('smooth', smooth), ('empirical', empirical)]:
                    if not retain:
                        continue
                    arm = shape + '__' + info
                    metrics, pmfs = summarize_joint(joint, row)
                    metadata = {k: row[k] for k in ('game_id', 'season', 'week', 'gameday', 'home_team', 'away_team',
                                                   'home_score', 'away_score', 'spread_line', 'total_line',
                                                   'home_moneyline', 'away_moneyline', 'q')}
                    records.append(dict(arm=arm, shape=shape, info=info, empirical_effective_neighbors=ess,
                                        covariance_clipped=bool(clipped_flags[info][pos]), **metadata, **metrics))
                    for target_name, pmf in pmfs.items():
                        pmf_values[arm][target_name].append(pmf.astype(np.float32))
                    if (year == 2025 and week == 1 and row.home_team == 'SEA') or row.game_id == '2026_05_SF_SEA':
                        examples[row.game_id + '__' + arm] = joint.astype(np.float32)
        # Only now do this week's realized errors become available for later weeks.
        for info in ('A_market', 'B_residual'):
            oof_errors[info][test.index] = test[['home_score', 'away_score']].to_numpy() - test_means[info]
        if int(week) == 1 or (int(year) == end_year and int(week) % 3 == 0):
            print(f'Forecasted {int(year)} W{int(week):02d}; {len(records):,} scored arm-games; {time.monotonic()-started:.1f}s', flush=True)
    predictions = add_binary_and_bet_scores(pd.DataFrame(records))
    predictions.to_csv(out / 'predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    f.to_csv(out / 'features.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    history_audit.to_csv(out / 'history_audit.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    pd.DataFrame(audits).to_csv(out / 'fit_audit.csv', index=False)
    with (out / 'coefficient_audit.jsonl').open('w') as handle:
        for item in coefficients:
            handle.write(json.dumps(item) + '\n')
    payload = dict(game_ids=np.array(pmf_ids), score_support=SCORE_SUPPORT,
                   margin_support=MOV_SUPPORT, total_support=TOTAL_SUPPORT)
    for arm, targets in pmf_values.items():
        for target_name, values in targets.items():
            payload[arm + '__' + target_name] = np.asarray(values, np.float32)
    np.savez_compressed(out / 'marginal_probabilities.npz', **payload)
    np.savez_compressed(out / 'example_joint_probabilities.npz', **examples)
    return predictions


def run(out, end_year=2026):
    out = guard_output(out)
    out.mkdir(parents=True, exist_ok=True)
    inputs = prepare_inputs(out)
    result = fit_and_forecast(inputs, out, end_year)
    source_paths = [Path(__file__), ROOT / 'research/JOINT_MARKET_RESIDUALS.md', out / 'frozen_inputs.csv.gz']
    meta = dict(base_commit='e93b936b9de03bab8e97a6b7ae71fb6d3a224fa7',
                experiment='joint-market-residuals-20261016', alpha=ALPHA, ridge=RIDGE,
                empirical_mix=EMPIRICAL_MIX, cap=CAP, arms=sorted(result.arm.unique()),
                input_rows=len(inputs), completed_games_by_year=result.drop_duplicates('game_id').groupby('season').size().to_dict(),
                source_hashes={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): sha256(p) for p in source_paths},
                numpy_version=np.__version__, pandas_version=pd.__version__,
                basis='historical development; quote timestamps unknown; no native forward capture')
    (out / 'provenance.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(f'Wrote {len(result):,} arm-game predictions to {out}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'research/joint_market_residual_results')
    parser.add_argument('--end-year', type=int, default=2026)
    args = parser.parse_args()
    run(args.output_dir, args.end_year)
