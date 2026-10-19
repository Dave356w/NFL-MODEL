# Every-season market retest: frozen exploratory design

Recorded before calculating this retest. The owner holds v1.19; no result here
authorizes a production change. Historical 2021–26 outcomes have already been
examined, including the new revision's poor 2026 results. These are exposed
development data, not fresh validation.

Two winner-probability anchors: paired no-vig moneylines and an earlier-trained
spread/total logistic baseline with [1,s/7,(t−44)/7,s(t−44)/49], ridge .01/ESS.
For each anchor, 29 individual existing football inputs, exactly the three
previously declared additive pairs, and the full 29-input joint correction are
fit before every target week. Each fitted departure from its anchor logit has
fixed gamma .05, .10, .25, .50 or 1. The .05 and .10 arms are new exploratory
stronger shrinkage arms. Gamma zero is stored once per anchor; v1.18 is a control.

Training uses 2019 onward, only earlier weeks and decisive ready games with
valid quotes, pass context, spread and total. Outcome weights have a 38-week
half-life, normalized to sum 1. Inputs use training-only weighted SD, no
centering, neutral zero for missing differences. Ridge is .01 for site and .1
for every other correction input. The three additive pairs retain their
original definitions: allowed passing efficiency + QB delta; passing product
+ DB absences; allowed first-down rate + opponents' assessed penalty yards.
There is no opponent-adjustment redesign or additional product interaction.

Evaluate 2021–25 and 2026 YTD separately on all 1,451 completed games. Binary
proper scores exclude NFL tied finals, while ATS grades include tied finals.
Probability gate: one fixed arm has lower log loss AND Brier than BOTH winner
anchors in every season. Also report counts versus its own anchor and versus
moneylines so alternative interpretations remain visible.

The unchanged 12.37 inverse-normal probability-to-margin link feeds three paths:
raw margin; own annual median MOV map; the incumbent's shared annual median map.
Mappings use only earlier-season 2021+ OOF games and production 0/3/7/10 bands,
including losses and tied finals. Keep two prior seasons, 300 total and 30 per
band minimums. Therefore 2021/22 median paths are unavailable and cannot pass
the full six-season coverage gate. Show 2023–26 median comparisons separately.

ATS gate: positive flat-stake ROI at assumed −110 AND strictly better ROI than
the same anchor under the same mapping path AND the same-row market favorite
in every season, with complete six-season coverage. Always-home is diagnostic.
At a model/line equality within 1e−10, take the market favorite; zero pick'em
skips. Pushes remain in the bet denominator. All comparator games are paired;
missing mappings never count as passed seasons. Joint gate requires both the
probability and ATS gates. No annual winner selection or ROI-tuned thresholds.

Observed sign gates and uncertainty are separate evidence tiers. Whole-week
paired bootstrap and a simultaneous complete-family adjustment are conditional
on these forecasts, omit refit/adaptive-history uncertainty, and cannot turn
this searched history into independent fresh evidence. Historical paired ATS
prices and capture timestamps are unavailable; −110 is a stated scenario.
