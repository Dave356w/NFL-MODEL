"""H13: H12's capped-residual fade as a reporting-only shadow on the ATS locks.

Protocol: research/PREREGISTRATION.md (2026-10-27, H13). Never bets and changes no lock,
pick or page. Also reports the 2026 replay diagnostic (basis 3, never pooled with H13).

    python -m research.h13_shadow
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fixed_bands
from research import h12_capped_residual as h12

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'data/latest/fixed_band_ledger.csv'
LOCKS = ROOT / 'data/ats_locks.jsonl'
OUTPUT = ROOT / 'research/h13_results'
REVISION = 'boxscore-composite-v1.18'
CUTOFF = pd.Timestamp('2026-10-28T00:00:00Z')
REPLAY_SEASON = 2026
DECISION_N = 300


def history(path=HISTORY):
    """Completed regular-season games with a spread, in H12's column names."""
    g = pd.read_csv(path).rename(columns={'home': 'home_team', 'away': 'away_team'})
    g = g[g.season.ge(2024) & g.week.le(18)].dropna(subset=['result', 'spread_line'])
    for side in ('home_team', 'away_team'):
        g[side] = g[side].replace(h12.FRANCHISE)
    return g.sort_values(['season', 'week', 'game_id'], kind='stable').reset_index(drop=True)


def signal(hist, season, week, home, away, n=h12.N):
    """Home minus away mean of the last n capped residuals from strictly earlier weeks."""
    past = hist[(hist.season < season) | ((hist.season == season) & (hist.week < week))]
    games = {}
    for r in past.itertuples(index=False):
        t = r.result - r.spread_line
        games.setdefault(r.home_team, []).append(h12.cap(t, r.spread_line))
        games.setdefault(r.away_team, []).append(h12.cap(-t, r.spread_line))
    h, a = games.get(home, [])[-n:], games.get(away, [])[-n:]
    return np.mean(h) - np.mean(a) if len(h) == n and len(a) == n else np.nan


def shadow_side(x):
    return -np.sign(x) if np.isfinite(x) and abs(x) >= h12.THRESHOLD else 0.


def arms(rows):
    """Shadow and same-row baselines on graded shadow bets."""
    b = rows[(rows.side != 0) & rows.margin.notna()]
    m = b.margin.to_numpy(float)
    fav = np.sign(b.line.to_numpy(float))
    out = dict(shadow=h12.record(b.side.to_numpy(float), m),
               favorite=h12.record(fav[fav != 0], m[fav != 0]),
               home=h12.record(np.ones(len(b)), m))
    if 'production' in b and b.production.notna().any():
        p = b.production.notna().to_numpy()
        out['production'] = h12.record(b.production.to_numpy(float)[p], m[p])
    return out


def forward_rows(hist, locks):
    rows = []
    for s in locks:
        if s.get('revision') != REVISION or pd.Timestamp(s['lock_at_utc']) < CUTOFF:
            continue
        x = signal(hist, int(s['season']), int(s['week']), h12.FRANCHISE.get(s['home'], s['home']),
                   h12.FRANCHISE.get(s['away'], s['away']))
        done = hist[hist.game_id == s['game_id']]
        line = float(s['market_spread'])
        rows.append(dict(game_id=s['game_id'], week=int(s['week']), x=x, side=shadow_side(x), line=line,
                         production=float(fixed_bands.pick([s['fixed_band_spread']], [line])[0]),
                         margin=float(done.result.iloc[0]) - line if len(done) else np.nan,
                         recovered=bool(s.get('recovered_after_kickoff', False))))
    return pd.DataFrame(rows, columns=['game_id', 'week', 'x', 'side', 'line', 'production', 'margin', 'recovered'])


def replay_rows(hist, season=REPLAY_SEASON):
    rows = []
    for r in hist[hist.season == season].itertuples(index=False):
        x = signal(hist, season, int(r.week), r.home_team, r.away_team)
        mapped = r.fixed_band_spread
        rows.append(dict(game_id=r.game_id, week=int(r.week), x=x, side=shadow_side(x), line=r.spread_line,
                         production=float(fixed_bands.pick([mapped], [r.spread_line])[0]) if pd.notna(mapped) else np.nan,
                         margin=r.result - r.spread_line))
    return pd.DataFrame(rows, columns=['game_id', 'week', 'x', 'side', 'line', 'production', 'margin'])


def verdict(r):
    if r['bets'] < DECISION_N:
        return f"interim (n = {r['bets']} < {DECISION_N} shadow bets): no verdict"
    if r['cover'] <= h12.BREAK_EVEN:
        return 'falsified'
    if r['roi'] - 2 * r['roi_se'] > 0:
        return 'supported: an owner decision on a new ATS policy version is justified'
    return 'unresolved'


def table(res):
    lines = ['| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |', '|---|---|---|---|---|---|']
    names = dict(shadow='H12 fade (shadow)', production='Production median map', favorite='Always favorite',
                 home='Always home')
    for k in ('shadow', 'production', 'favorite', 'home'):
        r = res.get(k)
        if r is None or not r['bets']:
            lines.append(f'| {names[k]} | 0 | — | — | — | — |')
            continue
        cover = (f"{100 * r['cover']:.1f}% [{100 * r['cover_lo']:.1f}, {100 * r['cover_hi']:.1f}]"
                 if np.isfinite(r['cover']) else 'n/a')
        se = f" ± {100 * r['roi_se']:.1f}" if np.isfinite(r['roi_se']) else ''
        lines.append(f"| {names[k]} | {r['bets']} | {r['wins']}-{r['losses']}-{r['pushes']} | {cover} | "
                     f"{r['units']:+.2f}u | {100 * r['roi']:+.1f}%{se} |")
    return lines


def run(output=OUTPUT):
    hist = history()
    locks = [json.loads(line) for line in LOCKS.read_text().splitlines() if line.strip()]
    fwd, rep = forward_rows(hist, locks), replay_rows(hist)
    recovered = fwd.recovered.astype(bool).to_numpy()
    pregame = fwd.loc[~recovered]
    res = dict(forward=arms(pregame), recovered=arms(fwd.loc[recovered]), replay=arms(rep),
               forward_locks=len(fwd), forward_pending=int(pregame.margin.isna().sum()),
               forward_shadow_pending=int(((pregame.side != 0) & pregame.margin.isna()).sum()),
               replay_games=int(rep.x.notna().sum()))
    res['verdict'] = verdict(res['forward']['shadow'])
    output.mkdir(parents=True, exist_ok=True)
    fwd.to_csv(output / 'forward_rows.csv', index=False, float_format='%.6g')
    rep.to_csv(output / 'replay_rows.csv', index=False, float_format='%.6g')
    (output / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    md = ['# H13: H12 capped-residual fade, forward shadow on the ATS locks', '',
          'Pre-registered in research/PREREGISTRATION.md (2026-10-27). Reporting only: never bet, no lock, '
          'pick or page changes. Assumed -110; pushes in the ROI denominator; break-even 52.4%.', '',
          f"**Forward ({REVISION} locks from {CUTOFF:%Y-%m-%d %H:%M} UTC): {res['verdict']}.** "
          f"{len(fwd)} locks, {res['forward_pending']} pending ({res['forward_shadow_pending']} shadow bets pending).", '']
    md += table(res['forward'])
    md += ['', f"Diagnostic, never pooled: {REPLAY_SEASON} replay on every completed regular-season game "
           f"(exposed current season; {res['replay_games']} games with both histories; production pick where a "
           'saved or replayed mapped spread exists).', '']
    md += table(res['replay'])
    md += ['', 'Reproduce: `python -m research.h13_shadow`', '']
    (output / 'REPORT.md').write_text('\n'.join(md))
    return res


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
    print((OUTPUT / 'REPORT.md').read_text())


if __name__ == '__main__':
    main()
