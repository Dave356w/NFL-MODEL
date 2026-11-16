"""Restart an absent watcher and surface stale heartbeats without deleting evidence."""
import base64
import argparse
import csv
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

CONTROLLER_FILES=('lock_watcher.py','lock_refresh.py','ats_locks.py','availability_collect.py',
                  'espn_spreads.py','forecast_history.py','nfl_model.py','qb_replacement.py',
                  'fixed_bands.py','schedule_gate.py','lock_watchdog.py')


def restart_outdated(runs, sleep=time.sleep):
    """Code updates require a new Python process, not just a new prepared bundle.

    Stop and wait for the old serialized runner BEFORE requesting a successor.
    Its confirmed candidates/receipts remain in Git; unsent work is never an
    acknowledged official candidate. Ordinary data commits do not restart it.
    """
    restarted=False
    for run in runs:
        if run['status']!='in_progress':continue
        changed=subprocess.check_output(['git','diff','--name-only',run['headSha'],'HEAD','--',*CONTROLLER_FILES],text=True).splitlines()
        if not changed:continue
        ident=str(run['databaseId'])
        print('Restarting watcher '+ident+' for controller changes: '+', '.join(changed),flush=True)
        subprocess.run(['gh','run','cancel',ident],check=True)
        for attempt in range(24):
            state=json.loads(subprocess.check_output(['gh','run','view',ident,'--json','status']))
            if state['status']=='completed':break
            sleep(5)
        else:raise RuntimeError('Old watcher has not stopped; refusing overlapping writers')
        restarted=True
    if restarted:
        fresh=json.loads(subprocess.check_output(['gh','run','list','-w','lock-watcher.yml',
            '--limit','30','--json','databaseId,status']))
        if not any(r['status'] in ('in_progress','queued','pending','waiting') for r in fresh):
            subprocess.run(['gh','workflow','run','lock-watcher.yml','--ref','main'],check=True)
    return restarted


AT_RISK_MINUTES=30        # from T-90, warn when the latest saved observation is blocked
MISSED_RETENTION_HOURS=24  # keep a missed game visible for a full day, not just through the game


def observation_blockers(board):
    """Short source/parser reasons from a saved timing observation's evidence."""
    out=[]
    for side in ('home','away'):
        raw=board.get(side+'_availability_evidence')
        try:ev=json.loads(raw) if isinstance(raw,str) else (raw or {})
        except ValueError:continue
        team=ev.get('team') or board.get(side,'')
        collection=ev.get('collection') or {}
        for kind in ('report','inactives'):
            item=collection.get(kind) or {}
            if item.get('error'):out.append(f"{team} {kind}: {item['error']}")
            elif item and item.get('complete') is not True:
                # Lock policy v7 can lock on final reports alone; inactive gaps are warnings.
                out.append(f'{team} {kind}: incomplete' + (' (report-only fallback allowed)' if kind=='inactives' else ''))
        # Evidence blockers can exist with complete collection (e.g. an unresolved
        # starting QB or conflicting observations); always report them.
        out+=[f'{team}: {b}' for b in ev.get('blockers') or []]
    if str(board.get('quote_ready')) not in ('True','true','1'):out.append('no fresh paired quote')
    return sorted(set(out))


def latest_blockers(stores, identity, now):
    import ats_locks as a
    import forecast_history
    rows=[r for store in stores for r in forecast_history.timing_rows(store)
          if (r.get('revision'),r.get('game_id'))==identity and a.utc(r['observed_utc'])<=now]
    if not rows:return ['no saved forecast observation']
    return observation_blockers(max(rows,key=lambda r:a.utc(r['observed_utc']))['board'])


def coverage_issues(data='data', now=None):
    """A live process is insufficient: check saved decisions for each deadline.

    Stdlib only, usable in the cheap monitor without installing the model.
    Candidates become eligible at T-70; by T-65 absence is actionable. From T-90
    a game whose latest saved observation is blocked is flagged AT RISK. Alerts
    name the latest saved source/parser blockers. A game counts as covered by a saved
    lock from any revision (lock continuity, owner decision 2026-11-15). Missed
    deadlines stay visible for MISSED_RETENTION_HOURS after kickoff.
    """
    import ats_locks as a
    from schedule_gate import kickoff
    data=Path(data);now=a.utc(now or dt.datetime.now(dt.timezone.utc))
    manifest=data/'latest/manifest.json';board=data/'latest/board.csv'
    if not manifest.exists() or not board.exists():return ['ATS schedule/manifest missing; lock coverage cannot be checked']
    revision=json.loads(manifest.read_text())['revision']
    stores=[data]+a.runtime_stores(data)
    records={a.key(r):r for store in stores for r in a.read(store/a.LOCKS)}
    locked=set(a.current_records(records,revision))
    candidates={a.key(r) for store in stores for r in a.durable_candidates(store,a.read(store/a.CANDIDATES))}
    out=[]
    for row in csv.DictReader(board.open()):
        ko=kickoff(row)
        if ko is None or now>ko+dt.timedelta(hours=MISSED_RETENTION_HOURS):continue
        cutoff=a.deadline(ko);key=(revision,row['game_id'])
        if key in locked:continue
        if now>=cutoff and key in candidates:
            if now>=cutoff+dt.timedelta(minutes=3):out.append(row['game_id']+': durable candidate not finalized after cutoff')
        elif now>=cutoff:
            out.append(row['game_id']+': MISSED CUTOFF; no eligible durable candidate; '
                       +'; '.join(latest_blockers(stores,key,cutoff)))
        elif now>=cutoff-dt.timedelta(minutes=5) and key not in candidates:
            out.append(row['game_id']+': cutoff within five minutes; no eligible durable candidate; '
                       +'; '.join(latest_blockers(stores,key,now)))
        elif now>=cutoff-dt.timedelta(minutes=AT_RISK_MINUTES) and key not in candidates:
            blockers=[b for b in latest_blockers(stores,key,now) if b!='no saved forecast observation']
            if blockers:
                out.append(row['game_id']+f': AT RISK {int((cutoff-now).total_seconds()//60)} min before cutoff; '
                           +'; '.join(blockers))
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restart-outdated',action='store_true')
    args=parser.parse_args()
    runs = json.loads(subprocess.check_output(['gh', 'run', 'list', '-w', 'lock-watcher.yml',
        '--limit', '30', '--json', 'databaseId,status,headSha']))
    if args.restart_outdated and restart_outdated(runs):
        return 0
    running = [r for r in runs if r['status']=='in_progress']
    alerts=coverage_issues()
    for alert in alerts:print('::error::'+alert)
    summary=__import__('os').environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a') as out:
            out.write('ATS lock coverage\n\n'+('\n'.join('- '+a for a in alerts) if alerts else 'All due games have saved coverage.')+'\n')
    if not running and not any(r['status'] in ('queued', 'pending', 'waiting') for r in runs):
        subprocess.run(['gh', 'workflow', 'run', 'lock-watcher.yml', '--ref', 'main'], check=True)
        print('Watcher restart requested')
        return 1 if alerts else 0
    if running:
        try:
            encoded = subprocess.check_output(['gh', 'api',
                'repos/{owner}/{repo}/contents/data/lock_runtime/watcher_status.json', '--jq', '.content'])
            state = json.loads(base64.b64decode(encoded))
            age = (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(state['updated_utc'])).total_seconds()/60
            if age > 10:
                print(f'::error::ATS watcher heartbeat is {age:.1f} minutes old; active run '
                      f'{running[0]["databaseId"]}. Evidence is retained; investigate runner/provider health.')
                return 1
        except subprocess.CalledProcessError:
            print('::warning::Watcher has not committed its first heartbeat yet')
    return 1 if alerts else 0


if __name__ == '__main__':
    raise SystemExit(main())
