"""Fixed earlier-season pressure study; see PRESSURE_MARGIN.md. No live-model imports.

python research/pressure_margin.py --prepare --raw-dir /path/to/nflverse/csvs
python research/pressure_margin.py
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'research/pressure_inputs'
OUTPUT = ROOT / 'research/pressure_margin_results'
EXTRA = ['pressure_allowed_diff', 'pressure_generated_diff', 'pressure_matchup']
ALIASES = {'STL': 'LA', 'LAR': 'LA', 'SD': 'LAC', 'OAK': 'LV'}


def normalize(s):
    return s.replace(ALIASES)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download_sources(raw_dir):
    """Fetch missing raw inputs; existing snapshots are deliberately never overwritten."""
    raw_dir.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for season in range(2018,2027):
        for tag,name in [('pfr_advstats',f'advstats_week_pass_{season}.csv'),('pbp',f'play_by_play_{season}.csv.gz')]:
            jobs.append((name,f'https://github.com/nflverse/nflverse-data/releases/download/{tag}/{name}'))
    def fetch(job):
        name,url=job;path=raw_dir/name
        if path.exists():return
        with urllib.request.urlopen(url,timeout=120) as response,open(path,'wb') as out:
            while True:
                block=response.read(1024*1024)
                if not block:break
                out.write(block)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch,jobs))


def prepare(raw_dir):
    """Freeze pressures and independent opportunities; never infer missing pressure as zero."""
    INPUT.mkdir(parents=True, exist_ok=True)
    parts, audit = [], []
    for season in range(2018, 2027):
        pp = raw_dir / f'advstats_week_pass_{season}.csv'
        bp = raw_dir / f'play_by_play_{season}.csv.gz'
        p = pd.read_csv(pp)
        p = p[p.game_type.eq('REG')].copy()
        for col in ['team', 'opponent']:
            p[col] = normalize(p[col])
        if p.duplicated(['game_id', 'team', 'pfr_player_id']).any():
            raise ValueError('Duplicate passer-game pressure rows')
        if p[['times_pressured', 'times_pressured_pct']].isna().any().any():
            raise ValueError('Missing pressure data')
        cols = ['game_id', 'season_type', 'week', 'posteam', 'defteam', 'play_type',
                'pass_attempt', 'sack', 'qb_scramble', 'two_point_attempt', 'play_deleted']
        chunks = []
        for f in pd.read_csv(bp, usecols=lambda c: c in cols, chunksize=25000, low_memory=False):
            valid = f.season_type.eq('REG') & f.posteam.notna() & ~f.play_type.eq('no_play')
            valid &= ~f.two_point_attempt.eq(1)
            if 'play_deleted' in f:
                valid &= ~f.play_deleted.eq(1)
            f = f.loc[valid].copy()
            f['opportunities'] = (f.pass_attempt.eq(1) | f.sack.eq(1) | f.qb_scramble.eq(1)).astype(int)
            chunks.append(f.groupby(['game_id', 'week', 'posteam', 'defteam'], as_index=False).opportunities.sum())
        counts = pd.concat(chunks).groupby(['game_id', 'week', 'posteam', 'defteam'], as_index=False).opportunities.sum()
        counts = counts.rename(columns={'posteam': 'team', 'defteam': 'opponent'})
        counts['team'], counts['opponent'] = normalize(counts.team), normalize(counts.opponent)
        g = p.groupby(['game_id', 'season', 'week', 'team', 'opponent'], as_index=False).times_pressured.sum()
        g = g.merge(counts, how='outer', on=['game_id', 'week', 'team', 'opponent'], validate='one_to_one', indicator=True)
        missing = g[g._merge.ne('both')]
        if len(missing) and season < 2026:
            raise ValueError(f'{season}: unmatched pressure/opportunity team games: {missing.to_dict("records")}')
        missing_ids = sorted(missing.game_id.unique().tolist())
        # The latest PBP may precede pressure publication. Preserve the coverage gap;
        # never fill its missing numerator with zero or pretend it was available.
        g = g[g._merge.eq('both')].drop(columns='_merge')
        if (g.opportunities.le(0) | g.times_pressured.lt(0) | g.times_pressured.gt(g.opportunities)).any():
            raise ValueError('Invalid pressure opportunities')
        if not g.groupby('game_id').size().eq(2).all():
            raise ValueError('Game missing one team')
        opponent = g[['game_id', 'team', 'opponent', 'times_pressured', 'opportunities']].rename(
            columns={'team': 'opponent', 'opponent': 'team', 'times_pressured': 'generated', 'opportunities': 'def_opportunities'})
        g = g.merge(opponent, on=['game_id', 'team', 'opponent'], validate='one_to_one')
        # Report discrepancies for one-passer games; PFR and PBP conventions may differ.
        single = p.groupby(['game_id', 'team']).filter(lambda f: len(f) == 1)
        check = single.merge(g[['game_id', 'team', 'opportunities']], on=['game_id', 'team'], validate='one_to_one')
        discrepancy = abs(check.times_pressured / check.opportunities - check.times_pressured_pct)
        audit.append(dict(season=season, games=int(g.game_id.nunique()), team_games=len(g),
                          max_week=int(g.week.max()), missing_team_games=len(missing), missing_game_ids=missing_ids,
                          single_passer_rate_diff_median=float(discrepancy.median()),
                          single_passer_rate_diff_max=float(discrepancy.max()),
                          single_passer_games=len(check),
                          single_passer_rate_diff_gt_005=int(discrepancy.gt(.005).sum()),
                          pressure_sha256=sha(pp), opportunities_sha256=sha(bp)))
        parts.append(g)
    g = pd.concat(parts, ignore_index=True).sort_values(['season', 'week', 'game_id', 'team'])
    g.to_csv(INPUT / 'team_games.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    (INPUT / 'coverage.json').write_text(json.dumps(audit, indent=2) + '\n')


def forecasts():
    if (INPUT / 'base_forecasts.csv').exists():
        return pd.read_csv(INPUT / 'base_forecasts.csv')
    h = pd.read_csv(ROOT / 'data/latest/fixed_band_ledger.csv')
    h = h[h.season.lt(2026) & h.fixed_band_spread.notna()].copy()
    h['prediction'] = h.fixed_band_spread
    # Frozen user-facing season snapshot is separate from reconstructed history.
    c = pd.read_csv(INPUT / 'ats_2026_results.csv')
    c = c[c.ats_status.eq('graded')].copy()
    c['prediction'] = c.model_spread
    cols = ['game_id', 'season', 'week', 'home', 'away', 'result', 'spread_line', 'prediction']
    f = pd.concat([h[cols], c[cols]], ignore_index=True).sort_values(['season', 'week', 'game_id'])
    if f.game_id.duplicated().any() or f[cols].isna().any().any():
        raise ValueError('Missing or duplicate base forecasts')
    return f.reset_index(drop=True)


def eligible(g, season, week, lag):
    return ((g.season.lt(season)) | (g.season.eq(season) & g.week.le(week - lag))) & g.season.ge(season - 5)


def profiles(f, g, lag):
    rows = []
    for (season, week), batch in f.groupby(['season', 'week'], sort=True):
        hist = g[eligible(g, season, week, lag)]
        if hist.empty:
            raise ValueError('No earlier pressure history')
        league_p = hist.times_pressured.sum() / hist.opportunities.sum()
        league_n = hist.opportunities.mean()
        team = {}
        for t in set(batch.home) | set(batch.away):
            q = hist[hist.team.eq(t)].sort_values(['season', 'week', 'game_id'])
            if q.empty:
                raise ValueError(f'No pressure history for {t}')
            age = np.arange(len(q) - 1, -1, -1)
            w = np.exp2(-age / 8) * .5 ** (season - q.season.to_numpy())
            allowed = (w @ q.times_pressured + 4 * league_n * league_p) / (w @ q.opportunities + 4 * league_n)
            generated = (w @ q.generated + 4 * league_n * league_p) / (w @ q.def_opportunities + 4 * league_n)
            team[t] = ((allowed - league_p) / .05, (generated - league_p) / .05, len(q))
        last = hist.sort_values(['season', 'week']).iloc[-1]
        for r in batch.itertuples():
            ha, hd, hn = team[r.home]
            aa, ad, an = team[r.away]
            rows.append(dict(game_id=r.game_id, pressure_allowed_diff=ha-aa,
                             pressure_generated_diff=hd-ad, pressure_matchup=ha*ad-aa*hd,
                             home_pressure_allowed=ha*.05+league_p, away_pressure_allowed=aa*.05+league_p,
                             home_pressure_generated=hd*.05+league_p, away_pressure_generated=ad*.05+league_p,
                             source_max_season=int(last.season), source_max_week=int(last.week),
                             home_history_n=hn, away_history_n=an, lag_weeks=lag))
    return f.merge(pd.DataFrame(rows), on='game_id', validate='one_to_one')


def fit(train, offset, extra, columns=None):
    columns = EXTRA if columns is None else columns
    required=['result',offset]+(columns if extra else [])
    if len(train) <= 1+(len(columns) if extra else 0) or not np.isfinite(train[required].to_numpy(float)).all():
        raise ValueError('Insufficient or nonfinite fit inputs')
    residual = train.result.to_numpy() - train[offset].to_numpy()
    if extra:
        raw = train[columns].to_numpy(float)
        mu, scale = raw.mean(axis=0), raw.std(axis=0)
        scale[scale < 1e-8] = 1
        x = np.column_stack([np.ones(len(train)), (raw - mu) / scale])
    else:
        mu, scale = np.zeros(len(columns)), np.ones(len(columns))
        x = np.ones((len(train), 1))
    penalty = np.diag([0.] + ([10.] * len(columns) if extra else []))
    coef = np.linalg.solve(x.T @ x + penalty, x.T @ residual)
    error = residual - x @ coef
    sigma = float(np.sqrt(error @ error / (len(train) - x.shape[1])))
    return dict(coef=coef, mu=mu, scale=scale, sigma=sigma, columns=columns)


def predict(f, offset, fitted):
    coef = fitted['coef']
    x = np.ones((len(f), 1)) if len(coef) == 1 else np.column_stack([
        np.ones(len(f)), (f[fitted['columns']].to_numpy() - fitted['mu']) / fitted['scale']])
    return f[offset].to_numpy() + x @ coef


def cover_probability(mean, sigma, line):
    """Round a continuous normal to integer football margins; exclude push mass."""
    line = np.asarray(line)
    upper = np.floor(line) + .5
    lower = np.ceil(line) - .5
    home = ndtr((np.asarray(mean) - upper) / sigma)
    away = ndtr((lower - np.asarray(mean)) / sigma)
    return np.clip(home / (home + away), 1e-6, 1-1e-6)


def picked_side(mean, line):
    return np.where(mean > line, 1, np.where(mean < line, -1, np.sign(line)))


def score(frame):
    d = frame.result - frame.spread_line
    dec = d.ne(0)
    y = d[dec].gt(0).astype(float).to_numpy()
    p = frame.loc[dec, 'p_home_cover'].to_numpy()
    side = picked_side(frame['mean'], frame.spread_line)
    pick_margin = d.to_numpy() * side
    win, loss, push, skip = pick_margin > 0, pick_margin < 0, (pick_margin == 0) & (side != 0), side == 0
    u = np.where(win, 100/110, np.where(loss, -1., 0.))
    n = int((~skip).sum())
    error = frame.result - frame['mean']
    return dict(n=len(frame), bets=n, wins=int(win.sum()), losses=int(loss.sum()), pushes=int(push.sum()), skips=int(skip.sum()),
                cover_rate=float(win.sum() / max(1, (win | loss).sum())), units=float(u.sum()),
                roi=float(u.sum()/n), roi_se=float(u[~skip].std(ddof=1)/np.sqrt(n)),
                mae=float(abs(error).mean()), rmse=float(np.sqrt((error**2).mean())),
                cover_n=int(dec.sum()), log_loss=float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean()),
                brier=float(((y-p)**2).mean()), mean_home_cover_probability=float(p.mean()),
                observed_home_cover=float(y.mean()))


def bootstrap(base, arm, reps=10000):
    d = pd.DataFrame({'season': base.season, 'week': base.week})
    d['mae_gain'] = abs(base.result-base['mean']) - abs(arm.result-arm['mean'])
    y = (base.result > base.spread_line).astype(float)
    ll = lambda f: -(y*np.log(f.p_home_cover)+(1-y)*np.log1p(-f.p_home_cover))
    d['ll_gain'] = (ll(base)-ll(arm)).where(base.result.ne(base.spread_line))
    rng = np.random.default_rng(20261113)
    groups = []
    for season, q in d.groupby('season'):
        ag = q.groupby('week').agg(mae_sum=('mae_gain','sum'), n=('mae_gain','size'), ll_sum=('ll_gain','sum'), nd=('ll_gain','count'))
        groups.append(ag.to_numpy())
    vals = np.zeros((reps, 4))
    for a in groups:
        vals += a[rng.integers(0, len(a), size=(reps, len(a)))].sum(axis=1)
    return dict(mae_gain=float(d.mae_gain.mean()), mae_gain_ci95=np.quantile(vals[:,0]/vals[:,1], [.025,.975]).tolist(),
                log_loss_gain=float(d.ll_gain.mean()), log_loss_gain_ci95=np.quantile(vals[:,2]/vals[:,3], [.025,.975]).tolist())


def write_report(output, label, metrics, comparisons):
    title = {'pressure':'Pressure allowed/generated and matchup','scoring':'Scoring opportunities and finishing',
             'punts':'Punts per possession and defensive forced-punt rate',
             'ppp':'Points per possession for and allowed'}[label]
    candidate='model_'+label
    lines=[f'# {title}: earlier-season margin study', '',
           '**Decision: retain for research; no production adoption supported.**', '',
           'Basis: exposed historical reconstruction, not native forward evidence. Coefficients are pooled across all teams,',
           'fitted on 2023 for 2024, 2023-24 for 2025, and 2023-25 for the separate 2026 diagnostic.',
           'Primary source lag is two week indices; one-week sensitivity was fixed in advance. No ROI-selected settings.', '',
           'All ATS returns below risk 1u at assumed -110; these differ from the public page\'s mixed-price returns.',
           'Cover probability is a research discretized-Gaussian margin approximation, conditioned on no push,',
           'not an existing saved production probability. Its scale is fitted on prior-season training residuals.', '',
           'The intercept-only control separates adding the new statistics from merely recalibrating the base margin.',
           'The original model retains its original mapped margin without this intercept adjustment.', '',
           '## Primary and current-season comparisons', '',
           '| Cohort | Arm | n | ATS W-L-P | Units | ROI ± SE | MAE | RMSE | Cover LL | Brier |',
           '|---|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for cohort in ['2024-25','2026']:
        for arm in ['model_original','model_control',candidate,'market_original','market_control','market_'+label,'always_home','fair_cover']:
            r=next(v for v in metrics if v['lag']==2 and v['cohort']==cohort and v['arm']==arm)
            mae='—' if r['mae'] is None else f"{r['mae']:.4f}"
            rmse='—' if r['rmse'] is None else f"{r['rmse']:.4f}"
            lines.append(f"| {cohort} | {arm} | {r['n']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} pp | {mae} | {rmse} | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines += ['', 'Market_original is the same-row always-favorite action baseline. Always-home has no margin forecast.',
              'Fair_cover is a .5 probability benchmark; its displayed action uses the same favorite-on-zero-edge convention.',
              'Cover rates exclude pushes; ROI includes pushes; skip counts and cover rates are in metrics.csv.', '',
              '## Annual original/control/challenger', '', '| Season | Arm | MAE | Cover LL | ATS W-L-P |', '|---|---|---:|---:|---|']
    for cohort in ['2024','2025','2026']:
        for arm in ['model_original','model_control',candidate]:
            r=next(v for v in metrics if v['lag']==2 and v['cohort']==cohort and v['arm']==arm)
            lines.append(f"| {cohort} | {arm} | {r['mae']:.4f} | {r['log_loss']:.6f} | {r['wins']}-{r['losses']}-{r['pushes']} |")
    lines += ['', '## Increment over the intercept-only control', '',
              'Positive gain favors the new statistics. Paired whole-week bootstrap within season, 10,000 draws.',
              ('These are nominal 95% intervals, not corrected for the multiple feature families or prior research selection.' if label in ['punts','ppp']
               else 'These are nominal 95% intervals, not corrected for both feature families or prior research selection.'), '',
              '| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |', '|---|---|---|---|']
    for r in comparisons:
        if r['lag']!=2 or r['cohort'] not in ['2024-25','2026']:continue
        a,b=r['mae_gain_ci95'];c,d=r['log_loss_gain_ci95']
        lines.append(f"| {r['cohort']} | {r['comparison']} | {r['mae_gain']:+.4f} [{a:+.4f}, {b:+.4f}] | {r['log_loss_gain']:+.6f} [{c:+.6f}, {d:+.6f}] |")
    lines += ['', '## Fixed one-week-lag sensitivity', '', '| Cohort | Arm | MAE | Cover LL | ATS W-L-P |', '|---|---|---:|---:|---|']
    for r in metrics:
        if r['lag']==1 and r['cohort'] in ['2024-25','2026'] and r['arm']==candidate:
            lines.append(f"| {r['cohort']} | {r['arm']} | {r['mae']:.4f} | {r['log_loss']:.6f} | {r['wins']}-{r['losses']}-{r['pushes']} |")
    lines += ['', '## Audit and limits', '',
              '- Frozen forecasts and input hashes are in ../pressure_inputs; feature-source coverage is in the corresponding input directory.',
              '- All source statistics precede the prediction by the declared lag; fit labels are from earlier seasons only.',
              '- Historical source files were revised after games. Asset modification time is not original row publication time.',
              '  The lag is a conservative assumption, not proof of point-in-time availability. Latest PBP has week-10 2026 data',
              '  while PFR pressure ends in week 9; missing pressure is excluded, never treated as zero.',
              '- PBP-defined opportunities and rounded PFR pressure percentages mostly agree; convention mismatches are counted in pressure_inputs/coverage.json.',
              '- Reliability by five fixed probability bins is in reliability.csv. Pick accuracy is not calibration.',
              '- Only two full evaluation seasons and a partially completed current season are available under the comparable mapped base.',
              '- No production fit, notebook, lock, journal, public page or betting policy is modified.', '']
    if label=='scoring':
        lines += ['Fourth-down decision features measure contextual aggressiveness, not optimal go/punt/FG regret.',
                  'Fourth-down execution conditions on selected attempts. True counterfactual decision values remain unimplemented.', '']
    elif label=='pressure':
        lines += ['The three pressure coefficients and standardization values are in fits.json. The matchup coefficient changes sign',
                  'between annual fits; its contribution is not independently established by this joint three-term experiment.', '']
    elif label=='punts':
        lines += ['This is a two-feature drive-stall study: offensive punts per possession and defensive punts forced per opponent possession.',
                  'It does not measure punt quality, return value, kicking accuracy or starting field position.',
                  'Turnovers and failed fourth downs can lower offensive punt rate without improving the offense.', '']
    elif label=='ppp':
        lines += ['This isolates offensive points per possession and opponent offensive points allowed per opponent possession.',
                  'It excludes defensive/return touchdowns and is not adjusted for opponents, game state or starting field position.',
                  'It is separate from the earlier finishing bundle, which also fitted red-zone and fourth-down terms.', '']
    command={'pressure':'pressure_margin.py','scoring':'scoring_finishing.py','punts':'punts_per_possession.py',
             'ppp':'points_per_possession.py'}[label]
    lines += ['## Reproduce', '', '```sh',
              'python research/'+command,
              '```', '', 'This uses committed frozen aggregate inputs. See the protocol for raw reconstruction and source definitions.', '']
    (output/'REPORT.md').write_text('\n'.join(lines))


def run(frame_builder=None, output=None, extra_columns=None, feature_label='pressure'):
    output = OUTPUT if output is None else output
    output.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(INPUT / 'team_games.csv.gz')
    f = forecasts()
    forecasts_out, fits = [], []
    for lag in [2, 1]:
        z = profiles(f, g, lag) if frame_builder is None else frame_builder(f, lag)
        for season in [2024, 2025, 2026]:
            train, test = z[z.season.lt(season)], z[z.season.eq(season)].copy()
            assert train.season.max() < season
            for name, offset, extra in [('model_control','prediction',False), ('model_'+feature_label,'prediction',True),
                                        ('market_control','spread_line',False), ('market_'+feature_label,'spread_line',True)]:
                fitted = fit(train, offset, extra, extra_columns)
                a = test.copy()
                a['mean'] = predict(test, offset, fitted)
                a['p_home_cover'] = cover_probability(a['mean'], fitted['sigma'], a.spread_line)
                a['arm'] = name
                forecasts_out.append(a)
                fits.append(dict(lag=lag, season=season, arm=name, training_n=len(train),
                                 training_max_season=int(train.season.max()),
                                 feature_names=['intercept']+(fitted['columns'] if extra else []),
                                 sigma=fitted['sigma'], **{k:fitted[k].tolist() for k in ['coef','mu','scale']}))
            # Raw offsets use the control's training sigma, without intercept adjustment.
            for name, offset in [('model_original','prediction'), ('market_original','spread_line')]:
                fitted = fit(train, offset, False)
                a = test.copy(); a['mean'] = a[offset]
                a['p_home_cover'] = cover_probability(a['mean'], fitted['sigma'], a.spread_line)
                a['arm'] = name; forecasts_out.append(a)
            a = test.copy(); a['mean'] = a.spread_line; a['p_home_cover'] = .5; a['arm'] = 'fair_cover'; forecasts_out.append(a)
    pred = pd.concat(forecasts_out, ignore_index=True)
    metrics, reliability, comparisons = [], [], []
    for lag in [2, 1]:
        for cohort, seasons in [('2024',[2024]),('2025',[2025]),('2024-25',[2024,2025]),('2026',[2026])]:
            q = pred[pred.lag_weeks.eq(lag) & pred.season.isin(seasons)]
            for arm, a in q.groupby('arm'):
                metrics.append(dict(lag=lag, cohort=cohort, arm=arm, **score(a)))
                a = a[a.result.ne(a.spread_line)].copy()
                a['bin'] = pd.cut(a.p_home_cover, [0,.2,.4,.6,.8,1], include_lowest=True)
                for band, b in a.groupby('bin', observed=True):
                    reliability.append(dict(lag=lag,cohort=cohort,arm=arm,band=str(band),n=len(b),
                                            predicted=float(b.p_home_cover.mean()),observed=float((b.result>b.spread_line).mean())))
            home = q[q.arm.eq('market_original')].copy()
            home['mean'] = home.spread_line + 1  # Force home on every row, including pick'em.
            home['p_home_cover'] = .5
            home_metrics = score(home)
            home_metrics.update(mae=None, rmse=None)  # An action baseline has no margin forecast.
            metrics.append(dict(lag=lag,cohort=cohort,arm='always_home',**home_metrics))
            for off in ['model','market']:
                base=q[q.arm.eq(off+'_control')].sort_values('game_id').reset_index(drop=True)
                arm=q[q.arm.eq(off+'_'+feature_label)].sort_values('game_id').reset_index(drop=True)
                assert base.game_id.equals(arm.game_id)
                comparisons.append(dict(lag=lag,cohort=cohort,comparison=off+'_'+feature_label+'_minus_control',**bootstrap(base,arm)))
    pred.to_csv(output/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(metrics).to_csv(output/'metrics.csv',index=False)
    pd.DataFrame(reliability).to_csv(output/'reliability.csv',index=False)
    (output/'fits.json').write_text(json.dumps(fits,indent=2)+'\n')
    (output/'comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    write_report(output,feature_label,metrics,comparisons)
    # Freeze the exact base forecast rows used, independent of future bot updates.
    f.to_csv(INPUT/'base_forecasts.csv',index=False)
    print(pd.DataFrame(metrics).query('lag == 2')[['cohort','arm','n','mae','rmse','log_loss','brier','wins','losses','pushes','units']].to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--download', action='store_true',help='Download missing raw inputs before preparation')
    parser.add_argument('--raw-dir', type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.raw_dir is None:
            parser.error('--prepare requires --raw-dir')
        if args.download:download_sources(args.raw_dir)
        prepare(args.raw_dir)
    elif args.download:
        parser.error('--download requires --prepare and --raw-dir')
    run()
