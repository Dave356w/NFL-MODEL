"""Test 60: model band versus the line's own band through the same median map; see MAP_VS_LINE.md.

    python research/map_vs_line.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
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

OUT = ROOT/'research/map_vs_line_results'
PROTOCOL_COMMIT = 'b91ca42'
LEDGER = ROOT/'data/latest/fixed_band_ledger.csv'
RULES = ROOT/'data/latest/fixed_band_rules.json'
TEST, DISCOVERY = (2016, 2022), (2023, 2026)
ARMS = ('D model', 'D line-only', 'A model', 'A line-only', 'R raw')
CONTRASTS = (('D model', 'D line-only'), ('A model', 'A line-only'), ('D model', 'R raw'), ('D model', 'A model'))
DISCOVERY_CHECK = dict(units=55.36, flips=139, n=952)
TEST59 = {'D model': '785-740-41', 'A model': '741-784-41'}  # 2017-22, n 1,566


def through(values, rules):
    """Each row's value through that row's own rule (None gives NaN)."""
    return np.array([fb.apply([v], r)[0] for v, r in zip(np.asarray(values, float), rules)])


def replay_maps(d):
    """Annual and weekly decayed rules fitted on this replay's earlier games only."""
    annual = {int(y): fb.fit(d, int(y)) for y in sorted(d.season.unique())}
    weekly = {(int(y), int(w)): fb.fit_weekly(d, int(y), int(w))
              for y, w in d[['season', 'week']].drop_duplicates().itertuples(index=False)}
    for (y, w), rule in weekly.items():
        if rule is not None and not fb.trained_before(rule, y, w):
            raise ValueError('Weekly rule trained on its own or a later week')
    a = [annual[int(y)] for y in d.season]
    w = [weekly[(int(y), int(k))] for y, k in zip(d.season, d.week)]
    return a, w


def predictions(d, annual, weekly):
    x, line = d.model_spread.to_numpy(float), d.spread_line.to_numpy(float)
    return {'D model': through(x, weekly), 'D line-only': through(line, weekly),
            'A model': through(x, annual), 'A line-only': through(line, annual), 'R raw': x}


def frame(d, annual, weekly):
    preds = predictions(d, annual, weekly)
    out = d[['game_id', 'season', 'week', 'spread_line', 'result', 'model_spread']].copy()
    for arm in ARMS:
        out[arm] = preds[arm]
    ok = np.isfinite(out[['spread_line', 'result', 'model_spread', *ARMS]]).all(axis=1)
    return out[ok].reset_index(drop=True)


def summarize(d, basis, label):
    line = d.spread_line.to_numpy(float); margin = (d.result-d.spread_line).to_numpy(float)
    rows, rets, sides = [], {}, {}
    for arm in ARMS:
        sides[arm] = fb.pick(d[arm].to_numpy(float), line)
        rec, rets[arm] = sm.ats_record(sides[arm], margin)
        rows.append({'basis': basis, 'period': label, 'arm': arm, **rec})
    for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(d)))):
        rec, _ = sm.ats_record(side, margin); rows.append({'basis': basis, 'period': label, 'arm': name, **rec})
    contrasts = []
    for a, b in CONTRASTS:
        diff = rets[a]-rets[b]; differ = sides[a] != sides[b]; r = rets[a][differ]
        se = float(diff.std(ddof=1)*np.sqrt(len(diff))) if len(diff) > 1 else np.nan
        contrasts.append({'basis': basis, 'period': label, 'contrast': f'{a} - {b}', 'n': len(d),
                          'differ': int(differ.sum()), 'units': float(diff.sum()), 'se': se,
                          'z': float(diff.sum()/se) if se and se > 0 else np.nan,
                          'first_arm_record_on_differing': f'{int((r > 0).sum())}-{int((r < 0).sum())}-{int((r == 0).sum())}'})
    return rows, contrasts


def verdict(c):
    if c['units'] > 0 and c['z'] >= 2: return 'supported'
    if c['units'] < 0 and c['z'] <= -2: return 'contradicted'
    return 'unresolved'


def discovery_frame():
    prod = pd.read_csv(LEDGER, low_memory=False)
    # The exported rules are weekly only; the annual arm refits production's superseded annual map on
    # the ledger's own earlier seasons (2021 on), as the site did before 2026-11-04.
    fits = {y: fb.fit(prod, y) for y in range(DISCOVERY[0], DISCOVERY[1]+1)}
    prod = prod[prod.season.between(*DISCOVERY)].copy()
    rules = json.loads(RULES.read_text())
    weekly = [fb.rule_for(rules, int(y), int(w), weekly=True) for y, w in zip(prod.season, prod.week)]
    annual = [fits[int(y)] for y in prod.season]
    d = frame(prod, annual, weekly)
    err = float(np.nanmax(np.abs(d['D model']-prod.set_index('game_id').fixed_band_spread.reindex(d.game_id).to_numpy())))
    return d, err


def forecast_reproduction(rep):
    """market_implied.reproduction's two forecast checks. Its third check compares the annual map with
    production's fixed_band_spread, which has been the weekly map since 2026-11-04; the production map is
    checked against the ledger in discovery_frame instead."""
    errs = {}
    r = pd.read_csv(mi.t.RETRO)[['game_id', 'model_wp']]
    j = rep[rep.season.between(2021, 2025)].merge(r, on='game_id', validate='one_to_one')
    errs['v1.19 retro_ledger 2021-25'] = float(np.max(np.abs(j.p-j.model_wp)))
    s3 = pd.read_csv(mi.S3_FORECASTS); s3 = s3[s3.arm == 'S3 core'][['game_id', 'p']]
    j = rep[rep.season.between(2014, 2020)].merge(s3, on='game_id', suffixes=('', '_s3'), validate='one_to_one')
    errs['Test 50 S3 2014-20 (6-digit CSV)'] = float(np.max(np.abs(j.p-j.p_s3)))
    if errs['v1.19 retro_ledger 2021-25'] > 1e-9 or errs['Test 50 S3 2014-20 (6-digit CSV)'] > mi.S3_CSV_TOL:
        raise ValueError(f'Replay does not reproduce v1.19 ({errs})')
    return errs


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    rep, _ = mi.forecasts(mi.season_parts(mi.scores()))
    repro = forecast_reproduction(rep)
    annual, weekly = replay_maps(rep)
    full = frame(rep, annual, weekly)
    annual_err = float(np.nanmax(np.abs(full['A model']-rep.set_index('game_id').mapped_spread.reindex(full.game_id).to_numpy())))
    test = full[full.season.between(*TEST)].reset_index(drop=True)
    disc, disc_err = discovery_frame()
    rows, contrasts = [], []
    for basis, d, span in (('test', test, TEST), ('discovery', disc, DISCOVERY)):
        r, c = summarize(d, basis, f'{span[0]}-{span[1]}'); rows += r; contrasts += c
        for y, s in d.groupby('season'):
            r, c = summarize(s.reset_index(drop=True), basis, str(int(y))); rows += r; contrasts += c
    r59, _ = summarize(test[test.season >= 2017].reset_index(drop=True), 'test', '2017-2022 (Test 59 rows)'); rows += r59
    rows, contrasts = pd.DataFrame(rows), pd.DataFrame(contrasts)
    key = contrasts.contrast.eq('D model - D line-only')
    primary = contrasts[key & contrasts.basis.eq('test') & contrasts.period.eq(f'{TEST[0]}-{TEST[1]}')].iloc[0].to_dict()
    dc = contrasts[key & contrasts.basis.eq('discovery') & contrasts.period.eq(f'{DISCOVERY[0]}-{DISCOVERY[1]}')].iloc[0]
    checks = {'annual_map_matches_harness': annual_err, 'discovery_map_matches_ledger': disc_err,
              'discovery_units': float(dc.units), 'discovery_differ': int(dc.differ), 'discovery_n': int(dc.n),
              'discovery_reproduced': bool(abs(dc.units-DISCOVERY_CHECK['units']) < .01
                                           and dc.differ == DISCOVERY_CHECK['flips'] and dc.n == DISCOVERY_CHECK['n']),
              'test59_records': {a: (lambda q: f'{q.W}-{q.L}-{q.P}')(rows[(rows.period == '2017-2022 (Test 59 rows)')
                                 & (rows.arm == a)].iloc[0]) for a in TEST59}, 'test59_expected': TEST59}
    res = {'protocol': 'research/MAP_VS_LINE.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'checks': checks, 'primary': primary, 'verdict': verdict(primary)}
    rows.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'contrasts.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/MAP_VS_LINE.md', ROOT/'research/market_implied.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', LEDGER, RULES, mi.SCORES)}, indent=2))
    report(res, rows, contrasts, out)
    return res


def report(res, rows, contrasts, out):
    p, c = res['primary'], res['checks']
    L = ['# Test 60: model band versus the line\'s own band through the same median map', '',
         f'Protocol: [MAP_VS_LINE.md](../MAP_VS_LINE.md), committed (`{res["protocol_commit"]}`) before the line-only arm was '
         'scored before 2023. Flat 1u at -110; break-even cover 52.4%; ROI SE has pushes in the denominator. '
         'Both bases exposed; diagnostic only.', '',
         'Reproduction of v1.19: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.',
         f'Checks: annual map vs harness {c["annual_map_matches_harness"]:.1e}; discovery map vs ledger '
         f'{c["discovery_map_matches_ledger"]:.1e}; discovery D model - D line-only {c["discovery_units"]:+.2f}u on '
         f'{c["discovery_differ"]} of {c["discovery_n"]} (reproduced: {c["discovery_reproduced"]}); Test 59 rows 2017-22 '
         + ', '.join(f'{a} {c["test59_records"][a]} (Test 59: {v})' for a, v in c['test59_expected'].items()) + '.', '',
         f'**Primary (test 2016-22): D model - D line-only = {p["units"]:+.1f}u ± {p["se"]:.1f} (z {p["z"]:+.2f}, n {p["n"]}, '
         f'sides differ on {p["differ"]}, model record there {p["first_arm_record_on_differing"]}) -> {res["verdict"]}.**', '',
         '## Paired contrasts', '', '| Basis | Period | Contrast | Games | Sides differ | First arm on differing | Units | z |',
         '|---|---|---|---:|---:|---|---:|---:|']
    for _, k in contrasts.iterrows():
        L.append(f'| {k.basis} | {k.period} | {k.contrast} | {k.n} | {k.differ} | {k.first_arm_record_on_differing} | '
                 f'{k.units:+.1f} ± {k.se:.1f} | {k.z:+.2f} |')
    L += ['', '## Records', '', '| Basis | Period | Arm | W-L-P | Skips | Units | ROI ± SE | Cover |', '|---|---|---|---|---:|---:|---:|---:|']
    for _, r in rows.iterrows():
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    r = run(); print(json.dumps({k: r[k] for k in ('checks', 'primary', 'verdict')}, indent=2, default=float))
