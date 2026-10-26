"""Public ATS-only presentation with unchanged internal probabilities/archives."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import pandas as pd

import build_site as b


class ATSOnlySite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        cls.data = root/'data'
        source = Path(__file__).resolve().parents[1]/'data'
        shutil.copytree(source, cls.data)
        # Keep the display fixture on a known archived skip even when the
        # production board advances to a later week.
        card = dict(game_id='2026_06_TEN_IND', season=2026, week=6, home='IND', away='TEN',
                    gameday='2026-10-18', gametime='13:00', ready=True, result=-6.,
                    home_score=20., away_score=26., model_wp=.6, spread_line=6.5,
                    home_injury_report='final', away_injury_report='final')
        # This game has a completed season selection but no saved ATS lock.
        # Deliberately change the postgame board to a conflicting home pick.
        historical = dict(card, game_id='2026_06_SEA_DEN', home='DEN', away='SEA',
                          gameday='2026-10-15', gametime='20:15', result=float('nan'),
                          home_score=float('nan'), away_score=float('nan'), model_wp=.99, spread_line=9.5)
        pd.DataFrame([card, historical]).to_csv(cls.data/'latest/board.csv',index=False)
        manifest=json.loads((cls.data/'latest/manifest.json').read_text())
        manifest.update(season=2026,week=6,revision='boxscore-composite-v1.18',
                        generated_utc='2026-10-19T05:40:00+00:00')
        (cls.data/'latest/manifest.json').write_text(json.dumps(manifest))
        cls.out = root/'public'
        cls.before = {name:hashlib.sha256((cls.data/name).read_bytes()).hexdigest()
                      for name in ('forward_predictions.jsonl','ats_forward_shadow.jsonl','ats_lock_candidates.jsonl')}
        b.render_all(cls.out, cls.data, now=dt.datetime(2026,10,19,5,40,tzinfo=dt.timezone.utc))
        cls.pool=pd.read_csv(cls.out/'ats_2026_results.csv',keep_default_na=False)

    @staticmethod
    def visible(text):
        text=re.sub(r'<style>.*?</style>|<script>.*?</script>','',text,flags=re.S)
        return re.sub(r'<[^>]+>',' ',text)

    def test_all_pages_are_ats_only(self):
        for page in ('index.html','grades.html','market-calibration.html'):
            with self.subTest(page=page):
                raw=(self.out/page).read_text();text=self.visible(raw)
                self.assertIn('NFL ATS',text)
                self.assertIn('Picks',text)
                grades=self.pool.fixed_band_ats_result
                record='–'.join(str(int(grades.eq(k).sum())) for k in 'WLP')
                self.assertIn(record,text)
                for banned in ('moneyline','win probability','win probabilities','model confidence','no-vig'):
                    self.assertNotIn(banned,text.lower())
                self.assertNotRegex(text,r'\bnan\b|\bNaN\b|\bNone\b')
                self.assertNotIn("class='probbar'",raw)

    def test_cards_backfill_saved_skips_at_the_saved_line_not_a_refreshed_winner(self):
        html=(self.out/'index.html').read_text()
        card=next(c for c in html.split("<details class='card")[1:] if 'Titans' in c.split('</summary>')[0])
        summary=card.split('</summary>')[0]
        self.assertIn('IND −7.0',summary)
        self.assertNotIn('backfilled',summary)
        self.assertIn('ATS result · L',summary)
        self.assertNotIn('TEN +6.5',summary)

    def test_public_exports_exclude_moneyline_and_probability_fields(self):
        for path in self.out.glob('*.csv'):
            with self.subTest(file=path.name):
                frame=pd.read_csv(path)
                for column in frame.columns:
                    self.assertNotIn('moneyline',column)
                    self.assertNotIn('model_wp',column)
                    self.assertFalse(column.startswith(('bet_','original_ats_')))

    def test_board_download_matches_frozen_card(self):
        frame=pd.read_csv(self.out/'fixed_band_board.csv',keep_default_na=False).set_index('game_id')
        row=frame.loc['2026_06_TEN_IND']
        self.assertEqual(row.ats_status,'locked')
        self.assertEqual(row.model_spread,7.)
        self.assertEqual(row.spread_line,7.)
        self.assertEqual(row.selected_team,'IND')
        self.assertEqual(row.ats_result,'L')
        expected=self.pool.set_index('game_id').loc['2026_06_TEN_IND']
        self.assertEqual(str(row.ats_units),str(expected.fixed_band_ats_units))
        saved=pd.read_csv(self.out/'ats_locked_picks.csv',keep_default_na=False).set_index('game_id')
        # Public downloads use the effective displayed favorite; originals and
        # source/backfill flags remain in the unchanged backend archive.
        self.assertEqual(saved.loc['2026_06_TEN_IND'].selected_side,'home')
        self.assertEqual(saved.loc['2026_06_TEN_IND'].selected_team,'IND')
        self.assertEqual(float(saved.loc['2026_06_TEN_IND'].handicap),-7.)
        for field in ('timing_policy','skip_reason','backfilled_favorite','legacy_lock','ats_basis'):
            self.assertNotIn(field,saved.columns)

    def test_completed_card_and_board_download_use_the_season_selection(self):
        expected=self.pool.set_index('game_id').loc['2026_06_SEA_DEN']
        board=pd.read_csv(self.out/'fixed_band_board.csv',keep_default_na=False).set_index('game_id')
        shown=board.loc['2026_06_SEA_DEN']
        self.assertEqual(shown.ats_status,'graded')
        self.assertEqual(float(shown.model_spread),float(expected.model_spread))
        self.assertEqual(float(shown.spread_line),float(expected.spread_line))
        self.assertEqual(shown.selected_team,expected.fixed_band_ats_team)
        self.assertEqual(shown.selected_side,expected.fixed_band_ats_side)
        self.assertEqual(shown.ats_result,expected.fixed_band_ats_result)
        self.assertEqual(str(shown.ats_units),str(expected.fixed_band_ats_units))
        self.assertEqual(float(shown.home_score),float(expected.home_score))
        self.assertEqual(float(shown.away_score),float(expected.away_score))
        self.assertEqual(float(shown.result),float(expected.result))
        self.assertNotEqual(shown.spread_line,9.5)
        html=(self.out/'index.html').read_text()
        card=next(c for c in html.split("<details class='card")[1:] if 'Seahawks' in c.split('</summary>')[0])
        summary=card.split('</summary>')[0]
        self.assertIn('SEA −2.5',summary)
        self.assertIn('ATS result · L',summary)
        self.assertIn('Final 14–17',summary)
        self.assertNotIn('Unavailable',card)
        self.assertNotIn('so it is not graded',card)
        self.assertNotIn('replay',self.visible(card).lower())

    def test_results_pool_each_game_once_and_keep_sources_internal(self):
        html=(self.out/'grades.html').read_text()
        self.assertIn('Game-by-game ATS results',html)
        self.assertIn('−110 reference 52.4%',html)
        self.assertRegex(self.visible(html),r'(Sun|Sat|Thu|Mon) \d{1,2}:\d{2} [AP]M PDT')  # Pacific kickoffs
        for page in ('index.html','grades.html','market-calibration.html'):
            text=self.visible((self.out/page).read_text())
            for source in ('Pick sources','Season replay','Pregame forecast replay','Historical replay',
                           'Earlier recorded picks','Recorded skips backfilled','backfilled','replayed','Source'):
                self.assertNotIn(source,text)
        report=(self.data/'ledger_report.txt').read_text()
        self.assertIn('Historical replay:',report)
        self.assertIn('Recorded pregame:',report)
        for game in self.pool.game_id:
            self.assertEqual(html.count(f"data-game-id='{game}'"),1)
        self.assertEqual(html.count("data-game-id='2026_06_TEN_IND'"),1)
        week=self.pool[self.pool.week.eq(6)].fixed_band_ats_result
        record='–'.join(str(int(week.eq(k).sum())) for k in 'WLP')
        self.assertIn(f'2026 week 6 · {record} · {int(week.eq("S").sum())} skips',html)

    def test_public_results_export_matches_the_full_season_pool(self):
        latest=b.load_latest(self.data/'latest')
        latest['ats_locks']=b.ats_locks.display_records(self.data)
        expected=b.season_ats.build(latest,b.load_ledger(self.data))
        self.assertEqual(set(self.pool.game_id),set(expected.game_id))
        self.assertNotIn('ats_basis',self.pool.columns)
        self.assertTrue({'Historical replay','Replayed pregame forecast','Recorded pregame'} <= set(expected.ats_basis))
        pd.testing.assert_series_equal(self.pool.set_index('game_id').fixed_band_ats_result,
            expected.set_index('game_id').fixed_band_ats_result,check_names=False)
        grades=self.pool.fixed_band_ats_result
        if len(grades[grades.isin(list('WLP'))])==92:
            self.assertEqual(tuple(int(grades.eq(k).sum()) for k in 'WLP'),(49,37,6))
        weekly=sum(b.season_ats.summary(g)['units'] for _,g in self.pool.groupby('week'))
        self.assertAlmostEqual(weekly,b.season_ats.summary(expected)['units'])
        self.assertFalse(self.pool.game_id.duplicated().any())
        for name in ('fixed_band_ledger.csv','fixed_band_summary.csv','fixed_band_rules.json'):
            self.assertFalse((self.out/name).exists())
            self.assertTrue((self.data/'latest'/name).exists())

    def test_performance_has_ats_controls_and_cover_rates(self):
        html=(self.out/'market-calibration.html').read_text()
        common=self.pool[self.pool.spread_line.ne(0) & self.pool.fixed_band_ats_result.isin(['W','L','P'])]
        wins=int(common.fixed_band_ats_result.eq('W').sum())
        losses=int(common.fixed_band_ats_result.eq('L').sum())
        rate=f'{100*wins/(wins+losses):.1f}%'
        for text in ('ATS performance','Model ATS','Market favorite ATS','Home side ATS','Cover rate',rate,
                     'Running units','How picks work'):
            self.assertIn(text,html)
        self.assertIn('<svg',html)

    def test_render_keeps_forecast_archives_and_internal_probabilities(self):
        for name,before in self.before.items():
            self.assertEqual(hashlib.sha256((self.data/name).read_bytes()).hexdigest(),before)
        internal=pd.read_csv(self.data/'latest/fixed_band_ledger.csv')
        self.assertIn('model_wp',internal)
        self.assertIn('home_moneyline',internal)

    def test_empty_surfaces_still_render(self):
        for renderer in (b.render_index,b.render_grades,b.render_calibration):
            if renderer is b.render_index:
                html=renderer(None,pd.DataFrame(),'test')
            else:
                html=renderer(pd.DataFrame(),None,'test') if renderer is b.render_grades else renderer(None,pd.DataFrame(),'test')
            self.assertIn('<!doctype html>',html)
            self.assertNotIn('moneyline',self.visible(html).lower())


if __name__=='__main__':
    unittest.main()
