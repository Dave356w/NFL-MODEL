"""Model-confidence band mean signed MOV, fitted on strictly earlier seasons.

Research only. Fixed design: research/WP_BAND_MOV.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

from research import continuous_spread as c

ROOT = c.ROOT
ARMS = ("wp_mean", "wp_monotone_mean", "four_band_mean", "wp_median", "four_band_median")
BASELINES = c.BASELINES
WP_CUTS = np.array([.55, .60, .65, .70, .75, .80])
FOUR_CUTS = ndtr(np.array([3., 7., 10.]) / 12.37)
WP_LABELS = ["50–55%", "55–60%", "60–65%", "65–70%", "70–75%", "75–80%", "80%+"]
INPUT = ROOT / "research/continuous_spread_results/input.csv"
BOARD = ROOT / "research/continuous_spread_results/board_input.csv"


def prepare(frame):
    d = frame.copy()
    if d.game_id.isna().any() or d.game_id.duplicated().any():
        raise ValueError("Missing or duplicate game IDs")
    for name in ("season", "week", "model_wp"):
        d[name] = pd.to_numeric(d[name], errors="coerce")
    if not np.isfinite(d[["season", "week"]]).all().all():
        raise ValueError("Missing season/week")
    if ((d[["season", "week"]] % 1) != 0).any().any():
        raise ValueError("Noninteger season/week")
    bad = d.model_wp.notna() & (~np.isfinite(d.model_wp) | ~d.model_wp.between(0, 1))
    if bad.any():
        raise ValueError("Invalid model probability")
    d["confidence"] = np.maximum(d.model_wp, 1-d.model_wp)
    d["pick_sign"] = np.sign(d.model_wp-.5)
    if "result" in d:
        d["result"] = pd.to_numeric(d.result, errors="coerce")
    return d


def isotonic_means(means, counts):
    """Weighted PAVA: exact constrained least-squares fit of bin means."""
    means, counts = np.asarray(means, float), np.asarray(counts, float)
    if (means.ndim != 1 or counts.shape != means.shape or not len(means) or
            not np.isfinite(means).all() or not np.isfinite(counts).all() or
            (counts <= 0).any()):
        raise ValueError("Invalid bin means/counts")
    blocks = []
    for i, (value, weight) in enumerate(zip(means, counts)):
        blocks.append([value * weight, weight, i, i+1])
        while len(blocks) > 1 and blocks[-2][0]/blocks[-2][1] > blocks[-1][0]/blocks[-1][1]:
            b = blocks.pop()
            a = blocks.pop()
            blocks.append([a[0]+b[0], a[1]+b[1], a[2], b[3]])
    fitted = np.empty_like(means)
    for total, weight, first, last in blocks:
        fitted[first:last] = total/weight
    return fitted


def fit_prior(history, target_season):
    d = prepare(history)
    if not (d.season < target_season).all():
        raise ValueError("Own/future season in mean-MOV training")
    d = d[np.isfinite(d[["result", "model_wp"]]).all(axis=1) & d.pick_sign.ne(0)]
    if len(d) < 300 or d.season.nunique() < 2:
        raise ValueError("Requires >=300 directed games and >=2 earlier seasons")
    margin = (d.pick_sign * d.result).to_numpy(float)
    fit = {"target_season": int(target_season), "training_games": len(d),
           "training_max_season": int(d.season.max()), "wp_cuts": WP_CUTS.tolist(),
           "four_cuts": FOUR_CUTS.tolist()}
    for prefix, cuts in (("wp", WP_CUTS), ("four", FOUR_CUTS)):
        band = np.digitize(d.confidence, cuts)
        counts = np.bincount(band, minlength=len(cuts)+1)
        if not counts.all():
            raise ValueError("Empty prior-season confidence band")
        means = np.bincount(band, weights=margin, minlength=len(counts))/counts
        fit[prefix+"_counts"] = counts.tolist()
        fit[prefix+"_means"] = means.tolist()
        fit[prefix+"_medians"] = [float(np.median(margin[band == k])) for k in range(len(counts))]
    fit["wp_monotone_means"] = isotonic_means(fit["wp_means"], fit["wp_counts"]).tolist()
    return fit


def predict(frame, fit):
    d = prepare(frame)
    if fit["training_max_season"] >= fit["target_season"]:
        raise ValueError("Fit has own/future labels")
    if not (d.season == fit["target_season"]).all():
        raise ValueError("Forecast season differs from fitted season")
    for arm, key, cuts in (("wp_mean", "wp_means", fit["wp_cuts"]),
                          ("wp_monotone_mean", "wp_monotone_means", fit["wp_cuts"]),
                          ("four_band_mean", "four_means", fit["four_cuts"]),
                          ("wp_median", "wp_medians", fit["wp_cuts"]),
                          ("four_band_median", "four_medians", fit["four_cuts"])):
        band = np.digitize(d.confidence, cuts)
        d[arm] = d.pick_sign * np.asarray(fit[key])[band]
        d.loc[d.model_wp.isna(), arm] = np.nan
    return d


def evaluate(history):
    d = prepare(history).sort_values(["season", "week", "game_id"])
    scored, fits = [], []
    for year in sorted(int(y) for y in d.season.unique() if y >= 2023):
        fit = fit_prior(d[d.season < year], year)
        fits.append(fit)
        test = d[d.season == year]
        valid = np.isfinite(test[["result", "model_wp", *BASELINES]]).all(axis=1)
        if valid.any():
            scored.append(predict(test[valid], fit))
    if not scored:
        raise ValueError("No common evaluation games")
    return pd.concat(scored, ignore_index=True), fits


def paired_comparisons(d, draws=10_000):
    """Pair methods, resample complete weeks within each represented season."""
    rows, losses = [], {}
    for arm in (*ARMS, *BASELINES):
        error = d[arm].to_numpy()-d.result.to_numpy()
        losses[arm] = {"mse": error**2, "mae": np.abs(error),
                       "ats_units_per_opportunity": -c.grade(d, d[arm])[1]}
    differences = []
    for arm in ARMS:
        baselines = list(BASELINES)
        if arm in ("wp_median", "four_band_median"):
            baselines.append("wp_mean" if arm == "wp_median" else "four_band_mean")
        for baseline in baselines:
            for metric in ("mse", "mae", "ats_units_per_opportunity"):
                rows.append({"candidate": arm, "baseline": baseline, "metric": metric})
                differences.append(losses[baseline][metric]-losses[arm][metric])
    values = np.column_stack(differences)
    total, count = np.zeros((draws, values.shape[1])), np.zeros(draws)
    rng, clusters = np.random.default_rng(20261017), 0
    for year in sorted(d.season.unique()):
        ix = np.flatnonzero(d.season.to_numpy() == year)
        weeks = d.week.to_numpy()[ix]
        keys = np.unique(weeks)
        sizes = np.array([(weeks == w).sum() for w in keys])
        sums = np.array([values[ix[weeks == w]].sum(axis=0) for w in keys])
        sampled = rng.integers(0, len(keys), (draws, len(keys)))
        total += sums[sampled].sum(axis=1)
        count += sizes[sampled].sum(axis=1)
        clusters += len(keys)
    samples = total/count[:, None]
    for j, rec in enumerate(rows):
        rec.update(games=len(d), season_week_blocks=clusters, gain=float(values[:, j].mean()),
                   ci95=np.quantile(samples[:, j], [.025, .975]).tolist(),
                   ci_five_candidates=np.quantile(samples[:, j], [.05/10, 1-.05/10]).tolist())
    return rows


def summary(d):
    primary = d[d.season.between(2023, 2025)]
    if primary.empty:
        raise ValueError("Missing primary cohort")
    cohorts = {"primary_2023_2025": primary, "all_2023_onward": d,
               **{str(int(y)): g for y, g in d.groupby("season")}}
    paired = {key: paired_comparisons(g) for key, g in cohorts.items()
              if key in ("primary_2023_2025", "all_2023_onward", "2026")}
    nominees = []
    for arm in ARMS:
        target_metric = "mae" if arm in ("wp_median", "four_band_median") else "mse"
        tests = [r for r in paired["primary_2023_2025"] if r["candidate"] == arm and
                 r["metric"] == target_metric and r["baseline"] in ("model_spread", "spread_line")]
        if len(tests) == 2 and all(r["ci_five_candidates"][0] > 0 for r in tests):
            nominees.append(arm)
    sensitivity = {}
    for key, g in cohorts.items():
        if key not in ("primary_2023_2025", "2026", "all_2023_onward"):
            continue
        sensitivity[key] = {}
        for arm in ("fixed_band_spread", "wp_median", "four_band_median"):
            sensitivity[key][arm] = {}
            for epsilon in (-.01, 0., .01):
                perturbed = g.copy()
                perturbed["perturbed"] = g[arm] + epsilon*np.sign(g.model_wp-.5)
                sensitivity[key][arm][str(epsilon)] = c.ats_scores(perturbed, "perturbed")
    return {"status": "exposed historical development; assumed -110 ATS prices",
            "decision": "nominate_for_fresh_forward_test" if nominees else "retain_production_no_candidate_qualifies",
            "nominees": nominees, "primary_mean_arm": "wp_mean", "primary_median_arm": "wp_median",
            "paired_comparisons": paired,
            "integer_line_sensitivity": sensitivity,
            "cohorts": {key: {a: {**c.point_scores(g, a), "ats": c.ats_scores(g, a)}
                                 for a in (*BASELINES, *ARMS)} for key, g in cohorts.items()},
            "seed": 20261017, "bootstrap_draws": 10_000}


def run(source, board_source, output):
    output = output.resolve()
    for protected in (ROOT / "data", ROOT / "public"):
        if output == protected or protected in output.parents:
            raise ValueError("Protected output directory")
    history = pd.read_csv(source, float_precision="round_trip")
    board = pd.read_csv(board_source, float_precision="round_trip")
    d, fits = evaluate(history)
    result = summary(d)
    current, board_fits = [], []
    for year, g in board.groupby("season"):
        fitted = fit_prior(history[history.season < year], int(year))
        current.append(predict(g, fitted))
        board_fits.append(fitted)
    output.mkdir(parents=True, exist_ok=True)
    d.to_csv(output / "per_game.csv", index=False)
    pd.concat(current, ignore_index=True).to_csv(output / "current_counterfactuals.csv", index=False)
    (output / "fits.json").write_text(json.dumps({"historical": fits, "board": board_fits}, indent=2)+"\n")
    (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    sources = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):
               hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (source, board_source, Path(__file__), ROOT / "research/WP_BAND_MOV.md",
                         ROOT / "research/continuous_spread.py", ROOT / "fixed_bands.py")}
    (output / "provenance.json").write_text(json.dumps({"sources": sources,
        "scope": "research only; no production or ledger writes"}, indent=2)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "research/wp_band_mov_results")
    args = parser.parse_args()
    result = run(args.input, args.board, args.output_dir)
    print(result["decision"])
    for name in ("primary_2023_2025", "2026", "all_2023_onward"):
        print(name)
        for arm, metrics in result["cohorts"][name].items():
            print(arm, metrics)


if __name__ == "__main__":
    main()
