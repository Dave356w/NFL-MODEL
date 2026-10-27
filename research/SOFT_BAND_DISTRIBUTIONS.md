# Soft neighboring-band empirical margin distributions: SB1

Protocol fixed before the first SB1 result, 2026-10-26. Research only.
Production v1.18, its median map, public pages and original archives stay unchanged.
All historical periods are exposed development, including the 2026 diagnostic.

## Fixed forecast

- Recompute the production raw home-margin projection as
  `12.37 * Phi^-1(clip(model_wp, .005, .995))`.
- For target season Y, use completed games from seasons strictly before Y.
  Require two seasons, 300 games and 30 observations in each existing magnitude
  band: `[0,3)`, `[3,7)`, `[7,10)`, `[10,infinity)`.
- Sign each observed actual home margin toward that game's model-projected
  winner. Estimate the four **complete empirical margin PMFs**, including losses
  and ties, on integer margins -100 through 100. Add no Gaussian mass, translated
  margins, invented scores, pseudocounts or outcome-fitted transition parameters.
- Each band's anchor is its prior-sample median raw spread magnitude. Between
  adjacent anchors, use linear nonnegative weights summing to one on those two
  PMFs. Outside the anchors use the nearest endpoint distribution. This removes
  jumps at 3, 7 and 10 without imposing a smooth density on football key numbers.
- Flip the signed-margin PMF back to home-margin orientation for away favorites.
  Exactly zero raw projections are explicitly unavailable: this design does not
  solve the separate orientation boundary at zero.
- Compute home-cover, push and away-cover mass at the row's actual listed spread.
  Pushes have mass only at an integer handicap actually present in the PMF.

## Controls and prices

Hard empirical bands use the identical four prior PMFs with hard 3/7/10 assignment.
This isolates blending from the choice of empirical distribution. The production
median map, original raw projection, always-spread-favorite and always-home remain
decision controls. The median map uses the original saved decision for 2026
where available and prior-season fitted medians for historical years.

The main period is 2023-25. Completed 2026 games are a separate diagnostic.
Inputs are frozen in `soft_band_distribution_inputs/games.csv`; every scored
game's own and later seasons are excluded from its fit. No weekly updating,
band search, curve search, price search or ROI-selected variant is introduced.

Two price scenarios are kept separate:

1. Uniform -110 each side on all eligible games: an explicit hypothetical scenario.
2. Existing archived paired spread prices, only for exact game/handicap matches
   with valid prices on **both** sides. Historical schedule quote times are unknown;
   ESPN closing estimates are retrospective. Neither is verified historical lock
   execution. Missing paired prices are excluded from this scenario, not imputed.

Probability controls: fair 50/50 conditional on no push on the full cohort, and
normalized two-sided implied probabilities on the paired-price cohort. Neither
two-sided price control identifies market push mass or a full margin distribution.

## Evaluation and decision

Primary prediction contrasts are soft versus hard-band conditional cover log loss
on all decisive 2023-25 games, and soft versus the actual two-sided market on the
exact-paired decisive subset. Report paired 97.5% whole-season-week bootstrap
intervals for these two fixed contrasts (Bonferroni familywise 95%). No ROI-based
model selection. Secondary scores: conditional cover Brier, all-game three-event
log loss, discrete-margin CRPS, median MAE, calibration bins and annual results.
Probability clipping at 1e-12 applies to scoring only; zero probability events
are counted explicitly and forecasts remain unchanged.

At each side's offered American price, risk 1u. Home EV is
`win_profit(home_odds) * P(home cover) - P(away cover)`; reverse for away.
Select the strictly positive maximum, otherwise pass. No additional threshold.
Pushes refund the stake. Report W-L-P, passes, units, ROI +/- SE, week-bootstrap
intervals, expected returns, conditional cover calibration and same-selected-game
favorite/home/median/raw controls. Compare soft and hard EV policies per opportunity
so passing policies are not rewarded by incompatible denominators.

Advancement requires both primary prediction gain intervals strictly above zero.
A profitable point estimate, a result on a selected slice, or fewer bets cannot
override that gate. Passing this development gate would justify a separately
registered forward shadow, not immediate production adoption or a profit claim.
No live shadow capture or production deployment is enabled by this experiment.

## Reproduce

```sh
python -m research.soft_band_distributions --prepare-inputs
python -m research.soft_band_distributions
python -m pytest tests/test_soft_band_distributions.py -q
```

Input preparation is explicit; ordinary replay uses the committed frozen pack.
The result includes input hashes, prior-season fits, PMFs, per-game forecasts,
paired-price provenance, exact selections, calibration tables and uncertainty.
Post-run numerical audit addition (no fit or decision-policy change): an
outcome-free continuity table evaluates synthetic raw values 0.01 below,
at and 0.01 above each original cutoff, at a handicap equal to that cutoff.
This is a numerical diagnostic, not a live game prediction or a selection rule.
