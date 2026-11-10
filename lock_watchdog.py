"""Restart an absent watcher and surface stale heartbeats without deleting evidence."""
import base64
import datetime as dt
import json
import subprocess


def main():
    runs = json.loads(subprocess.check_output(['gh', 'run', 'list', '-w', 'lock-watcher.yml',
        '--limit', '30', '--json', 'databaseId,status']))
    running = [r for r in runs if r['status']=='in_progress']
    if not running and not any(r['status'] in ('queued', 'pending', 'waiting') for r in runs):
        subprocess.run(['gh', 'workflow', 'run', 'lock-watcher.yml', '--ref', 'main'], check=True)
        print('Watcher restart requested')
        return 0
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
