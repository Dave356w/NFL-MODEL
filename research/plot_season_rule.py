"""Plot saved every-season retest results; never fit or select a production model.

The fixed comparison rows below are declared before the retest has completed.
Two explicitly descriptive rows show the nearest observed raw-path misses using
the documented deterministic rankings. They are not prospective selections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import textwrap

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "nfl-season-rule-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd


RESULTS = Path(__file__).resolve().parent / "season_rule_retest_results"
YEARS = tuple(range(2021, 2027))
DEF_QB = (
    "pair:d__allowed__rates_core__net_pass_yards_per_pass_play|"
    "d__avail__qb_delta"
)
FIXED_ROWS = (
    ("market:moneyline", "raw", "Market moneyline anchor"),
    ("market:spread_total", "raw", "Market spread/total anchor"),
    ("incumbent:v118", "own_median", "v1.18 recipe · own median"),
    ("spread_total::full29::g1", "raw", "Held v1.19 · full 29 · raw"),
    ("spread_total::full29::g1", "own_median", "Full 29 · g1 · own median"),
    ("spread_total::full29::g1", "shared_median", "Full 29 · g1 · shared median"),
    ("spread_total::full29::g0.1", "raw", "Full 29 · g0.10 · raw"),
    (f"spread_total::{DEF_QB}::g0.25", "raw", "Defense + QB · g0.25 · raw"),
)
NEAREST_RULES = {
    "probability": [
        "probability_passing_seasons", "worst_log_loss_gain_vs_both",
        "worst_brier_gain_vs_both",
    ],
    "ats": [
        "ats_passing_seasons", "worst_roi", "worst_roi_gain_own",
        "worst_roi_gain_favorite",
    ],
}
PANELS = (
    ("log_loss_gain", "Winner log-loss gain", "vs both market probability anchors · ×1,000", ".2f"),
    ("brier_gain", "Winner Brier-score gain", "vs both market probability anchors · ×1,000", ".2f"),
    ("roi_pct", "ATS ROI", "flat 1u at assumed −110 · %", ".1f"),
    ("roi_control_gain_pp", "ATS ROI gain vs controls", "vs own-anchor/same-map AND market favorite · pp", ".1f"),
)


def _bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    mapped = series.astype(str).str.lower().map({"true": True, "false": False})
    if mapped.isna().any():
        raise ValueError(f"Unrecognized Boolean in {series.name}")
    return mapped.astype(bool)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_label(row: pd.Series) -> str:
    features = {
        "full29": "full 29",
        "d__allowed__rates_core__net_pass_yards_per_pass_play": "allowed pass efficiency",
        "d__avail__qb_delta": "QB availability",
        "d__allowed__rates_core__first_down_rate": "allowed first-down rate",
        "d__allowed__rates_core__penalty_yards_per_game": "opponent penalties",
        "pass_product": "passing product",
        "d__avail__DB_out_cs": "DB absences",
        "site": "location",
    }

    def pretty(value: str) -> str:
        if value in features:
            return features[value]
        return (value.replace("d__allowed__rates_core__", "allowed ")
                .replace("d__for__rates_core__", "offensive ")
                .replace("d__avail__", "availability ").replace("d__", "")
                .replace("_", " "))

    candidate = str(row.candidate)
    if candidate.startswith("single:"):
        candidate = pretty(candidate.removeprefix("single:"))
    elif candidate.startswith("pair:"):
        candidate = " + ".join(pretty(x) for x in candidate.removeprefix("pair:").split("|"))
    else:
        candidate = pretty(candidate)
    anchor = "S/T" if row.anchor == "spread_total" else "ML"
    return f"{anchor} · {candidate} · g{row.gamma:g} · raw"


def select_rows(gates: pd.DataFrame) -> list[dict]:
    """Keep the declared rows and append at most two labeled post-hoc misses."""
    gates = gates.copy()
    gates["is_control"] = _bool(gates.is_control)
    rows = [dict(variant_id=identity, path=path, label=label, role="fixed")
            for identity, path, label in FIXED_ROWS]
    pool = gates.loc[~gates.is_control & gates.path.eq("raw") & gates.covered_seasons.eq(6)]
    if pool.empty:
        raise ValueError("No complete raw-path candidate family for descriptive rankings")
    seen = {(r["variant_id"], r["path"]) for r in rows}
    for kind, columns in NEAREST_RULES.items():
        # Stable lexical last tie break prevents output ordering from determining
        # a descriptive winner. A sign-count ranking is not a significance test.
        leader = pool.sort_values(columns + ["variant_id"],
                                  ascending=[False] * len(columns) + [True],
                                  kind="stable").iloc[0]
        count = int(leader["probability_passing_seasons" if kind == "probability" else "ats_passing_seasons"])
        identity = (leader.variant_id, "raw")
        title = "ATS" if kind == "ats" else kind
        status = "nearest miss" if count < 6 else "leader"
        description = f"Post-hoc {title} {status} ({count}/6)"
        if identity in seen:
            existing = next(r for r in rows if (r["variant_id"], r["path"]) == identity)
            existing["label"] += f"\n{description}"
            existing["descriptive_rank"] = existing.get("descriptive_rank", []) + [kind]
        else:
            rows.append(dict(variant_id=leader.variant_id, path="raw", role="posthoc",
                             label=description + "\n" + _candidate_label(leader),
                             descriptive_rank=[kind]))
            seen.add(identity)
    # Show a unique secondary-window ATS-only survivor when there is one. Its
    # missing early years and all-six-year probability failures remain visible.
    if "pass_2023_2026_ats" in gates:
        secondary = gates.loc[~gates.is_control & gates.path.ne("raw") &
                              _bool(gates.pass_2023_2026_ats) &
                              ~_bool(gates.all_seasons_ats_pass)]
        if len(secondary) == 1:
            leader = secondary.iloc[0]
            if (leader.variant_id, leader.path) not in seen:
                label = _candidate_label(leader).removesuffix(" · raw")
                rows.append(dict(variant_id=leader.variant_id, path=leader.path, role="posthoc",
                    label="Post-hoc 2023–26 ATS-only (4/4)\n" + label + " · own median",
                    descriptive_rank=["unique_secondary_window_ats_only_survivor"]))
    return rows


def plot_data(annual: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    if annual.duplicated(["variant_id", "path", "season"]).any():
        raise ValueError("Duplicate annual score key")
    annual = annual.copy()
    annual["full_coverage"] = _bool(annual.full_coverage)
    pieces = []
    for number, row in enumerate(rows):
        block = annual.loc[annual.variant_id.eq(row["variant_id"]) & annual.path.eq(row["path"])].copy()
        if set(block.season) != set(YEARS):
            raise ValueError(f"Incomplete year labels: {row['variant_id']} / {row['path']}")
        block = block.sort_values("season")
        block["display_row"] = number
        block["display_label"] = row["label"]
        block["display_role"] = row["role"]
        block["log_loss_gain"] = 1000 * block[["log_loss_gain_ml", "log_loss_gain_spread_total"]].min(axis=1)
        block["brier_gain"] = 1000 * block[["brier_gain_ml", "brier_gain_spread_total"]].min(axis=1)
        block["roi_pct"] = 100 * block.roi
        block["roi_control_gain_pp"] = 100 * block[["roi_gain_own", "roi_gain_favorite"]].min(axis=1)
        # Probability forecasts predate the mapping, so retain all six seasons
        # of proper scores, including failures before an ATS map is available.
        block.loc[~block.full_coverage, ["roi_pct", "roi_control_gain_pp"]] = np.nan
        pieces.append(block)
    return pd.concat(pieces, ignore_index=True)


def render(results: Path = RESULTS, out_dir: Path | None = None) -> dict:
    results = Path(results)
    out_dir = Path(out_dir) if out_dir is not None else results
    inputs = {name: results / name for name in ("annual_scores.csv", "gate_summary.csv", "variants.csv")}
    annual, gates, variants = (pd.read_csv(inputs[x]) for x in inputs)
    if set(annual.variant_id) != set(variants.id):
        raise ValueError("Annual scores and variant definitions differ")
    rows = select_rows(gates)
    data = plot_data(annual, rows)
    counts = annual.groupby("season").opportunities.nunique()
    if not counts.eq(1).all():
        raise ValueError("Inconsistent season cohorts across variants")
    games_per_year = annual.groupby("season").opportunities.first().to_dict()
    labels = ["\n".join(textwrap.fill(line, 41) for line in row["label"].splitlines()) for row in rows]
    height = max(11.5, 4.1 + .77 * len(rows))
    fig, axes = plt.subplots(2, 2, figsize=(16.8, height), layout="constrained")
    fig.patch.set_facecolor("#f8fafc")
    cmap = LinearSegmentedColormap.from_list("gain", ["#a1303c", "#fffdf8", "#007f74"])
    cmap.set_bad("#dce2e8")
    labels_x = [f"{year}{' YTD' if year == 2026 else ''}\nn={games_per_year[year]}" for year in YEARS]
    for ax, (metric, title, subtitle, fmt) in zip(axes.flat, PANELS):
        array = data.pivot(index="display_row", columns="season", values=metric).reindex(index=range(len(rows)), columns=YEARS).to_numpy()
        finite = np.abs(array[np.isfinite(array)])
        limit = max(float(finite.max()) if len(finite) else 1., 1e-5)
        image = ax.imshow(np.ma.masked_invalid(array), cmap=cmap,
                          norm=TwoSlopeNorm(vmin=-limit, vcenter=0., vmax=limit), aspect="auto")
        ax.set_title(title + "\n" + subtitle, fontsize=11, fontweight="bold", loc="left", pad=11)
        ax.set_xticks(range(len(YEARS)), labels_x, fontsize=8.5)
        ax.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=5)
        ax.set_yticks(range(len(rows)), labels, fontsize=8.3)
        ax.set_xticks(np.arange(-.5, len(YEARS), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.5)
        ax.tick_params(which="minor", bottom=False, left=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for r in range(len(rows)):
            for c in range(len(YEARS)):
                value = array[r, c]
                rounded_zero = np.isfinite(value) and abs(value) < .5 * 10**(-int(fmt[1]))
                text = "—" if not np.isfinite(value) else (format(0., fmt) if rounded_zero else format(value, "+" + fmt))
                color = "#64748b" if not np.isfinite(value) else ("white" if abs(value) > .63 * limit else "#17283b")
                ax.text(c, r, text, ha="center", va="center", fontsize=8.8, color=color)
        cbar = fig.colorbar(image, ax=ax, shrink=.42, pad=.015, fraction=.022)
        cbar.ax.tick_params(labelsize=7.5, length=2)
        for tick, row in zip(ax.get_yticklabels(), rows):
            tick.set_color("#6b45a4" if row["role"] == "posthoc" else "#17283b")
        first_posthoc = next((i for i, row in enumerate(rows) if row["role"] == "posthoc"), None)
        if first_posthoc is not None:
            ax.axhline(first_posthoc - .5, color="#6b45a4", linewidth=1.8)
    feature_raw = gates.loc[~_bool(gates.is_control) & gates.path.eq("raw")]
    feature_all = gates.loc[~_bool(gates.is_control)]
    probability_passes = int(_bool(feature_raw.all_seasons_probability_pass).sum())
    ats_passes = int(_bool(feature_all.all_seasons_ats_pass).sum())
    joint_passes = int(_bool(feature_all.all_seasons_joint_pass).sum())
    fig.suptitle(
        "Every-season market-rule retest\n"
        f"Complete-family sign gates: probability {probability_passes}/{len(feature_raw)} raw arms; "
        f"ATS {ats_passes}/{len(feature_all)} paths; joint {joint_passes}/{len(feature_all)} paths",
        fontsize=16, fontweight="bold", color="#17283b",
    )
    fig.supxlabel(
        "Positive = favorable point estimate. Probability panels use the smaller gain vs paired no-vig moneyline and earlier-fit spread/total anchors.\n"
        "ATS control panel uses the smaller ROI gain vs the same-anchor/same-map policy and same-row market favorite. "
        "These are winner scores, not ATS-cover probabilities.\n"
        "Gray ATS cells = unavailable prior-season median mapping (2021/22). Winner scores remain visible for all six years; "
        "header n counts all games, while winner scores exclude tied finals.\n"
        "All rows are retrospective same-source recipe replays, not saved production bets. 2026 is partial; "
        "pushes remain in ATS denominators. Rounded zeros do not establish a strict gain.\n"
        "Historical ATS prices are assumed −110. Exposed search; nearest misses are descriptive post-hoc rows, not validated selections. "
        "Colors do not show uncertainty or significance; no production promotion.",
        fontsize=8.5, color="#34465b",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    png, svg = out_dir / "season_rule_heatmap.png", out_dir / "season_rule_heatmap.svg"
    fig.savefig(png, dpi=175, bbox_inches="tight", facecolor=fig.get_facecolor(), metadata={"Software": "Matplotlib; saved-results-only research plot"})
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor(), metadata={"Date": None})
    # Matplotlib emits trailing spaces in SVG paths; keep generated diffs clean.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    data.to_csv(out_dir / "season_rule_heatmap_data.csv", index=False)
    metadata = dict(
        title="Every-season market-rule retest", source_sha256={name: _sha(path) for name, path in inputs.items()},
        rows=rows, years=list(YEARS), games_per_year=games_per_year,
        descriptive_nearest_ranking=NEAREST_RULES,
        derived_columns={
            "log_loss_gain": "1000 * min(log_loss_gain_ml, log_loss_gain_spread_total)",
            "brier_gain": "1000 * min(brier_gain_ml, brier_gain_spread_total)",
            "roi_pct": "100 * roi",
            "roi_control_gain_pp": "100 * min(roi_gain_own, roi_gain_favorite)",
        },
        coverage_mask="Only ATS panels blank for paths without complete same-season coverage; proper scores remain visible",
        outputs={png.name: _sha(png), svg.name: _sha(svg)},
        warnings=["Exposed historical search, not fresh validation", "2026 is partial",
                  "ATS −110 is an assumption", "Point estimates only; no significance claim",
                  "Winner proper scores do not estimate ATS-cover probabilities"],
    )
    (out_dir / "season_rule_heatmap_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    result = render(args.results, args.out_dir)
    print(json.dumps(dict(rows=len(result["rows"]), outputs=list(result["outputs"]))))
