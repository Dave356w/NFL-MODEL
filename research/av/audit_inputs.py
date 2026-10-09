"""Data-quality audit of the AV research inputs, run before reading any model result.

    python research/av/audit_inputs.py [CACHE_DIR]     # after walkforward.py has built its caches

Writes output/provenance.json and output/data_audit.md: source coverage, the rAV reconstruction against
PFR career AV (validation only), the fitted priors and replacement levels by season, the participation
layer's rule counts, and the game-week reserve timing check (research Test 29's method, re-run here).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from _common import cache_dir_from_argv, load_inputs  # noqa: E402
import player_value as pv  # noqa: E402
from game_week_reserve import timing_check  # noqa: E402
from prepare_data import UNITS, prepare, provenance  # noqa: E402

OUT = HERE / 'output'


def per_game_validation(seasons, draft, pg):
    """Career rAV per game played vs PFR career w_av per game (draft_picks.games): removes the
    career-length component that dominates the career-total correlation."""
    d = draft[(draft.draft_year >= 2013) & (draft.draft_year <= 2021) & draft.w_av.notna()]
    gp = pg[pg.share > 0].groupby('gsis_id').game_id.nunique()
    tot = seasons.groupby('gsis_id').rav.apply(lambda x: pv.weighted_career(x.tolist()))
    unit = seasons.sort_values('games').drop_duplicates('gsis_id', keep='last').set_index('gsis_id').unit
    d = d.assign(rav_w=d.gsis_id.map(tot), gp=d.gsis_id.map(gp), unit=d.gsis_id.map(unit)).dropna(subset=['rav_w', 'gp'])
    d = d[d.gp >= 16]
    rows = []
    for u, g in [('all', d)] + [(u, d[d.unit == u]) for u in UNITS]:
        a, b = g.rav_w / g.gp, g.w_av / g.gp
        rows.append({'unit': u, 'players': len(g), 'pearson_per_game': float(np.corrcoef(a, b)[0, 1]),
                     'spearman_per_game': float(a.rank().corr(b.rank()))})
    return pd.DataFrame(rows)


def main():
    cache = cache_dir_from_argv()
    d = prepare(cache)
    info = provenance(d, OUT / 'provenance.json')
    pgv = pd.read_parquet(Path(cache) / 'av' / 'pgv.parquet')
    seasons = pv.season_table(pgv)
    L = ['# AV research: input audit', '', '## Sources and coverage', '',
         f"nflreadpy {info['nflreadpy']}; REG season {info['seasons'][0]}–{info['seasons'][1]} (snap counts start 2013).",
         f"Snap share mapped to GSIS ids: {100 * info['audit']['snap_share_mapped_to_gsis']:.2f}%; box-score yards with no "
         f"snap row: {100 * info['audit']['stat_yards_without_snap_row']:.3f}%; rows with no unit (K/P/LS, not modelled): "
         f"{info['audit']['rows_without_unit']}.", '',
         '| Season | Player-games | Players | Games |', '|---|---:|---:|---:|']
    for y, c in info['coverage_by_season'].items():
        L.append(f"| {y} | {c['player_games']} | {c['players']} | {c['games']} |")
    v = pv.validate_against_pfr(seasons, d['draft'])
    pgv_ = per_game_validation(seasons, d['draft'], pgv)
    L += ['', '## rAV against PFR career AV (validation only; never a feature)', '',
          'Weighted career rAV (100% best season, 95% next, ...) against nflverse `draft_picks.w_av` for players drafted '
          '2013–2021. Per game: both divided by career games (rAV: games with a snap; PFR: `games`), players with ≥ 16.', '',
          '| Unit | Players | Pearson | Spearman | Mean rAV_w | Mean PFR w_av | Per-game players | Per-game Pearson | Per-game Spearman |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    j = v.merge(pgv_, on='unit', how='left', suffixes=('', '_pg'))
    for r in j.itertuples():
        L.append(f'| {r.unit} | {r.players} | {r.pearson:.3f} | {r.spearman:.3f} | {r.mean_rav_w:.1f} | {r.mean_pfr_w_av:.1f} | '
                 f'{r.players_pg} | {r.pearson_per_game:.3f} | {r.spearman_per_game:.3f} |')
    est = pv.Estimator(pgv, seasons, d['draft'], d['rookie_season'])
    L += ['', '## Replacement levels and rookie draft priors (fitted on earlier seasons only)', '',
          'Replacement = 25th percentile of player-season rAV per full game (≥ 4 full-game equivalents), the three seasons '
          'before. Rookie prior = a ln(pick) + b per unit, rookie seasons of earlier cohorts (WLS by full games).', '',
          '| Season | ' + ' | '.join(f'{u} rep' for u in UNITS) + ' | ' + ' | '.join(f'{u} a / b (n)' for u in ('QB', 'OL', 'WRTE', 'DL', 'DB')) + ' |',
          '|---|' + '---:|' * (len(UNITS) + 5)]
    for y in range(2019, 2026):
        rep, pr = est.replacement(y), est.priors(y)
        L.append(f'| {y} | ' + ' | '.join(f'{rep[u]:.3f}' for u in UNITS) + ' | ' +
                 ' | '.join(f"{pr[u]['a']:+.3f} / {pr[u]['b']:.3f} ({pr[u]['n_drafted']})" for u in ('QB', 'OL', 'WRTE', 'DL', 'DB')) + ' |')
    a = pd.read_parquet(Path(cache) / 'av' / 'av_player_audit.parquet')
    f = pd.read_parquet(Path(cache) / 'av' / 'av_features.parquet')
    a = a[a.season >= 2019]
    L += ['', '## Participation layer (2019–2025 team-weeks)', '',
          f"Team-weeks: {len(f)}; v1.15 projected QB matched to an id: {100 * f.qb_matched.mean():.1f}% (else the QB unit "
          f"uses the generic fill); membership skipped as a data gap: {int(f.membership_gap.sum())}.",
          f"Player rows: {len(a)}; Out {int((a.status == 'Out').sum())}, Doubtful {int((a.status == 'Doubtful').sum())}, "
          f"Questionable {int((a.status == 'Questionable').sum())}; roster-out {int(a.roster_out.sum())}; departed "
          f"{int(a.departed.sum())}.",
          f"Mean projected-share total per unit equals its slots by construction; mean |projected − full-health| share moved per "
          f"team-week: {a.assign(dd=(a.proj_share - a.full_share).abs()).groupby(['season', 'week', 'team']).dd.sum().mean():.2f} "
          'full-game equivalents.',
          f"Teams with ≥ 3 starters out (share ≥ .5, Out/Doubtful/roster-out): {100 * (f.starters_out >= 3).mean():.1f}% of team-weeks; "
          f"median roster continuity {f.continuity.median():.3f}."]
    inp = load_inputs(cache)
    tc = timing_check(inp['a']['rost'], inp['a']['snaps'])
    L += ['', '## Same-week reserve list: publication timing', '',
          f"Players newly on a game-week out list (weeks 2+, 2019–25): {len(tc)}; took an offensive or defensive snap in that "
          f"game: {int(tc.played.sum())} ({100 * tc.played.mean():.2f}%). Weekly roster rows carry no publish time; this bounds "
          'how often a historical row reflects a post-kickoff move, not moves between the final injury report and kickoff.']
    (OUT / 'data_audit.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
