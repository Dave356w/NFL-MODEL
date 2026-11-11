# Official injury reports and inactives for v1.22

v1.22 keeps v1.19's ten fitted terms and coefficients for the same training inputs. It adds
sourced corrections for upcoming games. Non-QB absence columns still have no fitted coefficient.
This release establishes correct player selection and temporal safeguards, not a demonstrated
increase in predictive accuracy or betting returns.

## Automatic collection

`availability_collect.py` reads official current-game injury tables and discovers official inactive
announcements through NFL.com's inactive hub. RSS polling, team-news fact extraction and
news-freshness lock requirements are retired (owner request 2026-11-09). No API key or model-generated interpretation is required. The model refreshes
collection before scoring upcoming games. `.github/workflows/availability.yml` also polls every
15 minutes, sharing the build's serialized `site-build` queue. GitHub schedules are best effort;
the held build collects sources every 15 minutes during long waits and refreshes the model
again before the 60-minute cutoff. A fresh candidate for one game cannot suppress retries
for another game at the same kickoff.

```bash
python availability_collect.py                 # collect without running the model
python availability_collect.py --force          # recheck sources now
python validate_data_files.py                  # includes hashes and fact-to-source links
```

| Generated file in `data/` | Purpose |
|---|---|
| `team_news.jsonl` | Retired RSS evidence, retained unchanged for audit; no production appends |
| `availability_sources.jsonl` | Parsed factual tables/lists/announcements, source URLs and capture hashes |
| `availability_auto_observations.jsonl` | Confirmed game/player facts linked to saved source evidence |
| `availability_review.jsonl` | Uncertain announcements, unknown players and unsupported formats |
| `availability_collection_status.json` | Latest checks, failures and report/inactive completeness per team/game |
| `ats_capture_status.json` | Each game's candidate/lock state (including the watcher's `lock_runtime` stores) and reasons the latest full-build board cannot lock; rewritten by every full build. `lock_runtime/watcher_status.json` is the watcher's own live heartbeat |
| `forecast_refreshes.jsonl` | Immutable pregame board refreshes, including blocked projections, their map and injury evidence |

The first four files are append-only; only operational health is replaced atomically. Rechecking
unchanged evidence updates health without changing its first-capture time. A report that changes
and later reverts receives a new capture. Full article prose is not republished.

Injury tables must identify the scheduled week and both opponents. A final report also requires
the final practice day to be populated and every player to resolve to an exact GSIS ID. Blank
practice cells, missing tables and unknown players remain incomplete. The explicit `(-)` marker
for a player removed from a practice report is distinct from an unpublished blank. Undated tables
use their first capture as the conservative effective/publication bound, explicitly labelled
`first_capture`; they are never backdated.

Inactive lists must be published before kickoff on that game's Eastern calendar date and identify
the correct week/opponent and team section. Each listed player becomes ineligible, including an
emergency third QB. A revised list supersedes the old list's observations; omission alone never
asserts health or active status. Box-score participation and ESPN roster `active` flags are not
used to infer an official inactive list.

A list is complete only when every row in the team's section parses exactly. The team's rows
must form one contiguous block under a single section. Any list-shaped line that names a player
or carries a position prefix must resolve, including an unknown prefix, a bare name or a one-word
name. Otherwise the whole list is rejected rather than accepted with that player missing. A club
page whose text flattens its bullets may use the HTML bullet list instead, but only if that list
contains every name found in the text. Lines are read from the page's rendered blocks
(paragraphs, list items, headings, line breaks) when it has them, because JSON-LD article text
often joins blocks without separators. A position-prefixed player name joined to other text
rejects the list.

A failed revision of the page that supplied the accepted list withdraws completeness. Any other
failure of an NFL.com list covering this game also withdraws it, and outranks another page's
success in the same refresh. A club article's failure is queued for review but cannot withdraw a
list accepted from another page. Club articles are often prose or both-team lists in varied
formats: of 20 club pages from 2026 week 8, 7 parsed (each checked row by row against the page)
and 13 were rejected. `tests/test_club_inactive_formats.py` keeps those formats as fixtures.

Legacy v1.21 news parsing and its fixtures are retained for archive compatibility only. New
production forecasts exclude every automatic `official_team_news` fact, including older facts
already in the journal. Confirmed owner-curated corrections remain a separate supported input.

Both teams need successful source checks within 35 minutes of the forecast. ATS candidates
additionally require both complete official inactive lists and checks fresh through the cutoff.
Completeness must link to the actual saved source facts. Missing/stale reports, official inactive-article
download failures, unresolved reports or an unknown player on an updated inactive list prevent a
candidate. No earlier candidate can silently substitute for the missing lists. The hold watches
scheduled games even before a candidate exists, refreshes at T-70, and freezes only candidates
already saved by T-60. A failed refresh cannot create a late selection.

The collection workflow exposes a team-by-team job summary. The CLI also fails on incomplete final
reports within 24 hours of kickoff and missing official inactive lists within 85 minutes. Reports
for more distant games do not fail that readiness check. Transient schedule/roster downloads are
retried three times; exhausted failures are saved in operational health without replacing source
evidence or substituting stale roster identities. A failed latest source check blocks readiness
even if an earlier success is less than 35 minutes old. Previous evidence is retained. Unpublished Sunday reports
on Wednesday are pending, not healthy. Unsupported source formats or unresolved player identities
need a parser/identity correction before automated completeness can be certified.

## Inputs and resolution

Existing v1.21 locks whose deadlines precede 2026-11-09 19:30 UTC remain authoritative across
the retirement. They stay under their actual revision and timestamps in the original journals.
Tampa Bay–Chicago is explicitly authorized for recovery from commit
`b049776c391f7903623b7a2cd650f28eb198f44a` (00:13 UTC, before its 00:20 cutoff): Tampa Bay +6.
Its original parser blocker and actual recovery time stay in the backend record.

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
v1.16 through v1.21 retain their frozen config signatures and archives. v1.22 has a new
revision, output folder and signature; the previous season replay cutoff remains unchanged.

Each team gets an availability evidence object containing its selected observations, baseline
injury/roster input hashes, projected QB, final-report completeness, reference week and blockers.
The board carries that object and its hash through the compact snapshot. Forward predictions
and ATS candidates freeze it alongside their existing inputs. ATS archive validation independently
checks game/team identity, source timing, completeness and the forecast cutoff. New corrections
cannot change existing candidates or locked decisions.

`data/latest` and `data/projections` remain rolling reporting views. Full site builds also append
each observed pregame refresh to `forecast_refreshes.jsonl`, including projections blocked by
availability checks. Hashes, actual observation times, map rules and injury evidence are retained.
This journal is diagnostic only: it cannot create a lock, authorize a retro lock or enter grading.
Existing first-forward snapshots, candidates and locks are never rewritten. Pages-only publications
do not append forecast refreshes.

v1.22 never treats practice-only data as a complete final report merely because kickoff is close.
Legacy rows keep their old report gate. A v1.20/v1.21/v1.22 ATS board missing its evidence columns cannot
produce a candidate. The public site retains its existing ATS presentation; source details stay
in repository outputs and archives.

## Validation and remaining limits

Game-card injury notes (`report_notes.csv`) show the sourced facts the forecast applied. These
include official statuses, official inactives (labelled as such) and sourced roster activations.
A team whose resolution has blockers keeps the feed's notes, as the model does. One sourced player
status does not mark the team's report final.

Tests cover late observations, future effective times, pending deals, team/game isolation,
same-week additions, returns, medical exclusions, outdated clearances, conflicting starters,
unknown IDs, corrupt journals, evidence tampering, unchanged historical inputs, unchanged
coefficients, shadow isolation and immutable ATS capture/finalization.

RSS feeds are retired. Official injury tables and inactive announcements are collected
automatically; unresolved names or incomplete lists remain blocked and visible in diagnostics. Routine injury, roster and depth-chart downloads continue.
An absence of news is not proof of health. Broader injury coefficients or new QB mixture
probabilities need separate chronological and forward validation before adoption.

Research replay checks preserve the original result and provenance files byte for byte after
verifying the numerical outputs. A new runner revision/signature and verified model/grading
source hashes are recorded separately in `_replay_validation.json` in the job artifact. Only
those execution identity fields may differ; input hashes, recipes, outcomes, schema, text and
integer values remain strict. A numerical change still fails, and a failed rerun replaces any
earlier PASS audit. Original research files are not relabelled with the new production revision.
For the H10/H11/H13 reports, `--frozen-data-at-report` exports the `data/` tree from the Git
commit that wrote each report into a temporary directory. The current code replays against that
snapshot, and the audit records its commit and archive hash. This prevents a growing live ledger
from being compared to an older report's sample. The scheduled research job still scores current
data. The ladder workflow retains its pinned numerical-library versions, including pandas 2.2.3.

Before a PR, run `python sync_notebook.py`, `python validate_data_files.py`, and
`python -m pytest tests/ -q`. The three previously failing snapshot assertions now distinguish
annual targets from weekly map exports and settle historical ROI at actual spread prices.
