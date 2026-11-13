# Fixed additional −2 team-margin points for 2026 backup starts

Owner-requested research sensitivity, 2026-11-13. No production change and no
rewrite of saved selections. The two-point value is fixed by the request; do not
sweep penalties or refit existing QB terms.

Primary basis is the current published 2026 ATS pool: 137 completed picks in the
frozen data/latest/ats_pricing_results.csv snapshot; exclude the pending row.
Retain its replay/saved-record source distinctions in backend research. Also
show the 45-decision archived saved-pick audit as a separate sensitivity; earlier
revision locks do not replace the owner-authorized replays in the published pool.

Two pregame cohorts are reported separately, not conflated:

* Chart backup: projected QB below QB1 on the latest dated chart at least 24h
  before kickoff, no older than seven days and no later than the saved forecast
  where that timestamp exists. Promoted backups now listed QB1 are missed.
* Replacement proxy: projected QB differs from the established incumbent with
  >=2 strictly earlier starts this season (most starts, ties by latest), incumbent
  remains at QB on latest earlier roster. Includes benchings and loses long-term
  backups once they become incumbents. Unknown roster/name coverage and blends
  remain unresolved. This is the same longer-history proxy as the prior fit.

Use saved QB evidence for recorded decisions and the frozen historical
availability reconstruction for replays. Actual first QB-position passer labels
are outcome diagnostics, never pregame flags. Show correctly projected subsets.

Apply exactly two points directly to the final published/locked mapped margin:

    adjusted_home_margin = original_margin - 2*home_flag + 2*away_flag

Both backups cancel in relative margin. No median remapping after this overlay.
Use the existing zero-edge market-favorite policy; pick'em zero edge skips.
Recompute selection and grade against the SAME market handicap. Do not reuse the
original side's price after a flip. Primary returns are flat 1u at a common −110;
matched side-specific quotes are a secondary paired sensitivity, without
inventing missing opposite-side prices. Raw-margin −2 is a separate sensitivity
where original raw projections exist, not a substitute for the final-margin test.

Report all-pool results (unresolved lineups retain the original pick, explicitly
counted), known-lineup pairs, backup-involved games, source subsets, flips,
W-L-P, skips, units, ROI/SE, cover rate versus the −110 52.4% break-even reference,
MAE/MSE/signed margin residuals, and same-row favorite/home baselines. Give a
week-cluster paired-return interval; 2026 was already inspected and is exposed
research, not fresh confirmation. No ROI or threshold optimization.
