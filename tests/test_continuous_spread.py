import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

from research import continuous_spread as c


def history():
    n = 400
    line = np.resize(np.array([-7., -3., 3., 7.]), n)
    signal = np.resize(np.array([-2., 2., -2., 2.]), n)
    d = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)],
        "season": np.repeat([2021, 2022], n // 2), "week": 1,
        "home": "H", "away": "A", "spread_line": line,
        "model_wp": ndtr((line + signal) / c.SIGMA),
        "market_ml_wp": ndtr(line / c.SIGMA),
        "result": line + .8 * signal,
        "model_spread": line + signal, "fixed_band_spread": line})
    return d


def test_prior_slope_uses_margin_residual_and_shrinks():
    d = history()
    fit = c.fit_prior(d, 2023)
    expected = .8 * 1600 / (1600 + c.RIDGE)
    assert fit["beta_gap"] == pytest.approx(expected)
    assert fit["beta_signal"] == pytest.approx(expected)
    assert fit["training_max_season"] == 2022
    g = d.iloc[:4].copy()
    g["season"] = 2023
    p = c.predict(g, fit)
    assert np.allclose(p.signal_anchor, g.spread_line + expected * c.features(g).signal)
    # Positive signal reinforces home/away moneyline favorites symmetrically.
    assert c.features(g).reinforcing.tolist() == [True, False, False, True]


def test_slopes_are_bounded_and_zero_signal_returns_market():
    d = history()
    d["result"] = d.spread_line - 2 * c.features(d).signal
    assert c.fit_prior(d, 2023)["beta_signal"] == 0
    d["result"] = d.spread_line + 10 * c.features(d).signal
    fit = c.fit_prior(d, 2023)
    assert fit["beta_signal"] == 1
    g = d.iloc[:1].copy()
    g["season"] = 2023
    g["model_wp"] = g.market_ml_wp
    p = c.predict(g, fit)
    assert p.signal_anchor.iloc[0] == g.spread_line.iloc[0]
    assert p.split_signal_anchor.iloc[0] == g.spread_line.iloc[0]


def test_conversion_mismatch_is_removed_from_signal():
    d = history().iloc[:1].copy()
    d["model_wp"] = d.market_ml_wp
    d["spread_line"] += 1.5
    f = c.features(d)
    assert f.signal.iloc[0] == 0
    assert f.gap.iloc[0] == pytest.approx(-1.5)


def test_missing_inputs_never_create_forecast_even_with_zero_slope():
    fit = c.fit_prior(history(), 2023)
    fit.update(beta_gap=0., beta_signal=0., beta_reinforcing=0., beta_other=0.)
    d = history().iloc[:3].copy()
    d["season"] = 2023
    for i, col in enumerate(["model_wp", "market_ml_wp", "spread_line"]):
        d.loc[d.index[i], col] = np.nan
    assert c.predict(d, fit)[list(c.ARMS)].isna().all().all()


def test_rejects_own_future_labels_and_wrong_forecast_season():
    d = history()
    with pytest.raises(ValueError, match="Own/future"):
        c.fit_prior(d, 2022)
    with pytest.raises(ValueError, match="season differs"):
        c.predict(d.iloc[:1], c.fit_prior(d, 2023))
    with pytest.raises(ValueError, match="300"):
        c.fit_prior(d.iloc[:100], 2023)


@pytest.mark.parametrize("column,value,match", [
    ("model_wp", 1.01, "Invalid probability"),
    ("market_ml_wp", np.inf, "Invalid probability"),
    ("season", np.nan, "Missing season/week"),
    ("week", 1.5, "Noninteger"),
])
def test_malformed_inputs_fail(column, value, match):
    d = history()
    d[column] = d[column].astype(float)
    d.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        c.fit_prior(d, 2023)


def test_duplicate_ids_fail():
    d = history()
    d.loc[1, "game_id"] = d.loc[0, "game_id"]
    with pytest.raises(ValueError, match="duplicate"):
        c.fit_prior(d, 2023)


def test_evaluation_never_learns_current_season_labels():
    h = history()
    test = h.iloc[:16].copy()
    test["season"] = 2023
    test["game_id"] += "test"
    a, fits_a = c.evaluate(pd.concat([h, test], ignore_index=True))
    test["result"] += 100
    b, fits_b = c.evaluate(pd.concat([h, test], ignore_index=True))
    assert fits_a == fits_b
    assert np.array_equal(a[list(c.ARMS)], b[list(c.ARMS)])
    bad = pd.concat([h, test], ignore_index=True)
    bad.loc[0, "model_spread"] += 1
    with pytest.raises(ValueError, match="Saved raw spread"):
        c.evaluate(bad)


def test_ats_tied_final_can_win_and_zero_edge_skips_before_push():
    d = pd.DataFrame({"result": [0., 3., 3., 0.],
                      "spread_line": [3., 3., 3., 0.],
                      "forecast": [2., 4., 3., 0.]})
    s = c.ats_scores(d, "forecast")
    assert (s["wins"], s["losses"], s["pushes"], s["skips"]) == (1, 0, 1, 2)
    assert s["units"] == pytest.approx(10/11)
    assert s["opportunities"] == 4 and s["bets"] == 2


def test_week_bootstrap_is_paired_and_deterministic():
    d = history().iloc[:32].copy()
    d["season"] = 2023
    d["week"] = np.repeat([1, 2, 3, 4], 8)
    for arm in c.ARMS:
        d[arm] = d.model_spread
    a = c.paired_gains(d, draws=100)
    assert a == c.paired_gains(d, draws=100)
    for r in a:
        assert r["blocks"] == 4 and r["games"] == 32
        if r["baseline"] == "model_spread":
            assert r["gain"] == 0 and r["ci95"] == [0, 0]


def test_protected_output_fails_before_reading_or_writing():
    with pytest.raises(ValueError, match="Protected"):
        c.run(c.ROOT / "absent.csv", c.ROOT / "absent_board.csv", c.ROOT / "data/test")
