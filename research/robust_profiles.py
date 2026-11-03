"""Test 49: outlier-robust team profiles, stage 1 (stat-level screen); see ROBUST_PROFILES.md.

    python research/robust_profiles.py --capped PBP_DIR   # arm C: capped yardage from raw play-by-play
    python research/robust_profiles.py                    # fidelity checks and the stage-1 screen (no network)

Arms: P production (decayed ratio of sums, 4 league pseudo-games), A weighted median, B winsorized
mean, C per-play yardage cap. Stage 1 uses no win/loss outcomes, prices or ROI. Never writes data/,
public/ or the ledger. Development evidence only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import form_windows as fw  # noqa: E402

INPUTS = ROOT/'research/robust_profiles_inputs'
CAPPED = INPUTS/'capped_yardage.csv'
OUT = ROOT/'research/robust_profiles_results'
PROTOCOL = ROOT/'research/ROBUST_PROFILES.md'
PROTOCOL_COMMIT = '0271988'
SEASONS = range(2013, 2027)
HALF_LIFE = 8.
PASS_CAP, RUSH_CAP = 20., 10.  # Test 33's explosive thresholds
WIN_LO, WIN_HI = .025, .975
TRAIN0 = 2014                  # recalibration fits start here; 2013 is warm-up
BASES = {'2015-16': (2015, 2016), '2017-22': (2017, 2022), '2023-25': (2023, 2025)}
POOLED = ('2015-25', (2015, 2025))
DIAG = ('2026 wk1-5 (diagnostic)', (2026, 2026))
SEED, DRAWS, LEVEL, FEATURE_LEVEL = 20261103, 2000, 1-.05/3, .95
WEEK_BUCKETS = {'wk1-4': (1, 4), 'wk5-9': (5, 9), 'wk10-18': (10, 18)}

METRICS = ('plays_per_game', 'net_pass_yards_per_pass_play', 'rush_yards_per_attempt', 'first_down_rate',
           'fumbles_lost_per_game', 'interception_pct', 'penalty_yards_per_game')
SPECS = {k: m.RATES[k] for k in METRICS}
assert set(METRICS) == set(m.FAMILIES['rates_core'])-{'sacks_taken_pct'}
RATE_FEATURES = [f'{role}:{k}' for role in ('for', 'allowed') for k in METRICS]
FEATURES = RATE_FEATURES+list(m.PEAK_COLUMNS)
APPLIED = {
    'A': [f'{r}:{k}' for r in ('for', 'allowed') for k in METRICS if k not in ('fumbles_lost_per_game', 'interception_pct')]
         + list(m.PEAK_COLUMNS),
    'B': list(FEATURES),
    'C': [f'{r}:{k}' for r in ('for', 'allowed') for k in ('net_pass_yards_per_pass_play', 'rush_yards_per_attempt')],
}
ARMS = tuple(APPLIED)


# --- estimators -------------------------------------------------------------------------------------

def weighted_median(x, w):
    """Lower weighted median: the smallest value whose cumulative weight reaches half the total; at
    exactly half, the midpoint with the next value. Non-finite values and non-positive weights are ignored."""
    x = np.asarray(x, float); w = np.asarray(w, float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not ok.any(): return np.nan
    o = np.argsort(x[ok], kind='mergesort'); xs, ws = x[ok][o], w[ok][o]
    c = np.cumsum(ws); half = c[-1]/2; tol = 1e-12*c[-1]
    i = int(np.searchsorted(c, half-tol, side='left'))
    if abs(c[i]-half) <= tol and i+1 < len(xs): return float((xs[i]+xs[i+1])/2)
    return float(xs[i])


def _parts(values, league, num, den):
    """Per-game numerators/denominators (den None -> 1), validity mask and league prior means, as metric_profile."""
    a = values[:, 0]; b = np.ones(len(values)) if den is None else values[:, 1]
    la = league[:, 0]; lb = np.ones(len(league)) if den is None else league[:, 1]
    lok = np.isfinite(la) & np.isfinite(lb) & (lb > 0)
    pa, pb = (float(la[lok].mean()), float(lb[lok].mean())) if lok.any() else (np.nan, np.nan)
    ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
    return a, b, ok, pa, pb


def median_rate(values, weights, league, num, den, mult):
    """Arm A: weighted median of per-game rates (weight = decay x denominator) with production's shrinkage share."""
    a, b, ok, pa, pb = _parts(values, league, num, den)
    if not np.isfinite(pb): return np.nan
    mass = float(np.dot(weights[ok], b[ok])); lam = m.PRIOR_EQUIVALENT_GAMES*pb/(mass+m.PRIOR_EQUIVALENT_GAMES*pb)
    med = weighted_median(a[ok]/b[ok], weights[ok]*b[ok]) if ok.any() else 0.
    return mult*((1-lam)*med+lam*pa/pb)


def winsor_rate(values, weights, league, num, den, mult, lo, hi):
    """Arm B: per-game rates clipped to [lo, hi], then production's ratio of sums and league prior."""
    a, b, ok, pa, pb = _parts(values, league, num, den)
    if not np.isfinite(pb): return np.nan
    ac = np.clip(a[ok]/b[ok], lo, hi)*b[ok]
    numer = float(np.dot(weights[ok], ac))+m.PRIOR_EQUIVALENT_GAMES*pa
    denom = float(np.dot(weights[ok], b[ok]))+m.PRIOR_EQUIVALENT_GAMES*pb
    return mult*numer/denom if denom > 0 else np.nan


def peak(x, weights, arm, lo=None, hi=None):
    """Score peaks shrink toward zero by 4 pseudo-games: P mean, A weighted median, B clipped mean."""
    x = np.asarray(x, float); s = weights.sum()+m.PRIOR_EQUIVALENT_GAMES
    if arm == 'P': return float(np.dot(weights, x)/s)
    if arm == 'A': return float(weights.sum()*weighted_median(x, weights)/s) if len(x) else 0.
    if arm == 'B': return float(np.dot(weights, np.clip(x, lo, hi))/s)
    raise ValueError(arm)


def thresholds(hist):
    """Arm B clip points: league per-game percentiles over the profile's own history (unweighted)."""
    out = {}
    for k, (num, den, _) in SPECS.items():
        a = hist[num].to_numpy(float); b = np.ones(len(a)) if den is None else hist[den].to_numpy(float)
        ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
        out[k] = tuple(np.quantile(a[ok]/b[ok], [WIN_LO, WIN_HI])) if ok.any() else (-np.inf, np.inf)
    for c in m.PEAK_COLUMNS:
        x = hist[c].to_numpy(float); x = x[np.isfinite(x)]
        out[c] = tuple(np.quantile(x, [WIN_LO, WIN_HI])) if len(x) else (-np.inf, np.inf)
    return out


# --- profiles ---------------------------------------------------------------------------------------

def paired(box):
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    return box.merge(opp, on=['game_id', 'opponent'], how='left', validate='one_to_one')


def team_profiles(box, schedules, arms=('P', 'A', 'B')):
    """One row per (game, team) with each arm's pregame profile of every feature and the realized target.
    Profiles use strictly earlier games (seasons >= season-3), production's h8 decay and offseason halving."""
    both = paired(box)
    ix = {c: i for i, c in enumerate(m.COUNTS)}
    own_cols, opp_cols = list(m.COUNTS), ['opp_'+c for c in m.COUNTS]

    def pick(arr, num, den):
        return arr[:, [ix[num]]] if den is None else arr[:, [ix[num], ix[den]]]

    rows = []
    for (year, week), games in schedules.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        hist = both[m.before(both, year, week) & (both.season >= year-m.MAX_HISTORY_SEASONS)]
        league = hist[own_cols].to_numpy(float)
        thr = thresholds(hist) if 'B' in arms and len(hist) else None
        cur = both[(both.season == year) & (both.week == week)].set_index(['game_id', 'team'])
        for g in games.itertuples(index=False):
            for team in (g.home_team, g.away_team):
                h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
                w = fw.team_weights(h, year, half_life=HALF_LIFE)
                r = {'game_id': g.game_id, 'season': year, 'week': week, 'team': team, 'history_games': len(h)}
                key = (g.game_id, team)
                own = cur.loc[key] if key in cur.index else None
                for role, cols in (('for', own_cols), ('allowed', opp_cols)):
                    arr = h[cols].to_numpy(float)
                    prod = m.metric_profile(arr, w, league, SPECS) if 'P' in arms and len(hist) else {}
                    for k, (num, den, mult) in SPECS.items():
                        f = f'{role}:{k}'
                        vals, lg = pick(arr, num, den), pick(league, num, den)
                        if 'P' in arms: r[f'P|{f}'] = prod.get(k, np.nan)
                        if 'A' in arms: r[f'A|{f}'] = median_rate(vals, w, lg, num, den, mult) if len(hist) else np.nan
                        if 'B' in arms: r[f'B|{f}'] = winsor_rate(vals, w, lg, num, den, mult, *thr[k]) if len(hist) else np.nan
                        if own is not None:
                            pre = '' if role == 'for' else 'opp_'
                            y = float(own[pre+num]); d = 1. if den is None else float(own[pre+den])
                            r[f'y|{f}'] = mult*y/d if np.isfinite(d) and d > 0 else np.nan
                            r[f'w|{f}'] = d if np.isfinite(d) and d > 0 else np.nan
                for c in m.PEAK_COLUMNS:
                    x = h[c].to_numpy(float)
                    for arm in arms:  # empty history -> 0, as production (four zero pseudo-games)
                        r[f'{arm}|{c}'] = peak(x, w, arm, *(thr[c] if thr is not None else (-np.inf, np.inf)) if arm == 'B' else (None, None))
                    if own is not None: r[f'y|{c}'] = float(own[c]); r[f'w|{c}'] = 1.
                rows.append(r)
    return pd.DataFrame(rows)


def home_minus_away(tp, schedules, arm='P'):
    """Per-game home-minus-away differences in production's column names (for the fidelity check)."""
    s = schedules[['game_id', 'home_team', 'away_team']]
    t = tp.set_index(['game_id', 'team'])
    out = {'game_id': s.game_id.to_numpy()}
    hk = list(zip(s.game_id, s.home_team)); ak = list(zip(s.game_id, s.away_team))
    for f in FEATURES:
        name = 'd__'+f if f in m.PEAK_COLUMNS else 'd__'+f.split(':')[0]+'__rates_core__'+f.split(':')[1]
        out[name] = t.loc[hk, f'{arm}|{f}'].to_numpy(float)-t.loc[ak, f'{arm}|{f}'].to_numpy(float)
    return pd.DataFrame(out)


# --- arm C: capped yardage from raw play-by-play ----------------------------------------------------

def cap_plays(p, pass_cap=PASS_CAP, rush_cap=RUSH_CAP):
    """Cap yards_gained on pass plays (attempts and sacks) and rushes; other rows unchanged."""
    p = p.copy()
    y = pd.to_numeric(p.yards_gained, errors='coerce')
    is_pass = (pd.to_numeric(p.pass_attempt, errors='coerce') == 1) | (pd.to_numeric(p.sack, errors='coerce') == 1)
    is_rush = (pd.to_numeric(p.rush_attempt, errors='coerce') == 1) & ~is_pass
    p['yards_gained'] = np.where(is_pass, np.minimum(y, pass_cap), np.where(is_rush, np.minimum(y, rush_cap), y))
    return p


def build_capped(pbp_dir):
    """Re-aggregate box scores uncapped (fidelity) and capped; save the two yardage columns for every frozen game."""
    INPUTS.mkdir(parents=True, exist_ok=True)
    frozen = pd.read_csv(fw.BOXES); sched = fw.schedule_frame(pd.read_csv(fw.SCHEDULE))
    prov = json.loads((fw.INPUTS/'provenance.json').read_text())['pbp']
    parts, fid, hashes = [], {}, {}
    cols = ['net_pass_yards', 'rush_yards']
    for y in SEASONS:
        f = Path(pbp_dir)/f'play_by_play_{y}.parquet'
        hashes[f.name] = h = hashlib.sha256(f.read_bytes()).hexdigest()
        if y < 2026 and h != prov[f.name]: raise ValueError(f'{f.name} differs from the Test 40/43 download')
        p = m.normalize_teams(pd.read_parquet(f, columns=fw.PBP_COLS))
        s = sched[sched.season == y]
        b0 = m.aggregate_boxscores(p, s, y); b1 = m.aggregate_boxscores(cap_plays(p), s, y)
        fz = frozen[frozen.season == y][['game_id', 'team', *[c for c in m.COUNTS]]]
        j = fz.merge(b0[['game_id', 'team', *m.COUNTS]], on=['game_id', 'team'], suffixes=('', '_r'), validate='one_to_one')
        diff = {c: float(np.nanmax(np.abs(j[c].to_numpy(float)-j[c+'_r'].to_numpy(float)))) if len(j) else np.nan for c in m.COUNTS}
        fid[str(y)] = {'frozen_games': int(len(fz)), 'matched': int(len(j)), 'max_abs_diff': diff}
        k = b0[['game_id', 'team', *cols]].merge(b1[['game_id', 'team', *cols]], on=['game_id', 'team'], suffixes=('', '_capped'))
        parts.append(fz[['game_id', 'team']].merge(k, on=['game_id', 'team'], how='left', validate='one_to_one'))
        print(f'  {y}: {len(fz)} frozen team-games, {len(j)} matched; max diff '
              f'{max(v for v in diff.values() if np.isfinite(v)):.3g}')
    out = pd.concat(parts, ignore_index=True)
    if out.isna().any(axis=None): raise ValueError('Frozen team-games missing from the play-by-play rebuild')
    out.to_csv(CAPPED, index=False, float_format='%.6f')
    (INPUTS/'provenance.json').write_text(json.dumps({
        'pbp_sha256': hashes, 'pass_cap': PASS_CAP, 'rush_cap': RUSH_CAP, 'uncapped_fidelity_vs_frozen_boxes': fid,
        'capped_yardage_sha256': hashlib.sha256(CAPPED.read_bytes()).hexdigest(), 'frozen_boxes_sha256': sha(fw.BOXES),
        'note': '2013-25 play-by-play is hash-identical to the Test 40/43 download; 2026 is a later in-season file. '
                'Columns *_capped re-aggregate with pass plays capped at 20 yards and rushes at 10; the uncapped '
                'columns are the same rebuild without the cap. Raw files are not committed.'}, indent=2))


def capped_boxes(frozen, capped):
    """Frozen box scores with the yardage columns replaced: capped (arm C) and uncapped rebuild (C's comparator)."""
    out = {}
    for name, suf in (('C', '_capped'), ('Pc', '')):
        new = capped[['game_id', 'team', 'net_pass_yards'+suf, 'rush_yards'+suf]].rename(
            columns={'net_pass_yards'+suf: '_npy', 'rush_yards'+suf: '_ry'})
        b = frozen.merge(new, on=['game_id', 'team'], how='left', validate='one_to_one')
        if b[['_npy', '_ry']].isna().any(axis=None): raise ValueError('Missing capped yardage')
        b['net_pass_yards'] = b.pop('_npy'); b['rush_yards'] = b.pop('_ry')
        b['net_yards'] = b.net_pass_yards+b.rush_yards
        out[name] = b[frozen.columns]
    return out


# --- stage 1 scoring --------------------------------------------------------------------------------

def recalibrate(f, y, w, season, train0=TRAIN0):
    """Walk-forward weighted LS y ~ a + b*f, fitted on seasons train0..s-1 and applied to season s."""
    out = np.full(len(f), np.nan)
    X = np.column_stack([np.ones(len(f)), f])
    for s in np.unique(season):
        tr = (season >= train0) & (season < s); te = season == s
        if s <= train0 or tr.sum() < 3: continue
        sw = np.sqrt(w[tr])
        coef, *_ = np.linalg.lstsq(X[tr]*sw[:, None], y[tr]*sw, rcond=None)
        out[te] = X[te] @ coef
    return out


def draw_matrix(strata, clusters, draws=DRAWS, seed=SEED):
    """Stratified cluster bootstrap counts (draws x clusters), resampling clusters within each stratum."""
    rng = np.random.default_rng(seed); C = np.zeros((draws, int(clusters.max())+1))
    for s in np.unique(strata):
        ids = np.unique(clusters[strata == s])
        C[:, ids] = rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=draws)
    return C


def frame(tp):
    """Common scored rows: team has MIN_TEAM_HISTORY earlier games and every target/profile is finite."""
    d = tp[(tp.history_games >= m.MIN_TEAM_HISTORY) & tp.season.between(min(SEASONS), max(SEASONS))].copy()
    need = [c for c in d if c.startswith(('y|', 'w|')) or '|' in c]
    d = d[np.isfinite(d[need].to_numpy(float)).all(axis=1)].reset_index(drop=True)
    d['stratum'] = np.select([d.season.between(*v) for v in BASES.values()]+[d.season == 2026], list(BASES)+[DIAG[0]], 'warm-up')
    d['cluster'] = pd.factorize(d.team+'_'+d.season.astype(str))[0]
    return d


def score(d, comparators=None):
    """Per arm and feature: raw and recalibrated weighted squared errors summed by cluster."""
    comparators = comparators or {a: 'P' for a in ARMS}
    season = d.season.to_numpy(int)
    arms = sorted(set(ARMS) | set(comparators.values()))
    S = {}
    for f in FEATURES:
        y, w = d[f'y|{f}'].to_numpy(float), d[f'w|{f}'].to_numpy(float)
        for a in arms:
            col = f'{a}|{f}' if f'{a}|{f}' in d else f'P|{f}'
            p = d[col].to_numpy(float)
            for kind, pred in (('raw', p), ('recal', recalibrate(p, y, w, season))):
                e = np.where(np.isfinite(pred), w*(y-pred)**2, np.nan)
                S[(a, f, kind)] = e
    return S


def summarize(d, S, comparators=None, C=None):
    comparators = comparators or {a: 'P' for a in ARMS}
    C = draw_matrix(d.stratum.to_numpy(), d.cluster.to_numpy()) if C is None else C
    ncl = C.shape[1]; cl = d.cluster.to_numpy(); wk = d.week.to_numpy(int); season = d.season.to_numpy(int)
    groups = {**{b: d.season.between(*v).to_numpy() for b, v in BASES.items()},
              POOLED[0]: d.season.between(*POOLED[1]).to_numpy(), DIAG[0]: (season == 2026)}
    for b, (lo, hi) in WEEK_BUCKETS.items():
        groups[f'{POOLED[0]} {b}'] = groups[POOLED[0]] & (wk >= lo) & (wk <= hi)

    def mse(e, w, mask):
        ok = mask & np.isfinite(e)
        se = np.bincount(cl[ok], e[ok], ncl); sw = np.bincount(cl[ok], w[ok], ncl)
        return se.sum()/sw.sum(), (C @ se)/(C @ sw)

    primary, feats = [], []
    for kind in ('recal', 'raw'):
        for arm in ARMS:
            ref = comparators[arm]
            for g, mask in groups.items():
                if not mask.any(): continue
                pct, boot = [], []
                for f in APPLIED[arm]:
                    w = d[f'w|{f}'].to_numpy(float)
                    a, ab = mse(S[(arm, f, kind)], w, mask); r, rb = mse(S[(ref, f, kind)], w, mask)
                    pct.append(100*(a/r-1)); boot.append(100*(ab/rb-1))
                    if kind == 'recal':
                        lo, hi = np.nanpercentile(boot[-1], [50*(1-FEATURE_LEVEL), 50*(1+FEATURE_LEVEL)])
                        feats.append({'arm': arm, 'group': g, 'feature': f, 'mse_arm': a, 'mse_comparator': r,
                                      'pct_change': pct[-1], 'ci95_lo': lo, 'ci95_hi': hi})
                stat = float(np.mean(pct)); bs = np.mean(np.vstack(boot), axis=0)
                lo, hi = np.nanpercentile(bs, [50*(1-LEVEL), 50*(1+LEVEL)])
                primary.append({'score': kind, 'arm': arm, 'comparator': ref, 'group': g, 'rows': int(mask.sum()),
                                'features': len(APPLIED[arm]), 'mean_pct_change': stat, 'ci9833_lo': lo, 'ci9833_hi': hi})
    return pd.DataFrame(primary), pd.DataFrame(feats)


def verdict(primary, arm):
    p = primary[(primary.score == 'recal') & (primary.arm == arm)].set_index('group')
    per = [float(p.loc[b, 'mean_pct_change']) for b in BASES]
    if sum(x >= 0 for x in per) >= 2: return 'stop'
    if all(x < 0 for x in per) and float(p.loc[POOLED[0], 'ci9833_hi']) < 0: return 'advance to stage 2'
    return 'unresolved'


# --- run --------------------------------------------------------------------------------------------

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guard(out):
    out = Path(out).resolve()
    if any(out == x or x in out.parents for x in (ROOT/'data', ROOT/'public')): raise ValueError('Protected output')
    return out


def run(out=OUT):
    out = guard(out); out.mkdir(parents=True, exist_ok=True)
    frozen = pd.read_csv(fw.BOXES); sched = fw.schedule_frame(pd.read_csv(fw.SCHEDULE))
    sched = sched[sched.result.notna()]
    print('Profiles: P, A, B'); tp = team_profiles(frozen, sched)
    print('Fidelity: P against form_windows.profiles(half_life=8)')
    ref = fw.profiles(frozen, sched, half_life=HALF_LIFE).set_index('game_id')
    mine = home_minus_away(tp, sched).set_index('game_id').loc[ref.index, ref.columns]
    a, b = ref.to_numpy(float), mine.to_numpy(float)
    if not np.array_equal(np.isfinite(a), np.isfinite(b)): raise ValueError('P availability differs from production')
    fid = {'games': int(len(ref)), 'max_abs_diff': float(np.nanmax(np.abs(a-b)))}
    if fid['max_abs_diff'] > 1e-9: raise ValueError(f'P does not reproduce production: {fid}')
    comparators = {a: 'P' for a in ARMS}
    cprov = json.loads((INPUTS/'provenance.json').read_text())
    boxes = capped_boxes(frozen, pd.read_csv(CAPPED))
    print('Profiles: C (capped) and Pc (uncapped rebuild)')
    tc = team_profiles(boxes['C'], sched, arms=('P',)); tpc = team_profiles(boxes['Pc'], sched, arms=('P',))
    key = ['game_id', 'team']
    tp = tp.merge(tc[key+[f'P|{f}' for f in APPLIED['C']]].rename(columns={f'P|{f}': f'C|{f}' for f in APPLIED['C']}), on=key, validate='one_to_one')
    tp = tp.merge(tpc[key+[f'P|{f}' for f in APPLIED['C']]].rename(columns={f'P|{f}': f'Pc|{f}' for f in APPLIED['C']}), on=key, validate='one_to_one')
    pc_diff = float(np.nanmax(np.abs(tp[[f'Pc|{f}' for f in APPLIED['C']]].to_numpy(float)-tp[[f'P|{f}' for f in APPLIED['C']]].to_numpy(float))))
    comparators['C'] = 'Pc'
    d = frame(tp)
    S = score(d, comparators)
    primary, feats = summarize(d, S, comparators)
    verdicts = {a: verdict(primary, a) for a in ARMS}
    keep = key+['season', 'week', 'history_games']+sorted(c for c in d if '|' in c)
    d[keep].to_csv(out/'stage1_frame.csv.gz', index=False, float_format='%.6g')
    primary.to_csv(out/'primary.csv', index=False, float_format='%.6g')
    feats.to_csv(out/'features.csv', index=False, float_format='%.6g')
    clip_rate = winsor_activity(frozen, sched)
    info = {'protocol': 'research/ROBUST_PROFILES.md', 'protocol_commit': PROTOCOL_COMMIT, 'interval_level': LEVEL,
            'feature_interval_level': FEATURE_LEVEL, 'draws': DRAWS, 'seed': SEED, 'scored_team_games': int(len(d)),
            'rows_by_group': {g: int(r) for g, r in primary[(primary.score == 'recal') & (primary.arm == 'A')].set_index('group').rows.items()},
            'fidelity_P_vs_production_profiles': fid, 'fidelity_uncapped_rebuild_vs_frozen': cprov['uncapped_fidelity_vs_frozen_boxes'],
            'Pc_minus_P_max_abs_diff': pc_diff, 'winsor_clip_share': clip_rate, 'verdicts': verdicts}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), PROTOCOL, ROOT/'nfl_model.py', ROOT/'research/form_windows.py',
                                                       fw.BOXES, fw.SCHEDULE, CAPPED)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, primary, feats, out)
    return info, primary, feats


def winsor_activity(box, sched):
    """Descriptive: share of history team-games each B threshold clips, at the final week of each season."""
    both = paired(box); res = {}
    for y in range(2015, 2026):
        wk = int(sched[sched.season == y].week.max())
        hist = both[m.before(both, y, wk) & (both.season >= y-m.MAX_HISTORY_SEASONS)]
        thr = thresholds(hist)
        for k, (num, den, _) in SPECS.items():
            x = hist[num].to_numpy(float)/(1. if den is None else hist[den].to_numpy(float))
            res.setdefault(k, []).append(float(np.mean((x < thr[k][0]) | (x > thr[k][1]))))
        for c in m.PEAK_COLUMNS:
            x = hist[c].to_numpy(float); res.setdefault(c, []).append(float(np.mean((x < thr[c][0]) | (x > thr[c][1]))))
    return {k: float(np.mean(v)) for k, v in res.items()}


def write_report(info, primary, feats, out):
    def f(x, fmt='+.2f'): return '–' if not np.isfinite(x) else format(x, fmt).replace('-', '−')
    names = {'A': 'A weighted median', 'B': 'B winsorized mean', 'C': 'C per-play cap'}
    groups = list(BASES)+[POOLED[0], DIAG[0]]
    L = ['# Test 49 stage 1: outlier-robust team profiles, stat-level screen', '',
         f"Protocol: [ROBUST_PROFILES.md](../ROBUST_PROFILES.md), pushed (`{info['protocol_commit']}`) before any arm was built or scored. "
         'Production v1.18 and the ledger are unchanged. No win/loss outcomes, prices or ROI are used. Development evidence on '
         'already-exposed seasons.', '',
         '## Fidelity', '',
         f"- P reproduces production's half-life-8 profiles (`form_windows.profiles`, tested against `nfl_model.lagged_features`) on "
         f"{info['fidelity_P_vs_production_profiles']['games']} games, max abs difference "
         f"{info['fidelity_P_vs_production_profiles']['max_abs_diff']:.1e}.",
         f"- Arm C's comparator (P on the uncapped re-aggregation of the same play-by-play) differs from frozen P by at most "
         f"{info['Pc_minus_P_max_abs_diff']:.1e}.", '',
         f"Scored team-games: {info['scored_team_games']} (all seasons, including warm-up 2013–14). "
         f"Interval level {100*info['interval_level']:.2f}% for the primary statistic; team-season cluster bootstrap, "
         f"{info['draws']} draws, seed {info['seed']}.", '',
         '## Primary statistic: mean % change in recalibrated MSE vs production (negative = better)', '',
         '| Arm | Features | '+' | '.join(groups)+' | Pooled 98.33% interval | Verdict |',
         '|---|---:|'+'---:|'*len(groups)+'---|---|']
    pr = primary[primary.score == 'recal']
    for a in ARMS:
        p = pr[pr.arm == a].set_index('group')
        L.append(f"| {names[a]} | {len(APPLIED[a])} | "+' | '.join(f(p.loc[g, 'mean_pct_change'], '+.3f') for g in groups)
                 + f" | [{f(p.loc[POOLED[0], 'ci9833_lo'], '+.3f')}, {f(p.loc[POOLED[0], 'ci9833_hi'], '+.3f')}] | {info['verdicts'][a]} |")
    L += ['', 'Raw (unrecalibrated) MSE, secondary:', '', '| Arm | '+' | '.join(groups)+' |', '|---|'+'---:|'*len(groups)]
    rw = primary[primary.score == 'raw']
    for a in ARMS:
        p = rw[rw.arm == a].set_index('group')
        L.append(f"| {names[a]} | "+' | '.join(f(p.loc[g, 'mean_pct_change'], '+.3f') for g in groups)+' |')
    L += ['', 'By week bucket, 2015–25 pooled (descriptive):', '', '| Arm | '+' | '.join(WEEK_BUCKETS)+' |', '|---|'+'---:|'*len(WEEK_BUCKETS)]
    for a in ARMS:
        p = pr[pr.arm == a].set_index('group')
        L.append(f"| {names[a]} | "+' | '.join(f(p.loc[f'{POOLED[0]} {b}', 'mean_pct_change'], '+.3f') for b in WEEK_BUCKETS)+' |')
    L += ['', '## Per feature: % change in recalibrated MSE (2015–25 pooled, 95% interval; descriptive)', '',
          '| Feature | '+' | '.join(names[a] for a in ARMS)+' |', '|---|'+'---|'*len(ARMS)]
    fp = feats[feats.group == POOLED[0]]
    for ft in FEATURES:
        cells = []
        for a in ARMS:
            r = fp[(fp.arm == a) & (fp.feature == ft)]
            cells.append('–' if r.empty else f"{f(r['pct_change'].iloc[0], '+.2f')} [{f(r['ci95_lo'].iloc[0], '+.2f')}, {f(r['ci95_hi'].iloc[0], '+.2f')}]")
        L.append(f'| {ft} | '+' | '.join(cells)+' |')
    L += ['', 'Arm B clip activity: share of history team-games outside the 2.5–97.5% thresholds (final week of each 2015–25 '
          'season, averaged): '+', '.join(f'{k} {100*v:.1f}%' for k, v in info['winsor_clip_share'].items())+'.', '']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--capped', metavar='PBP_DIR', help='build arm C capped yardage from raw play-by-play')
    a = ap.parse_args()
    if a.capped: build_capped(a.capped)
    else: run()
