# Saved injury residual-overlay validation

Scope: this validates saved-input extraction and a median-margin residual overlay.
It does not validate starter-to-replacement efficiency propagation.

- Full repository suite: 1195 passed, 1 expected failure, 123 subtests passed.
- Eight new behavior tests cover latest pre-T60 vector selection, report capture/
  publication cutoffs, incomplete newer report blocking, missing team/report data,
  immutable source objects, role-specific prior snap shares, target/future snap
  exclusion, median rather than outlier-driven mean fitting, planted injury
  effects, prior-week-only weight updates, empirical cover symmetry and push refunds.
- Frozen source audit: 72 completed games with saved positional vectors, and
  12 with both teams' latest pre-T60 official report complete and issue-free.
  Older complete reports cannot override a newer incomplete report. This excludes
  GB-NE from the initial 13-game report-coverage count.
- Historical proxy training has 816 games; historical medical training has 783
  after 33 games with a nonfinal/missing team-report state are excluded.
- Every rolling fit cutoff precedes its evaluation week. Current-week labels
  never enter its weights; final all-completed-2026 fits are future-use diagnostics.
- All saved input timestamps precede their own T60 cutoff. No duplicate
  cohort/arm/game predictions; cover probabilities are finite and strictly (0,1).
- Source-journal, parquet, historical-pack and frozen-base hashes reproduce and
  remain unchanged. Production data/ and all journals are untouched.
- Complete repeat gives byte-identical weights, forecasts, uncertainty summaries,
  reports and post-hoc unpenalized estimates. Those alpha=0 estimates never
  generate replay forecasts or choose the prespecified alpha=.02 penalty.
- All penalized positional/QB coefficients are zero at prior, weekly and final
  stages. Injury arms reproduce the corresponding median-control forecasts;
  rolling probability-score differences arise from updated error distributions.
- Notebook is already synchronized; all 308 existing data files validate.
- Historical source-publication times and reconstructed snap-input availability
  remain unverified. Neither cohort certifies native executable injury pricing.
