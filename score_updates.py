"""Refresh reporting-only final scores without rerunning the prediction model.

The scoreboard request is independent of bookmaker odds and play-by-play
availability. Only explicitly final, identity-checked regular-season results
enter this derived store. An unavailable or malformed response never clears a
previous final; a later valid final can correct a provider's earlier score.
No forecast, handicap, price, candidate or lock is written here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import urllib.request


STORE = 'final_scores.json'
SITE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
UTC = dt.timezone.utc
ALIASES = {'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())


def utc(value):
    parsed = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('score timestamp must include a timezone')
    return parsed.astimezone(UTC)


def integer(value, name):
    if isinstance(value, bool):
        raise ValueError(f'invalid {name}')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'invalid {name}') from exc
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f'invalid {name}')
    return int(number)


def validate(row):
    required = {'season', 'week', 'game_id', 'home', 'away', 'completed',
                'home_score', 'away_score', 'kickoff_utc', 'captured_utc', 'event_id'}
    if not isinstance(row, dict) or not required.issubset(row):
        raise ValueError('missing required final score fields')
    for name in ('season', 'week', 'home_score', 'away_score'):
        if type(row[name]) is not int:
            raise ValueError(f'invalid saved {name}: expected JSON integer')
    season, week = integer(row['season'], 'season'), integer(row['week'], 'week')
    if season < 2000 or not 1 <= week <= 18:
        raise ValueError('invalid regular-season identity')
    if (not isinstance(row['home'], str) or not isinstance(row['away'], str)
            or row['home'] not in TEAMS or row['away'] not in TEAMS or row['home'] == row['away']):
        raise ValueError('invalid score teams')
    if row['game_id'] != f"{season}_{week:02d}_{row['away']}_{row['home']}":
        raise ValueError('score game identity mismatch')
    if row.get('completed') is not True:
        raise ValueError('score is not final')
    if not isinstance(row['event_id'], str) or not row['event_id'].isdigit():
        raise ValueError('invalid final score event identity')
    for name in ('home_score', 'away_score'):
        integer(row[name], name)
    if utc(row['kickoff_utc']) > utc(row['captured_utc']):
        raise ValueError('final score precedes kickoff')
    return row


def event_row(event, season, now):
    """Ignore live/cancelled games; reject malformed finals instead of grading them."""
    if event.get('season', {}).get('type') != 2 or event.get('season', {}).get('year') != season:
        return None
    status = event.get('status', {}).get('type', {})
    if status.get('completed') is not True or status.get('state') != 'post':
        return None
    # Cancelled/forfeited events must not become ordinary played finals.
    if status.get('name') not in {'STATUS_FINAL', 'STATUS_FINAL_OVERTIME'}:
        return None
    competitions = event['competitions']
    if len(competitions) != 1:
        raise ValueError('ambiguous score competition')
    competitors = competitions[0]['competitors']
    if len(competitors) != 2 or {r['homeAway'] for r in competitors} != {'home', 'away'}:
        raise ValueError('ambiguous score opponents')
    teams = {r['homeAway']: ALIASES.get(r['team']['abbreviation'], r['team']['abbreviation'])
             for r in competitors}
    week = integer(event['week']['number'], 'week')
    row = dict(game_id=f"{season}_{week:02d}_{teams['away']}_{teams['home']}",
        season=season, week=week, **teams, event_id=str(event['id']),
        completed=True, kickoff_utc=utc(event['date']).isoformat(),
        captured_utc=now.isoformat(),
        source_url=f"{SITE}/summary?event={event['id']}")
    row.update({r['homeAway'] + '_score': integer(r.get('score'), 'score') for r in competitors})
    return validate(row)


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'nfl-model-final-scores/1'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def read(data='data'):
    path = Path(data) / STORE
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list):
        raise ValueError('invalid final score store')
    seen = set()
    for row in rows:
        validate(row)
        if row['game_id'] in seen:
            raise ValueError('duplicate final score identity')
        seen.add(row['game_id'])
    return rows


def refresh(data='data', season=2026, now=None, get=fetch):
    now = utc(now or dt.datetime.now(UTC))
    previous = {row['game_id']: row for row in read(data)}
    current, conflicted, errors, successes = {}, set(), [], 0
    # ESPN does not consistently support a date range crossing January 1.
    for year in range(season, min(season + 1, now.year) + 1):
        url = f'{SITE}/scoreboard?dates={year}&limit=1000'
        try:
            payload = get(url)
            if not isinstance(payload.get('events'), list):
                raise ValueError('scoreboard events missing')
            successes += 1
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append(f'{year}: {type(exc).__name__}: {exc}')
            continue
        for event in payload['events']:
            try:
                row = event_row(event, season, now)
                if row is None:
                    continue
                if row['game_id'] in conflicted:
                    continue
                prior = current.get(row['game_id'])
                if prior and any(prior[k] != row[k] for k in ('home_score', 'away_score', 'kickoff_utc')):
                    conflicted.add(row['game_id'])
                    del current[row['game_id']]
                    raise ValueError('conflicting scoreboard finals')
                current[row['game_id']] = row
            except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
                errors.append(f"event {event.get('id', '?') if isinstance(event, dict) else '?'}: {type(exc).__name__}: {exc}")
    if not successes:
        raise RuntimeError('No scoreboard response available; retained saved scores: ' + '; '.join(errors))
    saved = 0
    for game, row in current.items():
        prior = previous.get(game)
        # No timestamp-only commits on every poll.
        if prior and all(prior[k] == row[k] for k in ('home_score', 'away_score', 'kickoff_utc', 'event_id')):
            continue
        previous[game] = row
        saved += 1
    if saved:
        path = Path(data) / STORE
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps([previous[k] for k in sorted(previous)], indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    return dict(saved=saved, finals=len(previous), errors=errors)


def overlay(frame, scores):
    """Copy outcome fields only; the prediction, selected side and prices stay frozen."""
    import pandas as pd

    out = frame.copy()
    if out.empty or 'game_id' not in out:
        return out
    rows = {row['game_id']: validate(row) for row in scores}
    for i, original in out.iterrows():
        row = rows.get(original['game_id'])
        if row is None:
            continue
        for side in ('home', 'away'):
            value = original.get(side, original.get(side + '_team'))
            if pd.notna(value) and ALIASES.get(value, value) != row[side]:
                raise ValueError('score overlay teams do not match saved game')
        for name in ('home_score', 'away_score'):
            out.loc[i, name] = row[name]
        result = row['home_score'] - row['away_score']
        out.loc[i, 'result'] = result
        if 'home won' in out:
            out.loc[i, 'home won'] = 1. if result > 0 else 0. if result < 0 else .5
        if 'status' in out:
            out.loc[i, 'status'] = 'tie' if result == 0 else 'graded'
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--season', type=int, default=2026)
    args = parser.parse_args(argv)
    report = refresh(args.data_dir, args.season)
    print(f"Final scores: {report['saved']} changed, {report['finals']} saved")
    for error in report['errors']:
        print(f'::warning::{error}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
