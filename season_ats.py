"""Deduplicated 2026 ATS overview; saved decisions take precedence over replay.

This is a reporting view, never an append to either forecast archive. Earlier
unregistered ATS decisions can be reconstructed from pre-adoption moneyline
snapshots, but are explicitly replay, not native ATS evidence. A zero edge takes
the market favorite everywhere; saved zero-edge skips are backfilled as favorite
bets (owner decision 2026-10-19) under their own basis label.

Backend reporting also grades the timed locks against same-row controls. The
line-only map runs the market line through the same frozen median map, so the
production map's difference from it is what the model adds beyond the line.
"""
import numpy as np
import pandas as pd

import ats_locks
import fixed_bands
import nfl_model as m
import espn_spreads
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
            espn_quote=saved.get('espn_quote'),
            fixed_band_spread=saved['fixed_band_spread'], policy_version=saved.get('policy_version'),
            finalized_utc=saved.get('finalized_utc'),
            recovered_after_kickoff=saved.get('recovered_after_kickoff', False),
            ats_basis='Backfilled recorded skip' if ats_locks.backfilled(saved)
            else 'Recovered saved forecast' if saved.get('recovered_after_kickoff')
            else 'Recorded pregame' if saved.get('legacy_lock') else '60-minute lock')
    # ESPN supplies final scores only. It cannot create or change a decision.
    # Completed games without a model row remain visible as unavailable.
    for event in latest.get('espn_archive', []):
        if event['season'] != 2026 or not event['completed']:
            continue
        game = event['game_id']
        rows.setdefault(game, dict(game_id=game, season=2026, week=event['week'],
            home=event['home'], away=event['away'], spread_line=np.nan,
            fixed_band_spread=np.nan, ats_basis='Awaiting ATS lock'))
        rows[game].setdefault('kickoff_utc', event['kickoff_utc'])
        outcomes[game] = dict(home_score=event['home_score'], away_score=event['away_score'],
                              result=event['home_score'] - event['away_score'])
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
    frame = frame.sort_values(['week', 'game_id'], kind='stable').reset_index(drop=True)
    frame['_time'] = pd.to_datetime(frame.get('kickoff_utc', pd.Series(index=frame.index, dtype=str)), utc=True, errors='coerce')
    frame['_time'] = frame['_time'].fillna(pd.to_datetime(frame.get('gameday', pd.Series(index=frame.index, dtype=str)), utc=True, errors='coerce'))
    frame = frame.sort_values(['week', '_time', 'game_id'], kind='stable').drop(columns='_time').reset_index(drop=True)
    if 'espn_archive' in latest:
        frame = price(frame, latest['espn_archive'], assume_unmatched=True)
    return frame


def price(frame, evidence, assume_unmatched=False):
    """Keep W/L/P and saved handicaps; replace proxy returns with matched prices."""
    frame = frame.copy()
    offers = espn_spreads.quotes(evidence)
    priced = []
    for row in frame.to_dict('records'):
        info = espn_spreads.match(row, offers)
        info.pop('espn_quote', None)
        info['ats_match_status'] = info['ats_price_basis']
        if (assume_unmatched and 'ats_price' not in info
                and row.get('fixed_band_ats_side') in ('home', 'away')
                and espn_spreads.number(row.get('spread_line')) is not None):
            info.update(ats_price=-110., ats_price_basis='assumed_minus110')
        priced.append(info)
    prices = pd.DataFrame(priced, index=frame.index)
    for name in ('ats_price', 'ats_home_odds', 'ats_away_odds'):
        if name not in prices:
            prices[name] = np.nan
    frame = frame.drop(columns=[c for c in prices if c in frame]).join(prices)
    frame['proxy_ats_units'] = frame.fixed_band_ats_units
    grade = frame.fixed_band_ats_result
    payout = frame.ats_price.map(espn_spreads.profit)
    frame['fixed_band_ats_units'] = np.where(grade.eq('W'), payout,
        np.where(grade.eq('L'), -1., np.where(grade.isin(['P', 'S']), 0., np.nan)))
    frame.loc[grade.isin(['W', 'L', 'P']) & frame.ats_price.isna(), 'fixed_band_ats_units'] = np.nan
    frame['ats_priced_stake'] = (grade.isin(['W', 'L', 'P']) & frame.ats_price.notna()).astype(int)
    frame['ats_cumulative_units'] = frame.fixed_band_ats_units.fillna(0).cumsum()
    return frame


def summary(frame):
    r = frame.get('fixed_band_ats_result', pd.Series(dtype=str))
    w, l, p, s = [int(r.eq(k).sum()) for k in 'WLPS']
    bets = w + l + p
    if 'ats_price_basis' in frame:
        numeric_units = pd.to_numeric(frame.fixed_band_ats_units, errors='coerce')
        eligible = r.isin(list('WLP')) & numeric_units.notna()
        returns = numeric_units.loc[eligible].to_numpy(float)
        priced_bets = len(returns)
        units = float(returns.sum()) if priced_bets else np.nan
        prelock = int((eligible & frame.ats_price_basis.isin(['captured_prelock', 'historical_prelock'])).sum())
        estimates = int((eligible & frame.ats_price_basis.eq('closing_estimate')).sum())
        assumed = int((eligible & frame.ats_price_basis.eq('assumed_minus110')).sum())
    else:
        # Legacy research callers without a quote archive retain their explicit
        # -110 reference. Public builds always load an archive, even if empty.
        units = w / 1.1 - l
        returns = np.array([1 / 1.1] * w + [-1.] * l + [0.] * p)
        priced_bets, prelock, estimates = bets, 0, 0
        assumed = 0
    status = frame.get('ats_status', pd.Series(dtype=str))
    return dict(wins=w, losses=l, pushes=p, skips=s, bets=bets, selected=bets,
                opportunities=bets+s, units=units, roi=units/priced_bets if priced_bets else np.nan,
                priced_bets=priced_bets, prelock_prices=prelock, closing_estimates=estimates,
                assumed_prices=assumed, quoted_bets=prelock+estimates,
                unpriced=bets-priced_bets,
                roi_se=float(returns.std(ddof=1)/np.sqrt(priced_bets)) if priced_bets > 1 else np.nan,
                cover_rate=w/(w+l) if w+l else np.nan,
                pending=int(status.eq('pending').sum()), unavailable=int(status.eq('unavailable').sum()))


def report(frame):
    r = summary(frame)
    lines = ['2026 pooled ATS overview: one row per game; saved ATS decisions override replay.',
             'Priority: timed/earlier ATS archive, pre-adoption pregame snapshot replay, historical replay.',
             'Snapshot replay is not a registered ATS forecast; post-adoption missing locks are not reconstructed.',
             f"Record {r['wins']}-{r['losses']}-{r['pushes']}, {r['skips']} skips, {r['pending']} pending, "
             f"{r['unavailable']} unavailable; {r['units']:+.2f}u, ROI {100*r['roi']:+.2f}%.",
             (f"ESPN exact-handicap pricing: {r['prelock_prices']} pre-lock, {r['closing_estimates']} closing estimates, "
              f"{r['assumed_prices']} assumed -110, {r['unpriced']} unpriced; "
              f"ROI denominator {r['priced_bets']} 1u stakes (pushes included). "
              "Missing or mismatched ESPN prices use labelled -110 assumptions in the pooled estimate. "
              "Closing estimates and assumed prices are not verified lock-time returns."
              if 'ats_price_basis' in frame else 'Legacy reference: proxy -110 pricing.')]
    if len(frame):
        for basis, g in frame.groupby('ats_basis', sort=True):
            v = summary(g)
            lines.append(f"  {basis}: {v['wins']}-{v['losses']}-{v['pushes']}, {v['skips']} skips, "
                         f"{v['pending']} pending, {v['unavailable']} unavailable; {v['units']:+.2f}u")
    lines.append('This mixed-basis season total is descriptive, not a pooled native-forward claim.')
    return '\n'.join(lines)


TIMED_BASES = ('60-minute lock', 'Recovered saved forecast')
BASELINES = ('Median map (production)', 'Raw model spread', 'Line-only map',
             'Always favorite', 'Always home')


def baseline_sides(mapped, line, raw, line_mapped):
    """Same-row sides (+1 home, -1 away, 0 skip): the production map and its controls.

    line_mapped is the market line passed through the same median map. Every
    rule takes the favorite on a zero edge; a pick'em line skips for both maps.
    """
    line = np.asarray(line, float)
    return {'Median map (production)': fixed_bands.pick(mapped, line),
            'Raw model spread': fixed_bands.pick(raw, line),
            'Line-only map': fixed_bands.pick(line_mapped, line),
            'Always favorite': np.where(np.isfinite(line), np.sign(line), np.nan),
            'Always home': np.where(np.isfinite(line), 1., np.nan)}


def flat_returns(side, margin):
    """Per-row 1u returns at assumed -110: NaN ungraded, 0 for skips and pushes."""
    side, margin = np.asarray(side, float), np.asarray(margin, float)
    edge = side * margin
    out = np.where(edge > fixed_bands.EPS, 1 / 1.1, np.where(edge < -fixed_bands.EPS, -1., 0.))
    return np.where(np.isfinite(side) & np.isfinite(margin), out, np.nan)


def flat_record(side, margin):
    side, margin = np.asarray(side, float), np.asarray(margin, float)
    ret = flat_returns(side, margin)
    graded = np.isfinite(ret)
    bet = graded & (side != 0)
    r = ret[bet]
    w, l = int((r > 0).sum()), int((r < 0).sum())
    n = len(r)
    units = float(r.sum())
    return dict(wins=w, losses=l, pushes=n - w - l, skips=int((graded & (side == 0)).sum()),
                bets=n, units=units, roi=units / n if n else np.nan,
                roi_se=float(r.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
                cover_rate=w / (w + l) if w + l else np.nan)


def _pct(x):
    return 'n/a' if not np.isfinite(x) else f'{100 * x:+.1f}%'


def _baseline_lines(sides, margin):
    lines = []
    for name in BASELINES:
        v = flat_record(sides[name], margin)
        se = f" +/- {100 * v['roi_se']:.1f}" if np.isfinite(v['roi_se']) else ''
        cover = 'n/a' if not np.isfinite(v['cover_rate']) else f"{100 * v['cover_rate']:.1f}%"
        lines.append(f"  {name:24s} {v['wins']}-{v['losses']}-{v['pushes']}, {v['skips']} skips, "
                     f"{v['units']:+.2f}u, ROI {_pct(v['roi'])}{se}, cover {cover}")
    production = flat_returns(sides[BASELINES[0]], margin)
    for control in ('Line-only map', 'Raw model spread'):
        other = flat_returns(sides[control], margin)
        ok = np.isfinite(production) & np.isfinite(other)
        diff = production[ok] - other[ok]
        differ = int((sides[BASELINES[0]][ok] != sides[control][ok]).sum())
        se = f" +/- {diff.std(ddof=1) / np.sqrt(len(diff)):.3f}" if len(diff) > 1 else ''
        mean = f'{diff.mean():+.3f}' if len(diff) else 'n/a'
        lines.append(f"  Paired, median map minus {control.lower()}: sides differ on {differ} of {len(diff)}; "
                     f"{diff.sum():+.2f}u (per game {mean}{se}, 1 SE)")
    return lines


def lock_baselines(latest, frame):
    """Timed locks graded beside same-row controls; backend reporting only."""
    revision = (latest or {}).get('manifest', {}).get('revision', m.REVISION)
    locks = (latest or {}).get('ats_locks', {})
    rules = {r['season']: r for r in (latest or {}).get('fixed_band_rules', []) if 'season' in r}
    lines = ['ATS same-row baselines (backend reporting; every arm 1u at assumed -110, pushes in the ROI denominator; '
             'break-even cover 52.4%).',
             'Line-only map: the market line through the same frozen median map, without model input. '
             'Median map minus line-only is what the model adds beyond the line\'s own band.',
             'Per-arm records are descriptive; the map-versus-raw review is at 100 decided locks.']
    for basis in TIMED_BASES:
        g = frame.loc[frame.ats_basis.eq(basis)] if len(frame) and 'ats_basis' in frame else frame.iloc[0:0]
        rows = []
        for r in g.to_dict('records'):
            saved = locks.get((revision, r['game_id']), {})
            rule = saved.get('fixed_rule') or rules.get(int(r['season']))
            rows.append(dict(mapped=r['fixed_band_spread'], line=r['spread_line'], result=r['result'],
                             raw=pd.to_numeric(saved.get('raw_spread'), errors='coerce'),
                             line_mapped=float(fixed_bands.apply([r['spread_line']], rule)[0])))
        d = pd.DataFrame(rows, columns=['mapped', 'line', 'result', 'raw', 'line_mapped'])
        decided = d.loc[np.isfinite(d.result.astype(float))]
        lines.append(f'{basis}, {revision}: {len(decided)} graded, {len(d) - len(decided)} pending'
                     + (' (reported separately from pregame-finalized locks)' if basis != TIMED_BASES[0] else ''))
        if len(decided):
            sides = baseline_sides(decided.mapped, decided.line, decided.raw, decided.line_mapped)
            lines += _baseline_lines(sides, (decided.result - decided.line).to_numpy(float))
    history = (latest or {}).get('fixed_band_ledger', pd.DataFrame())
    if len(history) and 'model_spread' in history:
        h = history.loc[history.fixed_band_spread.notna() & history.spread_line.notna()
                        & history.result.notna() & history.season.isin(list(rules))]
        if len(h):
            line_mapped = np.full(len(h), np.nan)
            for year, rule in rules.items():
                mask = (h.season == year).to_numpy()
                line_mapped[mask] = fixed_bands.apply(h.spread_line.to_numpy(float)[mask], rule)
            lines.append(f'Development history (replay, not forward evidence; backtest seasons share the recipe '
                         f'selection, the current season is walk-forward): '
                         f'{int(h.season.min())}-{int(h.season.max())}, {len(h)} graded')
            sides = baseline_sides(h.fixed_band_spread, h.spread_line, h.model_spread, line_mapped)
            lines += _baseline_lines(sides, (h.result - h.spread_line).to_numpy(float))
    return '\n'.join(lines)
