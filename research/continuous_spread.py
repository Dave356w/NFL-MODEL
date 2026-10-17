"""Prior-season continuous mean-margin calibration; research only.

Run: python -m research.continuous_spread
Design and decision rule: research/CONTINUOUS_SPREAD.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtri

from fixed_bands import grade

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("gap_anchor", "signal_anchor", "split_signal_anchor")
BASELINES = ("model_spread", "spread_line", "fixed_band_spread")
RIDGE = 200.0
SIGMA = 12.37
SEED = 20261017
DRAWS = 10_000
INPUT_COLUMNS = ["game_id", "season", "week", "home", "away", "result",
                 "spread_line", "model_wp", "market_ml_wp", "model_spread",
                 "fixed_band_spread"]


def implied(p):
    return SIGMA * ndtri(np.clip(np.asarray(p, float), .005, .995))


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """Use only forecast inputs; outcomes and fixed bands are never features."""
    d = frame.copy()
    for col in ("season", "week", "spread_line", "model_wp", "market_ml_wp"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    for col in ("model_wp", "market_ml_wp"):
        bad = d[col].notna() & (~np.isfinite(d[col]) | ~d[col].between(0, 1))
        if bad.any():
            raise ValueError(f"Invalid probability in {col}")
    if d.game_id.isna().any() or d.game_id.duplicated().any():
        raise ValueError("Missing or duplicate game IDs")
    if not np.isfinite(d[["season", "week"]]).all().all():
        raise ValueError("Missing season/week")
    if ((d[["season", "week"]] % 1) != 0).any().any():
        raise ValueError("Noninteger season/week")
    d["raw_spread"] = implied(d.model_wp)
    d["market_probability_spread"] = implied(d.market_ml_wp)
    d["gap"] = d.raw_spread - d.spread_line
    d["signal"] = d.raw_spread - d.market_probability_spread
    d["reinforcing"] = (d.market_ml_wp - .5) * d.signal > 0
    # Both split features must remain missing if an upstream input is missing.
    d["signal_reinforcing"] = d.signal.where(d.reinforcing, 0.).where(d.signal.notna())
    d["signal_other"] = d.signal.where(~d.reinforcing, 0.).where(d.signal.notna())
    return d


def fit_prior(history: pd.DataFrame, target_season: int) -> dict:
    """Fit three fixed candidates at the season boundary, never in-season."""
    d = features(history)
    if not (d.season < target_season).all():
        raise ValueError("Own/future season in spread calibration")
    d["result"] = pd.to_numeric(d.result, errors="coerce")
    cols = ["result", "spread_line", "raw_spread", "signal"]
    d = d.loc[np.isfinite(d[cols]).all(axis=1)]
    if len(d) < 300 or d.season.nunique() < 2:
        raise ValueError("Requires >=300 complete games and >=2 earlier seasons")
    residual = d.result.to_numpy() - d.spread_line.to_numpy()

    def slope(column):
        x = d[column].to_numpy(float)
        return float(np.clip(x @ residual / (x @ x + RIDGE), 0., 1.))

    return {"target_season": int(target_season),
            "training_max_season": int(d.season.max()), "training_games": len(d),
            "ridge": RIDGE, "sigma": SIGMA,
            "beta_gap": slope("gap"), "beta_signal": slope("signal"),
            "beta_reinforcing": slope("signal_reinforcing"),
            "beta_other": slope("signal_other")}


def predict(frame: pd.DataFrame, fitted: dict) -> pd.DataFrame:
    d = features(frame)
    if fitted["training_max_season"] >= fitted["target_season"]:
        raise ValueError("Calibration has own/future labels")
    if not (d.season == fitted["target_season"]).all():
        raise ValueError("Forecast season differs from calibration season")
    d["gap_anchor"] = d.spread_line + fitted["beta_gap"] * d.gap
    d["signal_anchor"] = d.spread_line + fitted["beta_signal"] * d.signal
    d["split_signal_anchor"] = (d.spread_line +
        fitted["beta_reinforcing"] * d.signal_reinforcing +
        fitted["beta_other"] * d.signal_other)
    valid = np.isfinite(d[["spread_line", "model_wp", "market_ml_wp"]]).all(axis=1)
    d.loc[~valid, list(ARMS)] = np.nan
    return d


def evaluate(history: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    d = features(history).sort_values(["season", "week", "game_id"])
    d["result"] = pd.to_numeric(d.result, errors="coerce")
    d["fixed_band_spread"] = pd.to_numeric(d.fixed_band_spread, errors="coerce")
    complete = np.isfinite(d[["result", "spread_line", "model_wp", "market_ml_wp"]]).all(axis=1)
    d = d.loc[complete]
    if not np.allclose(d.model_spread, d.raw_spread, atol=1e-10, rtol=0):
        raise ValueError("Saved raw spread differs from production probability conversion")
    scored, fits = [], []
    for year in sorted(int(y) for y in d.season.unique() if y >= 2023):
        fit = fit_prior(d[d.season < year], year)
        fits.append(fit)
        # The same complete baseline rows are scored for every method.
        test = d[(d.season == year) & d.fixed_band_spread.notna()]
        if len(test):
            scored.append(predict(test, fit))
    if not scored:
        raise ValueError("No matched evaluation games")
    return pd.concat(scored, ignore_index=True), fits


def point_scores(d: pd.DataFrame, arm: str) -> dict:
    error = d[arm].to_numpy(float) - d.result.to_numpy(float)
    return {"games": len(d), "mae": float(np.abs(error).mean()),
            "mse": float((error ** 2).mean()),
            "rmse": float(np.sqrt((error ** 2).mean())),
            "bias_prediction_minus_actual": float(error.mean())}


def ats_scores(d: pd.DataFrame, arm: str) -> dict:
    g, units = grade(d, d[arm])
    n = int(np.isin(g, ["W", "L", "P"]).sum())
    return {"opportunities": len(d), "bets": n, "wins": int((g == "W").sum()),
            "losses": int((g == "L").sum()), "pushes": int((g == "P").sum()),
            "skips": int((g == "S").sum()), "coverage": n / len(d),
            "units": float(np.sum(units)),
            "roi": float(np.sum(units) / n) if n else None,
            "units_per_opportunity": float(np.sum(units) / len(d))}


def paired_gains(d: pd.DataFrame, draws: int = DRAWS) -> list[dict]:
    """Season-stratified whole-week resampling; positive = lower candidate loss."""
    comparisons, delta = [], []
    for arm in ARMS:
        for baseline in BASELINES:
            for metric in ("mse", "mae"):
                a = np.abs(d[arm].to_numpy() - d.result.to_numpy())
                b = np.abs(d[baseline].to_numpy() - d.result.to_numpy())
                if metric == "mse":
                    a, b = a ** 2, b ** 2
                comparisons.append({"candidate": arm, "baseline": baseline, "metric": metric})
                delta.append(b - a)
    values = np.column_stack(delta)
    total, counts = np.zeros((draws, values.shape[1])), np.zeros(draws)
    rng = np.random.default_rng(SEED)
    blocks = 0
    for year in sorted(d.season.unique()):
        ix = np.flatnonzero(d.season.to_numpy() == year)
        weeks = d.week.to_numpy()[ix]
        unique = np.unique(weeks)
        sums = np.array([values[ix[weeks == w]].sum(axis=0) for w in unique])
        sizes = np.array([(weeks == w).sum() for w in unique])
        sampled = rng.integers(0, len(unique), size=(draws, len(unique)))
        total += sums[sampled].sum(axis=1)
        counts += sizes[sampled].sum(axis=1)
        blocks += len(unique)
    samples = total / counts[:, None]
    alpha = .05 / len(ARMS)
    for j, rec in enumerate(comparisons):
        rec.update(gain=float(values[:, j].mean()), games=len(d), blocks=blocks,
                   ci95=np.quantile(samples[:, j], [.025, .975]).tolist(),
                   ci_three_candidates=np.quantile(samples[:, j], [alpha / 2, 1-alpha / 2]).tolist())
    return comparisons


def summary(d: pd.DataFrame) -> dict:
    primary = d[d.season.between(2023, 2025)]
    if primary.empty:
        raise ValueError("Missing primary 2023-25 sample")
    comparisons = paired_gains(primary)
    nominees = []
    for arm in ARMS:
        tests = [r for r in comparisons if r["candidate"] == arm and
                 r["metric"] == "mse" and r["baseline"] in ("model_spread", "spread_line")]
        if len(tests) == 2 and all(r["ci_three_candidates"][0] > 0 for r in tests):
            nominees.append(arm)
    cohorts = {"primary_2023_2025": primary, "all_2023_onward": d,
               **{str(int(y)): g for y, g in d.groupby("season")}}
    arms = (*BASELINES, *ARMS)
    return {"status": "exposed historical development; assumed -110 ATS prices",
            "decision": "nominate_for_fresh_forward_test" if nominees else "retain_production_no_candidate_qualifies",
            "nominees": nominees, "primary_comparisons": comparisons,
            "cohorts": {name: {a: {**point_scores(g, a), "ats": ats_scores(g, a)}
                                 for a in arms} for name, g in cohorts.items()},
            "seed": SEED, "bootstrap_draws": DRAWS}


def run(source: Path, board_source: Path, output: Path) -> dict:
    output = output.resolve()
    for protected in (ROOT / "data", ROOT / "public"):
        if output == protected or protected in output.parents:
            raise ValueError("Protected output directory")
    frozen = output / "input.csv"
    # Output must never replace the caller's input, including on reruns.
    if source.resolve() == frozen or board_source.resolve() == output / "board_input.csv":
        raise ValueError("Input and output snapshots must differ")
    history = pd.read_csv(source, float_precision="round_trip")[INPUT_COLUMNS]
    board = pd.read_csv(board_source, float_precision="round_trip")
    if "market_ml_wp" not in board:
        board["market_ml_wp"] = board.market_wp
    board = board[["game_id", "season", "week", "home", "away", "spread_line",
                   "model_wp", "market_ml_wp"]]
    output.mkdir(parents=True, exist_ok=True)
    history.to_csv(frozen, index=False)
    board.to_csv(output / "board_input.csv", index=False)
    d, fits = evaluate(history)
    result = summary(d)
    current, board_fits = [], []
    for year, g in board.groupby("season"):
        fit = fit_prior(history[history.season < year], int(year))
        current.append(predict(g, fit))
        board_fits.append(fit)
    d.to_csv(output / "per_game.csv", index=False)
    pd.concat(current, ignore_index=True).to_csv(output / "current_counterfactuals.csv", index=False)
    (output / "fits.json").write_text(json.dumps({"historical": fits, "board": board_fits}, indent=2) + "\n")
    (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    sources = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):
               hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (source, board_source, Path(__file__), ROOT / "fixed_bands.py",
                         ROOT / "research/CONTINUOUS_SPREAD.md")}
    (output / "provenance.json").write_text(json.dumps({"sources": sources,
        "scope": "research only; no production or ledger writes",
        "latest_evaluation": [int(d.season.max()), int(d[d.season == d.season.max()].week.max())]}, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/latest/fixed_band_ledger.csv")
    parser.add_argument("--board", type=Path, default=ROOT / "data/latest/board.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "research/continuous_spread_results")
    args = parser.parse_args()
    result = run(args.input, args.board, args.output_dir)
    print(result["decision"])


if __name__ == "__main__":
    main()
