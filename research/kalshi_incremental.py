"""Incremental Kalshi 2026 pricing history refresh; never reprice old games.

Runs after completed games are added to data/latest/retro_ledger.csv.
Retrieves only IDs absent from the verified Kalshi archive. Earlier records
retain their original historical cutoff and ticker; no current quotes backfill.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
import pandas as pd

from research import kalshi_ats_prices as quotes
from research import kalshi_backfill as merge


def new_games(retro: pd.DataFrame, previous: pd.DataFrame,
              schedules: pd.DataFrame) -> pd.DataFrame:
    """Eligible missing completed games, with strictly schedule-derived kickoff."""
    d=retro[(retro.season>=2025)&retro["home won"].notna()].copy()
    d=d[~d.game_id.isin(previous.game_id)]
    if d.empty:
        return d
    required={"game_id","gameday","gametime"}
    if not required.issubset(schedules):
        raise ValueError("nflverse schedule missing kickoff fields")
    import nfl_model as m
    times=schedules[["game_id","gameday","gametime"]].drop_duplicates("game_id").copy()
    if times.game_id.duplicated().any():
        raise ValueError("duplicate schedule game IDs")
    times["kickoff_utc"]=[m.kickoff_utc(r).isoformat() if m.kickoff_utc(r)
                          else None for r in times.to_dict("records")]
    d=d[["game_id","season","week","home","away","spread_line","model_spread"]]
    d=d.merge(times[["game_id","kickoff_utc"]],on="game_id",how="left",validate="one_to_one")
    if d.kickoff_utc.isna().any():
        raise ValueError("completed NFL game has no scheduled kickoff")
    return d.sort_values("game_id")


def sync(data=Path("data"), *, get=quotes.kalshi.fetch) -> dict:
    data=Path(data)
    out=data/"kalshi_historical"
    archive=out/"kalshi_quotes.csv"
    if not archive.exists():
        raise FileNotFoundError("initial Kalshi archive is required")
    old=pd.read_csv(archive)
    retro=pd.read_csv(data/"latest"/"retro_ledger.csv")
    current=int(retro.season.max())
    if current < 2025:
        raise ValueError("cannot backfill Kalshi NFL spreads before 2025")
    missing=retro[(retro.season>=2025)&retro["home won"].notna()&
                  ~retro.game_id.isin(old.game_id)]
    if missing.empty:
        return {"new_games":0,"action":"no_change"}
    import nfl_model as m
    schedules=m.load_schedule(current)
    todo=new_games(retro,old,schedules)
    records=quotes.historical_quotes(todo.to_dict("records"),get=get,max_games=0)
    if len(records)!=len(todo):
        raise ValueError("not all new games received a coverage status")
    from research import ats_cover_probability as cp
    ats,_=cp.evaluate(pd.read_csv(data/"latest"/"fixed_band_ledger.csv"))
    # Filter old merged archive back to its actual quote columns.
    discard={"home_quote","away_quote","season","week","home","away",
             "missing_reason"}
    original=old.drop(columns=[c for c in discard if c in old])
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        original.to_csv(root/"kalshi_quotes_existing.csv",index=False)
        pd.DataFrame(records).to_csv(root/"kalshi_quotes_new.csv",index=False)
        ats.to_csv(root/"ats_predictions.csv",index=False)
        summary=merge.assemble([root/"kalshi_quotes_existing.csv",
                                root/"kalshi_quotes_new.csv"],
                               data/"latest"/"retro_ledger.csv",
                               root/"ats_predictions.csv",out)
    return {"new_games":len(records),"action":"refreshed","summary":summary}


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--data",type=Path,default=Path("data"))
    args=a.parse_args()
    print(json.dumps(sync(args.data),indent=2,allow_nan=False))


if __name__=="__main__":
    main()
