# Phase 9.1 report — self-referential author-action subjects

Date: 2026-11-06  
Worktree: `D:\6_OJT\aprkb-spacy-spike`  
Branch: `feat/spacy-nlp-spike`  
Base: `184bc02` (`184bc0203f4d66b1d487354245df63adcd135ace`); changes remain uncommitted.

## Result

Phase 9.1 adds only the approved literal active subjects `this paper`, `this study`, and
`this article` to the Phase 8 `author_action` construction. The existing `we` subject remains
allowed. A subject is accepted only when its complete active `nsubj` subtree case-folds to an
exact registry entry. The subject remains literal in the frame; only existing object and
registered adjunct spans become slots. Matching, frame generation and validation use dependency
features and source spans. No regex subject matcher, anchor, adjunct, slot rule or frame contract
was added.

Passive subjects reject as `unsupported_voice`; other or expanded subject phrases reject as
`unsupported_subject`. Copular clauses remain unsupported because they have no approved
author-action anchor. The policy registry is version `0.3.0`. The subject allowlist is explicit;
anchor and adjunct inventories remain provisional and retain `TODO(owner, FR-06.2)`.

## Counts-only corpus comparison

The read-only analysis used the same 51 rights-checked stored articles as Phase 8. It emitted only
counts and anonymous hashes, not source sentences or frames. The corpus represents one field
(federated learning). It includes one exact duplicate (FedQueue, two copies) and a partial
duplicate (two versions of a survey), so duplicates inflate per-article counts.

| Measure | Phase 8 | Phase 9.1 |
|---|---:|---:|
| Sentences scanned | 29,344 | 29,344 |
| Filtered / kept | 17,166 / 12,178 | 17,166 / 12,178 |
| Reporting-path extractions | 203 | 203 |
| Construction matches | 46 (45 `author_action`, 1 `performance`) | 49 (48 `author_action`, 1 `performance`) |
| Distinct masked frames | 102 | 105 |
| Cluster keys | 239 | 242 |
| Frames with document frequency >= 2 | 35 | 35 |

These figures are the Phase 9.1 comparison before the Phase 8.1 correctness recovery. Phase 8.1
re-ran the same corpus with the object-internal PP and controlled modifier/auxiliary fixes; its
updated totals are recorded in `261106-spacy-phase8.1-report.md`. The subject frames
`we present [X]` and `this paper presents [X]` remain separate; merging them is a future
`frame_key` / P3 decision.

Subject counts: `this paper` occurred 25 times (24 active `nsubj`, one passive `nsubjpass`) and
yielded 20 anchor-root candidates. `this study` occurred six times (all active) and yielded two
candidates. `this article` had zero occurrences. Of the 22 candidates, three became new
`author_action` matches and 19 were rejected:

| Phase 9.1 rejection reason | Candidate count |
|---|---:|
| `unlisted_adjunct` | 15 |
| `coordinated_construction` | 2 |
| `missing_child` | 1 |
| `unsafe_frame` | 1 |
| **Total rejected** | **19** |

For these candidates, Phase 8 recorded 20 `missing_child` and two `coordinated_construction`
rejections. All-corpus Phase 9.1 results: 48 `author_action` and one `performance` match; rejection
counts were `unsupported_subject` 589, `no_anchor` 10,139, `missing_child` 212,
`coordinated_construction` 239, `unlisted_adjunct` 384, `unsafe_frame` 67,
`unmatched_content` 49, and `too_many_adjuncts` 10. These are candidate counts, not recall estimates.
The three new extractions demonstrate a coverage improvement on this 22-instance comparison
set only; they do not prove a corresponding coverage increase across the full corpus.

### Anonymous instance tracking

Each row has a SHA-256 source identity and, when accepted, a SHA-256 masked-frame hash. `—` means
the phase rejected the candidate and emitted no frame. Rejection reasons make every result
traceable without storing source text.

| Source identity SHA-256 | Phase 8 frame SHA-256 | Phase 8 reason | Phase 9.1 frame SHA-256 | Status | Phase 9.1 reason |
|---|---|---|---|---|---|
| 16f4094901ff3861b1c8d23a42bbddfb83b5f4eb9998dfd85fc9fa049251f947 | — | missing_child | — | rejected | unlisted_adjunct |
| 37e207fad3acf7833f24e0e67f98f4672cc0983d55b0f3c7aef66f25891bbd1b | — | missing_child | — | rejected | missing_child |
| 44d2cfbc1b54c88b30fddc8a1bfdfd72249a8ff6b8f2dab2706fe82330eef125 | — | missing_child | — | rejected | unlisted_adjunct |
| 426d50a9b30c99c89eaea5b4a562303d2f7b99960198860adbfaa8f9ff7572a0 | — | missing_child | 480f4261358219fd6a355947a4a6088adfad4ff1be64c7473a0e57e6c0c58db9 | changed | — |
| 7f1a8ccf2e841ec6fb17245f9a494ab56d81985b488903d5ab9016ed33ee9b49 | — | missing_child | — | rejected | unlisted_adjunct |
| ac9114a5ff747fb862783cfe502ce3066e742c47c0261ac387641abd54fb49c9 | — | missing_child | — | rejected | unlisted_adjunct |
| 15e557fb39ad85647eb1da8a9b6a37d34d15c3d3aeac8f963bb5294841c10932 | — | missing_child | — | rejected | unlisted_adjunct |
| c3254af62deea9183908a0c87f0f9a96bb355e20c90fa753026b32e7b55f539b | — | coordinated_construction | — | rejected | coordinated_construction |
| 70a97619bd167d5555d494fdf24a15dcd5125ddb41ec8e90f1f2194a42711225 | — | missing_child | — | rejected | unlisted_adjunct |
| 2e10cdf3b3742df297ca2f2ba12265102393036612d6d4c414892ae9fb02de77 | — | missing_child | — | rejected | unlisted_adjunct |
| 03f9244a8109bf060d21d93a572df201b48f4c547296fd53f265899242a03f16 | — | missing_child | — | rejected | unlisted_adjunct |
| 9e4f6880d315b1cdda70c2063c0630d589c784a3c503e5afe15512f8ea60956f | — | missing_child | — | rejected | unlisted_adjunct |
| 8e91ce6730770289d1242091fe4e63501ecfc329990336505deff5320414c7aa | — | missing_child | — | rejected | unlisted_adjunct |
| 7902de2cd097d0adad5f2a835e0535e5b9e3c46cf787d972f2d712ee2ce87e38 | — | missing_child | — | rejected | unlisted_adjunct |
| 1ab997599362716e9ee048b4c009c21a8dac5a4c0267e8ada8695c86d4e5a657 | — | coordinated_construction | — | rejected | coordinated_construction |
| 8dc5eae94987701ef09da3b2ef16843498c4de6e9b7bea3f63487bcce9ed1608 | — | missing_child | — | rejected | unlisted_adjunct |
| 9784d181d78430b86d870ae53c96e513e478a05d2ac61d86f50fc7ef7eb51dbc | — | missing_child | — | rejected | unlisted_adjunct |
| 8901a22973977f5a17234351b44eb22f3da6bfcdb1edbc81b4e3fbf1aace6d3e | — | missing_child | — | rejected | unlisted_adjunct |
| e1f23042ddd1e643b6cfc774ccdf7d5edea326a76f8f793f7bd7621f762b0525 | — | missing_child | — | rejected | unsafe_frame |
| 2ad2bf8c613d3a7cd8c81e6d8e44ce0b26038aa5b87760558cc2d758f9bbf8a8 | — | missing_child | 90fda4e8f91407c98fbbe422a96781873bb168d1483074fe96f307ea532b372d | changed | — |
| 7fa5f5680d8f4ee7e8b1334a881582c575c3a8e08fa4d683df210fedc564cde9 | — | missing_child | fa48972b75af071c294085def38df12b501d064cc2347138ffec78f6dbbd1556 | changed | — |
| 11a742f177bd56c6a17726353afeeb548eaaf51f402681e9cc47987ef77dfd92 | — | missing_child | — | rejected | unlisted_adjunct |

## Fixtures, tests and expectation changes

Eleven self-authored Phase 9.1 cases were added to the NLP-spike fixtures and token snapshots.
The 104 previous snapshot records remain byte-identical; the regenerated file contains 115 records.
Cases cover all three approved subjects, an adjunct-bearing positive, unsupported `this method`,
`this result`, `this approach`, `this work`, an expanded `this paper` subject, a passive negative,
and a copular negative.

| Expectation | Result | Reason |
|---|---|---|
| `this paper`, `this study`, `this article` with an existing author-action anchor | Accept only when other closed-world checks pass; preserve subject literally | These are the only newly approved active subject forms |
| `this method`, `this result`, `this approach`, `this work` | `unsupported_subject` | A subject that refers to an object in the paper does not establish author ownership |
| Extra content in the complete subject subtree | `unsupported_subject` | Eligibility requires an exact subject-list match |
| Passive subject | `unsupported_voice` | Passive is out of scope |
| Copula without an approved action anchor | `no_anchor` | Copula is out of scope |
| Existing `we` construction | Remains accepted | Phase 9.1 retains the previous subject and slot behavior |

Frame assertions reconstruct each accepted frame by replacing only selected source spans. Safe-frame
checks accept the three approved subjects and reject an unapproved subject. The subject eligibility
check uses syntax features and does not change reporting-path behavior.

## Verification

Commands ran from `apps/backend`. Test basetemps and tool caches were placed in `%TEMP%` because
default worktree temp/cache locations are not writable in this Windows setup.

| Check | Command / environment | Result |
|---|---|---|
| Ruff | `python -m ruff check src tests` | Passed |
| Ruff format | `python -m ruff format --check src tests` | Passed; 287 files already formatted |
| Mypy | `%MYPY_CACHE_DIR%` set under `%TEMP%`; `.venv\Scripts\mypy.exe src/aprkb` | Passed; 201 source files |
| Full unit suite, regex | `$env:NLP_ENGINE='regex'; python -m pytest tests/unit -q -p no:cacheprovider --basetemp=<new %TEMP% dir>` | 617 passed, 3 existing warnings |
| Construction tests, regex | `$env:NLP_ENGINE='regex'; python -m pytest tests/unit/mining/test_phase4_constructions.py -q -p no:cacheprovider --basetemp=<new %TEMP% dir>` | 41 passed, 1 existing warning |
| Construction tests, spaCy | `$env:PYTHONPATH='src'; $env:NLP_ENGINE='spacy'; <phase3-spacy-venv>\Scripts\python.exe -m pytest tests/unit/mining/test_phase4_constructions.py -q -p no:cacheprovider --basetemp=<new %TEMP% dir>` | 41 passed (spaCy 3.8.18) |
| PostgreSQL integration, regex | Owner-verified `NLP_ENGINE=regex` against `localhost:55433/aprkb_test` with actual test-container credentials | 79 passed (independently verified) |
| PostgreSQL integration, spaCy | Owner-verified `NLP_ENGINE=spacy` against `localhost:55433/aprkb_test` with actual test-container credentials | 79 passed (independently verified) |

The previous failed attempt used placeholder configuration from `.env.example` and targeted only
port 55433; the real database on 55432 was not used. Independent verification with actual
test-container credentials passed both integration suites. Phase 8.1's attempt to rerun these
tests was rejected by the command safety hook because the test command would place the
password-bearing database URL in `TEST_DATABASE_URL`; no credentials were printed.

## Open boundaries

- Only the three exact subjects above are enabled; the corpus sample had no `this article` case.
- Passive voice, copula `be`, `it`, and other `this ...` phrases remain unsupported.
- Counts describe a single-field corpus sample with the duplicates noted above; they are not a
general coverage estimate.
- This phase adds no anchors, adjunct types, or policy phrases. Any later construction expansion
  needs reviewed positive and hard-negative examples, token/dependency snapshots, explicit slot
  boundaries, rejection cases, and regression tests.
- Phase 8.1 must rerun integration after its matcher changes with the verified test-container
  credential handoff available to the test process.
- Changes remain uncommitted and unpushed for owner review.
