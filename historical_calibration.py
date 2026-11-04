"""Public historical calibration, using completed regular-season weeks only.

This is an aggregate reporting view. It never changes forecasts, the median map,
ATS selections, snapshots or the forward ledger.

Spread-band ROI (owner decision 2026-11-04) is graded at each game's actual spread price for
the side bet (nflverse home/away spread odds, closing basis): a win pays that price, a loss
costs 1u, a push 0. A game without a valid price (|odds| >= 100) is graded at −110 and
counted in `assumed_prices`.

The page shows win-probability calibration folded to the favorite (owner decision 2026-11-04):
each game enters once, at its favorite's probability, so the four 50%+ bands carry everything the
eight two-sided bands do. The CSV keeps the full eight-band, two-sided export.

Moneyline ROI (owner decision 2026-11-04, page only, never in the CSV): MODEL.md's legacy flat 1u
basis. The model's favorite at its posted moneyline, beside the market favorite on the same
games and the market-correct null (negative by the hold). Aggregate history only.
"""
from html import escape

import numpy as np
import pandas as pd

import fixed_bands

FIRST_SEASON = 2023
PROB_CUTS = [.2, .3, .4, .5, .6, .7, .8]
PROB_LABELS = ['0–<20%', '20–<30%', '30–<40%', '40–<50%',
               '50–<60%', '60–<70%', '70–<80%', '80–100%']
FAV_CUTS = [.6, .7, .8]
FAV_LABELS = ['50–<60%', '60–<70%', '70–<80%', '80–100%']
SPREAD_CUTS = [3., 7., 10.]
SPREAD_LABELS = ['<3 points', '3–<7 points', '7–<10 points', '10+ points']
EXPORT_COLUMNS = ['season', 'view', 'band', 'side', 'observations', 'decided',
                  'wins', 'losses', 'pushes', 'ties', 'implied_wp', 'actual_wp',
                  'gap_pp', 'se_pp', 'median_mov', 'units', 'roi', 'roi_se_pp',
                  'actual_prices', 'assumed_prices']


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
                median_mov=float(group.mov.median()) if len(group) else None,
                units=None, roi=None, roi_se_pp=None, actual_prices=None, assumed_prices=None))
    return rows


def win_payout(odds):
    """Profit per 1u on a win at American odds; NaN for a missing or invalid price."""
    o = pd.to_numeric(pd.Series(odds), errors='coerce').to_numpy(float)
    valid = np.isfinite(o) & (np.abs(o) >= 100)
    safe = np.where(valid, o, 100.)
    return np.where(valid, np.where(safe > 0, safe/100., 100./-safe), np.nan)


def roi_rows(frame, model, view):
    """ATS returns against market lines, grouped by each source's own spread."""
    valid = (np.isfinite(frame.spread_line) & frame.spread_line.ne(0)
             & np.isfinite(frame.fixed_band_spread))
    data = frame.loc[valid].copy()
    prediction = data.fixed_band_spread if model else data.spread_line
    # A market-line forecast has zero edge, so the production rule backs its
    # favorite. The model forecast selects its ATS side using that same rule.
    data['ats_result'], _ = fixed_bands.grade(data, prediction)
    side = fixed_bands.pick(prediction, data.spread_line)
    home = win_payout(data['home_spread_odds'] if 'home_spread_odds' in data else np.nan)
    away = win_payout(data['away_spread_odds'] if 'away_spread_odds' in data else np.nan)
    if np.ndim(home) == 0 or len(home) != len(data): home = np.full(len(data), np.nan)
    if np.ndim(away) == 0 or len(away) != len(data): away = np.full(len(data), np.nan)
    actual = np.where(side > 0, home, np.where(side < 0, away, np.nan))
    data['priced'] = np.isfinite(actual)
    payout = np.where(data.priced, actual, 1/1.1)
    data['units'] = np.where(data.ats_result.eq('W'), payout, np.where(data.ats_result.eq('L'), -1., 0.))
    data['band_number'] = np.digitize(prediction.abs(), SPREAD_CUTS)
    rows = []
    for k, band in enumerate(SPREAD_LABELS):
        group = data.loc[data.band_number.eq(k)]
        n = len(group)
        wins, losses, pushes = [int(group.ats_result.eq(x).sum()) for x in ['W', 'L', 'P']]
        units = float(group.units.sum())
        se = standard_error(group.units, group.game_id)
        rows.append(dict(view=view, band=band, side='model_pick' if model else 'market_favorite',
            observations=n, decided=wins+losses, wins=wins, losses=losses, pushes=pushes,
            ties=int(group.result.eq(0).sum()), implied_wp=None, actual_wp=None,
            gap_pp=None, se_pp=None,
            median_mov=None, units=units if n else None, roi=units/n if n else None,
            roi_se_pp=100*se if se is not None else None,
            actual_prices=int(group.priced.sum()), assumed_prices=int((~group.priced).sum())))
    return rows


def favorite_rows(frame, column):
    """Each game once, at its favorite's probability; MOV signed toward that favorite.
    A 50% game counts its home side. Keyed by (band, 'home' | 'away' | 'all')."""
    p = frame[column].to_numpy(float)
    home = p >= .5
    fav = pd.DataFrame({'game_id': frame.game_id.to_numpy(), 'side': np.where(home, 'home', 'away'),
                        'probability': np.where(home, p, 1-p),
                        'mov': np.where(home, 1, -1) * frame.result.to_numpy(float)})
    fav['band_number'] = np.digitize(np.round(fav.probability, 12), FAV_CUTS)
    out = {}
    for k, band in enumerate(FAV_LABELS):
        for side in ['home', 'away', 'all']:
            group = fav.loc[fav.band_number.eq(k) & (fav.side.eq(side) if side != 'all' else True)]
            decided = group.loc[group.mov.ne(0)]
            n = len(decided)
            actual = float(decided.mov.gt(0).mean()) if n else None
            implied = float(decided.probability.mean()) if n else None
            se = standard_error(decided.mov.gt(0).astype(float) - decided.probability, decided.game_id)
            out[band, side] = dict(decided=n, ties=int(group.mov.eq(0).sum()), actual_wp=actual,
                implied_wp=implied, gap_pp=100*(actual-implied) if n else None,
                se_pp=100*se if se is not None else None,
                median_mov=float(group.mov.median()) if len(group) else None)
    return out


def moneyline_rows(frame):
    """Flat 1u at the posted moneyline (MODEL.md legacy basis), by the model favorite's WP band.
    Both sources use the same games: priced, decided by the model and not a market pick'em."""
    import nfl_model as m
    if not {'home_moneyline', 'away_moneyline'} <= set(frame):
        return []
    d = frame.copy()
    d['home won'] = np.where(d.result > 0, 1., np.where(d.result < 0, 0., .5))
    d['market_ml_wp'] = m.market_ml_wp(d)
    model, market = m.flat_bets(d, 'model_wp'), m.flat_bets(d, 'market_ml_wp')
    keep = (model.units.notna() & market.units.notna()).to_numpy()
    band = np.digitize(np.round(np.maximum(d.model_wp, 1-d.model_wp), 12), FAV_CUTS)
    rows = []
    for k, label in [*enumerate(FAV_LABELS), (None, 'All bands')]:
        mask = keep & (band == k) if k is not None else keep
        rows.append(dict(band=label, model=m.roi_summary(model[mask]), market=m.roi_summary(market[mask]),
                         differ=int((model.side[mask] != market.side[mask]).sum())))
    return rows


def panel(frame, season):
    binary = frame.loc[frame.result.ne(0)]
    y = binary.result.gt(0).to_numpy(float)
    def log_loss(column):
        p = np.clip(binary[column].to_numpy(float), 1e-12, 1-1e-12)
        return float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean()) if len(y) else None
    rows = (wp_rows(frame, 'market_wp', 'market_wp')
            + wp_rows(frame, 'model_wp', 'model_wp')
            + roi_rows(frame, False, 'market_spread')
            + roi_rows(frame, True, 'model_spread'))
    return dict(season=season, games=len(frame), binary_games=len(binary),
        ties=int(frame.result.eq(0).sum()), market_log_loss=log_loss('market_wp'),
        model_log_loss=log_loss('model_wp'), rows=rows,
        favorites={v: favorite_rows(frame, v) for v in ('market_wp', 'model_wp')},
        moneyline=moneyline_rows(frame))


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


def american_odds(probability):
    """Rounded fair American odds for an interior probability cutoff."""
    odds = (100 * (1-probability) / probability if probability <= .5
            else -100 * probability / (1-probability))
    return number(odds, digits=0, signed=True)


def market_odds_band(index):
    if index == 0:
        return 'Longer than ' + american_odds(PROB_CUTS[0])
    if index == len(PROB_LABELS)-1:
        return american_odds(PROB_CUTS[-1]) + ' or shorter'
    return '≈ ' + american_odds(PROB_CUTS[index-1]) + ' to ' + american_odds(PROB_CUTS[index])


def wp_table(rows, view):
    lookup = {(r['band'], r['side']): r for r in rows if r['view'] == view}
    body = []
    for index, band in enumerate(PROB_LABELS):
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
        odds = ("<span class='cal-odds'>" + market_odds_band(index) + '</span>'
                if view == 'market_wp' else '')
        body.append('<tr><th scope="row">' + band + odds + '</th>' + ''.join(cells) + '</tr>')
    odds_heading = "<span class='cal-odds'>Fair American odds</span>" if view == 'market_wp' else ''
    return ("<div class='gr-tablewrap'><table class='gr cal-wp'><thead><tr>"
            "<th scope='col'>Implied WP band" + odds_heading + "</th><th scope='col'>Home side</th>"
            "<th scope='col'>Away side</th><th scope='col'>Both sides</th>"
            "</tr></thead><tbody>" + ''.join(body) + '</tbody></table></div>')


def roi_table(rows, view):
    body = []
    for r in rows:
        if r['view'] != view:
            continue
        n = r['observations']
        meta = f"{n:,} bet{'s' if n != 1 else ''}"
        if n:
            meta += (' · ± ' + number(r['roi_se_pp']) + ' pp'
                     if r['roi_se_pp'] is not None else ' · SE unavailable')
            if r.get('assumed_prices'):
                meta += f" · {r['assumed_prices']:,} at assumed −110"
        roi = number(100*r['roi'], signed=True, suffix='%') if n else '—'
        tone = 'pos-tx' if n and r['roi'] > 0 else 'neg-tx' if n and r['roi'] < 0 else ''
        body.append("<tr><th scope='row'>" + r['band'] + '</th>'
            + f"<td class='n'><div class='cal-roi-rate {tone}'>" + roi + '</div>'
            + "<div class='cal-roi-meta'>" + meta + '</div></td></tr>')
    source = 'Market' if view == 'market_spread' else 'Model'
    return ("<div class='gr-tablewrap cal-roi-wrap'><table class='gr cal-roi'><thead><tr>"
            + f"<th scope='col'>{source} spread band</th><th scope='col'>ATS ROI</th>"
            "</tr></thead><tbody>" + ''.join(body) + '</tbody></table></div>')


def favorite_odds(index):
    if index == len(FAV_LABELS)-1:
        return american_odds(FAV_CUTS[-1]) + ' or shorter'
    low = '−100' if index == 0 else american_odds(FAV_CUTS[index-1])
    return '≈ ' + low + ' to ' + american_odds(FAV_CUTS[index])


def calibration_cell(r):
    if not r['decided']:
        return "<td><div class='cal-rate'>—</div><div class='cal-meta'>No decided games</div></td>"
    gap = number(r['gap_pp'], signed=True)
    uncertainty = f'{gap} ± {number(r["se_pp"])} pp' if r['se_pp'] is not None else f'{gap} pp'
    tone = '' if r['se_pp'] is None or abs(r['gap_pp']) < r['se_pp'] else (' pos-tx' if r['gap_pp'] > 0 else ' neg-tx')
    return ("<td><div class='cal-rate'>" + percentage(r['actual_wp']) + "</div>"
            + "<div class='cal-detail'>vs " + percentage(r['implied_wp']) + " implied · "
            + f"<span class='cal-gap{tone}'>{uncertainty}</span></div>"
            + f"<div class='cal-meta'>n={r['decided']:,}" + (f" · {r['ties']} tie{'s' if r['ties'] != 1 else ''}" if r['ties'] else '')
            + " · median MOV " + number(r['median_mov'], signed=True) + "</div></td>")


def favorite_table(p):
    body = []
    for index, band in enumerate(FAV_LABELS):
        body.append("<tr><th scope='row'>" + band + "<span class='cal-odds'>" + favorite_odds(index) + '</span></th>'
                    + calibration_cell(p['favorites']['market_wp'][band, 'all'])
                    + calibration_cell(p['favorites']['model_wp'][band, 'all']) + '</tr>')
    return ("<div class='gr-tablewrap'><table class='gr cal-wp cal-fav'><thead><tr>"
            "<th scope='col'>Favorite WP band<span class='cal-odds'>Fair odds (market)</span></th>"
            "<th scope='col'>Market favorite</th><th scope='col'>Model favorite</th>"
            "</tr></thead><tbody>" + ''.join(body) + '</tbody></table></div>')


def favorite_split_table(p, view):
    body = ''.join("<tr><th scope='row'>" + band + '</th>'
                   + calibration_cell(p['favorites'][view][band, 'home'])
                   + calibration_cell(p['favorites'][view][band, 'away']) + '</tr>' for band in FAV_LABELS)
    source = 'Market' if view == 'market_wp' else 'Model'
    return ("<div class='gr-tablewrap'><table class='gr cal-wp cal-fav'><thead><tr>"
            f"<th scope='col'>{source} favorite WP</th><th scope='col'>Favorite at home</th>"
            "<th scope='col'>Favorite away</th></tr></thead><tbody>" + body + '</tbody></table></div>')


def roi_cell(summary, null=None):
    n = summary['bets']
    if not n:
        return "<td class='n'><div class='cal-roi-rate'>—</div><div class='cal-roi-meta'>No bets</div></td>"
    roi = summary['roi']
    tone = 'pos-tx' if roi > 0 else 'neg-tx' if roi < 0 else ''
    se = summary['roi_se']
    meta = (f"{summary['wins']}-{summary['losses']}-{summary['pushes']} · {number(summary['units'], 1, True)}u"
            + (f" · ± {number(100*se)} pp" if se is not None and np.isfinite(se) else ''))
    return (f"<td class='n'><div class='cal-roi-rate {tone}'>" + number(100*roi, signed=True, suffix='%')
            + "</div><div class='cal-roi-meta'>" + meta + '</div></td>')


def moneyline_table(rows):
    body = []
    for r in rows:
        total = r['band'] == 'All bands'
        null = r['model']['null_roi']
        body.append(f"<tr{' class=cal-total' if total else ''}><th scope='row'>" + r['band']
                    + f"<span class='cal-odds'>{r['model']['bets']:,} games · {r['differ']:,} on different sides</span></th>"
                    + roi_cell(r['model']) + roi_cell(r['market'])
                    + "<td class='n'><div class='cal-roi-rate cal-null'>"
                    + (number(100*null, signed=True, suffix='%') if r['model']['bets'] else '—')
                    + "</div><div class='cal-roi-meta'>if the market is right</div></td></tr>")
    return ("<div class='gr-tablewrap'><table class='gr cal-roi cal-ml'><thead><tr>"
            "<th scope='col'>Model favorite WP band</th><th scope='col'>Model favorite</th>"
            "<th scope='col'>Market favorite</th><th scope='col'>Market-correct null</th>"
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
        out.append("<h2 class='sec'>Win probability vs actual win rate</h2><p class='sec-lead'>Each game counted "
                   "once, at its favorite’s probability. The market uses paired moneylines with the book’s margin "
                   "removed; the model uses its production win probabilities.</p>")
        out.append(favorite_table(p))
        out.append("<details class='cal-more'><summary>Split by favorite at home or away</summary>"
                   + favorite_split_table(p, 'market_wp') + favorite_split_table(p, 'model_wp') + '</details>')
        out.append("<p class='mut small'>WP = win probability. Bands below 50% are the underdog side of these same "
                   "games, so they are omitted here; the CSV keeps both sides. Actual and implied WP use decided games; "
                   "n excludes tied finals. ± is one standard error; the gap is colored only when it exceeds it. "
                   "Median MOV includes losses and ties, signed toward the favorite. Fair odds are approximate, "
                   "after removing the bookmaker’s margin.</p>")
        out.append("<h2 class='sec'>ATS ROI by spread band</h2><p class='sec-lead'>Left: back the market favorite, "
                   "grouped by market spread. Right: back the model’s ATS pick, grouped by its mapped spread. Both are "
                   "graded against the market handicap.</p><div class='cal-pair'>"
                   + roi_table(p['rows'], 'market_spread') + roi_table(p['rows'], 'model_spread') + '</div>')
        spread_rows = [r for r in p['rows'] if r['view'] == 'model_spread']
        priced = sum(r['actual_prices'] or 0 for r in spread_rows)
        assumed = sum(r['assumed_prices'] or 0 for r in spread_rows)
        price_text = ('Flat 1-unit stakes at each game’s actual spread price for the side bet (closing quotes). '
                      + (f'{assumed:,} of {priced + assumed:,} model stakes had no price and use assumed −110. '
                         if assumed else ''))
        out.append("<p class='mut small cal-roi-note'>" + price_text + "ROI is net profit divided "
            "by total stakes, including pushes. ± is one standard error. Both tables use the same eligible games, "
            "each counted once; their band counts can differ because each uses its own spread. Market pick’em "
            "lines and unavailable model spreads are excluded.</p>")
        if p.get('moneyline'):
            out.append("<h2 class='sec'>Moneyline ROI: model vs market favorite</h2><p class='sec-lead'>Flat 1u on "
                       "the side each source makes the favorite, at that side’s posted closing moneyline, on the same "
                       "games. Grouped by the model favorite’s win probability.</p>" + moneyline_table(p['moneyline'])
                       + "<p class='mut small cal-roi-note'>The market-correct null is the ROI expected on the model’s "
                       "bets if the market’s no-vig probabilities were exactly right. It is negative by the hold, so it "
                       "is the bar to beat, not zero. The two sources differ only on games where they favor different "
                       "sides. ± is one standard error; an interval that crosses the null is unresolved. Historical "
                       "aggregate only: the live product is ATS, and no moneyline picks are published.</p>")
        out.append('</section>')
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
.cal-wp tbody th,.cal-roi tbody th{font:650 12px var(--mono);letter-spacing:0;text-transform:none;color:var(--ink);
 background:transparent;white-space:nowrap;border-bottom:1px solid var(--line-2)}
.cal-wp td{vertical-align:top!important}.cal-rate{font:800 23px/1.3 var(--mono);letter-spacing:-.04em}
.cal-detail{font-size:12px;line-height:1.6;color:var(--muted);margin:5px 0}.cal-gap{display:block}
.cal-meta{font:500 11px/1.5 var(--mono);color:var(--faint)}
.cal-odds{display:block;font:500 11px/1.5 var(--mono);color:var(--muted);margin-top:6px;
 letter-spacing:0;text-transform:none;white-space:normal}
.cal-mov{font-size:12px;margin-top:7px;color:var(--muted)}.cal-mov b{font:650 12px var(--mono);color:var(--ink)}
.cal-roi-wrap{max-width:640px}.cal-roi{min-width:360px;table-layout:fixed}
.cal-roi th:first-child{width:48%}.cal-roi td{padding-top:15px;padding-bottom:15px}
.cal-roi-rate{font:800 22px/1.3 var(--mono);letter-spacing:-.04em}
.cal-roi-meta{font:500 11px/1.6 var(--mono);color:var(--faint);margin-top:5px}
.cal-roi-note{max-width:100ch;line-height:1.7}
.cal-fav{min-width:520px}.cal-fav th:first-child{width:30%}
.cal-gap.pos-tx,.cal-gap.neg-tx{font-weight:700}
.cal-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.cal-pair .cal-roi-wrap{max-width:none}
.cal-ml{min-width:600px}.cal-ml th:first-child{width:28%}.cal-null{color:var(--muted)}
.cal-total th,.cal-total td{border-top:2px solid var(--line)}
.cal-more{margin:12px 0 4px}.cal-more summary{cursor:pointer;font-size:13px;font-weight:700;color:var(--muted);padding:6px 0}
.cal-more .gr-tablewrap{margin-top:10px}
[data-cal-season][hidden]{display:none!important}
@media(max-width:720px){.cal-pair{grid-template-columns:1fr}
 .cal-fav,.cal-ml,.cal-roi{min-width:0}.cal-fav th,.cal-fav td,.cal-ml th,.cal-ml td{padding-left:8px!important;padding-right:8px!important;white-space:normal!important}
 .cal-fav th:first-child{width:27%}.cal-ml th:first-child{width:25%}.cal-ml .cal-roi-rate{font-size:16px}
 .cal-ml .cal-roi-meta,.cal-fav .cal-meta{white-space:normal;overflow-wrap:anywhere}.cal-fav .cal-rate{font-size:18px}.cal-summary{grid-template-columns:repeat(3,minmax(0,1fr))}.cal-summary .v{font-size:20px}
 .cal-summary .gr-stat{padding:12px 9px}.cal-summary .l{font-size:10px}.cal-summary .s{font-size:11px}
 .cal-toolbar{align-items:flex-start}.cal-wp td{white-space:normal!important}.cal-rate{font-size:21px}}
"""

SCRIPT = """<script>(function(){var select=document.getElementById('cal-season');if(!select)return;
select.addEventListener('change',function(){document.querySelectorAll('[data-cal-season]').forEach(function(panel){
panel.hidden=panel.getAttribute('data-cal-season')!==select.value;});});})();</script>"""
