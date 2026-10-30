"""Public historical calibration, using completed regular-season weeks only.

This is an aggregate reporting view. It never changes forecasts, annual maps,
ATS selections, snapshots or the forward ledger.
"""
from html import escape

import numpy as np
import pandas as pd

import fixed_bands
import nfl_model as m

FIRST_SEASON = 2023
PROB_CUTS = [.2, .3, .4, .5, .6, .7, .8]
PROB_LABELS = ['0–<20%', '20–<30%', '30–<40%', '40–<50%',
               '50–<60%', '60–<70%', '70–<80%', '80–100%']
SPREAD_CUTS = [3., 7., 10.]
SPREAD_LABELS = ['<3 points', '3–<7 points', '7–<10 points', '10+ points']
EXPORT_COLUMNS = ['season', 'view', 'band', 'side', 'observations', 'decided',
                  'wins', 'losses', 'pushes', 'ties', 'implied_wp', 'actual_wp',
                  'gap_pp', 'se_pp', 'implied_mov', 'median_mov', 'cover_rate',
                  'units', 'roi']


def history(latest):
    """One reconstructed row per game; an incomplete board week is excluded.

    The model's historical export ends before its current board week. Once all
    board games are final, include that week immediately rather than waiting
    for the next week's board. Retain existing historical forecasts on overlap.
    """
    if latest is None:
        return pd.DataFrame()
    manifest = latest.get('manifest', {})
    current = int(manifest.get('season', FIRST_SEASON))
    week = int(manifest.get('week', 18))
    hist = latest.get('fixed_band_ledger', pd.DataFrame()).copy()
    board = latest.get('board', pd.DataFrame()).copy()
    if len(hist) and hist.game_id.duplicated().any():
        raise ValueError('Duplicate historical calibration game')
    if len(board):
        if board.game_id.duplicated().any():
            raise ValueError('Duplicate calibration board game')
        completed = []
        for (year, wk), group in board.groupby(['season', 'week']):
            if not pd.to_numeric(group.result, errors='coerce').notna().all():
                if len(hist):
                    hist = hist.loc[~(hist.season.eq(year) & hist.week.eq(wk))]
            else:
                completed.append(group)
        if completed:
            hist = pd.concat([hist, *completed], ignore_index=True)
            hist = hist.drop_duplicates('game_id', keep='first')
    required = ['game_id', 'season', 'week', 'result', 'model_wp', 'market_wp']
    if hist.empty or not set(required).issubset(hist):
        return pd.DataFrame()
    for col in ['season', 'week', 'result', 'model_wp', 'market_wp',
                'spread_line', 'fixed_band_spread']:
        hist[col] = pd.to_numeric(hist[col], errors='coerce') if col in hist else np.nan
    valid = (hist.season.ge(FIRST_SEASON) & hist.season.le(current)
             & (hist.season.lt(current) | hist.week.le(week))
             & np.isfinite(hist.result) & hist.model_wp.between(0., 1.)
             & hist.market_wp.between(0., 1.))
    return hist.loc[valid].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def standard_error(values, game_ids):
    """Game-cluster SE; paired home/away sides are not independent samples."""
    values = np.asarray(values, float)
    if len(values) < 2:
        return None
    sums = pd.Series(values - values.mean()).groupby(np.asarray(game_ids)).sum()
    groups = len(sums)
    if groups < 2:
        return None
    return float(np.sqrt(groups / (groups - 1) * np.square(sums).sum()) / len(values))


def wp_rows(frame, column, view):
    sides = []
    for label, sign in [('home', 1), ('away', -1)]:
        sides.append(pd.DataFrame({'game_id': frame.game_id, 'side': label,
            'probability': frame[column] if sign == 1 else 1 - frame[column],
            'mov': sign * frame.result}))
    sides = pd.concat(sides, ignore_index=True)
    # Keep complements such as 1-.8 at the exact 20% boundary despite float noise.
    sides['band_number'] = np.digitize(np.round(sides.probability, 12), PROB_CUTS)
    rows = []
    for k, band in enumerate(PROB_LABELS):
        for side in ['home', 'away', 'both']:
            group = sides.loc[sides.band_number.eq(k)]
            if side != 'both':
                group = group.loc[group.side.eq(side)]
            decided = group.loc[group.mov.ne(0)]
            n = len(decided)
            wins = int(decided.mov.gt(0).sum())
            actual = wins / n if n else None
            implied = float(decided.probability.mean()) if n else None
            residual = decided.mov.gt(0).astype(float) - decided.probability
            se = standard_error(residual, decided.game_id)
            rows.append(dict(view=view, band=band, side=side, observations=len(group),
                decided=n, wins=wins, losses=n-wins, pushes=0,
                ties=int(group.mov.eq(0).sum()), implied_wp=implied, actual_wp=actual,
                gap_pp=100 * (actual-implied) if n else None,
                se_pp=100 * se if se is not None else None,
                implied_mov=None, median_mov=float(group.mov.median()) if len(group) else None,
                cover_rate=None, units=None, roi=None))
    return rows


def ats_rows(frame, model, view):
    # Identical eligible games and market-spread bands in both ATS views.
    valid = (np.isfinite(frame.spread_line) & frame.spread_line.ne(0)
             & np.isfinite(frame.fixed_band_spread))
    data = frame.loc[valid].copy()
    side = (fixed_bands.pick(data.fixed_band_spread, data.spread_line) if model
            else np.sign(data.spread_line.to_numpy()))
    data['mov'] = side * data.result
    data['implied_mov'] = side * (data.fixed_band_spread if model else data.spread_line)
    data['cover_margin'] = side * (data.result - data.spread_line)
    data['band_number'] = np.digitize(data.spread_line.abs(), SPREAD_CUTS)
    rows = []
    for k, band in enumerate(SPREAD_LABELS):
        group = data.loc[data.band_number.eq(k)]
        n = len(group)
        won = group.cover_margin.gt(fixed_bands.EPS)
        lost = group.cover_margin.lt(-fixed_bands.EPS)
        w, losses = int(won.sum()), int(lost.sum())
        decided = group.loc[won | lost]
        se = standard_error(decided.cover_margin.gt(0).astype(float), decided.game_id)
        units = w / 1.1 - losses
        rows.append(dict(view=view, band=band, side='selected', observations=n,
            decided=w+losses, wins=w, losses=losses, pushes=n-w-losses,
            ties=int(group.result.eq(0).sum()), implied_wp=None, actual_wp=None,
            gap_pp=None, se_pp=100 * se if se is not None else None,
            implied_mov=float(group.implied_mov.mean()) if n else None,
            median_mov=float(group.mov.median()) if n else None,
            cover_rate=w/(w+losses) if w+losses else None,
            units=units if n else None, roi=units/n if n else None))
    return rows


def panel(frame, season):
    binary = frame.loc[frame.result.ne(0)]
    y = binary.result.gt(0).to_numpy(float)
    def log_loss(column):
        p = np.clip(binary[column].to_numpy(float), 1e-12, 1-1e-12)
        return float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean()) if len(y) else None
    rows = (wp_rows(frame, 'market_wp', 'market_wp')
            + wp_rows(frame, 'model_wp', 'model_wp')
            + ats_rows(frame, False, 'market_ats')
            + ats_rows(frame, True, 'model_ats'))
    return dict(season=season, games=len(frame), binary_games=len(binary),
        ties=int(frame.result.eq(0).sum()), market_log_loss=log_loss('market_wp'),
        model_log_loss=log_loss('model_wp'), rows=rows)


def build(latest):
    frame = history(latest)
    if frame.empty:
        return dict(panels=[], coverage={}, current_season=int(
            (latest or {}).get('manifest', {}).get('season', FIRST_SEASON)))
    years = sorted(frame.season.astype(int).unique())
    panels = [panel(frame, 'all')]
    panels += [panel(frame.loc[frame.season.eq(year)], str(year)) for year in reversed(years)]
    return dict(panels=panels, current_season=int(latest['manifest']['season']),
                coverage={int(y): int(frame.loc[frame.season.eq(y), 'week'].max()) for y in years})


def export(pack):
    return pd.DataFrame([dict(season=p['season'], **row)
                         for p in pack['panels'] for row in p['rows']], columns=EXPORT_COLUMNS)


def number(value, digits=1, signed=False, suffix=''):
    if value is None or not np.isfinite(value):
        return '—'
    sign = '+' if signed else ''
    return (f'{value:{sign}.{digits}f}' + suffix).replace('-', '−')


def percentage(value):
    return number(100*value, suffix='%') if value is not None else '—'


def wp_table(rows, view):
    lookup = {(r['band'], r['side']): r for r in rows if r['view'] == view}
    body = []
    for band in PROB_LABELS:
        cells = []
        for side in ['home', 'away', 'both']:
            r = lookup[band, side]
            gap = number(r['gap_pp'], signed=True)
            se = number(r['se_pp'])
            uncertainty = (f'({gap} ± {se} pp)' if r['se_pp'] is not None
                           else f'({gap} pp · SE unavailable)' if r['decided'] else 'No decided games')
            cells.append("<td><div class='cal-rate'>" + percentage(r['actual_wp'])
                + "</div><div class='cal-detail'>vs " + percentage(r['implied_wp'])
                + f" implied <span class='cal-gap'>{uncertainty}</span></div>"
                + f"<div class='cal-meta'>n={r['decided']} · {r['ties']} ties</div>"
                + "<div class='cal-mov'>Median MOV <b>" + number(r['median_mov'], signed=True)
                + "</b></div></td>")
        body.append('<tr><th scope="row">' + band + '</th>' + ''.join(cells) + '</tr>')
    return ("<div class='gr-tablewrap'><table class='gr cal-wp'><thead><tr>"
            "<th scope='col'>Implied WP band</th><th scope='col'>Home side</th>"
            "<th scope='col'>Away side</th><th scope='col'>Both sides</th>"
            "</tr></thead><tbody>" + ''.join(body) + '</tbody></table></div>')


def ats_table(rows, view):
    body = []
    for r in rows:
        if r['view'] != view:
            continue
        record = f"{r['wins']}–{r['losses']}–{r['pushes']}"
        body.append("<tr><th scope='row'>" + r['band'] + '</th>'
            + f"<td class='n'>{r['observations']}</td>"
            + "<td class='n'>" + number(r['implied_mov'], signed=True) + '</td>'
            + "<td class='n cal-median'>" + number(r['median_mov'], signed=True) + '</td>'
            + "<td class='n'>" + record + '</td>'
            + "<td class='n'>" + percentage(r['cover_rate'])
            + "<small class='cal-se'>± " + number(r['se_pp']) + ' pp</small></td>'
            + "<td class='n'>" + number(r['units'], digits=2, signed=True, suffix='u') + '</td>'
            + "<td class='n'>" + percentage(r['roi']) + '</td></tr>')
    return ("<div class='gr-tablewrap'><table class='gr cal-ats'><thead><tr>"
            "<th scope='col'>Market spread band</th><th scope='col'>Bets</th>"
            "<th scope='col'>Avg implied MOV</th><th scope='col'>Median actual MOV</th>"
            "<th scope='col'>W–L–P</th><th scope='col'>Cover rate</th>"
            "<th scope='col'>Units</th><th scope='col'>ROI</th>"
            "</tr></thead><tbody>" + ''.join(body) + '</tbody></table></div>')


def render_body(pack):
    if not pack['panels']:
        return "<p class='empty'>No completed weeks are available for historical calibration yet.</p>"
    coverage = pack['coverage']
    years = sorted(coverage)
    current = pack['current_season']
    week = coverage.get(current)
    cutoff = f'{current} through Week {week}' if week else f'Awaiting the first completed {current} week'
    options = "<option value='all'>All seasons · " + str(years[0]) + '–' + str(years[-1]) + '</option>'
    options += ''.join(f"<option value='{y}'>{y} · through Week {coverage[y]}</option>" for y in reversed(years))
    out = ["<div class='cal-toolbar'><div><span class='badge'>Historical replay</span> "
           + "<span class='mut small'>" + cutoff + "</span></div>"
           + "<div class='cal-season-control'><label for='cal-season'>Season</label>"
           + "<select id='cal-season'>" + options + '</select></div></div>',
           "<p class='gr-note'>Completed regular-season weeks from 2023 onward. Tables refresh when a full weekly slate "
           "has final scores. These are reconstructed historical forecasts, including exposed development seasons; "
           "the live season record remains on Results.</p>"]
    for p in pack['panels']:
        label = 'All seasons' if p['season'] == 'all' else p['season']
        out.append(f"<section data-cal-season='{p['season']}' aria-label='{escape(label)}'"
                   + ('' if p['season'] == 'all' else ' hidden') + '>')
        out.append("<div class='gr-summary cal-summary'>"
            + f"<div class='gr-stat'><div class='l'>{label} · games</div><div class='v'>{p['games']:,}</div>"
            + f"<div class='s'>{p['binary_games']:,} decided · {p['ties']} tied final{'s' if p['ties'] != 1 else ''}</div></div>"
            + "<div class='gr-stat'><div class='l'>Market log loss</div><div class='v'>"
            + number(p['market_log_loss'], 4) + "</div><div class='s'>Lower is better</div></div>"
            + "<div class='gr-stat'><div class='l'>Model log loss</div><div class='v'>"
            + number(p['model_log_loss'], 4) + "</div><div class='s'>Same decided games</div></div></div>")
        for view, title, lead in [
            ('market_wp', 'Market implied vs actual WP', 'Paired market moneylines with the book’s margin removed.'),
            ('model_wp', 'Model implied vs actual WP', 'The production model’s win probabilities, including its confidence adjustment.'),
            ('market_ats', 'Market ATS vs actual', 'The market favorite against its market handicap, grouped by market spread magnitude.'),
            ('model_ats', 'Model ATS vs actual', 'The model’s ATS selection against the same market handicap, in the same market-spread groups.')]:
            out.append("<h2 class='sec'>" + title + "</h2><p class='sec-lead'>" + lead + '</p>')
            out.append(wp_table(p['rows'], view) if view.endswith('_wp') else ats_table(p['rows'], view))
            if view == 'model_wp':
                out.append("<p class='mut small'>WP = win probability. Actual WP and implied WP use decided games only; "
                    "n excludes tied finals. Both sides contains one observation per team. A game can appear in two "
                    "different bands; paired sides stay together when computing the ±1 standard error. "
                    "Median MOV includes losses and tied finals, signed toward the home or away side in each cell.</p>")
        out.append("<p class='mut small'>ATS = against the spread. Both ATS views use the same eligible games; pick’em "
            "lines and games without a model spread are excluded. Avg implied MOV and median actual MOV are signed "
            "toward the selected team, so an underdog can have a negative MOV and still cover. The model supplies a "
            "spread, not an implied cover probability. Cover rates exclude pushes; flat 1u returns assume −110 and "
            "include pushed stakes. Break-even cover rate: 52.4%. ± is one standard error.</p></section>")
    out.append("<div class='downloads'><a href='historical_calibration.csv'>Download all calibration bands</a></div>"
               "<noscript><style>[data-cal-season][hidden]{display:block!important} .cal-season-control{display:none}</style>"
               "<p class='mut small'>All season tables are shown below when JavaScript is disabled.</p></noscript>")
    return ''.join(out)


CSS = """
.cal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin:22px 0 14px}
.cal-season-control{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:700;color:var(--muted)}
.cal-toolbar select{font:600 13px var(--sans);padding:10px 34px 10px 12px;border:1px solid var(--line);
 border-radius:9px;background:var(--surface);color:var(--ink);max-width:100%}
.cal-summary{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:22px}
.cal-wp{min-width:650px;table-layout:fixed}.cal-wp th:first-child{width:19%}
.cal-wp tbody th,.cal-ats tbody th{font:650 12px var(--mono);letter-spacing:0;text-transform:none;color:var(--ink);
 background:transparent;white-space:nowrap;border-bottom:1px solid var(--line-2)}
.cal-wp td{vertical-align:top!important}.cal-rate{font:800 23px/1.3 var(--mono);letter-spacing:-.04em}
.cal-detail{font-size:12px;line-height:1.6;color:var(--muted);margin:5px 0}.cal-gap{display:block}
.cal-meta{font:500 11px/1.5 var(--mono);color:var(--faint)}
.cal-mov{font-size:12px;margin-top:7px;color:var(--muted)}.cal-mov b{font:650 12px var(--mono);color:var(--ink)}
.cal-ats{min-width:900px}.cal-median{font-weight:750;color:rgb(var(--accent-tx))}
.cal-se{display:block;font:500 10px/1.6 var(--mono);color:var(--faint);margin-top:3px}
[data-cal-season][hidden]{display:none!important}
@media(max-width:720px){.cal-summary{grid-template-columns:repeat(3,minmax(0,1fr))}.cal-summary .v{font-size:20px}
 .cal-summary .gr-stat{padding:12px 9px}.cal-summary .l{font-size:10px}.cal-summary .s{font-size:11px}
 .cal-toolbar{align-items:flex-start}.cal-wp td{white-space:normal!important}.cal-rate{font-size:21px}}
"""

SCRIPT = """<script>(function(){var select=document.getElementById('cal-season');if(!select)return;
select.addEventListener('change',function(){document.querySelectorAll('[data-cal-season]').forEach(function(panel){
panel.hidden=panel.getAttribute('data-cal-season')!==select.value;});});})();</script>"""
