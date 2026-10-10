# Validation

- 221 repository tests passed, including 9 new margin/total and interaction tests; two existing pandas FutureWarnings.
- Notebook already in sync; 28 data files validated; git diff check passed.
- Historical full-production reproduction error: 1.027e-10; archived current: 2.220e-16.
- Every distribution fit and dispersion reference precedes the scored week. Every stage-two training row has earlier-week stage-one cutoff metadata; in-sample/future forecasts are rejected.
- Integer pushes, no-vig prices, standalone price invariance, current/future-label rejection, source-ablation invariance and exact matched-production fitting tested.
- Frozen-input replay completed; original primary result values remained unchanged after cutoff metadata and supplementary diagnostics were added.
- Production code/settings and append-only ledger unchanged; ledger SHA256 40e98327259dc80c75bb7325d83e7f89b0857c48bca12906f022ed0bd0890a86.
- Native forward qualification is not established. No website/UI changes were made in this research task.
