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
        self.assertEqual(saved['selected_side'], '')
        self.assertEqual(saved['skip_reason'], 'zero_edge')
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

    def test_no_finalization_at_or_after_kickoff(self):
        self.board(CUTOFF - dt.timedelta(minutes=2))
        a.record(self.data, CUTOFF - dt.timedelta(minutes=2))
        a.record(self.data, KO)
        a.record(self.data, KO + dt.timedelta(minutes=5))
        self.assertEqual(self.locks(), [])

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

    def test_saved_skip_stays_a_skip_on_a_refreshed_winning_card(self):
        self.board(CUTOFF)
        a.record(self.data, CUTOFF)
        html = b.render_index(self.latest(), pd.DataFrame(), 'test', KO+dt.timedelta(hours=4))
        self.assertIn('No bet · zero projected edge', html)
        self.assertIn('Market IND −7.0', html)
        self.assertIn('ATS locked', html)
        self.assertNotIn('TEN +6.5 ·', html)

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
        for minutes, due in [(91,False),(90,True),(61,True),(60,True),(50,True),(49,False),(300,False)]:
            with self.subTest(minutes=minutes):
                now = KO-dt.timedelta(minutes=minutes)
                result = sg.decision('schedule', sg.ATS_CRON, now, games=[game], recorded=set())
                self.assertEqual(result[0], due)
        workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/build.yml').read_text()
        self.assertIn(f"cron: '{sg.ATS_CRON}'",workflow)
        self.assertIn('cancel-in-progress: false',workflow)


if __name__ == '__main__':
    unittest.main()
