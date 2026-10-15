"""Test 48: prior-season NFL margin PMF -> ATS cover probabilities (RESEARCH ONLY).

A discrete market-centered Gaussian with empirical score-margin key-number weights
is fit strictly on seasons before the scored season. A single pre-season shrinkage
coefficient tilts that PMF by the ORIGINAL model-minus-market spread disagreement.
The frozen historical recipe was selected on exposed data: not independent OOS.

No tuning on scored seasons; benchmark market cover is 50% conditional on no push.
Prices are hypothetical -110 both sides; no bookmaker ATS timestamp/quote exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/latest/fixed_band_ledger.csv"
GRID = np.arange(-70, 71, dtype=float)
ABS = np.abs(GRID).astype(int)
SIGMA = 12.37  # already used by the production spread comparator; not tuned here
L2 = 200.0
PSEUDO = 8.0
MAX_KEY = 40
WIN_PROFIT = 10.0 / 11.0
EPS = 1e-9
ARMS = ("original", "fixed_band", "cover_probability", "market_favorite")


def bin_normal(center: np.ndarray | float) -> np.ndarray:
    mu = np.asarray(center, dtype=float).reshape(-1, 1)
    p = ndtr((GRID[None, :] + .5 - mu) / SIGMA) - ndtr(
        (GRID[None, :] - .5 - mu) / SIGMA)
    return np.maximum(p, 0.) / np.maximum(p.sum(axis=1, keepdims=True), 1e-300)


def fit_prior(training: pd.DataFrame, target_season: int) -> dict:
    """Season boundary fit; no own/future result even from another week."""
    if len(training) and not (pd.to_numeric(training.season) < target_season).all():
        raise ValueError("own/future seasons in margin calibration")
    d = training.copy()
    for col in ("result", "spread_line", "model_spread"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["result", "spread_line", "model_spread"])
    d = d.loc[np.isfinite(d[["result", "spread_line", "model_spread"]]).all(axis=1)]
    if d.season.nunique() < 2 or len(d) < 300:
        raise ValueError("requires >=2 earlier seasons and >=300 games")
    observed = np.abs(np.rint(d.result.to_numpy())).astype(int)
    expected_bins = bin_normal(d.spread_line.to_numpy()).sum(axis=0)
    expected_abs = np.bincount(ABS, weights=expected_bins, minlength=71)
    observed_abs = np.bincount(observed[observed <= 70], minlength=71)
    boosts = np.ones(71)
    boosts[:MAX_KEY + 1] = np.clip(
        (observed_abs[:MAX_KEY + 1] + PSEUDO) /
        (expected_abs[:MAX_KEY + 1] + PSEUDO), .5, 2.5)
    delta = d.model_spread.to_numpy() - d.spread_line.to_numpy()
    residual = d.result.to_numpy() - d.spread_line.to_numpy()
    beta = np.clip(np.dot(delta, residual) / (np.dot(delta, delta) + L2), -1., 1.)
    return {"target_season": int(target_season),
            "training_max_season": int(d.season.max()),
            "n_training": len(d), "beta": float(beta),
            "boosts": boosts.tolist(), "sigma": SIGMA,
            "ridge": L2, "pseudocount": PSEUDO}


def distribution(line: float, model_gap: float, fitted: dict) -> tuple[np.ndarray, np.ndarray]:
    """Market PMF calibrated to a 50/50 nonpush cover; optional model tilt."""
    if fitted["training_max_season"] >= fitted["target_season"]:
        raise ValueError("calibration has future labels")
    boost = np.asarray(fitted["boosts"], float)[ABS]
    above = GRID > line + EPS
    below = GRID < line - EPS

    def calc(mu: float) -> np.ndarray:
        p = bin_normal(mu)[0] * boost
        return p / p.sum()

    lo, hi = line - 8., line + 8.
    for _ in range(28):
        mid = (lo + hi) / 2.
        p = calc(mid)
        if p[above].sum() > p[below].sum():
            hi = mid
        else:
            lo = mid
    anchor = (hi + lo) / 2.
    market = calc(anchor)
    corrected = calc(anchor + fitted["beta"] * model_gap)
    return market, corrected


def event(p: np.ndarray, line: float) -> tuple[float, float, float]:
    h = float(p[GRID > line + EPS].sum())
    a = float(p[GRID < line - EPS].sum())
    push = max(0., 1. - h - a)
    return h, a, push


def grade(margin: float, line: float, side: str) -> tuple[str, float]:
    if side not in ("home", "away"):
        return "S", 0.
    covered = margin - line
    if abs(covered) <= EPS:
        return "P", 0.
    won = (covered > 0.) == (side == "home")
    return ("W", WIN_PROFIT) if won else ("L", -1.)


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    for c in ("season", "week", "result", "spread_line", "model_spread", "fixed_band_spread"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["game_id", "season", "week", "result", "spread_line", "model_spread"])
    d = d.loc[np.isfinite(d[["result", "spread_line", "model_spread"]]).all(axis=1)]
    if d.game_id.duplicated().any():
        raise ValueError("duplicate game IDs would bias evaluation")
    return d.sort_values(["season", "week", "game_id"]).reset_index(drop=True)


def evaluate(frame: pd.DataFrame, start_season: int = 2023) -> tuple[pd.DataFrame, list[dict]]:
    d = prepare(frame)
    observations, fits = [], []
    for year in sorted(int(y) for y in d.season.unique() if y >= start_season):
        prior = d[d.season < year]
        test = d[(d.season == year) & d.fixed_band_spread.notna()]
        if test.empty:
            continue
        fit = fit_prior(prior, year)
        fits.append({key: fit[key] for key in ("target_season", "training_max_season",
                     "n_training", "beta")} |
                    {"key3": fit["boosts"][3], "key7": fit["boosts"][7]})
        for _, record in test.iterrows():
            line = float(record.spread_line)
            margin = float(record.result)
            gap = float(record.model_spread - record.spread_line)
            base, corrected = distribution(line, gap, fit)
            hm, am, pm = event(base, line)
            hc, ac, pc = event(corrected, line)
            ev_home = WIN_PROFIT * hc - ac
            ev_away = WIN_PROFIT * ac - hc
            side = ("home" if ev_home > ev_away else "away") if max(ev_home, ev_away) > EPS else ""
            original = "home" if gap > EPS else "away" if gap < -EPS else ""
            fixed_gap = float(record.fixed_band_spread) - line
            fixed = "home" if fixed_gap > EPS else "away" if fixed_gap < -EPS else ""
            fav = "home" if line > EPS else "away" if line < -EPS else ""
            out = {"game_id": record.game_id, "season": year, "week": int(record.week),
                   "basis": record.basis, "spread_line": line, "model_spread": float(record.model_spread),
                   "fixed_band_spread": float(record.fixed_band_spread), "margin": margin,
                   "beta_prior": fit["beta"], "market_home_cover": hm, "market_away_cover": am,
                   "market_push": pm, "corrected_home_cover": hc, "corrected_away_cover": ac,
                   "corrected_push": pc, "home_ev_110": ev_home, "away_ev_110": ev_away,
                   "nll_market_margin": -np.log(max(base[int(margin + 70)] if margin.is_integer() and -70 <= margin <= 70 else 1e-15, 1e-15)),
                   "nll_corrected_margin": -np.log(max(corrected[int(margin + 70)] if margin.is_integer() and -70 <= margin <= 70 else 1e-15, 1e-15))}
            for arm, s in (("original", original), ("fixed_band", fixed),
                           ("cover_probability", side), ("market_favorite", fav)):
                g, u = grade(margin, line, s)
                out[arm + "_side"] = s
                out[arm + "_grade"] = g
                out[arm + "_units"] = u
            if abs(margin - line) > EPS:
                actual = float(margin > line)
                q0 = hm / (hm + am)
                q1 = hc / (hc + ac)
                out.update(binary_scored=True,
                           market_cover_ll=-np.log(np.clip(q0 if actual else 1-q0, 1e-12, 1.)),
                           corrected_cover_ll=-np.log(np.clip(q1 if actual else 1-q1, 1e-12, 1.)),
                           market_cover_brier=(q0-actual)**2,
                           corrected_cover_brier=(q1-actual)**2)
            else:
                out.update(binary_scored=False, market_cover_ll=np.nan,
                           corrected_cover_ll=np.nan, market_cover_brier=np.nan,
                           corrected_cover_brier=np.nan)
            observations.append(out)
    return pd.DataFrame(observations), fits


def score(frame: pd.DataFrame, arm: str) -> dict:
    g = frame[frame[arm+"_grade"] != "S"]
    units = float(g[arm+"_units"].sum())
    return {"games": len(frame), "bets": len(g), "coverage": float(len(g)/len(frame)) if len(frame) else 0.,
            "W": int(g[arm+"_grade"].eq("W").sum()), "L": int(g[arm+"_grade"].eq("L").sum()),
            "P": int(g[arm+"_grade"].eq("P").sum()), "units": units,
            "ROI": units/len(g) if len(g) else None,
            "units_per_game": units/len(frame) if len(frame) else None}


def paired_ci(frame: pd.DataFrame, arm: str, comparator: str) -> dict:
    if len(frame) < 2:
        return {}
    diff = frame[arm+"_units"] - frame[comparator+"_units"]
    mean = float(diff.mean())
    g = (diff-mean).groupby([frame.season, frame.week]).sum()
    n, k = len(frame), len(g)
    se = np.sqrt(k/(k-1)*float(np.dot(g,g))/n**2) if k > 1 else np.nan
    return {"difference_units_per_game": mean, "clusters": k,
            "CI95_normal": [float(mean-1.96*se), float(mean+1.96*se)]}


def paired_metric_ci(frame: pd.DataFrame, baseline_col: str, challenger_col: str) -> dict:
    """Descriptive 95% season-week clustered paired gain (positive = better)."""
    d = frame.dropna(subset=[baseline_col, challenger_col])
    if len(d) < 2:
        return {"n": len(d), "gain": None, "CI95_normal": None}
    delta = d[baseline_col] - d[challenger_col]
    gain = float(delta.mean())
    clusters = (delta - gain).groupby([d.season, d.week]).sum()
    k, n = len(clusters), len(d)
    if k < 2:
        return {"n": n, "gain": gain, "clusters": k, "CI95_normal": None}
    se = float(np.sqrt(k/(k-1) * np.dot(clusters, clusters)/n**2))
    return {"n": n, "gain": gain, "clusters": k, "se": se,
            "CI95_normal": [gain - 1.96*se, gain + 1.96*se]}


def report(observations: pd.DataFrame, fits: list[dict]) -> dict:
    d = observations
    if d.empty:
        return {"error": "No eligible historical ATS games"}
    binary = d[d.binary_scored]
    matched_fixed = d[d.fixed_band_grade != "S"]
    return {
        "status": "exploratory exposed data; assumed -110 no historical ATS quotes",
        "games": len(d), "nonpush_games": len(binary), "fits": fits,
        "arms": {arm: score(d, arm) for arm in ARMS},
        "by_season": {str(int(year)): {arm: score(g, arm) for arm in ARMS}
                      for year, g in d.groupby("season")},
        "proper_scores": {
            metric: float(binary[metric].mean()) for metric in
            ("market_cover_ll", "corrected_cover_ll",
             "market_cover_brier", "corrected_cover_brier")},
        "margin_nll": {key: float(d[key].mean()) for key in
                       ("nll_market_margin", "nll_corrected_margin")},
        "paired_score_gains": {
            "cover_log_loss": paired_metric_ci(binary, "market_cover_ll", "corrected_cover_ll"),
            "cover_brier": paired_metric_ci(binary, "market_cover_brier", "corrected_cover_brier"),
            "margin_nll": paired_metric_ci(d, "nll_market_margin", "nll_corrected_margin"),
        },
        "paired_fixed_vs_original_matched": paired_ci(matched_fixed, "fixed_band", "original"),
        "paired_probability_vs_original_per_game": paired_ci(d, "cover_probability", "original"),
        "sha256_input": hashlib.sha256(d[["game_id", "season", "week", "margin",
                                      "spread_line", "model_spread",
                                      "fixed_band_spread"]].to_csv(index=False).encode()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    raw = pd.read_csv(args.input)
    d, fits = evaluate(raw)
    summary = report(d, fits)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        d.to_csv(args.output_dir / "predictions.csv", index=False)
        (args.output_dir / "results.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2, allow_nan=False))
    return summary


if __name__ == "__main__":
    main()
