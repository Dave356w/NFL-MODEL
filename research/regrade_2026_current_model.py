"""Regrade every 2026 game with the current production model (owner request 2026-11-16).

Research/backend view only. The public pages keep lock continuity (owner decision
2026-11-15): a saved pregame lock stays the game's decision. This script replays the
current revision (manifest in data/latest) over every completed 2026 game with its
own walk-forward forecast, weekly decayed median map and post-map QB overlay, then
grades it ATS beside the public decision and same-row baselines. The recipe, map
and lock policy are unchanged; nothing under data/ is written.

Pricing: each replay pick is priced at the exact handicap from ESPN evidence
captured at or before its T-60 deadline (the lock rule), else the closing price at
that handicap (an estimate), else an explicit -110 assumption. Baselines use flat
-110, as in the backend same-row report.

Run: python -m research.regrade_2026_current_model
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import ats_locks
import build_site as b
import fixed_bands
import season_ats

OUT = Path(__file__).with_name('regrade_2026_results')
BREAK_EVEN = 110 / 210


def load(data='data'):
    latest = b.load_latest(Path(data) / 'latest')
    if latest is None:
        raise FileNotFoundError('data/latest snapshot missing')
    latest['ats_locks'] = ats_locks.display_records(data)
    ledger = b.score_updates.overlay(b.load_ledger(data), latest['final_scores'])
    pool = season_ats.build(latest, ledger)
    return latest, pool


def replay(latest, pool):
    """Current-revision replay: walk-forward ledger plus the current week's board."""
    keep = ['game_id', 'season', 'week', 'home', 'away', 'spread_line', 'model_wp',
            'model_spread', 'fixed_band_spread', 'qb_replacement_applied',
            'qb_replacement_margin_adjustment']
    hist = latest['fixed_band_ledger']
    hist = hist.loc[hist.season.eq(2026)].reindex(columns=keep)
    board = latest.get('board', pd.DataFrame())
    board = board.loc[board.season.eq(2026) & ~board.game_id.isin(hist.game_id)].reindex(columns=keep)
    frame = pd.concat([hist.assign(replay_source='walk-forward ledger'),
                       board.assign(replay_source='current-week board')], ignore_index=True)
    if frame.game_id.duplicated().any():
        raise ValueError('duplicate replay game')
    # Outcomes and kickoffs come from the public pool (final-score evidence), never
    # from the replay; only games with a final score are graded.
    facts = pool.set_index('game_id')
    for name in ('result', 'home_score', 'away_score', 'kickoff_utc'):
        frame[name] = frame.game_id.map(facts[name]) if name in facts else np.nan
    frame['result'] = pd.to_numeric(frame.result, errors='coerce')
    frame = frame.loc[frame.result.notna() & frame.spread_line.notna() & frame.fixed_band_spread.notna()].copy()
    frame['lock_at_utc'] = [ats_locks.deadline(k).isoformat() for k in frame.kickoff_utc]
    grades, units = fixed_bands.grade(frame, frame.fixed_band_spread)
    frame['fixed_band_ats_result'], frame['fixed_band_ats_units'] = grades, units
    side = fixed_bands.pick(frame.fixed_band_spread, frame.spread_line)
    frame['fixed_band_ats_side'] = np.where(side > 0, 'home', np.where(side < 0, 'away', ''))
    frame = frame.sort_values(['week', 'kickoff_utc', 'game_id'], kind='stable').reset_index(drop=True)
    frame = season_ats.price(frame, latest['espn_archive'], assume_unmatched=True)
    rules = latest.get('fixed_band_rules', [])
    frame['line_mapped'] = [float(fixed_bands.apply([r.spread_line], fixed_bands.rule_for(rules, 2026, int(r.week)))[0])
                            for r in frame.itertuples()]
    return frame


def record(results, units):
    r = pd.Series(results)
    u = pd.to_numeric(pd.Series(units), errors='coerce')
    w, l, p, s = (int(r.eq(k).sum()) for k in 'WLPS')
    bets = r.isin(list('WLP')) & u.notna()
    x = u[bets].to_numpy(float)
    n = len(x)
    return dict(w=w, l=l, p=p, s=s, n=n, units=float(x.sum()) if n else 0.,
                roi=x.mean() if n else np.nan,
                se=x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan,
                cover=w / (w + l) if w + l else np.nan)


def fmt(v):
    se = f" ± {100*v['se']:.1f}" if np.isfinite(v['se']) else ''
    cover = f"{100*v['cover']:.1f}%" if np.isfinite(v['cover']) else 'n/a'
    roi = f"{100*v['roi']:+.1f}%" if np.isfinite(v['roi']) else 'n/a'
    return f"{v['w']}-{v['l']}-{v['p']} | {v['s']} | {v['n']} | {v['units']:+.2f} | {roi}{se} | {cover}"


HEAD = '| Arm | W-L-P | Skips | n | Units | ROI ± SE | Cover |\n|---|---|---|---|---|---|---|'


def baseline_table(frame, line, mapped, raw, line_mapped):
    margin = (frame.result - line).to_numpy(float)
    sides = season_ats.baseline_sides(mapped, line, raw, line_mapped)
    rows = []
    for name in season_ats.BASELINES:
        ret = season_ats.flat_returns(sides[name], margin)
        res = np.where(sides[name] == 0, 'S', np.where(ret > 0, 'W', np.where(ret < 0, 'L', 'P')))
        rows.append(f"| {name} (flat −110) | " + fmt(record(res, np.where(sides[name] == 0, 0., ret))).replace(' | ', ' | ', 5) + ' |')
    prod = season_ats.flat_returns(sides[season_ats.BASELINES[0]], margin)
    paired = []
    for control in ('Line-only map', 'Raw model spread', 'Always favorite'):
        other = season_ats.flat_returns(sides[control], margin)
        d = prod - other
        differ = int((sides[season_ats.BASELINES[0]] != sides[control]).sum())
        paired.append(f"- Median map minus {control.lower()}: sides differ on {differ} of {len(d)}; "
                      f"{d.sum():+.2f}u, per game {d.mean():+.3f} ± {d.std(ddof=1)/np.sqrt(len(d)):.3f} (1 SE).")
    return [HEAD] + rows, paired


def main(data='data'):
    latest, pool = load(data)
    revision = latest['manifest']['revision']
    frame = replay(latest, pool)
    pub = pool.set_index('game_id')
    frame['public_basis'] = frame.game_id.map(pub.ats_basis)
    frame['public_side'] = frame.game_id.map(pub.fixed_band_ats_side)
    frame['public_line'] = frame.game_id.map(pub.spread_line)
    frame['public_result'] = frame.game_id.map(pub.fixed_band_ats_result)
    frame['public_units'] = frame.game_id.map(pub.fixed_band_ats_units)
    frame['public_price_basis'] = frame.game_id.map(pub.ats_price_basis)
    frame['public_forecast_revision'] = frame.game_id.map(pub.get('forecast_revision', pd.Series(dtype=object)))
    frame['same_side'] = frame.fixed_band_ats_side.eq(frame.public_side)
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ['game_id', 'week', 'kickoff_utc', 'away', 'home', 'replay_source', 'model_wp', 'model_spread',
            'qb_replacement_margin_adjustment', 'fixed_band_spread', 'spread_line', 'line_mapped',
            'home_score', 'away_score', 'result', 'fixed_band_ats_side', 'fixed_band_ats_result',
            'ats_price', 'ats_price_basis', 'ats_quote_utc', 'ats_kickoff_check', 'fixed_band_ats_units',
            'public_basis', 'public_forecast_revision', 'public_line', 'public_side', 'public_result',
            'public_price_basis', 'public_units', 'same_side']
    frame[cols].rename(columns={'fixed_band_spread': 'v124_mapped_margin', 'fixed_band_ats_side': 'v124_side',
                                'fixed_band_ats_result': 'v124_result', 'fixed_band_ats_units': 'v124_units',
                                'model_spread': 'raw_model_spread'}).to_csv(OUT / 'games.csv', index=False)

    v = record(frame.fixed_band_ats_result, frame.fixed_band_ats_units)
    flat = record(frame.fixed_band_ats_result, np.where(frame.fixed_band_ats_result.eq('W'), 1/1.1,
                  np.where(frame.fixed_band_ats_result.eq('L'), -1., 0.)))
    pubv = record(frame.public_result, frame.public_units)
    basis = frame.ats_price_basis.value_counts().to_dict()
    lines = [f'# 2026 regrade with the current model ({revision})', '',
             f"Snapshot: `data/latest` generated {latest['manifest']['generated_utc']}, "
             f"config signature `{latest['manifest']['config_signature'][:12]}…`. "
             f'Graded games: {len(frame)} (weeks {int(frame.week.min())}–{int(frame.week.max())}); '
             'pending games are excluded.', '',
             '**Basis.** Current-season walk-forward replay of the unchanged production recipe: each week\'s '
             'forecast uses only earlier games, the weekly decayed median map is fitted before that week, and '
             'the −2 replacement-QB adjustment is applied after mapping. This is a reconstruction (evidence '
             'basis 3 in CLAUDE.md: diagnostic), not native forward evidence. The replay line is the replay '
             'ledger\'s market line, which can differ from a saved lock\'s T-60 line. Public pages are unchanged '
             '(lock continuity, 2026-11-15).', '',
             '## Headline', '', HEAD,
             f'| {revision} replay, priced | ' + fmt(v) + ' |',
             f'| {revision} replay, flat −110 | ' + fmt(flat) + ' |',
             f'| Public decisions, same games | ' + fmt(pubv) + ' |', '',
             f"Break-even cover at −110: {100*BREAK_EVEN:.1f}%. ROI ± 1 SE; pushes stay in the denominator.",
             f"Replay pricing: {basis.get('captured_prelock', 0)} ESPN quotes captured by T-60, "
             f"{basis.get('closing_estimate', 0)} closing estimates at the exact handicap, "
             f"{basis.get('assumed_minus110', 0)} assumed −110 (no ESPN price at that handicap).", '',
             '## Same-row baselines, all graded games', '']
    t, paired = baseline_table(frame, frame.spread_line.to_numpy(float), frame.fixed_band_spread.to_numpy(float),
                               frame.model_spread.to_numpy(float), frame.line_mapped.to_numpy(float))
    lines += t + [''] + paired + ['']

    lines += ['## Agreement with the public decision', '',
              f"Same side on {int(frame.same_side.sum())} of {len(frame)} games. Where the replay and the public "
              'decision differ, the public decision is a saved lock (different revision, line or inputs) or a '
              'replay under the same recipe with a different line.', '',
              '| Public basis | Games | Same side | Replay W-L-P, units | Public W-L-P, units |', '|---|---|---|---|---|']
    for name, g in frame.groupby('public_basis', sort=True):
        a, p = record(g.fixed_band_ats_result, g.fixed_band_ats_units), record(g.public_result, g.public_units)
        lines.append(f"| {name} | {len(g)} | {int(g.same_side.sum())} | {a['w']}-{a['l']}-{a['p']}, {a['units']:+.2f} | "
                     f"{p['w']}-{p['l']}-{p['p']}, {p['units']:+.2f} |")
    diff = frame.loc[~frame.same_side]
    line_moved = diff.public_line.ne(diff.spread_line)
    qb = pd.to_numeric(diff.qb_replacement_margin_adjustment, errors='coerce').fillna(0).ne(0)
    older = diff.public_forecast_revision.notna() & diff.public_forecast_revision.ne(revision)
    lines += ['', f"Of the {len(diff)} disagreements: {int(line_moved.sum())} have a different market line "
              f"(saved T-60 line vs replay line), {int(qb.sum())} carry a replay QB adjustment, and "
              f"{int(older.sum())} were saved by an earlier revision. These games: "
              + ', '.join(f"{r.game_id} (replay {r.fixed_band_ats_result}, public {r.public_result})" for r in diff.itertuples()) + '.',
              '', '**Hindsight warning.** v1.19–v1.24 (including the replacement-QB rule adopted 2026-11-13 after an '
              'audit of saved picks) were designed after weeks 7–9 were observed. The replay\'s advantage on games '
              'where it disagrees with saved locks is therefore in-sample and is not evidence that the current model '
              'would have beaten those locks forward.']
    lines += ['', '## By week (replay, priced)', '', '| Week | W-L-P | Units | Same side as public |', '|---|---|---|---|']
    for week, g in frame.groupby('week'):
        a = record(g.fixed_band_ats_result, g.fixed_band_ats_units)
        lines.append(f"| {int(week)} | {a['w']}-{a['l']}-{a['p']} | {a['units']:+.2f} | {int(g.same_side.sum())}/{len(g)} |")

    # Native forward evidence: pregame-finalized 60-minute locks only, on their own lock lines.
    native = pool.loc[pool.ats_basis.eq('60-minute lock') & pool.result.notna()].copy()
    locks = ats_locks.current_records(latest['ats_locks'], revision)
    native['raw'] = [pd.to_numeric(locks.get((revision, g), {}).get('raw_spread'), errors='coerce') for g in native.game_id]
    native['line_mapped'] = [float(fixed_bands.apply([r.spread_line], locks.get((revision, r.game_id), {}).get('fixed_rule')
                                                     or fixed_bands.rule_for(latest['fixed_band_rules'], 2026, int(r.week)))[0])
                             for r in native.itertuples()]
    nv = record(native.fixed_band_ats_result, native.fixed_band_ats_units)
    lines += ['', '## Native 60-minute locks against same-game baselines', '',
              'Forward evidence basis 1: pregame-finalized locks of every revision (lock continuity), graded on the '
              'saved lock line. Owner-requested retro and recovered locks are excluded here.', '', HEAD,
              '| Saved native locks, priced | ' + fmt(nv) + ' |']
    t, paired = baseline_table(native, native.spread_line.to_numpy(float), native.fixed_band_spread.to_numpy(float),
                               native.raw.to_numpy(float), native.line_mapped.to_numpy(float))
    lines += t[1:] + [''] + paired
    revs = native.forecast_revision.value_counts().to_dict()
    lines += ['', 'Native locks by saving revision: ' + ', '.join(f'{k.split("-")[-1]} {v}' for k, v in sorted(revs.items()))
              + f". n = {nv['n']} decided of the 100 needed for the map-versus-raw review.", '',
              '## Limits', '',
              '- Replay rows have no saved pregame timestamp; most are priced at the closing price for the exact '
              'handicap or an assumed −110. They are not lock-time returns.',
              '- The recipe was selected on earlier seasons; 2026 is walk-forward but the model design was exposed '
              'to it. Per-band and per-week records are descriptive.',
              '- Intervals crossing zero leave the effect unresolved; they do not show it is zero.']
    (OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
