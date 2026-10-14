"""Offline full/compact profile equality and runtime check on frozen 2013-14 inputs."""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m
import form_windows as fw

OUT = ROOT/'research/profile_runtime_results'


def run(out=OUT):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    box = pd.read_csv(fw.BOXES)
    sched = fw.schedule_frame(pd.read_csv(fw.SCHEDULE))
    box = box[box.season.isin([2013, 2014])]
    sched = sched[sched.season.isin([2013, 2014])]
    sig = m.config_signature()[0]
    frames = {}; seconds = {}; columns = {}
    for mode in ('full', 'production'):
        start = time.perf_counter()
        frames[mode] = {h: m.lagged_features(box, sched, h, profile_families=('rates_core',) if mode == 'production' else None)
                        for h in m.profile_half_lives(mode)}
        seconds[mode] = time.perf_counter()-start
        columns[mode] = {str(h): len(f.columns) for h, f in frames[mode].items()}
    for h, compact in frames['production'].items():
        pd.testing.assert_frame_equal(compact, frames['full'][h][compact.columns], check_exact=True)
    for f in frames.values(): m.prepare_product_features(f, sched)
    errors = []
    for week in (1, 8, 17):
        forecasts = []
        for f in frames.values():
            g = f[8.]
            fit = m.fit_composite(g[m.before(g, 2014, week)], m.PRODUCT_RECIPE, 2014, week)
            forecasts.append(m.apply_fit(g[(g.season == 2014) & (g.week == week)], fit))
        np.testing.assert_array_equal(*forecasts)
        errors.append(float(np.max(np.abs(forecasts[0]-forecasts[1]))))
    if sig != m.config_signature()[0]: raise ValueError('Production identity changed')
    info = {'basis': 'frozen 2013-14 box scores; availability omitted identically in both paths',
            'seconds': seconds, 'speedup': seconds['full']/seconds['production'], 'columns': columns,
            'shared_columns_bitwise_equal': True, 'forecast_max_abs_error': max(errors),
            'forecast_weeks_checked': [1, 8, 17], 'config_signature': sig,
            'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__), ROOT/'nfl_model.py', ROOT/'research/form_windows.py', fw.BOXES, fw.SCHEDULE)}}
    (out/'results.json').write_text(json.dumps(info, indent=2)+'\n')
    (out/'REPORT.md').write_text(
        '# Compact profile runtime and equality check\n\n'
        'Frozen 2013-14 team-game boxes and schedule. Availability is omitted identically in both paths. '
        'This is a pipeline equivalence check, not model-performance evidence.\n\n'
        f"Full h4/h8/h16 path: {seconds['full']:.2f}s. Raw h8/h16 path: {seconds['production']:.2f}s. "
        f"Observed speedup: {info['speedup']:.2f}× for profile generation only. Single run; not an end-to-end build benchmark.\n\n"
        'Every retained profile column is bitwise equal. Final forecasts are bitwise equal for 2014 weeks 1, 8 and 17. '
        'Production configuration signature is unchanged. Sources and measurements are in `results.json`.\n\n'
        'Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/profile_runtime.py`.\n')
    return info


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
