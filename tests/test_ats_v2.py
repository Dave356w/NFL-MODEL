"""ATS v2 scoring-aware production selection and immutable benchmark tests."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import ats_v2
import fixed_bands


def test_consensus_requires_positive_expected_return():
    d = ats_v2.decide(8., 7., 6.5, .60, .35, .05)
    assert d["side"] == "home" and d["source"] == "agreement"
    assert d["ev"] > 0
    d = ats_v2.decide(8., 7., 6.5, .48, .48, .04)
    assert d["side"] == "" and d["reason"] == "no_positive_ev"


def test_conflict_only_probability_supported_side_is_selected():
    # Legacy fixed bands flip to the underdog; the probability model supports
    # the original favorite. ATS v2 must avoid the unsupported reversal.
    d = ats_v2.decide(8.3, 7., 7.5, .60, .35, .05)
    assert d["side"] == "home" and d["source"] == "original_confirmed"
    # Opposite scoring evidence supports the fixed-band underdog.
    d = ats_v2.decide(8.3, 7., 7.5, .40, .55, .05)
    assert d["side"] == "away" and d["source"] == "fixed_reversal_confirmed"
    # A push is refunded: win profitability excludes the push.
    d = ats_v2.decide(8.3, 7., 7.5, .48, .48, .04)
    assert d["side"] == "" and d["reason"] == "no_positive_ev"


def test_zero_edge_candidate_can_fall_back_or_skip():
    d = ats_v2.decide(7.8, 7., 7., .60, .35, .05)
    assert d["side"] == "home" and d["source"] == "original_confirmed"
    d = ats_v2.decide(7., 7., 7., .60, .35, .05)
    assert d["side"] == "" and d["reason"] == "no_candidate"


def test_invalid_and_unavailable_distribution_fail_closed():
    d = ats_v2.decide(math.nan, 7., 7.5, .60, .35, .05)
    assert d["side"] == "" and d["reason"] == "unavailable"
    try:
        ats_v2.decide(8., 7., 7.5, .7, .7, 0.)
        assert False, "Expected invalid total to be rejected"
    except ValueError:
        pass


def test_graded_opportunities_include_skips_and_pushes():
    frame = pd.DataFrame({
        "season": [2026] * 4, "fixed_band_spread": [7.] * 4,
        "spread_line": [7.] * 4, "result": [8., 7., 6., 8.],
        "v2_ats_result": ["W", "P", "L", "S"]})
    result = ats_v2.summary(frame)
    row = result[result.season == "All"].iloc[0]
    assert row.opportunities == 4 and row.bets == 3 and row.skips == 1
    assert row.wins == row.losses == row.pushes == 1
    assert math.isclose(row.units, 10/11 - 1)
    assert math.isclose(row.coverage, .75)


def test_fixed_historical_benchmark_not_modified_by_v2():
    root = Path(__file__).resolve().parents[1]
    legacy = pd.read_csv(root / "data/latest/fixed_band_ledger.csv")
    baseline = fixed_bands.summary(legacy)
    assert "Fixed bands" in set(baseline.method)
    assert baseline[(baseline.method == "Fixed bands") &
                    (baseline.season == "All")].iloc[0].bets == 856


def test_chronology_and_no_training_on_current_season():
    # Only 2021 and 2022 may train the 2023 scoring distribution.
    x = pd.DataFrame({
        "season": [2021] * 160 + [2022] * 160 + [2023] * 2,
        "week": [1] * 322,
        "game_id": [str(i) for i in range(322)],
        "home": ["BUF"] * 322,
        "away": ["MIA"] * 322,
        "model_spread": [4.] * 322,
        "fixed_band_spread": [5.] * 322,
        "spread_line": [4.5] * 322,
        "result": [7., 3.] * 161,
        "home won": [1., 1.] * 161,
    })
    latest = {"fixed_band_ledger": x,
              "board": x.iloc[-1:].drop(columns=["result"]).assign(result=np.nan)}
    ats_v2.prepare(latest)
    y = latest["ats_v2_ledger"]
    assert all(y.loc[y.season < 2023, "v2_ats_skip_reason"] ==
               "insufficient_prior_seasons")
    assert math.isfinite(y.loc[y.season == 2023, "v2_p_home_cover"].iloc[0])
    assert math.isfinite(latest["board"].v2_p_home_cover.iloc[0])
    # Poison target year results: the 2023 fit must remain unchanged.
    poisoned = x.copy()
    poisoned.loc[poisoned.season == 2023, "result"] = -75.
    latest2 = {"fixed_band_ledger": poisoned,
               "board": x.iloc[-1:].drop(columns=["result"]).assign(result=np.nan)}
    ats_v2.prepare(latest2)
    assert np.isclose(latest["board"].v2_p_home_cover.iloc[0],
                      latest2["board"].v2_p_home_cover.iloc[0])
