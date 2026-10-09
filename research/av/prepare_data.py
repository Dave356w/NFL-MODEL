"""Reproducible inputs for the AV research, with provenance (research only; never touches data/).

    python research/av/prepare_data.py [CACHE_DIR]     # ~1 min cold, cached afterwards

Sources (nflverse via nflreadpy; versions and row counts are written to output/provenance.json):
  * load_player_stats(seasons)   weekly player box scores (gsis ids), REG season
  * load_snap_counts(seasons)    PFR snap counts per player-game (offense/defense/ST and pct), 2013+
  * load_players()               pfr_id -> gsis_id map, draft fields for players missing from draft_picks
  * load_draft_picks()           overall pick by gsis_id (and the PFR career AV columns, used ONLY to
                                 validate the reconstruction, never as a feature: they are career totals
                                 scraped after the fact, i.e. lookahead by construction)
  * nfl_model.load_schedule      scores, used for the team offensive/defensive point pools

Why not PFR Approximate Value itself: per-season AV exists only on pro-football-reference.com, which
refuses this environment (HTTP 403) and whose terms restrict automated collection; nflverse carries
only career AV. `player_value.py` therefore builds rAV, a per-game RECONSTRUCTION that follows PFR's
published allocation scheme from box-score inputs. It is labelled rAV everywhere and is not PFR AV.

Snap counts begin in 2013 (nflverse returns no 2012 rows), so player history starts there.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from _common import m  # noqa: E402

FIRST, LAST = 2013, 2025
UNITS = ('QB', 'OL', 'RB', 'WRTE', 'DL', 'LB', 'DB')
OFF_UNITS, DEF_UNITS = ('QB', 'OL', 'RB', 'WRTE'), ('DL', 'LB', 'DB')
STAT_COLS = ('passing_yards', 'attempts', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'receiving_yards',
             'receiving_tds', 'passing_tds', 'def_tackles_solo', 'def_tackle_assists', 'def_tackles_for_loss',
             'def_sacks', 'def_qb_hits', 'def_interceptions', 'def_pass_defended', 'def_fumbles_forced', 'def_tds',
             'def_safeties', 'special_teams_tds', 'fumble_recovery_tds')


def unit_of(pos):
    if pos == 'QB': return 'QB'
    return m.POS_GROUP.get(pos)


def _cache(cache_dir):
    d = Path(cache_dir) / 'av'; d.mkdir(parents=True, exist_ok=True); return d


def load_raw(cache_dir, first=FIRST, last=LAST):
    """Raw nflverse tables, cached as parquet under CACHE_DIR/av (completed seasons only)."""
    import nflreadpy as nfl
    c = _cache(cache_dir); out = {}
    years = list(range(first, last + 1))
    spec = {'stats': lambda: nfl.load_player_stats(years).to_pandas(),
            'snaps': lambda: pd.concat([nfl.load_snap_counts(y).to_pandas() for y in years], ignore_index=True),
            'players': lambda: nfl.load_players().to_pandas(),
            'draft': lambda: nfl.load_draft_picks().to_pandas()}
    for k, fn in spec.items():
        p = c / f'raw_{k}_{first}_{last}.parquet'
        if p.exists():
            out[k] = pd.read_parquet(p)
        else:
            df = m.fetch_upstream(fn, f'av {k}')
            df = df[[x for x in df.columns if x not in ('headshot_url', 'headshot', 'fg_made_list', 'fg_missed_list',
                                                        'fg_blocked_list', 'fg_made_distance', 'fg_missed_distance',
                                                        'fg_blocked_distance', 'gwfg_distance')]]
            df.to_parquet(p, index=False); out[k] = df
    out['sched'] = pd.concat([m.load_schedule(y) for y in years], ignore_index=True)
    return out


def player_games(raw):
    """One row per (game_id, team, gsis_id), REG season: unit, snap shares and box-score stats.

    Snap rows define participation; stat rows without a snap row (rare) keep their stats with zero
    snaps. Team names follow nfl_model.normalize_teams (OAK->LV etc.)."""
    pmap = raw['players'].dropna(subset=['pfr_id', 'gsis_id']).drop_duplicates('pfr_id').set_index('pfr_id').gsis_id
    sn = m.normalize_teams(raw['snaps'][raw['snaps'].game_type == 'REG'].copy())
    sn['gsis_id'] = sn.pfr_player_id.map(pmap)
    tot = (sn.offense_snaps + sn.defense_snaps).sum()
    mapped = (sn.offense_snaps + sn.defense_snaps)[sn.gsis_id.notna()].sum()
    audit = {'snap_rows': int(len(sn)), 'snap_share_mapped_to_gsis': float(mapped / tot)}
    sn = sn.dropna(subset=['gsis_id'])
    sn = (sn.groupby(['game_id', 'season', 'week', 'team', 'gsis_id'], as_index=False)
            .agg(position=('position', 'first'), off_snaps=('offense_snaps', 'sum'), def_snaps=('defense_snaps', 'sum'),
                 off_pct=('offense_pct', 'max'), def_pct=('defense_pct', 'max'), player=('player', 'first')))
    st = m.normalize_teams(raw['stats'][raw['stats'].season_type == 'REG'].copy()).rename(columns={'player_id': 'gsis_id'})
    st = st[st.gsis_id.notna()]
    cols = [c for c in STAT_COLS if c in st]
    st = st.groupby(['game_id', 'season', 'week', 'team', 'gsis_id'], as_index=False).agg(
        stat_position=('position', 'first'), stat_name=('player_display_name', 'first'), **{c: (c, 'sum') for c in cols})
    g = sn.merge(st, on=['game_id', 'season', 'week', 'team', 'gsis_id'], how='outer', indicator=True)
    yards = st.passing_yards.clip(lower=0).sum() + st.rushing_yards.clip(lower=0).sum() + st.receiving_yards.clip(lower=0).sum()
    unmatched = g[g._merge == 'right_only']
    uy = (unmatched.passing_yards.clip(lower=0).sum() + unmatched.rushing_yards.clip(lower=0).sum()
          + unmatched.receiving_yards.clip(lower=0).sum())
    audit['stat_yards_without_snap_row'] = float(uy / yards)
    g['position'] = g.position.fillna(g.stat_position)
    g['player'] = g.player.fillna(g.stat_name)
    g = g.drop(columns=['_merge', 'stat_position', 'stat_name'])
    for c in ('off_snaps', 'def_snaps', 'off_pct', 'def_pct', *cols): g[c] = g[c].fillna(0.).astype(float)
    g['unit'] = g.position.map(unit_of)
    audit['rows_without_unit'] = int(g.unit.isna().sum())  # K, P, LS
    g['share'] = np.where(g.unit.isin(OFF_UNITS), g.off_pct, np.where(g.unit.isin(DEF_UNITS), g.def_pct, 0.))
    g['season'] = g.season.astype(int); g['week'] = g.week.astype(int)
    return g.sort_values(['season', 'week', 'game_id', 'team', 'gsis_id']).reset_index(drop=True), audit


def team_games(pg, sched):
    """Per (game_id, team): points, offensive points (non-offensive TDs and safeties removed),
    the opponent's offensive points, and net pass / rush yards from the player rows."""
    s = sched[sched.result.notna()]
    rows = []
    for r in s.itertuples():
        for team, opp, pf, pa in ((r.home_team, r.away_team, r.home_score, r.away_score),
                                  (r.away_team, r.home_team, r.away_score, r.home_score)):
            rows.append({'game_id': r.game_id, 'season': int(r.season), 'week': int(r.week), 'team': team,
                         'opponent': opp, 'points': float(pf), 'points_allowed': float(pa)})
    t = pd.DataFrame(rows)
    agg = pg.groupby(['game_id', 'team']).agg(
        non_off_td=('def_tds', 'sum'), st_td=('special_teams_tds', 'sum'), fr_td=('fumble_recovery_tds', 'sum'),
        safeties=('def_safeties', 'sum'), pass_yds=('passing_yards', 'sum'), rush_yds=('rushing_yards', 'sum')).reset_index()
    t = t.merge(agg, on=['game_id', 'team'], how='left').fillna({'non_off_td': 0, 'st_td': 0, 'fr_td': 0, 'safeties': 0,
                                                                  'pass_yds': 0, 'rush_yds': 0})
    # def_tds already include defensive fumble-recovery TDs; fumble_recovery_tds can double count, so cap at def+st.
    t['off_points'] = (t.points - 7 * (t.non_off_td + t.st_td) - 2 * t.safeties).clip(lower=0)
    opp = t[['game_id', 'team', 'off_points']].rename(columns={'team': 'opponent', 'off_points': 'opp_off_points'})
    return t.merge(opp, on=['game_id', 'opponent'], how='left')


def draft_table(raw):
    """gsis_id -> (draft_year, overall pick); undrafted players are absent. draft_picks first,
    players' draft fields as fallback (overall pick only when draft_pick is overall)."""
    d = raw['draft'].dropna(subset=['gsis_id'])[['gsis_id', 'season', 'pick', 'position', 'w_av', 'to']]
    d = d.rename(columns={'season': 'draft_year'}).drop_duplicates('gsis_id')
    pl = raw['players'].dropna(subset=['gsis_id', 'draft_year', 'draft_pick'])
    extra = pl[~pl.gsis_id.isin(d.gsis_id)][['gsis_id', 'draft_year', 'draft_pick']].rename(columns={'draft_pick': 'pick'})
    out = pd.concat([d, extra], ignore_index=True)
    out['draft_year'] = out.draft_year.astype(int); out['pick'] = out.pick.astype(float)
    return out


def first_seasons(raw):
    """gsis_id -> rookie season (players.rookie_season; else the first season seen in snap/stat rows)."""
    pl = raw['players'].dropna(subset=['gsis_id'])
    return dict(zip(pl.gsis_id, pl.rookie_season))


def prepare(cache_dir, first=FIRST, last=LAST):
    c = _cache(cache_dir)
    p_pg, p_tg = c / f'player_games_{first}_{last}.parquet', c / f'team_games_{first}_{last}.parquet'
    raw = load_raw(cache_dir, first, last)
    if p_pg.exists() and p_tg.exists():
        pg, tg = pd.read_parquet(p_pg), pd.read_parquet(p_tg)
        audit = json.loads((c / 'prepare_audit.json').read_text())
    else:
        pg, audit = player_games(raw)
        tg = team_games(pg, raw['sched'])
        pg.to_parquet(p_pg, index=False); tg.to_parquet(p_tg, index=False)
        (c / 'prepare_audit.json').write_text(json.dumps(audit, indent=2))
    return {'pg': pg, 'tg': tg, 'draft': draft_table(raw), 'rookie_season': first_seasons(raw),
            'sched': raw['sched'], 'audit': audit}


def provenance(data, out_path):
    import importlib.metadata as md
    pg = data['pg']
    cov = pg.groupby('season').agg(player_games=('gsis_id', 'size'), players=('gsis_id', 'nunique'),
                                   games=('game_id', 'nunique'), no_unit=('unit', lambda s: int(s.isna().sum())))
    info = {'nflreadpy': md.version('nflreadpy'), 'pandas': pd.__version__,
            'seasons': [int(pg.season.min()), int(pg.season.max())], 'season_type': 'REG',
            'sources': ['nflverse player_stats (weekly)', 'nflverse snap_counts (PFR)', 'nflverse players',
                        'nflverse draft_picks', 'nflverse schedules'],
            'pfr_av': 'NOT USED AS A FEATURE: per-season PFR AV unavailable (pro-football-reference.com HTTP 403 from '
                      'this environment; nflverse has career totals only). Career w_av is used only to validate rAV.',
            'audit': data['audit'], 'coverage_by_season': {int(k): v for k, v in cov.to_dict('index').items()}}
    Path(out_path).write_text(json.dumps(info, indent=2, default=lambda o: int(o) if isinstance(o, np.integer) else str(o)))
    return info


if __name__ == '__main__':
    from _common import cache_dir_from_argv
    d = prepare(cache_dir_from_argv())
    print(json.dumps(provenance(d, HERE / 'output' / 'provenance.json')['audit'], indent=2))
