"""H12: fade the band-capped team ATS residual, 2013-2018; research, never production.

Protocol: research/PREREGISTRATION.md (2026-10-27, H12). One out-of-period run on
exposed seasons; not forward evidence.

    python -m research.h12_capped_residual --prepare-inputs   # one download, frozen
    python -m research.h12_capped_residual
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GAMES_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
SEED = ROOT / 'research/ml_spread_inputs/games_2006_2012.csv'
INPUTS = ROOT / 'research/h12_inputs'
FROZEN = INPUTS / 'games_2013_2018.csv'
OUTPUT = ROOT / 'research/h12_results'
FIRST, LAST = 2013, 2018
CUTS = np.array([3., 7., 10.])
MAGS = np.array([3., 4., 7., 14.])  # 2026 production median-map magnitudes
N = 8
THRESHOLD = 2.51  # SD of x on 2019-25, fixed in the pre-registration
SECONDARY_N = (4, 16)
MIN_BETS = 150
BREAK_EVEN = 110 / 210
FRANCHISE = {'STL': 'LA', 'SD': 'LAC'}
COLUMNS = ['game_id', 'season', 'week', 'game_type', 'home_team', 'away_team', 'result', 'spread_line']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare_inputs():
    # Hash of pandas' re-serialization of the download, not of the raw HTTP bytes.
    raw = pd.read_csv(GAMES_URL).to_csv(index=False).encode()
    g = pd.read_csv(io.BytesIO(raw))
    g = g[g.season.between(FIRST, LAST) & g.game_type.eq('REG')][COLUMNS]
    INPUTS.mkdir(parents=True, exist_ok=True)
    g.to_csv(FROZEN, index=False)
    (INPUTS / 'provenance.json').write_text(json.dumps(dict(
        source=GAMES_URL, downloaded_utc=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
        source_reserialized_sha256=sha(raw), frozen=str(FROZEN.relative_to(ROOT)), frozen_sha256=sha(FROZEN.read_bytes()),
        rows=len(g), note=f'All {FIRST}-{LAST} regular-season games, priced or not.'), indent=2) + '\n')


def cap(t, line):
    c = MAGS[np.digitize(abs(line), CUTS)]
    return float(np.clip(t, -c, c))


def load(seed=SEED, frozen=FROZEN):
    g = pd.concat([pd.read_csv(seed), pd.read_csv(frozen)], ignore_index=True)
    g = g[g.game_type.eq('REG') & (g.season.eq(FIRST - 1) | g.season.between(FIRST, LAST))]
    g = g.dropna(subset=['result', 'spread_line']).copy()
    for side in ('home_team', 'away_team'):
        g[side] = g[side].replace(FRANCHISE)
    return g.sort_values(['season', 'week', 'game_id'], kind='stable').reset_index(drop=True)


def signals(g, n):
    """x = home minus away mean of the last n capped residuals, from strictly earlier weeks."""
    hist, x = {}, np.full(len(g), np.nan)
    keys = list(zip(g.season, g.week))
    for key in dict.fromkeys(keys):
        cur = [i for i, k in enumerate(keys) if k == key]
        for i in cur:
            h, a = hist.get(g.home_team[i], [])[-n:], hist.get(g.away_team[i], [])[-n:]
            if len(h) == n and len(a) == n:
                x[i] = np.mean(h) - np.mean(a)
        for i in cur:
            t, line = g.result[i] - g.spread_line[i], g.spread_line[i]
            hist.setdefault(g.home_team[i], []).append(cap(t, line))
            hist.setdefault(g.away_team[i], []).append(cap(-t, line))
    return x


def returns(side, margin):
    e = side * margin
    return np.where(e > 0, 1 / 1.1, np.where(e < 0, -1., 0.))


def wilson(w, n, z=1.96):
    if not n:
        return np.nan, np.nan
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def record(side, margin):
    u = returns(side, margin)
    w, l = int((u > 0).sum()), int((u < 0).sum())
    lo, hi = wilson(w, w + l)
    n = len(u)
    return dict(bets=n, wins=w, losses=l, pushes=n - w - l, cover=w / (w + l) if w + l else np.nan,
                cover_lo=lo, cover_hi=hi, units=float(u.sum()), roi=float(u.mean()) if n else np.nan,
                roi_se=float(u.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan)


def evaluate(g, n=N):
    x = signals(g, n)
    scored = g.season.between(FIRST, LAST).to_numpy() & np.isfinite(x)
    bet = scored & (np.abs(x) >= THRESHOLD)
    margin = (g.result - g.spread_line).to_numpy()
    side = -np.sign(x)  # fade: away when home's recent residual is higher
    fav = np.sign(g.spread_line.to_numpy())
    out = dict(n=n, scored_games=int(scored.sum()), rule=record(side[bet], margin[bet]),
               favorite=record(fav[bet & (fav != 0)], margin[bet & (fav != 0)]),
               home=record(np.ones(bet.sum()), margin[bet]))
    z, cov = x[scored] / THRESHOLD, np.sign(margin[scored])
    X = np.c_[np.ones(len(z)), z]
    beta = np.linalg.lstsq(X, cov, rcond=None)[0]
    r = cov - X @ beta
    out['cover_slope'] = float(beta[1])
    out['cover_slope_se'] = float(np.sqrt(r.var(ddof=2) / ((z - z.mean()) ** 2).sum()))
    out['by_season'] = {int(s): record(side[bet & g.season.eq(s).to_numpy()], margin[bet & g.season.eq(s).to_numpy()])
                        for s in range(FIRST, LAST + 1)}
    return out


def verdict(primary):
    r, f = primary['rule'], primary['favorite']
    if r['bets'] < MIN_BETS:
        return 'inconclusive (fewer than 150 bets): dropped'
    if r['cover'] > BREAK_EVEN and r['cover'] > f['cover']:
        return 'replicates: register a reporting-only forward shadow as its own hypothesis'
    return 'falsified: dropped'


def line(name, r):
    return (f"| {name} | {r['bets']} | {r['wins']}-{r['losses']}-{r['pushes']} | {100 * r['cover']:.1f}% "
            f"[{100 * r['cover_lo']:.1f}, {100 * r['cover_hi']:.1f}] | {r['units']:+.2f}u | "
            f"{100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} |")


def run(output=OUTPUT):
    g = load()
    primary = evaluate(g, N)
    res = dict(primary=primary, secondary={n: evaluate(g, n) for n in SECONDARY_N}, verdict=verdict(primary),
               threshold=THRESHOLD, frozen_sha256=sha(FROZEN.read_bytes()))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(res, indent=2, default=float) + '\n')
    head = '| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |\n|---|---|---|---|---|---|'
    p = primary
    md = ['# H12: fade the band-capped team ATS residual, 2013-2018', '',
          'Pre-registered in research/PREREGISTRATION.md (2026-10-27). One out-of-period run on exposed '
          'seasons; not forward evidence. Assumed -110; pushes in the ROI denominator; break-even 52.4%.', '',
          f"**Verdict: {res['verdict']}.**", '',
          f"Primary: N = {N}, |x| >= {THRESHOLD} pts; {p['scored_games']} scored games.", '', head,
          line('Fade rule', p['rule']), line('Always favorite (same rows)', p['favorite']),
          line('Always home (same rows)', p['home']), '',
          f"Secondary: cover slope per {THRESHOLD} pts of x, all scored games: "
          f"{p['cover_slope']:+.3f} ± {p['cover_slope_se']:.3f} (negative = fading works)", '',
          '| Season | ' + head.split('\n')[0][2:].replace('Arm | ', ''), '|---|---|---|---|---|---|']
    md += [line(str(s), r) for s, r in p['by_season'].items()]
    md += ['', 'Secondary windows (never decisive):', '', head]
    for n, s in res['secondary'].items():
        md += [line(f'Fade, N = {n}', s['rule']), line(f'Favorite, N = {n} rows', s['favorite'])]
    md += ['', 'Reproduce: `python -m research.h12_capped_residual`', '']
    (output / 'REPORT.md').write_text('\n'.join(md))
    return res


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-inputs', action='store_true')
    args = parser.parse_args()
    if args.prepare_inputs:
        prepare_inputs()
        print(f'Frozen: {FROZEN}')
    else:
        run()
        print((OUTPUT / 'REPORT.md').read_text())


if __name__ == '__main__':
    main()
