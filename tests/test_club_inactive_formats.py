"""Club-site inactive articles in the formats clubs actually published in 2026 week 8.

Each fixture keeps the markup and list rows of a real page (player names and positions are
facts); article prose is replaced by short placeholders. The pages were fetched from the
clubs' official RSS feeds on 2026-11-04, and each fixture names its source URL.
Probe of 20 club pages: 7 parse exactly (every row checked by hand against the page), 13
are rejected. None is accepted with a player missing or the opponent's players merged in.
"""
import datetime as dt
import json

import pytest

import availability_collect as c

UTC = dt.timezone.utc


def index(rows):
    return c.PlayerIndex([dict(gsis_id=f'00-{i:07d}', full_name=name, position=pos, team=team,
                               season=2026, week=7, status='ACT')
                          for i, (team, pos, name) in enumerate(rows, 1)])


def event(home, away, kickoff, week=8):
    return dict(game_id=f'2026_{week:02d}_{away}_{home}', season=2026, week=week, home=home, away=away,
                kickoff_utc=kickoff.isoformat())


def page(title, ld_body, blocks, published, team):
    """A club CMS page: JSON-LD articleBody plus nfl-c-body-part blocks."""
    parts = ''.join(f'<div class="nfl-c-body-part nfl-c-body-part--text">{b}</div>' for b in blocks)
    text = ('<h1>' + title + '</h1><script type="application/ld+json">'
            + json.dumps({'@type': 'NewsArticle', 'headline': title, 'articleBody': ld_body,
                          'datePublished': published.isoformat()}) + '</script>' + parts)
    info = c.article(text)
    info['source_team'] = team
    return info


def ids(parsed, idx):
    return sorted(idx.players[r['gsis_id']]['player'] for r in parsed['rows'])


# https://www.atlantafalcons.com/news/atlanta-falcons-week-8-inactives-vs-tampa-bay-buccaneers
# The JSON-LD body joins the intro paragraph to the first row:
# "...announced their full list of inactives.QB Andy Dalton (3rd QB)".
ATL_ROWS = ['QB Andy Dalton (3rd QB)', 'QB Jack Strand', 'LB Divine Deablo', 'RB Brian Robinson',
            'DB Billy Bowman', 'DB Robert Longerbeam', 'DE Drake Jackson']
ATL = [('ATL', 'QB', 'Andy Dalton'), ('ATL', 'QB', 'Jack Strand'), ('ATL', 'LB', 'Divine Deablo'),
       ('ATL', 'RB', 'Brian Robinson'), ('ATL', 'DB', 'Billy Bowman'), ('ATL', 'DB', 'Robert Longerbeam'),
       ('ATL', 'DE', 'Drake Jackson'), ('TB', 'WR', 'Emeka Egbuka')]
ATL_KO = dt.datetime(2026, 11, 1, 17, 0, tzinfo=UTC)


def atl_page(with_markup=True):
    intro = 'The Falcons announced their full list of inactives against the Buccaneers.'
    ld = intro + '\n'.join(ATL_ROWS) + '\n\nPlaceholder closing paragraph.'
    blocks = [f'<p>{intro}</p>', '<ul>' + ''.join(f'<li>{r}</li>' for r in ATL_ROWS) + '</ul>',
              '<p>Placeholder closing paragraph.</p>'] if with_markup else []
    return page('Atlanta Falcons Week 8 inactives vs. Tampa Bay Buccaneers', ld, blocks,
                ATL_KO - dt.timedelta(minutes=10), 'ATL')


def test_glued_json_ld_rows_are_read_from_the_page_blocks():
    idx = index(ATL)
    parsed = c.parse_inactives(atl_page(), 'ATL', event('ATL', 'TB', ATL_KO), idx)
    # Before block lines, this page parsed as complete with 6 rows: the emergency QB was dropped.
    assert len(parsed['rows']) == 7 and 'Andy Dalton' in ids(parsed, idx)


def test_glued_row_without_page_markup_is_rejected_not_dropped():
    with pytest.raises(ValueError, match='joined to other text'):
        c.parse_inactives(atl_page(with_markup=False), 'ATL', event('ATL', 'TB', ATL_KO), index(ATL))


# https://www.tennesseetitans.com/news/game-inactives-week-8-titans-at-bengals
# Jersey-numbered rows for both teams under full club-name headings.
TEN_BLOCKS = ['<p>Here are the Week 8 Inactives for both teams:</p>', '<p>TENNESSEE TITANS</p>',
              '<p>2 RB Tyjae Spears<br>3 P Tommy Townsend<br>14 WR Carnell Tate<br>42 CB Jaylon Jones<br>'
              '78 T Brandon Crenshaw-Dickson<br>86 TE Kylen Granson<br>96 DT Jackie Marshall</p>',
              '<p>CINCINNATI BENGALS</p>',
              '<p>29 S Kyle Dugger<br>65 C Connor Lew<br>77 OT Myles Hinton<br>82 WR Mitch Tinsley<br>'
              '96 DT Landon Robinson</p>']
TEN = [('TEN', 'RB', 'Tyjae Spears'), ('TEN', 'P', 'Tommy Townsend'), ('TEN', 'WR', 'Carnell Tate'),
       ('TEN', 'CB', 'Jaylon Jones'), ('TEN', 'T', 'Brandon Crenshaw-Dickson'), ('TEN', 'TE', 'Kylen Granson'),
       ('TEN', 'DT', 'Jackie Marshall'), ('CIN', 'S', 'Kyle Dugger'), ('CIN', 'C', 'Connor Lew'),
       ('CIN', 'OT', 'Myles Hinton'), ('CIN', 'WR', 'Mitch Tinsley'), ('CIN', 'DT', 'Landon Robinson')]


def test_numbered_two_team_page_gives_each_team_only_its_own_section():
    idx = index(TEN)
    ev = event('CIN', 'TEN', ATL_KO)
    info = page('Game Inactives | Week 8 Titans at Bengals', 'Placeholder.', TEN_BLOCKS,
                ATL_KO - dt.timedelta(minutes=30), 'TEN')
    ten = c.parse_inactives(info, 'TEN', ev, idx)
    assert len(ten['rows']) == 7 and 'Kyle Dugger' not in ids(ten, idx)
    info['source_team'] = 'CIN'
    assert ids(c.parse_inactives(info, 'CIN', ev, idx), idx) == sorted(
        ['Kyle Dugger', 'Connor Lew', 'Myles Hinton', 'Mitch Tinsley', 'Landon Robinson'])


# https://www.clevelandbrowns.com/news/browns-announce-inactives-for-week-8-vs-the-steelers
# The emergency QB row has no position prefix. The pre-fix parser returned the other 5 as complete.
def test_bare_name_row_rejects_the_list_instead_of_dropping_the_player():
    idx = index([('CLE', 'QB', 'Dillon Gabriel'), ('CLE', 'QB', 'Taylen Green'), ('CLE', 'LB', 'Justin Jefferson'),
                 ('CLE', 'CB', 'Noah Igbinoghene'), ('CLE', 'RB', 'Audric Estime'), ('CLE', 'C', 'Parker Brailsford'),
                 ('PIT', 'QB', 'Will Howard')])
    info = page('Browns announce inactives for Week 8 vs. the Steelers', 'Placeholder.',
                ['<p>The Browns announced their inactives for Week 8 against the Steelers.</p><p>INACTIVES</p>',
                 '<p>Dillon Gabriel (3QB)<br>QB Taylen Green<br>LB Justin Jefferson<br>CB Noah Igbinoghene<br>'
                 'RB Audric Estime<br>C Parker Brailsford</p>'],
                ATL_KO - dt.timedelta(minutes=30), 'CLE')
    with pytest.raises(ValueError, match='Dillon Gabriel'):
        c.parse_inactives(info, 'CLE', event('PIT', 'CLE', ATL_KO), idx)


# https://www.panthers.com/news/week-8-inactives-at-green-bay-panthers-down-three-starters-for-packers
# "PANTHERS INACTIVES" / "PACKERS INACTIVES" are not section headings the parser knows, so the
# Packers' rows would follow the Panthers' rows. The pre-fix parser returned all 13 as Carolina's.
def test_unrecognised_two_team_headings_never_merge_the_opponents_list():
    kickoff = dt.datetime(2026, 10, 30, 0, 15, tzinfo=UTC)
    car = ["TE Ja'Tavion Sanders", 'OLB Jaelan Phillips', 'QB Haynes King (emergency third QB)', 'RB AJ Dillon',
           'G Damien Lewis', 'G Torricelli Simpkins', 'DT Bobby Brown']
    gb = ['TE Jonnu Smith', 'RB Kaleb Johnson', 'LB Zaire Franklin', 'G Donovan Jennings', 'C Sean Rhyan',
          'G Travis Glover']
    players = ([('CAR', r.split()[0], ' '.join(w for w in r.split()[1:] if not w.startswith('(') and ')' not in w and w != 'emergency' and w != 'third'))
                for r in car] + [('GB', r.split()[0], ' '.join(r.split()[1:])) for r in gb])
    info = page('Week 8 Inactives at Green Bay: Panthers down three starters for Packers', 'Placeholder.',
                ['<p>PANTHERS INACTIVES</p>', '<ul>' + ''.join(f'<li>{r}</li>' for r in car) + '</ul>',
                 '<p>PACKERS INACTIVES</p>', '<ul>' + ''.join(f'<li>{r}</li>' for r in gb) + '</ul>'],
                kickoff - dt.timedelta(minutes=90), 'CAR')
    with pytest.raises(ValueError):
        c.parse_inactives(info, 'CAR', event('GB', 'CAR', kickoff), index(players))


# https://www.baltimoreravens.com/news/ravens-bills-inactives-andrew-vorhees--start-right-guard-week-8
# Prose only: the article names some inactives in sentences but publishes no list.
def test_prose_only_club_article_is_not_a_list():
    idx = index([('BAL', 'G', 'Andrew Vorhees'), ('BAL', 'S', 'Jaylinn Hawkins'), ('BUF', 'WR', 'Moore Placeholder')])
    info = page('Andrew Vorhees Set to Start vs. Bills', 'Placeholder text naming the inactives.',
                ["<p>Andrew Vorhees is active for Sunday's game against the Buffalo Bills.</p>",
                 '<p>Starting safety Jaylinn Hawkins was ruled out on Friday and is inactive.</p>'],
                ATL_KO - dt.timedelta(minutes=30), 'BAL')
    with pytest.raises(ValueError, match='no complete inactive list'):
        c.parse_inactives(info, 'BAL', event('BAL', 'BUF', ATL_KO), idx)
