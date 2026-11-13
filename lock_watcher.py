"""Independent T-60 controller. Repository commits are its durable event store.

Full builds and source collectors never write this controller's directory.
Only this workflow's serialized runner may write it. Recovery replays saved
candidates and receipts; page publication is a separate retryable workflow.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import ats_locks as locks
import forecast_history
import lock_refresh

UTC = dt.timezone.utc
LEADS = (120, 90, 60, 45, 30)
FORECASTS = 'timing_forecasts'
CHECKPOINTS = 'timing_checkpoints.jsonl'


def git(*args):
    return subprocess.check_output(['git', *args])


def refresh_prepared(data):
    """Adopt a complete prepared bundle from main without resetting local evidence."""
    git('fetch', '--quiet', 'origin', 'main')
    ref = git('rev-parse', 'origin/main').decode().strip()
    path = f'{data}/{lock_refresh.INPUTS}/manifest.json'
    raw = git('show', f'{ref}:{path}')
    manifest = json.loads(raw)
    root = Path(data) / lock_refresh.INPUTS
    if (root/'manifest.json').exists() and (root/'manifest.json').read_bytes() == raw:
        return
    root.mkdir(parents=True, exist_ok=True)
    for name in manifest['files']:
        (root/f'{name}.parquet').write_bytes(git('show', f'{ref}:{data}/{lock_refresh.INPUTS}/{name}.parquet'))
    (root/'manifest.json').write_bytes(raw)
    lock_refresh.load(data)  # hash/identity/training audit before any scoring


def persist(data, message):
    runtime = Path(data) / lock_refresh.RUNTIME
    subprocess.run([sys.executable, 'validate_data_files.py'], check=True)
    subprocess.run([sys.executable, 'commit_data.py', '--branch', 'main', '--no-fallback',
                    '--path', str(runtime), '--message', message], check=True)
    return git('rev-parse', 'HEAD').decode().strip()


def acknowledge(data, commit, runtime=None):
    """The server commit timestamp's upper second is a conservative durability bound."""
    runtime = runtime or Path(data) / lock_refresh.RUNTIME
    saved = {r['candidate_sha256'] for r in locks.read(runtime/locks.RECEIPTS)}
    stamp = locks.utc(git('show', '-s', '--format=%cI', commit).decode().strip()) + dt.timedelta(seconds=1)
    # Read the committed blob, never candidates appended after this acknowledgement.
    try:
        blob = git('show', f'{commit}:{runtime}/{locks.CANDIDATES}').decode()
    except subprocess.CalledProcessError:
        return
    rows = [json.loads(s) for s in blob.splitlines() if s.strip()]
    locks.append(runtime/locks.RECEIPTS, [dict(candidate_sha256=r['candidate_sha256'],
        commit=commit, committed_utc=stamp.isoformat(), timestamp_basis='server commit upper-second bound')
        for r in rows if r['candidate_sha256'] not in saved
        and locks.utc(r['observed_utc']) <= stamp])


def recover_receipts(data, runtime=None):
    """Recover a crash between the candidate commit and receipt commit.

    Only commits reachable from origin/main are proof. A local unsent forecast
    or a newly committed post-cutoff candidate cannot acquire an earlier time.
    """
    runtime = runtime or Path(data)/lock_refresh.RUNTIME
    known = {r['candidate_sha256'] for r in locks.read(runtime/locks.RECEIPTS)}
    pending = {r['candidate_sha256'] for r in locks.read(runtime/locks.CANDIDATES)}-known
    if not pending:
        return
    commits = git('log', '--reverse', '--format=%H', 'origin/main', '--',
                  str(runtime/locks.CANDIDATES)).decode().split()
    for commit in commits:
        acknowledge(data, commit, runtime)
        known = {r['candidate_sha256'] for r in locks.read(runtime/locks.RECEIPTS)}
        if pending <= known:
            return


def dispatch(workflow):
    started = dt.datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    subprocess.run(['gh', 'workflow', 'run', workflow, '--ref', 'main'], check=True)
    for _ in range(6):
        runs = json.loads(subprocess.check_output(['gh', 'run', 'list', '-w', workflow,
            '--limit', '20', '--json', 'databaseId,createdAt,status,event']))
        successor = next((r for r in runs if r['event']=='workflow_dispatch' and r['createdAt'] >= started
                          and str(r['databaseId']) != os.environ.get('GITHUB_RUN_ID')
                          and r['status'] in ('queued', 'pending', 'in_progress')), None)
        if successor:
            return successor['databaseId']
        time.sleep(5)
    raise RuntimeError('No acknowledged successor; watcher cannot silently hand off')


def publish(pending):
    state = json.loads(pending.read_text())
    if state.get('run_id'):
        result = json.loads(subprocess.check_output(['gh', 'run', 'view', str(state['run_id']),
            '--json', 'status,conclusion']))
        if result['status'] != 'completed':
            return
        if result['conclusion'] == 'success':
            pending.write_text(json.dumps(dict(pending=False))+'\n')
            return
    pending.write_text(json.dumps(dict(pending=True, run_id=dispatch('publish.yml')))+'\n')


def checkpoints(runtime, now):
    """Use the last actually observed pre-deadline forecast; record missing coverage too."""
    rows = forecast_history.timing_rows(runtime)
    existing = {(r['revision'], r['game_id'], r['lead_minutes']) for r in locks.read(runtime/CHECKPOINTS)}
    grouped = {}
    for r in rows:
        grouped.setdefault((r['revision'], r['game_id']), []).append(r)
    added = []
    for (revision, game), group in grouped.items():
        ko = locks.utc(group[-1]['kickoff_utc'])
        for lead in LEADS:
            identity = (revision, game, lead)
            deadline = ko-dt.timedelta(minutes=lead)
            if identity in existing or now < deadline:
                continue
            eligible = [r for r in group if locks.utc(r['observed_utc']) <= deadline]
            chosen = max(eligible, key=lambda r: r['observed_utc']) if eligible else None
            age = (deadline-locks.utc(chosen['observed_utc'])).total_seconds()/60 if chosen else None
            added.append(dict(revision=revision, game_id=game, lead_minutes=lead,
                deadline_utc=deadline.isoformat(), recorded_utc=now.isoformat(),
                forecast_sha256=chosen['snapshot_sha256'] if chosen else None,
                age_minutes=age, fresh=age is not None and age <= 5,
                basis='diagnostic only; never authorizes a production lock'))
    locks.append(runtime/CHECKPOINTS, added)


def tick(data, now=None):
    now = locks.utc(now or dt.datetime.now(UTC))
    runtime = Path(data) / lock_refresh.RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    previous = runtime/'watcher_status.json'
    if previous.exists():
        age = (now-locks.utc(json.loads(previous.read_text())['updated_utc'])).total_seconds()/60
        if age > 10:
            print(f'::error::ATS watcher heartbeat gap: {age:.1f} minutes', flush=True)
    # Finalize and durably save first: scoring, providers and publication may fail.
    stores = locks.runtime_stores(data)
    old_checkpoints = sum(len(locks.read(p/CHECKPOINTS)) for p in stores)
    changed = False
    for store in stores:
        recover_receipts(data, store)
        before = len(locks.read(store/locks.LOCKS))
        locks.record(store, now, policy_version=locks.policy_for_revision(
            json.loads((store/'latest/manifest.json').read_text()).get('revision')) if (store/'latest/manifest.json').exists() else locks.WATCHER_POLICY)
        changed |= len(locks.read(store/locks.LOCKS)) > before
        checkpoints(store, now)
    if changed:
        (runtime/'publish_pending.json').write_text(json.dumps(dict(pending=True))+'\n')
        persist(data, f'ATS durable finalization {now.isoformat()}')
    # A deployment retry is needed after every missed checkpoint too (no-pick state).
    if sum(len(locks.read(p/CHECKPOINTS)) for p in stores) > old_checkpoints:
        (runtime/'publish_pending.json').write_text(json.dumps(dict(pending=True))+'\n')
    health = dict(heartbeat_utc=now.isoformat(), run_id=os.environ.get('GITHUB_RUN_ID'), errors=[])
    try:
        refresh_prepared(data)
        manifest, board = lock_refresh.score(data, now)
        health['prepared_bundle_sha256'] = manifest['sha256']
        health['games'] = []
        if len(board):
            store = lock_refresh.runtime_dir(data, manifest)
            store.mkdir(parents=True, exist_ok=True)
            generated = board.generated_utc.iloc[0]
            latest = store/'latest'
            latest.mkdir(exist_ok=True)
            board.to_csv(latest/'board.csv', index=False)
            (latest/'manifest.json').write_text(json.dumps(dict(revision=manifest['revision'],
                recipe=manifest['fit']['recipe'], config_signature=manifest['config_signature'],
                generated_utc=generated, prepared_bundle_sha256=manifest['sha256'],
                fit=manifest['fit']))+'\n')
            (latest/'fixed_band_rules.json').write_text(json.dumps([manifest['rule']])+'\n')
            # Preserve blocked forecasts too, with exact inline source evidence.
            snapshot = dict(manifest=dict(revision=manifest['revision'], generated_utc=generated,
                            config_signature=manifest['config_signature']), board=board,
                            fixed_band_rules=[manifest['rule']])
            forecast_history.record(store, snapshot, sharded=True)
            locks.record(store, dt.datetime.now(UTC), policy_version=locks.policy_for_revision(manifest['revision']), finalize=False)
            for row in board.to_dict('records'):
                reasons = []
                for side in ('home', 'away'):
                    evidence = row.get(side+'_availability_evidence')
                    evidence = json.loads(evidence) if isinstance(evidence, str) else evidence or {}
                    reasons.extend(evidence.get('blockers', []))
                if not row.get('ready'):
                    reasons.append('fresh paired quote or base features unavailable')
                if not row.get('availability_ready'):
                    reasons.append('complete current official availability required')
                health['games'].append(dict(game_id=row['game_id'],
                    cutoff_utc=locks.deadline(row['kickoff_utc'] if row.get('kickoff_utc') else __import__('nfl_model').kickoff_utc(row)).isoformat(),
                    blockers=sorted(set(reasons))))
            commit = persist(data, f'ATS candidates and sources {dt.datetime.now(UTC).isoformat()}')
            acknowledge(data, commit, store)
    except Exception as exc:
        health['errors'].append(str(exc))
        print(f'::error::ATS refresh failed: {exc}', flush=True)
    stores = locks.runtime_stores(data)
    for store in stores:
        checkpoints(store, dt.datetime.now(UTC))
    if sum(len(locks.read(p/CHECKPOINTS)) for p in stores) > old_checkpoints:
        (runtime/'publish_pending.json').write_text(json.dumps(dict(pending=True))+'\n')
    health['updated_utc'] = dt.datetime.now(UTC).isoformat()
    (runtime/'watcher_status.json').write_text(json.dumps(health, indent=2)+'\n')
    persist(data, 'ATS durability receipts and heartbeat')
    pending = runtime/'publish_pending.json'
    if pending.exists() and json.loads(pending.read_text()).get('pending'):
        try:
            publish(pending)
            persist(data, 'ATS publication delivery status')
        except Exception as exc:
            print(f'::error::ATS publication pending retry: {exc}', flush=True)
    return health


def handoff():
    """Require API acknowledgement of a queued successor; cron is only a backup."""
    return dispatch('lock-watcher.yml')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--max-minutes', type=float, default=270)
    args = parser.parse_args()
    start = time.monotonic()
    while True:
        health = None
        try:
            health = tick('data')
        except Exception as exc:
            print(f'::error::ATS persistence failure; retaining local evidence: {exc}', flush=True)
        if args.once:
            return 0 if health is not None and not health['errors'] else 1
        if time.monotonic()-start >= args.max_minutes*60:
            successor = handoff()
            path = Path('data')/lock_refresh.RUNTIME/'handoff.json'
            path.write_text(json.dumps(dict(successor_run_id=successor,
                acknowledged_utc=dt.datetime.now(UTC).isoformat(), state='successor queued'))+'\n')
            persist('data', 'ATS watcher handoff acknowledged')
            return
        time.sleep(60 if health and health.get('games') else 300)


if __name__ == '__main__':
    sys.exit(main())
