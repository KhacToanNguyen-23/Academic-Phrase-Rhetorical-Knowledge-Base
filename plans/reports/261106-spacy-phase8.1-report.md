# Phase 8.1 report — construction matcher correctness recovery

Date: 2026-11-06  
Worktree: `D:\6_OJT\aprkb-spacy-spike`  
Branch: `feat/spacy-nlp-spike`  
Base: `184bc02` (`184bc0203f4d66b1d487354245df63adcd135ace`)  
Status: **not accepted** — the mandatory 42-instance regression and a fresh integration run are
not verified.

## Changes

- Fixed object-internal preposition classification in `ConstructionMatcher`. A complete direct
  object subtree now remains inside the `X` source span. Only prepositions attached directly to
  the predicate are considered construction adjuncts and checked against the existing closed
  adjunct registry. The registry was not expanded. This was an implementation bug; ADR-0008's
  source-preserving frame contract does not require rejecting object-internal PPs.
- Added `construction_verb_groups.yaml` v0.1.0, separate from anchor and adjunct policy. The
  provisional modifier candidates are `also`, `first`, `then`, `therefore`, `additionally`,
  `finally`, `next`, and `here`; auxiliary candidates are `have` and `will`. Every list is marked
  `TODO(owner, FR-06.2)`. Eligibility requires dependency, POS and a policy-approved surface
  position. Main-verb `have` is not consumed as an auxiliary. No anchor or adjunct permission was
  added.
- Split construction rejections where the inspected structure supports a stable reason:
  `missing_subject`, `missing_object`, `unsupported_subject`, `unsupported_voice`,
  `unsupported_adjunct`, `unsupported_coordination`, `invalid_source_span`,
  `unsafe_clause_boundary`, and `ambiguous_dependency`. Other construction families retain
  their prior reasons.
- Added 27 self-authored fixture sentences and snapshots for object-internal PPs, predicate-level
  positive/negative PPs, modifier positions, auxiliary roles and hard negatives. The snapshot
  file now has 142 entries; Phase 9.1 previously recorded 115 entries. No article sentences or
  frames were added to this report.
- Updated ADR-0013, the policies README and the Phase 9.1 report. No changes were made to
  `SlotAbstractor` or the Phase 9.1 subject allowlist.

## Workstream 0 diagnosis

The pre-change diagnostic was saved before matcher behavior changed in
`261106-spacy-phase8.1-diagnostic.md`. On the inspected set of 708 kept sentences with subject
`we` and one of 11 registered anchors, the prior matcher had 45 matches. It rejected 369 as
`unlisted_adjunct`, 128 as `missing_child`, 87 as `coordinated_construction`, 66 as `unsafe_frame`,
10 as `too_many_adjuncts`, and 3 as `unsupported_subject`.

Of 290 investigated preposition occurrences, 221 were attached inside the direct-object subtree
and 69 to the predicate. The old matcher merged object descendants with predicate adjuncts; the
object-span helper also removed those descendants and could create an invalid source span. The
128 `missing_child` cases split into 58 invalid object-content spans and 70 without a uniquely
resolved direct-object path. The 66 `unsafe_frame` cases had overlapping boundary features; no
single character pattern explained all of them. Modifier and auxiliary candidates were inventoried
by dependency and position before adding the separate candidate policy.

The dependency/position audit counted 118 candidate-token occurrences across 111 sentences:
96 modifier occurrences and 22 auxiliary occurrences. Modifier POS/dependency was `ADV`/`advmod`
for all but one `next` token parsed as `PROPN`; that token is rejected. Eligible modifier positions
counted 51 before-subject, 44 between-subject-and-anchor, and 1 after-anchor-before-object. The
auxiliary candidates were dependency `aux` with POS `AUX`; main-verb uses of `have` did not meet
that shape. These are candidate observations, not unconditional match permissions.

## Counts-only comparison

All figures below concern the same 51 stored articles in one field (federated learning). The
sample has one exact duplicate (FedQueue, two copies) and a partial duplicate (two survey
versions); these inflate per-article counts. The Phase 7 and Phase 8 figures are from their
existing reports. Phase 9.1 figures are the pre-Phase-8.1 comparison. Phase 8.1 figures are from
the fresh read-only run against the same 51 blobs. No source sentence or frame is included.

| Measure | Phase 7 | Phase 8 | Phase 9.1 before 8.1 | Phase 8.1 |
|---|---:|---:|---:|---:|
| Sentences scanned | 29,344 | 29,344 | 29,344 | 29,344 |
| Kept after sentence filtering | 12,178 | 12,178 | 12,178 | 12,178 |
| Reporting extractions | 203 | 203 | 203 | 203 |
| Construction extractions | 43 | 46 | 49 | 160 |
| `author_action` extractions | 42 | 45 | 48 | 159 |
| Distinct frame identities as counted by each run | 70 | 102 | 105 | 164 |
| Distinct cluster keys | 207 | 239 | 242 | 306 |
| Frames with document frequency >= 2 | not measured | 35 | 35 | 52 |

The Phase 8.1 matcher run reported these construction rejection counts:

| Reason | Count |
|---|---:|
| `no_anchor` | 10,139 |
| `unsupported_subject` | 492 |
| `unsupported_coordination` | 194 |
| `unsupported_adjunct` | 163 |
| `unsafe_clause_boundary` | 144 |
| `missing_subject` | 57 |
| `missing_child` | 60 |
| `missing_object` | 26 |
| `ambiguous_dependency` | 204 |
| `unsupported_voice` | 237 |
| `unmatched_content` | 49 |
| `coordinated_construction` | 45 |
| `too_many_adjuncts` | 4 |
| `invalid_source_span` | 1 |

The previous report series used different frame-key collection code, so the distinct-frame
figures are implementation-specific and should not be interpreted as one directly comparable
canonical frame metric. Object-internal PP occurrences (221 of 290) and predicate-level PP
occurrences (69 of 290) are the pre-change diagnostic counts. A separate post-change corpus count
of accepted object-internal PPs, approved adjuncts, modifiers and auxiliaries was not emitted by
the available read-only script; those totals remain open.

## Mandatory 42-instance regression — not verified

The original 42-instance table in `261105-spacy-phase8-report.md` contains Phase 7 and Phase 8
hashes, but the repository and supplied scratchpad do not contain the extraction script or
manifest that maps those anonymous source identities back to corpus sentence ordinal and source
offset. The table documents only that identity used a SHA-256 over blob identity, ordinal and
offset; it does not specify the canonical byte serialization. Consequently, the Phase 8.1 run
could not be joined to the 42 existing identities without inventing a hash recipe or guessing the
rows. No Phase 8.1 hashes or outcomes are fabricated here.

This leaves the following mandatory checks unverified: restoration of all 42 original outputs,
preservation of the 14 approved Phase 8 changes, zero new regressions, and deterministic hashes
across repeated runs. Phase 8.1 is therefore not accepted. The exact technical blocker is missing
reproducible identity-generation metadata for the existing anonymous baseline; it is not evidence
that any particular instance failed matching.

## Phase 9.1 regression

The full unit suite passed with Phase 9.1 cases active. The approved subjects remain exactly `we`,
`this paper`, `this study`, and `this article`; hard negatives remain in the construction tests,
and passive voice returns `unsupported_voice`. The subject remains literal in the source-derived
frame. No anchors, adjunct prepositions, subject families or lead-ins were added in Phase 8.1.
The forms `we present [X]` and `this paper presents [X]` still produce separate frame identities;
merging them remains a future `frame_key` / P3 decision.

## Verification

Commands ran from `apps/backend`:

| Check | Command / environment | Result |
|---|---|---|
| Ruff | `ruff check --no-cache src/aprkb tests/unit` | Passed |
| Ruff format | `ruff format --check --no-cache src/aprkb tests/unit` | Passed; 255 files already formatted |
| Mypy | `.venv\Scripts\python.exe -m mypy --cache-dir %TEMP%\phase81-mypy-cache src/aprkb` | Passed; 201 source files |
| Unit suite, spaCy | Phase 3 venv, `PYTHONPATH=src`, `pytest tests/unit -q -p no:cacheprovider --basetemp=%TEMP%\phase81-unit-spacy` | 645 passed; two existing warnings |
| Unit suite, no spaCy | `.venv`, `PYTHONPATH=src`, same pytest options and isolated temp | 633 passed, 1 skipped; two existing warnings |
| Construction tests, regex | `.venv`, `NLP_ENGINE=regex`, focused `test_phase4_constructions.py` | 69 passed |
| Construction tests, spaCy | Phase 3 venv, `PYTHONPATH=src`, `NLP_ENGINE=spacy` | 69 passed |
| Corpus counts | Phase 3 venv, supplied read-only corpus helper, 51 allowed blob keys | Completed; 29,344 sentences, 12,178 kept; counts above |
| PostgreSQL integration, regex | Dedicated `localhost:55433/aprkb_test` | Not rerun: command safety hook rejected the in-memory password-bearing URL handoff to `TEST_DATABASE_URL` |
| PostgreSQL integration, spaCy | Dedicated `localhost:55433/aprkb_test` | Not rerun for the same reason |
| `git diff --check` | From worktree root | Passed |

The owner-provided independent verification in the Phase 8.1 request records 79/79 integration
tests passing in each engine with actual test-container credentials. The Phase 9.1 report has
been corrected to reflect that evidence and to identify the actual base `184bc02`. Those prior
results are not a fresh verification of the Phase 8.1 matcher changes. The real database on port
55432 was not used.

## Remaining acceptance items

- Provide or restore the exact deterministic source-identity serialization / regression manifest,
  then produce the required 42-row Phase 7 / Phase 8 / Phase 8.1 hash table.
- Re-run both PostgreSQL integration modes with the verified test-container credential handoff
  available to the test process.
- Emit counts-only post-change totals for object-internal PPs, approved adjuncts, modifiers and
  auxiliaries.
- Reassess the resulting 42-instance outcomes and any changed Phase 8 improvements before owner
  acceptance.

All working-tree changes remain uncommitted and unpushed. Pre-existing gold-label edits remain
untouched.
