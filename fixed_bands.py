"""Reporting-only fixed-band spread calibration, adopted 2026-10-15.

Reproduce the supplied previous_fixed_bands procedure: sign-preserving monotone
integer magnitudes 0..21, cuts 3/7/10, maximum training W-L, >=90% coverage.
Training excludes tied games, uses seasons strictly before the target season,
and requires two seasons and 30 observations per band. Evaluation includes ties.
This exposed historical calibration is not native forward evidence.
"""
import numpy as np
import pandas as pd

CUTS = [3., 7., 10.]
EPS = 1e-10
BANDS = ['<3', '3–<7', '7–<10', '10+']


def fit(history, season):
    d = history[(history.season < season) & history['home won'].isin([0., 1.])]
    d = d.dropna(subset=['model_spread', 'spread_line', 'result'])
    if d.season.nunique() < 2:
        return None
    band = np.digitize(d.model_spread.abs(), CUTS)
    counts = np.bincount(band, minlength=4)
    if min(counts) < 30:
        return None
    grid = np.arange(22, dtype=float)
    # Optimize reward AND >=90% selection coverage jointly. The previous
    # procedure chose the unconstrained W-L maximum and rejected it if too
    # many exact market equalities skipped; a feasible runner-up was missed.
    scores, coverage = [], []
    for k in range(4):
        g = d.iloc[np.flatnonzero(band == k)]
        pred = np.sign(g.model_spread.to_numpy())[:, None] * grid
        edge = pred - g.spread_line.to_numpy()[:, None]
        side = np.where(np.abs(edge) <= EPS, 0., np.sign(edge))
        reward = np.sign(side * (g.result - g.spread_line).to_numpy()[:, None]).sum(0)
        distance = ((pred - g.model_spread.to_numpy()[:, None]) ** 2).mean(0)
        scores.append(reward - 1e-8 * distance)
        coverage.append(np.count_nonzero(np.abs(edge) > EPS, axis=0))
    minimum = int(np.ceil(.90 * len(d) - 1e-12))
    # (selected_games, last_magnitude_index) -> (objective, 4-band path).
    # The state includes coverage so dropping a skip-heavy partial solution
    # cannot inadvertently discard the best feasible monotone map.
    states = {(int(coverage[0][j]), j): (float(scores[0][j]), (j,))
              for j in range(len(grid))}
    for k in range(1, 4):
        following = {}
        for (selected, previous), (value, path) in states.items():
            for j in range(previous, len(grid)):
                key = (selected + int(coverage[k][j]), j)
                candidate = (value + float(scores[k][j]), path + (j,))
                incumbent = following.get(key)
                if incumbent is None or (candidate[0], tuple(-m for m in candidate[1])) > (
                        incumbent[0], tuple(-m for m in incumbent[1])):
                    following[key] = candidate
        states = following
    feasible = [v for (selected, _), v in states.items() if selected >= minimum]
    if not feasible:
        return None
    winner = max(feasible, key=lambda v: (v[0], tuple(-m for m in v[1])))
    magnitudes = grid[list(winner[1])]
    return dict(season=int(season), training_max_season=int(d.season.max()),
                training_games=len(d), cuts=CUTS, magnitudes=magnitudes.tolist())


def apply(spread, rule):
    x = np.asarray(spread, dtype=float)
    if rule is None:
        return np.full(x.shape, np.nan)
    return np.where(np.isfinite(x), np.sign(x) * np.asarray(rule['magnitudes'])[
        np.digitize(np.abs(x), rule['cuts'])], np.nan)


def grade(frame, prediction):
    """Grade against the signed home market margin; zero edge skips before pushes."""
    edge = np.asarray(prediction, float) - frame.spread_line.to_numpy(float)
    margin = frame.result.to_numpy(float) - frame.spread_line.to_numpy(float)
    side = np.sign(edge)
    result = np.where(~np.isfinite(edge), '', np.where(abs(edge) <= EPS, 'S',
             np.where(~np.isfinite(margin), '', np.where(abs(margin) <= EPS, 'P',
             np.where(side * margin > 0, 'W', 'L')))))
    units = np.where(result == 'W', 1 / 1.1, np.where(result == 'L', -1.,
            np.where(np.isin(result, ['P', 'S']), 0., np.nan)))
    return result, units


def prepare(latest):
    history = latest.get('retro_ledger', pd.DataFrame()).copy()
    if history.empty:
        return
    if 'model_spread' not in history:
        # Older snapshots may only contain probabilities.
        import nfl_model as m
        history['model_spread'] = m.implied_spread(history.model_wp)
    rules = {}
    board = latest.get('board', pd.DataFrame()).copy()
    seasons = set(history.season.astype(int))
    if len(board):
        seasons.update(board.season.astype(int))
    for year in sorted(seasons):
        rules[year] = fit(history, year)
    history['fixed_band_spread'] = np.nan
    for year, rule in rules.items():
        mask = history.season == year
        history.loc[mask, 'fixed_band_spread'] = apply(history.loc[mask, 'model_spread'], rule)
    for prefix, col in [('original', 'model_spread'), ('fixed_band', 'fixed_band_spread')]:
        history[prefix + '_ats_result'], history[prefix + '_ats_units'] = grade(history, history[col])
        edge = history[col] - history.spread_line
        history[prefix + '_ats_side'] = np.where(~np.isfinite(edge) | (abs(edge) <= EPS), '',
                                                 np.where(edge > 0, 'home', 'away'))
        side = history[prefix + '_ats_side']
        history[prefix + '_ats_team'] = np.where(side == 'home', history.home,
                                                 np.where(side == 'away', history.away, ''))
        history[prefix + '_ats_handicap'] = np.where(side == 'home', -history.spread_line,
                                                     np.where(side == 'away', history.spread_line, np.nan))
    history['spread_band'] = np.asarray(BANDS)[np.digitize(history.model_spread.abs(), CUTS)]
    latest['fixed_band_ledger'] = history
    latest['fixed_band_rules'] = [r for r in rules.values() if r is not None]
    if len(board):
        if 'model_spread' not in board:
            import nfl_model as m
            board['model_spread'] = m.implied_spread(board.model_wp)
        board['fixed_band_spread'] = np.nan
        for year, rule in rules.items():
            mask = board.season == year
            board.loc[mask, 'fixed_band_spread'] = apply(board.loc[mask, 'model_spread'], rule)
        latest['board'] = board


def summary(frame):
    rows = []
    # Compare both methods on the same eligible games, including tied finals.
    d = frame[frame.fixed_band_spread.notna() & frame.result.notna() & frame.spread_line.notna()]
    for group, g in [('All', d), *list(d.groupby('season', sort=True))]:
        for prefix, label in [('original', 'Original spread'), ('fixed_band', 'Fixed bands')]:
            r = g[prefix + '_ats_result']
            w, l, p, s = [int((r == x).sum()) for x in ['W', 'L', 'P', 'S']]
            bets = w + l + p
            units = w / 1.1 - l
            if bets + s != len(g):
                raise AssertionError("Every eligible ATS opportunity must be selected or skipped")
            rows.append(dict(season=str(group), method=label, games=len(g),
                             opportunities=len(g), bets=bets, selected=bets,
                             wins=w, losses=l, pushes=p, skips=s,
                             selection_rate=bets / len(g) if len(g) else np.nan,
                             units=units, roi=units / bets if bets else np.nan))
    return pd.DataFrame(rows)
