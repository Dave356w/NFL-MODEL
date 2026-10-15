"""Team-prior shrinkage-target profiles (research build only; no outcome evaluation).

Rebuilds production v1.18's half-life-8 raw box-score profiles (rates_core metrics used by
rates_core_avail_cs_peaks_nosacks, plus the two score peaks) for every team-game, replicating
nfl_model.lagged_features / metric_profile, then rebuilds them with alternative targets for the
PRIOR_EQUIVALENT_GAMES pseudo-games. Weights, window and everything else are production's.

Reads only: research/form_windows_inputs/{boxes,schedule}.csv, dl/games.csv (data), the frozen packs.
Writes only: team_prior/profiles.csv.gz, team_prior/build_notes.md (+ validation json in agent_scratch).
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
PACKS = {'2013-20 pack (out_of_sample_results/frozen_features_2013_2020)': MAIN/'research/out_of_sample_results/frozen_features_2013_2020.csv.gz',
         '2019-26 pack (shrinkage_results/frozen_training_features)': MAIN/'research/shrinkage_results/frozen_training_features.csv.gz'}
OUT = WORK
SCRATCH = WORK
FIRST_OUTPUT_SEASON = 2015

FAMILY = m.LEGACY_PRODUCT_RECIPE['family']           # rates_core_avail_cs_peaks_nosacks
HALF = float(m.LEGACY_PRODUCT_RECIPE['half_life'])     # 8
PASS_HALF = float(m.LEGACY_PRODUCT_RECIPE['pass_half_life'])  # 16
K = m.PRIOR_EQUIVALENT_GAMES
SPECS = m.FAMILIES['rates_core']
NAMES = m.feature_names(FAMILY)
RATE_FEATURES = [n for n in NAMES if n.startswith('d__for__') or n.startswith('d__allowed__')]
ROLE_METRICS = [(n.split('__')[1], n.split('__')[3]) for n in RATE_FEATURES]   # (role, metric)
USED = {}
for role, metric in ROLE_METRICS: USED.setdefault(role, []).append(metric)
PEAKS = list(m.PEAK_COLUMNS)
assert m.MARGIN_FEATURE not in NAMES, 'margin unexpectedly in production family'
assert [n for n in NAMES if n.startswith('d__') and not n.startswith('d__avail__')] == RATE_FEATURES+list(m.PEAK_FEATURES)
PROFILE_COLS = [f'{r}__rates_core__{mt}' for r, mt in ROLE_METRICS]+PEAKS
EXTRA_COLS = ['margin']   # not a v1.18 regressor; reference only
PASS_METRIC = 'net_pass_yards_per_pass_play'
H16_COLS = [f'h16__{r}__rates_core__{PASS_METRIC}' for r in ('for', 'allowed')]
QB_METRICS = ('net_pass_yards_per_pass_play', 'interception_pct', 'first_down_rate')   # offense ('for') only
MIN_COACH_GAMES = 8
MIN_QB_GAMES = 8
VARIANTS = ('league', 'league_level', 'team_window', 'team_prior', 'continuity', 'coach', 'qb_offense', 'none')
OPP = ['opp_'+c for c in m.COUNTS]
IX = {c: i for i, c in enumerate(m.COUNTS)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def schedule_frame(s):
    """The columns production's load_schedule adds, from the frozen nflverse REG schedule."""
    s = m.normalize_teams(s.copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.get('location', pd.Series('', index=s.index)).astype(str).str.lower() == 'neutral', 0., 1.)
    s['market WP'] = ndtr(pd.to_numeric(s.spread_line, errors='coerce')/m.MARKET_SIGMA)
    return s


# --- coach / starting QB per team-game (pregame-safe lookups) ---------------------------------------

def team_games(games_csv):
    """One row per REG team-game from nflverse games: coach of that game, that game's starting QB.
    QB ids: an id seen only under one name whose name has a majority id elsewhere is mapped to it."""
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
    # QB id canonicalisation (documented in build_notes): only ids used exclusively under one name.
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
    # display name per canonical id: most common name among played starts
    disp = (t[t.played & t.qb_id.notna()].groupby(['qb_id', 'qb_name']).size().reset_index(name='n')
            .sort_values(['qb_id', 'n'], ascending=[True, False]).drop_duplicates('qb_id').set_index('qb_id').qb_name)
    if t.duplicated(['game_id', 'team']).any(): raise ValueError('duplicate team-game in games.csv')
    return t, remap, disp


def pregame_lookups(tg):
    """Per (team, season): last played REG game's coach, primary starter (most starts; tie -> most recent).
    Per team: chronologically ordered played REG starters for 'most recent earlier game' lookups."""
    pl = tg[tg.played].sort_values(['season', 'week', 'game_id'])
    last_coach = pl.groupby(['team', 'season']).coach.last().to_dict()
    prim = {}
    for (team, season), d in pl.groupby(['team', 'season']):
        d = d[d.qb_id.notna()]
        if d.empty: continue
        st = d.groupby('qb_id').agg(n=('qb_id', 'size'), last=('week', 'max')).sort_values(['n', 'last'], ascending=False)
        prim[(team, season)] = (st.index[0], int(st.n.iloc[0]), int(len(d)))
    seq = {team: (d.season.to_numpy(int), d.week.to_numpy(int), d.qb_id.tolist(), d.coach.tolist()) for team, d in pl.groupby('team')}
    return last_coach, prim, seq


def recent_start(seq, team, year, week):
    """QB id and coach of the team's most recent played REG game strictly before (year, week)."""
    a = seq.get(team)
    if a is None: return None, None
    ss, ww, qq, cc = a
    ok = (ss < year) | ((ss == year) & (ww < week))
    if not ok.any(): return None, None
    i = int(np.flatnonzero(ok)[-1])
    return (qq[i] if isinstance(qq[i], str) else None), cc[i]


# --- profile arithmetic (mirrors nfl_model.metric_profile) ------------------------------------------

def target_means(T, specs):
    """Pseudo-game numerator/denominator per metric: plain means over valid target rows (production's
    league construction). None when no valid row."""
    out = {}
    for name, (num, den, mult) in specs.items():
        la = T[:, IX[num]]
        lb = np.ones(len(T)) if den is None else T[:, IX[den]]
        lok = np.isfinite(la) & np.isfinite(lb) & (lb > 0)
        out[name] = (float(la[lok].mean()), float(lb[lok].mean())) if lok.any() else None
    return out


def with_fallback(t, fb):
    return {k: (v if v is not None else fb[k]) for k, v in t.items()}


def profile(values, weights, targ, specs, k=K):
    """Ratio of decayed counts plus k pseudo-games at targ[metric]=(num, den). k=0: no shrinkage."""
    out = {}
    for name, (num, den, mult) in specs.items():
        a = values[:, IX[num]]
        b = np.ones(len(values)) if den is None else values[:, IX[den]]
        ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
        if k > 0:
            if targ.get(name) is None: out[name] = np.nan; continue
            pa, pb = targ[name]
            numer = float(np.dot(weights[ok], a[ok]))+k*pa
            denom = float(np.dot(weights[ok], b[ok]))+k*pb
        else:
            numer = float(np.dot(weights[ok], a[ok])); denom = float(np.dot(weights[ok], b[ok]))
        out[name] = mult*numer/denom if denom > 0 else np.nan
    return out


def scalar_mean(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else None


def scalar_profile(x, w, t, k, masked):
    """Peaks (masked=False, production uses every weight) and margin (masked=True)."""
    x = np.asarray(x, float)
    if masked:
        ok = np.isfinite(x); x, w = x[ok], w[ok]
    if k == 0: return float(np.dot(w, x)/w.sum()) if w.sum() > 0 else np.nan
    return float((np.dot(w, x)+k*t)/(w.sum()+k)) if t != 0. else float(np.dot(w, x)/(w.sum()+k))


SUB = {r: {mt: SPECS[mt] for mt in USED[r]} for r in USED}
SUB16 = {mt: SPECS[mt] for mt in (PASS_METRIC,)}


def build(box, sched, tg, lookups, years=None, check_production=True):
    """Profiles per (season, week, team, variant) for every scheduled team-week (played or not)."""
    last_coach, prim, seq = lookups
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    both = box.merge(opp, on=['game_id', 'opponent'], how='left', validate='one_to_one')
    res = sched[['game_id', 'home_team', 'result']].drop_duplicates('game_id').rename(columns={'home_team': '_h', 'result': '_r'})
    both = both.merge(res, on='game_id', how='left', validate='many_to_one')
    both['margin'] = np.where(both.team == both._h, both._r, -both._r).astype(float)
    both = both.merge(tg[['game_id', 'team', 'coach', 'qb_id']], on=['game_id', 'team'], how='left', validate='one_to_one')
    if both.coach.isna().any() or both.qb_id.isna().any():
        raise ValueError('box rows without coach/QB in games.csv')
    cur_coach = tg.set_index(['game_id', 'team']).coach.to_dict()
    prof, info, maxdiff = {}, {}, 0.
    groups = sched.groupby(['season', 'week'], sort=True)
    for (year, week), games in groups:
        year, week = int(year), int(week)
        if years is not None and year not in years: continue
        hist = both[m.before(both, year, week) & (both.season >= year-m.MAX_HISTORY_SEASONS)]
        league = hist[list(m.COUNTS)].to_numpy(float)
        LT = {r: target_means(league, SUB[r]) for r in SUB}
        LT16 = target_means(league, SUB16)
        LL = {c: scalar_mean(hist[c]) for c in PEAKS+EXTRA_COLS}       # league window level (peaks ~9.5, margin 0)
        LL = {c: (v if v is not None else 0.) for c, v in LL.items()}
        h_team = hist.team.to_numpy(); h_coach = hist.coach.to_numpy(); h_qb = hist.qb_id.to_numpy()
        teams = {}
        for g in games.itertuples(index=False):
            teams[g.home_team] = g.game_id; teams[g.away_team] = g.game_id
        for team, gid in teams.items():
            h = hist[h_team == team].sort_values(['season', 'week', 'game_id'])
            n = len(h)
            age = np.arange(n-1, -1, -1, dtype=float)
            ret = np.power(m.OFFSEASON_RETENTION, year-h.season.to_numpy(float))
            w8 = np.exp2(-age/HALF)*ret
            w16 = np.exp2(-age/PASS_HALF)*ret
            vals = {'for': h[list(m.COUNTS)].to_numpy(float), 'allowed': h[OPP].to_numpy(float)}
            # --- pregame identities (current game's coach is public pregame; its QB is never used)
            coach = cur_coach.get((gid, team))
            pcoach = last_coach.get((team, year-1))
            rqb, _ = recent_start(seq, team, year, week)
            pq = prim.get((team, year-1))
            pqb = pq[0] if pq else None
            coach_change = None if (coach is None or pcoach is None) else bool(coach != pcoach)
            qb_change = None if (rqb is None or pqb is None) else bool(rqb != pqb)
            prior = h[h.season < year]
            Rc = hist[h_coach == coach] if coach is not None else hist.iloc[:0]
            Rq = hist[h_qb == rqb] if rqb is not None else hist.iloc[:0]

            def tt(R):
                return {r: with_fallback(target_means(R[list(m.COUNTS) if r == 'for' else OPP].to_numpy(float), SUB[r]), LT[r]) for r in SUB}, \
                       with_fallback(target_means(R[list(m.COUNTS)].to_numpy(float), SUB16), LT16), \
                       with_fallback(target_means(R[OPP].to_numpy(float), SUB16), LT16), \
                       {c: (scalar_mean(R[c]) if scalar_mean(R[c]) is not None else LL[c]) for c in PEAKS+EXTRA_COLS}
            league_t = (LT, LT16, LT16, {c: 0. for c in PEAKS+EXTRA_COLS}, 'league', len(hist))
            level_t = (LT, LT16, LT16, dict(LL), 'league', len(hist))
            targets = {'league': league_t, 'league_level': level_t}
            targets['team_window'] = (*tt(h), 'team_window', n) if n else (*level_t[:4], 'league', len(hist))
            targets['team_prior'] = (*tt(prior), 'team_prior', len(prior)) if len(prior) else (*level_t[:4], 'league', len(hist))
            cont = coach_change is False and qb_change is False and len(prior) > 0
            targets['continuity'] = targets['team_prior'] if cont else level_t
            targets['coach'] = (*tt(Rc), 'coach', len(Rc)) if len(Rc) >= MIN_COACH_GAMES else level_t
            if len(Rq) >= MIN_QB_GAMES:
                q_for = target_means(Rq[list(m.COUNTS)].to_numpy(float), {mt: SPECS[mt] for mt in QB_METRICS})
                qf = dict(LT['for']); qf.update({k2: v for k2, v in q_for.items() if v is not None})
                q16 = target_means(Rq[list(m.COUNTS)].to_numpy(float), SUB16)
                targets['qb_offense'] = ({'for': qf, 'allowed': LT['allowed']}, with_fallback(q16, LT16), LT16,
                                         {c: 0. for c in PEAKS+EXTRA_COLS}, 'qb', len(Rq))
            else:
                targets['qb_offense'] = league_t
            targets['none'] = (None, None, None, None, 'none', 0)
            out = {}
            for v in VARIANTS:
                rt, t16f, t16a, st, src, ng = targets[v]
                k = 0. if v == 'none' else K
                r = {}
                for role in SUB:
                    for mt, val in profile(vals[role], w8, rt[role] if rt else {}, SUB[role], k).items():
                        r[f'{role}__rates_core__{mt}'] = val
                for c in PEAKS:
                    r[c] = scalar_profile(h[c].to_numpy(float), w8, st[c] if st else 0., k, masked=False)
                r['margin'] = scalar_profile(h.margin.to_numpy(float), w8, st['margin'] if st else 0., k, masked=True)
                r[H16_COLS[0]] = profile(vals['for'], w16, t16f or {}, SUB16, k)[PASS_METRIC]
                r[H16_COLS[1]] = profile(vals['allowed'], w16, t16a or {}, SUB16, k)[PASS_METRIC]
                r['target_source'] = src; r['target_games'] = int(ng)
                out[v] = r
            if check_production:   # league variant == production metric_profile, bit for bit
                for role, cols in (('for', list(m.COUNTS)), ('allowed', OPP)):
                    ref = m.metric_profile(h[cols].to_numpy(float), w8, league, SPECS)
                    for mt in USED[role]:
                        a, b = ref[mt], out['league'][f'{role}__rates_core__{mt}']
                        if not (np.isnan(a) and np.isnan(b)): maxdiff = max(maxdiff, abs(a-b))
            prof[(year, week, team)] = out
            info[(year, week, team)] = {
                'history_games': n, 'weight_sum_h8': float(w8.sum()), 'prior_season_window_games': int(len(prior)),
                'head_coach': coach, 'prior_season_last_coach': pcoach, 'recent_starter_qb_id': rqb,
                'prior_season_primary_qb_id': pqb, 'prior_primary_qb_starts': pq[1] if pq else 0,
                'coach_window_games': int(len(Rc)), 'qb_window_games': int(len(Rq)),
                'coach_change': coach_change, 'qb_change': qb_change}
    return prof, info, both, maxdiff


def assemble(prof, info, both, sched, disp, first_season=FIRST_OUTPUT_SEASON, played_only=True):
    rows = []
    bx = both.set_index(['game_id', 'team'])
    for g in sched.itertuples(index=False):
        if g.season < first_season: continue
        for team, opp_, home in ((g.home_team, g.away_team, True), (g.away_team, g.home_team, False)):
            key = (int(g.season), int(g.week), team)
            if key not in prof: continue
            played = (g.game_id, team) in bx.index
            if played_only and not played: continue
            base = {'game_id': g.game_id, 'season': int(g.season), 'week': int(g.week), 'team': team, 'opponent': opp_,
                    'is_home': home, 'neutral_site': bool(g.site == 0.)}
            act = {}
            if played:
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
            for v in VARIANTS:
                rows.append({**base, 'variant': v, **prof[key][v], **inf, **act})
    df = pd.DataFrame(rows)
    for c in ('coach_change', 'qb_change'): df[c] = df[c].astype('boolean')
    lead = ['game_id', 'season', 'week', 'team', 'opponent', 'is_home', 'neutral_site', 'variant']
    order = (lead+PROFILE_COLS+EXTRA_COLS+H16_COLS+['history_games', 'coach_change', 'qb_change', 'target_source', 'target_games',
             'weight_sum_h8', 'prior_season_window_games', 'head_coach', 'prior_season_last_coach', 'coach_window_games',
             'recent_starter_qb_id', 'recent_starter_qb_name', 'prior_season_primary_qb_id', 'prior_season_primary_qb_name',
             'prior_primary_qb_starts', 'qb_window_games'])
    act_cols = [f'{p}__{r}__rates_core__{mt}' for r, mt in ROLE_METRICS for p in ('actual', 'den')]+[f'{p}__{c}' for c in PEAKS+EXTRA_COLS for p in ('actual', 'den')]
    return df[order+act_cols].sort_values(['season', 'week', 'game_id', 'is_home', 'variant'], ascending=[True, True, True, False, True]).reset_index(drop=True)


def game_frame(prof, sched, variant, years=None):
    """Production-shaped per-game frame (home__/away__/d__) from one variant, all scheduled games."""
    rows = []
    for g in sched.itertuples(index=False):
        if years is not None and g.season not in years: continue
        r = {'game_id': g.game_id, 'season': int(g.season), 'week': int(g.week)}
        hp, ap = prof[(int(g.season), int(g.week), g.home_team)][variant], prof[(int(g.season), int(g.week), g.away_team)][variant]
        for c in PROFILE_COLS+EXTRA_COLS+H16_COLS:
            r['home__'+c], r['away__'+c], r['d__'+c] = hp[c], ap[c], hp[c]-ap[c]
        rows.append(r)
    return pd.DataFrame(rows).sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def main():
    t0 = time.time()
    box = pd.read_csv(BOXES)
    sched = schedule_frame(pd.read_csv(SCHED))
    tg, remap, disp = team_games(GAMES)
    lookups = pregame_lookups(tg)
    prof, info, both, md = build(box, sched, tg, lookups)
    print(f'built in {time.time()-t0:.0f}s; league vs metric_profile max |diff| {md:.3g}')
    val = {'league_vs_metric_profile_max_abs': md, 'qb_id_remap': remap}

    # 1. league variant == nfl_model.lagged_features on the same inputs (h8 and h16), every scheduled game
    gf = game_frame(prof, sched, 'league')
    lf8 = m.lagged_features(box, sched, HALF, profile_families=['rates_core'])
    lf16 = m.lagged_features(box, sched, PASS_HALF, profile_families=['rates_core'])
    chk = {}
    j = gf.merge(lf8, on='game_id', suffixes=('', '_p'))
    j16 = gf.merge(lf16, on='game_id', suffixes=('', '_p'))
    for side in ('home', 'away'):
        for c in PROFILE_COLS+EXTRA_COLS:
            a_, b_ = j[f'{side}__{c}'].to_numpy(float), j[f'{side}__{c}_p'].to_numpy(float)
            d = np.abs(a_-b_)
            chk[f'{side}__{c}'] = float(np.nanmax(d)) if np.isfinite(d).any() else 0.
            if (np.isnan(a_) != np.isnan(b_)).any(): raise ValueError(f'NaN pattern differs for {side}__{c}')
        for r in ('for', 'allowed'):
            c = f'{side}__{r}__rates_core__{PASS_METRIC}'
            d = np.abs(j16[f'{side}__h16__{r}__rates_core__{PASS_METRIC}'].to_numpy(float)-j16[c+'_p'].to_numpy(float))
            chk[f'{side}__h16__{r}__rates_core__{PASS_METRIC}'] = float(np.nanmax(d))
    val['league_vs_lagged_features'] = {'games': int(len(j)), 'max_abs_any_column': max(chk.values()), 'by_column': chk}
    print('vs lagged_features max', max(chk.values()))

    # 2. d__ features and h16 pass contexts vs frozen packs
    pf = gf.copy()
    for side, role in (('home', 'for'), ('away', 'allowed'), ('away', 'for'), ('home', 'allowed')):
        pf[f'{side}__{role}__rates_core__{PASS_METRIC}'] = pf[f'{side}__h16__{role}__rates_core__{PASS_METRIC}']
    ctx, _ = m.pass_contexts(pf)
    pf = pd.concat([pf[['game_id', 'season']], ctx[list(m.PRODUCT_CONTEXT_NAMES)]], axis=1)
    main_cols = RATE_FEATURES+list(m.PEAK_FEATURES)
    packs = {}
    for name, path in PACKS.items():
        pk = pd.read_csv(path)
        jj = pk[['game_id', 'season']+main_cols+list(m.PRODUCT_CONTEXT_NAMES)].merge(
            gf[['game_id']+main_cols], on='game_id', suffixes=('', '_r')).merge(
            pf[['game_id']+list(m.PRODUCT_CONTEXT_NAMES)], on='game_id', suffixes=('', '_r'))
        res = {'games': int(len(jj)), 'by_season': {}}
        for grp, cols in (('profiles_d', main_cols), ('pass_contexts', list(m.PRODUCT_CONTEXT_NAMES))):
            A = jj[cols].to_numpy(float); B = jj[[c+'_r' for c in cols]].to_numpy(float)
            d = np.abs(A-B)
            nanmis = int((np.isnan(A) != np.isnan(B)).sum())
            ident = np.nan_to_num(d, nan=0.).max(axis=1) <= 1e-9
            res[grp] = {'max_abs_diff': float(np.nanmax(d)), 'nan_pattern_mismatches': nanmis, 'share_games_identical_1e-9': float(ident.mean()),
                        'max_abs_by_column': {c: float(np.nanmax(d[:, i])) for i, c in enumerate(cols)}}
            for s_, gi in pd.Series(ident).groupby(jj.season.to_numpy()):
                dd = d[jj.season.to_numpy() == s_]
                res['by_season'].setdefault(str(int(s_)), {})[grp] = {'share_identical': float(gi.mean()), 'max_abs': float(np.nanmax(dd)) if np.isfinite(dd).any() else 0.}
        packs[name] = res
    val['vs_frozen_packs'] = packs
    print(json.dumps({k: {g: v[g]['max_abs_diff'] for g in ('profiles_d', 'pass_contexts')} for k, v in packs.items()}, indent=1))

    # 3. output
    df = assemble(prof, info, both, sched, disp)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'profiles.csv.gz'
    df.to_csv(path, index=False, float_format='%.12g', compression={'method': 'gzip', 'mtime': 0})
    val['output'] = {'path': str(path), 'rows': int(len(df)), 'columns': list(df.columns), 'sha256': sha(path)}
    val['inputs'] = {str(p): sha(p) for p in (BOXES, SCHED, GAMES, *PACKS.values())}
    (SCRATCH/'team_prior_validation.json').write_text(json.dumps(val, indent=1, default=str))
    print('rows', len(df), 'time', round(time.time()-t0))


if __name__ == '__main__':
    main()
