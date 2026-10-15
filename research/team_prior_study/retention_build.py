"""Continuity-conditioned OFFSEASON_RETENTION profile variants (research build only; no outcomes scored).

POST HOC: these arms were added after the earlier team-prior variants (league_level, team_window,
team_prior, continuity, coach, qb_offense, none) had already been scored on 2015-2025. 2015-2025 are
exposed development history; anything scored on this file is exploratory, never confirmation.

Production v1.18 (nfl_model.lagged_features) weights each prior team-game by
    2^(-age/8) * OFFSEASON_RETENTION^(year - season),  OFFSEASON_RETENTION = 0.5,
with 4 pseudo-games at the LEAGUE target. Here the pseudo-game target stays the production league target;
only the season-boundary retention changes, per team-game:
    multiplier for a history game of season s = prod_{b=s+1..year} r_b,
    r_b = r_cont if the team's regime is continuous across boundary (b-1 -> b), r_change otherwise.
Boundary continuity (pregame only):
  * current boundary (year-1 -> year): identical to build_team_prior_profiles.py's gate:
      coach of THIS game == coach of the team's last REG game of year-1   (coach_change False)
      AND starter of the team's most recent EARLIER REG game == year-1 primary starter (qb_change False)
  * older boundaries b in {year-1, year-2} (completed seasons, so every input is from earlier games):
      opening coach of season b (first REG game) == coach of the team's last REG game of b-1
      AND primary starter of season b (most starts; tie -> latest start) == primary starter of b-1
    This is the season-level definition already used for the persistence splits in eval_stat_prediction.py.
  * unknown flag (never happens from 2015): r = 0.5 (production), counted in the validation json.
Arms:      retention_cont_75_25 (0.75 / 0.25), retention_cont_50_25 (0.5 / 0.25)
Controls:  retention_flat_75 (0.75 everywhere), retention_flat_25 (0.25 everywhere), written to a
           separate file; they separate 'continuity matters' from 'a different retention level matters'.
League:    (0.5, 0.5) through the SAME generalized code path; must reproduce production bit for bit.

Weighting/profile arithmetic is copied (not imported, not edited) from
agent_scratch/build_team_prior_profiles.py.
Reads only: research/form_windows_inputs/{boxes,schedule}.csv, dl/games.csv (data), team_prior/profiles.csv.gz.
Writes only: team_prior/retention_profiles.csv.gz, team_prior/retention_controls_profiles.csv.gz,
             team_prior/retention_build_*.csv, agent_scratch/retention_validation.json.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

from paths import ROOT, WORK, GAMES_CSV  # noqa: E402
MAIN = ROOT
sys.path.insert(0, str(MAIN))
import nfl_model as m  # noqa: E402

BOXES = MAIN/'research/form_windows_inputs/boxes.csv'
SCHED = MAIN/'research/form_windows_inputs/schedule.csv'
GAMES = GAMES_CSV
EXISTING = WORK/'profiles.csv.gz'
OUT = WORK
SCRATCH = WORK
FIRST_OUTPUT_SEASON = 2015

FAMILY = m.LEGACY_PRODUCT_RECIPE['family']
HALF = float(m.LEGACY_PRODUCT_RECIPE['half_life'])
PASS_HALF = float(m.LEGACY_PRODUCT_RECIPE['pass_half_life'])
K = m.PRIOR_EQUIVALENT_GAMES
SPECS = m.FAMILIES['rates_core']
NAMES = m.feature_names(FAMILY)
RATE_FEATURES = [n for n in NAMES if n.startswith('d__for__') or n.startswith('d__allowed__')]
ROLE_METRICS = [(n.split('__')[1], n.split('__')[3]) for n in RATE_FEATURES]
USED = {}
for role, metric in ROLE_METRICS: USED.setdefault(role, []).append(metric)
PEAKS = list(m.PEAK_COLUMNS)
PROFILE_COLS = [f'{r}__rates_core__{mt}' for r, mt in ROLE_METRICS]+PEAKS
EXTRA_COLS = ['margin']
PASS_METRIC = 'net_pass_yards_per_pass_play'
H16_COLS = [f'h16__{r}__rates_core__{PASS_METRIC}' for r in ('for', 'allowed')]
OPP = ['opp_'+c for c in m.COUNTS]
IX = {c: i for i, c in enumerate(m.COUNTS)}
P0 = float(m.OFFSEASON_RETENTION)   # 0.5
ARMS = {'retention_cont_75_25': (.75, .25), 'retention_cont_50_25': (P0, .25)}
CONTROLS = {'retention_flat_75': (.75, .75), 'retention_flat_25': (.25, .25)}
SCHEMES = {'league': (P0, P0), **ARMS, **CONTROLS}
MAIN_VARIANTS = ['league', *ARMS]
CONTROL_VARIANTS = list(CONTROLS)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# --- copied from build_team_prior_profiles.py ------------------------------------------------------
def schedule_frame(s):
    s = m.normalize_teams(s.copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.get('location', pd.Series('', index=s.index)).astype(str).str.lower() == 'neutral', 0., 1.)
    s['market WP'] = ndtr(pd.to_numeric(s.spread_line, errors='coerce')/m.MARKET_SIGMA)
    return s


def team_games(games_csv):
    g = pd.read_csv(games_csv, low_memory=False)
    g = g[g.game_type == 'REG'].copy()
    parts = []
    for side, other in (('home', 'away'), ('away', 'home')):
        t = g[['game_id', 'season', 'week', f'{side}_team', f'{other}_team', f'{side}_coach', f'{side}_qb_id', f'{side}_qb_name', 'result']].copy()
        t.columns = ['game_id', 'season', 'week', 'team', 'opponent', 'coach', 'qb_id', 'qb_name', 'result']
        parts.append(t)
    t = pd.concat(parts, ignore_index=True)
    t = m.normalize_teams(t)
    t['played'] = t.result.notna()
    p = t[t.played & t.qb_id.notna()]
    by_name = p.groupby(['qb_name', 'qb_id']).size().reset_index(name='n')
    names_per_id = p.groupby('qb_id').qb_name.nunique()
    remap = {}
    for name, d in by_name.groupby('qb_name'):
        if len(d) < 2: continue
        major = d.sort_values('n', ascending=False).iloc[0]
        for r in d.itertuples():
            if r.qb_id != major.qb_id and names_per_id[r.qb_id] == 1 and r.n < major.n:
                remap[r.qb_id] = major.qb_id
    t['qb_id_raw'] = t.qb_id
    t['qb_id'] = t.qb_id.replace(remap)
    disp = (t[t.played & t.qb_id.notna()].groupby(['qb_id', 'qb_name']).size().reset_index(name='n')
            .sort_values(['qb_id', 'n'], ascending=[True, False]).drop_duplicates('qb_id').set_index('qb_id').qb_name)
    if t.duplicated(['game_id', 'team']).any(): raise ValueError('duplicate team-game in games.csv')
    return t, remap, disp


def pregame_lookups(tg):
    """As the builder, plus the opening coach (first played REG game) per (team, season)."""
    pl = tg[tg.played].sort_values(['season', 'week', 'game_id'])
    last_coach = pl.groupby(['team', 'season']).coach.last().to_dict()
    first_coach = pl.groupby(['team', 'season']).coach.first().to_dict()
    prim = {}
    for (team, season), d in pl.groupby(['team', 'season']):
        d = d[d.qb_id.notna()]
        if d.empty: continue
        st = d.groupby('qb_id').agg(n=('qb_id', 'size'), last=('week', 'max')).sort_values(['n', 'last'], ascending=False)
        prim[(team, season)] = (st.index[0], int(st.n.iloc[0]), int(len(d)))
    seq = {team: (d.season.to_numpy(int), d.week.to_numpy(int), d.qb_id.tolist(), d.coach.tolist()) for team, d in pl.groupby('team')}
    return last_coach, prim, seq, first_coach


def recent_start(seq, team, year, week):
    a = seq.get(team)
    if a is None: return None, None
    ss, ww, qq, cc = a
    ok = (ss < year) | ((ss == year) & (ww < week))
    if not ok.any(): return None, None
    i = int(np.flatnonzero(ok)[-1])
    return (qq[i] if isinstance(qq[i], str) else None), cc[i]


def target_means(T, specs):
    out = {}
    for name, (num, den, mult) in specs.items():
        la = T[:, IX[num]]
        lb = np.ones(len(T)) if den is None else T[:, IX[den]]
        lok = np.isfinite(la) & np.isfinite(lb) & (lb > 0)
        out[name] = (float(la[lok].mean()), float(lb[lok].mean())) if lok.any() else None
    return out


def profile(values, weights, targ, specs, k=K):
    out = {}
    for name, (num, den, mult) in specs.items():
        a = values[:, IX[num]]
        b = np.ones(len(values)) if den is None else values[:, IX[den]]
        ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
        if targ.get(name) is None: out[name] = np.nan; continue
        pa, pb = targ[name]
        numer = float(np.dot(weights[ok], a[ok]))+k*pa
        denom = float(np.dot(weights[ok], b[ok]))+k*pb
        out[name] = mult*numer/denom if denom > 0 else np.nan
    return out


def scalar_profile(x, w, t, k, masked):
    x = np.asarray(x, float)
    if masked:
        ok = np.isfinite(x); x, w = x[ok], w[ok]
    return float((np.dot(w, x)+k*t)/(w.sum()+k)) if t != 0. else float(np.dot(w, x)/(w.sum()+k))


SUB = {r: {mt: SPECS[mt] for mt in USED[r]} for r in USED}
SUB16 = {mt: SPECS[mt] for mt in (PASS_METRIC,)}


# --- new: boundary continuity and retention multipliers ----------------------------------------------
def season_continuity(lookups):
    """(team, b) -> True/False/None: regime continuous across boundary b-1 -> b, using only seasons b-1 and b
    (complete). Used only for boundaries b < forecast year."""
    last_coach, prim, seq, first_coach = lookups
    out, parts = {}, {}
    for (team, b), fc in first_coach.items():
        lc = last_coach.get((team, b-1)); p1 = prim.get((team, b)); p0 = prim.get((team, b-1))
        coach_same = None if (fc is None or lc is None) else bool(fc == lc)
        qb_same = None if (p1 is None or p0 is None) else bool(p1[0] == p0[0])
        out[(team, b)] = None if (coach_same is None or qb_same is None) else (coach_same and qb_same)
        parts[(team, b)] = (coach_same, qb_same)
    return out, parts


def boundary_factors(cont_by_b, r_cont, r_change):
    """cont_by_b: {b: True/False/None}. Returns {b: r_b}; unknown -> production 0.5."""
    return {b: (P0 if c is None else (r_cont if c else r_change)) for b, c in cont_by_b.items()}


def season_multipliers(year, r_by_b):
    """{history season s: prod_{b=s+1..year} r_b} for s = year .. year-MAX_HISTORY_SEASONS."""
    mult, acc = {year: 1.}, 1.
    for b in range(year, year-m.MAX_HISTORY_SEASONS, -1):
        acc = acc*r_by_b[b]
        mult[b-1] = acc
    return mult


def build(box, sched, tg, lookups, years=None, check_production=True):
    last_coach, prim, seq, first_coach = lookups
    scont, _ = season_continuity(lookups)
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    both = box.merge(opp, on=['game_id', 'opponent'], how='left', validate='one_to_one')
    res = sched[['game_id', 'home_team', 'result']].drop_duplicates('game_id').rename(columns={'home_team': '_h', 'result': '_r'})
    both = both.merge(res, on='game_id', how='left', validate='many_to_one')
    both['margin'] = np.where(both.team == both._h, both._r, -both._r).astype(float)
    cur_coach = tg.set_index(['game_id', 'team']).coach.to_dict()
    prof, info = {}, {}
    chk = {'rates_max_abs': 0., 'peaks_margin_max_abs': 0., 'retention_weight_max_abs': 0., 'team_weeks': 0, 'unknown_flags': 0}
    for (year, week), games in sched.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        if years is not None and year not in years: continue
        hist = both[m.before(both, year, week) & (both.season >= year-m.MAX_HISTORY_SEASONS)]
        league = hist[list(m.COUNTS)].to_numpy(float)
        LT = {r: target_means(league, SUB[r]) for r in SUB}
        LT16 = target_means(league, SUB16)
        h_team = hist.team.to_numpy()
        teams = {}
        for g in games.itertuples(index=False):
            teams[g.home_team] = g.game_id; teams[g.away_team] = g.game_id
        for team, gid in teams.items():
            h = hist[h_team == team].sort_values(['season', 'week', 'game_id'])
            n = len(h)
            age = np.arange(n-1, -1, -1, dtype=float)
            hs = h.season.to_numpy(int)
            vals = {'for': h[list(m.COUNTS)].to_numpy(float), 'allowed': h[OPP].to_numpy(float)}
            # current boundary: the builder's coach_change / qb_change (this game's QB never used)
            coach = cur_coach.get((gid, team)); pcoach = last_coach.get((team, year-1))
            rqb, _ = recent_start(seq, team, year, week)
            pq = prim.get((team, year-1)); pqb = pq[0] if pq else None
            coach_change = None if (coach is None or pcoach is None) else bool(coach != pcoach)
            qb_change = None if (rqb is None or pqb is None) else bool(rqb != pqb)
            cont = {year: None if (coach_change is None or qb_change is None) else (not coach_change and not qb_change)}
            for b in range(year-1, year-m.MAX_HISTORY_SEASONS, -1):   # year-1, year-2: completed seasons only
                cont[b] = scont.get((team, b))
            # unknown flags only matter if a history game sits behind that boundary
            for b, c in cont.items():
                if c is None and (hs < b).any(): chk['unknown_flags'] += 1
            out, mults = {}, {}
            for v, (rc, rx) in SCHEMES.items():
                mult = season_multipliers(year, boundary_factors(cont, rc, rx))
                ret = np.array([mult[s] for s in hs], float)
                w8 = np.exp2(-age/HALF)*ret
                w16 = np.exp2(-age/PASS_HALF)*ret
                r = {}
                for role in SUB:
                    for mt, val in profile(vals[role], w8, LT[role], SUB[role]).items():
                        r[f'{role}__rates_core__{mt}'] = val
                for c in PEAKS:
                    r[c] = scalar_profile(h[c].to_numpy(float), w8, 0., K, masked=False)
                r['margin'] = scalar_profile(h.margin.to_numpy(float), w8, 0., K, masked=True)
                r[H16_COLS[0]] = profile(vals['for'], w16, LT16, SUB16)[PASS_METRIC]
                r[H16_COLS[1]] = profile(vals['allowed'], w16, LT16, SUB16)[PASS_METRIC]
                r['target_source'] = 'league'; r['target_games'] = int(len(hist))
                r['weight_sum_h8'] = float(w8.sum())
                r['ret_mult_prev1'] = mult[year-1]; r['ret_mult_prev2'] = mult[year-2]; r['ret_mult_prev3'] = mult[year-3]
                out[v] = r
                if v == 'league' and check_production:
                    # (a) the generalized retention == production np.power(0.5, year-season), bitwise
                    ref_ret = np.power(m.OFFSEASON_RETENTION, year-h.season.to_numpy(float))
                    chk['retention_weight_max_abs'] = max(chk['retention_weight_max_abs'], float(np.max(np.abs(ret-ref_ret))) if n else 0.)
                    pw = np.exp2(-age/HALF)*ref_ret
                    # (b) rates == nfl_model.metric_profile with production weights
                    for role, cols in (('for', list(m.COUNTS)), ('allowed', OPP)):
                        ref = m.metric_profile(h[cols].to_numpy(float), pw, league, SPECS)
                        for mt in USED[role]:
                            a_, b_ = ref[mt], r[f'{role}__rates_core__{mt}']
                            if np.isnan(a_) != np.isnan(b_): chk['rates_max_abs'] = np.inf
                            elif not np.isnan(a_): chk['rates_max_abs'] = max(chk['rates_max_abs'], abs(a_-b_))
                    # (c) peaks and margin == lagged_features formulas
                    for c in PEAKS:
                        ref = float(np.dot(pw, h[c].to_numpy(float))/(pw.sum()+K))
                        chk['peaks_margin_max_abs'] = max(chk['peaks_margin_max_abs'], abs(ref-r[c]))
                    mg = h.margin.to_numpy(float); ok = np.isfinite(mg)
                    ref = float(np.dot(pw[ok], mg[ok])/(pw[ok].sum()+K))
                    chk['peaks_margin_max_abs'] = max(chk['peaks_margin_max_abs'], abs(ref-r['margin']))
                    chk['team_weeks'] += 1
            prof[(year, week, team)] = out
            info[(year, week, team)] = {
                'history_games': n, 'prior_season_window_games': int((hs < year).sum()),
                'head_coach': coach, 'prior_season_last_coach': pcoach, 'recent_starter_qb_id': rqb,
                'prior_season_primary_qb_id': pqb, 'prior_primary_qb_starts': pq[1] if pq else 0,
                'coach_change': coach_change, 'qb_change': qb_change,
                'cont_boundary_cur': cont[year], 'cont_boundary_m1': cont[year-1], 'cont_boundary_m2': cont[year-2]}
    return prof, info, both, chk


def assemble(prof, info, both, sched, disp, variants, first_season=FIRST_OUTPUT_SEASON):
    rows = []
    bx = both.set_index(['game_id', 'team'])
    for g in sched.itertuples(index=False):
        if g.season < first_season: continue
        for team, opp_, home in ((g.home_team, g.away_team, True), (g.away_team, g.home_team, False)):
            key = (int(g.season), int(g.week), team)
            if key not in prof: continue
            if (g.game_id, team) not in bx.index: continue          # played only
            base = {'game_id': g.game_id, 'season': int(g.season), 'week': int(g.week), 'team': team, 'opponent': opp_,
                    'is_home': home, 'neutral_site': bool(g.site == 0.)}
            act = {}
            b = bx.loc[(g.game_id, team)]
            for role, mt in ROLE_METRICS:
                num, den, mult = SPECS[mt]
                pre = '' if role == 'for' else 'opp_'
                a = float(b[pre+num]); d = 1. if den is None else float(b[pre+den])
                act[f'actual__{role}__rates_core__{mt}'] = mult*a/d if (np.isfinite(a) and np.isfinite(d) and d > 0) else np.nan
                act[f'den__{role}__rates_core__{mt}'] = d
            for c in PEAKS+EXTRA_COLS:
                act[f'actual__{c}'] = float(b[c]); act[f'den__{c}'] = 1.
            inf = dict(info[key])
            inf['recent_starter_qb_name'] = disp.get(inf['recent_starter_qb_id'])
            inf['prior_season_primary_qb_name'] = disp.get(inf['prior_season_primary_qb_id'])
            for v in variants:
                rows.append({**base, 'variant': v, **prof[key][v], **inf, **act})
    df = pd.DataFrame(rows)
    for c in ('coach_change', 'qb_change', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2'):
        df[c] = df[c].astype('boolean')
    # same column order as profiles.csv.gz (columns that do not apply: coach/qb window counts -> dropped);
    # retention columns appended after the identity block
    lead = ['game_id', 'season', 'week', 'team', 'opponent', 'is_home', 'neutral_site', 'variant']
    order = (lead+PROFILE_COLS+EXTRA_COLS+H16_COLS+['history_games', 'coach_change', 'qb_change', 'target_source', 'target_games',
             'weight_sum_h8', 'prior_season_window_games', 'head_coach', 'prior_season_last_coach',
             'recent_starter_qb_id', 'recent_starter_qb_name', 'prior_season_primary_qb_id', 'prior_season_primary_qb_name',
             'prior_primary_qb_starts', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2',
             'ret_mult_prev1', 'ret_mult_prev2', 'ret_mult_prev3'])
    act_cols = [f'{p}__{r}__rates_core__{mt}' for r, mt in ROLE_METRICS for p in ('actual', 'den')]+[f'{p}__{c}' for c in PEAKS+EXTRA_COLS for p in ('actual', 'den')]
    return df[order+act_cols].sort_values(['season', 'week', 'game_id', 'is_home', 'variant'], ascending=[True, True, True, False, True]).reset_index(drop=True)


def game_frame(prof, sched, variant, years=None):
    rows = []
    for g in sched.itertuples(index=False):
        if years is not None and g.season not in years: continue
        r = {'game_id': g.game_id, 'season': int(g.season), 'week': int(g.week)}
        hp, ap = prof[(int(g.season), int(g.week), g.home_team)][variant], prof[(int(g.season), int(g.week), g.away_team)][variant]
        for c in PROFILE_COLS+EXTRA_COLS+H16_COLS:
            r['home__'+c], r['away__'+c], r['d__'+c] = hp[c], ap[c], hp[c]-ap[c]
        rows.append(r)
    return pd.DataFrame(rows).sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


# --- checks -------------------------------------------------------------------------------------------
def compare_with_existing(df_league):
    """Written league rows vs the existing profiles.csv.gz league rows (both written at %.12g)."""
    ex = pd.read_csv(EXISTING, low_memory=False)
    ex = ex[ex.variant == 'league']
    tmp = SCRATCH/'_retention_league_tmp.csv.gz'
    df_league.to_csv(tmp, index=False, float_format='%.12g', compression={'method': 'gzip', 'mtime': 0})
    mine = pd.read_csv(tmp, low_memory=False); tmp.unlink()
    key = ['game_id', 'team']
    common = [c for c in mine.columns if c in ex.columns and c not in key]
    j = ex[key+common].merge(mine[key+common], on=key, how='outer', suffixes=('_ex', '_new'), indicator=True)
    res = {'rows_existing': int(len(ex)), 'rows_new': int(len(mine)), 'unmatched': int((j._merge != 'both').sum()),
           'columns_compared': len(common), 'max_abs_diff_numeric': 0., 'mismatched_cells_any': 0, 'by_column_mismatches': {}}
    for c in common:
        a, b = j[c+'_ex'], j[c+'_new']
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b) and a.dtype != bool:
            A, B = a.to_numpy(float), b.to_numpy(float)
            bad = ~((A == B) | (np.isnan(A) & np.isnan(B)))
            if np.isfinite(A-B).any(): res['max_abs_diff_numeric'] = max(res['max_abs_diff_numeric'], float(np.nanmax(np.abs(A-B))))
        else:
            bad = ~((a.astype(str) == b.astype(str)) | (a.isna() & b.isna()))
        if bad.any(): res['by_column_mismatches'][c] = int(bad.sum())
        res['mismatched_cells_any'] += int(bad.sum())
    return res


def independent_recompute(df, box, tg, n=60, seed=11):
    """For random 2016-2025 rows of each arm/control: recompute boundary flags directly from games.csv rows
    and the profile with nfl_model.metric_profile under explicit loop weights. Different code path."""
    rng = np.random.default_rng(seed)
    pl = tg[tg.played].copy()
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    both = box.merge(opp, on=['game_id', 'opponent'], how='left')

    def primary(team, s):
        d = pl[(pl.team == team) & (pl.season == s) & pl.qb_id.notna()]
        c = d.groupby('qb_id').week.agg(['size', 'max']).reset_index().sort_values(['size', 'max'], ascending=False)
        return c.qb_id.iloc[0]

    def last_coach(team, s):
        d = pl[(pl.team == team) & (pl.season == s)].sort_values(['week', 'game_id'])
        return d.coach.iloc[-1]

    def first_coach(team, s):
        d = pl[(pl.team == team) & (pl.season == s)].sort_values(['week', 'game_id'])
        return d.coach.iloc[0]

    rows = df[df.season.between(2016, 2025) & df.variant.isin(list(ARMS)+list(CONTROLS))]
    pick = rows.iloc[rng.choice(len(rows), n, replace=False)]
    maxd, flag_mis = 0., 0
    for r in pick.itertuples(index=False):
        Y, W, team = r.season, r.week, r.team
        coach = tg[(tg.game_id == r.game_id) & (tg.team == team)].coach.iloc[0]
        e = pl[(pl.team == team) & ((pl.season < Y) | ((pl.season == Y) & (pl.week < W)))].sort_values(['season', 'week'])
        rqb = e.qb_id.iloc[-1]
        cur = (coach == last_coach(team, Y-1)) and (rqb == primary(team, Y-1))
        old = {b: (first_coach(team, b) == last_coach(team, b-1)) and (primary(team, b) == primary(team, b-1)) for b in (Y-1, Y-2)}
        if bool(cur) != bool(r.cont_boundary_cur) or bool(old[Y-1]) != bool(r.cont_boundary_m1) or bool(old[Y-2]) != bool(r.cont_boundary_m2):
            flag_mis += 1
        rc, rx = SCHEMES[r.variant]
        f = {b: (rc if c else rx) for b, c in {Y: cur, **old}.items()}
        hist = both[((both.season < Y) | ((both.season == Y) & (both.week < W))) & (both.season >= Y-3)]
        h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
        wts = []
        for i, s in enumerate(h.season.to_numpy(int)):
            age = len(h)-1-i
            mult = 1.
            for b in range(s+1, Y+1): mult *= f[b]
            wts.append(2**(-age/8.)*mult)
        wts = np.array(wts)
        ref = m.metric_profile(h[list(m.COUNTS)].to_numpy(float), wts, hist[list(m.COUNTS)].to_numpy(float), SPECS)
        refa = m.metric_profile(h[OPP].to_numpy(float), wts, hist[list(m.COUNTS)].to_numpy(float), SPECS)
        for role, mt in ROLE_METRICS:
            x = (ref if role == 'for' else refa)[mt]
            y = getattr(r, f'{role}__rates_core__{mt}')
            maxd = max(maxd, abs(x-y)/max(abs(x), 1e-9))
        for c in PEAKS:
            x = float(np.dot(wts, h[c].to_numpy(float))/(wts.sum()+K)); y = getattr(r, c)
            maxd = max(maxd, abs(x-y)/max(abs(x), 1e-9))
    return {'rows_checked': n, 'max_rel_diff': maxd, 'boundary_flag_mismatches': flag_mis}


def lookahead_test(box, sched, tg):
    """Season 2024 cut at week 10: perturb box counts/peaks/results of weeks >= 10, starters of weeks >= 10,
    coaches of weeks > 10, and ALL of 2025. Profiles/flags for 2024 weeks <= 10 must be unchanged (every
    scheme). Positive controls: week 11 changes; perturbing 2023 starters changes 2024-wk1 arm profiles via
    the older boundary but not league."""
    Y, W = 2024, 10
    bx = box[box.season.between(Y-3, Y+1)].copy(); sc = sched[sched.season.between(Y-3, Y+1)].copy()
    lk = pregame_lookups(tg)
    base, binfo, _, _ = build(bx, sc, tg, lk, years={Y}, check_production=False)
    rng = np.random.default_rng(7)
    late = ((bx.season == Y) & (bx.week >= W)) | (bx.season > Y)
    bx2 = bx.copy()
    cnt = [c for c in m.COUNTS if c not in ('net_yards',)]
    bx2.loc[late, cnt] = (bx2.loc[late, cnt].to_numpy()*rng.uniform(.5, 1.5, size=(late.sum(), len(cnt)))).round()
    bx2.loc[late, 'net_yards'] = bx2.loc[late, 'net_pass_yards']+bx2.loc[late, 'rush_yards']
    bx2.loc[late, 'plays'] = bx2.loc[late, 'plays'].clip(lower=1)
    bx2.loc[late, ['max_lead', 'max_deficit']] = bx2.loc[late, ['max_lead', 'max_deficit']].to_numpy()+3.
    sc2 = sc.copy(); sl = ((sc2.season == Y) & (sc2.week >= W)) | (sc2.season > Y)
    sc2.loc[sl, 'result'] = -sc2.loc[sl, 'result']+7
    tg2 = tg.copy()
    tg2.loc[((tg2.season == Y) & (tg2.week >= W)) | (tg2.season > Y), 'qb_id'] = '00-9999999'
    tg2.loc[((tg2.season == Y) & (tg2.week > W)) | (tg2.season > Y), 'coach'] = 'Nobody'
    pert, pinfo, _, _ = build(bx2, sc2, tg2, pregame_lookups(tg2), years={Y}, check_production=False)
    cols = PROFILE_COLS+EXTRA_COLS+H16_COLS+['weight_sum_h8', 'ret_mult_prev1', 'ret_mult_prev2', 'ret_mult_prev3']

    def maxdiff(keys, A, B, IA, IB):
        d, n = 0., 0
        for k in keys:
            for v in SCHEMES:
                for c in cols:
                    x, y = A[k][v][c], B[k][v][c]
                    if np.isnan(x) and np.isnan(y): continue
                    d = max(d, abs(x-y)); n += 1
            for c in ('coach_change', 'qb_change', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2', 'recent_starter_qb_id'):
                if IA[k][c] != IB[k][c]: d = np.inf
        return d, n
    upto = [k for k in base if k[1] <= W]; after = [k for k in base if k[1] == W+1]
    d0, n0 = maxdiff(upto, base, pert, binfo, pinfo); d1, _ = maxdiff(after, base, pert, binfo, pinfo)
    # older-boundary positive control: scramble 2023 starters of weeks >= 9 (changes 2023 primaries for some teams)
    tg3 = tg.copy(); tg3.loc[(tg3.season == Y-1) & (tg3.week >= 9), 'qb_id'] = '00-8888888'
    p3, i3, _, _ = build(bx, sc, tg3, pregame_lookups(tg3), years={Y}, check_production=False)
    wk1 = [k for k in base if k[1] == 1]
    moved = {v: float(np.mean([any(abs(base[k][v][c]-p3[k][v][c]) > 1e-12 for c in PROFILE_COLS) for k in wk1])) for v in SCHEMES}
    m1_changed = float(np.mean([binfo[k]['cont_boundary_m1'] != i3[k]['cont_boundary_m1'] for k in wk1]))
    res = {'season': Y, 'cut_week': W, 'weeks_le_cut_max_abs_change': d0, 'values_compared': n0,
           'week_after_cut_max_abs_change': d1,
           'older_boundary_control_share_wk1_team_weeks_changed_by_scheme': moved,
           'older_boundary_control_share_wk1_m1_flag_changed': m1_changed}
    assert d0 == 0., 'lookahead: profiles at or before the cut changed'
    assert d1 > 0, 'positive control failed'
    assert moved['league'] == 0. and moved['retention_flat_75'] == 0. and moved['retention_cont_75_25'] > 0, 'older-boundary control failed'
    return res


def main():
    t0 = time.time()
    box = pd.read_csv(BOXES)
    sched = schedule_frame(pd.read_csv(SCHED))
    tg, remap, disp = team_games(GAMES)
    lookups = pregame_lookups(tg)
    prof, info, both, chk = build(box, sched, tg, lookups)
    print(f'built in {time.time()-t0:.0f}s; production checks {chk}', flush=True)
    val = {'production_checks_league_scheme': chk, 'qb_id_remap': remap, 'schemes': SCHEMES}
    if chk['rates_max_abs'] != 0. or chk['peaks_margin_max_abs'] != 0. or chk['retention_weight_max_abs'] != 0.:
        raise ValueError('league scheme does not reproduce production bit for bit')

    # league vs nfl_model.lagged_features (h8 and h16) on the same inputs, every scheduled game
    gf = game_frame(prof, sched, 'league')
    lf8 = m.lagged_features(box, sched, HALF, profile_families=['rates_core'])
    lf16 = m.lagged_features(box, sched, PASS_HALF, profile_families=['rates_core'])
    j = gf.merge(lf8, on='game_id', suffixes=('', '_p')); j16 = gf.merge(lf16, on='game_id', suffixes=('', '_p'))
    lmax = 0.
    for side in ('home', 'away'):
        for c in PROFILE_COLS+EXTRA_COLS:
            a_, b_ = j[f'{side}__{c}'].to_numpy(float), j[f'{side}__{c}_p'].to_numpy(float)
            if (np.isnan(a_) != np.isnan(b_)).any(): raise ValueError('NaN pattern differs')
            if np.isfinite(a_-b_).any(): lmax = max(lmax, float(np.nanmax(np.abs(a_-b_))))
        for r in ('for', 'allowed'):
            d = np.abs(j16[f'{side}__h16__{r}__rates_core__{PASS_METRIC}'].to_numpy(float)-j16[f'{side}__{r}__rates_core__{PASS_METRIC}_p'].to_numpy(float))
            lmax = max(lmax, float(np.nanmax(d)))
    val['league_vs_lagged_features'] = {'games': int(len(j)), 'max_abs_any_column': lmax}
    print('league vs lagged_features max |diff|', lmax, flush=True)

    df = assemble(prof, info, both, sched, disp, list(SCHEMES))
    main_df = df[df.variant.isin(MAIN_VARIANTS)].reset_index(drop=True)
    ctl_df = df[df.variant.isin(['league']+CONTROL_VARIANTS)].reset_index(drop=True)
    val['vs_existing_profiles_league_rows'] = compare_with_existing(main_df[main_df.variant == 'league'])
    print('vs existing league rows', {k: v for k, v in val['vs_existing_profiles_league_rows'].items()}, flush=True)
    if val['vs_existing_profiles_league_rows']['mismatched_cells_any'] or val['vs_existing_profiles_league_rows']['unmatched']:
        raise ValueError('league rows differ from profiles.csv.gz')
    val['independent_recompute'] = independent_recompute(df, box, tg)
    print('independent recompute', val['independent_recompute'], flush=True)
    if val['independent_recompute']['max_rel_diff'] > 1e-9 or val['independent_recompute']['boundary_flag_mismatches']:
        raise ValueError('independent recomputation disagrees')
    val['lookahead_test'] = lookahead_test(box, sched, tg)
    print('lookahead', val['lookahead_test'], flush=True)

    p1 = OUT/'retention_profiles.csv.gz'; p2 = OUT/'retention_controls_profiles.csv.gz'
    for p_, d_ in ((p1, main_df), (p2, ctl_df)):
        if p_.exists(): raise FileExistsError(p_)
        d_.to_csv(p_, index=False, float_format='%.12g', compression={'method': 'gzip', 'mtime': 0})
    val['output'] = {str(p1): {'rows': int(len(main_df)), 'sha256': sha(p1), 'variants': MAIN_VARIANTS},
                     str(p2): {'rows': int(len(ctl_df)), 'sha256': sha(p2), 'variants': ['league']+CONTROL_VARIANTS}}
    val['inputs'] = {str(p): sha(p) for p in (BOXES, SCHED, GAMES, EXISTING)}

    # ---- descriptive coverage (no outcomes)
    L = df[df.variant == 'league']
    cov = L.groupby('season').agg(team_games=('team', 'size'),
                                  cur_changed=('cont_boundary_cur', lambda s: float((~s.astype(bool)).mean())),
                                  m1_changed=('cont_boundary_m1', lambda s: float((~s.astype(bool)).mean())),
                                  m2_changed=('cont_boundary_m2', lambda s: float((~s.astype(bool)).mean())),
                                  wk1_cur_changed=('cont_boundary_cur', lambda s: np.nan)).reset_index()
    wk1 = L[L.week == 1].groupby('season').cont_boundary_cur.apply(lambda s: float((~s.astype(bool)).mean()))
    cov['wk1_cur_changed'] = cov.season.map(wk1)
    for v in list(ARMS)+list(CONTROLS):
        X = df[df.variant == v].set_index(['game_id', 'team'])
        cov[f'{v}__mean_prev1_mult'] = cov.season.map(X.groupby('season').ret_mult_prev1.mean())
        diff_any = (X[PROFILE_COLS] - L.set_index(['game_id', 'team'])[PROFILE_COLS]).abs().max(axis=1) > 1e-12
        cov[f'{v}__share_rows_differing_from_league'] = cov.season.map(diff_any.groupby(X.season).mean())
    cov.to_csv(OUT/'retention_build_coverage.csv', index=False, float_format='%.4f')
    # how far each arm moves profiles: mean |v - league| / SD(league), 2016-2025
    Le = L[L.season.between(2016, 2025)].set_index(['game_id', 'team'])
    mv = []
    for v in list(ARMS)+list(CONTROLS):
        X = df[(df.variant == v) & df.season.between(2016, 2025)].set_index(['game_id', 'team']).loc[Le.index]
        for c in PROFILE_COLS+EXTRA_COLS:
            d = (X[c]-Le[c]).abs()
            mv.append({'variant': v, 'profile': c, 'mean_abs_shift_sd': float(d.mean()/Le[c].std()),
                       'mean_abs_shift_sd_cur_changed': float(d[~Le.cont_boundary_cur.astype(bool)].mean()/Le[c].std()),
                       'mean_abs_shift_sd_cur_continuous': float(d[Le.cont_boundary_cur.astype(bool)].mean()/Le[c].std()),
                       'mean_signed_shift': float((X[c]-Le[c]).mean())})
    pd.DataFrame(mv).to_csv(OUT/'retention_build_profile_shift.csv', index=False, float_format='%.5f')
    val['runtime_s'] = time.time()-t0
    (SCRATCH/'retention_validation.json').write_text(json.dumps(val, indent=1, default=str))
    print(cov.to_string()); print('rows', len(main_df), len(ctl_df), 'time', round(time.time()-t0))


if __name__ == '__main__':
    main()
