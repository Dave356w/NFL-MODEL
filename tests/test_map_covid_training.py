import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research'))
import map_covid_training as mct  # noqa: E402


def history(seasons, shift=None):
    """Four bands, 40 games each per season; the model side wins by its own spread plus a season shift."""
    rows = []
    for y in seasons:
        for w in range(1, 5):
            for x in (1., 5., 8., 12.):
                for k in range(10):
                    rows.append(dict(season=y, week=w, model_spread=x, spread_line=x,
                                     result=x + (shift or {}).get(y, 0.), game_id=f'{y}_{w}_{x}_{k}'))
    return pd.DataFrame(rows)


def test_excluded_seasons_never_enter_the_rule():
    h = history(range(2017, 2023), shift={2020: 20., 2021: 20.})
    scored = h[h.season == 2022]
    x = mct.weekly_rules(h, scored, mct.EXCLUDED)[(2022, 1)]
    f = mct.weekly_rules(h, scored)[(2022, 1)]
    assert x['magnitudes'] == [1., 5., 8., 12.] and x['training_max_season'] == 2019
    # The control map is pulled by the shifted seasons, which carry most of the decayed weight.
    assert f['magnitudes'] == [21., 25., 28., 32.] and f['training_max_season'] == 2021


def test_rule_uses_only_earlier_weeks_of_the_scored_season():
    h = history(range(2017, 2023), shift={2022: 50.})
    scored = h[h.season == 2022]
    rules = mct.weekly_rules(h, scored, mct.EXCLUDED)
    assert rules[(2022, 1)]['magnitudes'] == [1., 5., 8., 12.]
    assert rules[(2022, 2)]['training_max_season'] == 2022 and rules[(2022, 2)]['training_max_week'] == 1


def test_too_little_history_after_exclusion_gives_no_rule():
    h = history((2020, 2021, 2022))
    assert mct.weekly_rules(h, h[h.season == 2022], mct.EXCLUDED)[(2022, 1)] is None
    assert mct.weekly_rules(h, h[h.season == 2022])[(2022, 1)] is not None


def test_arm_without_predictions_is_skipped_not_scored():
    d = pd.DataFrame({'spread_line': [3.5], 'result': [7.], 'model_spread': [4.], 'X model': [5.], 'X line-only': [5.],
                      'F model': [5.], 'F line-only': [5.], 'P model': [np.nan], 'R raw': [4.]})
    rows, contrasts = mct.summarize(d, '2022', '2022')
    assert 'P model' not in {r['arm'] for r in rows}
    assert not any('P model' in c['contrast'] for c in contrasts)


def test_verdict_directions():
    assert mct.verdict(dict(units=-40., z=-2.5)) == 'covid training helped'
    assert mct.verdict(dict(units=40., z=2.5)) == 'covid training hurt'
    assert mct.verdict(dict(units=13.4, z=.82)) == 'unresolved'
