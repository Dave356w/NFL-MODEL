"""Test 20: do schedule and form features improve the v1.10 composite?

    python research/trend_features.py [CACHE_DIR]     # ~10 min warm

Tests 18-19 asked whether the closing line misprices schedule spots and team form
(it does not). This asks whether the MODEL, which trails the market, gains from
them. Two home-minus-away feature sets, each added to the v1.10 families and run
through the production grid with nested selection (recipe per held-out season from
earlier seasons only), then scored game by game against v1.10 on the same priced
held-out games. No market input enters either set.

  schedule : rest days, off a bye, bye next week, this trip's miles, time zones
             from home, early body clock (<= 10:36 AM), consecutive road games
  form     : streak entering the game (+wins / -losses), last game's margin
"""
import numpy as np
import pandas as pd

from _common import DHEAD, HEAD, LAST, availability, cache_dir_from_argv, diff_row, load_inputs, log, m, outer, row, score
from schedule_effects import team_games
from team_situations import situations, team_rows

SCHEDULE = ('rest', 'post_bye', 'pre_bye', 'trip_miles', 'tz_shift', 'early_body', 'road_streak')
FORM = ('streak', 'last_margin')
SETS = {'sch': tuple(f'd__sch_{c}' for c in SCHEDULE), 'form': tuple(f'd__form_{c}' for c in FORM)}


def side_features(sched):
    tg = team_games(sched)
    tg['early_body'] = (tg.body_clock <= 10.6).astype(float)
    st = situations(team_rows(sched))[['game_id', 'team', 'streak', 'last_margin']]
    teams = pd.concat([sched[['game_id', 'home_team']].rename(columns={'home_team': 'team'}).assign(side='home'),
                       sched[['game_id', 'away_team']].rename(columns={'away_team': 'team'}).assign(side='away')])
    st = st.merge(teams, on=['game_id', 'team'], how='inner')
    return tg.merge(st[['game_id', 'side', 'streak', 'last_margin']], on=['game_id', 'side'], how='left')


def add_features(f, sf):
    h = sf[sf.side == 'home'].set_index('game_id'); a = sf[sf.side == 'away'].set_index('game_id')
    out = f.copy()
    for c in SCHEDULE:
        out[f'd__sch_{c}'] = (f.game_id.map(h[c]) - f.game_id.map(a[c])).to_numpy(float)
    for c in FORM:
        out[f'd__form_{c}'] = (f.game_id.map(h[c]).fillna(0) - f.game_id.map(a[c]).fillna(0)).to_numpy(float)
    return out


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched = inp['sched']
    sf = side_features(sched)
    avail = availability(inp)
    feats = {h: add_features(m.lagged_features(inp['box'], sched, h, avail), sf) for h in m.TEAM_HALF_LIVES}
    log('features built')
    base = tuple(m.FEATURE_FAMILIES)  # v1.10 production
    names = m.feature_names

    def feature_names(fam):
        for tag, cols in SETS.items():
            if fam.endswith('_' + tag):
                return names(fam[:-len(tag) - 1]) + list(cols)
        return names(fam)
    m.feature_names = feature_names
    variants = {tag: tuple(f'{b}_{tag}' for b in base) for tag in SETS}
    m.FEATURE_FAMILIES = base + sum(variants.values(), ())
    oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
    prod, pp = outer(oof, base)
    a = score(prod)
    log(f'v1.10 picks {pp}')
    res = {}
    for tag, fams in variants.items():
        held, pk = outer(oof, fams); log(f'{tag} picks {pk}')
        res[tag] = (held, score(held))
    print('\n### Test 20: schedule and form features added to v1.10\n' + HEAD)
    print(row('v1.10 production', a))
    for tag, (_, s) in res.items():
        print(row(f'+ {tag} features', s))
    print('\n' + DHEAD)
    for tag, (_, s) in res.items():
        print(diff_row(f'+ {tag} vs v1.10', s, a))
    wk = prod.week.to_numpy()
    for tag, (_, s) in res.items():
        print(f'\n{tag}, by week:\n\n| Weeks | Games | ROI difference | Log-loss gain |\n|---|---:|---:|---:|')
        for lo, hi, name in ((1, 4, '1–4'), (5, 9, '5–9'), (10, 13, '10–13'), (14, 18, '14–18')):
            k = (wk >= lo) & (wk <= hi)
            du = (s['units_vec'] - a['units_vec']).to_numpy()[k]; du = du[np.isfinite(du)]
            dl = (a['ll_vec'] - s['ll_vec'])[k]
            print(f'| {name} | {k.sum()} | {100 * du.mean():+.2f} pts ± {100 * du.std(ddof=1) / np.sqrt(len(du)):.2f} | '
                  f'{dl.mean():+.4f} ± {dl.std(ddof=1) / np.sqrt(len(dl)):.4f} |')
    log('done')


if __name__ == '__main__':
    main()
