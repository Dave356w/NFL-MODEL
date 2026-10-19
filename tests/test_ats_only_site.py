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
        pd.DataFrame([card]).to_csv(cls.data/'latest/board.csv',index=False)
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

    def test_cards_preserve_skips_and_do_not_display_a_refreshed_winner(self):
        html=(self.out/'index.html').read_text()
        card=next(c for c in html.split("<details class='card'>")[1:] if 'Titans' in c.split('</summary>')[0])
        summary=card.split('</summary>')[0]
        self.assertIn('No bet · zero projected edge',summary)
        self.assertIn('Market IND −7.0',summary)
        self.assertIn('ATS result · Skip',summary)
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
        self.assertEqual(row.selected_team,'')
        self.assertEqual(row.ats_result,'S')
        self.assertEqual(float(row.ats_units),0.)

    def test_results_show_sources_and_each_game_once(self):
        html=(self.out/'grades.html').read_text()
        self.assertIn('Earlier recorded picks',html)
        self.assertIn('60-minute locks',html)
        self.assertIn('Historical replay',html)
        self.assertIn('Replayed pregame forecasts',html)
        self.assertIn('Game-by-game ATS results',html)
        self.assertEqual(html.count("data-game-id='2026_06_TEN_IND'"),1)
        week=self.pool[self.pool.week.eq(6)].fixed_band_ats_result
        record='–'.join(str(int(week.eq(k).sum())) for k in 'WLP')
        self.assertIn(f'2026 week 6 · {record} · {int(week.eq("S").sum())} skips',html)

    def test_performance_has_ats_controls_and_cover_rates(self):
        html=(self.out/'market-calibration.html').read_text()
        common=self.pool[self.pool.spread_line.ne(0) & self.pool.fixed_band_ats_result.isin(['W','L','P'])]
        wins=int(common.fixed_band_ats_result.eq('W').sum())
        losses=int(common.fixed_band_ats_result.eq('L').sum())
        rate=f'{100*wins/(wins+losses):.1f}%'
        for text in ('ATS performance','Model ATS','Market favorite ATS','Home side ATS','Cover rate',rate):
            self.assertIn(text,html)

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
