"""R001: fixed, prior-week tie hurdle; never imports production code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

import joint_market_residuals as j


def fit_tie_rate(frame, year, week):
    """Six-season, complete-case, unweighted Jeffreys Bernoulli estimate."""
    valid = np.isfinite(frame[['home_score', 'away_score', 'spread_line', 'total_line']]).all(axis=1)
    train = frame[valid & j.before(frame, year, week) & (frame.season >= year - 5)]
    if train.empty:
        raise ValueError('No eligible earlier tie training games')
    ties = int((train.home_score == train.away_score).sum())
    last = train.sort_values(['season', 'week']).iloc[-1]
    return (ties + .5) / (len(train) + 1), dict(
        season=int(year), week=int(week), training_games=len(train), training_ties=ties,
        training_max_season=int(last.season), training_max_week=int(last.week))


def tie_hurdle(joint, rate):
    """Rescale diagonal/off-diagonal strata, retaining conditional PMFs."""
    joint = np.asarray(joint, float)
    if (joint.ndim != 2 or joint.shape[0] != joint.shape[1] or
            not np.isfinite(joint).all() or (joint < 0).any() or
            not np.isclose(joint.sum(), 1, atol=1e-12, rtol=0) or not 0 < rate < 1):
        raise ValueError('Invalid joint distribution or tie rate')
    old_rate = np.trace(joint)
    if not 0 < old_rate < 1:
        raise ValueError('Both tie and decisive support are required')
    out = joint * ((1 - rate) / (1 - old_rate))
    ix = np.diag_indices_from(out)
    out[ix] = joint[ix] * (rate / old_rate)
    return out


def extra_scores(joint, row):
    pmfs = j.marginals(joint)
    ph, pt, pa = j.event_probabilities(pmfs['margin'], j.MOV_SUPPORT, 0)
    hs, aws = int(row.home_score), int(row.away_score)
    outcome = np.array([hs > aws, hs == aws, hs < aws], float)
    p = np.array([ph, pt, pa])
    z = dict(outcome_nll=float(-np.log(p[outcome.astype(bool)][0])),
             outcome_brier=float(np.sum((p-outcome)**2)),
             tie_ll=float(j.binary_loss(float(hs == aws), pt)),
             tie_brier=float((pt-float(hs == aws))**2))
    # Diagnostic thresholds are market-derived locations, NOT traded team totals.
    for name, actual, line in [('home', hs, (row.total_line+row.spread_line)/2),
                               ('away', aws, (row.total_line-row.spread_line)/2)]:
        win, push, lose = j.event_probabilities(pmfs[name], j.SCORE_SUPPORT, line)
        q = win/(win+lose)
        z[name+'_location_over_prob'] = q
        z[name+'_location_over_ll'] = float(j.binary_loss(float(actual > line), q)) if actual != line else np.nan
        z[name+'_location_over_brier'] = float((q-float(actual > line))**2) if actual != line else np.nan
    for name, actual, support in [('home', hs, j.SCORE_SUPPORT), ('away', aws, j.SCORE_SUPPORT),
                                   ('margin', hs-aws, j.MOV_SUPPORT), ('total', hs+aws, j.TOTAL_SUPPORT)]:
        p = pmfs[name]
        z[name+'_pit_mid'] = float(p[support < actual].sum()+.5*p[support == actual].sum())
    return z


def load_fit_index(path):
    index = {}
    for line in Path(path).read_text().splitlines():
        row = json.loads(line)
        if row['info'] == 'A_market':
            index[row['season'], row['week'], row['stage']] = {
                k: np.asarray(row[k]) for k in ('center', 'scale', 'coef')}
    return index


def run(base, out):
    out = Path(out).resolve()
    allowed = (j.ROOT/'research/experiments').resolve()
    if not out.is_relative_to(allowed) or out == Path(base).resolve():
        raise ValueError('Output must be a separate research/experiments directory')
    out.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv(base/'features.csv.gz')
    valid = np.isfinite(f[['home_score','away_score','spread_line','total_line']]).all(axis=1)
    complete = f[valid]
    fits = load_fit_index(base/'coefficient_audit.jsonl')
    saved = pd.read_csv(base/'predictions.csv.gz').set_index(['arm','game_id'])
    records, audits, pmf_ids, examples = [], [], [], {}
    arms = [s+'__'+i for s in j.SHAPES for i in ('A_market','R001_tie_hurdle')]
    payload = {arm+'__'+t: [] for arm in arms for t in ('home','away','margin','total')}
    max_error = 0.
    for (year, week), test in complete[complete.season >= 2017].groupby(['season','week'], sort=True):
        train = complete[j.before(complete, year, week) & (complete.season >= year-5)]
        weight = j.time_weights(train, year)
        means = test[['implied_home','implied_away']].to_numpy()+10*j.ridge_predict(
            fits[year,week,'mean'], test[list(j.BASE)])
        covs, _ = j.stable_covariance(100*j.ridge_predict(fits[year,week,'covariance'], test[list(j.BASE)]))
        rate, audit = fit_tie_rate(f, year, week)
        audits.append(dict(**audit, rate=rate))
        for pos, (_, row) in enumerate(test.iterrows()):
            pmf_ids.append(row.game_id)
            smooth = j.smooth_joint(means[pos], covs[pos])
            empirical, _ = j.empirical_joint(smooth, train, row, weight, ())
            for shape, p in [('smooth',smooth), ('empirical',empirical)]:
                baseline_arm = shape+'__A_market'
                base_metrics, _ = j.summarize_joint(p, row)
                original = saved.loc[baseline_arm, row.game_id]
                error = max(abs(base_metrics[k]-original[k]) for k in
                            ['joint_nll','home_mean','away_mean','p_home','p_tie','margin_crps','total_crps'])
                max_error = max(error, max_error)
                if error > 1e-10:
                    raise AssertionError(f'Baseline reconstruction mismatch: {row.game_id} {error}')
                for info, joint in [('A_market',p),('R001_tie_hurdle',tie_hurdle(p,rate))]:
                    arm = shape+'__'+info
                    metrics, pmfs = j.summarize_joint(joint, row)
                    metadata = {k: row[k] for k in ['game_id','season','week','gameday','home_team','away_team',
                        'home_score','away_score','spread_line','total_line','home_moneyline','away_moneyline','q']}
                    records.append(dict(arm=arm, **metadata, **metrics, **extra_scores(joint,row)))
                    for target, values in pmfs.items():
                        payload[arm+'__'+target].append(values.astype(np.float32))
                    if row.game_id == '2026_05_SF_SEA':
                        examples[row.game_id+'__'+arm] = joint.astype(np.float32)
    result = j.add_binary_and_bet_scores(pd.DataFrame(records))
    result.to_csv(out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(audits).to_csv(out/'tie_fit_audit.csv',index=False)
    np.savez_compressed(out/'marginal_probabilities.npz',game_ids=np.array(pmf_ids),
        score_support=j.SCORE_SUPPORT, margin_support=j.MOV_SUPPORT, total_support=j.TOTAL_SUPPORT,
        **{k:np.asarray(v) for k,v in payload.items()})
    np.savez_compressed(out/'example_joint_probabilities.npz',**examples)
    manifest = dict(experiment='R001',baseline_reconstruction_max_abs_error=max_error,
        protocol_sha256=j.sha256(out/'PROTOCOL.md'),code_sha256=j.sha256(Path(__file__)),
        source_hashes={p:j.sha256(base/p) for p in ['frozen_inputs.csv.gz','features.csv.gz','coefficient_audit.jsonl','predictions.csv.gz']},
        probability_version='R001-jeffreys-unweighted-six-seasons-v1',
        numpy=np.__version__,pandas=pd.__version__,quote_timestamps='unknown',
        prior_result_exposure=True)
    (out/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(rows=len(result),baseline_reconstruction_max_error=max_error)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=j.ROOT/'research/experiments/R000_reproduction')
    parser.add_argument('--output',type=Path,default=j.ROOT/'research/experiments/R001_tie_hurdle')
    args = parser.parse_args()
    run(args.baseline,args.output)
