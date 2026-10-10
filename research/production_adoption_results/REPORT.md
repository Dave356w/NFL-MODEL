# v1.16 production adoption verification

The owner adopted frozen market-offset Product + 1 SD contexts on 2026-10-09.
Raw main h8/ridge 0.1; raw pass h16; shared product plus four signed 1 SD
hinges/ridge 0.1; market no-vig logit coefficient fixed at 1. Coefficients refit
before each week from strictly earlier weeks, with two-season decay.

Executed the complete production model with current upstream inputs and rendered
all three site pages into an isolated preview. Regenerated all 15 week-5
projections (14 pending, one final). The current fit uses data only through
2026 week 4. Missing moneylines or contexts yield no prediction; native captures
also verify their probability against saved coefficients/inputs and their market
offset against the captured moneylines. New snapshots save raw model inputs,
pass descriptors and exact no-vig market probability for replay.

Retrospectively replayed all three original snapshots at their own original
moneylines. They are one unique game, 2026_05_TB_DAL, not three independent games.
Original revisions v1.12/v1.13/v1.14 had Dallas probabilities 64.45%, 63.29%,
61.92%; v1.16 replay gives 80.41%, 81.24%, 82.01%. Dallas loses under each replay,
-1u each. The original JSONL is byte-for-byte unchanged. This replay uses
reconstructed pregame features; it is not native forward evidence. The site
shows it in a separate retrospective section, preserving original predictions.

Verified the full production run against the frozen research candidate on all
815 binary historical evaluation games: maximum probability difference
9.16e-11, all picked sides identical. An additional cached-input test covers the
tied game too (816 total). All pass normalization references are strictly prior
weeks. Market plus learned contributions sum to the displayed forecast logit.
All current probabilities reproduce from the saved fit. 193 tests pass; notebook
is synchronized; all 26 existing data files validate; original ledger is intact.

Committed artifacts include current projections, retrospective snapshot grades,
coefficient fit, normalization timing audit, historical reproduction and source
hashes. Bot-generated data/latest, data/projections, graded native views and Pages
are refreshed by the normal serialized build after the code lands on main.
No retrospective snapshot is appended to the native ledger.

Most upcoming injury reports are currently marked practice-only rather than
final. Current projections remain provisional and the existing report gate
continues to control first native capture. Adoption follows exposed historical
research; it does not establish a reliable profit advantage.
