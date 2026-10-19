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
from schedule_gate import kickoff as scheduled_kickoff


def historical_before_adoption(row):
    """Permit replay only when its T-60 deadline is known to predate adoption.

    Older replay exports have a game date without a kickoff time. Keep such a
    game only if every possible kickoff on that Eastern date has an earlier
    deadline; an ambiguous adoption-day or missing date cannot authorize replay.
    """
    try:
        ko = ats_locks.utc(row.get('kickoff_utc'))
    except (ValueError, TypeError):
        ko = None
    if ko is not None:
        return ats_locks.deadline(ko) < ats_locks.ADOPTED_UTC
    ko = scheduled_kickoff(row)
    if ko is not None:
        return ats_locks.deadline(ko) < ats_locks.ADOPTED_UTC
    value = row.get('gameday')
    if not isinstance(value, str):
        return False
    day = pd.to_datetime(value, format='%Y-%m-%d', errors='coerce')
    if pd.isna(day):
        return False
    next_midnight = (pd.Timestamp(day.date()) + pd.Timedelta(days=1)).tz_localize('America/New_York')
    # Actual kickoffs on this date precede next midnight, so equality of this
    # upper bound still proves their deadlines are strictly before adoption.
    return ats_locks.deadline(next_midnight.to_pydatetime()) <= ats_locks.ADOPTED_UTC


def build(latest, ledger):
    if latest is None:
        return pd.DataFrame()
    if ats_locks.continuous_manifest(latest.get('manifest', {})):
        return continuous_build(latest, ledger)
    revision = latest.get('manifest', {}).get('revision', m.REVISION)
    history = latest.get('fixed_band_ledger', pd.DataFrame())
    rows = {}
    if len(history):
        for r in history.loc[history.season.eq(2026)].to_dict('records'):
            if r['game_id'] in rows:
                raise ValueError('duplicate historical ATS game')
            row = dict(r, ats_basis='Historical replay')
            if not historical_before_adoption(r):
                row.update(spread_line=np.nan, fixed_band_spread=np.nan,
                           ats_basis='Awaiting ATS lock')
            rows[r['game_id']] = row
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


def continuous_build(latest, ledger):
    """Owner-authorized v1.19 replay, separate from genuine new-policy locks.

    Only rebuilt new-revision retro forecasts supply reconstructed selections.
    Other revisions and the live board can supply outcomes, never replacement
    predictors or handicaps. Pending games continue to require an actual T-60
    decision. No archive is written by this reporting view.
    """
    revision = latest['manifest']['revision']
    history = latest.get('retro_ledger', pd.DataFrame())
    if len(history) and 'revision' in history:
        if not history.revision.eq(revision).all():
            raise ValueError('v1.19 retrospective history must be rebuilt for its own revision')
    rows = {}
    if len(history):
        for r in history.loc[history.season.eq(2026)].to_dict('records'):
            if r['game_id'] in rows:
                raise ValueError('duplicate historical ATS game')
            # The rebuilt retro file is the authorized forecast source. Do not
            # use old locks, first moneyline snapshots, or refreshed board inputs.
            wp = pd.to_numeric(r.get('model_wp'), errors='coerce')
            value = float(m.implied_spread([wp])[0]) if np.isfinite(wp) and 0 < wp < 1 else pd.to_numeric(r.get('model_spread'), errors='coerce')
            rows[r['game_id']] = dict(r, revision=revision, model_spread=value,
                raw_spread=value, ats_spread=value, fixed_band_spread=value,
                selection_method='continuous_spread', policy_version=ats_locks.POLICY_VERSION,
                ats_basis='Retrospective v1.19')
    outcomes = {}
    for frame in (history, ledger, latest.get('board', pd.DataFrame())):
        if not len(frame) or 'result' not in frame:
            continue
        for r in frame.to_dict('records'):
            if np.isfinite(pd.to_numeric(r.get('result'), errors='coerce')):
                outcomes[r['game_id']] = {name:r.get(name) for name in ('result','home_score','away_score')}
    native = pd.DataFrame()
    if len(ledger) and {'revision','season'} <= set(ledger):
        native = ledger.loc[ledger.revision.eq(revision) & ledger.season.eq(2026)].copy()
        native = native.sort_values('generated_utc', kind='stable').drop_duplicates('game_id', keep='first')
    for r in native.to_dict('records'):
        if r['game_id'] not in rows:
            rows[r['game_id']] = {name:r.get(name) for name in ('game_id','season','week','home','away',
                'kickoff_utc','generated_utc','result','home_score','away_score')}
            rows[r['game_id']].update(revision=revision, spread_line=np.nan, model_spread=np.nan,
                raw_spread=np.nan, ats_spread=np.nan, fixed_band_spread=np.nan,
                selection_method='continuous_spread', ats_basis='Awaiting ATS lock')
    for game, row in rows.items():
        row.update(outcomes.get(game, {}))
        if not np.isfinite(pd.to_numeric(row.get('result'), errors='coerce')):
            row.update(spread_line=np.nan, ats_spread=np.nan, fixed_band_spread=np.nan,
                       ats_basis='Awaiting ATS lock')
    # A real same-revision timed lock takes precedence, even over authorized
    # replay. Legacy revision archives never enter the new model's selections.
    for (rev, game), saved in latest.get('ats_locks', {}).items():
        if rev != revision or int(saved['season']) != 2026:
            continue
        if saved.get('policy_version') != ats_locks.POLICY_VERSION or saved.get('selection_method') != 'continuous_spread' or saved.get('legacy_lock'):
            raise ValueError('v1.19 saved selection requires its genuine continuous ATS policy')
        value = saved['raw_spread']
        rows[game] = dict(game_id=game, revision=revision, season=2026, week=int(saved['week']),
            home=saved['home'], away=saved['away'], kickoff_utc=saved['kickoff_utc'],
            generated_utc=saved['generated_utc'], lock_at_utc=saved['lock_at_utc'],
            model_wp=saved['model_wp'], model_spread=value, raw_spread=value,
            ats_spread=value, spread_line=saved['market_spread'], fixed_band_spread=value,
            selection_method='continuous_spread', policy_version=saved['policy_version'],
            ats_basis='60-minute lock')
        rows[game].update(outcomes.get(game, {}))
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows.values())
    for name in ('result','spread_line','fixed_band_spread'):
        if name not in frame:
            frame[name] = np.nan
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    grades, units = fixed_bands.grade(frame, frame.fixed_band_spread)
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
    for suffix in ('result','units','side','team','handicap'):
        frame['ats_'+suffix] = frame['fixed_band_ats_'+suffix]
    return frame.sort_values(['week','game_id'], kind='stable').reset_index(drop=True)


def summary(frame):
    r = frame.get('fixed_band_ats_result', pd.Series(dtype=str))
    w, l, p, s = [int(r.eq(k).sum()) for k in 'WLPS']
    bets = w + l + p
    units = w / 1.1 - l
    returns = np.array([1 / 1.1] * w + [-1.] * l + [0.] * p)
    status = frame.get('ats_status', pd.Series(dtype=str))
    return dict(wins=w, losses=l, pushes=p, skips=s, bets=bets, selected=bets,
                opportunities=bets+s, units=units, roi=units/bets if bets else np.nan,
                roi_se=float(returns.std(ddof=1)/np.sqrt(bets)) if bets > 1 else np.nan,
                cover_rate=w/(w+l) if w+l else np.nan,
                pending=int(status.eq('pending').sum()), unavailable=int(status.eq('unavailable').sum()))


def report(frame):
    r = summary(frame)
    lines = ['2026 pooled ATS overview: one row per game; saved ATS decisions override replay.',
             'Priority: timed/earlier ATS archive, pre-adoption pregame snapshot replay, historical replay.',
             'Snapshot replay is not a registered ATS forecast; post-adoption missing locks are not reconstructed.',
             f"Record {r['wins']}-{r['losses']}-{r['pushes']}, {r['skips']} skips, {r['pending']} pending, "
             f"{r['unavailable']} unavailable; {r['units']:+.2f}u, ROI {100*r['roi']:+.2f}% at proxy -110."]
    if 'selection_method' in frame and frame.selection_method.eq('continuous_spread').any():
        lines[1:3] = [
            'v1.19 uses its continuous market-context model spread without a median map.',
            'Owner-authorized retrospective v1.19 regrading includes completed pre/post-adoption games; '
            'these rows are not native forward evidence.',
            'Only genuine same-v1.19 T-60 locks override the rebuilt retrospective selection; '
            'pending games without a lock remain unselected. Earlier archives retain their bytes.']
    if len(frame):
        for basis, g in frame.groupby('ats_basis', sort=True):
            v = summary(g)
            lines.append(f"  {basis}: {v['wins']}-{v['losses']}-{v['pushes']}, {v['skips']} skips, "
                         f"{v['pending']} pending, {v['unavailable']} unavailable; {v['units']:+.2f}u")
    lines.append('This mixed-basis season total is descriptive, not a pooled native-forward claim.')
    return '\n'.join(lines)
