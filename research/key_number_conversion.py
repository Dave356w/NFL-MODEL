"""Key-number-aware spread <-> probability conversion (research only).

Problem: nfl_model.implied_spread uses MARKET_SIGMA * Phi^-1(p), a normal margin
with no key numbers. Feeding it the market's own no-vig q gives spreads that miss
the posted line by -0.5 pts at short lines and +0.5 to +1.0 pts at 3.5-7.5, so a
model equal to the market still shows a 1-pt "edge" in ~1 game in 7.

Fix: an empirical, discrete margin distribution conditioned on the market line.
For a favorite line L, the favorite's final margin pmf is the kernel-weighted
histogram of games whose |line| is near L (triangular kernel, bandwidth widened
until the effective sample is large enough). Key numbers (3, 7, 10, ...) are
kept because the pmf is built from margins, never shifted residuals.

From that pmf:
  win_prob(s)          P(home wins) for a home spread s (ties count half)
  spread_from_prob(p)  inverse of win_prob (monotone grid inversion)
  cover_prob(s, line)  P(home covers line | no push), margin pmf at s

Evaluation compares model and market in probability space on the same rows,
walk-forward: the distribution for season Y is fit on seasons < Y only.

Run from the repo root:  python research/key_number_conversion.py
Inputs are frozen in research/key_number_inputs/; no network access needed.
Production, frozen recipes and the forward ledger are untouched.
"""
# ---------------------------------------------------------------- config
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES_CSV = ROOT / 'research/key_number_inputs/nflverse_games_lines.csv'
OOS_CSV = ROOT / 'research/out_of_sample_results/predictions.csv'   # v1.16, 2017-20
LEDGER_CSV = ROOT / 'data/latest/fixed_band_ledger.csv'             # 2021-26
OUT_DIR = ROOT / 'research/key_number_results'
FIRST_FIT_SEASON = 1999
BANDWIDTH = 1.0          # initial triangular kernel half-width, points of line
BANDWIDTH_STEP = 0.5     # widen until effective n >= MIN_EFFECTIVE
MIN_EFFECTIVE = 300.0
MAX_MARGIN = 70
GRID_STEP = 0.25
GRID_MAX = 30.0
EMP_MAX = 14.0           # beyond this |line|, shift the EMP_MAX pmf by whole points
EDGE_BUCKETS = [0, .01, .02, .03, .05, 1.0]   # |cover prob - 0.5| buckets
LINE_BUCKETS = [-.1, 2.5, 3.25, 6.5, 7.25, 10, 40]
LINE_LABELS = ['<=2.5', '3', '3.5-6.5', '7', '7.5-10', '10+']
# ----------------------------------------------------------------

import sys

import numpy as np
import pandas as pd
from scipy.special import ndtri

sys.path.insert(0, str(ROOT))
MARKET_SIGMA = 12.37
try:
    import nfl_model as _m
    MARKET_SIGMA = float(_m.MARKET_SIGMA)
except Exception as exc:  # research must still run without the full model stack
    print(f'note: nfl_model not importable ({exc}); using MARKET_SIGMA={MARKET_SIGMA}')

SUPPORT = np.arange(-MAX_MARGIN, MAX_MARGIN + 1)


def no_vig_home(home_ml, away_ml):
    """No-vig home win probability from American moneylines (multiplicative de-vig)."""
    def imp(ml):
        ml = np.asarray(ml, float)
        return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))
    h, a = imp(home_ml), imp(away_ml)
    return h / (h + a)


def probit_spread(p):
    return MARKET_SIGMA * ndtri(np.clip(np.asarray(p, float), .005, .995))


class MarginModel:
    """Empirical favorite-margin pmf conditioned on the market line."""

    def __init__(self, games):
        g = games.dropna(subset=['spread_line', 'result'])
        if g.empty:
            raise ValueError('MarginModel needs games with spread_line and result')
        line = g.spread_line.to_numpy(float)
        res = g.result.to_numpy(float)
        fav = np.abs(line)
        fm = np.where(line > 0, res, np.where(line < 0, -res, res))
        # pick'em lines enter in both orientations at half weight
        pk = line == 0
        self.L = np.r_[fav[~pk], fav[pk], fav[pk]]
        self.M = np.clip(np.r_[fm[~pk], res[pk], -res[pk]], -MAX_MARGIN, MAX_MARGIN).astype(int)
        self.W0 = np.r_[np.ones((~pk).sum()), np.full(pk.sum(), .5), np.full(pk.sum(), .5)]
        self.n_games = len(g)
        self._cache = {}
        self.grid = np.arange(0, GRID_MAX + 1e-9, GRID_STEP)
        wp = np.array([self._wp_fav(L) for L in self.grid])
        wp[0] = .5
        wp = np.maximum.accumulate(np.clip(wp, .5, 1 - 1e-6))
        self.wp_grid = wp + 1e-9 * np.arange(len(wp))   # strictly increasing for interp

    def pmf(self, L):
        """Favorite-margin pmf on SUPPORT for favorite line L >= 0."""
        key = round(abs(float(L)) / GRID_STEP) * GRID_STEP
        if key in self._cache:
            return self._cache[key]
        if key > EMP_MAX:
            # Long lines are sparse: shift the EMP_MAX pmf by whole points so its
            # discreteness survives, mixing the two neighbouring shifts.
            base = self._kernel_pmf(EMP_MAX)
            k, frac = divmod(key - EMP_MAX, 1.0)
            lo, hi = np.roll(base, int(k)), np.roll(base, int(k) + 1)
            lo[:int(k)] = 0; hi[:int(k) + 1] = 0
            p = (1 - frac) * lo + frac * hi
            p = p / p.sum()
        else:
            p = self._kernel_pmf(key)
        self._cache[key] = p
        return p

    def _kernel_pmf(self, key):
        h = BANDWIDTH
        while True:
            w = self.W0 * np.clip(1 - np.abs(self.L - key) / h, 0, None)
            if w.sum() >= MIN_EFFECTIVE or h > 40:
                break
            h += BANDWIDTH_STEP
        p = np.bincount(self.M + MAX_MARGIN, weights=w, minlength=len(SUPPORT))
        return p / p.sum()

    def _wp_fav(self, L):
        p = self.pmf(L)
        return p[SUPPORT > 0].sum() + .5 * p[SUPPORT == 0].sum()

    def win_prob(self, s):
        s = np.asarray(s, float)
        w = np.interp(np.abs(s), self.grid, self.wp_grid)
        return np.where(s >= 0, w, 1 - w)

    def spread_from_prob(self, p):
        p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
        mag = np.interp(np.maximum(p, 1 - p), self.wp_grid, self.grid)
        return np.where(p >= .5, mag, -mag)

    def cover_prob(self, s, line):
        """P(home margin > line | not a push) when the home spread is s."""
        s = np.atleast_1d(np.asarray(s, float))
        line = np.atleast_1d(np.asarray(line, float))
        out = np.full(len(s), np.nan)
        for i, (si, li) in enumerate(zip(s, line)):
            if not (np.isfinite(si) and np.isfinite(li)):
                continue
            p = self.pmf(abs(si))
            hm = p if si >= 0 else p[::-1]          # home-margin pmf
            over, push = hm[SUPPORT > li].sum(), hm[SUPPORT == li].sum()
            out[i] = over / (1 - push) if push < 1 else np.nan
        return out


# ---------------------------------------------------------------- evaluation
def cluster_lpm(y, X, cl):
    X = np.c_[np.ones(len(y)), X]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    Xi = np.linalg.inv(X.T @ X)
    M = sum(np.outer(X[cl == c].T @ e[cl == c], X[cl == c].T @ e[cl == c]) for c in np.unique(cl))
    return b[1:], np.sqrt(np.diag(Xi @ M @ Xi))[1:]


def record(won, n_push=0):
    won = np.asarray(won, int)
    w, l = int(won.sum()), int(len(won) - won.sum())
    n = w + l + n_push
    u = np.r_[np.full(w, 1 / 1.1), np.full(l, -1.), np.zeros(n_push)]
    se = u.std() / np.sqrt(n) if n else np.nan
    return dict(W=w, L=l, cover=w / (w + l) if w + l else np.nan,
                roi=u.mean() if n else np.nan, roi_se=se)


def load_eval_sets():
    sets = {}
    if OOS_CSV.exists():
        o = pd.read_csv(OOS_CSV)
        sets['2017-20 OOS (v1.16)'] = o.rename(columns={'production': 'p'})[
            ['game_id', 'season', 'week', 'result', 'spread_line', 'q', 'p']]
    if LEDGER_CSV.exists():
        l = pd.read_csv(LEDGER_CSV, low_memory=False)
        sets['2021-26 ledger (2021-25 in-sample)'] = l.rename(
            columns={'market_wp': 'q', 'model_wp': 'p'})[
            ['game_id', 'season', 'week', 'result', 'spread_line', 'q', 'p']]
    if not sets:
        raise SystemExit('no evaluation inputs found')
    return sets


def evaluate(games, frame):
    d = frame.dropna(subset=['result', 'spread_line', 'q', 'p']).copy()
    if d.empty:
        return None
    parts = []
    for yr, g in d.groupby('season'):
        hist = games[(games.season < yr) & (games.season >= FIRST_FIT_SEASON)]
        if len(hist) < 1000:
            continue
        mm = MarginModel(hist)
        g = g.copy()
        g['s_q_probit'] = probit_spread(g.q)
        g['s_m_probit'] = probit_spread(g.p)
        g['s_q'] = mm.spread_from_prob(g.q)
        g['s_m'] = mm.spread_from_prob(g.p)
        g['wp_line'] = mm.win_prob(g.spread_line)
        g['c_q'] = mm.cover_prob(g.s_q, g.spread_line)
        g['c_m'] = mm.cover_prob(g.s_m, g.spread_line)
        parts.append(g)
    return pd.concat(parts, ignore_index=True) if parts else None


def report(name, d, lines):
    fav = np.sign(d.spread_line).replace(0, 1)
    d['lb'] = pd.cut(d.spread_line.abs(), LINE_BUCKETS, labels=LINE_LABELS)
    gaps = pd.DataFrame({
        'n': d.groupby('lb', observed=True).size(),
        'probit gap': d.assign(x=fav * (d.s_q_probit - d.spread_line)).groupby('lb', observed=True).x.mean(),
        'empirical gap': d.assign(x=fav * (d.s_q - d.spread_line)).groupby('lb', observed=True).x.mean(),
    }).round(2)
    lines.append(f'\n## {name}  (n={len(d)})\n')
    lines.append('### 1. Market q converted to a spread, minus the posted line (toward favorite, pts)\n')
    lines.append(gaps.to_markdown())
    for lab, col in [('probit', 's_q_probit'), ('empirical', 's_q')]:
        g = (d[col] - d.spread_line).abs()
        lines.append(f'- {lab}: MAE {g.mean():.2f} pts; share >= 1 pt {np.mean(g >= 1):.0%}; >= 2 pt {np.mean(g >= 2):.0%}')
    lines.append(f'- win prob at the posted line vs no-vig q, MAE: empirical {np.mean(np.abs(d.wp_line - d.q)):.3f}; '
                 f'probit {np.mean(np.abs(_probit_wp(d.spread_line) - d.q)):.3f}')

    m = d.result - d.spread_line
    dd = d[(m != 0) & d.c_q.notna() & d.c_m.notna()].copy()
    y = (dd.result > dd.spread_line).astype(float).to_numpy()
    cl = (dd.season.astype(str) + '_' + dd.week.astype(str)).to_numpy()
    lines.append('\n### 2. Home-cover LPM, week-clustered SE (probability space)\n')
    for label, X in [('market (c_q - .5)', dd[['c_q']].to_numpy() - .5),
                     ('model departure (c_m - c_q)', (dd.c_m - dd.c_q).to_numpy()[:, None]),
                     ('both', np.c_[dd.c_q - .5, dd.c_m - dd.c_q])]:
        b, se = cluster_lpm(y, X, cl)
        lines.append(f'- {label}: ' + ', '.join(f'{bi:+.2f} ± {si:.2f} (t {bi / si:+.1f})' for bi, si in zip(b, se)))

    lines.append('\n### 3. Pick agreement\n')
    raw_old = np.sign(d.s_m_probit - d.spread_line)
    q_old = np.sign(d.s_q_probit - d.spread_line)
    raw_new = np.sign(d.c_m - .5)
    q_new = np.sign(d.c_q - .5)
    lines.append(f'- probit raw picks identical to q-only picks: {np.mean(raw_old == q_old):.0%}')
    lines.append(f'- empirical raw picks identical to q-only picks: {np.mean(raw_new == q_new):.0%}')
    lines.append(f'- empirical raw picks identical to probit raw picks: {np.mean(raw_new == raw_old):.0%}')

    lines.append('\n### 4. Records (flat 1u at -110, pushes excluded from cover %)\n')
    rows = []
    pushes = int((d.result == d.spread_line).sum())
    for label, side in [('probit raw edge', raw_old), ('empirical raw (c_m vs .5)', raw_new),
                        ('pure model departure (c_m vs c_q)', np.sign(d.c_m - d.c_q))]:
        ok = (m != 0) & (side != 0) & np.isfinite(side)
        r = record((side[ok] * m[ok] > 0))
        rows.append(dict(rule=label, **r))
    lines.append(pd.DataFrame(rows).round(3).to_markdown(index=False))

    dd['edge'] = (dd.c_m - .5).abs()
    dd['side'] = np.sign(dd.c_m - .5)
    dd['won'] = (dd.side * (dd.result - dd.spread_line) > 0).astype(int)
    dd['eb'] = pd.cut(dd.edge, EDGE_BUCKETS)
    t = dd.groupby('eb', observed=True).won.agg(n='size', cover='mean')
    t['se'] = np.sqrt(t.cover * (1 - t.cover) / t.n)
    lines.append('\n### 5. Empirical raw: cover % by |c_m - 0.5|\n')
    lines.append(t.round(3).to_markdown())
    dd['dep'] = (dd.c_m - dd.c_q).abs()
    dd['side2'] = np.sign(dd.c_m - dd.c_q)
    dd['won2'] = (dd.side2 * (dd.result - dd.spread_line) > 0).astype(int)
    dd['db'] = pd.cut(dd.dep, EDGE_BUCKETS)
    t2 = dd[dd.side2 != 0].groupby('db', observed=True).won2.agg(n='size', cover='mean')
    t2['se'] = np.sqrt(t2.cover * (1 - t2.cover) / t2.n)
    lines.append('\n### 6. Pure model departure: cover % by |c_m - c_q|\n')
    lines.append(t2.round(3).to_markdown())


def _probit_wp(line):
    from scipy.special import ndtr
    return ndtr(np.asarray(line, float) / MARKET_SIGMA)


def main():
    if not GAMES_CSV.exists():
        raise SystemExit(f'missing {GAMES_CSV}')
    games = pd.read_csv(GAMES_CSV)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# Key-number-aware conversion: results\n',
             'Research only. Distribution for season Y is fit on nflverse games with seasons < Y '
             f'(from {FIRST_FIT_SEASON}). Triangular kernel on |line|, bandwidth {BANDWIDTH} '
             f'widened by {BANDWIDTH_STEP} until effective n >= {MIN_EFFECTIVE:.0f}.\n']
    # calibration of the conversion itself: pmf at the line should reproduce the line
    mm = MarginModel(games[games.season < 2026])
    chk = pd.DataFrame({'line': [1, 2.5, 3, 3.5, 6.5, 7, 7.5, 10, 14]})
    chk['win_prob'] = mm.win_prob(chk.line)
    chk['P(fav margin > line | no push)'] = mm.cover_prob(chk.line, chk.line)
    chk['probit win_prob'] = _probit_wp(chk.line)
    lines.append('\n## 0. Conversion check (fit on 1999-2025)\n')
    lines.append(chk.round(3).to_markdown(index=False))
    for name, frame in load_eval_sets().items():
        d = evaluate(games, frame)
        if d is None or d.empty:
            lines.append(f'\n## {name}: no evaluable rows')
            continue
        report(name, d, lines)
        d.to_csv(OUT_DIR / f"rows_{name.split()[0]}.csv", index=False)
    text = '\n'.join(lines) + '\n'
    (OUT_DIR / 'REPORT.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
