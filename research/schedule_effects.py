"""Test 18: does the closing moneyline misprice schedule spots (rest, travel, byes, calendar)?

    python research/schedule_effects.py [CACHE_DIR]     # ~1 min (schedules only)

Target: actual minus implied, i.e. the home result (1 win, 0 loss) minus the no-vig
closing-moneyline home probability, on every priced, decided regular-season game
2010-2025 (nflverse schedules). If the market prices a factor, that residual is
flat across it. Every feature is known before kickoff (schedule, rest, locations).

For each factor: the coefficient of the factor in y ~ logit(q) + factor (per 1 SD,
or per unit for indicators), its z, the log-loss gain over the market alone, and
the residual and flat 1u ROI of always backing the side the factor favours where it
applies. About 20 factors are tested, so read |z| < ~2.9 (Bonferroni 5%) as noise.

Travel uses each team's home stadium (by season, for relocations) and a fixed
location for neutral sites; a trip is the great-circle distance from the team's
previous game (or home before its first game). Time-zone shift is longitude
difference / 15 h. Body clock = ET kickoff hour + the team's home offset to ET.
"""
import math

import numpy as np
import pandas as pd
from scipy.special import logit

from _common import cache_dir_from_argv, log, m
from market_info import logistic

FIRST, LAST = 2010, 2025
HOME = {'ARI': (33.528, -112.263), 'ATL': (33.755, -84.401), 'BAL': (39.278, -76.623), 'BUF': (42.774, -78.787),
        'CAR': (35.226, -80.853), 'CHI': (41.862, -87.617), 'CIN': (39.095, -84.516), 'CLE': (41.506, -81.700),
        'DAL': (32.748, -97.093), 'DEN': (39.744, -105.020), 'DET': (42.340, -83.046), 'GB': (44.501, -88.062),
        'HOU': (29.685, -95.411), 'IND': (39.760, -86.164), 'JAX': (30.324, -81.637), 'KC': (39.049, -94.484),
        'LV': (36.091, -115.184), 'LAC': (33.953, -118.339), 'LA': (33.953, -118.339), 'MIA': (25.958, -80.239),
        'MIN': (44.974, -93.258), 'NE': (42.091, -71.264), 'NO': (29.951, -90.081), 'NYG': (40.813, -74.074),
        'NYJ': (40.813, -74.074), 'PHI': (39.901, -75.168), 'PIT': (40.447, -80.016), 'SF': (37.403, -121.970),
        'SEA': (47.595, -122.332), 'TB': (27.976, -82.503), 'TEN': (36.166, -86.771), 'WAS': (38.908, -76.864)}
RELOCATED = {('LV', 2019): (37.752, -122.201), ('LAC', 2016): (32.783, -117.120), ('LA', 2015): (38.633, -90.188)}
TZ = {**{t: 0 for t in ('ATL', 'BAL', 'BUF', 'CAR', 'CIN', 'CLE', 'DET', 'IND', 'JAX', 'MIA', 'NE', 'NYG', 'NYJ',
                         'PHI', 'PIT', 'TB', 'WAS')},
      **{t: -1 for t in ('CHI', 'DAL', 'GB', 'HOU', 'KC', 'MIN', 'NO', 'TEN')},
      'DEN': -2, 'ARI': -3, **{t: -3 for t in ('LV', 'LAC', 'LA', 'SF', 'SEA')}}
VENUE = {'Wembley': (51.556, -0.280), 'Tottenham': (51.604, -0.066), 'Twickenham': (51.456, -0.342),
         'Azteca': (19.303, -99.150), 'Banorte': (19.303, -99.150), 'Allianz': (48.219, 11.625),
         'Bayern': (48.219, 11.625), 'Deutsche Bank': (50.069, 8.645), 'Rogers': (43.641, -79.389),
         'Corinthians': (-23.545, -46.474), 'Maracana': (-22.912, -43.230), 'Melbourne': (-37.820, 144.983),
         'Stade de France': (48.924, 2.360), 'Bernabeu': (40.453, -3.688), 'Ford Field': HOME['DET'],
         'State Farm': HOME['ARI'], 'TIAA': HOME['JAX'], 'SoFi': HOME['LA'], 'Acrisure': HOME['PIT'],
         'FirstEnergy': HOME['CLE'], 'MetLife': HOME['NYG'], 'Lucas Oil': HOME['IND'], 'Hard Rock': HOME['MIA']}


def home_coords(team, season):
    for (t, upto), xy in RELOCATED.items():
        if t == team and season <= upto:
            return xy
    return HOME[team]


def team_tz(team, season):
    if team == 'LA' and season <= 2015:
        return -1  # St. Louis
    return TZ[team]


def miles(a, b):
    (la1, lo1), (la2, lo2) = map(lambda p: (math.radians(p[0]), math.radians(p[1])), (a, b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def game_site(r):
    if str(r.location).lower() == 'neutral':
        for key, xy in VENUE.items():
            if key.lower() in str(r.stadium).lower():
                return xy
    return home_coords(r.home_team, r.season)


def team_games(s):
    """One row per team-game with pregame schedule features."""
    rows = []
    for r in s.itertuples(index=False):
        site = game_site(r)
        for side, team, opp in (('home', r.home_team, r.away_team), ('away', r.away_team, r.home_team)):
            rows.append({'game_id': r.game_id, 'season': r.season, 'week': r.week, 'team': team, 'side': side,
                         'site': site, 'rest': getattr(r, f'{side}_rest'), 'gametime': r.gametime})
    t = pd.DataFrame(rows).sort_values(['team', 'season', 'week']).reset_index(drop=True)
    out = []
    for (team, yr), g in t.groupby(['team', 'season'], sort=False):
        prev = home_coords(team, yr); trips, road = [], 0
        bye_weeks = [w for w in range(2, 19) if w not in set(g.week) and w < g.week.max()]
        for x in g.itertuples(index=False):
            trip = miles(prev, x.site); prev = x.site; trips.append(trip)
            road = road + 1 if x.side == 'away' else 0
            hh, mm = map(int, str(x.gametime).split(':')) if isinstance(x.gametime, str) and ':' in x.gametime else (13, 0)
            tz = team_tz(team, yr)
            later_bye = [b for b in bye_weeks if b > x.week]
            out.append({'game_id': x.game_id, 'side': x.side, 'rest': float(x.rest),
                        'post_bye': float(x.rest >= 13), 'short_week': float(x.rest <= 5),
                        'trip_miles': trip, 'travel_3g': float(sum(trips[-3:])),
                        'tz_shift': abs(x.site[1] - home_coords(team, yr)[1]) / 15.,
                        'body_clock': hh + mm / 60 + tz, 'road_streak': float(road),
                        'pre_bye': float(bool(later_bye) and min(later_bye) == x.week + 1),
                        'games_since_bye': float(sum(w > max([b for b in bye_weeks if b < x.week], default=99) for w in g.week[g.week < x.week])),
                        'bye_done': float(any(b < x.week for b in bye_weeks))})
    return pd.DataFrame(out)


def build(sched):
    full = sched[(sched.season >= FIRST) & (sched.season <= LAST)].copy()
    tg = team_games(full)  # every scheduled game, so a cancelled game is not mistaken for a bye
    s = full[full['home won'].isin([0., 1.])].copy()
    s['q'] = m.market_ml_wp(s)
    s = s[np.isfinite(s.q)]
    h = tg[tg.side == 'home'].drop(columns='side').set_index('game_id')
    a = tg[tg.side == 'away'].drop(columns='side').set_index('game_id')
    d = s.set_index('game_id').join(h.add_prefix('h_')).join(a.add_prefix('a_')).reset_index()
    for c in ('rest', 'post_bye', 'short_week', 'trip_miles', 'travel_3g', 'tz_shift', 'road_streak', 'pre_bye'):
        d[f'd_{c}'] = d[f'h_{c}'] - d[f'a_{c}']
    d['a_early_body'] = (d.a_body_clock <= 10.6).astype(float)  # e.g. a Pacific team at 1:00 PM ET
    d['d_games_since_bye'] = d.h_games_since_bye.where(d.h_bye_done == 1, 0) - d.a_games_since_bye.where(d.a_bye_done == 1, 0)
    d['neutral'] = (d.location.str.lower() == 'neutral').astype(float)
    site = [game_site(r) for r in d.itertuples(index=False)]
    d['international'] = [float(n == 1 and (lon > -60 or lat < 20)) for n, (lat, lon) in zip(d.neutral, site)]
    d['primetime'] = d.gametime.astype(str).str[:2].astype(int).ge(19).astype(float)
    d['div'] = d.div_game.astype(float)
    return d


FACTORS = [  # (column, label, kind) kind: 'cont' home-minus-away continuous; 'ind' indicator favouring home if +1
    ('d_rest', 'Rest days, home − away', 'cont'),
    ('d_post_bye', 'Off a bye, home − away', 'ind'),
    ('d_short_week', 'Short week (≤ 5 days), home − away', 'ind'),
    ('d_trip_miles', 'This trip, miles, home − away', 'cont'),
    ('d_travel_3g', 'Miles over last 3 trips, home − away', 'cont'),
    ('d_tz_shift', 'Time zones from home, home − away', 'cont'),
    ('a_early_body', 'Away body clock ≤ 10:36 AM', 'ind'),
    ('d_road_streak', 'Consecutive road games, home − away', 'cont'),
    ('d_pre_bye', 'Bye next week, home − away', 'ind'),
    ('d_games_since_bye', 'Games since bye, home − away', 'cont'),
    ('div', 'Division game (home)', 'ind'),
    ('primetime', 'Primetime kickoff (home)', 'ind'),
    ('international', 'International game (designated home)', 'ind'),
]


def factor_table(d):
    y = d['home won'].to_numpy(float); mk = logit(d.q.to_numpy())
    _, _, base = logistic(mk[:, None], y)
    lines = ['| Factor | Games where it applies | Coef beyond market | z | LL gain | Actual − implied where it applies | Flat ROI backing it |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for col, label, kind in FACTORS:
        x = d[col].to_numpy(float)
        on = x != 0
        z = x / (x.std() or 1.) if kind == 'cont' else x
        b, se, l = logistic(np.column_stack([mk, z]), y)
        # residual and ROI from the side the factor favours, where it applies
        side_home = x[on] > 0
        res = np.where(side_home, y[on] - d.q.to_numpy()[on], (1 - y[on]) - (1 - d.q.to_numpy()[on]))
        pick = d[on].assign(p=np.where(side_home, .99, .01))
        r = m.roi_summary(m.flat_bets(pick, 'p'))
        lines.append(f'| {label} | {int(on.sum())} | {b[2]:+.3f} ± {se[2]:.3f} | {b[2] / se[2]:+.1f} | {base - l:+.4f} | '
                     f'{100 * res.mean():+.1f} pts ± {100 * res.std(ddof=1) / math.sqrt(on.sum()):.1f} | '
                     f'{100 * r["roi"]:+.1f}% ± {100 * r["roi_se"]:.1f} (null {100 * r["null_roi"]:+.1f}%) |')
    return '\n'.join(lines)


def trend_table(d, key, label):
    lines = [f'| {label} | Games | Home actual − implied | Favourite actual − implied | Favourite flat ROI |', '|---|---:|---:|---:|---:|']
    for k, g in d.groupby(key):
        y, q = g['home won'].to_numpy(float), g.q.to_numpy()
        fav = q > .5; fy, fq = np.where(fav, y, 1 - y), np.where(fav, q, 1 - q)
        r = m.roi_summary(m.flat_bets(g.assign(p=np.where(fav, .99, .01)), 'p'))
        n = len(g)
        lines.append(f'| {k} | {n} | {100 * (y - q).mean():+.1f} ± {100 * (y - q).std(ddof=1) / math.sqrt(n):.1f} | '
                     f'{100 * (fy - fq).mean():+.1f} ± {100 * (fy - fq).std(ddof=1) / math.sqrt(n):.1f} | '
                     f'{100 * r["roi"]:+.1f}% |')
    return '\n'.join(lines)


def main():
    m.CACHE_DIR = str(cache_dir_from_argv())
    sched = pd.concat([m.load_schedule(y) for y in range(FIRST, LAST + 1)], ignore_index=True)
    d = build(sched)
    log(f'{len(d)} priced, decided games {FIRST}-{LAST}')
    print('\n### Test 18A: schedule factors vs the closing moneyline\n')
    print(factor_table(d))
    d['week_group'] = pd.cut(d.week, [0, 4, 9, 13, 17, 18], labels=['1–4', '5–9', '10–13', '14–17', '18'])
    d['slot'] = np.select([d.weekday.eq('Thursday'), d.weekday.eq('Monday'), d.primetime.eq(1),
                           d.gametime.astype(str).str[:2].astype(int).ge(16)],
                          ['Thursday', 'Monday', 'Sunday/Sat night', 'Late afternoon'], 'Early afternoon')
    d['era'] = pd.cut(d.season, [2009, 2013, 2017, 2021, 2025], labels=['2010–13', '2014–17', '2018–21', '2022–25'])
    print('\n### Test 18B: temporal trends in actual − implied\n')
    for key, label in (('era', 'Seasons'), ('week_group', 'Weeks'), ('slot', 'Kickoff slot')):
        print(trend_table(d, key, label) + '\n')
    log('done')


if __name__ == '__main__':
    main()
