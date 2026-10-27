"""H10: band margin distributions vs the Kalshi spread ladder; research, never production.

Protocol: research/PREREGISTRATION.md (2026-10-27, H10). A prediction test with no
betting rule: does the production band's empirical margin PMF (SB1's hard bands)
price "team wins by over X.5" better than the Kalshi mid on the same rung?

    python -m research.band_ladder_score
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import kalshi as k
import nfl_model as m
from research import soft_band_distributions as sb

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/forward_ledger.csv'
SNAPSHOTS = ROOT / 'data/kalshi_snapshots.jsonl'
HISTORICAL = ROOT / 'data/kalshi_historical/kalshi_quotes.csv'
OUTPUT = ROOT / 'research/band_ladder_results'
PRIMARY = 'boxscore-composite-v1.18'
SECONDARY = 'boxscore-composite-v1.16'
MAX_STRIKE = 17.5
MAX_WIDTH = .05
CLIP = (.005, .995)
NEAR = 4.
DECISION_N = 100


def valid_quote(bid, ask):
    return bool(np.isfinite(bid) and np.isfinite(ask) and 0 < bid <= ask < 1 and ask - bid <= MAX_WIDTH + 1e-9)


def over(pmf, home_team, strike):
    """PMF mass on the named team's margin > strike (home-oriented PMF on sb.GRID)."""
    return float(pmf[sb.GRID > strike].sum() if home_team else pmf[sb.GRID < -strike].sum())


def log_loss(p, y):
    p = np.clip(np.asarray(p, float), *CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def capture(caps, generated_utc):
    """grade_ledger.kalshi_grades' join: first capture at or after the lock, else the last one."""
    lock = pd.Timestamp(generated_utc)
    after = [c for c in caps if pd.Timestamp(c['captured_utc']) >= lock]
    return (after[0], False) if after else ((caps[-1], True) if caps else (None, False))


def forward_rungs(ledger, snaps, fit, revision, table=None):
    by = {}
    for s in sorted(snaps, key=lambda s: pd.Timestamp(s['captured_utc'])):
        by.setdefault(s['game_id'], []).append(s)
    g = ledger[(ledger.revision == revision) & (ledger.status == 'graded')]
    g = g.sort_values('generated_utc', kind='stable').drop_duplicates('game_id')
    rows, early, invalid = [], 0, 0
    for r in g.itertuples(index=False):
        snap, before = capture(by.get(r.game_id, []), r.generated_utc)
        if snap is None:
            continue
        early += before
        raw = float(m.implied_spread([r.model_wp])[0])
        if not np.isfinite(raw) or raw == 0:
            continue
        hard, _ = sb.forecast(raw, fit, soft=False)
        soft, _ = sb.forecast(raw, fit, soft=True)
        fav_wp = team_fav = None
        if table is not None and pd.notna(r.home_moneyline) and pd.notna(r.away_moneyline):
            ih, ia = k.ml_implied(r.home_moneyline), k.ml_implied(r.away_moneyline)
            hp = ih / (ih + ia)
            fav_wp, team_fav = max(hp, 1 - hp), (r.home if hp >= .5 else r.away)
        for q in snap['spread_ladder']:
            if q['strike'] > MAX_STRIKE:
                continue
            if not valid_quote(q['bid'], q['ask']):
                invalid += 1
                continue
            home = q['team'] == r.home
            margin = r.result if home else -r.result
            line = r.spread_line if home else -r.spread_line
            ref = np.nan
            if fav_wp is not None:
                try:
                    ref = k.ladder_probability(table, fav_wp, q['team'] == team_fav, q['strike'])
                except KeyError:
                    pass
            rows.append(dict(game_id=r.game_id, week=int(r.week), team=q['team'], strike=q['strike'],
                             kalshi=(q['bid'] + q['ask']) / 2, band=over(hard, home, q['strike']),
                             soft=over(soft, home, q['strike']), h3=ref, y=float(margin > q['strike']),
                             near=bool(np.isfinite(line) and abs(q['strike'] - line) <= NEAR),
                             captured_before_lock=before))
    return pd.DataFrame(rows), dict(games_captured_before_lock=int(early), invalid_rungs=int(invalid))


def development_rungs(quotes, games):
    """2025-26 main-spread rung from exposed historical quotes and SB1's frozen raw spreads."""
    games = sb.clean(games)
    rows = []
    for season in sorted(set(quotes.season) & {2025, 2026}):
        fit = sb.fit_prior(games[games.season < season], season)
        base = games[games.season == season].set_index('game_id')
        for q in quotes[quotes.season == season].itertuples(index=False):
            if q.game_id not in base.index or not valid_quote(q.kalshi_yes_bid, q.kalshi_yes_ask):
                continue
            r = base.loc[q.game_id]
            hard, _ = sb.forecast(float(r.raw_spread), fit, soft=False)
            home = q.kalshi_favorite == r.home
            margin = r.result if home else -r.result
            rows.append(dict(game_id=q.game_id, week=int(r.week), team=q.kalshi_favorite, strike=q.kalshi_strike,
                             kalshi=(q.kalshi_yes_bid + q.kalshi_yes_ask) / 2,
                             band=over(hard, home, q.kalshi_strike), y=float(margin > q.kalshi_strike)))
    return pd.DataFrame(rows)


def score(rungs, challenger='band', subset=None):
    """Per-game mean of Kalshi loss - challenger loss (positive = challenger better)."""
    d = rungs if subset is None else rungs[subset]
    d = d[d[challenger].notna()]
    if not len(d):
        return dict(games=0, rungs=0, gain=np.nan, se=np.nan)
    gain = log_loss(d.kalshi, d.y) - log_loss(d[challenger], d.y)
    per = pd.Series(gain, index=d.index).groupby(d.game_id).mean()
    n = len(per)
    se = float(per.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
    return dict(games=n, rungs=len(d), gain=float(per.mean()), se=se,
                lo=float(per.mean() - 2 * se) if n > 1 else np.nan,
                kalshi_loss=float(log_loss(d.kalshi, d.y).mean()),
                challenger_loss=float(log_loss(d[challenger], d.y).mean()),
                pooled_rung_gain=float(gain.mean()))


def verdict(r):
    if r['games'] < DECISION_N:
        return f"interim (n = {r['games']} < {DECISION_N} games): no verdict"
    if r['gain'] <= 0:
        return 'falsified: no basis for an alt-line chooser'
    if r['lo'] > 0:
        return 'supported: a separately registered alt-line test is justified'
    return 'unresolved'


def fmt(r):
    if not r['games']:
        return 'no rows'
    se = f" +/- {r['se']:.4f}" if np.isfinite(r['se']) else ''
    return (f"gain {r['gain']:+.4f}{se} (1 SE; positive = challenger better); "
            f"{r['games']} games, {r['rungs']} rungs; log loss Kalshi {r['kalshi_loss']:.4f} vs "
            f"challenger {r['challenger_loss']:.4f}")


def run(output_dir=OUTPUT):
    ledger = pd.read_csv(LEDGER)
    snaps = [json.loads(line) for line in SNAPSHOTS.read_text().splitlines() if line.strip()]
    games = pd.read_csv(sb.INPUT)
    fit = sb.fit_prior(sb.clean(games)[lambda g: g.season < 2026], 2026)
    table = k.load_ladder_table() if k.LADDER_TABLE.exists() else None
    primary, audit = forward_rungs(ledger, snaps, fit, PRIMARY, table)
    v116, _ = forward_rungs(ledger, snaps, fit, SECONDARY, table)
    dev = development_rungs(pd.read_csv(HISTORICAL), games)
    res = dict(primary=score(primary), soft=score(primary, 'soft'), h3=score(primary, 'h3'),
               near=score(primary, subset=primary.near) if len(primary) else score(primary),
               v116=score(v116), development=score(dev),
               development_by_season={int(s): score(dev, subset=dev.game_id.str[:4].eq(str(s)))
                                      for s in sorted(dev.game_id.str[:4].astype(int).unique())} if len(dev) else {},
               fit=dict(training_games=fit['training_games'], band_counts=fit['band_counts'],
                        medians=fit['medians'], fit_sha256=fit['fit_sha256']), audit=audit)
    res['verdict'] = verdict(res['primary'])
    output_dir.mkdir(parents=True, exist_ok=True)
    primary.to_csv(output_dir / 'primary_rungs.csv', index=False, float_format='%.6g')
    dev.to_csv(output_dir / 'development_rungs.csv', index=False, float_format='%.6g')
    (output_dir / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    lines = ['# H10: band margin distributions vs the Kalshi spread ladder', '',
             'Pre-registered in research/PREREGISTRATION.md (2026-10-27). Prediction only; no bets. '
             'Production, the median map and the archives are unchanged.', '',
             f"**Primary ({PRIMARY}, forward): {res['verdict']}.**", '',
             f"- Hard band PMF vs Kalshi mid: {fmt(res['primary'])}",
             f"- Captures before the lock: {audit['games_captured_before_lock']} games; "
             f"invalid quotes excluded: {audit['invalid_rungs']} rungs", '',
             'Secondary, never decisive:', '',
             f"- (a) Soft band PMF: {fmt(res['soft'])}",
             f"- (b) H3 moneyline reference: {fmt(res['h3'])}",
             f"- (c) Near-line rungs (within {NEAR:g} pts of the team's line): {fmt(res['near'])}",
             f"- (d) {SECONDARY} forward rows (overlapping games): {fmt(res['v116'])}",
             f"- (e) Development, exposed 2025-26 main-spread rung 2h pregame: {fmt(res['development'])}"]
    lines += [f"  - {s}: {fmt(r)}" for s, r in res['development_by_season'].items()]
    lines += ['', 'Reproduce: `python -m research.band_ladder_score`', '']
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
