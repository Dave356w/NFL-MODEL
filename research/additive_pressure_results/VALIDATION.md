# Offensive-only and additive pressure validation

- Full repository suite: 1187 passed, 1 expected failure, 123 subtests passed.
- Targeted pressure checks: 15 passed. Offensive-only fits exactly one pressure
  coefficient; additive fits exactly two, and the interaction column is removed.
- Planted-signal tests learn separate offense/defense effects. Arbitrary or missing
  interaction inputs cannot affect predictions. Changing the defensive input
  alone changes the planted additive forecast while offense stays fixed.
- Offensive-only profiles match the original full-pressure offensive inputs at
  1e-12 tolerance on every frozen game at both source lags, without reading
  defensive columns. Both features reverse under team swap and exclude target,
  recent-unavailable and future source games.
- Annual fits use 272/544/816 previous-season games. Saved source cutoffs satisfy
  the declared two-week primary or one-week sensitivity lag. No duplicate
  game/arm/lag forecasts; conditional cover probabilities are strictly (0,1).
- Both studies rerun with byte-identical fits, forecasts, reports, reliability,
  uncertainty comparisons and all-team diagnostics; the direct additive-vs-
  offensive-only comparison uses identical games in the same sorted order.
- Notebook already in sync; 308 existing data files validate. Production model,
  maps, locks, journals, public pages and notebook are unchanged.
- This follow-up was selected after inspecting historical LAC/PHI/full-pressure
  results. Nominal intervals are not adjusted for that selection. Source lags
  are reconstructed chronology, not verified original publication availability.
