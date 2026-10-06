"""Test 4: game-state (garbage-time) filtering of the box-score profiles.

    python research/game_state.py [CACHE_DIR]     # ~25 min (downloads play-by-play)

Rebuilds every team box score from play-by-play keeping only plays whose offense
win probability before the snap (nflverse `wp`) is inside a band; plays without a
wp value are kept. Availability and the QB term are unchanged (production, window
4), so only the team profiles differ. Variants: G1 [0.05, 0.95], G2 [0.10, 0.90].
Each runs the production grid with the production selection rule and is compared
with production on the same held-out games.
"""
import nflreadpy as nfl
import pandas as pd

from _common import (FULL, DHEAD, HEAD, availability, cache_dir_from_argv, diff_row, grid, load_inputs, log,
                     m, outer, row, score)

COLS = ['game_id', 'play_id', 'season_type', 'posteam', 'play_type', 'yards_gained', 'pass_attempt', 'rush_attempt',
        'sack', 'interception', 'fumble_lost', 'third_down_converted', 'third_down_failed', 'first_down_rush',
        'first_down_pass', 'first_down_penalty', 'penalty', 'penalty_team', 'penalty_yards', 'two_point_attempt',
        'drive', 'drive_time_of_possession', 'play_deleted', 'fumbled_1_team', 'fumbled_2_team',
        'fumble_recovery_1_team', 'fumble_recovery_2_team', 'wp']
BANDS = {'G1 wp in [0.05, 0.95]': (.05, .95), 'G2 wp in [0.10, 0.90]': (.10, .90)}


def filtered_boxes(pbp, sched, lo, hi):
    boxes, kept, total = [], 0, 0
    for y, p in pbp.items():
        snap = p.play_type.isin(['pass', 'run'])
        keep = p.wp.isna() | p.wp.between(lo, hi)
        kept += int((keep & snap).sum()); total += int(snap.sum())
        boxes.append(m.aggregate_boxscores(p[keep], sched[sched.season == y], y))
    return m.validate_boxes(pd.concat(boxes, ignore_index=True)), 1 - kept / total


def main():
    inp = load_inputs(cache_dir_from_argv())
    pbp = {}
    for y in sorted(inp['sched'].season.unique()):
        raw = m.fetch_upstream(lambda: nfl.load_pbp(int(y)), f'play-by-play {y}')
        pbp[int(y)] = m.normalize_teams(raw.select([c for c in COLS if c in raw.columns]).to_pandas())
        log(f'play-by-play {y}: {len(pbp[int(y)])} plays')
    avail = availability(inp)
    res = {'production (all plays)': score(outer(grid(inp, avail, FULL, 'production'), FULL)[0])}
    dropped = {}
    for name, (lo, hi) in BANDS.items():
        box, share = filtered_boxes(pbp, inp['sched'], lo, hi)
        dropped[name] = share
        res[name] = score(outer(grid(dict(inp, box=box), avail, FULL, name), FULL)[0])
    print('\n## Test 4\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    print('\n' + DHEAD)
    base = res['production (all plays)']
    for k in BANDS: print(diff_row(f'{k} vs production', res[k], base))
    print('\nShare of offensive snaps dropped: ' + ', '.join(f'{k}: {100 * v:.1f}%' for k, v in dropped.items()))
    log('done')


if __name__ == '__main__':
    main()
