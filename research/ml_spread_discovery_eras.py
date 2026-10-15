"""The 2013-2026 disagreement re-estimates cited in research/ML_SPREAD_2006_12.md (discovery data).

    python research/ml_spread_discovery_eras.py      # writes research/ml_spread_results/discovery_eras.json

These are the numbers that motivated Test 46, not evidence for it: the lead was found on these
seasons. The protocol quotes the four era coefficients with model-based SEs, as first computed on
2026-10-14; the registered specification uses season-week cluster SEs, reported alongside, with the
whole 2013-2026 block as one estimate.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ml_spread_2006_12 as ms  # noqa: E402

OUT = ms.OUT/'discovery_eras.json'
ERAS = {'2013-2016': (2013, 2016), '2017-2020': (2017, 2020), '2021-2024': (2021, 2024), '2025-2026': (2025, 2026)}


def model_se(d):
    """Model-based (inverse-information) SE of b on dis in the free-slope fit."""
    X = np.column_stack([np.ones(len(d)), logit(np.clip(d.q, ms.CLIP, 1-ms.CLIP)), d.dis])
    b, _ = ms.logistic(X, d.y)
    p = expit(X@b)
    return float(np.sqrt(np.linalg.inv(X.T@(X*(p*(1-p))[:, None]))[2, 2]))


def run(out=OUT):
    later = ms.priced(pd.read_csv(ms.LATER))
    later = later[(later.week <= 18) & later.y.notna()]
    res = {}
    for name, (a, b) in {**ERAS, '2013-2026 (one block)': (2013, 2026)}.items():
        d = later[later.season.between(a, b)]
        r = ms.fit_free(d)
        res[name] = {'n': r['n'], 'b': r['b'], 'se_model': model_se(d), 'se_cluster': r['se'], 'b_per_sd': r['b_per_sd']}
    out.write_text(json.dumps(res, indent=2)+'\n')
    return res


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
