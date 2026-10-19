"""All-version reports preserve native identity and frozen comparison cohorts."""
import numpy as np
import pandas as pd
import pytest
from research import version_report as v


def test_historical_controls_and_cohorts_are_explicit():
    frame=v.historical_tests()
    assert set(frame.study)==set(v.STUDIES)
    assert frame.basis.eq('exposed 2023-2025 chronological development').all()
    assert frame.groupby('study').favorite_units.nunique().eq(1).all()
    assert set(frame.bets)=={811,812}
    assert frame.loc[frame.study.eq('context'),'study_production_label'].str.startswith('pre-v1.16').all()


def test_archived_pending_games_are_not_scored_or_backfilled():
    records=pd.read_csv(v.ROOT/'data/forward_ledger.csv')
    outcomes=records.assign(result=np.nan,**{'home won':np.nan})  # replace whole columns: an all-graded ledger stores integer results
    report=v.archived_tests(outcomes)
    assert report.bets.eq(0).all() and report.binary_games.eq(0).all()
    assert report.pending.eq(report.games).all()
    assert report.log_loss.isna().all()
    assert report.basis.str.contains('not native forward').all()


def test_conflicting_results_rejected():
    records=pd.read_csv(v.ROOT/'data/forward_ledger.csv')
    changed=records.iloc[:1].copy();changed['result']=999.;changed['home won']=1.
    with pytest.raises(ValueError,match='Conflicting'):
        v.archived_tests(pd.concat([records,changed],ignore_index=True))


def test_native_experiments_cannot_count_a_game_twice():
    records=pd.read_csv(v.ROOT/'data/forward_ledger.csv')
    with pytest.raises(ValueError,match='repeats a game'):
        v.native_tests(pd.concat([records,records.iloc[:1]],ignore_index=True))


def test_selection_benchmark_section_reports_the_committed_adjustment(tmp_path):
    lines='\n'.join(v.selection_lines())
    assert 'not forward evidence' in lines and 'v1.16 beats it by' in lines and 'Reality Check p' in lines
    assert 'p-values are optimistic' in lines
    assert v.selection_lines(tmp_path/'missing.json')==['The selection-adjusted benchmark has not been committed.']


def test_market_context_promotion_is_not_described_as_legacy_penalty(monkeypatch):
    monkeypatch.setattr(v.m,'REVISION','boxscore-composite-v1.19')
    monkeypatch.setattr(v.m,'PRODUCT_RECIPE',dict(architecture='market_spread_total'))
    monkeypatch.setattr(v.m,'config_signature',lambda:('new-signature',{}))
    text='\n'.join(v.production_lines())
    assert 'all 29 football inputs' in text and 'continuous ATS spread' in text
    assert 'Original pregame forecasts and older revisions remain unchanged' in text
    assert 'favorite-confidence penalty' not in text


def test_legacy_penalty_description_retains_its_own_identity(monkeypatch):
    monkeypatch.setattr(v.m,'REVISION','boxscore-composite-v1.18')
    monkeypatch.setattr(v.m,'PRODUCT_RECIPE',dict(architecture='market_product_1sd',favorite_penalty=.2))
    monkeypatch.setattr(v.m,'config_signature',lambda:('old-signature',{}))
    text='\n'.join(v.production_lines())
    assert 'favorite-confidence penalty' in text and '**boxscore-composite-v1.18**' in text
    assert '29 football inputs' not in text
