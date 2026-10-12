"""AV research (research/av): leakage, availability and aggregation rules on synthetic fixtures.

The real-data integration check (the exact v1.15 control) runs only when the walk-forward outputs exist.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research')); sys.path.insert(0, str(ROOT / 'research' / 'av'))
import aggregation as ag  # noqa: E402
import availability as av  # noqa: E402
import models as md  # noqa: E402
import player_value as pv  # noqa: E402
import walkforward as wf  # noqa: E402
from _common import m  # noqa: E402

STATS0 = {c: 0. for c in ('passing_yards', 'rushing_yards', 'receiving_yards', *pv.IMPACT)}
ROSTER = {'QB': ['q1', 'q2'], 'OL': [f'o{i}' for i in range(1, 7)], 'RB': ['r1'], 'WRTE': ['w1', 'w2'],
          'DL': ['d1', 'd2'], 'LB': ['l1'], 'DB': ['b1', 'b2']}


def fixture(seasons=(2016, 2017, 2018), weeks=6, teams=('AAA', 'BBB')):
    """Two teams playing each other every week. Team AAA's players carry the listed ids; BBB's get a 'B'
    suffix. Starters play every snap; o6 (AAA's sixth lineman) and q2 never play."""
    rows, tg = [], []
    for s in seasons:
        for w in range(1, weeks + 1):
            gid = f'{s}_{w:02d}_{teams[1]}_{teams[0]}'
            for team, opp, sfx in ((teams[0], teams[1], ''), (teams[1], teams[0], 'B')):
                pts = 24. + (3 if team == teams[0] else 0) + w
                tg.append({'game_id': gid, 'season': s, 'week': w, 'team': team, 'opponent': opp, 'off_points': pts})
                for unit, ids in ROSTER.items():
                    for pid in ids:
                        if pid in ('o6', 'q2'): continue
                        off = unit in ('QB', 'OL', 'RB', 'WRTE')
                        r = {'game_id': gid, 'season': s, 'week': w, 'team': team, 'gsis_id': pid + sfx, 'unit': unit,
                             'off_snaps': 60. if off else 0., 'def_snaps': 0. if off else 60., 'share': 1., **STATS0}
                        if unit == 'QB': r['passing_yards'] = 250.
                        if unit == 'RB': r['rushing_yards'] = 100.
                        if unit == 'WRTE': r['receiving_yards'] = 125.
                        if unit in ('DL', 'LB', 'DB'): r['def_tackles_solo'] = 4.
                        rows.append(r)
    tg = pd.DataFrame(tg)
    opp = tg[['game_id', 'team', 'off_points']].rename(columns={'team': 'opponent', 'off_points': 'opp_off_points'})
    return pd.DataFrame(rows), tg.merge(opp, on=['game_id', 'opponent'])


def estimator(pgv, draft=None, rookie=None):
    draft = pd.DataFrame(columns=['gsis_id', 'draft_year', 'pick', 'w_av']) if draft is None else draft
    return pv.Estimator(pgv, pv.season_table(pgv), draft, rookie or {})


# ---- no lookahead in player value ----

def test_game_rav_uses_only_its_own_game_and_prior_league_mean():
    pg, tg = fixture()
    base = pv.game_rav(pg, tg)
    tg2 = tg.copy(); later = (tg2.season == 2018) & (tg2.week == 6)
    tg2.loc[later, ['off_points', 'opp_off_points']] = 80.  # a later game in the same season
    pg2 = pg.copy(); pg2.loc[(pg2.season == 2018) & (pg2.week == 6), 'passing_yards'] = 900.
    alt = pv.game_rav(pg2, tg2)
    k = (base.season == 2018) & (base.week < 6)
    assert np.allclose(base.rav[k], alt.rav[k])
    assert not np.allclose(base.rav[~k & (base.season == 2018)], alt.rav[~k & (base.season == 2018)])
    # League normalization is the previous season's: changing 2018 games cannot move it for 2018.
    assert pv.league_means(tg)[2018] == pv.league_means(tg2)[2018] == tg[tg.season == 2017].off_points.mean()


def test_pregame_rate_ignores_the_game_week_and_later():
    pg, tg = fixture()
    pgv = pv.game_rav(pg, tg)
    e1 = estimator(pgv)
    pg2 = pgv.copy(); pg2.loc[(pg2.season == 2018) & (pg2.week >= 5), 'rav'] *= 10
    e2 = estimator(pg2)
    for mode in ('prior', 'blend'):
        assert np.isclose(e1.rate('o1', 'OL', 2018, 5, mode)[0], e2.rate('o1', 'OL', 2018, 5, mode)[0])
    assert not np.isclose(e1.rate('o1', 'OL', 2018, 6, 'blend')[0], e2.rate('o1', 'OL', 2018, 6, 'blend')[0])


def test_no_final_season_value_before_the_season_completes():
    pg, tg = fixture()
    pgv = pv.game_rav(pg, tg)
    e1 = estimator(pgv)
    pg2 = pgv.copy(); pg2.loc[pg2.season == 2018, 'rav'] = 99.  # the whole 2018 season, final totals included
    e2 = estimator(pg2)
    for w in (1, 3, 6):  # prior-only every week; blend before week 5 equals prior
        assert np.isclose(e1.rate('q1', 'QB', 2018, w, 'prior')[0], e2.rate('q1', 'QB', 2018, w, 'prior')[0])
    for w in (1, 4):
        assert e2.rate('q1', 'QB', 2018, w, 'blend')[0] == e2.rate('q1', 'QB', 2018, w, 'prior')[0]
    # Within season the blend uses only completed weeks: week 5 sees weeks 1-4 of 2018.
    assert e2.rate('q1', 'QB', 2018, 5, 'blend')[0] > e1.rate('q1', 'QB', 2018, 5, 'blend')[0]


def _rookie_fixture():
    rng = np.random.default_rng(0)
    rows = []
    for yr in (2015, 2016, 2017, 2018):
        for i in range(20):
            pick = 1 + 12 * i
            rows.append({'gsis_id': f'p{yr}_{i}', 'season': yr, 'rav': 10 - np.log(pick) + rng.normal(0, .1),
                         'games': 10., 'appearances': 10, 'unit': 'DB', 'rate': np.nan, 'pick': pick})
    s = pd.DataFrame(rows); s['rate'] = s.rav / s.games
    draft = s[['gsis_id', 'season', 'pick']].rename(columns={'season': 'draft_year'})
    return s.drop(columns='pick'), draft


def test_rookie_priors_use_only_past_cohorts():
    s, draft = _rookie_fixture()
    p18 = pv.rookie_priors(s, draft, {}, 2018)['DB']
    s2 = s.copy(); s2.loc[s2.season == 2018, 'rate'] = 5.  # the 2018 cohort's own rookie season
    assert pv.rookie_priors(s2, draft, {}, 2018)['DB'] == p18
    assert pv.rookie_priors(s2, draft, {}, 2019)['DB'] != pv.rookie_priors(s, draft, {}, 2019)['DB']
    assert p18['a'] < 0 and p18['n_drafted'] == 60  # earlier picks project higher; three past cohorts


def test_rookie_without_history_gets_draft_prior_not_zero():
    s, draft = _rookie_fixture()
    pgv = pd.DataFrame(columns=['gsis_id', 'season', 'week', 'unit', 'rav', 'share'])
    e = pv.Estimator(pgv, s, draft.assign(w_av=np.nan), {})
    hi = e.rate('p2018_0', 'DB', 2018, 1)  # pick 1 of the 2018 class, no NFL history
    lo = e.rate('p2018_19', 'DB', 2018, 1)
    assert hi[2] == 'rookie_draft' and hi[0] > lo[0] > 0


def test_replacement_level_uses_only_earlier_seasons():
    pg, tg = fixture()
    s = pv.season_table(pv.game_rav(pg, tg))
    rep = pv.replacement_levels(s, 2018)
    s2 = s.copy(); s2.loc[s2.season == 2018, 'rate'] = 0.
    assert pv.replacement_levels(s2, 2018) == rep
    q = s[(s.season < 2018) & (s.unit == 'OL') & (s.games >= pv.REPLACEMENT_MIN_GAMES)].rate.quantile(.25)
    assert np.isclose(rep['OL'], q)


def test_transferred_player_keeps_identity_and_history():
    pg, tg = fixture()
    pg.loc[(pg.gsis_id == 'q1') & (pg.season == 2017), 'passing_yards'] = 400.  # q1 strong with AAA in 2017
    pg.loc[(pg.gsis_id == 'q1') & (pg.season == 2018), 'team'] = 'BBB'         # ...then plays for BBB
    pgv = pv.game_rav(pg, tg)
    e = estimator(pgv)
    vet = e.priors(2018)['QB']['vet']
    r, n, src = e.rate('q1', 'QB', 2018, 1, 'prior')
    assert src == 'history' and n > 0 and r != vet
    part = av.Participation(pgv, pd.DataFrame(columns=['season', 'week', 'team', 'gsis_id', 'report_status']),
                            pd.DataFrame(columns=['season', 'week', 'team', 'gsis_id', 'position', 'status',
                                                  'status_description_abbr']),
                            pd.DataFrame(columns=['season', 'week', 'team', 'qb_expected', 'qb_usual']),
                            pd.DataFrame(columns=['gsis_id', 'name']))
    b, unit = part.base_share('q1', 2018, 3)  # his recent games with BBB, same id
    assert b == 1. and unit == 'QB'


# ---- participation ----

def test_injured_starter_loses_participation_and_replacements_absorb_it():
    base = np.array([1., 1., .1, 0.]); slots = 2.1
    p0, _ = av.waterfill(base, np.ones(4), slots)
    assert np.allclose(p0, [1., 1., .1, 0.])
    p1, short = av.waterfill(base, np.array([0., 1., 1., 1.]), slots)  # starter 0 Out
    assert p1[0] == 0. and np.isclose(p1.sum(), slots) and short == 0.
    assert p1[2] > .1 and p1[3] > 0.  # the backups pick up the starter's snaps


def test_returning_starter_takes_his_role_back_first():
    # Stand-in (base .9 recently) and the returning starter (base 1.0) for one slot.
    p, _ = av.waterfill(np.array([1., .9]), np.ones(2), 1.)
    assert np.allclose(p, [1., 0.])


def test_questionable_is_handled_consistently():
    assert av.MULT == {'Out': 0., 'Doubtful': .15, 'Questionable': .65}
    p, _ = av.waterfill(np.array([1., 0.]), np.array([.65, 1.]), 1.)
    assert np.isclose(p[0], .65) and np.isclose(p[1], .35)
    pg, tg = fixture(seasons=(2018,))
    pgv = pv.game_rav(pg, tg)
    rost = pd.DataFrame([{'season': 2018, 'week': w, 'team': 'AAA', 'gsis_id': pid, 'position': 'T' if u == 'OL' else
                          {'QB': 'QB', 'RB': 'RB', 'WRTE': 'WR', 'DL': 'DE', 'LB': 'LB', 'DB': 'CB'}[u], 'status': 'ACT',
                          'status_description_abbr': 'A01'} for w in range(1, 7) for u, ids in ROSTER.items() for pid in ids])
    inj = pd.DataFrame([{'season': 2018, 'week': 5, 'team': 'AAA', 'gsis_id': 'o1', 'report_status': 'Questionable'},
                        {'season': 2018, 'week': 5, 'team': 'AAA', 'gsis_id': 'o2', 'report_status': 'Doubtful'},
                        {'season': 2018, 'week': 5, 'team': 'AAA', 'gsis_id': 'o3', 'report_status': 'Out'},
                        {'season': 2018, 'week': 5, 'team': 'AAA', 'gsis_id': 'o4', 'report_status': None}])
    part = av.Participation(pgv, inj, rost, pd.DataFrame(columns=['season', 'week', 'team', 'qb_expected', 'qb_usual']),
                            pd.DataFrame(columns=['gsis_id', 'name']))
    df, slots, _ = part.team_week(2018, 5, 'AAA')
    mult = df.set_index('gsis_id').mult
    assert (mult['o1'], mult['o2'], mult['o3'], mult['o4'], mult['o5']) == (.65, .15, 0., 1., 1.)
    assert np.isclose(slots['OL'], 5.)


def test_game_week_reserve_and_departures_count_out():
    pg, tg = fixture(seasons=(2018,))
    pgv = pv.game_rav(pg, tg)
    pos = {'QB': 'QB', 'OL': 'T', 'RB': 'RB', 'WRTE': 'WR', 'DL': 'DE', 'LB': 'LB', 'DB': 'CB'}
    rows = []
    for w in range(1, 7):
        for u, ids in ROSTER.items():
            for pid in ids:
                if pid == 'w2' and w == 4: continue  # w2 gone from the week-4 roster: departed for week 5
                st = 'RES' if (pid == 'o1' and w == 5) else 'ACT'  # o1 to IR on the game week's own roster
                rows.append({'season': 2018, 'week': w, 'team': 'AAA', 'gsis_id': pid, 'position': pos[u], 'status': st,
                             'status_description_abbr': 'R01' if st == 'RES' else 'A01'})
    part = av.Participation(pgv, pd.DataFrame(columns=['season', 'week', 'team', 'gsis_id', 'report_status']),
                            pd.DataFrame(rows), pd.DataFrame(columns=['season', 'week', 'team', 'qb_expected', 'qb_usual']),
                            pd.DataFrame(columns=['gsis_id', 'name']))
    df = part.team_week(2018, 5, 'AAA')[0].set_index('gsis_id')
    assert df.mult['o1'] == 0. and df.roster_out['o1'] and df.mult['w2'] == 0. and df.departed['w2']


# ---- aggregation ----

def test_positional_contributions_use_matching_units():
    # One full-time lineman worth exactly 0.6 rAV per game: his rate is 0.6 per FULL game.
    rows = [{'gsis_id': 'x', 'season': 2017, 'week': w, 'unit': 'OL', 'rav': .3, 'share': .5} for w in range(1, 11)]
    pgv = pd.DataFrame(rows)
    e = estimator(pgv)
    r, n, _ = e.rate('x', 'OL', 2018, 1, 'prior')
    assert np.isclose(n, 5.) and r > 0  # 10 half-games in the latest season (weight 1) = 5 full games
    raw = (10 * .3 + pv.PRIOR_GAMES * e.priors(2018)['OL']['vet']) / (5. + pv.PRIOR_GAMES)
    assert np.isclose(r, raw)
    v = ag.unit_values(np.array([.5]), np.array([.6]), .2, 'RB')
    assert np.isclose(v['raw'], .3) and np.isclose(v['rel'], .2)  # rate x share = rAV for the game


def test_weak_link_penalizes_a_deficient_starter():
    p = np.ones(5)
    even = ag.unit_values(p, np.full(5, .6), .5, 'OL')
    assert np.isclose(even['weak'], even['rel'])  # equal starters: weak-link equals linear
    hole = ag.unit_values(p, np.array([.7, .7, .6, .6, .4]), .5, 'OL')   # same linear total as below
    flat = ag.unit_values(p, np.array([.6, .6, .6, .6, .6]), .5, 'OL')
    assert np.isclose(hole['rel'], flat['rel']) and hole['weak'] < flat['weak']
    assert hole['min'] < hole['weak']


# ---- models ----

def _games(n_weeks=12, seasons=(2019, 2020)):
    rng = np.random.default_rng(1)
    teams = [f'T{i}' for i in range(8)]
    rows = []
    for s in seasons:
        for w in range(1, n_weeks + 1):
            perm = rng.permutation(teams)
            for i in range(0, 8, 2):
                x = rng.normal(0, 1)
                res = float(np.round(3 * x + rng.normal(0, 10)))
                rows.append({'game_id': f'{s}_{w}_{i}', 'season': s, 'week': w, 'home': perm[i], 'away': perm[i + 1],
                             'site': 1., 'result': res, 'home won': 1. if res > 0 else 0. if res < 0 else .5, 'x': x})
    return pd.DataFrame(rows).sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def test_residual_signs_agree_for_both_teams():
    f = pd.DataFrame([{'game_id': 'g1', 'season': 2020, 'week': 1, 'home': 'H', 'away': 'A', 'result': 10.},
                      {'game_id': 'g2', 'season': 2020, 'week': 2, 'home': 'A', 'away': 'H', 'result': np.nan}])
    mu = pd.Series([4., 0.], index=f.index)
    for adj in (False, True):
        ah, aa = md.team_residual_states(f, mu, .9, 1., opponent_adjust=adj)
        # Week 2: H (away) carries +6 residual, A (home) carries -6, shrunk equally.
        assert np.isclose(aa[1], 3.) and np.isclose(ah[1], -3.)
        assert ah[0] == aa[0] == 0.


def test_dynamic_residuals_update_only_after_games_conclude():
    f = _games()
    mu = pd.Series(0., index=f.index)
    ah, aa = md.team_residual_states(f, mu, .9, 4.)
    f2 = f.copy(); late = (f2.season == 2020) & (f2.week >= 6)
    f2.loc[late, 'result'] = 50.
    bh, ba = md.team_residual_states(f2, mu, .9, 4.)
    k = ~((f.season == 2020) & (f.week >= 7)).to_numpy()
    assert np.allclose(ah[k], bh[k]) and np.allclose(aa[k], ba[k])  # week 6 states predate week 6 results
    assert not np.allclose(ah[~k], bh[~k])


def test_weekly_refits_use_earlier_observations_only():
    f = _games()
    with pytest.raises(ValueError):
        md.fit_margin(f, ['site', 'x'], 10., 2019, 5)  # training rows include week 5 and later
    old = m.MIN_TRAIN_GAMES; m.MIN_TRAIN_GAMES = 20
    try:
        mu, sg = md.walk_forward_margin(f, ['site', 'x'], 10.)
        f2 = f.copy(); late = (f2.season == 2020) & (f2.week >= 8)
        f2.loc[late, 'result'] = -f2.loc[late, 'result'] * 3
        mu2, sg2 = md.walk_forward_margin(f2, ['site', 'x'], 10.)
    finally:
        m.MIN_TRAIN_GAMES = old
    k = ~((f.season == 2020) & (f.week >= 9)).to_numpy()
    assert mu[k].notna().any() and np.allclose(mu[k].fillna(0), mu2[k].fillna(0)) and np.allclose(sg[k].fillna(0), sg2[k].fillna(0))
    assert not np.allclose(mu[~k], mu2[~k])


def test_recipe_selection_is_chronological():
    rng = np.random.default_rng(3); rows = []
    for yr in (2021, 2022, 2023, 2024, 2025):
        for i in range(40):
            y = float(rng.random() < .55)
            rows.append({'season': yr, 'home won': y, 'p__good_early': (.8 if y else .2) if yr < 2023 else .6,
                         'p__good_late': .55 if yr < 2023 else (.95 if y else .05)})
    o = pd.DataFrame(rows)
    wpcol, picks = wf.select(o, ['p__good_early', 'p__good_late'])
    # 2023 and 2024 see only 'early' strength; 2025 also sees 2023-24, where 'late' is better.
    assert picks == {2023: 'good_early', 2024: 'good_early', 2025: 'good_late'}
    assert (wpcol[o.season == 2023] == .6).all()
    # A season's own and later outcomes never change its pick.
    o2 = o.copy(); k = o2.season >= 2024
    o2.loc[k, 'p__good_late'] = 1 - o2.loc[k, 'home won'] * .9 - .05  # make 'late' terrible from 2024 on
    assert wf.select(o2, ['p__good_early', 'p__good_late'])[1][2024] == 'good_early'
    assert wf.select(o2, ['p__good_early', 'p__good_late'])[1][2023] == picks[2023]


def test_model_c_feature_rewrite():
    prod = m.FEATURE_FAMILIES[0]
    base = m.feature_names(prod)
    unit_out = [c for c in base if c.endswith('_out_cs')]
    assert len(unit_out) == 6 and 'd__avail__qb_delta' in base
    c1, c2, c3 = (md.c_feature_names(f'{prod}__{v}') for v in md.C_VARIANTS)
    assert not set(unit_out) & set(c1) and 'd__avail__qb_delta' in c1 and len(c1) == len(base)
    assert set(base) < set(c2) and len(c2) == len(base) + 6
    assert 'd__avail__qb_delta' not in c3 and 'd__av__loss_QB_blend' in c3
    assert md.c_feature_names(prod) == base


# ---- production untouched ----

def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_production_ledger_and_frozen_config_untouched():
    files = [ROOT / 'data' / 'forward_predictions.jsonl', *sorted((ROOT / 'data').glob('frozen_recipe_*.json'))]
    before = {f: _sha(f) for f in files}
    sig, rev, fams, names = m.config_signature(), m.REVISION, tuple(m.FEATURE_FAMILIES), m.feature_names
    pg, tg = fixture()
    pgv = pv.game_rav(pg, tg)
    estimator(pgv).rate('q1', 'QB', 2018, 6)
    md.team_residual_states(_games(), pd.Series(0., index=_games().index), .9, 4.)
    assert {f: _sha(f) for f in files} == before
    assert (m.config_signature(), m.REVISION, tuple(m.FEATURE_FAMILIES), m.feature_names) == (sig, rev, fams, names)
    assert m.REVISION == 'boxscore-composite-v1.16'
    src = '\n'.join(p.read_text() for p in (ROOT / 'research' / 'av').glob('*.py'))
    assert 'forward_predictions' not in src and 'frozen_recipe' not in src and 'STATE_DIR' not in src


# ---- integration: the exact v1.15 control on real data ----

def test_control_check_rejects_a_mismatch():
    held = pd.DataFrame({'wp__A': [.6, .4], 'home won': [1., 0.], 'home_moneyline': [-150., 120.],
                         'away_moneyline': [130., -140.]})
    res = wf.control_check(held, {'A': {2023: wf.CONTROL['pick']}})
    assert res['reproduced'] is False


@pytest.mark.skipif(not (ROOT / 'research' / 'av' / 'output' / 'control_check.json').exists(),
                    reason='real-data walk-forward outputs not present')
def test_v115_control_reproduced_on_real_data():
    cc = json.loads((ROOT / 'research' / 'av' / 'output' / 'control_check.json').read_text())
    assert cc['reproduced'], cc
    d = pd.read_csv(ROOT / 'research' / 'av' / 'output' / 'heldout_predictions.csv')
    assert d.game_id.is_unique and set(d.season) == {2023, 2024, 2025}
    for v in wf.PRIMARY:
        assert d[f'wp__{v}'].notna().all(), v  # every variant scored on every held-out game
