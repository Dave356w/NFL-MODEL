# Simple possession-rate study validation

- Full repository suite: 1180 passed, 1 expected failure, 123 subtests passed.
- All 20 study behavior tests pass, including drive counting, kneel/try/no-play
  exclusions, multiple punt attempts, offensive/defensive scoring separation,
  PAT/two-point accounting, exact opponent mirroring, source/target exclusion,
  team-swap symmetry, missing/nonpositive inputs and push treatment.
- Both new studies rerun with byte-identical forecasts, coefficients, metrics,
  reliability, uncertainty comparisons and reports.
- Each annual fit uses 272/544/816 previous-season games only. All saved feature
  cutoffs satisfy their declared two-week primary or one-week sensitivity lag.
- No duplicate arm/game/lag predictions; cover probabilities strictly in (0,1).
- PBP source hashes match the original shared source manifest for every year.
- PPP and punt studies use identical possession denominators on every source
  team-game; each opponent's numerator and denominator mirror exactly.
- PPP offensive points never exceed scoreboard points on 2990 matched ledger
  team-games. Defensive/return scoring is deliberately excluded, so equality to
  all scoreboard points is not expected.
- Notebook already in sync; 308 existing data files validate.
- Live model, maps, locks, journals, public site and notebook remain unchanged.
- Historical PBP first-publication times remain unverified; passing chronology
  checks do not establish native pregame availability or forward evidence.
