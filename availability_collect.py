"""Collect official NFL team news, final injury reports and game-day inactive lists.

No keys, model calls or subjective injury penalties. Raw news is reference material:
only explicit, game-bound statements become facts. Unresolved material is queued for review.
All journals are append-only. Publication and first-capture times are kept separate.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
import json
import re
import unicodedata
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UTC=dt.timezone.utc
POLICY='official-availability-collection-2026-11-04-v1'
AUTO='availability_auto_observations.jsonl'
SOURCES='availability_sources.jsonl'
NEWS='team_news.jsonl'
REVIEW='availability_review.jsonl'
STATE='availability_collection_status.json'
MAX_AGE_MINUTES=35
NEWS_POLL_MINUTES=15
NFL='https://www.nfl.com'
TEAMS={
 'ARI':('Arizona Cardinals','azcardinals.com'),'ATL':('Atlanta Falcons','atlantafalcons.com'),
 'BAL':('Baltimore Ravens','baltimoreravens.com'),'BUF':('Buffalo Bills','buffalobills.com'),
 'CAR':('Carolina Panthers','panthers.com'),'CHI':('Chicago Bears','chicagobears.com'),
 'CIN':('Cincinnati Bengals','bengals.com'),'CLE':('Cleveland Browns','clevelandbrowns.com'),
 'DAL':('Dallas Cowboys','dallascowboys.com'),'DEN':('Denver Broncos','denverbroncos.com'),
 'DET':('Detroit Lions','detroitlions.com'),'GB':('Green Bay Packers','packers.com'),
 'HOU':('Houston Texans','houstontexans.com'),'IND':('Indianapolis Colts','colts.com'),
 'JAX':('Jacksonville Jaguars','jaguars.com'),'KC':('Kansas City Chiefs','chiefs.com'),
 'LA':('Los Angeles Rams','therams.com'),'LAC':('Los Angeles Chargers','chargers.com'),
 'LV':('Las Vegas Raiders','raiders.com'),'MIA':('Miami Dolphins','miamidolphins.com'),
 'MIN':('Minnesota Vikings','vikings.com'),'NE':('New England Patriots','patriots.com'),
 'NO':('New Orleans Saints','neworleanssaints.com'),'NYG':('New York Giants','giants.com'),
 'NYJ':('New York Jets','newyorkjets.com'),'PHI':('Philadelphia Eagles','philadelphiaeagles.com'),
 'PIT':('Pittsburgh Steelers','steelers.com'),'SEA':('Seattle Seahawks','seahawks.com'),
 'SF':('San Francisco 49ers','49ers.com'),'TB':('Tampa Bay Buccaneers','buccaneers.com'),
 'TEN':('Tennessee Titans','tennesseetitans.com'),'WAS':('Washington Commanders','commanders.com')}
STATUSES={'OUT':'Out','DOUBTFUL':'Doubtful','QUESTIONABLE':'Questionable',
          '(-)':'Available','-':'Available','':'Available','UNSPECIFIED':'Available'}
UNCERTAIN=re.compile(r'\b(could|may|might|potential|possibly|reportedly|expected|likely|if|rumou?r|pundit|prediction|mock)\b',re.I)
NEGATION=re.compile(r"\b(?:not|never|no longer|cannot|unable|instead of|rather than|in place of|ruled out|benched)\b|n[\u2019']t\b",re.I)
RELEVANT=re.compile(r'inactiv|injur|quarterback|\bQB\b|start|signs?|signed|waiv|releas|activat|elevat|trad|reserve',re.I)


def utc(value):
    if isinstance(value,dt.datetime): out=value
    else:
        text=str(value)
        try: out=dt.datetime.fromisoformat(text.replace('Z','+00:00'))
        except ValueError: out=parsedate_to_datetime(text)
    if out.tzinfo is None: raise ValueError('source timestamps require a timezone')
    return out.astimezone(UTC)


def norm(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',unescape(str(text))) if not unicodedata.combining(c))
    words=re.sub(r'[^a-z0-9 ]','',text.casefold()).split()
    if words and words[-1] in ('jr','sr','ii','iii','iv','v'): words.pop()
    return ' '.join(words)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read(path):
    p=Path(path)
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()] if p.exists() else []


def append(path,rows):
    if not rows:return
    import os
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as out:
        for r in rows:out.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n')
        out.flush();os.fsync(out.fileno())


def fetch(url):
    """Fetch public sources with a bounded response; no credentials or browser cookies."""
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname is None:raise ValueError('HTTPS source required')
    request=urllib.request.Request(url,headers={'User-Agent':'NFL-MODEL/availability-collector (public reports)',
                                               'Accept':'application/rss+xml,text/html,application/json'})
    with urllib.request.urlopen(request,timeout=12) as response:
        final=urllib.parse.urlsplit(response.url)
        if final.hostname.removeprefix('www.')!=parsed.hostname.removeprefix('www.'):
            raise ValueError('source redirected outside its official host')
        body=response.read(3_000_001)
        if len(body)>3_000_000:raise ValueError('source exceeded response limit')
        charset=response.headers.get_content_charset() or 'utf-8'
        return dict(url=url,text=body.decode(charset,errors='replace'),captured_utc=dt.datetime.now(UTC).isoformat(),
                    body_sha256=hashlib.sha256(body).hexdigest())


class PlayerIndex:
    """Exact GSIS/name resolution. Never fuzzy-match a report to a different player."""
    def __init__(self,records):
        if hasattr(records,'to_dict'):records=records.to_dict('records')
        self.players={};self.names={}
        def number(v):
            try:return int(v)
            except (ValueError,TypeError,OverflowError):return 0
        for row in sorted(records,key=lambda r:(number(r.get('season')),number(r.get('week')))):
            pid=row.get('gsis_id')
            if not isinstance(pid,str) or not re.fullmatch(r'00-\d{7}',pid):continue
            name=next((row.get(k) for k in ('full_name','display_name','player_name')
                       if isinstance(row.get(k),str) and row[k].strip()),None)
            if not name:continue
            player=dict(gsis_id=pid,player=name,position=str(row.get('position') or ''),team=row.get('team'))
            old=self.players.get(pid,{})
            aliases=set(old.get('aliases',[]))|{name}
            last=row.get('last_name')
            for first in (row.get('first_name'),row.get('football_name')):
                if isinstance(first,str) and isinstance(last,str):aliases.add(first+' '+last)
            player['aliases']=sorted(aliases);self.players[pid]=player
            for alias in aliases:self.names.setdefault(norm(alias),set()).add(pid)

    def resolve(self,name,team,position=None,allow_transfer=False):
        ids=set(self.names.get(norm(name),()))
        if position=='QB':ids={i for i in ids if self.players[i]['position']=='QB'}
        home={i for i in ids if self.players[i]['team']==team}
        ids=home or (ids if allow_transfer else set())
        return self.players[next(iter(ids))] if len(ids)==1 else None


def soup(text):
    from bs4 import BeautifulSoup
    return BeautifulSoup(text,'html.parser')


def rss_items(text,base):
    root=ET.fromstring(text)
    if root.tag!='rss':raise ValueError('not an RSS news feed')
    out=[]
    for item in root.findall('./channel/item'):
        url=item.findtext('link') or '';title=item.findtext('title') or '';pub=item.findtext('pubDate')
        if not title or not pub:continue
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.hostname.removeprefix('www.')!=urllib.parse.urlsplit(base).hostname.removeprefix('www.'):
            continue
        out.append(dict(url=url,title=' '.join(title.split()),published_utc=utc(pub).isoformat()))
    if not out:raise ValueError('news feed has no dated official articles')
    return out


def article(text):
    doc=soup(text);data={}
    for tag in doc.select('script[type="application/ld+json"]'):
        try:raw=json.loads(tag.get_text())
        except ValueError:continue
        choices=raw if isinstance(raw,list) else raw.get('@graph',[raw]) if isinstance(raw,dict) else []
        for item in choices:
            if isinstance(item,dict) and ('Article' in str(item.get('@type')) or 'articleBody' in item):data=item;break
    title=data.get('headline') or (doc.h1.get_text(' ',strip=True) if doc.h1 else '')
    body=data.get('articleBody')
    if not isinstance(body,str) or not body.strip():
        nodes=doc.select('.nfl-c-body-part--text, .d3-l-article__content, [itemprop="articleBody"]')
        if not nodes:
            # NFL's newer renderer has semantic body paragraphs/lists without the older CMS classes.
            h=doc.h1;nodes=[]
            if h:
                for el in h.find_all_next(['h2','h3','p','ul','ol']):
                    if el.get_text(' ',strip=True)=='Related Content':break
                    nodes.append(el)
        body='\n'.join(n.get_text(' ',strip=True) for n in nodes)
    pub=data.get('datePublished')
    return dict(title=str(title).strip(),body=str(body or '').strip(),lines=block_lines(doc),
                published_utc=utc(pub).isoformat() if pub else None,document=doc)


BLOCKS=('p','li','h1','h2','h3','h4','h5','h6','div','tr','ul','ol','table','blockquote','section')


def block_lines(doc):
    """One line per rendered block (paragraph, list item, heading, <br>) of the article body.
    JSON-LD articleBody often joins blocks without separators ("...inactives.QB Andy Dalton"),
    which hides rows from a line-based list parser. Empty when the page has no body markup."""
    nodes=doc.select('.nfl-c-body-part--text, .d3-l-article__content, [itemprop="articleBody"]')
    if not nodes:return []
    nodes=[n for n in nodes if not any(p in nodes for p in n.parents)]
    lines=[]
    for node in nodes:
        copy=soup(str(node))
        for br in copy.find_all('br'):br.replace_with('\n')
        for el in copy.find_all(BLOCKS):
            el.insert(0,'\n');el.append('\n')
        lines+=[' '.join(x.split()) for x in copy.get_text().splitlines() if x.strip()]
    return lines


def parse_injury_report(text,team,event,index):
    """Read only this club's table for the selected regular-season week/opponent."""
    doc=soup(text);selected=doc.select_one('select option[selected]')
    if selected is None or not re.search(rf'/REG-{int(event["week"])}$',selected.get('value','')):
        raise ValueError('injury report does not identify the forecast week')
    containers=doc.select('.nfl-o-injury-report__container')
    expected={TEAMS[event[s]][0] for s in ('home','away')}
    found={c.select_one('.nfl-o-injury-report__club-name').get_text(' ',strip=True)
           for c in containers if c.select_one('.nfl-o-injury-report__club-name')}
    if not expected<=found:raise ValueError('injury report for both scheduled opponents not yet published')
    container=next((c for c in containers if c.select_one('.nfl-o-injury-report__club-name')
                    and c.select_one('.nfl-o-injury-report__club-name').get_text(' ',strip=True)==TEAMS[team][0]),None)
    table=container.find('table') if container else None
    if table is None:raise ValueError('club injury table missing')
    headers=[x.get_text(' ',strip=True) for x in table.select('thead th')]
    if not headers or headers[0]!='Player' or headers[-1]!='Game Status':raise ValueError('unknown injury table schema')
    from zoneinfo import ZoneInfo
    day=utc(event['kickoff_utc']).astimezone(ZoneInfo('America/New_York')).date()
    final=day-dt.timedelta(days=1 if day.weekday()==3 else 2)
    final_column=final.strftime('%a')
    if final_column not in headers:raise ValueError('injury table has no final practice-day column')
    final_index=headers.index(final_column);rows=[];issues=[];complete=True
    for tr in table.select('tbody tr'):
        cells=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
        if not cells:continue
        if len(cells)!=len(headers):raise ValueError('injury table row/header mismatch')
        status=cells[-1].upper();player=index.resolve(cells[0],team,allow_transfer=True)
        if status not in STATUSES:issues.append('unknown injury designation: '+status);continue
        # The CMS explicitly writes (-) when a previously listed player is no
        # longer on that day's report. An empty cell is an unpublished day.
        if not cells[final_index].strip() or cells[final_index].strip() in ('-','--'):complete=False
        if player is None:issues.append('unresolved injury player: '+cells[0]);continue
        rows.append(dict(gsis_id=player['gsis_id'],player=player['player'],position=player['position'],
                         status=STATUSES[status],practice=cells[final_index]))
    if not rows:complete=False
    return dict(rows=rows,complete=complete and not issues,issues=issues,final_date=final.isoformat())


def nickname(team):return TEAMS[team][0].split()[-1]


def bound_article(item,event,team,now):
    """News must be recent and belong to this team's current game week."""
    from zoneinfo import ZoneInfo
    pub=utc(item['published_utc']);ko=utc(event['kickoff_utc'])
    game_day=ko.astimezone(ZoneInfo('America/New_York')).date()
    # NFL Monday games belong to the preceding league week.
    monday=game_day-dt.timedelta(days=(game_day.weekday() if game_day.weekday()!=0 else 7))
    start=dt.datetime.combine(monday,dt.time(),ZoneInfo('America/New_York')).astimezone(UTC)
    return start<=pub<=now<ko


class InactiveIdentityMismatch(ValueError):
    """The article does not announce this team's list for this game (for example, a league bundle
    covering another kickoff). Any other parse failure concerns this team's own list."""


INACTIVE_POSITIONS=r'QB|RB|HB|FB|WR|TE|OL|OT|OG|IOL|LT|RT|LG|RG|C|G|T|DL|DE|DT|NT|IDL|EDGE|LB|OLB|ILB|MLB|CB|DB|NB|S|SAF|FS|SS|K|PK|P|LS'
INACTIVE_ROW=re.compile(r'^(?:\d+\s*[-.:)]?\s*)?(?:[-•*·–—]\s*)?('+INACTIVE_POSITIONS+r')\s*[:\-–—.,]?\s+(.+)$',re.I)
# A short line with no sentence ending is list-shaped; it must parse exactly or the list is not complete.
LIST_SHAPED=re.compile(r'^(?!.*[.!?]["\u201d\u2019]?$)(?:\S+\s+){0,7}\S+$')


def mentions_team_player(line,team,index):
    """Any exact alias of a current or transferred player inside a line, at word boundaries."""
    text=' '+norm(line)+' '
    return any(' '+key+' ' in text for key in index.names if key and len(key.split())>=2)


def embedded_row(line,team,index):
    """A position-prefixed exact player name inside a longer line: a list row glued to prose
    or to another row by text extraction ("...announced their inactives.QB Andy Dalton")."""
    for match in re.finditer(r'(?<![A-Za-z])(?:'+INACTIVE_POSITIONS+r')\s+((?:[A-Z][\w.\'\u2019-]*\s*){2,4})',line):
        words=match[1].split()
        if any(index.resolve(' '.join(words[:n]),team,allow_transfer=True) for n in range(len(words),1,-1)):return True
    return False


def parse_inactives(info,team,event,index):
    """A complete named list, never 'DNP', box-score participation, or an absent list."""
    from zoneinfo import ZoneInfo
    pub=info.get('published_utc')
    if not pub:raise ValueError('inactive article has no publication time')
    ko=utc(event['kickoff_utc']);stamp=utc(pub)
    if stamp.astimezone(ZoneInfo('America/New_York')).date()!=ko.astimezone(ZoneInfo('America/New_York')).date() or stamp>=ko:
        raise InactiveIdentityMismatch('inactive list is not a pregame publication for this game day')
    title=unescape(info['title']);body=unescape(info['body']);other=event['away'] if team==event['home'] else event['home']
    week=re.search(r'\bweek\s*(\d+)\b',title,re.I)
    if week and int(week[1])!=int(event['week']):raise InactiveIdentityMismatch('inactive article week mismatch')
    if not week and nickname(other).casefold() not in (title+'\n'+body[:5000]).casefold():raise InactiveIdentityMismatch('inactive article opponent missing')
    if 'inactiv' not in title.casefold() and not (info.get('source_team')==team and re.search(r'\binactives?\b',body,re.I)):
        raise InactiveIdentityMismatch('article is not an inactive announcement')
    lines=[unescape(s) for s in (info.get('lines') or [s.strip() for s in body.splitlines() if s.strip()])]
    headings={norm(name):key for key,(name,_) in TEAMS.items()}
    headings.update({norm(nickname(key)):key for key in TEAMS})
    section=None;listed=[]
    used_sections=any(norm(line) in headings for line in lines)
    # A league-wide article must name this team's section. A club article can be
    # a single list, but only when fetched from that club's verified feed.
    club_article=info.get('source_team')==team
    if not used_sections and not club_article:raise InactiveIdentityMismatch('inactive team section missing')
    if used_sections and not club_article and not any(headings.get(norm(line))==team for line in lines):
        raise InactiveIdentityMismatch('inactive team section missing')
    # Rows must form one contiguous block. Every list-shaped line that names a player or
    # carries a position prefix must resolve exactly; a skipped line would silently drop
    # an inactive player and leave a partial list marked complete.
    ended=False;team_sections=0;line_error=None;mentioned=set()
    try:
        for line in lines:
            heading=headings.get(norm(line))
            if heading:
                if listed and heading==team:raise ValueError('inactive team section repeated')
                if listed:ended=True
                section=heading;team_sections+=heading==team;continue
            if used_sections and section!=team:continue
            bare=index.resolve(re.sub(r'\s*\([^)]*\)\s*','',line).strip(' -–—:,•*·'),team,allow_transfer=True)
            if bare:mentioned.add(bare['gsis_id'])
            match=INACTIVE_ROW.match(line);player=None
            if match:
                name=re.sub(r'\s*\([^)]*\)\s*','',match[2]).strip(' -–—:,')
                player=index.resolve(name,team,allow_transfer=True) if len(name.split())>=2 else None
                if player is None and not LIST_SHAPED.match(line) and not mentions_team_player(line,team,index):match=None
                elif player is None:raise ValueError('unresolved inactive player: '+name)
            if match:
                if ended:raise ValueError('inactive list is fragmented by unparsed lines')
                listed.append(dict(gsis_id=player['gsis_id'],player=player['player'],position=player['position']))
                continue
            if LIST_SHAPED.match(line) and mentions_team_player(line,team,index):
                raise ValueError('unparsed inactive line: '+line[:80])
            if embedded_row(line,team,index):
                raise ValueError('inactive row joined to other text: '+line[:80])
            if listed:ended=True
        if used_sections and team_sections>1:raise ValueError('inactive team section repeated')
    except ValueError as exc:
        # A club page's bullets can flatten into bare names in the article text; only then may
        # the structured HTML list below stand in, and it must contain every bare name.
        if listed or not club_article or used_sections:raise
        line_error=exc
    if not listed and club_article:
        # Team articles often use HTML bullets without position prefixes.
        for ul in info['document'].select('.nfl-c-body-part--text ul, .d3-l-article__content ul, [itemprop="articleBody"] ul'):
            near=ul.find_previous(['p','h2','h3'])
            label=near.get_text(' ',strip=True) if near else ''
            if not re.search(r'inactiv',label,re.I) and nickname(team).casefold() not in label.casefold():continue
            names=[]
            for li in ul.find_all('li',recursive=False):
                text=li.get_text(' ',strip=True);row=INACTIVE_ROW.match(text)
                name=row[2] if row else text
                name=re.sub(r'\s*\([^)]*\)\s*','',name).strip(' -–—:,')
                player=index.resolve(name,team,allow_transfer=True)
                if player is None:raise ValueError('unresolved inactive player: '+name)
                names.append({k:player[k] for k in ('gsis_id','player','position')})
            if names:
                if not mentioned<={p['gsis_id'] for p in names}:raise ValueError('inactive bullets omit a listed player')
                listed=names;break
        if not listed and line_error is not None:raise line_error
    unique={p['gsis_id']:p for p in listed}
    if not 1<=len(unique)<=15:raise ValueError('no complete inactive list found')
    return dict(rows=list(unique.values()),complete=True,issues=[])


def news_facts(info,team,event,index):
    """Strict language rules; questions, conditional starts and proposed trades go to review."""
    title=info['title'];body=info['body'][:5000];text=title+'\n'+body
    if UNCERTAIN.search(title) or re.search(r'\breports?\b',title,re.I):
        return [],['unconfirmed or conditional news'] if RELEVANT.search(title) else []
    facts=[];issues=[]
    # A unique QB named in an explicit future start clause; first-team reps or practice are insufficient.
    phrases=[]
    for player in index.players.values():
        if player['position']!='QB' or player['team']!=team:continue
        aliases=player['aliases']+[player['player'].split()[-1]]
        for alias in aliases:
            escaped=re.escape(alias)
            pattern=rf'\b{escaped}\b[^.?!\n]{{0,45}}\b(?:will start|will be (?:the |\w+\x27s )?starting quarterback|named (?:the )?start(?:ing quarterback|er)|to start|set to start)\b'
            for match in re.finditer(pattern,text,re.I):
                sentence=re.split(r'[.?!\n]',text[max(0,match.start()-150):match.end()+120])
                clause=next((s for s in sentence if alias.casefold() in s.casefold() and re.search(r'\bstart',s,re.I)),match[0])
                if UNCERTAIN.search(clause) or '?' in title:continue
                # Negated or contrastive starts ("is not going to start", "won't start",
                # "will start instead of") are never positive facts; they go to review.
                if NEGATION.search(match[0]) or NEGATION.search(clause):
                    issues.append('negated or contrastive start statement');continue
                if re.search(r'\b(last (?:week|season)|previous|had been|was named|started)\b',clause,re.I):continue
                other=event['away'] if team==event['home'] else event['home']
                if not (nickname(other).casefold() in text.casefold() or re.search(r'\b(?:this (?:week|Thursday|Sunday|Monday)|tomorrow)\b',clause,re.I)):
                    continue
                if 'set to start' in match[0].lower() and not re.search(r'\b(announced|confirmed|named)\b',body,re.I):continue
                phrases.append(player)
    unique={p['gsis_id']:p for p in phrases}
    if len(unique)==1:
        p=next(iter(unique.values()));facts.append(dict(field='qb_starter',value=True,**{k:p[k] for k in ('gsis_id','player','position')}))
    elif len(unique)>1:issues.append('multiple confirmed starter candidates in article')
    # An explicit negative game designation may arrive before the table is updated.
    other=event['away'] if team==event['home'] else event['home']
    if nickname(other).casefold() in title.casefold() and re.search(r'\b(ruled out|will not play|will miss)\b',title,re.I):
        matched={p['gsis_id']:p for p in index.players.values() if p['team']==team and any(
            re.search(r'(?<!\w)'+re.escape(norm(a))+r'(?!\w)',norm(title)) for a in p['aliases'])}
        if len(matched)==1:
            p=next(iter(matched.values()));facts.append(dict(field='report_status',value='Out',**{k:p[k] for k in ('gsis_id','player','position')}))
        else:issues.append('medical announcement requires exact player resolution')
    # Signing FROM a practice squad can be an active-roster move; signing TO one is not.
    if re.search(r'\b(to (?:the |their )?practice squad|practice window|designated to return|could|expected|reports?)\b',title,re.I):return facts,issues
    movement=re.search(r'\b(signs?|signed|activate[sd]?|elevate[sd]?|waive[sd]?|release[sd]?)\b',title,re.I)
    if movement:
        additions=movement[1].lower().startswith(('sign','activat','elevat'))
        if additions and not re.search(r'\b(53.man|active roster|elevate[sd]?)\b',text[:1500],re.I):return facts,issues
        matches=[]
        for p in index.players.values():
            if any(norm(a) and re.search(r'(?<!\w)'+re.escape(norm(a))+r'(?!\w)',norm(title)) for a in p['aliases']):matches.append(p)
        unique={p['gsis_id']:p for p in matches}
        if len(unique)==1:
            p=next(iter(unique.values()))
            if additions or p['team']==team:
                facts.append(dict(field='eligible',value=additions,**{k:p[k] for k in ('gsis_id','player','position')}))
        elif not unique:issues.append('transaction player could not be resolved')
        else:issues.append('multiple transaction players require itemized confirmation')
    return facts,issues


def schedule_events(schedule,now):
    """Upcoming regular-season games only; never collect retroactive observations."""
    if hasattr(schedule,'to_dict'):schedule=schedule.to_dict('records')
    events={}
    from zoneinfo import ZoneInfo
    for r in schedule:
        if r.get('game_type','REG')!='REG':continue
        result=r.get('result')
        if result is not None and str(result) not in ('nan','<NA>','NaT',''):continue
        home=r.get('home_team',r.get('home'));away=r.get('away_team',r.get('away'))
        if home not in TEAMS or away not in TEAMS:continue
        ko=r.get('kickoff_utc',r.get('kickoff'))
        if ko is None:
            day=str(r.get('gameday',''))[:10];time=str(r.get('gametime',''))
            try:ko=dt.datetime.fromisoformat(day+'T'+time).replace(tzinfo=ZoneInfo('America/New_York'))
            except ValueError:continue
        try:ko=utc(ko)
        except (ValueError,TypeError):continue
        if not now<ko<=now+dt.timedelta(days=8):continue
        event=dict(game_id=r['game_id'],season=int(r['season']),week=int(r['week']),
                   home=home,away=away,kickoff_utc=ko.isoformat())
        for team in (home,away):
            # One current game per club; next week's report must not be mistaken for this week's.
            if team not in events or ko<utc(events[team]['kickoff_utc']):events[team]=event
    return events


def collection_ready(snapshot,asof,require_inactives=False):
    """Pure/stdlib validation of the source checks frozen inside a forecast."""
    try:
        if snapshot['policy']!=POLICY or snapshot['max_age_minutes']!=MAX_AGE_MINUTES:return False
        required=('news','report','inactives') if require_inactives else ('news','report')
        for kind in required:
            item=snapshot[kind];checked=utc(item['last_success_utc'])
            if kind=='news' and item.get('article_errors'):return False
            if not dt.timedelta(0)<=utc(asof)-checked<=dt.timedelta(minutes=MAX_AGE_MINUTES):return False
            if kind!='news' and (item.get('complete') is not True or not re.fullmatch(r'[a-f0-9]{64}',item.get('source_capture_sha256',''))):return False
        return True
    except (KeyError,ValueError,TypeError):return False


def refresh(data,schedule,players,now=None,fetcher=fetch,force=False):
    """Collect every club's news and current game's reports; persist facts before using them.

    The caller serializes writes (the build and collector workflows share site-build).
    Network/parser failure updates health; it never writes a fabricated empty report.
    Unchanged semantic evidence retains its first-capture time, even on revalidation.
    """
    data=Path(data);data.mkdir(parents=True,exist_ok=True)
    now=utc(now or dt.datetime.now(UTC));events=schedule_events(schedule,now)
    index=players if isinstance(players,PlayerIndex) else PlayerIndex(players)
    if not index.players:raise ValueError('no GSIS player names available for collection')
    state_path=data/STATE
    state=json.loads(state_path.read_text()) if state_path.exists() else {}
    if state.get('policy')!=POLICY:state={}
    state.update(policy=POLICY,max_age_minutes=MAX_AGE_MINUTES)
    teams=state.setdefault('teams',{});articles=state.setdefault('articles',{})
    sources=read(data/SOURCES);latest_sources={}
    for r in sources:latest_sources[(r['kind'],r['team'],r['game_id'],r['url'])]=r
    observations=read(data/AUTO);fact_keys={digest(r) for r in observations}
    news=read(data/NEWS);news_keys={(r['team'],r['url'],r['published_utc']) for r in news}
    reviews=read(data/REVIEW);review_keys={r['review_sha256'] for r in reviews}
    new_sources=[];new_facts=[];new_news=[];new_reviews=[]

    def due(health):
        try:return force or bool(health.get('error')) or now-utc(health['last_success_utc'])>=dt.timedelta(minutes=NEWS_POLL_MINUTES)
        except (KeyError,ValueError,TypeError):return True

    def failure(health,error):
        health.update(last_attempt_utc=now.isoformat(),error=str(error)[:250])

    def success(health,response,**values):
        health.update(last_attempt_utc=response['captured_utc'],last_success_utc=response['captured_utc'],error=None,**values)

    def capture(kind,team,event,response,parsed,published=None):
        basis='source_publication' if published else 'first_capture'
        payload=dict(policy=POLICY,kind=kind,team=team,game_id=event['game_id'],url=response['url'],
                     source_published_utc=published,publication_time_basis=basis,parsed=parsed)
        semantic=digest(payload)
        key=(kind,team,event['game_id'],response['url']);previous=latest_sources.get(key)
        if previous and previous['semantic_sha256']==semantic:return previous
        record=dict(payload,semantic_sha256=semantic,captured_utc=response['captured_utc'],body_sha256=response['body_sha256'])
        record['source_capture_sha256']=digest(record)
        latest_sources[key]=record;new_sources.append(record)
        return record

    def facts(source,values):
        stamp=source['source_published_utc'] or source['captured_utc']
        for value in values:
            r=dict(game_id=source['game_id'],team=source['team'],source_url=source['url'],
                   published_utc=stamp,observed_utc=source['captured_utc'],effective_utc=stamp,status='confirmed',
                   source_kind=source['kind'],source_capture_sha256=source['source_capture_sha256'],
                   publication_time_basis=source['publication_time_basis'],**value)
            h=digest(r)
            if h not in fact_keys:new_facts.append(r);fact_keys.add(h)

    def review(team,event,url,issues):
        for issue in issues:
            payload=dict(policy=POLICY,team=team,game_id=event['game_id'],source_url=url,issue=issue)
            h=digest(payload)
            if h not in review_keys:
                new_reviews.append(dict(payload,first_observed_utc=now.isoformat(),review_sha256=h));review_keys.add(h)

    def requests_batch(requests):
        # Read-only requests can run together; parse, append and state updates are serialized below.
        out={}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            jobs={pool.submit(fetcher,url):url for url in requests}
            for job in concurrent.futures.as_completed(jobs):
                url=jobs[job]
                try:out[url]=job.result()
                except Exception as exc:out[url]=exc
        return out

    requests={};feeds={};reports={}
    for team,(_,host) in TEAMS.items():
        health=teams.setdefault(team,{});health.setdefault('news',{})
        if due(health['news']):
            url='https://www.'+host+'/rss/news';requests[url]=None;feeds[team]=url
        event=events.get(team)
        if event:
            if health.get('game_id')!=event['game_id']:
                health.update(game_id=event['game_id'],kickoff_utc=event['kickoff_utc'],report={},inactives={})
                health['news']['article_errors']=[]
            if due(health['report']):
                url='https://www.'+host+'/team/injury-report/';requests[url]=None;reports[team]=url
        else:
            health.update(game_id=None,report={},inactives={})
    # The NFL hub discovers league-wide official lists when a team's feed is slow.
    near={t:e for t,e in events.items() if utc(e['kickoff_utc'])-now<=dt.timedelta(hours=4)}
    if near:requests[NFL+'/inactives/']=None
    responses=requests_batch(requests)
    article_jobs={}
    for team,url in feeds.items():
        health=teams[team]['news'];response=responses[url]
        try:
            if isinstance(response,Exception):raise response
            items=rss_items(response['text'],url)
            for item in items:
                if utc(item['published_utc'])>utc(response['captured_utc']):continue
                key=(team,item['url'],item['published_utc'])
                if key not in news_keys:
                    # Reference metadata only. Full article prose is not copied into the repository.
                    new_news.append(dict(team=team,url=item['url'],title=' '.join(item['title'].split()[:25]),
                        published_utc=item['published_utc'],first_observed_utc=response['captured_utc']))
                    news_keys.add(key)
                event=events.get(team)
                if event and bound_article(item,event,team,now) and (RELEVANT.search(item['title']) or 'inactiv' in item['url']):
                    if due(articles.get(item['url'],{})):
                        article_jobs.setdefault(item['url'],[]).append((team,event,item,True))
            success(health,response,items=len(items))
        except Exception as exc:failure(health,exc)
    for team,url in reports.items():
        response=responses[url];health=teams[team]['report'];event=events[team]
        try:
            if isinstance(response,Exception):raise response
            parsed=parse_injury_report(response['text'],team,event,index)
            from zoneinfo import ZoneInfo
            if utc(response['captured_utc']).astimezone(ZoneInfo('America/New_York')).date()<dt.date.fromisoformat(parsed['final_date']):parsed['complete']=False
            source=capture('official_injury_report',team,event,response,parsed)
            values=[dict(field='report_status',value=p['status'],**{k:p[k] for k in ('gsis_id','player','position')})
                    for p in parsed['rows'] if parsed['complete'] or p['status'] in ('Out','Doubtful','Questionable')]
            facts(source,values+[dict(field='report_complete',value=parsed['complete'])])
            success(health,response,complete=parsed['complete'],source_capture_sha256=source['source_capture_sha256'],issues=parsed['issues'])
            review(team,event,url,parsed['issues'])
        except Exception as exc:failure(health,exc)
    hub=responses.get(NFL+'/inactives/')
    if isinstance(hub,dict):
        for link in soup(hub['text']).select('a[href]'):
            url=urllib.parse.urljoin(NFL,link['href']).split('#')[0].split('?')[0]
            if urllib.parse.urlsplit(url).hostname!='www.nfl.com' or '/news/' not in url or 'inactiv' not in url:continue
            week=re.search(r'week-(\d+)-',url)
            for team,event in near.items():
                if week and int(week[1])==event['week'] and due(articles.get(url,{})):
                    article_jobs.setdefault(url,[]).append((team,event,None,False))
    for source in sources:
        team=source['team'];event=near.get(team)
        if (event and source['game_id']==event['game_id'] and source['kind']=='official_inactives'
                and due(articles.get(source['url'],{}))):
            url=source['url'];club=urllib.parse.urlsplit(url).hostname.removeprefix('www.')==TEAMS[team][1]
            job=(team,event,dict(published_utc=source['source_published_utc']),club)
            if not any(j[0]==team for j in article_jobs.get(url,[])):article_jobs.setdefault(url,[]).append(job)
    downloaded=requests_batch(article_jobs)
    article_errors={team:[] for team in events}
    inactive_failed=set()
    for url,jobs in article_jobs.items():
        response=downloaded[url];health=articles.setdefault(url,{})
        try:
            if isinstance(response,Exception):raise response
            info=article(response['text'])
            if not info['body']:raise ValueError('article body missing')
            # Do not mark failed parsers as successful cached analyses.
            success(health,response)
            for team,event,item,club in jobs:
                info['source_team']=team if club else None
                pub=info.get('published_utc') or (item or {}).get('published_utc')
                if not pub or utc(pub)>utc(response['captured_utc']):continue
                info['published_utc']=pub
                if not bound_article(info,event,team,now):continue
                if 'inactiv' in info['title'].casefold() or (club and re.search(r'\binactives?\b',info['body'],re.I)):
                    try:
                        parsed=parse_inactives(info,team,event,index)
                        source=capture('official_inactives',team,event,response,parsed,pub)
                        facts(source,[dict(field='eligible',value=False,**p) for p in parsed['rows']]
                              +[dict(field='inactives_complete',value=True)])
                        if team not in inactive_failed:
                            success(teams[team]['inactives'],response,complete=True,url=url,
                                    source_capture_sha256=source['source_capture_sha256'])
                    except ValueError as exc:
                        # A bundle may contain other kickoffs; only this team's failed list is reviewed.
                        review(team,event,url,[str(exc)])
                        # A failed revision of the page that supplied the accepted list never inherits
                        # it. Any other failure of an NFL.com list covering this game withdraws completeness
                        # too, and outranks another page's success in the same refresh. Club articles
                        # are often prose or both-team lists in varied formats (2026 week 8: 13 of 20
                        # failed to parse); their failures are reviewed but cannot withdraw a list
                        # accepted from another page.
                        h=teams[team]['inactives']
                        if h.get('url')==url or not (club or isinstance(exc,InactiveIdentityMismatch)):
                            failure(h,exc);h['complete']=False;inactive_failed.add(team)
                if club:
                    values,issues=news_facts(info,team,event,index)
                    if values:
                        source=capture('official_team_news',team,event,response,dict(facts=values),pub);facts(source,values)
                    review(team,event,url,issues)
        except Exception as exc:
            failure(health,exc)
            for team,_,_,club in jobs:
                if club:article_errors[team].append(url)
    for team,errors in article_errors.items():
        if team in feeds and teams[team]['news'].get('error') is None:teams[team]['news']['article_errors']=sorted(set(errors))
    # A cached inactive article is revalidated at each forced pre-lock refresh,
    # including when its headline has fallen off the RSS feed/hub.
    for team,event in near.items():
        h=teams[team]['inactives']
        if not h.get('last_attempt_utc'):h.update(last_attempt_utc=now.isoformat(),error='official inactive list not found')
    append(data/SOURCES,new_sources);append(data/AUTO,new_facts)
    append(data/NEWS,new_news);append(data/REVIEW,new_reviews)
    # Atomic replace for operational health only; source/fact/news/review evidence is never rewritten.
    state['updated_utc']=max([now]+[utc(h['last_attempt_utc']) for h in list(articles.values())+
        [item for team in teams.values() for item in (team['news'],team['report'],team['inactives'])]
        if h.get('last_attempt_utc')]).isoformat()
    temporary=state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');temporary.replace(state_path)
    validate_store(data)
    return state


def team_snapshot(state,team,game_id):
    h=state.get('teams',{}).get(team,{})
    return dict(policy=POLICY,max_age_minutes=MAX_AGE_MINUTES,team=team,game_id=game_id,
                **{k:dict(h.get(k,{})) if h.get('game_id')==game_id or k=='news' else {}
                   for k in ('news','report','inactives')})


def validate_store(data):
    """Verify content hashes and automatic fact-to-source links without third-party imports."""
    data=Path(data);by_hash={}
    for source in read(data/SOURCES):
        h=source['source_capture_sha256'];payload={k:v for k,v in source.items() if k!='source_capture_sha256'}
        if digest(payload)!=h or h in by_hash:raise ValueError('availability source hash mismatch/duplicate')
        semantic={k:source[k] for k in ('policy','kind','team','game_id','url','source_published_utc','publication_time_basis','parsed')}
        if digest(semantic)!=source['semantic_sha256']:raise ValueError('availability source semantic hash mismatch')
        if source['policy']!=POLICY or source['team'] not in TEAMS:raise ValueError('unknown automatic source identity')
        url=urllib.parse.urlsplit(source['url']);host=url.hostname.removeprefix('www.') if url.hostname else ''
        allowed={TEAMS[source['team']][1]}
        if source['kind']=='official_inactives':allowed.add('nfl.com')
        if url.scheme!='https' or url.username or url.password or host not in allowed:raise ValueError('automatic source is not an official host')
        if source['publication_time_basis']!=('source_publication' if source['source_published_utc'] else 'first_capture'):
            raise ValueError('source publication time basis mismatch')
        if not re.fullmatch(r'[a-f0-9]{64}',source['body_sha256']):raise ValueError('invalid source body hash')
        utc(source['captured_utc'])
        by_hash[h]=source
    for fact in read(data/AUTO):
        source=by_hash.get(fact.get('source_capture_sha256'))
        if source is None:raise ValueError('automatic observation has no saved source')
        if any(fact[k]!=source[s] for k,s in [('team','team'),('game_id','game_id'),('source_url','url'),('source_kind','kind'),('observed_utc','captured_utc'),('publication_time_basis','publication_time_basis')]):
            raise ValueError('automatic observation differs from saved source')
        if fact['published_utc']!=(source['source_published_utc'] or source['captured_utc']):raise ValueError('automatic publication time changed')
        if utc(fact['published_utc'])>utc(fact['observed_utc']) or fact['effective_utc']!=fact['published_utc']:raise ValueError('automatic observation time mismatch')
        parsed=source['parsed'];field=fact['field'];value=fact['value']
        if field in ('report_complete','inactives_complete'):
            valid=value==parsed.get('complete') and source['kind']=={'report_complete':'official_injury_report','inactives_complete':'official_inactives'}[field]
        elif source['kind']=='official_team_news':
            valid=any(all(fact.get(k)==v for k,v in row.items()) for row in parsed.get('facts',[]))
        else:
            rows=[r for r in parsed.get('rows',[]) if r['gsis_id']==fact.get('gsis_id')]
            valid=len(rows)==1 and all(fact.get(k)==rows[0][k] for k in ('player','position')) and ((field=='report_status' and value==rows[0]['status'] and source['kind']=='official_injury_report')
                                    or (field=='eligible' and value is False and source['kind']=='official_inactives'))
        if not valid:raise ValueError('automatic fact not supported by parsed evidence')
    # Ensure every journal is valid JSON, even before any facts are emitted.
    read(data/NEWS);read(data/REVIEW)
    return dict(sources=len(by_hash),observations=len(read(data/AUTO)))


def main(argv=None):
    import argparse
    import os
    import nflreadpy as nfl
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default=os.environ.get('NFL_STATE_DIR','data'))
    p.add_argument('--season',type=int,default=None)
    p.add_argument('--force',action='store_true')
    args=p.parse_args(argv);now=dt.datetime.now(UTC)
    season=args.season or (now.year if now.month>=8 else now.year-1)
    schedule=nfl.load_schedules(season).to_pandas()
    roster=nfl.load_rosters_weekly(season).to_pandas()
    roster['team']=roster.team.replace({'LAR':'LA','JAC':'JAX','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'})
    state=refresh(args.data,schedule,roster,now=now,force=args.force)
    def fresh(h):
        try:return not h['news'].get('article_errors') and dt.timedelta(0)<=dt.datetime.now(UTC)-utc(h['news']['last_success_utc'])<=dt.timedelta(minutes=MAX_AGE_MINUTES)
        except (KeyError,ValueError):return False
    count=sum(fresh(h) for h in state['teams'].values())
    print(json.dumps(dict(teams=len(state['teams']),news_fresh=count,
        pending_games=len({h.get('game_id') for h in state['teams'].values()}-{None}),**validate_store(args.data)),sort_keys=True))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        lines=['Official availability collection','',f'Fresh team news: {count}/32. Unpublished reports remain incomplete.','',
               '| Team | News | Injury report | Inactives |','|---|---|---|---|']
        for team,h in sorted(state['teams'].items()):
            cells=[team,'fresh' if fresh(h) else 'stale or unavailable']
            for kind in ('report','inactives'):
                item=h[kind]
                cells.append('no upcoming game' if not h.get('game_id') else 'complete' if item.get('complete') else 'pending')
            lines.append('| '+' | '.join(cells)+' |')
        with Path(summary).open('a') as out:out.write('\n'.join(lines)+'\n')
    return 0 if count==32 else 1


if __name__=='__main__':raise SystemExit(main())
