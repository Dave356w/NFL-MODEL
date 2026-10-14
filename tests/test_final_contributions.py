import numpy as np
import pandas as pd
import pytest
import nfl_model as m


@pytest.mark.parametrize('penalty', [None, .2])
def test_contributions_reconstruct_final_forecast_for_both_favorites_and_disagreements(penalty):
    # Home-bullish, away-bullish, market disagreement, weaker favorite, and neutral market.
    frame = pd.DataFrame({'game_id': list('abcde'), 'home': 'H', 'away': 'A',
                          'site': [1., -1., -1., -.1, 0.], 'q': [.6, .4, .6, .6, .5]})
    for c in m.PRODUCT_CONTEXT_NAMES: frame[c] = 0.
    recipe = {} if penalty is None else {'favorite_penalty': penalty}
    fit = {'names': ['site'], 'scale': [1.], 'beta': [1.], 'market_offset': True, 'recipe': recipe}
    _, score, raw = m.apply_fit(frame, fit, contributions=True)
    parts = m.contribution_table(frame, fit)
    sums = parts.groupby('game_id')['log-odds contribution'].sum().loc[frame.game_id]
    np.testing.assert_allclose(sums, score, rtol=0, atol=1e-12)
    expected = frame.site.to_numpy().copy()
    if penalty is not None: expected[:2] *= penalty
    np.testing.assert_allclose(parts[parts.feature == 'site']['log-odds contribution'], expected, atol=1e-12)
    np.testing.assert_array_equal(raw[:, 0], frame.site)    # raw research attribution stays raw


def test_native_snapshot_explanations_reconstruct_penalized_probabilities():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parents[1]
    # Native snapshots carry the actual fit and inputs, independent of regenerated exports.
    rows = [json.loads(x) for x in (root/'data/forward_predictions.jsonl').read_text().splitlines()]
    row = next(r for r in rows if r['revision'] == 'boxscore-composite-v1.16')
    board = pd.DataFrame([{**row['model_inputs'], 'q': row['market_no_vig_wp'],
                           'game_id': row['game_id'], 'home': row['home'], 'away': row['away']}])
    fit = dict(row['coefficient_fit'], recipe=m.PRODUCT_RECIPE)
    total = m.contribution_table(board, fit)['log-odds contribution'].sum()
    assert m.expit(total) == pytest.approx(m.apply_fit(board, fit)[0], abs=1e-12)
