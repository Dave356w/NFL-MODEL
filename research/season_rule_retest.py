"""Frozen exploratory retest under the owner's every-season market hurdle.

Research only: reads one prepared feature export, writes only --out. No network,
capture, production fitting entry point, ledger updates, or public-site changes.
The design is recorded in DESIGN.md before forecast generation starts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, ndtri

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fixed_bands as bands
import nfl_model as m

SOURCE = Path('/workspace/nfl-performance-audit/v119-rebuild-runs/2026_week6_20261019T191916104054Z/pregame_features_half_life_8.csv')
OUT = ROOT / 'research/season_rule_retest_results'
FEATURES = m.feature_names(m.LEGACY_PRODUCT_RECIPE['family']) + list(m.PRODUCT_CONTEXT_NAMES)
GAMMAS = (.05, .10, .25, .50, 1.)
ANCHORS = ('moneyline', 'spread_total')
SEASONS = tuple(range(2021, 2027))
PATHS = ('raw', 'own_median', 'shared_median')
# Numerical equality cannot manufacture a strict improvement from identical
# W-L-P counts or floating-point cancellation in paired proper scores.
SCORE_GAIN_EPS = 1e-12
ROI_GAIN_EPS = 1e-10
PAIRS = (
    ('d__allowed__rates_core__net_pass_yards_per_pass_play', 'd__avail__qb_delta'),
    ('pass_product', 'd__avail__DB_out_cs'),
    ('d__allowed__rates_core__first_down_rate', 'd__allowed__rates_core__penalty_yards_per_game'),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def definitions():
    result = [('single:' + x, [x]) for x in FEATURES]
    result += [('pair:' + '|'.join(p), list(p)) for p in PAIRS]
    return result + [('full29', list(FEATURES))]


def variants():
    rows = []
    for anchor in ANCHORS:
        control = 'market:' + anchor
        rows.append(dict(id=control, anchor=anchor, candidate='market', gamma=0.,
                         feature_list='[]', is_control=True, own_anchor_control_id=control))
        for candidate, cols in definitions():
            for gamma in GAMMAS:
                rows.append(dict(id=f'{anchor}::{candidate}::g{gamma:g}', anchor=anchor,
                    candidate=candidate, gamma=gamma, feature_list=json.dumps(cols),
                    is_control=False, own_anchor_control_id=control))
    rows.append(dict(id='incumbent:v118', anchor='moneyline', candidate='incumbent_v118',
        gamma=1., feature_list=json.dumps(FEATURES), is_control=True,
        own_anchor_control_id='market:moneyline'))
    return pd.DataFrame(rows)


def fit_group(x, y, weights, baseline, penalty):
    def objective(beta):
        eta = baseline + x @ beta
        value = weights @ (np.logaddexp(0, eta) - y * eta) + .5 * np.sum(penalty * beta * beta)
        gradient = x.T @ (weights * (expit(eta) - y)) + penalty * beta
        return float(value), gradient
    opt = minimize(objective, np.zeros(x.shape[1]), jac=True, method='L-BFGS-B',
        options=dict(gtol=1e-9, ftol=1e-14, maxiter=1500, maxls=100))
    grad = float(np.abs(objective(opt.x)[1]).max())
    if not np.isfinite(opt.x).all() or grad > 2e-6:
        raise RuntimeError(f'Fit convergence failure: {opt.message}; gradient={grad}')
    return opt.x, grad


def fit_small_batch(x, y, weights, baseline, indices, penalties):
    """Vectorized independent one/two-term Newton fits with checked line search."""
    indices = np.asarray(indices, int)
    a = x[:, indices[:, 0]]
    b = np.where(indices[None, :, 1] >= 0, x[:, np.maximum(indices[:, 1], 0)], 0.)
    beta = np.zeros((len(indices), 2))
    def state(coef):
        eta = baseline[:, None] + a * coef[:, 0] + b * coef[:, 1]
        p = expit(eta)
        val = weights @ (np.logaddexp(0, eta) - y[:, None] * eta)
        return p, val + .5 * np.sum(penalties * coef * coef, axis=1)
    for iteration in range(60):
        p, value = state(beta)
        r = weights[:, None] * (p - y[:, None])
        gradient = np.column_stack([(r*a).sum(0), (r*b).sum(0)]) + penalties*beta
        max_gradient = float(np.abs(gradient).max())
        if max_gradient < 1e-9:
            return beta, dict(iterations=iteration, small_max_gradient=max_gradient)
        v = weights[:, None] * p * (1-p)
        h00 = (v*a*a).sum(0) + penalties[:, 0]
        h11 = (v*b*b).sum(0) + penalties[:, 1]
        h01 = (v*a*b).sum(0)
        det = h00*h11-h01*h01
        step = np.column_stack([(h11*gradient[:, 0]-h01*gradient[:, 1])/det,
                                (h00*gradient[:, 1]-h01*gradient[:, 0])/det])
        rate = np.ones(len(indices))
        for _ in range(30):
            proposal = beta-rate[:, None]*step
            _, next_value = state(proposal)
            bad = next_value > value + 1e-13
            if not bad.any():
                beta = proposal
                break
            rate[bad] *= .5
        else:
            raise RuntimeError('Small-model Newton line search failed')
    raise RuntimeError('Small-model Newton convergence failed')


def prepared(source):
    frame = pd.read_csv(source)
    if frame.game_id.duplicated().any():
        raise ValueError('Duplicate game IDs in source')
    if len(FEATURES) != 29 or any(x not in FEATURES for p in PAIRS for x in p):
        raise ValueError('Unexpected production feature definitions')
    quote_q = m.market_ml_wp(frame)
    if not np.allclose(frame.q, quote_q, rtol=0., atol=1e-12, equal_nan=True):
        raise ValueError('Saved no-vig probabilities differ from paired moneylines')
    criteria = dict(
        ready=frame.ready.astype(bool),
        valid_q=np.isfinite(frame.q) & frame.q.gt(0) & frame.q.lt(1),
        valid_pass_context=np.isfinite(frame[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1),
        valid_market_context=np.isfinite(frame[['spread_line', 'total_line']]).all(axis=1),
        labeled=frame['home won'].isin([0., .5, 1.]) & np.isfinite(frame.result),
    )
    eligibility = frame[['game_id', 'season', 'week']].copy()
    for name, values in criteria.items():
        eligibility[name] = values
    eligibility['eligible'] = np.logical_and.reduce(list(criteria.values()))
    eligibility['target_season'] = frame.season.isin(SEASONS)
    pack = frame.loc[eligibility.eligible].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    games = pack[pack.season.isin(SEASONS)].reset_index(drop=True)
    if len(games) != 1451:
        raise ValueError(f'Expected 1,451 completed fresh-source games, received {len(games)}')
    if not (pack.train_through_week < pack.week).all():
        raise ValueError('Profile cutoff does not precede target week')
    return pack, games, eligibility


def forecast_week(pack, target, metadata):
    year, week = int(target.season.iloc[0]), int(target.week.iloc[0])
    train = pack.loc[m.before(pack, year, week) & pack['home won'].isin([0., 1.])].copy()
    if len(train) < m.MIN_TRAIN_GAMES or not m.before(train, year, week).all():
        raise ValueError('Insufficient or non-prior training rows')
    age = (year-train.season.to_numpy())*19 + week-train.week.to_numpy()
    weights = np.exp2(-age/38.)
    weights /= weights.sum()
    raw = np.nan_to_num(train[FEATURES].to_numpy(float), nan=0., posinf=0., neginf=0.)
    mean = weights@raw
    scale = np.sqrt(weights@((raw-mean)**2))
    scale = np.where(scale > 1e-8, scale, 1.)
    scale[FEATURES.index('site')] = 1.
    x = raw/scale
    xx = np.nan_to_num(target[FEATURES].to_numpy(float), nan=0., posinf=0., neginf=0.)/scale
    y = train['home won'].to_numpy(float)
    small = [(name, cols) for name, cols in definitions() if len(cols) <= 2]
    indices = [[FEATURES.index(cols[0]), FEATURES.index(cols[1]) if len(cols) == 2 else -1]
               for _, cols in small]
    penalties = np.array([[.01 if i == FEATURES.index('site') else .1,
                           .01 if j == FEATURES.index('site') else .1] for i, j in indices])
    full_penalty = np.array([.01 if f == 'site' else .1 for f in FEATURES])
    values, audit, coefficients = {}, [], []
    v118_error = v119_error = 0.
    for anchor in ANCHORS:
        if anchor == 'moneyline':
            baseline, testbaseline = logit(train.q.to_numpy()), logit(target.q.to_numpy())
            market_grad = 0.
        else:
            market_x, market_xx = m.market_context_design(train), m.market_context_design(target)
            ess = 1/np.sum(weights**2)
            coef, market_grad = fit_group(market_x, y, weights, np.zeros(len(y)), np.full(4, .01/ess))
            baseline, testbaseline = market_x@coef, market_xx@coef
        beta, small_audit = fit_small_batch(x, y, weights, baseline, indices, penalties)
        full_beta, full_grad = fit_group(x, y, weights, baseline, full_penalty)
        deltas = {'full29': xx@full_beta}
        for k, (name, cols) in enumerate(small):
            ix = [FEATURES.index(c) for c in cols]
            deltas[name] = xx[:, ix]@beta[k, :len(ix)]
        values['market:'+anchor] = expit(testbaseline)
        for row in metadata[metadata.anchor.eq(anchor) & ~metadata.is_control].itertuples():
            values[row.id] = expit(testbaseline+row.gamma*deltas[row.candidate])
        if anchor == 'moneyline':
            p16 = expit(testbaseline+deltas['full29'])
            values['incumbent:v118'] = m.favorite_penalized_wp(p16, target.q.to_numpy(), .2)
            # Production uses its legacy optimizer; differences must be below a
            # probability tolerance too small to alter reported decimal metrics.
            reference_fit = m.fit_composite(train, m.LEGACY_V118_RECIPE, year, week)
            reference = m.apply_fit(target, reference_fit)
            v118_error = float(np.max(np.abs(reference-values['incumbent:v118'])))
            if v118_error > 2e-6:
                raise ValueError(f'v1.18 fit reproduction failure {v118_error}')
            # Preserve the incumbent's actual optimizer output exactly. The
            # independently fitted full correction remains an experiment arm.
            values['incumbent:v118'] = reference
        else:
            reference_fit = m.fit_composite(train, m.PRODUCT_RECIPE, year, week)
            reference = m.apply_fit(target, reference_fit)
            v119_error = float(np.max(np.abs(reference-expit(testbaseline+deltas['full29']))))
            if v119_error > 2e-6:
                raise ValueError(f'v1.19 fit reproduction failure {v119_error}')
        audit.append(dict(season=year, week=week, anchor=anchor, training_games=len(train),
            training_effective_games=float(1/np.sum(weights**2)),
            training_max_season=int(train.season.max()),
            training_max_week=int(train.loc[train.season.eq(train.season.max()), 'week'].max()),
            training_max_key=int((train.season*100+train.week).max()), target_key=year*100+week,
            minimum_age_weeks=int(age.min()), market_gradient=market_grad,
            full_gradient=full_grad, missing_feature_cells=int((~np.isfinite(train[FEATURES].to_numpy(float))).sum()),
            **small_audit))
        coefficients.append(dict(season=year, week=week, anchor=anchor,
            feature_scale=scale.tolist(), full_beta=full_beta.tolist(),
            small_beta=beta.tolist(), small_candidates=[a for a, _ in small]))
    return np.column_stack([values[identity] for identity in metadata.id]), audit, coefficients, v118_error, v119_error


def probability_margin(probability):
    return 12.37*ndtri(np.clip(probability, .005, .995))


def mapped_margins(games, raw, metadata):
    incumbent = int(np.flatnonzero(metadata.id.eq('incumbent:v118'))[0])
    own = np.full_like(raw, np.nan)
    shared = np.full_like(raw, np.nan)
    rules = []
    base = games[['season', 'result']].copy()
    for year in SEASONS:
        mask = games.season.eq(year).to_numpy()
        base['model_spread'] = raw[:, incumbent]
        shared_rule = bands.fit(base, year)
        if shared_rule is not None:
            shared[mask] = bands.apply(raw[mask], shared_rule)
            rules.append(dict(variant_id='incumbent:v118', path='shared_median', **shared_rule))
        for k, identity in enumerate(metadata.id):
            base['model_spread'] = raw[:, k]
            rule = bands.fit(base, year)
            if rule is not None:
                own[mask, k] = bands.apply(raw[mask, k], rule)
                rules.append(dict(variant_id=identity, path='own_median', **rule))
    return {'raw': raw, 'own_median': own, 'shared_median': shared}, rules


def selection_and_returns(games, margins):
    side = bands.pick(margins, games.spread_line.to_numpy()[:, None], True)
    cover_margin = (games.result-games.spread_line).to_numpy()[:, None]
    won = side*cover_margin > 0
    lost = side*cover_margin < 0
    # Production treats an outcome within EPS of the offered line as a push.
    push = np.abs(cover_margin) <= bands.EPS
    units = np.where(~np.isfinite(side), np.nan, np.where(side == 0, 0.,
        np.where(push, 0., np.where(won, 1/1.1, np.where(lost, -1., np.nan)))))
    return side, units


def proper_losses(y, probability):
    p = np.clip(probability, 1e-12, 1-1e-12)
    y = np.asarray(y)[:, None]
    ll = -(y*np.log(p)+(1-y)*np.log1p(-p))
    brier = (p-y)**2
    invalid = ~np.isin(y[:, 0], [0., 1.])
    ll[invalid] = np.nan
    brier[invalid] = np.nan
    return ll, brier


def summarize(games, metadata, probabilities, margins, sides, units):
    ll, brier = proper_losses(games['home won'], probabilities)
    favorite_side = np.sign(games.spread_line.to_numpy())
    home_side = np.ones(len(games))
    cover_margin = (games.result-games.spread_line).to_numpy()
    push = np.abs(cover_margin) <= bands.EPS
    def returns(side):
        return np.where(side == 0, 0., np.where(push, 0., np.where(side*cover_margin > 0, 1/1.1, -1.)))
    favorite, home = returns(favorite_side), returns(home_side)
    rows = []
    controls = {a: int(np.flatnonzero(metadata.id.eq('market:'+a))[0]) for a in ANCHORS}
    for path in PATHS:
        for year in SEASONS:
            mask = games.season.eq(year).to_numpy()
            for k, variant in enumerate(metadata.itertuples()):
                active = mask & np.isfinite(units[path][:, k])
                selected = active & (sides[path][:, k] != 0)
                bets = int(selected.sum())
                rr = units[path][:, k]
                wins = int((selected & (rr > 0)).sum())
                losses = int((selected & (rr < 0)).sum())
                pushes = bets-wins-losses
                total = float(np.nansum(rr[active])) if active.any() else np.nan
                roi = total/bets if bets else np.nan
                own = controls[variant.anchor]
                # Exact paired rows: comparator denominators cannot differ after
                # a sparse candidate map leaves part of a season unavailable.
                paired = active & np.isfinite(units[path][:, own])
                paired_selected = paired & (sides[path][:, k] != 0)
                own_selected = paired & (sides[path][:, own] != 0)
                own_bets = int(own_selected.sum())
                own_total = float(np.nansum(units[path][paired, own])) if paired.any() else np.nan
                own_roi = own_total/own_bets if own_bets else np.nan
                fav_selected = active & (favorite_side != 0)
                fav_bets = int(fav_selected.sum())
                fav_total = float(favorite[active].sum()) if active.any() else np.nan
                fav_roi = fav_total/fav_bets if fav_bets else np.nan
                full_n = int(mask.sum())
                proper_mask = mask & np.isfinite(ll[:, k])
                ll_mean = float(np.mean(ll[proper_mask, k]))
                brier_mean = float(np.mean(brier[proper_mask, k]))
                ll_gain_ml = float(np.mean(ll[proper_mask, controls['moneyline']]-ll[proper_mask, k]))
                ll_gain_context = float(np.mean(ll[proper_mask, controls['spread_total']]-ll[proper_mask, k]))
                brier_gain_ml = float(np.mean(brier[proper_mask, controls['moneyline']]-brier[proper_mask, k]))
                brier_gain_context = float(np.mean(brier[proper_mask, controls['spread_total']]-brier[proper_mask, k]))
                rows.append(dict(variant_id=variant.id, anchor=variant.anchor, candidate=variant.candidate,
                    gamma=variant.gamma, is_control=variant.is_control, path=path, season=year,
                    opportunities=full_n, available=int(active.sum()), full_coverage=bool(active.sum() == full_n),
                    proper_n=int(proper_mask.sum()), log_loss=ll_mean, brier=brier_mean,
                    log_loss_gain_ml=ll_gain_ml, log_loss_gain_spread_total=ll_gain_context,
                    brier_gain_ml=brier_gain_ml, brier_gain_spread_total=brier_gain_context,
                    log_loss_gain_own=ll_gain_ml if variant.anchor == 'moneyline' else ll_gain_context,
                    brier_gain_own=brier_gain_ml if variant.anchor == 'moneyline' else brier_gain_context,
                    probability_pass=bool(min(ll_gain_ml,ll_gain_context,brier_gain_ml,brier_gain_context)>SCORE_GAIN_EPS),
                    probability_pass_own=bool((ll_gain_ml if variant.anchor == 'moneyline' else ll_gain_context)>SCORE_GAIN_EPS and
                        (brier_gain_ml if variant.anchor == 'moneyline' else brier_gain_context)>SCORE_GAIN_EPS),
                    probability_pass_ml=bool(ll_gain_ml>SCORE_GAIN_EPS and brier_gain_ml>SCORE_GAIN_EPS),
                    wins=wins, losses=losses, pushes=pushes, skips=int((active & ~selected).sum()),
                    bets=bets, units=total, roi=roi, own_anchor_control_id=variant.own_anchor_control_id,
                    paired_control_n=int(paired.sum()), own_control_bets=own_bets,
                    own_control_units=own_total, own_control_roi=own_roi,
                    own_control_units_gain=float(np.nansum(rr[paired]-units[path][paired,own])) if paired.any() else np.nan,
                    favorite_bets=fav_bets, favorite_units=fav_total, favorite_roi=fav_roi,
                    home_units=float(home[active].sum()) if active.any() else np.nan,
                    home_roi=float(home[active].mean()) if active.any() else np.nan,
                    roi_gain_own=roi-own_roi, roi_gain_favorite=roi-fav_roi,
                    ats_positive_roi=bool(roi>ROI_GAIN_EPS), ats_beats_own=bool(roi-own_roi>ROI_GAIN_EPS),
                    ats_beats_favorite=bool(roi-fav_roi>ROI_GAIN_EPS),
                    ats_pass=bool(roi>ROI_GAIN_EPS and roi-own_roi>ROI_GAIN_EPS and roi-fav_roi>ROI_GAIN_EPS),
                    paired_selection_differences=int(np.count_nonzero(sides[path][paired,k]!=sides[path][paired,own])),
                    mean_absolute_margin_error=float(np.mean(abs(margins[path][active,k]-games.result.to_numpy()[active]))) if active.any() else np.nan))
    return pd.DataFrame(rows), favorite, home


def gates(annual):
    rows = []
    for (identity,path), block in annual.groupby(['variant_id','path'], sort=False):
        b = block.sort_values('season')
        exact_score_seasons = tuple(b.season.astype(int)) == SEASONS
        coverage = bool(exact_score_seasons and b.full_coverage.all())
        last = b[b.season.between(2023,2026)]
        exact_last_seasons = tuple(last.season.astype(int)) == tuple(range(2023,2027))
        last_complete = bool(exact_last_seasons and last.full_coverage.all())
        first = b.iloc[0]
        rows.append(dict(variant_id=identity, anchor=first.anchor,candidate=first.candidate,
            gamma=first.gamma,is_control=first.is_control,path=path,
            covered_seasons=int(b.full_coverage.sum()), evaluated_seasons=6,
            probability_passing_seasons=int(b.probability_pass.sum()),
            own_probability_passing_seasons=int(b.probability_pass_own.sum()),
            ml_probability_passing_seasons=int(b.probability_pass_ml.sum()),
            positive_roi_seasons=int(b.ats_positive_roi.sum()),
            beats_own_ats_seasons=int(b.ats_beats_own.sum()),
            beats_favorite_seasons=int(b.ats_beats_favorite.sum()),
            ats_passing_seasons=int(b.ats_pass.sum()),
            all_seasons_probability_pass=bool(exact_score_seasons and b.probability_pass.all()),
            all_seasons_ats_pass=bool(coverage and b.ats_pass.all()),
            all_seasons_joint_pass=bool(coverage and b.probability_pass.all() and b.ats_pass.all()),
            common_window_2023_26_covered_seasons=int(last.full_coverage.sum()),
            common_window_2023_26_probability_passing_seasons=int(last.probability_pass.sum()),
            common_window_2023_26_own_probability_passing_seasons=int(last.probability_pass_own.sum()),
            common_window_2023_26_ml_probability_passing_seasons=int(last.probability_pass_ml.sum()),
            common_window_2023_26_ats_passing_seasons=int(last.ats_pass.sum()),
            common_window_2023_26_positive_roi_seasons=int(last.ats_positive_roi.sum()),
            common_window_2023_26_beats_own_ats_seasons=int(last.ats_beats_own.sum()),
            common_window_2023_26_beats_favorite_seasons=int(last.ats_beats_favorite.sum()),
            pass_2023_2026_probability=bool(last_complete and last.probability_pass.all()),
            pass_2023_2026_ats=bool(last_complete and last.ats_pass.all()),
            pass_2023_2026_components=bool(last_complete and last.ats_pass.all() and last.probability_pass.all()),
            median_comparison_2023_26_pass=bool(path!='raw' and last_complete and last.ats_pass.all() and last.probability_pass.all()),
            worst_log_loss_gain_vs_both=float(np.minimum(b.log_loss_gain_ml,b.log_loss_gain_spread_total).min()),
            worst_brier_gain_vs_both=float(np.minimum(b.brier_gain_ml,b.brier_gain_spread_total).min()),
            worst_roi=float(b.roi.min()), worst_roi_gain_own=float(b.roi_gain_own.min()),
            worst_roi_gain_favorite=float(b.roi_gain_favorite.min()),
            total_units=float(b.units.sum()), total_bets=int(b.bets.sum()),
            pooled_roi=float(b.units.sum()/b.bets.sum()) if b.bets.sum() else np.nan,
            failed_probability_seasons=','.join(b.loc[~b.probability_pass,'season'].astype(str)),
            failed_ats_seasons=','.join(b.loc[~b.ats_pass,'season'].astype(str))))
    return pd.DataFrame(rows)


DESIGN = '''# Every-season market retest: frozen exploratory design

Recorded before calculating this retest. The owner holds v1.19; no result here
authorizes a production change. Historical 2021–26 outcomes have already been
examined, including the new revision's poor 2026 results. These are exposed
development data, not fresh validation.

Two winner-probability anchors: paired no-vig moneylines and an earlier-trained
spread/total logistic baseline with [1,s/7,(t−44)/7,s(t−44)/49], ridge .01/ESS.
For each anchor, 29 individual existing football inputs, exactly the three
previously declared additive pairs, and the full 29-input joint correction are
fit before every target week. Each fitted departure from its anchor logit has
fixed gamma .05, .10, .25, .50 or 1. The .05 and .10 arms are new exploratory
stronger shrinkage arms. Gamma zero is stored once per anchor; v1.18 is a control.

Training uses 2019 onward, only earlier weeks and decisive ready games with
valid quotes, pass context, spread and total. Outcome weights have a 38-week
half-life, normalized to sum 1. Inputs use training-only weighted SD, no
centering, neutral zero for missing differences. Ridge is .01 for site and .1
for every other correction input. The three additive pairs retain their
original definitions: allowed passing efficiency + QB delta; passing product
+ DB absences; allowed first-down rate + opponents' assessed penalty yards.
There is no opponent-adjustment redesign or additional product interaction.

Evaluate 2021–25 and 2026 YTD separately on all 1,451 completed games. Binary
proper scores exclude NFL tied finals, while ATS grades include tied finals.
Probability gate: one fixed arm has lower log loss AND Brier than BOTH winner
anchors in every season. Also report counts versus its own anchor and versus
moneylines so alternative interpretations remain visible.

The unchanged 12.37 inverse-normal probability-to-margin link feeds three paths:
raw margin; own annual median MOV map; the incumbent's shared annual median map.
Mappings use only earlier-season 2021+ OOF games and production 0/3/7/10 bands,
including losses and tied finals. Keep two prior seasons, 300 total and 30 per
band minimums. Therefore 2021/22 median paths are unavailable and cannot pass
the full six-season coverage gate. Show 2023–26 median comparisons separately.

ATS gate: positive flat-stake ROI at assumed −110 AND strictly better ROI than
the same anchor under the same mapping path AND the same-row market favorite
in every season, with complete six-season coverage. Always-home is diagnostic.
At a model/line equality within 1e−10, take the market favorite; zero pick'em
skips. Pushes remain in the bet denominator. All comparator games are paired;
missing mappings never count as passed seasons. Joint gate requires both the
probability and ATS gates. No annual winner selection or ROI-tuned thresholds.

Observed sign gates and uncertainty are separate evidence tiers. Whole-week
paired bootstrap and a simultaneous complete-family adjustment are conditional
on these forecasts, omit refit/adaptive-history uncertainty, and cannot turn
this searched history into independent fresh evidence. Historical paired ATS
prices and capture timestamps are unavailable; −110 is a stated scenario.
'''


def run(source=SOURCE, out=OUT):
    started = time.monotonic()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # The immutable design text is materialized before the first prediction.
    design_path = out/'DESIGN.md'
    if design_path.exists() and design_path.read_text()!=DESIGN:
        raise ValueError('Refusing to overwrite a different pre-recorded design')
    design_path.write_text(DESIGN)
    (out/'GATE_NUMERICS.md').write_text(
        '# Strict gate numerical equality\n\n'
        'A proper-score gain must exceed 1e−12 and an ROI or ROI-comparison gain '
        'must exceed 1e−10. These equality tolerances prevent floating-point '
        'cancellation from turning identical records into strict improvement. '
        'They do not change any forecast, feature, mapping or searched recipe.\n')
    full_source_sha = sha256(source)
    full_source_path = str(source)
    frozen = out/'frozen_inputs.csv.gz'
    prior_provenance = out/'provenance.json'
    if Path(source).resolve()==frozen.resolve() and prior_provenance.exists():
        previous = json.loads(prior_provenance.read_text())
        full_source_sha = previous['source_sha256']
        full_source_path = previous['source_path']
    elif frozen.exists() and prior_provenance.exists():
        previous = json.loads(prior_provenance.read_text())
        if full_source_sha != previous['source_sha256']:
            raise ValueError('Refusing a different source in an existing frozen result directory; choose a new --out')
    if not frozen.exists():
        original = pd.read_csv(source)
        columns = list(dict.fromkeys(['game_id','season','week','home','away','gameday','gametime',
            'ready','q','home_moneyline','away_moneyline','spread_line','total_line','result',
            'home won','train_through_week','profile_half_life','home_history_games','away_history_games']
            +FEATURES))
        original[columns].to_csv(frozen,index=False,compression='gzip')
    pack,games,eligibility = prepared(frozen)
    metadata = variants()
    metadata.to_csv(out/'variants.csv',index=False)
    games.to_csv(out/'games.csv',index=False)
    eligibility.to_csv(out/'eligibility.csv',index=False)
    probabilities = np.full((len(games),len(metadata)),np.nan)
    audits,coefficients = [],[]
    max_v118 = max_v119 = 0.
    for (year,week),target in games.groupby(['season','week'],sort=True):
        p, audit, coef, err118, err119 = forecast_week(pack,target,metadata)
        probabilities[target.index] = p
        audits.extend(audit)
        coefficients.extend(coef)
        max_v118, max_v119 = max(max_v118,err118),max(max_v119,err119)
        print(f'{year} W{week:02d}: {len(target)} forecasts x {len(metadata)} arms',flush=True)
    if not np.isfinite(probabilities).all():
        raise ValueError('Missing forecast')
    audit_frame = pd.DataFrame(audits)
    if not (audit_frame.training_max_key<audit_frame.target_key).all():
        raise ValueError('Fitting cutoff leakage')
    audit_frame.to_csv(out/'fit_audit.csv',index=False)
    (out/'coefficients.json').write_text(json.dumps(coefficients,separators=(',',':'))+'\n')
    margins, rules = mapped_margins(games,probability_margin(probabilities),metadata)
    (out/'median_rules.json').write_text(json.dumps(rules,separators=(',',':'))+'\n')
    sides,units = {},{}
    for path in PATHS:
        sides[path],units[path] = selection_and_returns(games,margins[path])
    annual,favorite,home = summarize(games,metadata,probabilities,margins,sides,units)
    annual.to_csv(out/'annual_scores.csv',index=False)
    gate_frame = gates(annual)
    gate_frame.to_csv(out/'gate_summary.csv',index=False)
    np.savez_compressed(out/'predictions.npz',probabilities=probabilities,
        variant_ids=metadata.id.to_numpy(str),game_ids=games.game_id.to_numpy(str),
        favorite_units=favorite,home_units=home,
        **{'margins_'+p:v for p,v in margins.items()},
        **{'sides_'+p:v for p,v in sides.items()},
        **{'units_'+p:v for p,v in units.items()})
    provenance = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        source_path=full_source_path,source_sha256=full_source_sha,
        frozen_inputs_sha256=sha256(frozen),script_sha256=sha256(__file__),
        design_sha256=sha256(design_path),model_source_sha256=sha256(ROOT/'nfl_model.py'),
        bands_source_sha256=sha256(ROOT/'fixed_bands.py'),
        initial_history_season=int(pack.season.min()),target_seasons=list(SEASONS),
        target_games=len(games),binary_proper_score_games=int(games['home won'].isin([0.,1.]).sum()),
        tied_finals=int(games['home won'].eq(.5).sum()),variant_count=len(metadata),
        non_control_variants=int((~metadata.is_control).sum()),
        target_coverage_by_season=games.groupby('season').size().to_dict(),
        excluded_target_games=int((eligibility.target_season & ~eligibility.eligible & eligibility.labeled).sum()),
        source_rows=len(eligibility),training_cutoffs_strictly_prior=True,
        score_gain_equality_tolerance=SCORE_GAIN_EPS,roi_gain_equality_tolerance=ROI_GAIN_EPS,
        profiles_strictly_prior=bool((pack.train_through_week<pack.week).all()),
        v118_high_precision_refit_max_difference=max_v118,v118_max_reproduction_error=0.,
        v119_max_reproduction_error=max_v119,
        no_vig_quote_reproduction=True,never_run_main_or_capture=True,
        execution_seconds=round(time.monotonic()-started,3),
        warnings=['Exposed historical development, not independent validation',
                  'Historical feature vintages and source revisions are not verified as captured pregame',
                  'Actual historical paired ATS quotes/timestamps unavailable; −110 assumed',
                  'No untouched seasons; search-adjusted intervals omit earlier adaptive research'])
    provenance['artifacts'] = {p.name:sha256(p) for p in out.iterdir() if p.is_file() and p.name!='provenance.json'}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    feature_gates = gate_frame.loc[~gate_frame.is_control]
    print(json.dumps(dict(probability_pass=int(feature_gates[feature_gates.path.eq('raw')].all_seasons_probability_pass.sum()),
        ats_pass=int(feature_gates.all_seasons_ats_pass.sum()),joint_pass=int(feature_gates.all_seasons_joint_pass.sum()),
        elapsed_seconds=provenance['execution_seconds']),indent=2),flush=True)
    return provenance


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--replay',action='store_true',help='Use the portable frozen input subset')
    args=parser.parse_args()
    frozen=args.out/'frozen_inputs.csv.gz'
    source=frozen if args.replay or (args.source is None and frozen.exists()) else (args.source or SOURCE)
    run(source,args.out)
