"""RSS retirement preserves old decisions while official reports still gate new locks."""
import copy
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

import availability_collect as c
import ats_locks as locks
import nfl_model as m
import season_ats
import build_site
import retro_lock
from test_availability_collect import Sources, NOW, KO, EVENT, PLAYERS, SCHEDULE, collect, resolved, save_board


def reports_only(tmp_path):
    source=Sources()
    def fetch(url):
        assert '/rss/' not in url
        assert 'beta-to-start' not in url
        return source(url)
    return c.refresh(tmp_path,SCHEDULE,PLAYERS,now=NOW,fetcher=fetch,force=True)


def test_no_rss_requests_or_news_facts_and_failed_news_cannot_block(tmp_path):
    state=reports_only(tmp_path)
    assert state['policy']==c.REPORTS_POLICY and state['rss_enabled'] is False
    assert not (tmp_path/c.NEWS).exists()
    assert not any(r['source_kind']=='official_team_news' for r in c.read(tmp_path/c.AUTO))
    snap=c.team_snapshot(state,'BAL',EVENT['game_id'])
    snap['news']={'error':'retired feed outage','article_errors':['bad URL']}
    assert c.collection_ready(snap,NOW,True)
    snap['inactives']['complete']=False
    assert not c.collection_ready(snap,NOW,True)
    assert any('inactives' in issue for issue in c.readiness_issues(snap,NOW,True))


def test_old_news_journals_retained_but_not_applied_to_new_forecasts(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'REVISION','boxscore-composite-v1.22')  # original RSS-retirement contract
    collect(tmp_path)
    names=[c.NEWS,c.AUTO,c.SOURCES]
    before={n:(tmp_path/n).read_bytes() for n in names}
    state=reports_only(tmp_path)
    assert all((tmp_path/n).read_bytes().startswith(before[n]) for n in names)
    result=resolved(tmp_path,state)
    assert result.loc['BAL','qb_source']!='confirmed_starter'
    for text in result.availability_evidence:
        assert not any(r.get('source_kind')=='official_team_news' for r in json.loads(text)['observations'])
    save_board(tmp_path,result)
    assert locks.record(tmp_path,NOW)=={'candidates':1,'locks':0}
    assert locks.record(tmp_path,KO-dt.timedelta(hours=1))=={'candidates':0,'locks':1}
    saved,=locks.read(tmp_path/locks.LOCKS)
    assert saved['revision']==m.REVISION
    assert all(e['collection']['policy']==c.REPORTS_POLICY for e in saved['availability'].values())


def test_prior_signatures_are_frozen_and_retirement_has_a_new_identity():
    assert m.REVISION=='boxscore-composite-v1.24'
    assert m.OUTPUT_NAME=='nfl_boxscore_output_v1_24'
    with m.revision_identity('boxscore-composite-v1.21',m.PRODUCT_RECIPE):
        prior,_=m.config_signature()
    assert prior=='9eb27acbe2f14789d9a4b90b214122354d1fee7bf1d15fa736d5138af88d1c67'
    current,cfg=m.config_signature()
    assert current!=prior and cfg['automatic_availability']['policy']==c.REPORTS_POLICY
    assert cfg['automatic_availability']['news_observations']=='excluded'
    assert len(sum(m.model_terms(m.PRODUCT_RECIPE),[]))==10


def test_old_locks_stay_authoritative_without_rewriting_or_duplicating(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'REVISION','boxscore-composite-v1.23')  # v1.23 inherits prior locks; v1.24 replays
    root=Path(__file__).resolve().parents[1]
    records=locks.display_records(root/'data')
    before=copy.deepcopy(records)
    selected=locks.current_records(records,m.REVISION)
    old=list(locks.current_records(records,'boxscore-composite-v1.22').values())
    own={key:row for key,row in records.items() if key[0]==m.REVISION}
    expected={(m.REVISION,row['game_id']):row for row in old}
    expected.update(own)
    assert selected.keys()==expected.keys() and len(old)>=13
    assert all(selected[key] is row for key,row in expected.items())
    assert records==before
    # Current-version saved selection wins over the inherited one.
    original=old[0]
    replacement=dict(original,revision=m.REVISION)
    records[locks.key(replacement)]=replacement
    assert locks.current_records(records,m.REVISION)[locks.key(replacement)] is replacement
    later=dict(original,revision='boxscore-composite-v1.22',game_id='future',lock_at_utc=(locks.QB_REPAIRS_UTC+dt.timedelta(seconds=1)).isoformat())
    records[locks.key(later)]=later
    assert (m.REVISION,'future') not in locks.current_records(records,m.REVISION)


def test_rescue_uses_exact_last_committed_sunday_night_board():
    requests=json.loads(retro_lock.REQUESTS.read_text())
    request,=[r for r in requests if r['game_id']=='2026_09_TB_CHI']
    assert request['source_commit']=='b049776c391f7903623b7a2cd650f28eb198f44a'
    # Git-free synthetic source has the exact saved input values.
    source=dict(committed_utc='2026-11-09T00:13:00Z',
        manifest=dict(revision='boxscore-composite-v1.21',season=2026,week=9,
                      generated_utc='2026-11-09T00:12:47.148879+00:00',config_signature='old'),
        board_row=dict(game_id=request['game_id'],season='2026',week='9',home='CHI',away='TB',gameday='2026-11-08',
                       gametime='20:20',ready='True',result='',model_wp='0.669476',spread_line='6'),
        fixed_rule=dict(season=2026,week=9,training_max_season=2026,training_max_week=8,
                        method=locks.POLICY_METHODS[locks.POLICY_VERSION],cuts=[3,7,10],magnitudes=[3,5,6,13]))
    row=retro_lock.decision(source)
    assert (row['selected_side'],row['market_spread'],row['fixed_band_spread'])==('away',6.,5.)
    latest=dict(manifest=dict(revision='boxscore-composite-v1.22'),ats_locks={locks.key(row):row},
                board=pd.DataFrame([dict(game_id=request['game_id'],result=-7.,home_score=17.,away_score=24.)]))
    row.update(finalized_utc='2026-11-09T20:00:00Z',retro_locked=True)
    pool=season_ats.build(latest,pd.DataFrame())
    assert len(pool)==1
    assert pool.iloc[0].fixed_band_ats_team=='TB' and pool.iloc[0].fixed_band_ats_handicap==6
    assert pool.iloc[0].fixed_band_ats_result=='W'
    assert len(build_site.public_ats({'pooled_ats':pool}))==1


def test_retired_collection_policy_cannot_create_a_new_revision_candidate(tmp_path):
    old=collect(tmp_path)
    result=resolved(tmp_path,old)
    save_board(tmp_path,result)
    assert locks.record(tmp_path,NOW)=={'candidates':0,'locks':0}
