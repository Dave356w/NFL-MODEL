"""Select ATS reporting behavior from the forecast's saved recipe identity.

The market-spread/total architecture uses its continuous projected margin.
Legacy snapshots retain their median-map preparation. Compatibility aliases
keep existing exports and rendering URLs working without applying a map twice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fixed_bands
import nfl_model as model


CONTINUOUS_ARCHITECTURE = 'market_spread_total'
CONTINUOUS_METHOD = 'continuous_spread'


def is_continuous(value):
    """Dispatch by the saved architecture, never the running module revision."""
    manifest = (value or {}).get('manifest', value or {})
    return (manifest.get('recipe') or {}).get('architecture') == CONTINUOUS_ARCHITECTURE


def _continuous_frame(source):
    frame = source.copy()
    if frame.empty:
        return frame
    provided = pd.to_numeric(frame.get('model_spread', pd.Series(np.nan, index=frame.index)), errors='coerce')
    probability = pd.to_numeric(frame.get('model_wp', pd.Series(np.nan, index=frame.index)), errors='coerce')
    valid = np.isfinite(probability) & probability.gt(0) & probability.lt(1)
    canonical = model.implied_spread(probability.where(valid))
    # Use the same saved-probability conversion as timed locks and season grading.
    # A separately rounded spread column must not change the side near equality.
    frame['model_spread'] = np.where(valid, canonical, provided)
    for name in ('result', 'spread_line'):
        if name not in frame:
            frame[name] = np.nan
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    frame['raw_spread'] = frame.model_spread
    frame['ats_spread'] = frame.model_spread
    frame['selection_method'] = CONTINUOUS_METHOD
    frame['selection_version'] = fixed_bands.SELECTION_VERSION
    grades, units = fixed_bands.grade(frame, frame.model_spread)
    complete = np.isfinite(frame.result)
    frame['ats_result'] = np.where(complete, grades, '')
    frame['ats_units'] = np.where(complete, units, np.nan)
    side = fixed_bands.pick(frame.model_spread, frame.spread_line)
    frame['ats_side'] = np.where(side > 0, 'home', np.where(side < 0, 'away', ''))
    frame['ats_team'] = np.where(frame.ats_side.eq('home'), frame.home,
                                  np.where(frame.ats_side.eq('away'), frame.away, ''))
    frame['ats_handicap'] = np.where(frame.ats_side.eq('home'), -frame.spread_line,
                                     np.where(frame.ats_side.eq('away'), frame.spread_line, np.nan))
    frame['ats_status'] = np.where(~complete, 'pending',
        np.where(np.isin(frame.ats_result, list('WLPS')), 'graded', 'unavailable'))
    # These are file/column compatibility names, not a second calibration step.
    frame['fixed_band_spread'] = frame.model_spread
    for name in ('result', 'units', 'side', 'team', 'handicap'):
        frame['fixed_band_ats_'+name] = frame['ats_'+name]
    return frame


def prepare(latest):
    if not is_continuous(latest):
        fixed_bands.prepare(latest)
        return
    history = _continuous_frame(latest.get('retro_ledger', pd.DataFrame()))
    latest['ats_ledger'] = history
    latest['fixed_band_ledger'] = history
    latest['fixed_band_rules'] = []
    latest['ats_selection_method'] = CONTINUOUS_METHOD
    latest['board'] = _continuous_frame(latest.get('board', pd.DataFrame()))


def summary(latest):
    if not is_continuous(latest):
        history = latest.get('fixed_band_ledger', pd.DataFrame())
        return fixed_bands.summary(history) if len(history) else pd.DataFrame()
    history = latest.get('ats_ledger', latest.get('fixed_band_ledger', pd.DataFrame()))
    if history.empty:
        return pd.DataFrame()
    import season_ats
    rows = []
    for label, group in [('All', history), *list(history.groupby('season', sort=True))]:
        values = season_ats.summary(group)
        rows.append(dict(season=str(label), method='Continuous spread', games=len(group), **values))
    return pd.DataFrame(rows)
