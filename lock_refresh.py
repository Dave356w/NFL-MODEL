"""Prepared weekly scoring inputs; fast refreshes never refit or rebuild research."""
import hashlib
import json
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

import ats_locks as locks
import availability_collect as ac
import espn_spreads as espn
import fixed_bands
import nfl_model as m

INPUTS = 'lock_inputs'
RUNTIME = 'lock_runtime'
MAX_QUOTE_MINUTES = 5


def runtime_dir(data, manifest):
    return Path(data)/RUNTIME/f"{manifest['season']}_week{manifest['week']:02d}"


def prepare(data, fit, board, availability, qb, inputs, targets, schedules, events, history):
    """Save exact full-precision inputs and hashes independently of compact page CSVs."""
    root = Path(data) / INPUTS
    root.mkdir(parents=True, exist_ok=True)
    season, week = fit['fit_season'], fit['fit_week']
    frames = dict(board=board.loc[(board.season == season) & (board.week == week)],
                  availability=availability, qb=qb, targets=targets, schedules=schedules,
                  events=events, **{k: inputs.get(k) for k in ('snaps', 'inj', 'rost', 'depth')})
    files = {}
    for name, frame in frames.items():
        if frame is None:
            continue
        path = root / f'{name}.parquet'
        frame.to_parquet(path, index=False)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    rule = fixed_bands.fit_weekly(history.assign(model_spread=m.implied_spread(history.model_wp)), season, week)
    if not fixed_bands.trained_before(rule, season, week):
        raise ValueError('Cannot prepare a map from the forecast week')
    payload = dict(revision=m.REVISION, config_signature=m.config_signature()[0],
                   season=season, week=week, fit=fit, rule=rule, files=files)
    payload['sha256'] = locks.digest(payload)
    temporary = root / 'manifest.tmp'
    temporary.write_text(json.dumps(payload, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(root / 'manifest.json')


def load(data):
    root = Path(data) / INPUTS
    manifest = json.loads((root / 'manifest.json').read_text())
    if locks.digest({k: v for k, v in manifest.items() if k != 'sha256'}) != manifest['sha256']:
        raise ValueError('Prepared scoring manifest hash mismatch')
    if (manifest['revision'] != m.REVISION or manifest['config_signature'] != m.config_signature()[0]
            or (manifest['fit']['training_max_season'], manifest['fit']['training_max_week_in_latest_season'])
            >= (manifest['season'], manifest['week'])
            or not fixed_bands.trained_before(manifest['rule'], manifest['season'], manifest['week'])):
        raise ValueError('Prepared scoring identity or training cutoff mismatch')
    frames = {}
    for name, digest in manifest['files'].items():
        path = root / f'{name}.parquet'
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Prepared {name} hash mismatch')
        frames[name] = pd.read_parquet(path)
    return manifest, frames


def current_quotes(evidence, now):
    """Same captured book supplies the moneyline offset and paired spread/price."""
    offers = []
    for event in evidence:
        age = (locks.utc(now) - locks.utc(event['captured_utc'])).total_seconds() / 60
        if event['completed'] or not 0 <= age <= MAX_QUOTE_MINUTES:
            continue
        for page in event['odds_pages']:
            for item in page.get('items', []):
                h, a = item.get('homeTeamOdds', {}), item.get('awayTeamOdds', {})
                hm = espn.american(h.get('current', {}).get('moneyLine', {}).get('american', h.get('moneyLine')))
                am = espn.american(a.get('current', {}).get('moneyLine', {}).get('american', a.get('moneyLine')))
                normalized = espn.quotes([{**event, 'odds_pages': [{'items': [item]}], 'movements': []}])
                q = next((r for r in normalized if r['kind'] == 'current'), None)
                if (hm is None or am is None or q is None or q['home_handicap'] is None
                        or q['away_handicap'] != -q['home_handicap']
                        or q['home_odds'] is None or q['away_odds'] is None):
                    continue
                offers.append(dict(event=event, quote=q, home_moneyline=hm, away_moneyline=am))
    # Newest quote per book, with a fixed provider priority rather than best-price shopping.
    chosen = {}
    for offer in sorted(offers, key=lambda r: (r['quote']['provider_id'] != '100',
                                              r['quote']['provider_id'],
                                              -locks.utc(r['event']['captured_utc']).timestamp())):
        chosen.setdefault(offer['event']['game_id'], offer)
    return chosen


def score(data, now=None, clock=None):
    """Refresh sources and score current games using the frozen weekly fit."""
    clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
    now = locks.utc(now or clock())
    manifest, frames = load(data)
    runtime = runtime_dir(data, manifest)
    runtime.mkdir(parents=True, exist_ok=True)
    board = frames['board'].copy()
    ko = pd.to_datetime([m.kickoff_utc(r) for r in board.to_dict('records')], utc=True)
    board = board.loc[(ko > now) & (ko <= now + dt.timedelta(hours=3))].copy()
    if board.empty:
        return manifest, board
    ids = set(board.game_id)
    schedule = frames['schedules'].loc[frames['schedules'].game_id.isin(ids)]
    targets = frames['targets'].loc[frames['targets'].game_id.isin(ids)]
    collection = ac.refresh(runtime, schedule, frames['rost'], now=now, force=True)
    espn.refresh(runtime, season=manifest['season'], game_ids=ids, sharded=True)
    generated = clock()
    offers = current_quotes(espn.read(runtime), generated)
    observations = m.load_availability_observations(Path(data) / m.AVAILABILITY_FILE)
    observations += m.load_availability_observations(runtime / ac.AUTO)
    resolved = m.resolve_game_availability(targets, frames['availability'], frames.get('qb'),
        frames['snaps'], frames['inj'], frames['rost'], depth=frames.get('depth'),
        events=frames.get('events'), observations=observations, asof=generated, collection=collection)
    if manifest.get('revision')=='boxscore-composite-v1.24':
        import qb_replacement
        resolved=qb_replacement.annotate_availability(resolved,frames.get('qb'),frames['rost'])
    board = m.apply_game_availability(board, resolved)
    for i, row in board.iterrows():
        offer = offers.get(row.game_id)
        if offer is None or locks.utc(offer['event']['kickoff_utc']) != m.kickoff_utc(row):
            board.loc[i, 'ready'] = False
            continue
        board.loc[i, 'home_moneyline'] = offer['home_moneyline']
        board.loc[i, 'away_moneyline'] = offer['away_moneyline']
        board.loc[i, 'spread_line'] = -offer['quote']['home_handicap']
        board.loc[i, 'score_quote'] = json.dumps(offer['quote'], sort_keys=True)
    board['q'] = m.market_ml_wp(board)
    board['model_wp'] = m.apply_fit(board, manifest['fit'])
    board['model_spread'] = m.implied_spread(board.model_wp)
    board['fixed_band_spread'] = fixed_bands.apply(board.model_spread, manifest['rule'])
    if manifest.get('revision')=='boxscore-composite-v1.24':
        # The base map was freshly recomputed above; discard old overlay state.
        import qb_replacement
        board=board.drop(columns=[c for c in ('qb_replacement_base_margin','qb_replacement_margin_adjustment',
            'qb_replacement_policy','qb_replacement_applied','qb_replacement_overlay_status') if c in board])
        board=qb_replacement.overlay(board)
    board['generated_utc'] = generated.isoformat()
    board['prepared_bundle_sha256'] = manifest['sha256']
    board['quote_ready'] = [game in offers for game in board.game_id]
    board['availability_ready'] = [bool(m.availability_snapshot(row, m.kickoff_utc(row), generated)) and all(
        ac.collection_ready(ac.team_snapshot(collection, row[side], row['game_id']), generated, require_inactives=True)
        for side in ('home', 'away')) for row in board.to_dict('records')]
    return manifest, board
