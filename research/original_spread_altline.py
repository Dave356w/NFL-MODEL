"""Research-only: original implied spread as a hypothetical alternate-line wager.

No real alternate quotes are available. For each game, pick the side on which
model_spread differs from spread_line. Move that side's handicap from the
market line to the model line (optionally rounding to 0.5). Assume a fixed
*fair cover probability* decline of k per adverse point and preserve the
-110/-110 two-sided overround at every point (2*110/210 = 110/105).

Use 1u risked on each pick. The market-line comparator uses the identical
side and identical games at -110. Outcome pushes return 0 units. This is
exploratory exposed history, not an executable-price or forward test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

OVERROUND = 110 / 105
MARKET_PAYOUT = 100 / 110
EPS = 1e-9
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data/latest/retro_ledger.csv"


def grade_margin(signed_margin: np.ndarray, win_payout: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Graded W/L/P and flat-risk profit, with pushes refunded."""
    win = signed_margin > EPS
    lose = signed_margin < -EPS
    return (np.select([win, lose], ["W", "L"], default="P"),
            np.where(win, win_payout, np.where(lose, -1., 0.)))


def evaluate(frame: pd.DataFrame, points_per_point: float = .03,
             rounding: str = "half", max_gap: float = 7.) -> pd.DataFrame:
    """One paired market/alt observation for each eligible completed game."""
    if not 0 < points_per_point < .5:
        raise ValueError("points_per_point must be between 0 and 0.5")
    if rounding not in ("half", "exact"):
        raise ValueError("rounding must be half or exact")
    if max_gap <= 0:
        raise ValueError("max_gap must be positive")
    required = {"game_id", "season", "week", "result", "spread_line", "model_spread"}
    if not required.issubset(frame.columns):
        raise ValueError(f"missing columns: {sorted(required - set(frame.columns))}")
    d = frame.copy()
    for col in ["season", "week", "result", "spread_line", "model_spread"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["game_id", "season", "week", "result", "spread_line", "model_spread"])
    d = d.loc[np.isfinite(d[["result", "spread_line", "model_spread"]]).all(axis=1)].copy()
    if d.game_id.duplicated().any():
        raise ValueError("duplicate game_id observations; choose one model revision first")
    d["raw_gap"] = (d.model_spread - d.spread_line).abs()
    d = d.loc[d.raw_gap.gt(EPS) & d.raw_gap.le(max_gap)].copy()
    if d.empty:
        for col in ["alt_line", "point_shift", "alt_implied", "alt_win_profit",
                    "market_grade", "market_units", "alt_grade", "alt_units", "delta_units"]:
            d[col] = pd.Series(dtype="float64" if col not in ("market_grade", "alt_grade") else "object")
        return d

    side = np.sign(d.model_spread.to_numpy() - d.spread_line.to_numpy())
    model_line = d.model_spread.to_numpy()
    # Half-point handicaps; floor(x+0.5) mirrors half-up / JS Math.round.
    alt_line = np.floor(model_line * 2. + .5) / 2. if rounding == "half" else model_line
    shift = np.abs(alt_line - d.spread_line.to_numpy())
    fair_cover = np.clip(.5 - points_per_point * shift, .005, .995)
    quoted_implied = fair_cover * OVERROUND
    if (quoted_implied >= 1.).any():
        raise ValueError("implied probability >= 100%; invalid hypothetical quote")
    win_profit = 1. / quoted_implied - 1.
    m_grade, m_units = grade_margin(side * (d.result.to_numpy() - d.spread_line.to_numpy()),
                                   MARKET_PAYOUT)
    a_grade, a_units = grade_margin(side * (d.result.to_numpy() - alt_line), win_profit)

    d["alt_line"], d["point_shift"] = alt_line, shift
    d["alt_implied"], d["alt_win_profit"] = quoted_implied, win_profit
    d["market_grade"], d["market_units"] = m_grade, m_units
    d["alt_grade"], d["alt_units"] = a_grade, a_units
    d["delta_units"] = a_units - m_units
    return d


def summary(d: pd.DataFrame) -> dict:
    n = len(d)
    if n == 0:
        return {"bets": 0}
    output = {"bets": n, "seasons": int(d.season.nunique())}
    for prefix in ("market", "alt"):
        grade = d[f"{prefix}_grade"]
        units = d[f"{prefix}_units"]
        output[prefix] = dict(
            wins=int(grade.eq("W").sum()), losses=int(grade.eq("L").sum()),
            pushes=int(grade.eq("P").sum()), units=float(units.sum()),
            roi=float(units.mean()),
        )
    diff = d.delta_units
    mean = float(diff.mean())
    g = (diff - mean).groupby([d.season, d.week]).sum()
    count = len(g)
    se = float(np.sqrt((count / (count - 1)) * np.square(g).sum() / n**2)) if count > 1 else np.nan
    output["paired"] = {
        "delta_roi": mean, "clusters": count, "cluster_se": se,
        "ci95_normal": [mean - 1.96 * se, mean + 1.96 * se],
    }
    return output


def report(frame: pd.DataFrame, max_gap: float = 7.) -> dict:
    data = evaluate(frame, max_gap=max_gap)
    no_cap = evaluate(frame, max_gap=100.)
    sensitivity = {}
    for k in (.02, .025, .03, .035, .04):
        sensitivity[f"{k:.3f}"] = summary(evaluate(frame, k, max_gap=max_gap))
    return {
        "assumptions": {
            "fair_probability_drop_per_point": .03, "rounding": "half",
            "max_raw_model_market_gap": max_gap, "implied_probability_multiplier": OVERROUND,
            "market_price": -110, "stake": "1u risked on every eligible game",
            "quote_status": "hypothetical, never observed",
        },
        "primary": summary(data),
        "exact_line": summary(evaluate(frame, rounding="exact", max_gap=max_gap)),
        "by_season": {str(int(season)): summary(g) for season, g in data.groupby("season")},
        "sensitivity": sensitivity,
        "gaps_over_cap": int(len(no_cap) - len(data)),
        "uncapped_diagnostic_not_tradable": summary(no_cap),
        "half_lines_identical_to_market": int(data.point_shift.eq(0.).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--max-gap", type=float, default=7.)
    ap.add_argument("--export", type=Path, help="Optional game-level paired ledger CSV")
    args = ap.parse_args()
    source = pd.read_csv(args.input)
    output = report(source, max_gap=args.max_gap)
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        evaluate(source, max_gap=args.max_gap).to_csv(args.export, index=False)
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
