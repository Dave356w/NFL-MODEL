# Injury to efficiency propagation prototype

Fixed before scoring. Train stage-one efficiency effects on 2020–25 only;
evaluate the 12 completed 2026 games with both latest pre-T60 reports complete.
No current-game outcomes enter features or stage-one fitting. This follows
exposed research and is not independent confirmation or causal identification.

Use snap-weighted medical absences and the same status/window rules as the saved
injury study. Fresh burden is current unit burden minus the injury burden in the
earlier games represented by the rolling efficiency profile. This is an average
historical replacement proxy, NOT individual starter/replacement talent ratings.

Five fitted efficiency targets: offense first-down rate, offense INT percentage,
defense first-down rate allowed, defense INT percentage forced, opponents' penalty
yards per game. Fit actual-minus-prior-profile efficiencies on six own and six
opponent fresh-burden variables, controlling for home venue and five opponent
prior rates. Standardized ridge10, no search. Profiles h8/.5 offseason/four league
pseudo-games; prior injury exposure uses matched profile weights and league prior.
Only complete historical medical reports enter regression labels; prior report
coverage must account for >=90% of profile weight. Earlier injury/snap source
publication times remain unverified.

Apply ONLY the fresh-injury component, not stage-one intercept/context residual,
to the saved pregame efficiency inputs. Percentages bounded [0,100]; penalties
nonnegative. Preserve QB term, pass contexts, market offset, frozen win coefficients,
favorite penalty and weekly median map. Passing-product contexts/net passing and
individual replacement quality are outside this first prototype's scope.

Reproduce every saved core forecast before intervention. Compare adjusted/unadjusted
at the same saved spread, actual result, -110 price. Report first-stage held-out
rate errors, raw probabilities/margins, mapped medians, pick changes and ATS WLP.
No direct point-margin injury penalty; no mean-margin intercept. Stage-one fits
are earlier-season only. Do not tune using LAC/PHI or ROI; do not deploy.
