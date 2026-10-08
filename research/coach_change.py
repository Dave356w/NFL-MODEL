"""Test 34: a new head coach.

    python research/coach_change.py [CACHE_DIR]     # ~25 min warm

Plan and decision rule: research/README.md, Tests 33-34 (committed before any result).
One input added to both v1.12 families in every week: d__new_coach = home flag - away flag, where
a team's flag is 1 if its head coach for this game (nflverse schedule home_coach / away_coach,
named before kickoff) differs from the coach listed for its last regular-season game of the
previous season. Decided on held-out 2017-20; 2023-25 secondary (research/_bases.py).
"""
import pandas as pd

from _bases import compare, data_ok, load_basis, window_gain
from _common import cache_dir_from_argv, log, m

FEATURE = 'd__new_coach'
LEVEL = .975


def team_coaches(sched):
    """Long frame (season, week, game_id, team, coach) from a schedule with home_coach/away_coach."""
    h = sched[['season', 'week', 'game_id', 'home_team', 'home_coach']].rename(columns={'home_team': 'team', 'home_coach': 'coach'})
    a = sched[['season', 'week', 'game_id', 'away_team', 'away_coach']].rename(columns={'away_team': 'team', 'away_coach': 'coach'})
    return pd.concat([h, a], ignore_index=True)


def new_coach_flags(sched, prev_sched):
    """{(game_id, team): 1.0 if the team's coach for the game differs from its coach in its last
    regular-season game of the previous season, else 0.0}. No previous-season coach -> 0."""
    tc = team_coaches(sched)
    prev = team_coaches(prev_sched).sort_values(['season', 'week'])
    last = prev.groupby(['season', 'team']).coach.last().to_dict()
    flags = {}
    for r in tc.itertuples(index=False):
        before = last.get((int(r.season) - 1, r.team))
        flags[(r.game_id, r.team)] = float(isinstance(before, str) and isinstance(r.coach, str) and r.coach != before)
    return flags


def add_feature(f, flags):
    f = f.copy()
    f[FEATURE] = [flags.get((g, h), 0.) - flags.get((g, a), 0.) for g, h, a in zip(f.game_id, f.home, f.away)]
    return f


def main():
    cache = cache_dir_from_argv()
    names = m.feature_names
    results = {}
    for kind in ('old', 'recent'):
        basis = load_basis(kind, cache)
        years = sorted(basis['sched'].season.unique())
        prev = pd.concat([m.load_schedule(min(years) - 1), basis['sched']], ignore_index=True)
        flags = new_coach_flags(basis['sched'], prev)
        tc = team_coaches(basis['sched'])
        tc['new'] = [flags[(g, t)] for g, t in zip(tc.game_id, tc.team)]
        first = tc.sort_values('week').groupby(['season', 'team']).new.first()
        later = tc.groupby(['season', 'team']).new.max() - first
        print(f'\n{kind}: teams with a new head coach in week 1, by season: {first.groupby(level=0).sum().astype(int).to_dict()}; '
              f'teams that changed coach during the season: {int((later > 0).sum())}')
        arm = {h: add_feature(f, flags) for h, f in basis['feats'].items()}
        f8 = arm[m.TEAM_HALF_LIVES[0]]
        held = f8.season.isin(basis['outer']) & f8['home won'].isin([0., 1.]) & f8.ready
        print(f'{kind}: held-out games with a nonzero input: {int((f8.loc[held, FEATURE] != 0).sum())} of {int(held.sum())}')
        if kind == 'old': print('\n### Test 34 result')
        results[kind] = compare('Test 34: new head coach', basis, arm_feats=arm,
                                arm_names=lambda fam: names(fam) + [FEATURE], level=LEVEL)
    old, rec = results['old'], results['recent']
    g14, n14 = window_gain(old, 1, 4)
    print(f'\n2017–20 weeks 1–4: LL gain {g14:+.4f} (n={n14}); 2023–25 gain {rec["d"].mean():+.4f}')
    if not data_ok(old): verdict = 'not run (data check failed)'
    elif old['hi'] < 0 or old['hi'] < .001 or g14 <= 0: verdict = 'dropped'
    elif old['lo'] > 0 and rec['d'].mean() > 0: verdict = 'supported'
    else: verdict = 'unresolved'
    print(f'**Test 34 verdict: {verdict}**')
    log('done')


if __name__ == '__main__':
    main()
