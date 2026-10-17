import numpy as np
import pandas as pd
import pytest

from research import wp_band_mov as w


def history():
    n = 560
    band = np.arange(n) % 7
    confidence = np.array([.525, .575, .625, .675, .725, .775, .85])[band]
    side = np.where(np.arange(n) % 2, -1., 1.)
    # Includes wins, losses and tied finals.
    pick_margin = np.resize(np.array([-10., 0., 20., 0.]), n) + band
    return pd.DataFrame({"game_id": [f"g{i}" for i in range(n)],
        "season": np.repeat([2021, 2022], n//2), "week": 1,
        "model_wp": np.where(side > 0, confidence, 1-confidence),
        "result": side * pick_margin, "model_spread": side * (band+1),
        "spread_line": side * band, "fixed_band_spread": side * band})


def test_means_use_signed_margins_including_losses_and_ties():
    d = history()
    f = w.fit_prior(d, 2023)
    expected = (np.sign(d.model_wp-.5)*d.result).groupby(np.arange(len(d)) % 7).mean()
    assert np.allclose(f["wp_means"], expected)
    assert f["wp_counts"] == [80]*7
    assert f["training_games"] == 560 and f["training_max_season"] == 2022
    # A winning-only mean or mean absolute margin would produce a different fit.
    assert f["wp_means"][0] == pytest.approx(2.5)
    g = d.iloc[:14].copy()
    g["season"] = 2023
    p = w.predict(g, f)
    assert np.allclose(p.wp_mean, np.sign(g.model_wp-.5)*np.resize(expected, len(g)))


def test_negative_band_mean_is_retained_and_can_flip_margin_sign():
    d = history()
    d["result"] = -3*np.sign(d.model_wp-.5)
    f = w.fit_prior(d, 2023)
    assert f["wp_means"] == [-3.]*7
    assert f["wp_monotone_means"] == [-3.]*7
    assert f["wp_medians"] == [-3.]*7
    g = d.iloc[:1].copy()
    g["season"] = 2023
    assert w.predict(g, f).wp_mean.iloc[0] == -3


def test_median_counts_losses_and_ties_and_averages_even_central_values():
    d = history()
    f = w.fit_prior(d, 2023)
    assert f["wp_means"][0] == 2.5 and f["wp_medians"][0] == 0
    mask = np.arange(len(d)) % 7 == 0
    d.loc[mask, "result"] = np.sign(d.loc[mask, "model_wp"]-.5)*np.resize([1., 2., 3., 10.], mask.sum())
    f = w.fit_prior(d, 2023)
    assert f["wp_medians"][0] == 2.5
    g = d.iloc[:2].copy()
    g["season"] = 2023
    assert w.predict(g, f).wp_median.iloc[0] == 2.5


def test_median_uses_same_prior_group_membership_as_mean():
    d = history()
    f = w.fit_prior(d, 2023)
    conf = np.maximum(d.model_wp, 1-d.model_wp)
    signed = np.sign(d.model_wp-.5)*d.result
    for prefix, cuts in (("wp", w.WP_CUTS), ("four", w.FOUR_CUTS)):
        bins = np.digitize(conf, cuts)
        for k, value in enumerate(f[prefix+"_medians"]):
            assert value == np.median(signed[bins == k])


def test_weighted_isotonic_pools_only_reversals():
    assert np.allclose(w.isotonic_means([5, 1, 4, 9], [1, 3, 1, 1]), [2, 2, 4, 9])
    assert np.allclose(w.isotonic_means([-4, -2, 1], [1, 2, 3]), [-4, -2, 1])
    assert np.allclose(w.isotonic_means([6, 3, 1], [1, 1, 1]), [10/3]*3)
    with pytest.raises(ValueError, match="Invalid bin"):
        w.isotonic_means([1, 2], [1, 0])


def test_boundaries_endpoints_half_and_missing():
    f = w.fit_prior(history(), 2023)
    f["wp_means"] = list(range(7))
    p = [.5, .55, .6, .65, .7, .75, .8, 1., 0., np.nan]
    g = pd.DataFrame({"game_id": [str(i) for i in range(len(p))],
                      "season": 2023, "week": 1, "model_wp": p})
    result = w.predict(g, f).wp_mean.to_numpy()
    assert np.array_equal(result[:-1], [0., 1., 2., 3., 4., 5., 6., 6., -6.])
    assert np.isnan(result[-1])
    d = history()
    d.loc[0, "model_wp"] = .5
    d.loc[0, "result"] = 1000
    assert w.fit_prior(d, 2023)["training_games"] == 559


def test_cutoffs_and_empty_bins_fail_explicitly():
    d = history()
    with pytest.raises(ValueError, match="Own/future"):
        w.fit_prior(d, 2022)
    with pytest.raises(ValueError, match="300"):
        w.fit_prior(d.iloc[:100], 2023)
    with pytest.raises(ValueError, match="Empty"):
        w.fit_prior(d[np.arange(len(d)) % 7 != 6], 2023)
    with pytest.raises(ValueError, match="season differs"):
        w.predict(d.iloc[:1], w.fit_prior(d, 2023))


@pytest.mark.parametrize("column,value,message", [
    ("model_wp", 1.01, "Invalid model"),
    ("model_wp", np.inf, "Invalid model"),
    ("season", np.nan, "Missing season/week"),
    ("week", 1.5, "Noninteger"),
])
def test_malformed_inputs_fail(column, value, message):
    d = history()
    d[column] = d[column].astype(float)
    d.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        w.fit_prior(d, 2023)


def test_duplicate_games_fail():
    d = history()
    d.loc[1, "game_id"] = d.loc[0, "game_id"]
    with pytest.raises(ValueError, match="duplicate"):
        w.fit_prior(d, 2023)


def test_current_labels_cannot_change_same_year_forecasts():
    h = history()
    g = h.iloc[:21].copy()
    g["game_id"] += "new"
    g["season"] = 2023
    a, fa = w.evaluate(pd.concat([h, g], ignore_index=True))
    g["result"] = 1000
    b, fb = w.evaluate(pd.concat([h, g], ignore_index=True))
    assert fa == fb
    assert np.array_equal(a[list(w.ARMS)], b[list(w.ARMS)])


def test_paired_week_bootstrap_and_ats_skip_push_conventions():
    d = history().iloc[:28].copy()
    d["season"] = 2023
    d["week"] = np.repeat([1, 2, 3, 4], 7)
    for arm in w.ARMS:
        d[arm] = d.model_spread
    r = w.paired_comparisons(d, draws=100)
    assert r == w.paired_comparisons(d, draws=100)
    for row in r:
        assert row["season_week_blocks"] == 4
        if row["baseline"] == "model_spread":
            assert row["gain"] == 0 and row["ci95"] == [0, 0]
    d = pd.DataFrame({"result": [0., 3., 3.], "spread_line": [3., 3., 3.],
                      "wp_mean": [2., 4., 3.]})
    r = w.c.ats_scores(d, "wp_mean")
    assert (r["wins"], r["losses"], r["pushes"], r["skips"]) == (1, 0, 1, 1)


def test_protected_output_fails_before_io():
    with pytest.raises(ValueError, match="Protected"):
        w.run(w.ROOT/"absent", w.ROOT/"absent2", w.ROOT/"data/test")
