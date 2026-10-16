# R003-SC1: location, calendar and rest with sparse-context backoff

Locally frozen before candidate scoring. User-requested context extension to
the plain observed-score empirical model. All historical years are exposed.
Earlier schedule research was inspected; this is not independent confirmation.
No change to earlier model specifications, outputs, production, or ledger.

## Inputs, plain model and source timing

Use only R000's frozen schedule/outcome/price pack and the already committed
disjoint_features_inputs/schedule_context.csv for home/away rest. Join exact
game_id/season/week, one-to-one. Never replace outcomes or prices using a new
download. Complete baseline cases remain included; missing context falls back
to plain. The plain model is MC2 direct_ref_h2_t3_p0 (spread bandwidth 2,
total bandwidth 3, zero global backoff), using paired observed score outcomes,
strictly prior weeks and current plus five prior seasons, two-season time decay.
Reproduce its saved per-game metrics/probabilities before any comparison.

## Fixed pregame feature groups

1. slot: TNF = Thursday kickoff >=18 ET; Thursday daytime separately; MNF =
   Monday >=18; SNF = Sunday >=18; Sunday early <14:30; Sunday late >=14:30
   and <18; all other slots one class. Neutral sites have unknown slot because
   venue/time-source ambiguities cannot be resolved from this pack.
2. rest: joint home/away rest categories short <=6 days, normal 7–9, long >=10,
   plus rest-gap category home >=2 extra days, away >=2, or within one day.
   Week 1 is opener, not a supposed measured seven-day rest. Missing/nonpositive
   rest is unknown. No current or later outcome is used.
3. travel: home-base time-zone offset to the designated home venue at kickoff:
   eastward >=2 hours, westward >=2, or smaller shift. This is a geographic
   proxy, not an itinerary or acclimation measurement. Neutral sites unknown.
4. body_clock: home- and away-base local kickoff bands, early <12, afternoon
   12–<17, evening 17–<20, late >=20. Convert Eastern kickoff with ZoneInfo;
   Arizona does not observe DST; LA is Central through 2015, Pacific thereafter;
   STL Central, OAK/SD and subsequent LV/LAC Pacific. Neutral sites unknown.
5. venue: designated home team's time-zone region (Eastern/Central/Mountain/
   Phoenix/Pacific); neutral sites unknown. No team fixed effects.
6. phase: weeks 1–4, 5–13, late regular season, final regular-season week
   (17 through 2020, 18 thereafter). Do not infer rested starters from outcomes.

All groups use schedule fields or fixed historical home-zone mappings. Fail or
mark unknown on malformed data; never substitute a made-up timezone or clock.
Use frozen gameday/gametime as supplied. Retrospective schedule revisions and
unknown quote capture times remain limitations; actual input availability at
historical lock cannot be certified.

## Sparse-context shrinkage and fixed candidate family

Let w be the plain model's normalized market-context weights on historical
games. For a group, restrict to historical rows with the same known group key
as the target. Let mass=sum w_subset and kish=mass^2/sum(w_subset^2).
Relevant support = min(kish, ESS_plain*mass). The second term prevents a tiny
market-probability mass of distant games from looking adequately supported just
because their weights are similar to one another.

If the target key is unknown, subset empty, or support <20, use exactly plain.
Otherwise alpha=support/(support+K), and new weights are
(1-alpha)*w + alpha*w_subset/mass. K is fixed at 30 or 100. No outcome enters
alpha except through prior observed atoms already in w. Mixtures remain coherent
paired observed-score distributions, normalized, with no Gaussian or synthetic
score. Log mass, Kish ESS, relevant support, alpha, final ESS and fallback counts.

Six individual groups x two K =12 challengers. Add joint all-six-key matching x
two K =2 and additive average of all six independently shrunk distributions x
two K =2, for 16 challengers. Additive weights average all six components,
including plain fallback components; do not add correlated sample sizes.
Plain is an explicit candidate in every annual selector. Select all-family
and each individual-group/K path from strictly earlier OOF seasons beginning
2015, requiring two years, minimizing 0.5*(margin CRPS+total CRPS), never ROI.
Plain wins exact ties. No feature-group, interaction, threshold or K search
beyond these declarations after scoring; do not erase unfavorable variants.

## Evaluation and decision

Predict 2015 onward, evaluate 2017 onward; primary 816 games 2023–25, earlier
2017–22 separate development and 2026 W1–5 separate diagnostic. One new primary
policy: earlier-season selected all-family versus plain on identical games.
10,000 paired whole-week bootstrap draws within season, seed 20261016. Report
95% primary interval and 99.6875% 16-challenger sensitivity, without claiming
full adaptive-search coverage. Fixed-arm/group slices are descriptive.

Retain for research only if primary mean gain >=.01 points, 95% lower bound >0,
all three primary seasons improve, no margin/total CRPS or winner/cover/total LL
worsens by >.002, and integrity checks pass. A selected plain path has zero
gain and cannot pass. Forecast support is separate from net profitability.
Exact empirical wrong endpoint losses remain infinite; never floor or drop them.

Report all fixed arms, annual selections, group coverage and fallback/support,
home/away/margin/total CRPS, proper event scores, calibration, quantile coverage
and width, paired intervals, year/week stability and matched feature slices.
Flat 1u moneyline units, W-L-P, ROI +/- SE, same-row favorite, negative-hold
null and paired return intervals are reported, never optimized. No historical
ATS/total ROI because recorded two-sided spread/total prices are absent.

## Reproduction and scope

Test timezone/DST/relocation, weekday/slot/rest bins, neutral/missing fallback,
rare/irrelevant-context suppression, sufficient-context shrinkage, normalized
observed atoms and settlement, prior-week sources and earlier-season selectors.
Save feature table, source/input/protocol hashes, per-game data, source cutoffs,
annual selections and repeat checks. Independently rerun in another directory.
Preserve all prior user work and original results. No live data integration,
new outcome/price capture, production deployment, wagering or ledger mutation.
