"""Test 29: shrink each stat by its own reliability.

    python research/stat_shrinkage.py [CACHE_DIR]     # ~12 min warm

Plan and decision rule: research/README.md, Tests 29-31 (committed before any result).
Production pulls every profile toward the league average with PRIOR_EQUIVALENT_GAMES (4)
pseudo-games, and the point margin toward zero with the same 4. Here each core rate and
side (offense 'for', defense 'allowed') and the margin get their own k = n(1 - r)/r,
clamped to [1, 64], from the odd/even-game split-half correlation r over 2019-22
team-seasons (n = mean games per half). k replaces 4 in the raw profile, as the ridge on
the opponent-adjusted offense or defense effects, and for the margin. Everything else is
v1.12. With every k = 4 the replacement columns must equal production's.
"""
import numpy as np
import pandas as pd

from _common import LAST, availability, cache_dir_from_argv, load_inputs, log, m, outer, primary_row, report_family, \
    same_rows, score

K_SEASONS = (2019, 2020, 2021, 2022)
K_MIN, K_MAX = 1., 64.
LEVEL = 1 - .05 / 3
ROLES = (('for', ''), ('allowed', 'opp_'))


def _with_opponent_and_margin(box, sched):
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_' + c for c in m.COUNTS}})
    both = box.merge(opp, on=['game_id', 'opponent'], how='left', validate='one_to_one')
    res = (sched[['game_id', 'home_team', 'result']].drop_duplicates('game_id')
           .rename(columns={'home_team': '_margin_home', 'result': '_margin_result'}))
    both = both.merge(res, on='game_id', how='left', validate='many_to_one')
    both['margin'] = np.where(both.team == both._margin_home, both._margin_result, -both._margin_result).astype(float)
    return both


def k_from_r(r, n):
    return K_MAX if not np.isfinite(r) or r <= 0 else float(np.clip(n * (1 - r) / r, K_MIN, K_MAX))


def reliability_k(box, sched, seasons=K_SEASONS):
    """{(role, metric): k, 'margin': k} from odd/even-game split halves of `seasons`, and the table."""
    b = _with_opponent_and_margin(box[box.season.isin(seasons)], sched)
    b = b.sort_values(['team', 'season', 'week', 'game_id'])
    b['half'] = b.groupby(['team', 'season']).cumcount() % 2
    g = b.groupby(['team', 'season', 'half'])
    n = float(g.size().mean())
    k, rows = {}, []
    for metric, (num, den, _) in m.RATES_CORE.items():
        for role, pre in ROLES:
            v = (g[pre + num].sum() / (g[pre + den].sum() if den else g.size())).unstack('half')
            r = float(v[0].corr(v[1])); k[(role, metric)] = k_from_r(r, n)
            rows.append({'stat': f'{role} {metric}', 'r': r, 'k': k[(role, metric)]})
    v = g.margin.mean().unstack('half'); r = float(v[0].corr(v[1])); k['margin'] = k_from_r(r, n)
    rows.append({'stat': 'point margin', 'r': r, 'k': k['margin']})
    return k, pd.DataFrame(rows), n


def metric_profile_k(values, weights, league, specs, kmap):
    """nfl_model.metric_profile with a pseudo-game count per metric."""
    ix = {c: i for i, c in enumerate(m.COUNTS)}; out = {}
    for name, (num, den, mult) in specs.items():
        a = values[:, ix[num]]; b = np.ones(len(values)) if den is None else values[:, ix[den]]
        la = league[:, ix[num]]; lb = np.ones(len(league)) if den is None else league[:, ix[den]]
        lok = np.isfinite(la) & np.isfinite(lb) & (lb > 0)
        if not lok.any(): out[name] = np.nan; continue
        pa, pb = float(la[lok].mean()), float(lb[lok].mean())
        ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
        numer = float(np.dot(weights[ok], a[ok])) + kmap[name] * pa
        denom = float(np.dot(weights[ok], b[ok])) + kmap[name] * pb
        out[name] = mult * numer / denom if denom > 0 else np.nan
    return out


def opponent_adjust_k(offense, defense, num, den, weights, k_off, k_def):
    """nfl_model.opponent_adjust with separate prior games for offense and defense effects."""
    offense = np.asarray(offense); defense = np.asarray(defense)
    num = np.asarray(num, float); den = np.asarray(den, float); weights = np.asarray(weights, float)
    ok = np.isfinite(num) & np.isfinite(den) & (den > 0) & np.isfinite(weights) & (weights > 0)
    if not ok.any(): return np.nan, {}, {}
    teams = sorted(set(offense[ok]) | set(defense[ok])); ix = {t: i for i, t in enumerate(teams)}; T = len(teams)
    n = int(ok.sum()); X = np.zeros((n, 1 + 2 * T)); X[:, 0] = 1.
    X[np.arange(n), 1 + np.array([ix[t] for t in offense[ok]])] = 1.
    X[np.arange(n), 1 + T + np.array([ix[t] for t in defense[ok]])] = 1.
    y = num[ok] / den[ok]; w = weights[ok] * den[ok]
    A = X.T @ (w[:, None] * X); b = X.T @ (w * y)
    md = float(np.mean(den[ok]))
    A[1:1 + T, 1:1 + T] += k_off * md * np.eye(T); A[1 + T:, 1 + T:] += k_def * md * np.eye(T)
    beta = np.linalg.solve(A, b)
    return float(beta[0]), dict(zip(teams, beta[1:1 + T])), dict(zip(teams, beta[1 + T:]))


def profile_columns(box, sched, half_life, k):
    """The d__ columns production builds from profiles (raw and opponent-adjusted core rates,
    point margin), recomputed with per-stat k, exactly as nfl_model.lagged_features does."""
    both = _with_opponent_and_margin(box, sched)
    recs = []
    for (year, week), games in sched.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        hist = both[m.before(both, year, week) & (both.season >= year - m.MAX_HISTORY_SEASONS)]
        league = hist[list(m.COUNTS)].to_numpy(float)
        prof = {}
        for team in set(games.home_team) | set(games.away_team):
            h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
            age = np.arange(len(h) - 1, -1, -1, dtype=float)
            w = np.exp2(-age / half_life) * np.power(m.OFFSEASON_RETENTION, year - h.season.to_numpy(float))
            mg = h.margin.to_numpy(float); ok = np.isfinite(mg)
            p = {'margin': float(np.dot(w[ok], mg[ok]) / (w[ok].sum() + k['margin']))}
            for role, pre in ROLES:
                vals = h[[pre + c for c in m.COUNTS]].to_numpy(float)
                kmap = {mt: k[(role, mt)] for mt in m.RATES_CORE}
                for mt, v in metric_profile_k(vals, w, league, m.RATES_CORE, kmap).items():
                    p[f'{role}__rates_core__{mt}'] = v
            prof[team] = p
        ix = {c: i for i, c in enumerate(m.COUNTS)}
        if len(hist):
            slot = (hist.season.astype(int) * 100 + hist.week.astype(int)).to_numpy()
            uniq = np.unique(slot); slot_age = (len(uniq) - 1 - np.searchsorted(uniq, slot)).astype(float)
            decay = np.exp2(-slot_age / half_life) * np.power(m.OFFSEASON_RETENTION, year - hist.season.to_numpy(float))
            hv = hist[list(m.COUNTS)].to_numpy(float)
        for mt, (num, den, mult) in m.RATES_CORE.items():
            if len(hist):
                a = hv[:, ix[num]]; d = np.ones(len(hv)) if den is None else hv[:, ix[den]]
                mu, off, dfn = opponent_adjust_k(hist.team.to_numpy(), hist.opponent.to_numpy(), a, d, decay,
                                                 k[('for', mt)], k[('allowed', mt)])
            else: mu, off, dfn = np.nan, {}, {}
            for team in prof:
                prof[team][f'for__rates_core_adj__{mt}'] = mult * (mu + off.get(team, 0.))
                prof[team][f'allowed__rates_core_adj__{mt}'] = mult * (mu + dfn.get(team, 0.))
        for g in games.itertuples(index=False):
            hp, ap = prof[g.home_team], prof[g.away_team]
            recs.append({'game_id': g.game_id, **{'d__' + name: hp[name] - ap[name] for name in hp}})
    return pd.DataFrame(recs)


def with_k(features, box, sched, half_life, k):
    """features with the profile-derived columns replaced by their per-stat-k versions."""
    cols = profile_columns(box, sched, half_life, k).set_index('game_id')
    out = features.copy()
    for c in cols.columns: out[c] = out.game_id.map(cols[c]).to_numpy()
    return out, list(cols.columns)


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched, box = inp['sched'], inp['box']
    k, table, n = reliability_k(box, sched)
    print(f'\nk per stat (2019–22 split halves, {n:.2f} games per half):')
    print(table.round(3).to_string(index=False))
    avail = availability(inp)
    prod = {h: m.lagged_features(box, sched, h, avail) for h in m.TEAM_HALF_LIVES}
    check, cols = with_k(prod[8.], box, sched, 8., {key: m.PRIOR_EQUIVALENT_GAMES for key in k})
    for c in cols:
        if not np.allclose(check[c].to_numpy(float), prod[8.][c].to_numpy(float), equal_nan=True, rtol=0, atol=1e-9):
            raise ValueError(f'k = 4 does not reproduce production column {c}')
    log(f'k = 4 reproduces all {len(cols)} production profile columns')
    var = {h: with_k(prod[h], box, sched, h, k)[0] for h in m.TEAM_HALF_LIVES}
    log('features built')
    fams = tuple(m.FEATURE_FAMILIES)
    held, picks, sc = {}, {}, {}
    for name, feats in (('production (v1.12)', prod), ('Test 29: per-stat k', var)):
        oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
        held[name], picks[name] = outer(oof, fams); sc[name] = score(held[name])
        log(f'{name} picks {picks[name]}')
    same_rows(*held.values())
    print('\n### Test 29 result\n\n| Arm | LL gain vs production [98.33% CI] | ± SE | Verdict |\n|---|---:|---:|---|')
    d = sc['production (v1.12)']['ll_vec'] - sc['Test 29: per-stat k']['ll_vec']
    primary_row('Test 29: per-stat k', d, LEVEL,
                # below zero or under +0.001 at its upper end: dropped (too small to matter wins over lo > 0)
                lambda mean, lo, hi: 'dropped' if hi < .001 else 'supported' if lo > 0 else 'unresolved')
    report_family(held['production (v1.12)'], sc, LEVEL)
    log('done')


if __name__ == '__main__':
    main()
