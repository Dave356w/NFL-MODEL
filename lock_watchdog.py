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
                  'espn_spreads.py','forecast_history.py','nfl_model.py','qb_replacement.py')


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


def coverage_issues(data='data', now=None):
    """A live process is insufficient: check saved decisions for each deadline.

    Stdlib only, usable in the cheap monitor without installing the model.
    Candidates become eligible at T-70; by T-65 absence is actionable. Retain
    missed-deadline alerts through kickoff+3h, even when the rolling board has scores.
    """
    import ats_locks as a
    from schedule_gate import kickoff
    data=Path(data);now=a.utc(now or dt.datetime.now(dt.timezone.utc))
    manifest=data/'latest/manifest.json';board=data/'latest/board.csv'
    if not manifest.exists() or not board.exists():return ['ATS schedule/manifest missing; lock coverage cannot be checked']
    revision=json.loads(manifest.read_text())['revision']
    stores=[data]+a.runtime_stores(data)
    locked={a.key(r) for store in stores for r in a.read(store/a.LOCKS)}
    candidates={a.key(r) for store in stores for r in a.durable_candidates(store,a.read(store/a.CANDIDATES))}
    out=[]
    for row in csv.DictReader(board.open()):
        ko=kickoff(row)
        if ko is None or now>ko+dt.timedelta(hours=3):continue
        cutoff=a.deadline(ko);key=(revision,row['game_id'])
        if key in locked:continue
        if now>=cutoff and key in candidates:
            if now>=cutoff+dt.timedelta(minutes=3):out.append(row['game_id']+': durable candidate not finalized after cutoff')
        elif now>=cutoff:
            out.append(row['game_id']+': MISSED CUTOFF; no eligible durable candidate')
        elif now>=cutoff-dt.timedelta(minutes=5) and key not in candidates:
            out.append(row['game_id']+': cutoff within five minutes; no eligible durable candidate')
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
