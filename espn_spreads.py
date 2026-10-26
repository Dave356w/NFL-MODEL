"""ESPN spread evidence, exact-handicap pricing and pre-lock quote capture.

The append-only evidence store is separate from immutable forecast archives.
Historical closes are estimates, never described as prices available at lock.
No quote at a different handicap and no assumed -110 enters priced returns.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request

import ats_locks as locks

STORE = 'espn_spreads.jsonl'
CORE = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl'
SITE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
ALIASES = {'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX'}
UTC = dt.timezone.utc


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def american(value):
    n = number(value)
    return n if n is not None and abs(n) >= 100 else None


def profit(odds):
    odds = american(odds)
    return (odds / 100 if odds > 0 else 100 / -odds) if odds is not None else math.nan


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'nfl-model-spread-audit/1'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def pages(url, get=fetch):
    """Read every page even when ESPN caps the requested page size."""
    first = get(url)
    out = [first]
    for page in range(2, int(first.get('pageCount', 1)) + 1):
        parsed = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parsed.query), page=str(page))
        out.append(get(urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))))
    return out


def event_row(event):
    if event.get('season', {}).get('type') != 2:
        return None  # The ledger covers the regular season, not preseason.
    competitors = {r['homeAway']: r for r in event['competitions'][0]['competitors']}
    teams = {side: ALIASES.get(r['team']['abbreviation'], r['team']['abbreviation'])
             for side, r in competitors.items()}
    season, week = int(event['season']['year']), int(event['week']['number'])
    complete = event['status']['type']['completed']
    scores = {side + '_score': number(r.get('score')) if complete else None
              for side, r in competitors.items()}
    return dict(game_id=f"{season}_{week:02d}_{teams['away']}_{teams['home']}",
                event_id=event['id'], season=season, week=week, **teams, **scores,
                completed=complete, kickoff_utc=locks.utc(event['date']).isoformat())


def collect(event, get=fetch):
    url = f"{CORE}/events/{event['event_id']}/competitions/{event['event_id']}/odds?limit=1000"
    odds_pages = pages(url, get)
    movements = []
    for item in [r for page in odds_pages for r in page.get('items', [])]:
        provider = str(item['provider']['id'])
        movement_url = url.split('/odds?')[0] + f'/odds/{provider}/history/0/movement?limit=1000'
        try:
            movements.append(dict(provider_id=provider, url=movement_url, pages=pages(movement_url, get)))
        except (OSError, ValueError) as exc:
            movements.append(dict(provider_id=provider, url=movement_url, error=str(exc), pages=[]))
    row = dict(event, captured_utc=dt.datetime.now(UTC).isoformat(),
               odds_url=url, odds_pages=odds_pages, movements=movements)
    row['evidence_sha256'] = locks.digest(row)
    return row


def read(data='data'):
    return locks.read(Path(data) / STORE)


def validate(data='data'):
    seen = set()
    for row in read(data):
        digest = row['evidence_sha256']
        if locks.digest({k: v for k, v in row.items() if k != 'evidence_sha256'}) != digest:
            raise ValueError('ESPN spread evidence hash mismatch')
        if digest in seen:
            raise ValueError('duplicate ESPN spread evidence')
        seen.add(digest)
        locks.utc(row['captured_utc'])
        locks.utc(row['kickoff_utc'])
        expected = f"{row['season']}_{row['week']:02d}_{row['away']}_{row['home']}"
        if row['game_id'] != expected:
            raise ValueError('ESPN game identity mismatch')
    return len(seen)


def refresh(data='data', season=2026, get=fetch, now=None):
    """Backfill completed games; refresh upcoming games inside two days.

    Completed successes are reused. Failed odds/movement requests are retried.
    Individual failures are recorded in the return value and retried next build.
    """
    now = locks.utc(now or dt.datetime.now(UTC))
    raw = []
    # Calendar-year queries are supported consistently; cross-year date ranges
    # can return HTTP 400. January belongs to the preceding NFL season.
    for year in range(season, min(season+1, now.year)+1):
        raw.extend(get(f'{SITE}/scoreboard?dates={year}&limit=1000').get('events', []))
    events = [event_row(e) for e in raw]
    events = [e for e in events if e and e['season'] == season]
    events = list({e['event_id']: e for e in events}.values())
    old = {r['game_id']: r for r in read(data)}
    wanted = []
    for event in events:
        prior = old.get(event['game_id'])
        same_final = (prior and event['completed'] and prior['completed']
                      and all(prior[k] == event[k] for k in ('home_score', 'away_score', 'kickoff_utc'))
                      and any(p.get('items') for p in prior['odds_pages'])
                      and not any(m.get('error') for m in prior['movements']))
        upcoming = now < locks.utc(event['kickoff_utc']) <= now + dt.timedelta(days=2)
        if not same_final and (event['completed'] or upcoming):
            wanted.append(event)
    errors, saved = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(collect, event, get): event for event in wanted}
        for job in concurrent.futures.as_completed(jobs):
            event = jobs[job]
            try:
                row = job.result()
                locks.append(Path(data) / STORE, [row])
                saved.append(row)
            except (OSError, ValueError, KeyError) as exc:
                errors.append(dict(game_id=event['game_id'], error=str(exc)))
    return dict(completed=sum(e['completed'] for e in events), added=len(saved), errors=errors)


def safe_refresh(data='data'):
    try:
        result = refresh(data)
        print(f'ESPN spread capture: {result}', flush=True)
        return result
    except (OSError, ValueError, KeyError) as exc:
        print(f'ESPN spread capture unavailable: {exc}', flush=True)
        return dict(errors=[str(exc)])


def quotes(evidence):
    """Normalize paired spread offers; moneyline fields are never read.

    Core API spread sign is the HOME HANDICAP, opposite the model's home
    margin convention. Prefer each side's explicit pointSpread. Open/close
    lack quote timestamps; only a fetched pregame current or timestamped
    movement can establish availability before lock.
    """
    out = []
    for e in evidence:
        providers = {}
        for page in e['odds_pages']:
            for item in page.get('items', []):
                provider = str(item['provider']['id'])
                providers[provider] = item['provider']
                for kind in ('open', 'close', 'current'):
                    if kind == 'close' and not e['completed']:
                        continue
                    q = dict(game_id=e['game_id'], provider_id=provider, book=item['provider'].get('name', provider),
                             kind=kind, captured_utc=e['captured_utc'], quote_utc=None,
                             evidence_sha256=e['evidence_sha256'], source_url=e['odds_url'])
                    for side in ('home', 'away'):
                        team = item.get(side + 'TeamOdds', {})
                        offer = team.get(kind, {})
                        q[side + '_handicap'] = number(offer.get('pointSpread', {}).get('american'))
                        q[side + '_odds'] = american(offer.get('spread', {}).get('american'))
                        if kind == 'current':
                            if q[side + '_handicap'] is None and number(item.get('spread')) is not None:
                                q[side + '_handicap'] = float(item['spread']) * (1 if side == 'home' else -1)
                            if q[side + '_odds'] is None:
                                q[side + '_odds'] = american(team.get('spreadOdds'))
                    out.append(q)
        for movement in e['movements']:
            provider = movement['provider_id']
            for page in movement['pages']:
                for item in page.get('items', []):
                    stamp = item.get('timestamp') or item.get('date')
                    try:
                        stamp = locks.utc(stamp).isoformat()
                    except (ValueError, TypeError):
                        continue
                    q = dict(game_id=e['game_id'], provider_id=provider,
                             book=providers.get(provider, {}).get('name', provider), kind='movement',
                             captured_utc=e['captured_utc'], quote_utc=stamp,
                             evidence_sha256=e['evidence_sha256'], source_url=movement['url'])
                    for side in ('home', 'away'):
                        offer = item.get(side + 'TeamOdds', {})
                        handicap = offer.get('pointSpread', {})
                        odds = offer.get('spread', {})
                        q[side + '_handicap'] = number(handicap.get('american') if isinstance(handicap, dict) else handicap)
                        q[side + '_odds'] = american(odds.get('american') if isinstance(odds, dict) else offer.get('spreadOdds'))
                    out.append(q)
    return out


def match(row, offers, allow_close=True):
    """Exact game + selected side + handicap, with explicit price provenance."""
    side = row.get('fixed_band_ats_side') or row.get('selected_side')
    line = number(row.get('spread_line', row.get('market_spread')))
    if side not in ('home', 'away') or line is None:
        return dict(ats_price_basis='no_selection')
    handicap = -line if side == 'home' else line
    cutoff = None
    for name in ('lock_at_utc', 'generated_utc'):
        try:
            cutoff = locks.utc(row.get(name))
            break
        except (ValueError, TypeError):
            pass
    ko = row.get('kickoff_utc')
    try:
        ko = locks.utc(ko)
    except (ValueError, TypeError):
        ko = None
    offers = [q for q in offers if q['game_id'] == row['game_id']]
    # Prefer the immutable candidate's price over later recovered evidence.
    embedded = row.get('espn_quote')
    if isinstance(embedded, dict):
        offers = [embedded] + offers
    eligible = []
    for q in offers:
        try:
            stamp = locks.utc(q['quote_utc'] if q['kind'] == 'movement' else q['captured_utc'])
        except (ValueError, TypeError, KeyError):
            continue
        if q['kind'] not in ('movement', 'current') or cutoff is None or stamp > cutoff or (ko and stamp >= ko):
            continue
        eligible.append((stamp, q))
    # Only the latest known offer for each book is eligible. Do not resurrect
    # an old matching line after a known move to a different handicap.
    newest = {}
    for stamp, q in eligible:
        if q['provider_id'] not in newest or stamp > newest[q['provider_id']][0]:
            newest[q['provider_id']] = (stamp, q)
    exact = lambda q: (number(q.get(side + '_handicap')) == handicap
                       and american(q.get(side + '_odds')) is not None)
    matched = sorted((v for v in newest.values() if exact(v[1])), key=lambda v: (v[0], v[1]['provider_id']))
    basis, chosen = 'unmatched_handicap', None
    if embedded is not None and any(q is embedded and exact(q) for _, q in eligible):
        chosen, basis = embedded, 'captured_prelock'
    elif matched:
        chosen = matched[-1][1]
        basis = 'historical_prelock' if chosen['kind'] == 'movement' else 'captured_prelock'
    elif allow_close:
        closing = [q for q in offers if q['kind'] == 'close' and exact(q)]
        if closing:
            provider = min((q['provider_id'] for q in closing), key=lambda p: (p != '100', p))
            chosen = max((q for q in closing if q['provider_id'] == provider), key=lambda q: q['captured_utc'])
            basis = 'closing_estimate'
    if chosen is None:
        return dict(ats_price_basis=basis if offers else 'missing_quote')
    stamp = chosen['quote_utc'] if chosen['kind'] == 'movement' else chosen['captured_utc'] if basis == 'captured_prelock' else None
    return dict(ats_price=chosen[side + '_odds'], ats_price_basis=basis,
                ats_book=chosen['book'], ats_quote_utc=stamp,
                ats_quote_age_minutes=(cutoff - locks.utc(stamp)).total_seconds()/60 if cutoff and stamp else None,
                ats_evidence_sha256=chosen['evidence_sha256'], ats_quote_url=chosen['source_url'],
                ats_home_odds=chosen.get('home_odds') if chosen.get('home_handicap') == -line else None,
                ats_away_odds=chosen.get('away_odds') if chosen.get('away_handicap') == line else None,
                espn_quote=chosen)


def candidate_quote(row, data):
    """Attach only evidence actually received before this candidate's cutoff."""
    offers = [q for q in quotes(read(data)) if locks.utc(q['captured_utc']) <= locks.utc(row['observed_utc'])]
    return match(row, offers, allow_close=False).get('espn_quote')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', default='data')
    ap.add_argument('--season', type=int, default=2026)
    args = ap.parse_args()
    result = refresh(args.data, args.season)
    print(json.dumps(result, indent=2))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
