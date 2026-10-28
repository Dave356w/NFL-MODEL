"""H11: soft band margin distributions vs the Kalshi spread ladder; research, never production.

Protocol: research/PREREGISTRATION.md (2026-10-27, H11). H10's rungs and score with SB1's
soft PMF as the forecast, on games not already scored when H11 was registered.

    python -m research.soft_band_ladder_score
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import kalshi as k
from research import band_ladder_score as h10
from research import soft_band_distributions as sb

ROOT = Path(__file__).resolve().parents[1]
EXPOSED = ROOT / 'research/soft_band_ladder_inputs/exposed_games.txt'
OUTPUT = ROOT / 'research/soft_band_ladder_results'


def exposed_games(path=EXPOSED):
    return {line.strip() for line in Path(path).read_text().splitlines() if line.strip()}


def paired(rungs):
    """Soft minus hard: per-game mean of hard loss - soft loss (positive = soft better)."""
    return h10.score(rungs.assign(kalshi=rungs.band), 'soft')


def run(output_dir=OUTPUT):
    ledger = pd.read_csv(h10.LEDGER)
    snaps = [json.loads(line) for line in h10.SNAPSHOTS.read_text().splitlines() if line.strip()]
    games = pd.read_csv(sb.INPUT)
    fit = sb.fit_prior(sb.clean(games)[lambda g: g.season < 2026], 2026)
    table = k.load_ladder_table() if k.LADDER_TABLE.exists() else None
    rungs, audit = h10.forward_rungs(ledger, snaps, fit, h10.PRIMARY, table)
    seen = exposed_games()
    fresh = rungs[~rungs.game_id.isin(seen)] if len(rungs) else rungs
    exposed = rungs[rungs.game_id.isin(seen)] if len(rungs) else rungs
    dev = h10.development_rungs(pd.read_csv(h10.HISTORICAL), games)
    res = dict(primary=h10.score(fresh, 'soft'), exposed=h10.score(exposed, 'soft'),
               soft_vs_hard=paired(fresh) if len(fresh) else h10.score(fresh, 'soft'),
               near=h10.score(fresh, 'soft', subset=fresh.near) if len(fresh) else h10.score(fresh, 'soft'),
               development=h10.score(dev, 'soft'), exposed_games=len(seen), audit=audit,
               fit_sha256=fit['fit_sha256'])
    res['verdict'] = h10.verdict(res['primary']) if res['primary']['games'] else (
        f'interim (n = 0 < {h10.DECISION_N} fresh games): no verdict')
    output_dir.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(output_dir / 'primary_rungs.csv', index=False, float_format='%.6g')
    (output_dir / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    lines = ['# H11: soft band margin distributions vs the Kalshi spread ladder', '',
             'Pre-registered in research/PREREGISTRATION.md (2026-10-27). Prediction only; no bets. '
             'Production, the median map and the archives are unchanged.', '',
             f"**Primary ({h10.PRIMARY}, fresh forward games): {res['verdict']}.**", '',
             f"- Soft band PMF vs Kalshi mid: {h10.fmt(res['primary'])}",
             f"- Excluded as exposed at registration: {len(seen)} games", '',
             'Secondary, never decisive:', '',
             f"- (a) Exposed games (seen before H11 was registered): {h10.fmt(res['exposed'])}",
             f"- (b) Soft vs hard, fresh games (positive = soft better): {h10.fmt(res['soft_vs_hard'])}"
             .replace('Kalshi', 'hard'),
             f"- (c) Near-line rungs (within {h10.NEAR:g} pts of the team's line): {h10.fmt(res['near'])}",
             f"- (d) Development, exposed 2025-26 main-spread rung 2h pregame: {h10.fmt(res['development'])}",
             '', 'Reproduce: `python -m research.soft_band_ladder_score`', '']
    (output_dir / 'REPORT.md').write_text('\n'.join(lines))
    return res


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()
    res = run(args.output_dir)
    print((args.output_dir / 'REPORT.md').read_text())
    return res


if __name__ == '__main__':
    main()
