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
            dict(game_id='h', season=2026, week=5, home='IND', away='TEN',
                 fixed_band_spread=7., spread_line=6.5, result=7.),
            dict(game_id='overlap', season=2026, week=6, home='IND', away='TEN',
                 fixed_band_spread=4., spread_line=6.5, result=-6.),
            dict(game_id='pending', season=2026, week=7, home='IND', away='TEN',
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

    def test_archived_skip_replaces_a_reconstructed_win_and_never_duplicates(self):
        latest,native = self.fixture()
        pool = s.build(latest,native)
        self.assertEqual(pool.game_id.nunique(),len(pool))
        row=pool.set_index('game_id').loc['overlap']
        self.assertEqual(row.fixed_band_ats_result,'S')
        self.assertEqual(row.fixed_band_ats_units,0.)
        self.assertEqual(row.ats_basis,'Recorded pregame')
        self.assertEqual(row.spread_line,7.)

    def test_missing_post_adoption_lock_blocks_historical_and_native_reconstruction(self):
        latest,native=self.fixture()
        pool=s.build(latest,native).set_index('game_id')
        row=pool.loc['pending']
        # A known final score does not authorize a retrospective ATS lock.
        self.assertEqual(row.ats_status,'unavailable')
        self.assertEqual(row.fixed_band_ats_result,'')
        self.assertTrue(np.isnan(row.fixed_band_spread))

    def test_pre_adoption_unregistered_snapshot_is_explicit_replay(self):
        latest,native=self.fixture()
        latest['ats_locks']={}
        pool=s.build(latest,native).set_index('game_id')
        row=pool.loc['overlap']
        self.assertEqual(row.fixed_band_ats_result,'S')
        self.assertEqual(row.ats_basis,'Replayed pregame forecast')

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
        self.assertEqual((total['wins'],total['losses'],total['pushes'],total['skips']),(1,1,1,1))
        self.assertEqual(total['bets'],3)
        self.assertAlmostEqual(total['units'],1/1.1-1)
        self.assertAlmostEqual(total['roi'],(1/1.1-1)/3)
        for key in ['wins','losses','pushes','skips','bets','opportunities','units','pending','unavailable']:
            self.assertAlmostEqual(sum(s.summary(g)[key] for _,g in pool.groupby('week')),total[key])

    def test_duplicate_ledger_uses_first_snapshot_not_later_probability(self):
        latest,native=self.fixture();latest['ats_locks']={}
        later=native.iloc[[0]].assign(generated_utc='2026-10-17T13:00:00Z',model_wp=.9)
        pool=s.build(latest,pd.concat([later,native],ignore_index=True)).set_index('game_id')
        self.assertEqual(pool.loc['overlap'].fixed_band_ats_result,'S')

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
        self.assertEqual(pool.loc['overlap'].fixed_band_ats_result,'S')

    def test_display_uses_pooled_count_and_labels_both_sources(self):
        latest,native=self.fixture();latest['pooled_ats']=s.build(latest,native)
        html=b.spread_headline(latest,2026)
        self.assertIn('ATS 1–0–0 · 1 skips',html)
        self.assertIn('1 replayed · 1 recorded',html)
        self.assertIn('1 unavailable',html)

    def test_current_data_reconciles_and_preserves_ten_skip(self):
        data=Path(__file__).resolve().parents[1]/'data'
        latest=b.load_latest(data/'latest');latest['ats_locks']=ats_locks.display_records(data)
        pool=s.build(latest,b.load_ledger(data));r=s.summary(pool)
        self.assertEqual(pool.game_id.nunique(),len(pool))
        self.assertEqual(pool.set_index('game_id').loc['2026_06_TEN_IND'].fixed_band_ats_result,'S')
        # Pin this snapshot only while it still has the same completed cohort.
        if r['opportunities']==92:
            self.assertEqual((r['wins'],r['losses'],r['pushes'],r['skips']),(43,31,2,16))
            self.assertAlmostEqual(r['units'],8.090909090909093)
            self.assertEqual(r['bets'],76)
        saved=copy.deepcopy(latest['ats_locks'])
        s.build(latest,b.load_ledger(data))
        self.assertEqual(saved,latest['ats_locks'])


if __name__=='__main__':
    unittest.main()
