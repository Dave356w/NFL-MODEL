"""The T−60 data cutoff, immutable decisions and displayed skips."""
import csv
import datetime as dt
import json
from pathlib import Path
from statistics import NormalDist
import tempfile
import unittest

import pandas as pd

import ats_locks as a
import build_site as b
import nfl_model as m
import schedule_gate as sg
import validate_data_files as validation

UTC = dt.timezone.utc
KO = dt.datetime(2026, 10, 25, 17, tzinfo=UTC)
CUTOFF = KO - dt.timedelta(hours=1)


class TimedATS(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        (self.data / 'latest').mkdir()
        self.rule = dict(season=2026, training_max_season=2025, training_games=1359,
                         cuts=[3., 7., 10.], magnitudes=[3., 4., 7., 14.],
                         method='median_signed_mov', policy_version='median-mov-ats-2026-10-17-v1')
        (self.data / 'latest/fixed_band_rules.json').write_text(json.dumps([self.rule]))
        self.raw = dict(game_id='2026_07_TEN_IND', season=2026, week=7, home='IND', away='TEN',
                        gameday='2026-10-25', gametime='13:00', result='', ready=True,
                        model_wp=NormalDist().cdf(8 / 12.37), spread_line=7.,
                        home_injury_report='final', away_injury_report='final')

    def board(self, now, **changes):
        manifest = dict(revision=m.REVISION, season=2026, week=7, generated_utc=now.isoformat(),
                        config_signature='test', recipe={'family': 'rates_core_avail_cs'})
        (self.data / 'latest/manifest.json').write_text(json.dumps(manifest))
        row = dict(self.raw, **changes)
        with (self.data / 'latest/board.csv').open('w', newline='') as f:
            out = csv.DictWriter(f, fieldnames=list(row))
            out.writeheader()
            out.writerow(row)

    def locks(self):
        return a.read(self.data / a.LOCKS)

    def test_provisional_refreshes_then_freezes_latest_at_exact_cutoff(self):
        first = CUTOFF - dt.timedelta(minutes=20)
        self.board(first)
        self.assertEqual(a.record(self.data, first), {'candidates': 1, 'locks': 0})
        self.board(CUTOFF, spread_line=6.5)
        self.assertEqual(a.record(self.data, CUTOFF), {'candidates': 1, 'locks': 1})
        saved = self.locks()[0]
        self.assertEqual(saved['market_spread'], 6.5)
        self.assertEqual(saved['selected_side'], 'home')
        self.assertEqual(saved['lock_at_utc'], CUTOFF.isoformat())
        self.assertEqual(saved['generated_utc'], CUTOFF.isoformat())

    def test_one_second_before_cutoff_does_not_lock(self):
        now = CUTOFF - dt.timedelta(seconds=1)
        self.board(now)
        a.record(self.data, now)
        self.assertEqual(self.locks(), [])

    def test_future_candidate_freezes_received_espn_side_prices_with_its_hash(self):
        import espn_spreads as e
        stamp = (CUTOFF-dt.timedelta(minutes=1)).isoformat()
        offer = lambda handicap, price: dict(pointSpread={'american': str(handicap)},
                                              spread={'american': str(price)})
        evidence = dict(game_id=self.raw['game_id'], season=2026, week=7, home='IND', away='TEN',
            event_id='test', completed=False, captured_utc=stamp, kickoff_utc=KO.isoformat(),
            odds_url='https://example.test/odds', movements=[], odds_pages=[{'items': [dict(
                provider={'id':'100','name':'Draft Kings'},
                homeTeamOdds={'current':offer(-7, -118)}, awayTeamOdds={'current':offer(7, -102)})]}])
        evidence['evidence_sha256'] = a.digest(evidence)
        a.append(self.data/e.STORE, [evidence])
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        saved = self.locks()[0]
        self.assertEqual(saved['espn_quote']['home_odds'], -118.)
        self.assertEqual(saved['espn_quote']['away_odds'], -102.)
        self.assertEqual(saved['espn_quote_status'], 'captured_prelock')
        before = (self.data/a.LOCKS).read_bytes()
        a.record(self.data, CUTOFF+dt.timedelta(minutes=1))
        self.assertEqual((self.data/a.LOCKS).read_bytes(), before)
        # Rehashing a candidate cannot authorize a quote received after lock.
        candidate = a.read(self.data/a.CANDIDATES)[0]
        candidate['espn_quote']['captured_utc'] = (CUTOFF+dt.timedelta(seconds=1)).isoformat()
        candidate['candidate_sha256'] = a.digest({k:v for k,v in candidate.items() if k!='candidate_sha256'})
        (self.data/a.CANDIDATES).write_text(json.dumps(candidate)+'\n')
        with self.assertRaisesRegex(ValueError, 'exact pre-lock quote'):
            a.validate_store(self.data)

    def test_band_boundaries_use_the_identical_production_conversion(self):
        import fixed_bands
        from scipy.special import ndtr
        for raw in (0., 3., -3., 7., -7., 10., -10.):
            with self.subTest(raw=raw):
                for name in (a.CANDIDATES, a.LOCKS):
                    (self.data/name).unlink(missing_ok=True)
                wp = float(ndtr(raw/12.37))
                self.board(CUTOFF, model_wp=wp)
                a.record(self.data, CUTOFF)
                expected = fixed_bands.apply(m.implied_spread([wp]), self.rule)[0]
                self.assertEqual(self.locks()[0]['fixed_band_spread'], expected)

    def test_legacy_early_capture_stops_at_timed_policy_adoption(self):
        from research import ats_forward_shadow as old
        row = dict(revision=m.REVISION, game_id=self.raw['game_id'], model_wp=.7,
                   spread_line=7., generated_utc=CUTOFF.isoformat(), kickoff_utc=KO.isoformat())
        (self.data/'forward_predictions.jsonl').write_text(json.dumps(row)+'\n')
        self.assertEqual(old.possible_locks(self.data, CUTOFF), [])

    def test_delayed_run_cannot_use_post_cutoff_inputs(self):
        previous = CUTOFF - dt.timedelta(minutes=2)
        self.board(previous)
        a.record(self.data, previous)
        self.board(CUTOFF + dt.timedelta(seconds=1), model_wp=.9, spread_line=6.5)
        a.record(self.data, CUTOFF + dt.timedelta(minutes=4))
        saved = self.locks()[0]
        self.assertEqual(saved['generated_utc'], previous.isoformat())
        # The saved zero edge (7 against 7) takes the market favorite.
        self.assertEqual(saved['selected_side'], 'home')
        self.assertIsNone(saved['skip_reason'])
        self.assertEqual(saved['policy_version'], a.POLICY_VERSION)
        self.assertEqual(len(a.read(self.data / a.CANDIDATES)), 1)

    def test_old_generated_timestamp_first_observed_after_cutoff_is_rejected(self):
        self.board(CUTOFF - dt.timedelta(minutes=1))
        self.assertEqual(a.record(self.data, CUTOFF + dt.timedelta(seconds=1)),
                         {'candidates': 0, 'locks': 0})

    def test_post_lock_changes_and_reruns_leave_both_files_byte_identical(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        paths = [self.data / a.CANDIDATES, self.data / a.LOCKS]
        before = [p.read_bytes() for p in paths]
        self.board(CUTOFF + dt.timedelta(minutes=5), model_wp=.9, spread_line=6.5)
        a.record(self.data, CUTOFF + dt.timedelta(minutes=5))
        a.record(self.data, CUTOFF + dt.timedelta(minutes=6))
        self.assertEqual(before, [p.read_bytes() for p in paths])

    def test_recovery_uses_latest_saved_candidate_and_preserves_original_bytes(self):
        first = CUTOFF - dt.timedelta(minutes=20)
        latest = CUTOFF - dt.timedelta(minutes=2)
        self.board(first)
        a.record(self.data, first)
        self.board(latest, spread_line=7.5)
        a.record(self.data, latest)
        before = (self.data / a.CANDIDATES).read_bytes()
        # Completed-board data must not replace the saved line or selection.
        self.board(KO + dt.timedelta(hours=4), model_wp=.9, spread_line=3., result=6)
        now = KO + dt.timedelta(hours=12)
        self.assertEqual(a.record(self.data, now), {'candidates': 0, 'locks': 1})
        saved = self.locks()[0]
        self.assertEqual((saved['generated_utc'], saved['market_spread'], saved['selected_side']),
                         (latest.isoformat(), 7.5, 'away'))
        self.assertEqual(saved['finalized_utc'], now.isoformat())
        self.assertTrue(saved['recovered_after_kickoff'])
        self.assertEqual(saved['finalization_policy_version'], a.RECOVERY_POLICY)
        self.assertEqual((self.data / a.CANDIDATES).read_bytes(), before)
        locked = (self.data / a.LOCKS).read_bytes()
        a.record(self.data, now + dt.timedelta(minutes=5))
        self.assertEqual((self.data / a.LOCKS).read_bytes(), locked)
        self.assertIn('recovered saved forecast', a.report(self.data))

    def test_recovery_window_includes_kickoff_and_48_hours_but_not_later(self):
        for hours, seconds, allowed in [(0, 0, True), (48, 0, True), (48, 1, False)]:
            with self.subTest(hours=hours, seconds=seconds):
                for name in (a.CANDIDATES, a.LOCKS):
                    (self.data / name).unlink(missing_ok=True)
                self.board(CUTOFF - dt.timedelta(minutes=2))
                a.record(self.data, CUTOFF - dt.timedelta(minutes=2))
                a.record(self.data, KO + dt.timedelta(hours=hours, seconds=seconds))
                self.assertEqual(len(self.locks()), int(allowed))

    def test_recovered_lock_requires_truthful_metadata_and_actual_finalization_time(self):
        self.board(CUTOFF - dt.timedelta(minutes=2))
        a.record(self.data, CUTOFF - dt.timedelta(minutes=2))
        a.record(self.data, KO + dt.timedelta(hours=4))
        saved = self.locks()[0]
        for changes in ({'recovered_after_kickoff': False}, {'finalization_policy_version': None},
                        {'finalized_utc': (KO+dt.timedelta(hours=49)).isoformat()}):
            with self.subTest(changes=changes):
                (self.data / a.LOCKS).write_text(json.dumps(dict(saved, **changes))+'\n')
                with self.assertRaisesRegex(ValueError, 'allowed window'):
                    a.validate_store(self.data)

    def test_recovery_cannot_create_a_candidate_after_cutoff(self):
        self.board(CUTOFF - dt.timedelta(minutes=2))
        self.assertEqual(a.record(self.data, KO + dt.timedelta(hours=4)),
                         {'candidates': 0, 'locks': 0})

    def test_missing_line_or_unreported_or_completed_games_do_not_capture(self):
        for changes in ({'spread_line': ''}, {'model_wp': ''}, {'ready': False},
                        {'home_injury_report': 'none'}, {'result': 6}):
            with self.subTest(changes=changes):
                self.board(CUTOFF, **changes)
                self.assertEqual(a.record(self.data, CUTOFF), {'candidates': 0, 'locks': 0})

    def test_future_generated_forecast_is_not_eligible(self):
        self.board(CUTOFF)
        self.assertEqual(a.record(self.data, CUTOFF - dt.timedelta(seconds=1)),
                         {'candidates': 0, 'locks': 0})

    def test_early_moneyline_is_not_used_as_a_timed_forecast(self):
        p = self.data / 'forward_predictions.jsonl'
        p.write_text(json.dumps(dict(self.raw, revision=m.REVISION,
                                    generated_utc=(CUTOFF-dt.timedelta(days=1)).isoformat(),
                                    kickoff_utc=KO.isoformat()))+'\n')
        original = p.read_bytes()
        self.board(CUTOFF + dt.timedelta(seconds=1))
        self.assertEqual(a.record(self.data, CUTOFF + dt.timedelta(seconds=1))['locks'], 0)
        self.assertEqual(p.read_bytes(), original)

    def test_hash_tampering_is_rejected_by_data_validator(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        path = self.data / a.CANDIDATES
        row = a.read(path)[0]
        row['market_spread'] = 6.5
        path.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            validation.validate_data_dir(self.data)

    def test_lock_tampering_is_rejected(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        path = self.data / a.LOCKS
        row = a.read(path)[0]
        row['selected_side'] = 'away'
        path.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            a.validate_store(self.data)

    def test_moved_kickoff_does_not_freeze_the_old_deadline(self):
        self.board(CUTOFF - dt.timedelta(minutes=5))
        a.record(self.data, CUTOFF - dt.timedelta(minutes=5))
        self.board(CUTOFF, gametime='14:00')
        a.record(self.data, CUTOFF)
        self.assertEqual(self.locks(), [])
        a.record(self.data, CUTOFF + dt.timedelta(hours=1))
        self.assertEqual(self.locks()[0]['kickoff_utc'], (KO+dt.timedelta(hours=1)).isoformat())

    def latest(self):
        row = dict(self.raw, result=6., home_score=20, away_score=26, model_wp=.6,
                   spread_line=6.5, fixed_band_spread=4., home_moneyline=-298.,
                   away_moneyline=240., market_wp=.7, homefield_wp=.54)
        return dict(manifest=dict(revision=m.REVISION, season=2026, week=7,
                                  generated_utc=CUTOFF.isoformat(), recipe={}),
                    board=pd.DataFrame([row]), contributions=pd.DataFrame(),
                    ats_locks=a.display_records(self.data))

    def test_saved_zero_edge_favorite_stays_on_a_refreshed_winning_card(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        html = b.render_index(self.latest(), pd.DataFrame(), 'test', KO+dt.timedelta(hours=4))
        self.assertIn('IND −7.0', html)
        self.assertIn('ATS locked', html)
        # Graded at the saved 7, not the refreshed 6.5 line that would make TEN a winner.
        self.assertIn('ATS result · L', html)
        self.assertNotIn('TEN +6.5 ·', html)

    def test_saved_v1_skip_validates_unchanged_and_displays_as_backfilled_favorite(self):
        v1 = 'median-mov-ats-t60-2026-10-19-v1'
        current = a.POLICY_VERSION
        self.board(CUTOFF)
        a.POLICY_VERSION = v1
        try:
            a.record(self.data, CUTOFF)
        finally:
            a.POLICY_VERSION = current
        saved = self.locks()[0]
        self.assertEqual((saved['policy_version'], saved['selected_side'], saved['skip_reason']),
                         (v1, '', 'zero_edge'))
        before = (self.data / a.LOCKS).read_bytes()
        self.assertEqual(a.validate_store(self.data), {'candidates': 1, 'locks': 1})
        self.assertTrue(a.backfilled(saved))
        html = b.render_index(self.latest(), pd.DataFrame(), 'test', KO+dt.timedelta(hours=4))
        self.assertIn('IND −7.0', html)
        self.assertNotIn('skip backfilled as favorite', html)
        latest = self.latest()
        state = b.ats_card_state(latest, latest['board'].iloc[0].to_dict(), KO+dt.timedelta(hours=4))
        self.assertEqual(state['source'], 'Backfilled recorded skip')
        self.assertIn('ATS result · L', html)
        self.assertEqual((self.data / a.LOCKS).read_bytes(), before)

    def test_v2_candidate_saved_as_a_skip_is_rejected(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        path = self.data / a.CANDIDATES
        row = a.read(path)[0]
        row.update(selected_side='', skip_reason='zero_edge')
        row.pop('candidate_sha256')
        row['candidate_sha256'] = a.digest(row)
        path.write_text(json.dumps(row)+'\n')
        (self.data / a.LOCKS).unlink()
        with self.assertRaisesRegex(ValueError, 'does not match'):
            a.validate_store(self.data)

    def test_pickem_line_with_zero_mapped_spread_still_skips(self):
        self.board(CUTOFF, model_wp=.5, spread_line=0.)
        a.record(self.data, CUTOFF)
        saved = self.locks()[0]
        self.assertEqual((saved['fixed_band_spread'], saved['selected_side'], saved['skip_reason']),
                         (0., '', 'zero_edge'))

    def test_unknown_policy_version_is_rejected(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        path = self.data / a.CANDIDATES
        row = a.read(path)[0]
        row['policy_version'] = 'unregistered'
        row.pop('candidate_sha256')
        row['candidate_sha256'] = a.digest(row)
        path.write_text(json.dumps(row)+'\n')
        (self.data / a.LOCKS).unlink()
        with self.assertRaisesRegex(ValueError, 'timing policy mismatch'):
            a.validate_store(self.data)

    def test_no_lock_means_unavailable_after_cutoff_not_a_reconstructed_pick(self):
        html = b.render_index(self.latest(), pd.DataFrame(), 'test', KO)
        self.assertIn('Unavailable · no saved pre-lock forecast', html)
        self.assertNotIn('TEN +6.5 ·', html)

    def test_provisional_card_shows_60_minute_deadline(self):
        latest = self.latest()
        latest['board']['result'] = float('nan')
        html = b.render_index(latest, pd.DataFrame(), 'test', CUTOFF-dt.timedelta(minutes=5))
        self.assertIn('ATS provisional · locks Sun 9:00 AM PDT', html)

    def test_legacy_archive_is_displayed_without_rewriting_or_reusing_it_for_future_locks(self):
        legacy = dict(revision=m.REVISION, game_id='2026_06_TEN_IND', season=2026,
                      kickoff_utc='2026-10-18T17:00:00+00:00', archived_utc='2026-10-17T12:00:00+00:00',
                      generated_utc='2026-10-17T11:30:00+00:00', raw_spread=8.,
                      fixed_band_spread=7., market_spread=7., selected_side='', skip_reason='zero_edge')
        future = dict(legacy, game_id=self.raw['game_id'], kickoff_utc=KO.isoformat())
        path = self.data / 'ats_forward_shadow.jsonl'
        path.write_text(''.join(json.dumps(r)+'\n' for r in (legacy,future)))
        before = path.read_bytes()
        rows = a.display_records(self.data)
        self.assertEqual(set(rows), {(m.REVISION,legacy['game_id'])})
        self.assertEqual(path.read_bytes(), before)

    def test_fast_poll_is_limited_to_ats_window_even_without_moneyline_locks(self):
        game = dict(game_id='g', gameday='2026-10-25', gametime='13:00', game_type='REG', result='')
        for minutes, due in [(121,False),(120,True),(91,True),(61,True),(60,True),
                             (50,True),(49,True),(15,True),(14,False),(300,False)]:
            with self.subTest(minutes=minutes):
                now = KO-dt.timedelta(minutes=minutes)
                result = sg.decision('schedule', sg.ATS_CRON, now, games=[game], recorded=set())
                self.assertEqual(result[0], due)
        workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/build.yml').read_text()
        self.assertIn(f"cron: '{sg.ATS_CRON}'",workflow)
        self.assertIn('cancel-in-progress: false',workflow)


if __name__ == '__main__':
    unittest.main()
