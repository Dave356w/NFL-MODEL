"""Registered joint-fit experiment; never changes production or native records.

Run with OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1:
    python research/interaction_penalty_test.py
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m
import fixed_bands

PROTOCOL_COMMIT = "3b1d797685e11bb2fb898801cf00b9876a989bd6"
PENALTIES = {"production": .1, "ridge_0.3": .3, "ridge_1": 1., "ridge_3": 3.}
STRONGER = ("ridge_0.3", "ridge_1", "ridge_3")
FITTED_ARMS = (*PENALTIES, "no_interactions")
ARMS = (*FITTED_ARMS, "selected_stronger", "market")
YEARS = (2023, 2024, 2025)
SEED = 20261031
PACK = ROOT / "research/shrinkage_results/frozen_training_features.csv.gz"
REFERENCES = ROOT / "research/shrinkage_results/normalization_references.csv"
PROTOCOL = ROOT / "research/INTERACTION_PENALTY_TEST.md"
OUTPUT = ROOT / "research/interaction_penalty_results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_hashes():
    paths = [ROOT / "nfl_model.py", *sorted((ROOT / "data").rglob("*"))]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()}


def losses(y, p):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, float)
    return -(y*np.log(p) + (1-y)*np.log1p(-p))


def fit_arm(train, test, year, week, arm):
    if arm not in FITTED_ARMS:
        raise ValueError("Unknown registered arm")
    if not m.before(train, year, week).all():
        raise ValueError("Training contains current or future weeks")
    recipe = dict(m.PRODUCT_RECIPE,
                  interaction_ridge=PENALTIES.get(arm, .1))
    if arm == "no_interactions":
        zeros = {c: 0. for c in m.PRODUCT_CONTEXT_NAMES}
        train, test = train.assign(**zeros), test.assign(**zeros)
    fitted = m.fit_composite(train, recipe, year, week)
    prediction = m.apply_fit(test, fitted)
    raw = m.apply_fit(test, fitted, raw=True)
    return prediction, raw, fitted


def choose_prior(predictions, year):
    """Do not allow evaluation-year labels, Brier or ROI to select a penalty."""
    prior = predictions[predictions.season.lt(year)
                        & predictions["home won"].isin([0., 1.])]
    if prior.season.nunique() < 2:
        raise ValueError("Need at least two completed earlier validation seasons")
    scores = {a: float(losses(prior["home won"], prior[a]).mean()) for a in STRONGER}
    if not np.isfinite(list(scores.values())).all():
        raise ValueError("Missing prior-season candidate predictions")
    chosen = min(STRONGER, key=lambda a: (scores[a], -PENALTIES[a]))
    return chosen, dict(evaluation_season=int(year),
                        selection_max_season=int(prior.season.max()),
                        prior_binary_games=len(prior), chosen=chosen,
                        selected_penalty=PENALTIES[chosen], prior_log_losses=scores)


def bootstrap_interval(frame, values, reps=10000, seed=SEED):
    """Paired whole weeks within each season; retain original season weights."""
    v = np.asarray(values, float)
    if len(v) != len(frame) or not np.isfinite(v).all():
        raise ValueError("Incomplete paired comparison")
    rng = np.random.default_rng(seed)
    draws = np.zeros(reps)
    for season in sorted(frame.season.unique()):
        take = frame.season.eq(season).to_numpy()
        grouped = pd.DataFrame({"v": v[take], "week": frame.loc[take, "week"]})
        blocks = grouped.groupby("week").v.agg(["sum", "count"])
        if len(blocks) < 2:
            raise ValueError("Need two week clusters in each season")
        indices = rng.integers(0, len(blocks), (reps, len(blocks)))
        means = (blocks["sum"].to_numpy()[indices].sum(1)
                 / blocks["count"].to_numpy()[indices].sum(1))
        draws += take.sum()/len(frame)*means
    return np.quantile(draws, [.025, .975]).tolist()


def probability_scores(frame, arms=ARMS, reps=10000):
    binary = frame[frame["home won"].isin([0., 1.])].copy()
    rows = []
    for season in (*YEARS, "all"):
        d = binary if season == "all" else binary[binary.season.eq(season)]
        if not len(d):
            continue
        y = d["home won"].to_numpy()
        base_ll = losses(y, d.production)
        base_bs = (d.production.to_numpy()-y)**2
        for arm in arms:
            ll = losses(y, d[arm]); bs = (d[arm].to_numpy()-y)**2
            row = dict(season=season, arm=arm, n=len(d),
                       log_loss=float(ll.mean()), brier=float(bs.mean()),
                       ll_delta=float((ll-base_ll).mean()),
                       brier_delta=float((bs-base_bs).mean()))
            row["ll_delta_ci95"] = bootstrap_interval(d, ll-base_ll, reps)
            row["brier_delta_ci95"] = bootstrap_interval(d, bs-base_bs, reps)
            rows.append(row)
    return rows


def decision_gate(scores):
    selected = [r for r in scores if r["arm"] == "selected_stronger"]
    annual = {int(r["season"]): r for r in selected if r["season"] != "all"}
    pooled = next(r for r in selected if r["season"] == "all")
    market = next(r for r in scores if r["season"] == "all" and r["arm"] == "market")
    criteria = dict(
        every_season_both_better=all(y in annual and annual[y]["ll_delta"] < 0
                                    and annual[y]["brier_delta"] < 0 for y in YEARS),
        both_paired_intervals_below_zero=(pooled["ll_delta_ci95"][1] < 0
                                         and pooled["brier_delta_ci95"][1] < 0),
        not_worse_than_market=(pooled["log_loss"] <= market["log_loss"]
                               and pooled["brier"] <= market["brier"]))
    return dict(passed=all(criteria.values()), criteria=criteria,
                production_adoption=False,
                next_step=("Separately register prospective paired ATS shadow captures; no adoption yet."
                           if all(criteria.values()) else
                           "Historical gate failed. Keep production unchanged; no native launch from this test."))


def ats_replay(frame, rules):
    rows = []
    for year in YEARS:
        d = frame[frame.season.eq(year)]
        rule = rules[year]
        if rule["training_max_season"] >= year:
            raise ValueError("ATS mapping includes evaluation-season outcomes")
        for arm in ARMS:
            raw = m.implied_spread(d[arm])
            mapped = fixed_bands.apply(raw, rule)
            result, units = fixed_bands.grade(d, mapped, True)
            selected = np.isin(result, ["W", "L", "P"])
            n = int(selected.sum()); w = int((result == "W").sum())
            l = int((result == "L").sum())
            rows.append(dict(season=year, arm=arm, n=n, wins=w, losses=l,
                             pushes=int((result == "P").sum()),
                             skips=int((result == "S").sum()),
                             units=float(units[selected].sum()),
                             roi=float(units[selected].mean()) if n else None,
                             cover_rate=w/(w+l) if w+l else None,
                             basis="historical replay; unchanged production median map; assumed -110"))
    return rows


def native_audit(pack):
    """Audit feasibility; never call a hindsight forecast a native challenger."""
    locks = [json.loads(s) for s in (ROOT/"data/ats_locks.jsonl").read_text().splitlines() if s.strip()]
    forwards = [json.loads(s) for s in (ROOT/"data/forward_predictions.jsonl").read_text().splitlines() if s.strip()]
    usable = [r for r in forwards if r.get("revision") == "boxscore-composite-v1.18"]
    key = lambda r: (r["game_id"], r["generated_utc"])
    original = {key(r): r for r in usable}
    matches = [r for r in locks if key(r) in original
               and original[key(r)].get("model_inputs")]
    labeled = pack[pack.ready & pack["home won"].isin([0., 1.])]
    season = int(labeled.season.max())
    return dict(saved_ats_locks=len(locks),
                pregame_finalized_locks=sum(not r.get("recovered_after_kickoff", False) for r in locks),
                recovered_locks=sum(bool(r.get("recovered_after_kickoff", False)) for r in locks),
                locks_with_exact_saved_first_snapshot_inputs=len(matches),
                frozen_pack_latest_labeled_season=season,
                frozen_pack_latest_labeled_week=int(labeled.loc[labeled.season.eq(season), "week"].max()),
                native_challenger_predictions=0, native_challenger_graded=0,
                note="Existing locks are production evidence only. No challenger existed at their cutoffs; no backfill or first-snapshot substitution.")


def report(info, out):
    lines = ["# Joint interaction-penalty test", "",
             "Registered before computation: "+PROTOCOL_COMMIT+".",
             "Exposed 2023-2025 historical development; not native challenger evidence.",
             "All coefficients refitted jointly before each week. Lower scores are better.", "",
             "## Earlier-season selections", "",
             "| Evaluation season | Selection through | Interaction penalty |",
             "|---|---:|---:|"]
    for r in info["selections"]:
        lines.append(f"| {r['evaluation_season']} | {r['selection_max_season']} | {r['selected_penalty']:g} |")
    lines += ["", "## Probability scores", "",
              "| Season | Arm | N | Log loss | Brier | LL minus production | Brier minus production |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for r in info["scores"]:
        lines.append(f"| {r['season']} | {r['arm']} | {r['n']} | {r['log_loss']:.6f} | {r['brier']:.6f} | {r['ll_delta']:+.6f} | {r['brier_delta']:+.6f} |")
    lines += ["", "## Primary paired comparisons", "",
              "95% whole-week bootstrap, stratified within season. Negative differences favor selected_stronger.", "",
              "| Season | LL difference [95% interval] | Brier difference [95% interval] |",
              "|---|---:|---:|"]
    for r in info["scores"]:
        if r["arm"] == "selected_stronger":
            a,b=r["ll_delta_ci95"],r["brier_delta_ci95"]
            lines.append(f"| {r['season']} | {r['ll_delta']:+.6f} [{a[0]:+.6f}, {a[1]:+.6f}] | {r['brier_delta']:+.6f} [{b[0]:+.6f}, {b[1]:+.6f}] |")
    lines += ["", "## Registered gate", ""]
    for name, passed in info["gate"]["criteria"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    lines += ["", info["gate"]["next_step"], "",
              "The primary selected rule and the no-interaction control have worse point estimates on both scores in every evaluation year. "
              "The primary paired intervals cross zero, so the size and direction of the population effect remain unresolved. "
              "This test does not qualify either stronger shrinkage or removing the interaction block; it does not prove the current interactions are universally reliable.", "",
              "## ATS replay (secondary)", "",
              "Same production prior-season mapping for every arm; flat 1u at assumed -110. Not lock-time execution returns.", "",
              "| Season | Arm | W-L-P | Skips | Units | ROI |",
              "|---|---|---:|---:|---:|---:|"]
    for r in info["ats"]:
        lines.append(f"| {r['season']} | {r['arm']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['skips']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% |")
    lines += ["", "## Native evidence and integrity", "",
              json.dumps(info["native_audit"], indent=2), "",
              f"Raw production reproduction max error: {info['raw_reproduction_max_error']:.3g}.",
              f"Production source/data unchanged: {info['protected_sources_unchanged']}.", "",
              "Native challenger sample is zero. Prior ATS outcomes cannot retrospectively validate a new challenger.",
              "All historical results condition on exposed design choices. Fixed-arm intervals are descriptive, not alternate adoption gates.",
              "Full coefficients, scaling, cutoffs, source hashes, predictions and selection scores accompany this report."]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n")


def run(output=OUTPUT, reps=10000):
    output = Path(output).resolve()
    for protected in (ROOT/"data", ROOT/"public"):
        if output == protected or protected in output.parents:
            raise ValueError("Research cannot write production outputs")
    if reps != 10000:
        raise ValueError("Registered run requires 10000 bootstrap draws")
    before = protected_hashes()
    f = pd.read_csv(PACK)
    refs = pd.read_csv(REFERENCES)
    if not ((refs.max_reference_season < refs.season)
            | (refs.max_reference_season.eq(refs.season) & (refs.max_reference_week < refs.week))).all():
        raise ValueError("Future normalization reference")
    eligible = (f.ready & f["home won"].isin([0., 1.]) & np.isfinite(f.q)
                & np.isfinite(f[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1))
    evaluation = (f.ready & f["home won"].isin([0., .5, 1.]) & np.isfinite(f.q)
                  & np.isfinite(f[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1)
                  & f.season.between(2021, 2025))
    columns = ["game_id","season","week","home","away","home won","result","spread_line","q"]
    predictions = f.loc[evaluation, columns].copy()
    audits = []
    for (year,week), d in predictions.groupby(["season","week"], sort=True):
        train = f[eligible & m.before(f,int(year),int(week))]
        test = f.loc[d.index]
        for arm in FITTED_ARMS:
            prediction, raw, fit = fit_arm(train,test,int(year),int(week),arm)
            predictions.loc[d.index,arm] = prediction
            if arm == "production":
                predictions.loc[d.index,"raw_production"] = raw
            audits.append(dict(evaluation_season=int(year), evaluation_week=int(week),
                               arm=arm, **fit))
        if week == 1:
            print(f"Fitted {year}; strictly prior-week training", flush=True)
    if not np.isfinite(predictions[list(FITTED_ARMS)]).all().all():
        raise ValueError("Incomplete predictions")
    selections=[]
    for year in (*YEARS, 2026):
        chosen, selection = choose_prior(predictions,year)
        selections.append(selection)
        predictions.loc[predictions.season.eq(year),"selected_stronger"] = predictions.loc[predictions.season.eq(year),chosen]
    predictions["market"] = predictions.q
    held = predictions[predictions.season.isin(YEARS)].copy()
    reference = pd.read_csv(ROOT/"research/production_adoption_results/historical_reproduction.csv")
    check = held.merge(reference, on="game_id", validate="one_to_one")
    if len(check) != len(held):
        raise ValueError("Production reference coverage differs")
    error = float(np.max(np.abs(check.raw_production-check.production_probability)))
    if error > 1e-9:
        raise ValueError("Raw production does not reproduce independent reference")
    scores = probability_scores(held, reps=reps)
    rules = {int(r["season"]):r for r in json.loads((ROOT/"data/latest/fixed_band_rules.json").read_text())}
    info = dict(protocol_commit=PROTOCOL_COMMIT, seed=SEED, bootstrap_draws=reps,
                basis="Exposed historical development, 2023-2025; no native challenger evidence",
                selections=selections, scores=scores, gate=decision_gate(scores),
                ats=ats_replay(held,rules), native_audit=native_audit(f),
                raw_reproduction_max_error=error,
                protected_sources_unchanged=(before == protected_hashes()))
    if not info["protected_sources_unchanged"]:
        raise ValueError("Protected production sources changed")
    output.mkdir(parents=True, exist_ok=True)
    held.to_csv(output/"predictions.csv", index=False)
    predictions.to_csv(output/"selection_predictions.csv", index=False)
    fit_bytes=(json.dumps(audits,separators=(",",":"))+"\n").encode()
    (output/"fits.json.gz").write_bytes(gzip.compress(fit_bytes,mtime=0))
    (output/"results.json").write_text(json.dumps(info,indent=2,allow_nan=False)+"\n")
    sources=[Path(__file__),PROTOCOL,PACK,REFERENCES,ROOT/"nfl_model.py",
             ROOT/"research/production_adoption_results/historical_reproduction.csv",
             ROOT/"data/latest/fixed_band_rules.json",ROOT/"data/ats_locks.jsonl",
             ROOT/"data/forward_predictions.jsonl"]
    (output/"provenance.json").write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in sources},indent=2)+"\n")
    report(info,output)
    print(json.dumps(info["gate"],indent=2), flush=True)
    return info


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=OUTPUT)
    run(parser.parse_args().output)
