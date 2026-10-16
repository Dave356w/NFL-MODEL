# R003 brief finding

Conditioning raw empirical A on joint scoring reachability improves joint NLL
7.125372 -> 7.125085. Gain +0.000286158 nats/game on 816 exposed 2023-25 games;
paired week-bootstrap 95% [0.000256619, 0.000319438], two-new-contrast adjusted
97.5% [0.000252886, 0.000324715]. Annual gains remain positive.

**Reject advancement of this fixed support-only candidate:** it fails the locked
0.005 practical threshold by a large margin. The positive supported-outcome NLL
gain is algebraically -log(1-removed_mass), not learned football-score structure.
Team/MOV/total CRPS and winner LL/Brier worsen slightly. All negative secondary
metrics are retained; none exceed the fixed tolerance. Moneyline picks and
returns happen to remain unchanged, and ROI did not select the candidate.

The additive mask removes exactly 13 unreachable pairs from the 6,561-cell grid,
while retaining valid rare (6,1)/(1,6) scores and other one-point possibilities.
No observed outcome violated the mask; invalid realized support would hard-fail.
This is an independent raw-A ablation, never combined with R001/R002.

21 support tests passed before forecast execution. Final combined suite: 63
passed, including two serialization regression tests; 20 output checks pass.
The initial report failed because the compressed CSV lacked an EOF marker;
its first independent repeat also failed CSV equality, although PMF arrays,
transform audits and support matched. The corrupt file/logs are preserved in
failures/initial_write. Root cause remains unestablished. An I/O-only revision
constructs and validates the entire gzip stream before atomic publication.
Same-spec repaired output and independent repetition pass exactly. No forecast
formula, support mask, smoothing parameter or evaluation set changed.

No independent validation: historical outcomes exposed and quote times unknown.
No production or betting promotion. Next: one fixed football-score-frequency
hypothesis using fresh evaluation; a true overtime process needs audited
regulation/OT/possession data first.
