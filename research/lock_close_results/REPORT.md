# Lock vs close basis on native forward rows (outcome-free diagnostic)

`python research/lock_close_basis.py`, rerunnable as rows accrue. It reads `data/forward_ledger.csv`
(lock moneylines saved in each snapshot; nflverse's moneyline after the game, `close_q`) and uses no
outcomes for the measurement.

Rows with a known close: 2026 week 5, locked a median of about 28 hours before kickoff.

| Revision | Rows | Mean / max lock-to-close move (pts of no-vig q) | Mean \|departure\| vs lock / vs close (log-odds) | Correlation | Favorite changed | Close-anchored side changes |
|---|---:|---|---|---:|---:|---:|
| v1.16 | 14 | 0.92 / 2.51 | 0.303 / 0.323 | 0.996 | 0 | 0 |
| v1.17 | 14 | 0.99 / 2.20 | 0.318 / 0.332 | 0.996 | 0 | 2 |

The close-anchored probability is `expit(logit p − logit q_lock + logit q_close)`.

**Reading, after one week.** Lock-time and closing anchors rank the model's departures almost
identically. They would have picked the same v1.16 side in all 14 games. Departures measured against
the close are slightly larger, so on average the market moved a little away from the model's view
(consistent with the ledger's CLV line, −0.11 / +0.17 points). Historical tests scored at the close
therefore look comparable to forward locks on this evidence.

That is 14 games from one week. Rerun it each week; the moves are about 1 point, roughly the
size the pre-kickoff Kalshi capture would need to resolve.
