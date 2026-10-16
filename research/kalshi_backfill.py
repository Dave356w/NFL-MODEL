"""Merge Kalshi week archives and report exclusively Kalshi-priced NFL picks.

No sportsbook prices used for this grade; pre-2025 observations appear only in
coverage (unsupported). Historical model predictions remain reconstructed.
"""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from research import kalshi_ats_prices as kalshi

CORE = ["game_id","season","week","home","away","cutoff_utc","kickoff_utc",
        "kalshi_main_status","alternate_status","status","price_basis"]
QCOLS = CORE + ["winner_home_ask","winner_away_ask",
                "kalshi_spread_line","kalshi_home_ask","kalshi_away_ask",
                "kalshi_strike","kalshi_ticker","kalshi_source_ts",
                "alt_selection_side","alt_contract","alt_ask",
                "alt_target_strike","alt_quote_ts"]


def assemble(partitions: list[Path], retro_path: Path, ats_path: Path,
             output_dir: Path) -> dict:
    frames=[]
    for path in sorted(partitions):
        try:
            d=pd.read_csv(path)
        except pd.errors.EmptyDataError:
            continue
        if "game_id" not in d: raise ValueError(f"{path}: missing game_id")
        if len(d): frames.append(d)
    if not frames: raise ValueError("no archived Kalshi rows available")
    quotes=pd.concat(frames,ignore_index=True).sort_values(["game_id","cutoff_utc"])
    if quotes.game_id.duplicated().any():
        raise ValueError("duplicate Kalshi game_id across batch partitions")
    retro=pd.read_csv(retro_path)
    retro=retro[retro.season.ge(2025) & retro["home won"].notna()].copy()
    expected=retro[["game_id","season","week","home","away"]].drop_duplicates()
    if retro.game_id.duplicated().any():
        raise ValueError("duplicate reconstructed model games")
    # Include every graded game, even if Kalshi market does not exist.
    allq=expected.merge(quotes,how="left",on="game_id",validate="one_to_one",
                        suffixes=("","_quote"))
    for col in ("status","kalshi_main_status","alternate_status"):
        if col not in allq: allq[col] = "no_capture"
        allq[col] = allq[col].fillna("no_capture")
    for col in QCOLS:
        if col not in allq: allq[col] = np.nan
    allq["missing_reason"] = np.where(allq.kalshi_main_status=="quoted","",
                                     allq.kalshi_main_status)
    ml=kalshi.joined_kalshi_moneyline(retro,quotes.to_dict("records"))
    ats=pd.read_csv(ats_path)
    ats=ats[ats.season>=2025]
    ats_grades=kalshi.joined_ats_results(ats,quotes.to_dict("records"))
    report={"price_source":"Kalshi public historical candlestick bid/ask, completed minute only",
            "cutoff":"two hours before scheduled kickoff, 30-minute max staleness",
            "fee":"approximate 7% * price * (1-price); no slippage/depth",
            "note":"2025+ hindsight model picks; not native forward prices",
            "eligible_graded_games":len(expected),"captured_games":len(quotes),
            "winner_quote_pairs":int(allq.winner_home_ask.notna().mul(allq.winner_away_ask.notna()).sum()),
            "kalshi_main_spread":int(allq.kalshi_main_status.eq("quoted").sum()),
            "model_target_alt_spread":int(allq.alternate_status.eq("quoted").sum()),
            "year_breakdown":{},"outcomes":{}}
    for year,group in allq.groupby("season"):
        report["year_breakdown"][str(int(year))]={
            "graded":len(group),
            "winner_pairs":int(group.winner_home_ask.notna().mul(group.winner_away_ask.notna()).sum()),
            "main_spread_quotes":int(group.kalshi_main_status.eq("quoted").sum()),
            "model_alt_quotes":int(group.alternate_status.eq("quoted").sum()),
            "missing_reasons":group.kalshi_main_status.value_counts(dropna=False).to_dict()}
    def stat(series):
        v=pd.to_numeric(series,errors="coerce").dropna()
        return {"bets":len(v),"units":float(v.sum()),"roi_per_risked_unit":float(v.mean()) if len(v) else None}
    report["outcomes"]["model_moneyline"]=stat(ml.kalshi_ml_units)
    for arm in ("original","fixed_band","original_model_alt"):
        name = "original_model_alt_kalshi_units" if arm=="original_model_alt" else arm+"_kalshi_units"
        report["outcomes"][arm+"_ats"]=stat(ats_grades[name] if name in ats_grades else pd.Series(dtype=float))
    output_dir.mkdir(parents=True,exist_ok=True)
    allq.to_csv(output_dir/"kalshi_quotes.csv",index=False,float_format="%.6g")
    ml.to_csv(output_dir/"kalshi_moneyline_graded.csv",index=False,float_format="%.6g")
    ats_grades.to_csv(output_dir/"kalshi_ats_graded.csv",index=False,float_format="%.6g")
    (output_dir/"kalshi_summary.json").write_text(json.dumps(report,indent=2,allow_nan=False,default=int)+"\n")
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partition-dir",type=Path,required=True)
    ap.add_argument("--retro",type=Path,default=Path("data/latest/retro_ledger.csv"))
    ap.add_argument("--ats",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=Path("data/kalshi_historical"))
    args=ap.parse_args()
    files=list(args.partition_dir.rglob("*.csv"))
    files=[p for p in files if p.name.startswith("kalshi_quotes_")]
    print(json.dumps(assemble(files,args.retro,args.ats,args.out),indent=2))


if __name__=="__main__":
    main()
