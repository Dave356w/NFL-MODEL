# Independent every-season retest verification

The fresh retest's principal result is reproduced: **none of the 330 feature variants passes the full 2021–2026 probability hurdle, ATS hurdle, or joint hurdle.** The six-season sample contains 1,451 completed games, including 92 in 2026. It remains exposed historical development rather than fresh validation.

The independent verifier checked all 5,994 annual metric rows and 999 fixed-policy gate rows. All −110 settlements, side selections and prior-season median maps agree. It independently refit 182 deterministic sampled week/models with SciPy BFGS, using separately implemented normalized time weights, training-only scaling and ridge losses. The maximum forecast difference was 1.23×10⁻⁷. Earlier/future cutoffs, market quote identities, asset hashes and frozen game alignment pass.

The median paths' unavailable 2021/2022 seasons remain unavailable. They cannot pass the six-season ATS or joint hurdle. NFL tied finals are excluded from winner proper scores; ATS pushes remain in the bet denominator. Missing maps and skips do not become additional successful seasons. Strict comparisons have explicit numerical tolerances so rounding dust cannot turn identical records into an improvement.

Nine regression tests pass, including dropping a bad season, replacing a season with a duplicate, retaining an adverse year, missing early median maps, tiny positive numerical score/ROI differences, push/skip/away-favorite settlement, and exclusion of future margins from annual median fitting.

The archived 2023–2025 grid was also independently settled from its stored margins: all 1,219 paths' side, grade and return arrays match. Among its 1,188 fixed feature-policy paths:

| Probability definition | Proper scores beat their benchmark every year | Proper scores + positive ATS ROI + beats favorite every year |
|---|---:|---:|
| Stored path probability, against the same-mode market path | 92 | 2 paths, one distinct raw policy |
| Original winner-generator probability, against the original market anchor | 60 | 3 paths, two distinct policies |

The two raw path labels are `production` and `extended` versions of **spread_total/full/g0.5/raw**; their raw forecasts and settlements coincide. The other policy under the original-winner-probability interpretation is **production spread_total/full/g0.25/own median**. These are exposed diagnostics from a large search, not independent confirmations or new recommendations.

The archived count differs because its median paths converted mapped margins back through Φ(margin/12.37) to create a policy score. The fresh retest correctly keeps the original winner probabilities for proper scoring and applies median maps only to ATS settlement. Its probability gate additionally requires beating both market benchmarks in each season; its ATS gate also requires beating the matched anchor policy. Therefore the old three-season counts must not be presented as passing the new six-season rule.

Verifier: `/workspace/nfl-market-update/research/verify_season_rule_retest.py`.

Machine-readable result: `/workspace/nfl-performance-audit/season-rule-independent-verification.json`.

Reproduce the fresh verification:

```bash
cd /workspace/nfl-market-update
OPENBLAS_NUM_THREADS=1 /workspace/NFL-MODEL/.venv/bin/python research/verify_season_rule_retest.py research/season_rule_retest_results
```

The verification performs no candidate search, writes no native forecasts, and changes no model, ledger, production data or public page. Numerical agreement establishes implementation consistency; it does not authenticate historical pregame vintages or executable ATS prices.
