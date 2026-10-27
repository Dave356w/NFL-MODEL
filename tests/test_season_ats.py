"""Pooled ATS precedence, denominator, source labels and missing-lock behavior."""
import copy
import datetime as dt
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

import ats_locks
import build_site as b
import nfl_model as m
import season_ats as s


class SeasonATS(unittest.TestCase):
    def fixture(self):
        history = pd.DataFrame([
            dict(game_id='h', season=2026, week=5, home='IND', away='TEN', gameday='2026-10-11',
                 fixed_band_spread=7., spread_line=6.5, result=7.),
            dict(game_id='overlap', season=2026, week=6, home='IND', away='TEN', gameday='2026-10-18',
                 fixed_band_spread=4., spread_line=6.5, result=-6.),
            dict(game_id='pending', season=2026, week=7, home='IND', away='TEN', gameday='2026-10-25',
                 fixed_band_spread=4., spread_line=6.5, result=7.)])
        native = pd.DataFrame([
            dict(game_id='overlap', season=2026, week=6, revision=m.REVISION, home='IND', away='TEN',
                 model_wp=.73, spread_line=7., result=-6., generated_utc='2026-10-17T12:00:00Z',
                 kickoff_utc='2026-10-18T17:00:00Z'),
            dict(game_id='pending', season=2026, week=7, revision=m.REVISION, home='IND', away='TEN',
                 model_wp=.8, spread_line=7., result=np.nan, generated_utc='2026-10-20T12:00:00Z',
                 kickoff_utc='2026-10-25T17:00:00Z')])
        lock = dict(game_id='overlap', revision=m.REVISION, season=2026, week=6, home='IND', away='TEN',
                    model_wp=.73, market_spread=7., fixed_band_spread=7., selected_side='',
                    skip_reason='zero_edge', generated_utc='2026-10-17T12:00:00Z',
                    kickoff_utc='2026-10-18T17:00:00Z', lock_at_utc='2026-10-17T12:00:00Z',
                    policy_version='old', legacy_lock=True)
        latest = dict(manifest={'season':2026,'revision':m.REVISION}, fixed_band_ledger=history,
            fixed_band_rules=[dict(season=2026,training_max_season=2025,cuts=[3,7,10],magnitudes=[3,4,7,14])],
            ats_locks={(m.REVISION,'overlap'):lock}, board=pd.DataFrame())
        return latest, native

    def test_archived_skip_is_backfilled_at_its_saved_line_and_never_duplicates(self):
        latest,native = self.fixture()
        saved=copy.deepcopy(latest['ats_locks'])
        pool = s.build(latest,native)
        self.assertEqual(pool.game_id.nunique(),len(pool))
        row=pool.set_index('game_id').loc['overlap']
        # The saved 7-vs-7 skip is graded as the IND favorite at the saved line, not 6.5.
        self.assertEqual((row.fixed_band_ats_team,row.fixed_band_ats_handicap),('IND',-7.))
        self.assertEqual(row.fixed_band_ats_result,'L')
        self.assertEqual(row.fixed_band_ats_units,-1.)
        self.assertEqual(row.ats_basis,'Backfilled recorded skip')
        self.assertEqual(row.spread_line,7.)
        self.assertEqual(saved,latest['ats_locks'])

    def test_missing_post_adoption_lock_blocks_historical_and_native_reconstruction(self):
        latest,native=self.fixture()
        pool=s.build(latest,native).set_index('game_id')
        row=pool.loc['pending']
        # A known final score does not authorize a retrospective ATS lock.
        self.assertEqual(row.ats_status,'unavailable')
        self.assertEqual(row.fixed_band_ats_result,'')
        self.assertTrue(np.isnan(row.fixed_band_spread))

    def test_missing_post_adoption_snapshot_does_not_turn_history_into_a_bet(self):
        latest, _ = self.fixture()
        latest['fixed_band_ledger'] = latest['fixed_band_ledger'].query("game_id=='pending'").assign(
            kickoff_utc='2026-10-25T17:00:00Z', home_score=24., away_score=17.)
        latest['ats_locks'] = {}
        pool = s.build(latest, pd.DataFrame())
        row = pool.iloc[0]
        self.assertEqual((row.game_id, row.ats_status, row.ats_basis),
                         ('pending', 'unavailable', 'Awaiting ATS lock'))
        self.assertEqual((row.result, row.home_score, row.away_score), (7., 24., 17.))
        self.assertEqual((row.fixed_band_ats_result, row.fixed_band_ats_side), ('', ''))
        self.assertTrue(np.isnan(row.fixed_band_ats_units))
        self.assertTrue(np.isnan(row.spread_line))
        self.assertTrue(np.isnan(row.fixed_band_spread))
        self.assertEqual((s.summary(pool)['bets'], s.summary(pool)['unavailable']), (0, 1))

    def test_historical_timing_requires_a_provably_pre_adoption_deadline(self):
        boundary = ats_locks.ADOPTED_UTC + dt.timedelta(hours=1)
        cases = [
            ({'kickoff_utc': (boundary-dt.timedelta(seconds=1)).isoformat()}, True),
            ({'kickoff_utc': boundary.isoformat()}, False),
            ({'kickoff_utc': '2026-10-25T17:00:00Z', 'gameday': '2026-10-11'}, False),
            ({'gameday': '2026-10-18', 'gametime': '23:59'}, True),
            ({'gameday': '2026-10-19', 'gametime': '13:00'}, False),
            ({'gameday': '2026-10-18'}, True),
            ({'gameday': '2026-10-19'}, False),
            ({'gameday': '2026-10-25'}, False),
            ({'gameday': 'invalid'}, False),
            ({'gameday': 0}, False),
            ({'kickoff_utc': '2026-10-19'}, False),
            ({'kickoff_utc': '2026-10-19T13:00:00'}, False),
            ({'kickoff_utc': 0}, False),
            ({}, False),
        ]
        for timing, eligible in cases:
            with self.subTest(timing=timing):
                self.assertEqual(s.historical_before_adoption(timing), eligible)

    def test_saved_lock_overrides_post_adoption_history_without_native_snapshot(self):
        latest, _ = self.fixture()
        latest['fixed_band_ledger'] = latest['fixed_band_ledger'].query("game_id=='pending'")
        saved = dict(latest['ats_locks'][(m.REVISION, 'overlap')], game_id='pending', week=7,
                     kickoff_utc='2026-10-25T17:00:00Z', fixed_band_spread=3., market_spread=2.5,
                     selected_side='home', skip_reason=None, legacy_lock=False,
                     policy_version=ats_locks.POLICY_VERSION)
        latest['ats_locks'] = {(m.REVISION, 'pending'): saved}
        row = s.build(latest, pd.DataFrame()).iloc[0]
        self.assertEqual((row.ats_basis, row.ats_status, row.fixed_band_ats_result),
                         ('60-minute lock', 'graded', 'W'))
        self.assertEqual((row.spread_line, row.fixed_band_ats_handicap), (2.5, -2.5))

    def test_pre_adoption_unregistered_snapshot_is_explicit_replay(self):
        latest,native=self.fixture()
        latest['ats_locks']={}
        pool=s.build(latest,native).set_index('game_id')
        row=pool.loc['overlap']
        # Replay is regenerated, so its zero edge takes the market favorite.
        self.assertEqual(row.fixed_band_ats_side,'home')
        self.assertEqual(row.fixed_band_ats_handicap,-7.)
        self.assertEqual(row.fixed_band_ats_result,'L')
        self.assertEqual(row.ats_basis,'Replayed pregame forecast')

    def test_saved_v1_skip_is_labelled_backfill_while_v2_favorite_is_a_lock(self):
        latest,native=self.fixture()
        lock=latest['ats_locks'][(m.REVISION,'overlap')]
        lock.update(legacy_lock=False, policy_version='median-mov-ats-t60-2026-10-19-v1')
        row=s.build(latest,native).set_index('game_id').loc['overlap']
        self.assertEqual((row.fixed_band_ats_result,row.ats_basis),('L','Backfilled recorded skip'))
        lock.update(policy_version=ats_locks.POLICY_VERSION, selected_side='home', skip_reason=None)
        row=s.build(latest,native).set_index('game_id').loc['overlap']
        self.assertEqual((row.fixed_band_ats_result,row.fixed_band_ats_team),('L','IND'))
        self.assertEqual(row.ats_basis,'60-minute lock')

    def test_pickem_skip_is_not_backfilled(self):
        latest,native=self.fixture()
        lock=latest['ats_locks'][(m.REVISION,'overlap')]
        lock.update(market_spread=0., fixed_band_spread=0.)
        row=s.build(latest,native).set_index('game_id').loc['overlap']
        self.assertEqual((row.fixed_band_ats_result,row.ats_basis),('S','Recorded pregame'))

    def test_timed_lock_has_priority_and_uses_only_saved_lines(self):
        latest,native=self.fixture()
        lock=latest['ats_locks'][(m.REVISION,'overlap')]
        lock.update(legacy_lock=False, fixed_band_spread=3., market_spread=2.5,
                    selected_side='home', skip_reason=None, policy_version=ats_locks.POLICY_VERSION)
        pool=s.build(latest,native).set_index('game_id')
        self.assertEqual(pool.loc['overlap'].ats_basis,'60-minute lock')
        self.assertEqual(pool.loc['overlap'].spread_line,2.5)
        self.assertEqual(pool.loc['overlap'].fixed_band_ats_result,'L')

    def test_pending_skip_is_not_counted_until_final(self):
        latest,native=self.fixture()
        latest['fixed_band_ledger']=latest['fixed_band_ledger'].query("game_id!='overlap'")
        native.loc[native.game_id.eq('overlap'),'result']=np.nan
        pool=s.build(latest,native)
        row=pool.set_index('game_id').loc['overlap']
        self.assertEqual(row.ats_status,'pending')
        self.assertEqual(row.fixed_band_ats_result,'')
        self.assertTrue(np.isnan(row.fixed_band_ats_units))
        self.assertEqual(s.summary(pool)['skips'],0)

    def test_weekly_totals_reconcile_and_pushes_count_in_stakes(self):
        latest,native=self.fixture()
        h=latest['fixed_band_ledger'].iloc[[0]].copy()
        h=pd.concat([h,h.assign(game_id='push',result=6.5),h.assign(game_id='loss',result=0.)],ignore_index=True)
        latest['fixed_band_ledger']=h
        pool=s.build(latest,native)
        total=s.summary(pool)
        # The backfilled skip is a stake: one win, two losses, one push.
        self.assertEqual((total['wins'],total['losses'],total['pushes'],total['skips']),(1,2,1,0))
        self.assertEqual(total['bets'],4)
        self.assertAlmostEqual(total['units'],1/1.1-2)
        self.assertAlmostEqual(total['roi'],(1/1.1-2)/4)
        for key in ['wins','losses','pushes','skips','bets','opportunities','units','pending','unavailable']:
            self.assertAlmostEqual(sum(s.summary(g)[key] for _,g in pool.groupby('week')),total[key])

    def test_roi_standard_error_counts_push_stakes_and_excludes_skips_and_pending(self):
        frame = pd.DataFrame(dict(fixed_band_ats_result=['W', 'L', 'P', 'S', ''],
                                  ats_status=['graded'] * 4 + ['pending']))
        result = s.summary(frame)
        realized_returns = np.array([1 / 1.1, -1., 0.])
        self.assertEqual((result['bets'], result['skips'], result['pending']), (3, 1, 1))
        self.assertAlmostEqual(result['roi'], realized_returns.mean())
        self.assertAlmostEqual(result['roi_se'], realized_returns.std(ddof=1)/np.sqrt(3))
        for grades in [[], ['W'], ['P']]:
            with self.subTest(grades=grades):
                self.assertTrue(np.isnan(s.summary(pd.DataFrame({'fixed_band_ats_result': grades}))['roi_se']))

    def test_duplicate_ledger_uses_first_snapshot_not_later_probability(self):
        latest,native=self.fixture();latest['ats_locks']={}
        # The later snapshot would take the away side and win.
        later=native.iloc[[0]].assign(generated_utc='2026-10-17T13:00:00Z',model_wp=.1)
        pool=s.build(latest,pd.concat([later,native],ignore_index=True)).set_index('game_id')
        self.assertEqual(pool.loc['overlap'].fixed_band_ats_result,'L')

    def test_shadow_revisions_do_not_enter_pool(self):
        latest,native=self.fixture()
        shadow=native.iloc[[0]].assign(revision='research-shadow',game_id='shadow')
        pool=s.build(latest,pd.concat([native,shadow],ignore_index=True))
        self.assertNotIn('shadow',set(pool.game_id))

    def test_duplicate_history_is_rejected(self):
        latest,native=self.fixture()
        latest['fixed_band_ledger']=pd.concat([latest['fixed_band_ledger']]*2)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            s.build(latest,native)

    def test_newer_board_supplies_scores_without_replacing_saved_decision(self):
        latest,native=self.fixture()
        latest['board']=pd.DataFrame([dict(game_id='overlap',result=12.,model_wp=.1,spread_line=20.)])
        pool=s.build(latest,native).set_index('game_id')
        self.assertEqual(pool.loc['overlap'].result,12.)
        self.assertEqual(pool.loc['overlap'].spread_line,7.)
        # Graded at the saved 7 with the newer final score: IND by 12 covers.
        self.assertEqual(pool.loc['overlap'].fixed_band_ats_result,'W')

    def test_display_uses_pooled_count_and_labels_both_sources(self):
        latest,native=self.fixture();latest['pooled_ats']=s.build(latest,native)
        html=b.spread_headline(latest,2026)
        self.assertIn('ATS 1–1–0 · 0 skips',html)
        self.assertIn('1 replayed · 1 backfilled · 0 recorded',html)
        self.assertIn('1 unavailable',html)

    def test_current_data_reconciles_and_backfills_recorded_skips(self):
        data=Path(__file__).resolve().parents[1]/'data'
        latest=b.load_latest(data/'latest');latest['ats_locks']=ats_locks.display_records(data)
        pool=s.build(latest,b.load_ledger(data));r=s.summary(pool)
        self.assertEqual(pool.game_id.nunique(),len(pool))
        self.assertEqual(pool.set_index('game_id').loc['2026_06_TEN_IND'].fixed_band_ats_result,'L')
        # Pin this snapshot only while it still has the same completed cohort.
        if r['opportunities']==92:
            # All skips are favorite bets; the two recorded skips are backfilled (0-2).
            self.assertEqual((r['wins'],r['losses'],r['pushes'],r['skips']),(49,37,6,0))
            self.assertAlmostEqual(r['units'],49/1.1-37)
            self.assertEqual(r['bets'],92)
            backfill=pool[pool.ats_basis.eq('Backfilled recorded skip')]
            self.assertEqual(sorted(backfill.game_id),['2026_06_BAL_CLE','2026_06_TEN_IND'])
            self.assertEqual(backfill.fixed_band_ats_result.tolist(),['L','L'])
        saved=copy.deepcopy(latest['ats_locks'])
        s.build(latest,b.load_ledger(data))
        self.assertEqual(saved,latest['ats_locks'])

    def test_recovered_candidate_grades_once_and_keeps_backend_source(self):
        latest, native = self.fixture()
        saved = latest['ats_locks'][(m.REVISION, 'overlap')]
        saved.update(selected_side='away', fixed_band_spread=7., market_spread=7.5,
                     recovered_after_kickoff=True, finalized_utc='2026-10-20T04:00:00+00:00')
        pool = s.build(latest, native)
        row = pool.set_index('game_id').loc['overlap']
        self.assertEqual((row.ats_basis, row.ats_status, row.fixed_band_ats_result),
                         ('Recovered saved forecast', 'graded', 'W'))
        self.assertEqual(row.fixed_band_ats_team, 'TEN')
        self.assertAlmostEqual(row.fixed_band_ats_units, 1/1.1)
        self.assertEqual(pool.game_id.nunique(), len(pool))
        self.assertIn('Recovered saved forecast: 1-0-0', s.report(pool))
        latest['pooled_ats'] = pool
        self.assertEqual(b.public_ats(latest).set_index('game_id').loc['overlap'].fixed_band_ats_result, 'W')


if __name__=='__main__':
    unittest.main()


class LockBaselines(unittest.TestCase):
    RULE = dict(season=2026, training_max_season=2025, cuts=[3., 7., 10.], magnitudes=[3., 4., 7., 14.])

    def lock(self, game, line, mapped, raw, rule=None):
        return dict(game_id=game, revision=m.REVISION, season=2026, week=8, home='IND', away='TEN',
                    model_wp=.6, market_spread=line, fixed_band_spread=mapped, raw_spread=raw,
                    fixed_rule=rule or self.RULE, selected_side='home', skip_reason=None,
                    policy_version=ats_locks.POLICY_VERSION, generated_utc='2026-10-25T15:50:00Z',
                    kickoff_utc='2026-10-25T17:00:00Z', lock_at_utc='2026-10-25T16:00:00Z',
                    finalized_utc='2026-10-25T16:00:20Z')

    def latest(self, locks):
        return dict(manifest={'season': 2026, 'revision': m.REVISION}, fixed_band_rules=[self.RULE],
                    ats_locks={(m.REVISION, r['game_id']): r for r in locks}, board=pd.DataFrame())

    def pool(self, rows):
        return pd.DataFrame(rows, columns=['game_id', 'season', 'spread_line', 'fixed_band_spread',
                                           'result', 'ats_basis'])

    def test_line_only_map_differs_only_where_the_model_crosses_a_band(self):
        # Line 5.5 alone maps to 4 (take the dog). A model at 8 maps to 7 (take the
        # favorite): the model changed the side. At 4.5 both maps give 4 and agree.
        sides = s.baseline_sides([7., 4.], [5.5, 5.5], [8., 4.5], [4., 4.])
        self.assertEqual(list(sides['Median map (production)']), [1., -1.])
        self.assertEqual(list(sides['Line-only map']), [-1., -1.])
        self.assertEqual(list(sides['Raw model spread']), [1., -1.])
        self.assertEqual(list(sides['Always favorite']), [1., 1.])
        self.assertEqual(list(sides['Always home']), [1., 1.])

    def test_pickem_line_skips_line_only_and_favorite_but_not_home(self):
        sides = s.baseline_sides([3.], [0.], [1.], [0.])
        self.assertEqual(sides['Line-only map'][0], 0.)
        self.assertEqual(sides['Always favorite'][0], 0.)
        self.assertEqual(sides['Always home'][0], 1.)
        record = s.flat_record(sides['Line-only map'], [4.])
        self.assertEqual((record['bets'], record['skips']), (0, 1))

    def test_flat_record_counts_pushes_in_the_roi_denominator(self):
        record = s.flat_record([1., 1., -1., 1.], [3., 0., 2., np.nan])
        self.assertEqual((record['wins'], record['losses'], record['pushes'], record['bets']), (1, 1, 1, 3))
        self.assertAlmostEqual(record['units'], 1 / 1.1 - 1)
        self.assertAlmostEqual(record['roi'], (1 / 1.1 - 1) / 3)
        self.assertEqual(record['cover_rate'], .5)

    def test_report_grades_only_timed_locks_with_their_saved_rule(self):
        # The saved rule maps a 5.5 line to 6, so the line-only map takes the favorite;
        # the current rule would map it to 4 and take the dog.
        saved_rule = dict(self.RULE, magnitudes=[3., 6., 7., 14.])
        locks = [self.lock('a', 5.5, 7., 8., saved_rule), self.lock('pend', 3., 3., 2.)]
        pool = self.pool([
            ('a', 2026, 5.5, 7., 10., '60-minute lock'),
            ('pend', 2026, 3., 3., np.nan, '60-minute lock'),
            ('hist', 2026, 5.5, 4., -10., 'Historical replay'),
            ('back', 2026, 7., 7., -10., 'Backfilled recorded skip')])
        text = s.lock_baselines(self.latest(locks), pool)
        block = text.split('Recovered saved forecast')[0]
        self.assertIn('60-minute lock, ' + m.REVISION + ': 1 graded, 1 pending', block)
        self.assertIn('Median map (production)  1-0-0', block)
        self.assertIn('Line-only map            1-0-0', block)
        self.assertIn('sides differ on 0 of 1', block)
        self.assertIn('Recovered saved forecast, ' + m.REVISION + ': 0 graded, 0 pending', text)

    def test_report_paired_difference_when_the_model_changes_the_side(self):
        locks = [self.lock('a', 5.5, 7., 8.)]
        pool = self.pool([('a', 2026, 5.5, 7., 10., '60-minute lock')])
        text = s.lock_baselines(self.latest(locks), pool)
        self.assertIn('Line-only map            0-1-0', text)
        self.assertIn('median map minus line-only map: sides differ on 1 of 1; +1.91u', text)
        self.assertIn('median map minus raw model spread: sides differ on 0 of 1; +0.00u', text)

    def test_development_history_uses_each_seasons_prior_rule(self):
        latest = self.latest([])
        latest['fixed_band_rules'] = [self.RULE, dict(self.RULE, season=2025, magnitudes=[3., 6., 7., 14.])]
        latest['fixed_band_ledger'] = pd.DataFrame([
            dict(game_id='x', season=2025, spread_line=5.5, fixed_band_spread=6., model_spread=5., result=10.),
            dict(game_id='y', season=2026, spread_line=5.5, fixed_band_spread=4., model_spread=5., result=10.)])
        text = s.lock_baselines(latest, self.pool([]))
        history = text.split('Development history')[1]
        # 2025's rule maps the line to 6 (favorite, win); 2026's maps it to 4 (dog, loss).
        self.assertIn('2025-2026, 2 graded', history)
        self.assertIn('Line-only map            1-1-0', history)
        self.assertIn('sides differ on 0 of 2', history)

    def test_published_report_includes_the_baselines_section(self):
        text = b.published_report(Path(__file__).resolve().parents[1] / 'data')
        self.assertIn('ATS same-row baselines', text)
        self.assertIn('Median map minus line-only is what the model adds', text)
