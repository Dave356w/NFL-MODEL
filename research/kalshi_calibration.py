"""Is Kalshi a usable market benchmark? Research only: reads Kalshi's public API and
nflverse, writes nothing under data/.

For every regular-season and playoff game with a Kalshi game-winner market (Kalshi
lists NFL games from 2025), take the home team's mid price (best bid/ask) from the
last hourly candle ending at least `--hours` before kickoff, then score it beside the
sportsbook moneyline (margin removed), the spread-derived probability and, when an
outer_chronological_predictions.csv from a model run is given, the model's held-out
probability. Same rows for every comparison; ties excluded.

    python research/kalshi_calibration.py [--outer RUN_DIR/outer_chronological_predictions.csv]
                                          [--hours 1] [--out kalshi_game_prices.csv]
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, ndtr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kalshi as k  # noqa: E402
import nfl_model as m  # noqa: E402

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ET = ZoneInfo("America/New_York")


def all_events(get=k.fetch):
    out, cur = [], ""
    while True:
        d = get(f"/events?series_ticker={k.GAME_SERIES}&limit=200" + (f"&cursor={cur}" if cur else ""))
        out += d.get("events", [])
        cur = d.get("cursor") or ""
        if not cur or not d.get("events"):
            return out


def mid_before(candles, end_ts):
    """Mid of the last candle ending at or before end_ts (None if the book was empty)."""
    c = [x for x in candles if x["end_period_ts"] <= end_ts]
    if not c:
        return np.nan
    x = c[-1]
    f = lambda d: float(d.get("close") or d.get("close_dollars") or "nan")  # noqa: E731
    b, a = f(x["yes_bid"]), f(x["yes_ask"])
    return (a + b) / 2 if np.isfinite(a + b) and a > b else np.nan


def pull(hours=1., get=k.fetch):
    g = pd.read_csv(GAMES_URL)
    g = g[(g.season >= 2025) & g.result.notna() & (g.game_type != "PRE")]
    rows = []
    events = all_events(get)
    for r in g.itertuples():
        ko = dt.datetime.strptime(f"{r.gameday} {r.gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(dt.timezone.utc)
        tk = k.match_event(events, r.away_team, r.home_team, ko.isoformat())
        if not tk:
            continue
        hist = ko < dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)
        base = "/historical/markets" if hist else "/markets"
        mk = get(f"{base}?event_ticker={tk}").get("markets", []) or get(f"/historical/markets?event_ticker={tk}").get("markets", [])
        home = [x for x in mk if k.team(x["ticker"].rsplit("-", 1)[-1]) == r.home_team]
        if not home:
            continue
        t, end = home[0]["ticker"], int(ko.timestamp())
        q = f"?start_ts={end - 30 * 3600}&end_ts={end}&period_interval=60"
        try:
            cs = get(f"/series/{k.GAME_SERIES}/markets/{t}/candlesticks{q}").get("candlesticks", [])
        except Exception:  # noqa: BLE001 - settled markets move to the historical endpoint
            cs = get(f"/historical/markets/{t}/candlesticks{q}").get("candlesticks", [])
        rows.append({"game_id": r.game_id, "season": r.season, "kalshi_ticker": t,
                     "kalshi_wp": mid_before(cs, end - hours * 3600), "result": r.result,
                     "home_moneyline": r.home_moneyline, "away_moneyline": r.away_moneyline, "spread_line": r.spread_line})
    return pd.DataFrame(rows)


def ll(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calibration(y, p):
    """Logistic recalibration y ~ a + b * logit(p): (a, b) and their standard errors; (0, 1) is calibrated."""
    x = logit(np.clip(p, 1e-4, 1 - 1e-4))
    r = minimize(lambda t: ll(y, expit(t[0] + t[1] * x)).sum(), [0., 1.])
    return r.x, np.sqrt(np.diag(r.hess_inv))


def score(df, rng=None):
    rng = rng or np.random.default_rng(m.SEED)
    d = df[df.kalshi_wp.notna() & (df.result != 0)].copy()
    d["y"] = (d.result > 0).astype(float)
    d["book_ml"] = m.market_ml_wp(d)
    d["book_spread"] = ndtr(d.spread_line / m.MARKET_SIGMA)
    cols = [c for c in ("kalshi_wp", "book_ml", "book_spread", "model_wp") if c in d]
    d = d.dropna(subset=cols)
    rows = []
    for c in cols:
        (a, b), (sa, sb) = calibration(d.y.to_numpy(), d[c].to_numpy())
        diff = ll(d.y, d[c]) - ll(d.y, d.kalshi_wp)
        boot = [diff.to_numpy()[rng.integers(0, len(d), len(d))].mean() for _ in range(m.BOOTSTRAP_REPS)]
        rows.append({"source": c, "games": len(d), "log loss": ll(d.y, d[c]).mean(), "brier": ((d[c] - d.y) ** 2).mean(),
                     "cal intercept": a, "cal slope": b, "slope se": sb,
                     "LL vs kalshi": diff.mean(), "ci low": np.quantile(boot, .025), "ci high": np.quantile(boot, .975)})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outer", help="outer_chronological_predictions.csv from a model run (adds the model)")
    ap.add_argument("--hours", type=float, default=1.)
    ap.add_argument("--out", default="kalshi_game_prices.csv")
    args = ap.parse_args(argv)
    df = pull(args.hours)
    df.to_csv(args.out, index=False)
    if args.outer:
        df = df.merge(pd.read_csv(args.outer)[["game_id", "model_wp"]], on="game_id", how="left")
    pd.set_option("display.width", 200)
    print(f"{df.kalshi_wp.notna().sum()} games with a Kalshi price {args.hours:g}h before kickoff")
    print(score(df).round(4).to_string(index=False))
    print("Positive 'LL vs kalshi' means the source scored worse than Kalshi on the same games.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
