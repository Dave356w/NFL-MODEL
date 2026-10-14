"""Test 43: team profiles from the last 2, 3 or 4 games instead of production's decay; see FORM_WINDOWS.md.

    python research/form_windows.py --boxes PBP_DIR GAMES_CSV   # rebuild and freeze box scores (raw files needed)
    python research/form_windows.py                             # fidelity check, arms, comparison (no network)

Never writes data/ or the ledger. Development evidence only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import model_updates as mu  # noqa: E402
import kalman_ratings as kr  # noqa: E402
import kalman_iterations as ki  # noqa: E402

INPUTS = ROOT/'research/form_windows_inputs'
BOXES = INPUTS/'boxes.csv'
SCHEDULE = INPUTS/'schedule.csv'
OUT = ROOT/'research/form_windows_results'
PROTOCOL_COMMIT = 'd06f8e5'
SEASONS = range(2013, 2027)
FAMILY = m.LEGACY_PRODUCT_RECIPE['family']
PRODUCTION = list(m.feature_names(FAMILY))+list(m.PRODUCT_CONTEXT_NAMES)
MAIN = [n for n in PRODUCTION if n.startswith('d__for__') or n.startswith('d__allowed__')]+list(m.PEAK_FEATURES)
WINDOWS = (2, 3, 4)
PRIMARY = tuple(f'window_{n}' for n in WINDOWS)
SCHEDULE_COLS = ['game_id', 'season', 'week', 'gameday', 'gametime', 'home_team', 'away_team', 'location', 'result',
                 'home_score', 'away_score', 'spread_line', 'home_moneyline', 'away_moneyline']
PBP_COLS = ['game_id', 'play_id', 'season_type', 'posteam', 'play_type', 'yards_gained', 'pass_attempt', 'rush_attempt',
            'sack', 'interception', 'fumble_lost', 'third_down_converted', 'third_down_failed', 'first_down_rush',
            'first_down_pass', 'first_down_penalty', 'penalty', 'penalty_team', 'penalty_yards', 'two_point_attempt',
            'drive', 'drive_time_of_possession', 'play_deleted', 'fumbled_1_team', 'fumbled_2_team',
            'fumble_recovery_1_team', 'fumble_recovery_2_team', 'passer_player_id', 'passer_player_name',
            'qtr', 'game_seconds_remaining', 'total_home_score', 'total_away_score', 'sp']


def schedule_frame(s):
    """The columns production's schedule loader adds (load_schedule), from a raw nflverse schedule."""
    s = m.normalize_teams(s.copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.get('location', pd.Series('', index=s.index)).astype(str).str.lower() == 'neutral', 0., 1.)
    s['market WP'] = ndtr(pd.to_numeric(s.spread_line, errors='coerce')/m.MARKET_SIGMA)
    return s


# --- build: rebuild and freeze box scores ----------------------------------------------------------

def build(pbp_dir, games_csv):
    INPUTS.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(games_csv)
    g = g[(g.game_type == 'REG') & g.season.between(min(SEASONS), max(SEASONS))][SCHEDULE_COLS]
    g.to_csv(SCHEDULE, index=False)
    sched = schedule_frame(pd.read_csv(SCHEDULE))
    boxes, prov = [], {'games_csv_sha256': hashlib.sha256(Path(games_csv).read_bytes()).hexdigest(), 'pbp': {}}
    import out_of_sample_2017_2020 as oos  # the packs' committed score-peak repair (clock order -> play ID order)
    strict, m.aggregate_score_peaks = m.aggregate_score_peaks, oos.repaired_score_peaks
    try:
        _build_seasons(pbp_dir, sched, boxes, prov)
    finally:
        m.aggregate_score_peaks = strict
    prov['score_peak_repairs'] = sorted(oos.PEAK_REPAIRS, key=lambda r: r['game_id'])
    pd.concat(boxes, ignore_index=True).to_csv(BOXES, index=False, float_format='%.6f')
    prov.update(boxes_sha256=hashlib.sha256(BOXES.read_bytes()).hexdigest(), schedule_sha256=hashlib.sha256(SCHEDULE.read_bytes()).hexdigest(),
                note='Rebuilt with nfl_model.aggregate_boxscores / merge_score_peaks / validate_boxes (score-peak repair from '
                     'out_of_sample_2017_2020.py) from the Test 40 play-by-play download and the Test 37 schedule download. '
                     'Raw files are not committed.')
    (INPUTS/'provenance.json').write_text(json.dumps(prov, indent=2))


def _build_seasons(pbp_dir, sched, boxes, prov):
    for y in SEASONS:
        f = Path(pbp_dir)/f'play_by_play_{y}.parquet'
        prov['pbp'][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        p = m.normalize_teams(pd.read_parquet(f, columns=[c for c in PBP_COLS if c]))
        s = sched[sched.season == y]
        if s.result.notna().sum() == 0: continue
        b = m.aggregate_boxscores(p, s, y)
        b = m.merge_score_peaks(b, p, s)
        boxes.append(m.validate_boxes(b))
        print(f'  {y}: {len(b)} team-games')


# --- windowed profiles -----------------------------------------------------------------------------

def team_weights(h, year, n=None, half_life=None):
    """Equal weights on the last n games, or production's decay (2^(-age/h) halved per season boundary)."""
    k = len(h)
    if n is not None:
        w = np.zeros(k); w[max(0, k-n):] = 1.
        return w
    age = np.arange(k-1, -1, -1, dtype=float)
    return np.exp2(-age/half_life)*np.power(m.OFFSEASON_RETENTION, year-h.season.to_numpy(float))


def profiles(box, schedules, n=None, half_life=None):
    """Main box-score rates (raw family) and score peaks per game, home minus away, from strictly earlier
    games, weighted by `team_weights`. With half_life=8 this is production's computation (checked in tests)."""
    box = m.validate_boxes(box)
    opp = box[['game_id', 'team', *m.COUNTS]].rename(columns={'team': 'opponent', **{c: 'opp_'+c for c in m.COUNTS}})
    both = box.merge(opp, on=['game_id', 'opponent'], how='left', validate='one_to_one')
    specs = m.FAMILIES['rates_core']
    rows = []
    for (year, week), games in schedules.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        hist = both[m.before(both, year, week) & (both.season >= year-m.MAX_HISTORY_SEASONS)]
        league = hist[list(m.COUNTS)].to_numpy(float)
        prof = {}
        for team in set(games.home_team) | set(games.away_team):
            h = hist[hist.team == team].sort_values(['season', 'week', 'game_id'])
            w = team_weights(h, year, n, half_life)
            pr = {}
            for c in m.PEAK_COLUMNS: pr[c] = float(np.dot(w, h[c].to_numpy(float))/(w.sum()+m.PRIOR_EQUIVALENT_GAMES))
            for role, cols in (('for', list(m.COUNTS)), ('allowed', ['opp_'+c for c in m.COUNTS])):
                for metric, v in m.metric_profile(h[cols].to_numpy(float), w, league, specs).items():
                    pr[f'{role}__rates_core__{metric}'] = v
            prof[team] = pr
        for g in games.itertuples(index=False):
            r = {'game_id': g.game_id}
            for k, v in prof[g.home_team].items():
                r[f'd__{k}'] = v-prof[g.away_team][k]
            rows.append(r)
    out = pd.DataFrame(rows)
    return out[['game_id']+[c for c in MAIN if c in out]]


def swap(df, prof):
    """Replace the main profile columns of a pack frame with rebuilt ones (by game_id)."""
    keep = df.drop(columns=[c for c in MAIN if c in df])
    out = keep.merge(prof, on='game_id', how='left', validate='many_to_one')
    if out[MAIN].isna().all(axis=1).any(): raise ValueError('Games without rebuilt profiles')
    return out


def arm_frame(parts, prof):
    rows = []
    for pack, games in parts:
        pk, gm = swap(pack, prof), swap(games, prof)
        for (y, w), g in gm.groupby(['season', 'week']):
            f = kr.fit(pk[m.before(pk, int(y), int(w))], PRODUCTION, int(y), int(w))
            rows.append(g.assign(p16=kr.predict(g, f)))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d)


def fidelity(prof):
    """Rebuilt half-life-8 profiles against the frozen packs' features, per pack."""
    out = {}
    for name, path in (('2013-20 pack', t.OOS_PACK), ('2019-26 pack', t.T36_PACK)):
        pk = pd.read_csv(path)[['game_id', 'season']+MAIN].merge(prof, on='game_id', suffixes=('', '_r'))
        d = np.abs(pk[MAIN].to_numpy(float)-pk[[c+'_r' for c in MAIN]].to_numpy(float))
        ident = np.nan_to_num(d, nan=0.).max(axis=1) <= 1e-9  # NaN only where neither side has history
        out[name] = {'games': int(len(pk)), 'max_abs_diff': float(np.nanmax(d)), 'share_games_identical': float(ident.mean()),
                     'identical_by_season': {str(int(k)): float(v) for k, v in pd.Series(ident).groupby(pk.season.to_numpy()).mean().items()}}
    return out


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    box = pd.read_csv(BOXES); sched = schedule_frame(pd.read_csv(SCHEDULE))
    prof = {'production': profiles(box, sched, half_life=8.)}
    fid = fidelity(prof['production'])
    for n in WINDOWS: prof[f'window_{n}'] = profiles(box, sched, n=n)
    parts = {**fi.basis_parts(), '2026 wk1-5 (diagnostic)': mu.extra_parts()['2026 wk1-5 (diagnostic)']}
    frames = {(b, a): arm_frame(p, prof[a]) for b, p in parts.items() for a in prof}
    published = {b: mu.basis_frame(p, 'production', b) for b, p in parts.items()}
    agree = {}
    for b in parts:
        j = published[b][['game_id', 'p']].merge(frames[(b, 'production')][['game_id', 'p']], on='game_id', suffixes=('_pub', '_reb'))
        agree[b] = {'games': int(len(j)), 'max_abs_diff': float(np.max(np.abs(j.p_pub-j.p_reb))), 'mean_abs_diff': float(np.mean(np.abs(j.p_pub-j.p_reb))),
                    'same_side': float(np.mean((j.p_pub > .5) == (j.p_reb > .5)))}
    hist = {a: pd.concat([frames[(b, a)] for b in fi.BASES], ignore_index=True) for a in prof}
    choice = ki.select(hist)
    for b in ('2017-22', '2023-25'):
        frames[(b, 'selected')] = pd.concat([frames[(b, a)][frames[(b, a)].season == y] for y, a in choice.items()], ignore_index=True)
    rows, mkt = [], []
    for (b, a), d in frames.items():
        if a == 'production': continue
        rows += kr.compare(frames[(b, 'production')], d, b, a)
    for (b, a), d in frames.items():
        g, se = kr.vs_market(d); mkt.append({'basis': b, 'arm': a, 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    mkt = pd.DataFrame(mkt); mkt.to_csv(out/'vs_market.csv', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'p']].assign(basis=b, arm=a) for (b, a), d in frames.items()]).to_csv(out/'predictions.csv.gz', index=False, float_format='%.6g')
    prod_roi = {b: m.roi_summary(m.flat_bets(frames[(b, 'production')][frames[(b, 'production')].bet].assign(
        model_wp=frames[(b, 'production')].p[frames[(b, 'production')].bet]))) for b in parts}
    verdicts = {a: kr.verdict(res[res.arm == a]) for a in PRIMARY}
    verdicts['selected (descriptive)'] = ki.verdict(res[res.arm == 'selected'], ('2017-22', '2023-25'))
    info = {'protocol': 'research/FORM_WINDOWS.md', 'protocol_commit': PROTOCOL_COMMIT, 'level': kr.LEVEL, 'fidelity_vs_packs': fid,
            'rebuilt_vs_published_production': agree, 'verdicts': verdicts, 'selected_by_season': {str(k): v for k, v in choice.items()},
            'binary_games': {b: int(frames[(b, 'production')].y.notna().sum()) for b in parts},
            'production_roi': {b: {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/FORM_WINDOWS.md', ROOT/'nfl_model.py', BOXES, SCHEDULE,
                                                       t.OOS_PACK, t.T36_PACK, t.OOS_PRED, t.HELDOUT, t.RETRO, t.TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, mkt, prod_roi, out)
    return info, res, mkt


def write_report(info, res, mkt, prod_roi, out):
    B = list(fi.BASES); D = '2026 wk1-5 (diagnostic)'; allr = res[res.context == 'all']
    L = ['# Test 43: team profiles from the last 2, 3 or 4 games instead of long decay', '',
         f"Protocol: [FORM_WINDOWS.md](../FORM_WINDOWS.md), pushed (`{PROTOCOL_COMMIT}`) before any windowed profile was built or scored. "
         'Production v1.18 and the ledger are unchanged. Development evidence only.', '',
         '## Rebuild fidelity', '',
         'Production\'s half-life-8 profiles recomputed from the rebuilt box scores, against the frozen packs:', '']
    for k, v in info['fidelity_vs_packs'].items():
        L.append(f"- {k}: {v['games']} games; max abs difference {v['max_abs_diff']:.2e}; {100*v['share_games_identical']:.1f}% of games identical "
                 'to 1e-9; by season ' + ', '.join(f'{y} {100*x:.0f}%' for y, x in v['identical_by_season'].items()) + '.')
    L += ['', 'The 2019-26 pack, like the published 2021-25 history it reproduces exactly, starts its history in 2019, so its 2019-21 profiles lack the 2016-18 games '
          'that the three-season window reaches; the rebuild carries them, as the 2013-20 pack does. 2022-25 are identical. 2026 differs '
          'through upstream revisions of the current season (diagnostic only).']
    L += ['', 'Rebuilt production (rebuilt profiles, packs\' availability and pass contexts) against the published v1.18 forecasts:', '']
    for k, v in info['rebuilt_vs_published_production'].items():
        L.append(f"- {k}: max |dp| {v['max_abs_diff']:.2e}, mean {v['mean_abs_diff']:.2e}, same side {100*v['same_side']:.1f}%.")
    L += ['', 'Every arm, the comparator included, is scored on the rebuilt features (one data version).', '',
          '## Verdicts (log-loss gain over rebuilt production decides)', '']
    for a, v in info['verdicts'].items(): L.append(f"- **{a}**: {v}")
    L += ['', 'Nested selection chose, by season: ' + ', '.join(f'{y} {a}' for y, a in info['selected_by_season'].items()) + '.', '',
          '## Log-loss gain over rebuilt production (x1000 per game; [98.33% interval])', '',
          '| Arm | ' + ' | '.join(B) + ' | 2026 wk1-5 (diag.) |', '|---|' + '---:|'*(len(B)+1)]
    for a in PRIMARY+('selected',):
        r = allr[allr.arm == a].set_index('basis')
        cells = [f"{r.loc[b, 'll_gain_x1000']:+.2f} [{r.loc[b, 'lo_x1000']:+.2f}, {r.loc[b, 'hi_x1000']:+.2f}]" if b in r.index else '-' for b in B]
        L.append(f"| {a} | " + ' | '.join(cells) + ' | ' + (f"{r.loc[D, 'll_gain_x1000']:+.2f}" if D in r.index else '-') + ' |')
    L += ['', '## Log-loss gain over the market (x1000 per game ± SE)', '', '| Model | ' + ' | '.join(B) + ' | 2026 wk1-5 |', '|---|' + '---:|'*(len(B)+1)]
    for a in ('production',)+PRIMARY+('selected',):
        r = mkt[mkt.arm == a].set_index('basis')
        L.append(f"| {'rebuilt production' if a == 'production' else a} | " + ' | '.join(
            (f"{r.loc[b, 'll_gain_vs_market_x1000']:+.2f} ± {r.loc[b, 'se_x1000']:.2f}" if b in r.index else '-') for b in B+[D]) + ' |')
    L += ['', '## Flat 1u ROI (goal metric; reported, not used for the verdict)', '',
          '| Model | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B),
          '| rebuilt production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u)" for b in B) + ' |']
    for a in PRIMARY+('selected',):
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join((f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod, "
                                           f"{int(r.loc[b, 'side_flips'])} flips") if b in r.index else '-' for b in B) + ' |')
    r0 = allr[allr.arm == PRIMARY[0]].set_index('basis')
    L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
        f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in B) + '.', '',
          '## By total band (log-loss gain x1000; units vs rebuilt production)', '',
          '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
    for a in PRIMARY:
        for b in B:
            r = res[(res.arm == a) & (res.basis == b)].set_index('context')
            L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                    for c in ('total_low', 'total_mid', 'total_high')) + ' |')
    L += ['', '## Limits', '',
          'Exposed history; Test 8 swept half-lives on an older model. Upstream play-by-play revisions can make rebuilt profiles differ '
          'slightly from the frozen packs, so all arms use the rebuilt data. A "better" verdict would justify only a forward shadow test. '
          'Tables: `arms.csv`, `vs_market.csv`, `predictions.csv.gz`.', '',
          'Run: `python research/form_windows.py --boxes PBP_DIR GAMES_CSV` (raw files), then `python research/form_windows.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--boxes', nargs=2, metavar=('PBP_DIR', 'GAMES_CSV'), help='rebuild and freeze box scores from raw files')
    a = ap.parse_args()
    build(*a.boxes) if a.boxes else run()
