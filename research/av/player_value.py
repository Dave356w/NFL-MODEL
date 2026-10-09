"""rAV: a per-game reconstruction of PFR-style Approximate Value, and its pregame estimator.

NOT PFR AV. PFR publishes AV per season only and its pages are unreachable here (see prepare_data).
rAV follows PFR's published allocation scheme (Drinen 2008) at game level, so that an as-of-week value
can be built from games completed before kickoff instead of retro-allocating a final-season total:

  team offensive pool  = POOL x offensive points / league offensive points per team-game
  team defensive pool  = POOL x max(0, 2 - opponent offensive points / league)
      (league mean from the PREVIOUS season, known before any game of the season; the first season
       of data uses its own mean, which only feeds priors several seasons before any target)
  offense: 5/11 to the offensive line by offensive snaps; 6/11 to skill players, split between
           rushing and passing by the team's yards; rushing to rushers by rushing yards, passing
           26% to passers by passing yards and 74% to receivers by receiving yards
  defense: 2/3 to the front seven (DL+LB), 1/3 to defensive backs; within each half by defensive
           snaps and half by an impact score (tackles, sacks, TFL, hits, INT, PD, forced fumbles)
  POOL = 100/16: a league-average team earns ~100 rAV per side over 16 games, as in PFR.
  Special teams (K, P, LS, returners) are not modelled.

Units. Every player-game carries rAV and an opportunity `share` (fraction of his side's team snaps,
0-1). A RATE is rAV per full game (sum rAV / sum share), so rate x projected share is rAV for the
game. Season rAV ~= 17 x rate for a full-time player. Replacement levels are rates too.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from prepare_data import DEF_UNITS, OFF_UNITS, UNITS

POOL = 100. / 16.
OL_SHARE = 5. / 11.
PASSER_SHARE = .26
FRONT_SHARE = 2. / 3.
HISTORY_SEASONS = 3
SEASON_RETENTION = .5       # same offseason discount as nfl_model.OFFSEASON_RETENTION
PRIOR_GAMES = 4.            # shrinkage toward the positional prior, in full-game equivalents
YTD_FIRST_WEEK = 5          # blended estimator: current-season games count from week 5
REPLACEMENT_QUANTILE = .25
REPLACEMENT_MIN_GAMES = 4.  # full-game equivalents for a player-season to define replacement level
ROOKIE_MIN_GAMES = 1.
IMPACT = {'def_tackles_solo': 1., 'def_tackle_assists': .5, 'def_sacks': 2., 'def_tackles_for_loss': 1.,
          'def_qb_hits': .5, 'def_interceptions': 4., 'def_pass_defended': 1.5, 'def_fumbles_forced': 2.}


def league_means(tg):
    """season -> league mean offensive points per team-game of the PREVIOUS season."""
    own = tg.groupby('season').off_points.mean()
    return {int(s): float(own.get(s - 1, own[s])) for s in own.index}


def _split(values, pool):
    v = np.clip(np.asarray(values, float), 0, None); t = v.sum()
    return v / t * pool if t > 0 else np.zeros(len(v))


def game_rav(pg, tg):
    """rAV for every player-game. Uses only that game's box score and the prior-season league mean."""
    lg = league_means(tg)
    t = tg.set_index(['game_id', 'team'])
    out = np.zeros(len(pg))
    pg = pg.reset_index(drop=True)
    for (gid, team), ix in pg.groupby(['game_id', 'team']).indices.items():
        if (gid, team) not in t.index: continue
        r = t.loc[(gid, team)]
        g = pg.iloc[ix]; base = lg[int(r.season)]
        off = POOL * r.off_points / base
        dfn = POOL * max(0., 2. - r.opp_off_points / base) if pd.notna(r.opp_off_points) else 0.
        v = np.zeros(len(g)); u = g.unit.to_numpy()
        ol = u == 'OL'
        v[ol] += _split(g.off_snaps.to_numpy()[ol], OL_SHARE * off)
        skill = (1 - OL_SHARE) * off
        py, ry = max(g.passing_yards.sum(), 0.), max(g.rushing_yards.sum(), 0.)
        pf = py / (py + ry) if py + ry > 0 else .5
        v += _split(g.rushing_yards.to_numpy(), (1 - pf) * skill)
        v += _split(g.passing_yards.to_numpy(), pf * skill * PASSER_SHARE)
        v += _split(g.receiving_yards.to_numpy(), pf * skill * (1 - PASSER_SHARE))
        imp = sum(w * g[c].to_numpy(float) for c, w in IMPACT.items())
        for grp, pool in (((u == 'DL') | (u == 'LB'), FRONT_SHARE * dfn), (u == 'DB', (1 - FRONT_SHARE) * dfn)):
            if not grp.any(): continue
            snaps = g.def_snaps.to_numpy()[grp]
            if imp[grp].sum() > 0:
                v[grp] += _split(snaps, .5 * pool) + _split(imp[grp], .5 * pool)
            else:
                v[grp] += _split(snaps, pool)
        out[ix] = v
    return pg.assign(rav=out)


def season_table(pgv):
    """(gsis_id, season) totals: rAV, full-game equivalents, modal unit, games with snaps."""
    d = pgv[pgv.unit.notna()]
    s = d.groupby(['gsis_id', 'season']).agg(rav=('rav', 'sum'), games=('share', 'sum'),
                                             appearances=('share', lambda x: int((x > 0).sum()))).reset_index()
    mode = (d.groupby(['gsis_id', 'season', 'unit']).share.sum().reset_index()
             .sort_values('share').drop_duplicates(['gsis_id', 'season'], keep='last')[['gsis_id', 'season', 'unit']])
    s = s.merge(mode, on=['gsis_id', 'season'])
    s['rate'] = np.where(s.games > 0, s.rav / s.games.where(s.games > 0, 1), np.nan)
    return s


def replacement_levels(seasons, year):
    """unit -> 25th percentile of player-season rates in the HISTORY_SEASONS before `year` (rates
    are rAV per full game, the same unit as the projected values they are subtracted from)."""
    h = seasons[(seasons.season < year) & (seasons.season >= year - HISTORY_SEASONS) & (seasons.games >= REPLACEMENT_MIN_GAMES)]
    return {u: float(h[h.unit == u].rate.quantile(REPLACEMENT_QUANTILE)) if (h.unit == u).any() else 0. for u in UNITS}


def rookie_priors(seasons, draft, rookie_season, year):
    """Position-specific draft-capital prior fitted ONLY on cohorts whose rookie season is before `year`:
    rate = a_u ln(pick) + b_u (WLS, weight = full games), plus an undrafted mean and a veteran mean
    (players past their rookie year, HISTORY_SEASONS before `year`). Returns {unit: dict}."""
    dmap = draft.set_index('gsis_id')
    s = seasons[seasons.season < year].copy()
    s['rookie'] = [rookie_season.get(p) == y or (p in dmap.index and dmap.at[p, 'draft_year'] == y)
                   for p, y in zip(s.gsis_id, s.season)]
    s['pick'] = s.gsis_id.map(dmap.pick) if len(dmap) else np.nan
    out = {}
    for u in UNITS:
        r = s[s.rookie & (s.unit == u) & (s.games >= ROOKIE_MIN_GAMES)]
        dr = r[r.pick.notna()]
        vet = s[~s.rookie & (s.unit == u) & (s.season >= year - HISTORY_SEASONS) & (s.games > 0)]
        vet_mean = float(np.average(vet.rate, weights=vet.games)) if len(vet) else 0.
        a, b = 0., vet_mean
        if len(dr) >= 10:
            X = np.c_[np.log(dr.pick.to_numpy(float)), np.ones(len(dr))]; w = dr.games.to_numpy(float)
            a, b = np.linalg.lstsq(X * np.sqrt(w)[:, None], dr.rate.to_numpy() * np.sqrt(w), rcond=None)[0]
        ud = r[r.pick.isna()]
        out[u] = {'a': float(a), 'b': float(b), 'n_drafted': int(len(dr)), 'vet': vet_mean,
                  'undrafted': float(np.average(ud.rate, weights=ud.games)) if len(ud) else vet_mean,
                  'max_pick': float(dr.pick.max()) if len(dr) else 260.}
    return out


@dataclass
class Estimator:
    """Pregame rate for (player, season, week). mode 'prior': seasons before `year` only, every week.
    mode 'blend': plus completed games of `year` with week < `week`, from YTD_FIRST_WEEK on.
    Both shrink toward the player's positional prior with PRIOR_GAMES full-game equivalents:
        rate = (sum_s rho^(y-1-s) rAV_s [+ rAV_ytd] + k mu0) / (sum_s rho^(y-1-s) G_s [+ G_ytd] + k)
    which is the (1-w) prior + w YTD blend with w = G_ytd / (history + G_ytd + k)."""
    pgv: pd.DataFrame
    seasons: pd.DataFrame
    draft: pd.DataFrame
    rookie_season: dict
    _season: dict = field(default_factory=dict, init=False)
    _games: dict = field(default_factory=dict, init=False)
    _priors: dict = field(default_factory=dict, init=False)
    _rep: dict = field(default_factory=dict, init=False)
    _cache: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._season = {(p, int(s)): (r, g) for p, s, r, g in
                        zip(self.seasons.gsis_id, self.seasons.season, self.seasons.rav, self.seasons.games)}
        d = self.pgv[self.pgv.unit.notna()].sort_values(['season', 'week'])
        for (p, s), g in d.groupby(['gsis_id', 'season']):
            self._games[(p, int(s))] = (g.week.to_numpy(), np.cumsum(g.rav.to_numpy()), np.cumsum(g.share.to_numpy()))
        self._draft = self.draft.set_index('gsis_id')

    def priors(self, year):
        if year not in self._priors:
            self._priors[year] = rookie_priors(self.seasons, self.draft, self.rookie_season, year)
        return self._priors[year]

    def replacement(self, year):
        if year not in self._rep: self._rep[year] = replacement_levels(self.seasons, year)
        return self._rep[year]

    def prior_mean(self, pid, unit, year):
        """(mu0, source). Rookies: draft-capital fit (or the undrafted mean); everyone else: veteran mean."""
        pr = self.priors(year)[unit]
        rk = self.rookie_season.get(pid)
        drafted = pid in self._draft.index
        if drafted and int(self._draft.at[pid, 'draft_year']) == year:
            pick = min(float(self._draft.at[pid, 'pick']), pr['max_pick'])
            return pr['a'] * np.log(pick) + pr['b'], 'rookie_draft'
        if not drafted and (rk == year):
            return pr['undrafted'], 'rookie_undrafted'
        return pr['vet'], 'veteran_prior'

    def ytd(self, pid, year, week):
        g = self._games.get((pid, year))
        if g is None: return 0., 0.
        i = np.searchsorted(g[0], week, side='left')  # games strictly before `week`
        return (float(g[1][i - 1]), float(g[2][i - 1])) if i > 0 else (0., 0.)

    def rate(self, pid, unit, year, week, mode='blend'):
        key = (pid, unit, year, week if mode == 'blend' and week >= YTD_FIRST_WEEK else 0, mode)
        if key in self._cache: return self._cache[key]
        mu0, src = self.prior_mean(pid, unit, year)
        num = den = 0.
        for s in range(year - HISTORY_SEASONS, year):
            r, g = self._season.get((pid, s), (0., 0.))
            w = SEASON_RETENTION ** (year - 1 - s); num += w * r; den += w * g
        if den > 0 and src == 'veteran_prior': src = 'history'
        if mode == 'blend' and week >= YTD_FIRST_WEEK:
            r, g = self.ytd(pid, year, week); num += r; den += g
        out = ((num + PRIOR_GAMES * mu0) / (den + PRIOR_GAMES), den, src)
        self._cache[key] = out
        return out


def weighted_career(rates_by_season):
    """PFR's weighted career AV: 100% of the best season, 95% of the next, 90% ..."""
    v = sorted(rates_by_season, reverse=True)
    return float(sum(x * max(0., 1 - .05 * i) for i, x in enumerate(v)))


def validate_against_pfr(seasons, draft, first_class=2013, last_class=2021):
    """Correlate reconstructed weighted-career rAV with nflverse's PFR career w_av for drafted players
    whose whole career falls inside the rAV window. VALIDATION ONLY: w_av is never a feature."""
    d = draft[(draft.draft_year >= first_class) & (draft.draft_year <= last_class) & draft.w_av.notna()]
    tot = seasons.groupby('gsis_id').rav.apply(lambda x: weighted_career(x.tolist()))
    unit = seasons.sort_values('games').drop_duplicates('gsis_id', keep='last').set_index('gsis_id').unit
    d = d.assign(rav_w=d.gsis_id.map(tot).fillna(0.), unit=d.gsis_id.map(unit))
    rows = []
    for u, g in [('all', d)] + [(u, d[d.unit == u]) for u in UNITS]:
        if len(g) < 10: continue
        rows.append({'unit': u, 'players': len(g), 'pearson': float(np.corrcoef(g.rav_w, g.w_av)[0, 1]),
                     'spearman': float(g.rav_w.rank().corr(g.w_av.rank())),
                     'mean_rav_w': float(g.rav_w.mean()), 'mean_pfr_w_av': float(g.w_av.mean())})
    return pd.DataFrame(rows)
