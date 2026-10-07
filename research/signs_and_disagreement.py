"""Tests 10 and 11: coefficient sign stability, and where the held-out ROI comes from.

    python research/signs_and_disagreement.py [CACHE_DIR]     # ~15 min warm

Test 10. Three coefficients in the current fit (data/latest/weights.csv) have the
opposite sign to OFFENSE_HIGHER_BETTER. Coefficients are refit before every week,
so one fit says little. This refits the frozen recipe before every walk-forward
week 2021-2025 (exactly the fits the walk-forward makes) and reports, per feature,
how often the sign matches the direction map. Stable wrong signs point to
suppressor effects (correlation with other inputs); frequent flips point to noise.

Test 11. The production held-out predictions (recipe chosen on earlier seasons
only) split into the rows the pre-registration in research/PREREGISTRATION.md
names: games where the model picks the moneyline underdog, big model-market gaps
and week groups. Each row: model ROI, same-row market favorite, market-correct
null, and paired log loss vs the no-vig moneyline market. Diagnostics only.
"""
import numpy as np
import pandas as pd

from _common import FULL, LAST, availability, cache_dir_from_argv, load_inputs, log, m, outer

FROZEN = {'family': 'rates_core_avail_cs', 'half_life': 8., 'ridge': .1}  # data/frozen_recipe_2026.json


def expected_sign(name):
    """+1/-1 if a higher home-minus-away value should raise the home win probability; None if undirected."""
    if name == 'site': return None
    if name.startswith('d__avail__'): return 1 if name.endswith('qb_delta') else -1
    _, role, _, metric = name.split('__')
    hb = m.OFFENSE_HIGHER_BETTER.get(metric)
    if hb is None: return None
    return 1 if (hb != (role == 'allowed')) else -1


def weekly_fits(feats, recipe):
    f = feats[recipe['half_life']]
    valid = ((f.season >= m.BACKTEST_FIRST_SEASON) & (f.season <= LAST)
             & f['home won'].isin([0., 1.]) & f.ready)
    rows = []
    for (year, week), _ in f.loc[valid].groupby(['season', 'week'], sort=True):
        fit = m.fit_composite(f[m.before(f, int(year), int(week))], recipe, int(year), int(week))
        rows.append({'season': int(year), 'week': int(week), **dict(zip(fit['names'], fit['beta']))})
    return pd.DataFrame(rows)


def sign_table(fits):
    held = fits.season >= 2023
    lines = ['| Feature | Expected | Median coef | Expected sign, all fits | Expected sign, 2023–25 fits | Last fit (2025) |',
             '|---|:---:|---:|---:|---:|---:|']
    for name in [c for c in fits.columns if c not in ('season', 'week')]:
        s = expected_sign(name)
        if s is None: continue
        b = fits[name]
        ok, ok_h = (np.sign(b) == s).mean(), (np.sign(b[held]) == s).mean()
        flag = ' **wrong**' if np.sign(b.iloc[-1]) != s else ''
        label = name.replace('d__for__rates_core__', 'Off ').replace('d__allowed__rates_core__', 'Def allowed ').replace('d__avail__', 'Avail ')
        lines.append(f"| {label} | {'+' if s > 0 else '−'} | {b.median():+.3f} | {100 * ok:.0f}% | {100 * ok_h:.0f}% | {b.iloc[-1]:+.3f}{flag} |")
    return '\n'.join(lines) + f'\n\n{len(fits)} weekly fits ({fits.season.min()}–{fits.season.max()}), recipe {m.recipe_key(FROZEN)}.'


def subset_row(name, d):
    mb, fb = m.flat_bets(d, 'model_wp'), m.flat_bets(d, 'market_ml_wp')
    keep = mb.units.notna() & fb.units.notna()
    if keep.sum() < 2: return f'| {name} | {int(keep.sum())} | – | – | – | – | – |'
    r = m.roi_summary(mb[keep]); f = m.roi_summary(fb[keep])
    y = d['home won'].to_numpy(float)
    gain = m.ll(y, np.clip(d.market_ml_wp, 1e-6, 1 - 1e-6)) - m.ll(y, d.model_wp)  # positive = model better
    gain = gain[np.isfinite(gain)]
    return (f"| {name} | {r['bets']} | {r['units']:+.2f} | {100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} | "
            f"{100 * f['roi']:+.1f}% | {100 * r['null_roi']:+.1f}% | {gain.mean():+.4f} ± {gain.std(ddof=1) / np.sqrt(len(gain)):.4f} |")


def disagreement(held):
    d = held.copy(); d['market_ml_wp'] = m.market_ml_wp(d)
    d = d[np.isfinite(d.market_ml_wp)]
    gap_ml, gap_sp = (d.model_wp - d.market_ml_wp).abs(), (d.model_wp - d.market_wp).abs()
    under = (d.model_wp > .5) != (d.market_ml_wp > .5)
    wk = d.week
    rows = [('All held-out games', d), ('Model agrees with ML favorite', d[~under]),
            ('Model picks ML underdog', d[under]),
            ('|model − ML market| ≥ 0.10', d[gap_ml >= .10]),
            ('|model − ML market| > 0.17', d[gap_ml > .17]),
            ('|model − spread market| > 0.17', d[gap_sp > .17]),
            ('Weeks 1–4', d[wk <= 4]), ('Weeks 5–9', d[(wk >= 5) & (wk <= 9)]),
            ('Weeks 10–13', d[(wk >= 10) & (wk <= 13)]), ('Weeks 14–18', d[(wk >= 14) & (wk <= 18)]),
            ('Postseason (week 19+)', d[wk >= 19])]
    head = ('| Rows (held-out 2023–25) | Bets | Units | Model ROI ± SE | Same-row favorite ROI | Market-correct null | LL gain vs ML market |\n'
            '|---|---:|---:|---:|---:|---:|---:|')
    return head + '\n' + '\n'.join(subset_row(n, x) for n, x in rows)


def main():
    inp = load_inputs(cache_dir_from_argv())
    avail = availability(inp)
    feats = {h: m.lagged_features(inp['box'], inp['sched'], h, avail) for h in m.TEAM_HALF_LIVES}
    m.FEATURE_FAMILIES = FULL
    oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), inp['sched'])
    held, picks = outer(oof, FULL)
    log(f'held-out picks: {picks}')
    print('\n### Test 10: coefficient sign stability\n')
    print(sign_table(weekly_fits(feats, FROZEN)))
    print('\n### Test 11: where the held-out ROI comes from\n')
    print(disagreement(held))
    log('done')


if __name__ == '__main__':
    main()
