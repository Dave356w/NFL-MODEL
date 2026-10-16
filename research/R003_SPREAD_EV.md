# R003 spread decisions at quoted handicaps and odds

`R003-SPREAD-EV-v1` is an optional research decision layer. It reads the empirical
R003 margin PMF and externally supplied spread quotes; it never uses a projected
mean margin to select a side. It leaves R003's frozen model, protocols, metrics,
historical winner-picking benchmark and failed advancement gate unchanged.
This is not a new scoring model or the reserved R004 frequency experiment.

## Settlement, prices and selection

Handicaps use the quoted team's sportsbook sign. For margin M = home minus away:

| Offer | Cover | Push | Loss |
| --- | --- | --- | --- |
| Home with handicap H | M + H > 0 | M + H = 0 | M + H < 0 |
| Away with handicap H | -M + H > 0 | -M + H = 0 | -M + H < 0 |

Thus home -3 and away +3 share a three-point home-margin push. Half-point
handicaps have no push mass on integer margins. Quarter-point split wagers are
rejected rather than assigned an incorrect settlement rule. Zero handicaps and
different offered handicaps/prices are accepted.

Net win profit per 1u risk is odds/100 for positive American odds, or 100/abs(odds)
for negative odds. Optional commission is charged only against winning profit;
optional stake_fee is a fixed nonrefundable cost on every outcome, including a
push. With defaults of zero fees:

    EV = P(cover) * net_win_profit - P(loss)

With fees:

    EV = P(cover) * win_profit * (1 - commission) - P(loss) - stake_fee

Use unconditional cover/loss probabilities here. Do not discard the push mass
or treat a conditional cover probability as an unconditional probability.
Commission must be in [0, 1), and stake_fee nonnegative. This fee representation
is explicit; it is not an implementation of any exchange's contract-specific fee
schedule. Supply appropriate costs or extend settlement separately when needed.

For at most one flat 1u wager on one game, evaluate all supplied offers and
choose the highest positive net model-estimated EV. Otherwise pass, worth 0u.
An EV <= 1e-12 is treated as numerical zero. Equal positive EVs select the first
input offer, without looking at realized outcomes. This rule does not perform
portfolio optimization or bankroll sizing. It does not search thresholds using
historical ROI. Every offer requires actual odds; no -110 default or price-per-
point interpolation exists.

## Run offline

The full marginal NPZ is ignored by Git. Regenerate it when absent:

```bash
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R003
```

Create a JSON request with one game's ID and its offered quotes. The following
numbers are a synthetic format example, not captured market prices:

```json
{
  "game_id": "YOUR_GAME_ID",
  "offers": [
    {"side": "home", "handicap": -3, "american_odds": -110},
    {"side": "away", "handicap": 3, "american_odds": -105}
  ]
}
```

Optional fields on each offer are commission, stake_fee, quote_id, book and
quote_utc. A request must contain exactly game_id and offers. Outcomes are not
accepted. Quotes inside that request are asserted to belong to that game; the
caller must bind the request to the actual provider event. A list may be empty,
which yields a pass. Missing/invalid prices and malformed PMFs fail explicitly.

```bash
python research/r003_spread_ev.py /path/to/request.json
python research/r003_spread_ev.py /path/to/request.json --pmfs /path/to/marginal_probabilities.npz
```

The CLI prints JSON to stdout. It records every offer's cover/loss/push
probabilities, payout, fees and EV; the chosen offer or pass; policy identity,
game ID, arm and source PMF hash. It makes no file writes or network requests.
The PMF loader checks unique game IDs and row alignment. Saved float32 PMF
rounding within 2e-6 of unit mass is normalized; material errors are rejected.

## Evidence and limits

R003's original cover probabilities at the original line already came from its
joint PMF. The previous spread comparison chose sides by projected mean minus
market line; this new evaluator provides the requested probability-and-price
selection policy separately. Proper settlement does not establish calibrated
probabilities or a true positive EV. R003's support correction remains too small
under its locked research advancement rule.

Historical artifacts lack actual spread-side odds and independently verified
capture times. No historical spread ROI or forward result is claimed here.
User-supplied book/timestamp fields are retained as declarations, not verified.
There is no provider adapter, execution, forward-cohort activation, production
model change or ledger change. Evaluate any future comparison under a separately
locked fresh protocol with retained contemporaneous quotes and outcomes.

All 2,462 archived empirical R003 marginal forecasts agree with their stored
cover/loss/push probabilities at the original handicap to a maximum absolute
error of 6.61e-9. This is an event-probability compatibility check, not an ROI
test. Every imported frozen file still matches its recorded hash.

Repository verification: 603 tests passed, 1 expected failure; all 32 focused
tests passed. Data validation passes for 43 files; the notebook is already in
sync. Two existing pandas future warnings originate in site code.

Focused tests exercise
integer/half-point/zero handicaps, both sides' signs, push-aware EV, mean-versus-
cover disagreement, price-sensitive selection, costs, passes, invalid inputs,
NPZ row alignment, outcome exclusion, CLI roundtrips and read-only behavior.
