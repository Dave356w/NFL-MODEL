#!/usr/bin/env python3
"""Append a sourced fact for one game; first capture time is always the local clock.

See AVAILABILITY.md. This command never changes a forecast or an existing journal line.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path

import nfl_model as m


def append_observation(path, observation, now=None):
    path=Path(path)
    # Do not permit caller-supplied capture times or append behind a corrupt journal.
    row=dict(observation,observed_utc=(now or dt.datetime.now(dt.timezone.utc)).isoformat())
    row=m.validate_availability_observation(row)
    prior=m.load_availability_observations(path)
    if row in prior: return row
    path.parent.mkdir(parents=True,exist_ok=True)
    prefix='\n' if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b'\n') else ''
    with path.open('a',encoding='utf-8') as out:
        out.write(prefix+json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
        out.flush(); os.fsync(out.fileno())
    return row


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path',default='data/availability_observations.jsonl')
    parser.add_argument('--game-id',required=True)
    parser.add_argument('--team',required=True)
    parser.add_argument('--field',required=True,choices=m.AVAILABILITY_FIELDS)
    parser.add_argument('--value',required=True,help='true/false, or Available/Out/Doubtful/Questionable')
    parser.add_argument('--gsis-id')
    parser.add_argument('--player')
    parser.add_argument('--position')
    parser.add_argument('--source-url',required=True)
    parser.add_argument('--published-utc',required=True)
    parser.add_argument('--effective-utc')
    parser.add_argument('--status',choices=['confirmed','pending'],default='confirmed')
    parser.add_argument('--reason',required=True)
    args=parser.parse_args(argv)
    value={'true':True,'false':False}.get(args.value,args.value)
    row=dict(game_id=args.game_id,team=args.team,field=args.field,value=value,source_url=args.source_url,
             published_utc=args.published_utc,effective_utc=args.effective_utc or args.published_utc,
             status=args.status,reason=args.reason)
    for k,v in [('gsis_id',args.gsis_id),('player',args.player),('position',args.position)]:
        if v is not None: row[k]=v
    try: saved=append_observation(args.path,row)
    except (ValueError,OSError) as exc: parser.error(str(exc))
    print(f"Saved {saved['game_id']} {saved['team']} {saved['field']}={saved['value']} at {saved['observed_utc']}")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
