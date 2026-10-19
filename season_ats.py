"""Deduplicated 2026 ATS overview; saved decisions take precedence over replay.

This is a reporting view, never an append to either forecast archive. Earlier
unregistered ATS decisions can be reconstructed from pre-adoption moneyline
snapshots, but are explicitly replay, not native ATS evidence. A zero edge takes
the market favorite everywhere; saved zero-edge skips are backfilled as favorite
bets (owner decision 2026-10-19) under their own basis label.
"""
import numpy as np
import pandas as pd

import ats_locks
import fixed_bands
import nfl_model as m


def build(latest, ledger):
    if latest is None:
        return pd.DataFrame()
    revision = latest.get('manifest', {}).get('revision', m.REVISION)
    history = latest.get('fixed_band_ledger', pd.DataFrame())
    rows = {}
    if len(history):
        for r in history.loc[history.season.eq(2026)].to_dict('records'):
            if r['game_id'] in rows:
                raise ValueError('duplicate historical ATS game')
            rows[r['game_id']] = dict(r, ats_basis='Historical replay')
    # Actual scores may come from a newer board than the graded ledger. Only
    # outcomes are taken from the board, never postgame probabilities or lines.
    outcomes = {}
    for frame in (history, ledger, latest.get('board', pd.DataFrame())):
        if not len(frame) or 'result' not in frame:
            continue
        for r in frame.to_dict('records'):
            if np.isfinite(pd.to_numeric(r.get('result'), errors='coerce')):
                outcomes[r['game_id']] = {k: r.get(k) for k in ('result', 'home_score', 'away_score')}
    native = pd.DataFrame()
    if len(ledger):
        native = ledger.loc[ledger.revision.eq(revision) & ledger.season.eq(2026)].copy()
        native = native.sort_values('generated_utc', kind='stable').drop_duplicates('game_id', keep='first')
    rules = {r['season']: r for r in latest.get('fixed_band_rules', []) if 'season' in r}
    # Every native game blocks historical fallback, including pending games.
    for r in native.to_dict('records'):
        row = {k: r.get(k) for k in ('game_id', 'season', 'week', 'home', 'away',
               'kickoff_utc', 'generated_utc', 'model_wp', 'result', 'home_score', 'away_score')}
        row.update(spread_line=np.nan, fixed_band_spread=np.nan, ats_basis='Awaiting ATS lock')
        rule = rules.get(2026)
        ko = pd.to_datetime(r.get('kickoff_utc'), utc=True, errors='coerce')
        generated = pd.to_datetime(r.get('generated_utc'), utc=True, errors='coerce')
        early = (pd.notna(ko) and pd.notna(generated) and generated < ko
                 and ats_locks.deadline(ko.to_pydatetime()) < ats_locks.ADOPTED_UTC)
        if early and rule is not None and rule['training_max_season'] < 2026:
            wp, line = pd.to_numeric(r.get('model_wp'), errors='coerce'), pd.to_numeric(r.get('spread_line'), errors='coerce')
            if np.isfinite(wp) and np.isfinite(line):
                row.update(spread_line=float(line), fixed_band_spread=float(
                    fixed_bands.apply(m.implied_spread([wp]), rule)[0]),
                    ats_basis='Replayed pregame forecast')
        rows[r['game_id']] = row
    # Immutable ATS archives replace BOTH history and any snapshot replay.
    for (rev, game), saved in latest.get('ats_locks', {}).items():
        if rev != revision or int(saved['season']) != 2026:
            continue
        rows[game] = dict(game_id=game, season=2026, week=int(saved['week']),
            home=saved['home'], away=saved['away'], kickoff_utc=saved['kickoff_utc'],
            generated_utc=saved['generated_utc'], lock_at_utc=saved['lock_at_utc'],
            model_wp=saved['model_wp'], spread_line=saved['market_spread'],
            fixed_band_spread=saved['fixed_band_spread'], policy_version=saved.get('policy_version'),
            ats_basis='Backfilled recorded skip' if ats_locks.backfilled(saved)
            else 'Recorded pregame' if saved.get('legacy_lock') else '60-minute lock')
    if not rows:
        return pd.DataFrame()
    for game, row in rows.items():
        row.update(outcomes.get(game, {}))
    frame = pd.DataFrame(rows.values())
    for name in ('result', 'spread_line', 'fixed_band_spread'):
        if name not in frame:
            frame[name] = np.nan
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    grades, units = fixed_bands.grade(frame, frame.fixed_band_spread)
    # A pending zero-edge selection is not a completed skip yet.
    complete = np.isfinite(frame.result)
    frame['fixed_band_ats_result'] = np.where(complete, grades, '')
    frame['fixed_band_ats_units'] = np.where(complete, units, np.nan)
    frame['ats_status'] = np.where(~complete, 'pending',
        np.where(np.isin(frame.fixed_band_ats_result, list('WLPS')), 'graded', 'unavailable'))
    side = fixed_bands.pick(frame.fixed_band_spread, frame.spread_line)
    frame['fixed_band_ats_side'] = np.where(side > 0, 'home', np.where(side < 0, 'away', ''))
    side = frame.fixed_band_ats_side
    frame['fixed_band_ats_team'] = np.where(side.eq('home'), frame.home, np.where(side.eq('away'), frame.away, ''))
    frame['fixed_band_ats_handicap'] = np.where(side.eq('home'), -frame.spread_line,
                                               np.where(side.eq('away'), frame.spread_line, np.nan))
    return frame.sort_values(['week', 'game_id'], kind='stable').reset_index(drop=True)


def summary(frame):
    r = frame.get('fixed_band_ats_result', pd.Series(dtype=str))
    w, l, p, s = [int(r.eq(k).sum()) for k in 'WLPS']
    bets = w + l + p
    units = w / 1.1 - l
    status = frame.get('ats_status', pd.Series(dtype=str))
    return dict(wins=w, losses=l, pushes=p, skips=s, bets=bets, selected=bets,
                opportunities=bets+s, units=units, roi=units/bets if bets else np.nan,
                cover_rate=w/(w+l) if w+l else np.nan,
                pending=int(status.eq('pending').sum()), unavailable=int(status.eq('unavailable').sum()))


def report(frame):
    r = summary(frame)
    lines = ['2026 pooled ATS overview: one row per game; saved ATS decisions override replay.',
             'Priority: timed/earlier ATS archive, pre-adoption pregame snapshot replay, historical replay.',
             'Snapshot replay is not a registered ATS forecast; post-adoption missing locks are not reconstructed.',
             f"Record {r['wins']}-{r['losses']}-{r['pushes']}, {r['skips']} skips, {r['pending']} pending, "
             f"{r['unavailable']} unavailable; {r['units']:+.2f}u, ROI {100*r['roi']:+.2f}% at proxy -110."]
    if len(frame):
        for basis, g in frame.groupby('ats_basis', sort=True):
            v = summary(g)
            lines.append(f"  {basis}: {v['wins']}-{v['losses']}-{v['pushes']}, {v['skips']} skips, "
                         f"{v['pending']} pending, {v['unavailable']} unavailable; {v['units']:+.2f}u")
    lines.append('This mixed-basis season total is descriptive, not a pooled native-forward claim.')
    return '\n'.join(lines)
