"""Test 61: the weekly decayed median map with 2020-21 excluded from its training; see MAP_COVID_TRAINING.md.

    python research/map_covid_training.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import fixed_bands as fb  # noqa: E402
import slim_model as sm  # noqa: E402
import market_implied as mi  # noqa: E402
import map_vs_line as mvl  # noqa: E402

OUT = ROOT/'research/map_covid_training_results'
PROTOCOL_COMMIT = 'e3db8c8'
EXCLUDED = (2020, 2021)
BASES = {'2022': (2022, 2022), '2023-2026': (2023, 2026)}
ARMS = ('X model', 'X line-only', 'F model', 'F line-only', 'P model', 'R raw')
CONTRASTS = (('X model', 'F model'), ('X model', 'X line-only'), ('F model', 'F line-only'),
             ('X model', 'P model'), ('F model', 'P model'), ('X model', 'R raw'))
P_CHECK = '532-395-25'


def history():
    """Replay 2014-25 plus the ledger's 2026 rows; the ledger supplies production's map (P)."""
    rep, _ = mi.forecasts(mi.season_parts(mi.scores()))
    repro = mvl.forecast_reproduction(rep)
    led = pd.read_csv(mvl.LEDGER, low_memory=False)
    cols = ['game_id', 'season', 'week', 'spread_line', 'result', 'model_spread']
    j = rep[rep.season.between(2021, 2025)].merge(led[['game_id', 'model_spread']], on='game_id', suffixes=('', '_ledger'))
    repro['model spread, replay vs ledger 2021-25'] = float(np.nanmax(np.abs(j.model_spread-j.model_spread_ledger)))
    if repro['model spread, replay vs ledger 2021-25'] > 1e-9:
        raise ValueError(f'Replay and ledger model spreads differ ({repro})')
    h = pd.concat([rep.loc[rep.season <= 2025, cols], led.loc[led.season == 2026, cols]], ignore_index=True)
    if h.game_id.duplicated().any():
        raise ValueError('Duplicate games in the combined history')
    return h.merge(led[['game_id', 'fixed_band_spread']], on='game_id', how='left'), repro


def weekly_rules(h, scored, exclude=()):
    """Production's weekly rule for each scored (season, week); training drops the excluded seasons."""
    train = h[~h.season.isin(exclude)]
    rules = {}
    for y, w in scored[['season', 'week']].drop_duplicates().itertuples(index=False):
        rule = fb.fit_weekly(train, int(y), int(w))
        if rule is not None:
            if not fb.trained_before(rule, int(y), int(w)):
                raise ValueError('Weekly rule trained on its own or a later week')
        rules[(int(y), int(w))] = rule
    return rules


def frame(h):
    scored = h[h.season >= 2022].copy()
    x = weekly_rules(h, scored, EXCLUDED); f = weekly_rules(h, scored)
    xr = [x[(int(y), int(w))] for y, w in zip(scored.season, scored.week)]
    fr = [f[(int(y), int(w))] for y, w in zip(scored.season, scored.week)]
    ms, line = scored.model_spread.to_numpy(float), scored.spread_line.to_numpy(float)
    scored['X model'], scored['X line-only'] = mvl.through(ms, xr), mvl.through(line, xr)
    scored['F model'], scored['F line-only'] = mvl.through(ms, fr), mvl.through(line, fr)
    scored['P model'], scored['R raw'] = scored.fixed_band_spread, ms
    need = ['spread_line', 'result', 'model_spread', 'X model', 'X line-only', 'F model', 'F line-only']
    return scored[np.isfinite(scored[need]).all(axis=1)].reset_index(drop=True), x, f


def summarize(d, basis, label):
    line = d.spread_line.to_numpy(float); margin = (d.result-d.spread_line).to_numpy(float)
    rows, rets, sides = [], {}, {}
    for arm in ARMS:
        pred = d[arm].to_numpy(float)
        if not np.isfinite(pred).all():
            continue  # P does not exist before 2023
        sides[arm] = fb.pick(pred, line); rec, rets[arm] = sm.ats_record(sides[arm], margin)
        rows.append({'basis': basis, 'period': label, 'arm': arm, **rec})
    for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(d)))):
        rec, _ = sm.ats_record(side, margin); rows.append({'basis': basis, 'period': label, 'arm': name, **rec})
    contrasts = []
    for a, b in CONTRASTS:
        if a not in rets or b not in rets:
            continue
        diff = rets[a]-rets[b]; differ = sides[a] != sides[b]; r = rets[a][differ]
        se = float(diff.std(ddof=1)*np.sqrt(len(diff))) if len(diff) > 1 else np.nan
        contrasts.append({'basis': basis, 'period': label, 'contrast': f'{a} - {b}', 'n': len(d),
                          'differ': int(differ.sum()), 'units': float(diff.sum()), 'se': se,
                          'z': float(diff.sum()/se) if se and se > 0 else np.nan,
                          'first_arm_record_on_differing': f'{int((r > 0).sum())}-{int((r < 0).sum())}-{int((r == 0).sum())}'})
    return rows, contrasts


def verdict(c):
    if c['units'] < 0 and c['z'] <= -2: return 'covid training helped'
    if c['units'] > 0 and c['z'] >= 2: return 'covid training hurt'
    return 'unresolved'


def band_numbers(x, f, led_rules):
    rows = []
    for y in range(2022, 2027):
        p = fb.rule_for(led_rules, y, 1, weekly=True)
        for name, rule in (('X', x.get((y, 1))), ('F', f.get((y, 1))), ('P', p)):
            if rule:
                rows.append({'season': y, 'week': 1, 'map': name, **{b: m for b, m in zip(fb.BANDS, rule['magnitudes'])},
                             'training_games': rule['training_games']})
    return pd.DataFrame(rows)


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    h, repro = history()
    d, x, f = frame(h)
    rows, contrasts = [], []
    for basis, span in BASES.items():
        s = d[d.season.between(*span)].reset_index(drop=True)
        r, c = summarize(s, basis, basis); rows += r; contrasts += c
        if span[0] != span[1]:
            for y, g in s.groupby('season'):
                r, c = summarize(g.reset_index(drop=True), basis, str(int(y))); rows += r; contrasts += c
    rows, contrasts = pd.DataFrame(rows), pd.DataFrame(contrasts)
    prim = contrasts[(contrasts.contrast == 'X model - F model') & (contrasts.period == '2023-2026')].iloc[0].to_dict()
    p = rows[(rows.period == '2023-2026') & (rows.arm == 'P model')].iloc[0]
    checks = {'P_record_2023_26': f'{p.W}-{p.L}-{p.P}', 'P_expected': P_CHECK, 'P_reproduced': f'{p.W}-{p.L}-{p.P}' == P_CHECK,
              'excluded_seasons_in_X_training': bool(any(r and set(EXCLUDED) & {r['training_max_season']} for r in x.values())),
              'n_2022': int((d.season == 2022).sum()), 'n_2023_26': int(d.season.between(2023, 2026).sum())}
    if not checks['P_reproduced']:
        raise ValueError(f'Production map record not reproduced ({checks})')
    numbers = band_numbers(x, f, json.loads(mvl.RULES.read_text()))
    res = {'protocol': 'research/MAP_COVID_TRAINING.md', 'protocol_commit': PROTOCOL_COMMIT,
           'reproduction_max_error': repro, 'checks': checks, 'primary': prim, 'verdict': verdict(prim)}
    rows.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'contrasts.csv', index=False, float_format='%.6g')
    numbers.to_csv(out/'band_numbers.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(q.relative_to(ROOT)): mvl.sha(q) for q in (
        Path(__file__), ROOT/'research/MAP_COVID_TRAINING.md', ROOT/'research/map_vs_line.py',
        ROOT/'research/market_implied.py', ROOT/'nfl_model.py', ROOT/'fixed_bands.py', mvl.LEDGER, mvl.RULES, mi.SCORES)}, indent=2))
    report(res, rows, contrasts, numbers, out)
    return res


def report(res, rows, contrasts, numbers, out):
    p, c = res['primary'], res['checks']
    L = ['# Test 61: the weekly decayed median map with 2020-21 excluded from its training', '',
         f'Protocol: [MAP_COVID_TRAINING.md](../MAP_COVID_TRAINING.md), committed (`{res["protocol_commit"]}`) before any such map '
         'was fitted. Flat 1u at -110; break-even cover 52.4%; ROI SE has pushes in the denominator. Exposed bases; diagnostic only.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.',
         f'Checks: P on 2023-26 {c["P_record_2023_26"]} (expected {c["P_expected"]}); n 2022 {c["n_2022"]}, n 2023-26 {c["n_2023_26"]}.', '',
         f'**Primary (2023-26): X model - F model = {p["units"]:+.1f}u ± {p["se"]:.1f} (z {p["z"]:+.2f}, n {p["n"]}, sides differ on '
         f'{p["differ"]}, X record there {p["first_arm_record_on_differing"]}) -> {res["verdict"]}.**', '',
         'X: trained without 2020-21. F: full history from 2014. P: production (history from 2021). R: raw model spread.', '',
         '## Paired contrasts', '', '| Basis | Period | Contrast | Games | Sides differ | First arm on differing | Units | z |',
         '|---|---|---|---:|---:|---|---:|---:|']
    for _, k in contrasts.iterrows():
        L.append(f'| {k.basis} | {k.period} | {k.contrast} | {k.n} | {k.differ} | {k.first_arm_record_on_differing} | '
                 f'{k.units:+.1f} ± {k.se:.1f} | {k.z:+.2f} |')
    L += ['', '## Records', '', '| Basis | Period | Arm | W-L-P | Skips | Units | ROI ± SE | Cover |', '|---|---|---|---|---:|---:|---:|---:|']
    for _, r in rows.iterrows():
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% |')
    L += ['', '## Band numbers at week 1', '', '| Season | Map | ' + ' | '.join(fb.BANDS) + ' | Training games |', '|---|---|' + '---:|'*5]
    for _, n in numbers.iterrows():
        L.append(f'| {n.season} | {n["map"]} | ' + ' | '.join(f'{n[b]:g}' for b in fb.BANDS) + f' | {n.training_games} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    r = run(); print(json.dumps({k: r[k] for k in ('checks', 'primary', 'verdict')}, indent=2, default=float))
