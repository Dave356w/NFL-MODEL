# Availability corrections for v1.20

v1.20 keeps v1.19's ten fitted terms and coefficients for the same training inputs. It adds
sourced corrections for upcoming games. Non-QB absence columns still have no fitted coefficient.
This release establishes correct player selection and temporal safeguards, not a demonstrated
increase in predictive accuracy or betting returns.

## Inputs and resolution

The optional, append-only `data/availability_observations.jsonl` is an owner-curated input,
like `personnel_events.csv`, not a bot-generated model output. Use the capture command below
instead of editing old journal lines. Correct an earlier assertion by appending newer evidence.

Each observation names an exact `game_id` and team, a GSIS player ID for player facts, an HTTPS
source URL, publication time, effective time and first local capture time. All timestamps include
a timezone. The command stamps capture time with the current clock; it cannot be backdated.
Only confirmed observations published, captured and effective by the forecast's availability
snapshot apply. Pending transactions remain inert. Every fact expires with its targeted game.

| Field | Value | Meaning |
|---|---|---|
| `eligible` | `true` / `false` | Explicit eligibility for this game; true requires player name and position |
| `report_status` | `Available`, `Out`, `Doubtful`, `Questionable` | Medical availability for this game |
| `qb_starter` | `true` | Confirmed starting QB; requires player name and `position=QB` |
| `report_complete` | `true` / `false` | Explicit confirmation of a team's complete final report, including zero designations |
| `inactives_complete` | `true` / `false` | Records that a complete inactive list was reviewed; individual exclusions still need player facts |

Eligibility, medical availability and starter role are separate. Adding a player to a team
never makes an injured player medically available. A starter must belong to the eligible QB list.
An explicitly eligible acquisition can enter this game's reference roster, and a returning player
can supersede a legacy personnel exclusion. Final same-week historical rosters are never used to
infer when a signing or activation was knowable.

For the same field, the latest effective and publication times win. Equal-time contradictory
facts block the forecast's lock. Two different confirmed starter IDs at the same time also block.
Newer timestamped injury-feed information beats older medical corrections. An undated existing
Out/Doubtful cannot be cleared automatically: resolve the source timing rather than assuming
the correction is newer. An unknown ID, position mismatch, unresolved QB or ineligible confirmed
starter also prevents a lock.

## Capture a correction

For a team-announced starter (replace the source publication time with the actual one):

```bash
python set_availability.py \
  --game-id 2026_09_JAX_BAL --team BAL \
  --field qb_starter --value true \
  --gsis-id 00-0040981 --player 'Joe Fagnano' --position QB \
  --source-url https://www.baltimoreravens.com/news/transcript-press-conferences-11-3-26 \
  --published-utc 2026-11-03T22:37:06.153Z \
  --reason 'Head coach named the starter for this game.'
```

The optional `--effective-utc` defaults to publication time; `--status pending` records a
transaction that must not yet change eligibility. Team completeness facts omit the player fields.
`report_complete=true` asserts that the entire team's final report was checked. A single player's
news story is not enough. Capture all designated absences before asserting completeness.

The committed Week 9 Baltimore corrections cite the team's own press-conference transcript and
its injury report article. They exclude Jackson and Huntley and name Fagnano. They do not assert
that the full final report or inactive list has been published, and do not add Brissett to Baltimore.

## Forecast and archive behavior

The baseline historical features are built as before. Corrections apply only to upcoming
game/team rows, before scoring those rows with the existing fit. Coefficients are not refitted
on the corrections. The v1.16 shadow is scored and captured from its original, uncorrected inputs.
v1.16, v1.18 and v1.19 retain their frozen config signatures and archives. v1.20 has a new
revision, output folder and signature; the previous season replay cutoff remains unchanged.

Each team gets an availability evidence object containing its selected observations, baseline
injury/roster input hashes, projected QB, final-report completeness, reference week and blockers.
The board carries that object and its hash through the compact snapshot. Forward predictions
and ATS candidates freeze it alongside their existing inputs. ATS archive validation independently
checks game/team identity, source timing, completeness and the forecast cutoff. New corrections
cannot change existing candidates or locked decisions.

v1.20 never treats practice-only data as a complete final report merely because kickoff is close.
Legacy rows keep their old report gate. A v1.20 ATS board missing its evidence columns cannot
produce a candidate. The public site retains its existing ATS presentation; source details stay
in repository outputs and archives.

## Validation and remaining limits

Tests cover late observations, future effective times, pending deals, team/game isolation,
same-week additions, returns, medical exclusions, outdated clearances, conflicting starters,
unknown IDs, corrupt journals, evidence tampering, unchanged historical inputs, unchanged
coefficients, shadow isolation and immutable ATS capture/finalization.

The source feed still refreshes on its own schedule. This change does not scrape every team's
news or automatically ingest official game-day inactive lists. The journal supplies sourced
exceptions; routine injury, roster and depth-chart downloads continue as before. An absence of
news is not proof of health. Broader injury coefficients or new QB mixture probabilities need
separate chronological and forward validation before adoption.

Before a PR, run `python sync_notebook.py`, `python validate_data_files.py`, and
`python -m pytest tests/ -q`. The three previously failing snapshot assertions now distinguish
annual targets from weekly map exports and settle historical ROI at actual spread prices.
