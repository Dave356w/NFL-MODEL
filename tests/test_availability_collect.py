"""Automatic sources must become exact pregame facts, or remain visibly unresolved."""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

import availability_collect as c
import ats_locks as locks
import ats_wait
import nfl_model as m

UTC=dt.timezone.utc
KO=dt.datetime(2026,11,6,1,15,tzinfo=UTC)
NOW=KO-dt.timedelta(minutes=90)
EVENT=dict(game_id='2026_09_JAX_BAL',season=2026,week=9,home='BAL',away='JAX',kickoff_utc=KO.isoformat())
PLAYERS=[dict(gsis_id=f'00-000000{i}',full_name=name,position=pos,team=team,season=2026,week=8,
              first_name=name.split()[0],last_name=name.split()[-1],status='ACT')
         for i,name,pos,team in [(1,'Aaron Alpha','QB','BAL'),(2,'Bob Beta','QB','BAL'),(3,'Dan Gamma','WR','BAL'),
                                 (4,'Evan Delta','QB','JAX'),(5,'Fred Epsilon','WR','JAX')]]
SCHEDULE=[dict(EVENT,game_type='REG',result=None)]
INACTIVE_URL=c.NFL+'/news/week-9-thursday-night-inactives-jacksonville-jaguars-at-baltimore-ravens'
START_URL='https://www.baltimoreravens.com/news/beta-to-start'


def report(team,week=9,last='FP',unknown=False):
    names={'BAL':[('Aaron Alpha','QB','OUT'),('Bob Beta','QB','(-)'),('Dan Gamma','WR','OUT')],
           'JAX':[('Fred Epsilon','WR','QUESTIONABLE')]}
    tables=[]
    for t in ('BAL','JAX'):
        rows=''.join(f'<tr><td>{"Unknown Player" if unknown and t==team else name}</td><td>{pos}</td><td>Knee</td>'
                     f'<td>LP</td><td>LP</td><td>{last}</td><td>{status}</td></tr>' for name,pos,status in names[t])
        tables.append(f'<div class="nfl-o-injury-report__container"><h2 class="nfl-o-injury-report__club-name">{c.TEAMS[t][0]}</h2>'
                      '<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Player','Position','Injury','Mon','Tue','Wed','Game Status'])
                      +'</tr></thead><tbody>'+rows+'</tbody></table></div>')
    return f'<select><option selected value="/team/injury-report/week/REG-{week}">Week</option></select>'+''.join(tables)


def html(title,body,pub):
    return '<h1>'+title+'</h1><script type="application/ld+json">'+json.dumps(dict(
        **{'@type':'NewsArticle'},headline=title,articleBody=body,datePublished=pub.isoformat()))+'</script>'


def inactive_html(body=None,pub=None,title='Week 9 Thursday night inactives: Jaguars at Ravens'):
    return html(title,body or 'RAVENS\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon',pub or NOW-dt.timedelta(minutes=1))


class Sources:
    def __init__(self):
        self.now=NOW;self.calls=[];self.fail=False;self.unknown=False;self.inactives=True;self.inactive_body=None

    def __call__(self,url):
        self.calls.append(url)
        if self.fail:raise OSError('fixture outage')
        if url.endswith('/rss/news'):
            club=next(t for t,(_,host) in c.TEAMS.items() if host in url)
            article=START_URL if club=='BAL' else 'https://www.'+c.TEAMS[club][1]+'/news/club-update'
            title='Bob Beta Will Start vs. Jaguars' if club=='BAL' else 'Club community update'
            text=f'<rss><channel><item><title>{title}</title><link>{article}</link><pubDate>Wed, 04 Nov 2026 18:00:00 GMT</pubDate></item></channel></rss>'
        elif url.endswith('/team/injury-report/'):
            team=next(t for t,(_,host) in c.TEAMS.items() if host in url)
            text=report(team,unknown=self.unknown)
        elif url.endswith('/inactives/'):
            text=f'<a href="{INACTIVE_URL}">Lists</a>' if self.inactives else '<p>Not announced</p>'
        elif url==INACTIVE_URL:text=inactive_html(body=self.inactive_body)
        elif url==START_URL:text=html('Bob Beta Will Start vs. Jaguars','The Ravens announced Bob Beta will start against the Jaguars this Thursday.',NOW-dt.timedelta(days=1))
        else:raise AssertionError(url)
        return dict(url=url,text=text,captured_utc=self.now.isoformat(),body_sha256=c.digest(text))


def collect(tmp_path,source=None,**kwargs):
    source=source or Sources()
    return c.refresh(tmp_path,SCHEDULE,PLAYERS,now=source.now,fetcher=source,force=True,**kwargs)


def test_all_32_official_feeds_and_sourced_facts_are_automatic(tmp_path):
    source=Sources();state=collect(tmp_path,source)
    assert len(c.TEAMS)==32 and set(state['teams'])==set(c.TEAMS)
    assert sum(url.endswith('/rss/news') for url in source.calls)==32
    assert all(h['news']['error'] is None for h in state['teams'].values())
    observations=c.read(tmp_path/c.AUTO)
    assert any(r['field']=='qb_starter' and r['gsis_id']=='00-0000002' for r in observations)
    assert sum(r['field']=='inactives_complete' and r['value'] is True for r in observations)==2
    assert sum(r['field']=='report_complete' and r['value'] is True for r in observations)==2
    assert c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)
    assert all(m.validate_availability_observation(r)==r for r in observations)
    from validate_data_files import validate_availability_observations
    validate_availability_observations(tmp_path/c.AUTO)
    assert len(c.read(tmp_path/c.NEWS))==32
    assert c.validate_store(tmp_path)['observations']==len(observations)


def test_repeated_collection_is_idempotent_and_preserves_first_capture(tmp_path):
    source=Sources();collect(tmp_path,source)
    journals=[c.AUTO,c.SOURCES,c.NEWS,c.REVIEW]
    before={f:(tmp_path/f).read_bytes() if (tmp_path/f).exists() else b'' for f in journals}
    source.now+=dt.timedelta(minutes=5);state=collect(tmp_path,source)
    assert all(((tmp_path/f).read_bytes() if (tmp_path/f).exists() else b'')==body for f,body in before.items())
    assert state['teams']['BAL']['report']['last_success_utc']==source.now.isoformat()
    assert all(r['observed_utc']==NOW.isoformat() for r in c.read(tmp_path/c.AUTO))
    assert c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)


def test_outage_keeps_evidence_but_expired_sources_cannot_lock(tmp_path):
    source=Sources();collect(tmp_path,source);before=(tmp_path/c.AUTO).read_bytes()
    source.fail=True;source.now+=dt.timedelta(minutes=36);state=collect(tmp_path,source)
    assert (tmp_path/c.AUTO).read_bytes()==before
    assert state['teams']['BAL']['news']['error']=='fixture outage'
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)


def test_changed_report_then_reversion_is_a_new_capture(tmp_path):
    source=Sources();collect(tmp_path,source)
    source.now+=dt.timedelta(minutes=1);source.unknown=True;collect(tmp_path,source)
    source.now+=dt.timedelta(minutes=1);source.unknown=False;state=collect(tmp_path,source)
    sources=c.read(tmp_path/c.SOURCES)
    latest=next(r for r in sources if r['source_capture_sha256']==state['teams']['BAL']['report']['source_capture_sha256'])
    assert latest['captured_utc']==source.now.isoformat()
    assert sum(r['kind']=='official_injury_report' and r['team']=='BAL' for r in sources)==3


def test_revised_inactive_list_supersedes_old_list_and_unknown_update_blocks(tmp_path):
    source=Sources();collect(tmp_path,source)
    source.now+=dt.timedelta(minutes=1)
    source.inactive_body='RAVENS\nQB Aaron Alpha\nJAGUARS\nWR Fred Epsilon'
    state=collect(tmp_path,source);result=resolved(tmp_path,state,asof=source.now)
    observations=json.loads(result.loc['BAL','availability_evidence'])['observations']
    assert not any(r.get('gsis_id')=='00-0000003' and r.get('source_kind')=='official_inactives' for r in observations)
    assert any(r.get('gsis_id')=='00-0000001' and r.get('source_kind')=='official_inactives' for r in observations)
    source.now+=dt.timedelta(minutes=1);source.inactive_body='RAVENS\nWR Unknown Player\nJAGUARS\nWR Fred Epsilon'
    state=collect(tmp_path,source)
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)


def test_relevant_news_article_failure_is_visible_and_blocks_completeness(tmp_path):
    source=Sources()
    def fetch(url):
        if url==START_URL:raise OSError('article unavailable')
        return source(url)
    state=c.refresh(tmp_path,SCHEDULE,PLAYERS,now=NOW,fetcher=fetch,force=True)
    assert state['teams']['BAL']['news']['article_errors']==[START_URL]
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)


@pytest.mark.parametrize('change',[{'week':8},{'last':'-'},{'unknown':True}])
def test_wrong_week_incomplete_or_unresolved_report_is_not_complete(change):
    index=c.PlayerIndex(PLAYERS)
    if 'week' in change:
        with pytest.raises(ValueError,match='week'):c.parse_injury_report(report('BAL',**change),'BAL',EVENT,index)
    else:assert not c.parse_injury_report(report('BAL',**change),'BAL',EVENT,index)['complete']


def test_wrong_opponent_report_is_rejected():
    with pytest.raises(ValueError,match='opponent'):
        c.parse_injury_report(report('BAL'),'BAL',dict(EVENT,away='BUF'),c.PlayerIndex(PLAYERS))


def test_explicit_removed_report_marker_is_not_an_unpublished_blank():
    text=report('BAL').replace('<td>FP</td><td>(-)</td>','<td>(-)</td><td>(-)</td>')
    assert c.parse_injury_report(text,'BAL',EVENT,c.PlayerIndex(PLAYERS))['complete']


def test_explicit_same_game_medical_news_and_active_roster_move():
    idx=c.PlayerIndex(PLAYERS)
    title='Aaron Alpha Ruled Out vs. Jaguars'
    facts,_=c.news_facts(dict(title=title,body=title),'BAL',EVENT,idx)
    assert facts==[dict(field='report_status',value='Out',gsis_id='00-0000001',player='Aaron Alpha',position='QB')]
    title='Ravens Sign Bob Beta Off Jaguars Practice Squad'
    facts,_=c.news_facts(dict(title=title,body='The Ravens signed Bob Beta to the active roster.'),'BAL',EVENT,idx)
    assert facts[0]['field']=='eligible' and facts[0]['value'] is True
    title='Ravens Sign Bob Beta to the Practice Squad'
    assert not c.news_facts(dict(title=title,body='Practice squad addition.'),'BAL',EVENT,idx)[0]


@pytest.mark.parametrize('body,pub,title',[
    ('RAVENS\nWR Unknown Player',None,None),
    ('JAGUARS\nWR Fred Epsilon',None,None),
    ('WR Dan Gamma',None,None),  # a league article without a team section is ambiguous
    (None,NOW-dt.timedelta(days=1),None),
    (None,None,'Week 8 Thursday inactives: Jaguars at Ravens'),
    (None,KO,None),
])
def test_inactive_unknown_wrong_team_day_week_or_late_is_rejected(body,pub,title):
    args={k:v for k,v in [('body',body),('pub',pub),('title',title)] if v is not None}
    with pytest.raises(ValueError):c.parse_inactives(c.article(inactive_html(**args)),'BAL',EVENT,c.PlayerIndex(PLAYERS))


def test_emergency_qb_is_an_inactive_not_a_starter_or_inferred_active():
    info=c.article(inactive_html(body='RAVENS\nQB Bob Beta (emergency third quarterback)\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon'))
    parsed=c.parse_inactives(info,'BAL',EVENT,c.PlayerIndex(PLAYERS))
    assert {r['gsis_id'] for r in parsed['rows']}=={'00-0000002','00-0000003'}
    assert parsed['complete']


@pytest.mark.parametrize('encoded', ['Cam&#39;Ron', 'Cam&#x27;Ron', 'Cam’Ron'])
@pytest.mark.parametrize('rendered_lines', [False, True])
def test_html_encoded_apostrophe_resolves_exact_inactive_player(encoded, rendered_lines):
    player=dict(gsis_id='00-0000008', full_name="Cam'Ron Silmon-Craig", position='S', team='JAX')
    idx=c.PlayerIndex(PLAYERS+[player])
    body=f'RAVENS\nWR Dan Gamma\nJAGUARS\nS {encoded} Silmon-Craig\nWR Fred Epsilon'
    info=c.article(inactive_html(body=body))
    if rendered_lines:info['lines']=body.splitlines()
    parsed=c.parse_inactives(info,'JAX',EVENT,idx)
    assert parsed['complete']
    assert {p['gsis_id'] for p in parsed['rows']}=={'00-0000008','00-0000005'}
    # Decoding an entity never authorizes fuzzy matching to an unknown name.
    info['body']=body.replace('Silmon-Craig','Unknown')
    info['lines']=info['body'].splitlines() if rendered_lines else []
    with pytest.raises(ValueError,match='unresolved inactive player'):
        c.parse_inactives(info,'JAX',EVENT,idx)


@pytest.mark.parametrize('text',[
    'Bob Beta could start against the Jaguars this Thursday.',
    'Bob Beta is expected to start against the Jaguars.',
    'Last week Bob Beta was named the starting quarterback.',
    'Bob Beta will start against the Bills.',
    'Bob Beta took first-team reps at practice.',
    'Could Bob Beta start this Thursday?',
])
def test_uncertain_past_different_opponent_and_practice_are_not_starter_facts(text):
    facts,_=c.news_facts(dict(title=text,body=text),'BAL',EVENT,c.PlayerIndex(PLAYERS))
    assert not facts


def test_exact_aliases_and_ambiguous_names_never_fuzzy_match():
    players=PLAYERS+[dict(PLAYERS[0],gsis_id='00-0000009',team='BAL')]
    idx=c.PlayerIndex(players)
    assert idx.resolve('Aaron Alpha','BAL') is None
    assert idx.resolve('A. Alpha','BAL') is None
    assert idx.resolve('Bob Beta Jr.','BAL')['gsis_id']=='00-0000002'


def test_unknown_names_are_reviewed_and_report_cannot_complete(tmp_path):
    source=Sources();source.unknown=True;state=collect(tmp_path,source)
    assert not state['teams']['BAL']['report']['complete']
    assert any('unresolved injury player' in r['issue'] for r in c.read(tmp_path/c.REVIEW))
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)


def test_hash_linkage_rejects_tampering(tmp_path):
    collect(tmp_path)
    rows=c.read(tmp_path/c.AUTO);rows[0]['value']='Available'
    (tmp_path/c.AUTO).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError,match='not supported'):c.validate_store(tmp_path)


def resolved(tmp_path,state,asof=NOW):
    target=pd.DataFrame([dict(game_id=EVENT['game_id'],season=2026,week=9,team=t,gameday='2026-11-05',kickoff=KO,result=float('nan')) for t in ('BAL','JAX')])
    qb=pd.DataFrame([dict(season=2026,week=w,game_id=t+str(w),team=t,gsis_id=pid,name=name,
                         dropbacks=n,net_yards=n*eff,leader=n==30,starter=n==30)
                     for t,pid,name,n,eff in [('BAL','00-0000001','Aaron Alpha',30,8),('BAL','00-0000002','Bob Beta',5,4),('JAX','00-0000004','Evan Delta',30,7)]
                     for w in range(5,9)])
    roster=pd.DataFrame(PLAYERS);snaps=pd.DataFrame(columns=['season','week','game_id','team','gsis_id','position','offense_snaps','defense_snaps'])
    injury=pd.DataFrame(columns=['season','week','team','gsis_id','report_status'])
    base=m.availability_table(target,qb,snaps,injury,roster)
    result=m.resolve_game_availability(target,base,qb,snaps,injury,roster,observations=c.read(tmp_path/c.AUTO),asof=asof,collection=state).set_index('team')
    return result


def save_board(tmp_path,result,generated=NOW):
    row=dict(game_id=EVENT['game_id'],season=2026,week=9,home='BAL',away='JAX',gameday='2026-11-05',gametime='20:15',result='',ready=True,
             model_wp=.7,spread_line=3.,availability_policy=m.AVAILABILITY_POLICY)
    for side,team in [('home','BAL'),('away','JAX')]:
        for col in ('injury_report','qb_expected','availability_evidence','availability_evidence_sha256'):row[f'{side}_{col}']=result.loc[team,col]
    latest=tmp_path/'latest';latest.mkdir(exist_ok=True)
    (latest/'manifest.json').write_text(json.dumps(dict(revision=m.REVISION,generated_utc=generated.isoformat(),recipe=m.PRODUCT_RECIPE,config_signature=m.config_signature()[0])))
    (latest/'fixed_band_rules.json').write_text(json.dumps([dict(season=2026,week=9,training_max_season=2026,training_max_week=8,training_games=1400,
        cuts=[3.,7.,10.],magnitudes=[3.,4.,7.,14.],method='weighted_median_signed_mov_weekly_decay')]))
    pd.DataFrame([row]).to_csv(latest/'board.csv',index=False)


def test_collection_to_corrected_starter_to_immutable_t60_lock(tmp_path):
    state=collect(tmp_path);result=resolved(tmp_path,state)
    assert result.loc['BAL','qb_expected']=='Bob Beta'
    assert result.loc['BAL','qb_source']=='confirmed_starter'
    save_board(tmp_path,result,generated=NOW-dt.timedelta(minutes=1))
    assert locks.record(tmp_path,NOW)==dict(candidates=0,locks=0)  # run start predates evidence
    save_board(tmp_path,result)
    assert locks.record(tmp_path,NOW)==dict(candidates=1,locks=0)
    cutoff=KO-dt.timedelta(hours=1)
    assert locks.record(tmp_path,cutoff)==dict(candidates=0,locks=1)
    before=(tmp_path/locks.LOCKS).read_bytes()
    state['teams']['BAL']['inactives']['complete']=False
    save_board(tmp_path,resolved(tmp_path,state,asof=cutoff+dt.timedelta(seconds=1)),generated=cutoff+dt.timedelta(seconds=1))
    assert locks.record(tmp_path,cutoff+dt.timedelta(seconds=1))==dict(candidates=0,locks=0)
    assert (tmp_path/locks.LOCKS).read_bytes()==before
    locks.validate_store(tmp_path)


def test_no_inactives_no_candidate_but_hold_refreshes_and_locks(tmp_path):
    source=Sources();source.inactives=False
    state=collect(tmp_path,source);save_board(tmp_path,resolved(tmp_path,state))
    assert locks.record(tmp_path,NOW)==dict(candidates=0,locks=0)
    from test_ats_wait import Clock
    clock=Clock(NOW)
    def refresh():
        source.now=clock.now;source.inactives=True
        state=collect(tmp_path,source);save_board(tmp_path,resolved(tmp_path,state,asof=clock.now),generated=clock.now)
        return locks.record(tmp_path,clock.now)
    steps=ats_wait.hold(tmp_path,KO,refresh,lambda:locks.record(tmp_path,clock.now),clock,clock.sleep)
    assert [r[0] for r in steps]==['refresh','finalize']
    assert steps[0][2]['candidates']==1 and steps[1][2]['locks']==1


def test_failed_refresh_cannot_freeze_a_missing_inactive_list(tmp_path):
    source=Sources();source.inactives=False
    state=collect(tmp_path,source);save_board(tmp_path,resolved(tmp_path,state))
    from test_ats_wait import Clock
    clock=Clock(NOW)
    steps=ats_wait.hold(tmp_path,KO,lambda:1,lambda:locks.record(tmp_path,clock.now),clock,clock.sleep)
    assert [r[0] for r in steps]==['refresh','refresh','finalize']
    assert not c.read(tmp_path/locks.LOCKS)


def test_both_teams_fresh_resolved_lists_required_even_if_digest_is_recomputed(tmp_path):
    state=collect(tmp_path);state['teams']['JAX']['inactives']['complete']=False
    save_board(tmp_path,resolved(tmp_path,state))
    assert locks.record(tmp_path,NOW)==dict(candidates=0,locks=0)
    state['teams']['JAX']['inactives']['complete']=True
    state['teams']['BAL']['news']['last_success_utc']=(NOW-dt.timedelta(hours=1)).isoformat()
    save_board(tmp_path,resolved(tmp_path,state))
    assert locks.record(tmp_path,NOW)==dict(candidates=0,locks=0)


def test_legacy_signature_and_shadow_are_preserved():
    with m.revision_identity('boxscore-composite-v1.20',m.PRODUCT_RECIPE):
        old,cfg=m.config_signature()
        assert old=='d8f1c3da2479d934a3d9c3890a3225d301b8cdf11acd49007eb184f969e9fe60'
        assert 'automatic_availability' not in cfg and 'availability_observations' in cfg
    new,cfg=m.config_signature()
    assert new!=old and cfg['automatic_availability']['policy']==c.POLICY


# --- Regression cases from the 2026-11-04 review of commit adf72ed ---------------------------

# Body text of NFL.com's "Week 8 Monday night inactives: Chicago Bears at Seattle Seahawks"
# (published 2026-11-02), as article() extracts it.
REAL_BODY=('BEARS\n\nQB Case Keenum (emergency third quarterback)\nRB Kyle Monangai\nOL Jordan McFadden\n'
           'OL Jordan van den Berg\nDL Jayden Loving\nDB Malik Muhammad\n\nSEAHAWKS\n\n'
           'QB Drew Lock (emergency third quarterback)\nRB Velus Jones\nWR Rashid Shaheed\nG Beau Stephens\n'
           'OT Charles Cross\nDT Brandon Pili\nLB Uchenna Nwosu')


def test_real_nfl_inactive_page_format_parses_every_row():
    ko=dt.datetime(2026,11,3,1,15,tzinfo=UTC)
    event=dict(game_id='2026_08_CHI_SEA',season=2026,week=8,home='SEA',away='CHI',kickoff_utc=ko.isoformat())
    rows=[]
    for line in REAL_BODY.splitlines():
        parts=line.split()
        if len(parts)<3:continue
        team='CHI' if not rows or rows[-1]['team']=='CHI' and 'Drew' not in line else 'SEA'
        name=' '.join(p for p in parts[1:] if not p.startswith('(') and not p.endswith(')') and p not in ('third',))
        rows.append(dict(gsis_id=f'00-{len(rows)+10:07d}',full_name=name,position=parts[0],team=team,season=2026,week=7,status='ACT'))
    index=c.PlayerIndex(rows)
    info=c.article(html('Week 8 Monday night inactives: Chicago Bears at Seattle Seahawks',REAL_BODY,ko-dt.timedelta(minutes=90)))
    assert len(c.parse_inactives(info,'CHI',event,index)['rows'])==6
    assert len(c.parse_inactives(info,'SEA',event,index)['rows'])==7


@pytest.mark.parametrize('body',[
    'RAVENS\nQuarterback Bob Beta\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon',   # unknown prefix
    'RAVENS\nBob Beta\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon',               # bare name
    'RAVENS\nQB Bob\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon',                 # one-word name
    'RAVENS\nQB Bob Beta, WR Dan Gamma\nJAGUARS\nWR Fred Epsilon',            # two players on a line
    'RAVENS\nWR Dan Gamma\nAlso inactive for Baltimore:\nQB Bob Beta\nJAGUARS\nWR Fred Epsilon',  # fragmented
    'RAVENS\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon\nRAVENS\nQB Bob Beta',   # repeated section
])
def test_partial_inactive_list_is_never_complete(body):
    with pytest.raises(ValueError):
        c.parse_inactives(c.article(inactive_html(body=body)),'BAL',EVENT,c.PlayerIndex(PLAYERS))


def test_strict_inactive_parser_accepts_punctuated_rows_and_trailing_prose():
    body='RAVENS\nQB: Bob Beta\n- WR Dan Gamma (hamstring)\nJAGUARS\nWR Fred Epsilon\nStay with NFL.com for coverage of the game.'
    info=c.article(inactive_html(body=body));index=c.PlayerIndex(PLAYERS)
    assert {r['gsis_id'] for r in c.parse_inactives(info,'BAL',EVENT,index)['rows']}=={'00-0000002','00-0000003'}
    assert {r['gsis_id'] for r in c.parse_inactives(info,'JAX',EVENT,index)['rows']}=={'00-0000005'}


def test_bundle_without_this_team_is_an_identity_mismatch_not_a_list_failure():
    info=c.article(inactive_html(body='BILLS\nWR Fred Epsilon'))
    with pytest.raises(c.InactiveIdentityMismatch):c.parse_inactives(info,'BAL',EVENT,c.PlayerIndex(PLAYERS))


def test_partial_list_end_to_end_blocks_collection(tmp_path):
    source=Sources();source.inactive_body='RAVENS\nQuarterback Aaron Alpha\nWR Dan Gamma\nJAGUARS\nWR Fred Epsilon'
    state=collect(tmp_path,source)
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)
    assert c.collection_ready(c.team_snapshot(state,'JAX',EVENT['game_id']),NOW,True)
    assert not any(r['field']=='inactives_complete' and r['team']=='BAL' for r in c.read(tmp_path/c.AUTO))


@pytest.mark.parametrize('body',[
    'RAVENS\nQuarterback Aaron Alpha\nJAGUARS\nWR Fred Epsilon',   # unparseable revision of the same page
    'JAGUARS\nWR Fred Epsilon',                                     # revision dropped this team's section
])
def test_failed_revision_of_accepted_list_withdraws_completeness(tmp_path,body):
    source=Sources();state=collect(tmp_path,source)
    assert c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)
    source.now+=dt.timedelta(minutes=1);source.inactive_body=body
    state=collect(tmp_path,source)
    assert state['teams']['BAL']['inactives']['complete'] is False
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)
    assert c.collection_ready(c.team_snapshot(state,'JAX',EVENT['game_id']),source.now,True)
    # No candidate can be saved from the withdrawn list.
    save_board(tmp_path,resolved(tmp_path,state,asof=source.now),generated=source.now)
    assert locks.record(tmp_path,source.now)['candidates']==0


@pytest.mark.parametrize('text',[
    'Bob Beta is not going to start against the Jaguars this Thursday.',
    "Bob Beta won't start against the Jaguars this Thursday.",   # no start phrase: no fact, nothing to review
    'Bob Beta won’t be the starting quarterback; Aaron Alpha will start against the Jaguars, not Beta.',
    'Instead of Aaron Alpha, Bob Beta will start against the Jaguars this Thursday.',
])
def test_negated_or_contrastive_start_is_review_not_a_fact(text):
    facts,issues=c.news_facts(dict(title='Ravens quarterback update',body=text),'BAL',EVENT,c.PlayerIndex(PLAYERS))
    assert not any(f['field']=='qb_starter' for f in facts)
    if "won't start" not in text:assert 'negated or contrastive start statement' in issues


def test_plain_confirmed_start_is_still_a_fact():
    text='The Ravens announced Bob Beta will start against the Jaguars this Thursday.'
    facts,issues=c.news_facts(dict(title='Ravens quarterback update',body=text),'BAL',EVENT,c.PlayerIndex(PLAYERS))
    assert [f['gsis_id'] for f in facts if f['field']=='qb_starter']==['00-0000002'] and not issues


CLUB_URL='https://www.baltimoreravens.com/news/ravens-inactives-vs-jaguars-week-9'


class ClubSources(Sources):
    """Baltimore's feed also carries a club inactive article."""
    club_body='The Ravens announced their inactives against the Jaguars.\nQB Aaron Alpha\nWR Dan Gamma'

    def __call__(self,url):
        if url=='https://www.baltimoreravens.com/rss/news':
            self.calls.append(url)
            items=''.join(f'<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate></item>' for t,u,d in [
                ('Bob Beta Will Start vs. Jaguars',START_URL,'Wed, 04 Nov 2026 18:00:00 GMT'),
                ('Ravens inactives vs. Jaguars',CLUB_URL,'Thu, 05 Nov 2026 23:30:00 GMT')])
            text=f'<rss><channel>{items}</channel></rss>'
            return dict(url=url,text=text,captured_utc=self.now.isoformat(),body_sha256=c.digest(text))
        if url==CLUB_URL:
            self.calls.append(url)
            text=html('Ravens inactives vs. Jaguars',self.club_body,NOW-dt.timedelta(minutes=15))
            return dict(url=url,text=text,captured_utc=self.now.isoformat(),body_sha256=c.digest(text))
        return super().__call__(url)


def test_failed_club_article_cannot_withdraw_a_complete_league_list(tmp_path):
    # Prose-only club articles are common (BAL, DEN, DET in 2026 week 8); they are reviewed, not blocking.
    source=ClubSources();source.club_body='Bob Beta is active. Dan Gamma is among the Ravens inactives.'
    state=collect(tmp_path,source)
    assert CLUB_URL in source.calls
    assert state['teams']['BAL']['inactives']['complete'] is True
    assert state['teams']['BAL']['inactives']['url']==INACTIVE_URL
    assert c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)
    assert any(r['source_url']==CLUB_URL and r['issue']=='no complete inactive list found' for r in c.read(tmp_path/c.REVIEW))


def test_failed_revision_of_the_accepted_club_list_withdraws_it(tmp_path):
    source=ClubSources();source.inactives=False   # no NFL.com list: the club page is the only source
    state=collect(tmp_path,source)
    assert state['teams']['BAL']['inactives']['url']==CLUB_URL
    assert c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)
    source.now+=dt.timedelta(minutes=1)
    source.club_body='The Ravens announced their inactives against the Jaguars.\nQuarterback Aaron Alpha\nWR Dan Gamma'
    state=collect(tmp_path,source)
    assert state['teams']['BAL']['inactives']['complete'] is False
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),source.now,True)


def test_failed_league_list_outranks_a_club_success_in_the_same_refresh(tmp_path):
    source=ClubSources();source.inactive_body='RAVENS\nQuarterback Aaron Alpha\nJAGUARS\nWR Fred Epsilon'
    state=collect(tmp_path,source)
    assert state['teams']['BAL']['inactives']['complete'] is False
    assert not c.collection_ready(c.team_snapshot(state,'BAL',EVENT['game_id']),NOW,True)
