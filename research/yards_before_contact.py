"""Test 44: yards before contact and tackles for loss, offense and defense; see YARDS_BEFORE_CONTACT.md.

    python research/yards_before_contact.py --build DIR --pbp PBP_DIR   # freeze team-game aggregates from raw files
    python research/yards_before_contact.py                             # profiles, arms, comparison (no network)

Never writes data/ or the ledger. Development evidence only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import model_updates as mu  # noqa: E402
import kalman_ratings as kr  # noqa: E402
import kalman_iterations as ki  # noqa: E402
import form_windows as fw  # noqa: E402

INPUTS = ROOT/'research/ybc_inputs'
TEAM_GAMES = INPUTS/'team_games.csv'
TFL_GAMES = INPUTS/'tfl_team_games.csv'
OUT = ROOT/'research/ybc_results'
PROTOCOL_COMMIT = 'fac1eee'
ADDENDUM_COMMIT = '1c0464d'
URL = 'https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_rush_{y}.parquet'
SEASONS = range(2018, 2027)
PBP_SEASONS = range(2013, 2027)
PBP_COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'play_type', 'qb_scramble',
            'tackled_for_loss', 'two_point_attempt', 'play_deleted']
HALF_LIFE = 8.
SPLIT = ['d_ybc_off', 'd_ybc_def', 'd_yac_off', 'd_yac_def']
TFL = ['d_tfl_off', 'd_tfl_def']
PRODUCTION = list(fw.PRODUCTION)
RUSH = ['d__for__rates_core__rush_yards_per_attempt', 'd__allowed__rates_core__rush_yards_per_attempt']
ARMS = {'plus_ybc': PRODUCTION+['d_ybc_off', 'd_ybc_def'],
        'plus_ybc_yac': PRODUCTION+SPLIT,
        'swap_rush': [n for n in PRODUCTION if n not in RUSH]+SPLIT,
        'plus_tfl': PRODUCTION+TFL}
PRIMARY = tuple(ARMS)
LEVEL = 1-.05/len(PRIMARY)  # K = 4 (addendum); 98.75% intervals for every arm
Z = float(norm.ppf(1-(1-LEVEL)/2))
BASES = ('2021-22', '2023-25')
TFL_BASES = tuple(fi.BASES)
ARM_BASES = {a: TFL_BASES if a == 'plus_tfl' else BASES for a in ARMS}
DIAG = '2026 wk1-5 (diagnostic)'


# --- build -----------------------------------------------------------------------------------------

def aggregate(raw):
    d = raw[raw.game_type == 'REG'].copy()
    for c in ('team', 'opponent'): d[c] = d[c].replace(m.TEAM_ALIASES)
    cols = {'carries': 'carries', 'rushing_yards_before_contact': 'ybc', 'rushing_yards_after_contact': 'yac',
            'rushing_broken_tackles': 'broken_tackles'}
    g = d.groupby(['game_id', 'season', 'week', 'team', 'opponent'], as_index=False)[list(cols)].sum(min_count=1)
    return g.rename(columns=cols)


def aggregate_tfl(p):
    """Designed runs (play_type run, not a scramble, not deleted, not a two-point try) and runs tackled
    for a loss, per team game, regular season."""
    p = p[(p.season_type == 'REG') & (p.play_type == 'run')].copy()
    for c in ('qb_scramble', 'play_deleted', 'two_point_attempt'):
        if c in p: p = p[pd.to_numeric(p[c], errors='coerce').fillna(0) != 1]
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(m.TEAM_ALIASES)
    p['tfl'] = (pd.to_numeric(p.tackled_for_loss, errors='coerce').fillna(0) == 1).astype(int)
    g = p.groupby(['game_id', 'season', 'week', 'posteam', 'defteam'], as_index=False).agg(runs=('tfl', 'size'), tfl=('tfl', 'sum'))
    return g.rename(columns={'posteam': 'team', 'defteam': 'opponent'})


def build(raw_dir, pbp_dir):
    INPUTS.mkdir(parents=True, exist_ok=True)
    parts, prov = [], {'source': URL, 'files': {}, 'pbp_source': kr.PBP_URL, 'pbp_files': {}}
    for y in SEASONS:
        f = Path(raw_dir)/f'advstats_week_rush_{y}.parquet'
        prov['files'][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        parts.append(aggregate(pd.read_parquet(f)))
    tg = pd.concat(parts, ignore_index=True).sort_values(['season', 'week', 'game_id', 'team'])
    tg.to_csv(TEAM_GAMES, index=False)
    test40 = json.loads((ROOT/'research/kalman_ratings_inputs/provenance.json').read_text())['files']
    tparts = []
    for y in PBP_SEASONS:
        f = Path(pbp_dir)/f'play_by_play_{y}.parquet'
        prov['pbp_files'][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        if prov['pbp_files'][f.name] != test40[f.name]: raise ValueError(f'{f.name} is not the Test 40 download')
        tparts.append(aggregate_tfl(pd.read_parquet(f, columns=PBP_COLS)))
    tf = pd.concat(tparts, ignore_index=True).sort_values(['season', 'week', 'game_id', 'team'])
    tf.to_csv(TFL_GAMES, index=False)
    prov.update(team_games_sha256=hashlib.sha256(TEAM_GAMES.read_bytes()).hexdigest(), rows=len(tg),
                tfl_team_games_sha256=hashlib.sha256(TFL_GAMES.read_bytes()).hexdigest(), tfl_rows=len(tf),
                note='team_games.csv: nflverse weekly PFR advanced rushing stats, regular season, summed per team game. '
                     'tfl_team_games.csv: designed runs and runs tackled for a loss per team game from the Test 40 play-by-play '
                     '(hashes checked against kalman_ratings_inputs/provenance.json). Raw files not committed.')
    (INPUTS/'provenance.json').write_text(json.dumps(prov, indent=2))


# --- profiles --------------------------------------------------------------------------------------

def ratio(h, w, num, den, league):
    """Production's metric_profile form: weighted sums plus four league-average pseudo-games."""
    lok = league[num].notna().to_numpy() & league[den].notna().to_numpy() & (league[den].to_numpy(float) > 0)
    if not lok.any(): return np.nan
    pa, pb = float(league[num].to_numpy(float)[lok].mean()), float(league[den].to_numpy(float)[lok].mean())
    ok = h[num].notna().to_numpy() & h[den].notna().to_numpy() & (h[den].to_numpy(float) > 0)
    numer = float(np.dot(w[ok], h[num].to_numpy(float)[ok]))+m.PRIOR_EQUIVALENT_GAMES*pa
    denom = float(np.dot(w[ok], h[den].to_numpy(float)[ok]))+m.PRIOR_EQUIVALENT_GAMES*pb
    return numer/denom if denom > 0 else np.nan


YBC_SPECS = {'ybc': ('ybc', 'carries'), 'yac': ('yac', 'carries')}
TFL_SPECS = {'tfl': ('tfl', 'runs')}


def profiles(tg, games, specs=YBC_SPECS):
    """Home-minus-away profiles for every game in `games` (season, week, game_id, home, away), from
    strictly earlier team games, weighted as production weights team profiles. `specs` maps a profile
    name to (numerator, denominator) columns of `tg`."""
    tg = tg.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    rows = []
    for (year, week), g in games.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        hist = tg[m.before(tg, year, week) & (tg.season >= year-m.MAX_HISTORY_SEASONS)]
        prof = {}
        for team in set(g.home) | set(g.away):
            r = {}
            for side, rows_ in (('off', hist[hist.team == team]), ('def', hist[hist.opponent == team])):
                h = rows_.sort_values(['season', 'week', 'game_id'])
                w = fw.team_weights(h, year, half_life=HALF_LIFE)
                for name, (num, den) in specs.items(): r[f'{name}_{side}'] = ratio(h, w, num, den, hist)
            prof[team] = r
        for x in g.itertuples(index=False):
            rows.append({'game_id': x.game_id, **{f'd_{k}': prof[x.home][k]-prof[x.away][k] for k in prof[x.home]}})
    return pd.DataFrame(rows)


# --- arms ------------------------------------------------------------------------------------------

def parts():
    """Every scored basis: Tests 40-43's three (tackles for loss), 2021-22 (yards before contact) and the
    2026 diagnostic. 2023-25 and the diagnostic are the same rows for both families."""
    t36 = pd.read_csv(t.T36_PACK)
    return {**fi.basis_parts(), '2021-22': [(t36, t36[t36.season.isin([2021, 2022])])],
            DIAG: mu.extra_parts()[DIAG]}


def frame(part, prof, names):
    rows = []
    for pack, games in part:
        pk = pack.merge(prof, on='game_id', how='left', validate='one_to_one')
        gm = games.merge(prof, on='game_id', how='left', validate='one_to_one')
        for (y, w), g in gm.groupby(['season', 'week']):
            f = kr.fit(pk[m.before(pk, int(y), int(w))], names, int(y), int(w))
            rows.append(g.assign(p16=kr.predict(g, f)))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d)


def coefficients(part, prof, names, keep):
    out = []
    for pack, games in part:
        pk = pack.merge(prof, on='game_id', how='left', validate='one_to_one')
        for (y, w), _ in games.groupby(['season', 'week']):
            f = kr.fit(pk[m.before(pk, int(y), int(w))], names, int(y), int(w))
            out.append(dict(zip(names, map(float, f['beta']))))
    c = pd.DataFrame(out)
    return {n: {'mean_per_sd': float(c[n].mean()), 'share_positive': float((c[n] > 0).mean())} for n in keep}


def reproduction(prod):
    """Production must reproduce its published forecasts: Tests 38-43's checks plus the 2021-22 basis."""
    errs = fi.reproduction(prod)
    a = prod['2021-22'].merge(pd.read_csv(t.RETRO)[['game_id', 'model_wp']], on='game_id', validate='one_to_one')
    errs['2021-22 basis'] = float(np.max(np.abs(a.p-a.model_wp)))
    if errs['2021-22 basis'] > 1e-9: raise ValueError(f"2021-22 does not reproduce ({errs['2021-22 basis']:.1e})")
    return errs


def compare(prod, arm, basis, name):
    old = mu.Z; mu.Z = Z
    try: return mu.compare(prod, arm, basis, name)
    finally: mu.Z = old


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def all_profiles():
    keys = ['game_id', 'season', 'week', 'home', 'away']
    oos, t36 = pd.read_csv(t.OOS_PACK), pd.read_csv(t.T36_PACK)
    games = pd.concat([oos[keys], t36[keys]], ignore_index=True).drop_duplicates('game_id')
    ybc = profiles(pd.read_csv(TEAM_GAMES), t36[keys])
    tfl = profiles(pd.read_csv(TFL_GAMES), games, TFL_SPECS)
    return tfl.merge(ybc, on='game_id', how='left', validate='one_to_one')


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    prof = all_profiles()
    P = parts()
    prod = {b: frame(p, prof, PRODUCTION) for b, p in P.items()}
    repro = reproduction(prod)
    frames = {(b, a): frame(P[b], prof, names) for a, names in ARMS.items() for b in ARM_BASES[a]+(DIAG,)}
    rows, mkt = [], []
    for (b, a), d in frames.items():
        rows += compare(prod[b], d, b, a)
        g, se = kr.vs_market(d); mkt.append({'basis': b, 'arm': a, 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    for b, d in prod.items():
        g, se = kr.vs_market(d); mkt.append({'basis': b, 'arm': 'production', 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    mkt = pd.DataFrame(mkt); mkt.to_csv(out/'vs_market.csv', index=False, float_format='%.6g')
    prof.to_csv(out/'profiles.csv.gz', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'p']].assign(basis=b, arm=a) for (b, a), d in frames.items()] +
              [d[['game_id', 'p']].assign(basis=b, arm='production') for b, d in prod.items()]).to_csv(
        out/'predictions.csv.gz', index=False, float_format='%.6g')
    oos, t36 = pd.read_csv(t.OOS_PACK), pd.read_csv(t.T36_PACK)
    ev = pd.concat([oos[oos.season.between(2015, 2020)][['game_id', 'season']+RUSH],
                    t36[t36.season.between(2021, 2025)][['game_id', 'season']+RUSH]], ignore_index=True).merge(prof, on='game_id')
    corr = ev[ev.season >= 2021][RUSH+SPLIT+TFL].corr()
    corr.round(3).to_csv(out/'correlations_2021_25.csv')
    corr_tfl = ev[RUSH+TFL].corr().loc[RUSH, TFL]
    coefs = {'plus_ybc_yac': {b: coefficients(P[b], prof, ARMS['plus_ybc_yac'], SPLIT+RUSH) for b in BASES},
             'plus_tfl': {b: coefficients(P[b], prof, ARMS['plus_tfl'], TFL+RUSH) for b in TFL_BASES}}
    coverage = {fam: {b: float(pd.concat([g for _, g in P[b]]).merge(prof, on='game_id')[cols].notna().all(axis=1).mean())
                      for b in bases+(DIAG,)} for fam, cols, bases in (('ybc', SPLIT, BASES), ('tfl', TFL, TFL_BASES))}
    prod_roi = {b: m.roi_summary(m.flat_bets(d[d.bet].assign(model_wp=d.p[d.bet]))) for b, d in prod.items()}
    info = {'protocol': 'research/YARDS_BEFORE_CONTACT.md', 'protocol_commit': PROTOCOL_COMMIT, 'addendum_commit': ADDENDUM_COMMIT,
            'level': LEVEL, 'reproduction_max_error': repro,
            'verdicts': {a: ki.verdict(res[res.arm == a], ARM_BASES[a]) for a in PRIMARY},
            'corr_2021_25': json.loads(corr.loc[RUSH, SPLIT+TFL].to_json()), 'corr_tfl_2015_25': json.loads(corr_tfl.to_json()),
            'corr_tfl_ybc_2021_25': json.loads(corr.loc[TFL, ['d_ybc_off', 'd_ybc_def']].to_json()),
            'coefficients': coefs, 'coverage': coverage,
            'binary_games': {b: int(d.y.notna().sum()) for b, d in prod.items()},
            'production_roi': {b: {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/YARDS_BEFORE_CONTACT.md', ROOT/'research/form_windows.py',
                                                       ROOT/'nfl_model.py', TEAM_GAMES, TFL_GAMES, t.OOS_PACK, t.T36_PACK, t.OOS_PRED,
                                                       t.RETRO, t.HELDOUT, t.TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, mkt, prod_roi, out)
    return info, res, mkt


def short(n):
    return n.replace('d__for__rates_core__', 'off ').replace('d__allowed__rates_core__', 'def ')


def write_report(info, res, mkt, prod_roi, out):
    allr = res[res.context == 'all']
    pct = f'{100*LEVEL:.2f}%'
    L = ['# Test 44: yards before contact and tackles for loss, offense and defense', '',
         f"Protocol: [YARDS_BEFORE_CONTACT.md](../YARDS_BEFORE_CONTACT.md), pushed (`{PROTOCOL_COMMIT}`) before any profile was built or scored; "
         f"tackles-for-loss addendum pushed (`{ADDENDUM_COMMIT}`) before any profile was built or scored. Production v1.18 and the ledger are "
         'unchanged. Development evidence only.', '',
         'Production reproduces its published forecasts (max abs error): ' + ', '.join(f'{k} {v:.1e}' for k, v in info['reproduction_max_error'].items()) + '.', '',
         '**Inputs** (home minus away, production\'s half-life-8 weighting with four league pseudo-games): yards before contact per carry, offense '
         '(`d_ybc_off`) and allowed (`d_ybc_def`); yards after contact per carry (`d_yac_off`, `d_yac_def`), PFR charting via nflverse from 2018; '
         'share of designed runs tackled for a loss, offense (`d_tfl_off`, higher is worse) and forced by the defense (`d_tfl_def`), nflverse '
         'play-by-play from 2013.', '',
         'Coverage of evaluation games: ' + '; '.join(f"{fam} " + ', '.join(f'{b} {100*v:.0f}%' for b, v in c.items())
                                                    for fam, c in info['coverage'].items()) + '.', '',
         '## Verdicts (log-loss gain over production decides; K = 4)', '']
    for a, v in info['verdicts'].items(): L.append(f"- **{a}** ({', '.join(ARM_BASES[a])}): {v}")
    L += ['', f'Rule: better if the gain is positive on every basis and its {pct} interval excludes zero on at least one; not better if <= 0 '
          'on at least half the bases (one of two; two of three); otherwise unresolved.', '']
    for title, arms, bases in (('Yards before / after contact', [a for a in PRIMARY if a != 'plus_tfl'], BASES),
                               ('Tackles for loss', ['plus_tfl'], TFL_BASES)):
        B = list(bases)
        L += [f'## {title}: log-loss gain over production (x1000 per game; [{pct} interval])', '',
              '| Arm | ' + ' | '.join(B) + ' | 2026 wk1-5 (diag.) |', '|---|' + '---:|'*(len(B)+1)]
        for a in arms:
            r = allr[allr.arm == a].set_index('basis')
            L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_x1000']:+.2f} [{r.loc[b, 'lo_x1000']:+.2f}, {r.loc[b, 'hi_x1000']:+.2f}]" for b in B)
                     + f" | {r.loc[DIAG, 'll_gain_x1000']:+.2f} |")
        L += ['', 'Log-loss gain over the market (x1000 per game ± SE):', '', '| Model | ' + ' | '.join(B) + ' | 2026 wk1-5 |', '|---|' + '---:|'*(len(B)+1)]
        for a in ['production']+arms:
            r = mkt[mkt.arm == a].set_index('basis')
            L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_vs_market_x1000']:+.2f} ± {r.loc[b, 'se_x1000']:.2f}" for b in B+[DIAG]) + ' |')
        L += ['', 'Flat 1u ROI at the moneyline (goal metric; reported, not used for the verdict):', '',
              '| Model | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B),
              '| production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u, "
                                             f"n={int(prod_roi[b]['bets'])})" for b in B) + ' |']
        for a in arms:
            r = allr[allr.arm == a].set_index('basis')
            L.append(f"| {a} | " + ' | '.join(f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod, "
                                              f"{int(r.loc[b, 'side_flips'])} flips" for b in B) + ' |')
        r0 = allr[allr.arm == arms[0]].set_index('basis')
        L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
            f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in B) + '.', '',
              'By total band (log-loss gain x1000; units vs production):', '',
              '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
        for a in arms:
            for b in B:
                r = res[(res.arm == a) & (res.basis == b)].set_index('context')
                L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                        for c in ('total_low', 'total_mid', 'total_high')) + ' |')
        L.append('')
    L += ['## What the fits learn (mean fitted coefficient per SD; share of weekly fits positive)', '']
    for arm, keep, bases in (('plus_ybc_yac', SPLIT+RUSH, BASES), ('plus_tfl', TFL+RUSH, TFL_BASES)):
        B = list(bases); c = info['coefficients'][arm]
        L += [f'**{arm}**', '', '| Input | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B)]
        for n in keep: L.append(f"| {short(n)} | " + ' | '.join(f"{c[b][n]['mean_per_sd']:+.3f} ({c[b][n]['share_positive']:.0%})" for b in B) + ' |')
        L.append('')
    cr = info['corr_2021_25']
    L += ['Correlations (2021-25 games, `correlations_2021_25.csv`): ' + '; '.join(
        f"{c} vs {short(r)} {cr[c][r]:+.2f}" for c in SPLIT for r in RUSH if (c.endswith('off')) == ('for' in r)) + '. '
          + 'Tackles for loss, 2015-25: ' + '; '.join(f"{c} vs {short(r)} {info['corr_tfl_2015_25'][c][r]:+.2f}" for c in TFL for r in RUSH
                                                      if (c.endswith('off')) == ('for' in r))
          + '; with yards before contact (2021-25): ' + '; '.join(f"{c} vs {r} {info['corr_tfl_ybc_2021_25'][r][c]:+.2f}" for c in TFL
                                                                   for r in ('d_ybc_off', 'd_ybc_def') if c[-3:] == r[-3:]) + '.', '',
          '## Limits', '',
          'Yards before contact can only be scored on 2021-25 (data from 2018; fits need two seasons of rows): two bases and less power '
          'than Tests 40-43. PFR charting is a human judgement of the contact point. Tackles for loss are scored on 2015-25, all exposed '
          'history. A "better" verdict would justify only a forward shadow test. Tables: `arms.csv`, `vs_market.csv`, `profiles.csv.gz`, '
          '`predictions.csv.gz`, `correlations_2021_25.csv`.', '',
          'Run: `python research/yards_before_contact.py --build DIR --pbp PBP_DIR` (raw files), then `python research/yards_before_contact.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--build', metavar='DIR', help='freeze team-game aggregates from raw advstats_week_rush files')
    ap.add_argument('--pbp', metavar='PBP_DIR', help='the Test 40 play_by_play_{season}.parquet files (with --build)')
    a = ap.parse_args()
    if a.build and not a.pbp: ap.error('--build needs --pbp')
    build(a.build, a.pbp) if a.build else run()
