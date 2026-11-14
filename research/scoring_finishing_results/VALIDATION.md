# Validation

- Full repository suite: 1171 passed, 1 expected failure; 123 subtests passed.
- New study tests cover future/target exclusion, team-swap symmetry, missing/nonfinite
  input rejection, planted signal, push treatment and favorite-on-zero-edge behavior.
- Scoring tests cover prior-only contextual expectations, kneel-only exclusion,
  offensive vs defensive touchdown accounting, one drive/one trip counting, and
  fourth-down opportunity/attempt/conversion separation.
- Both studies reran from frozen aggregates with byte-identical predictions,
  annual fits, metrics, reliability, comparison intervals and reports.
- Every annual fit uses strictly earlier seasons (272/544/816 training games).
- Every saved feature cutoff satisfies the declared one- or two-week source lag.
- No duplicate game/season/lag/arm forecasts; all cover probabilities strictly in (0,1).
- Scoring-input offensive points never exceed actual team scores on matched ledger games.
- 138 of 3609 single-passer games differ from the rounded PFR pressure rate by more
  than 0.5 percentage points under the explicit PBP opportunity definition; median
  discrepancies per season are about 0.02-0.03 percentage points. Do not present
  these as byte-exact PFR percentage reproductions.
- Notebook already in sync; data validation passes for 308 existing data files.
- Existing tracked production/source/data/public/notebook files have no changes.
- Original source publication times cannot be verified. The passing checks establish
  chronology against reconstructed game dates, not point-in-time source availability.

The four full-suite warnings are existing fixture/runtime warnings (pytest plugin,
small-sample residual variance, and pandas empty-frame concatenation).
