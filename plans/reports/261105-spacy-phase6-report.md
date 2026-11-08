# spaCy phase 6: slot abstractor frames and ownership

Date: 2026-11-05  
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike`  
Base: `30a55a2`  
Status: implementation and self-authored regressions are present; changes remain uncommitted.

## Changes

- The syntax path now renders from its syntax `_Located` result and ROOT only. It retains a lead-in only when it matches `policies/lexicon/lead_ins.yaml`; the seven phrases are the complete owner-approved 0.1.0 set. Unlisted lead-ins, unlisted adverbs, unexplained gaps, and non-punctuation tails reject with counted reasons. The regex locator and its frame rendering are unchanged; only the explicit FR-05 ownership cases alter regex slot shape/ownership.
- Subject and clause citations directly following their spans are kept in the slot and receive the CITATION signal.
- Syntax tense reads auxiliary tags. `past_perfect` is available in mining and gold-label enums. `MiningItem.modality` carries the modal word from the literal verb group; it is not included in `cluster_key` and is not persisted.
- Ownership is shared by reporting extraction and `ConstructionMatcher`: `we` is OWN; `our`, `the present`, and `the current` are unconditional DET_OWN; `their`, `prior`, `previous`, and `earlier` are DET_PRIOR. `this`, `these`, and `the only` become DET_OWN only with a configured own-study cue in the previous same-section sentence and no citation/prior blocker. Otherwise they remain inside the noun-phrase slot. The cue list is provisional and marked `TODO(owner, FR-06.2)`.
- `EpistemicTagger` now applies irregular forms at the base marker's strength. `has been shown` and `had shown` resolve to `high`.
- Safe-frame validation accepts the optional approved lead-in while retaining the existing slot, verb, connector, and bracket checks.
- The tense inventory found `gold.labels.Tense` also enumerated values, so `past_perfect` was added there. No mining tense field is exposed in the OpenAPI/TypeScript contracts or constrained by a database check; no contract regeneration or migration was needed.

## Regression coverage and expectation changes

All added sentence examples are self-authored. The spaCy token snapshot keeps every prior case unchanged and adds only new cases.

The phase-3 parity test still compares syntax and regex outputs. Its remaining differences are explicitly allow-listed with one-line reasons: syntax may locate a reporting form regex missed; syntax slots follow dependency subtrees/citation boundaries; and the previous `It is widely argued` case is now syntax-only rejection because `widely` is not an approved verb modifier.

Changed expectations and reasons:

| Case | Change | Reason |
|---|---|---|
| `It is widely argued ...` | Accepted frame → `unlisted_modifier` rejection | The closed modifier list excludes `widely`. |
| `Our results surprisingly suggest ...` | Accepted frame → `unlisted_modifier` rejection | The closed modifier list excludes `surprisingly`. |
| `The only result ...` without cue | DET_OWN slots/OWN → one noun-phrase slot/UNCLEAR | Contextual ownership requires a prior same-section cue. |
| `These results ...` without cue, syntax and regex | `[X] [Y] ... [Z]` → `[X] ... [Y]` | The determiner stays literal inside one noun-phrase slot absent a cue. This is the owner-approved FR-05 exception to general regex compatibility. |
| `These findings may indicate ...` | Determiner slots → one noun-phrase slot | Same contextual determiner rule; syntax still locates `indicate` and `may`. |
| Phase-3 parity case 6 | `both_differ` → `only_regex` | Syntax now rejects the unlisted `widely` modifier. |
| Invalid-token fallback fixture using `These results ...` | Updated frame assertion | Invalid tokens fall back to regex, where the explicit contextual-determiner rule applies. |
| Reporting-vs-construction precedence fixture using `These results ...` | Updated frame assertion | Same explicit contextual-determiner rule; reporting still wins over the construction registry. |

Named regressions cover every measured failure class, all seven approved lead-ins, `Recently`, `Surprisingly`, a long free lead-in, the wrong-root `We note ...` case, subject and clause citations, present/past perfect and modal tense, `can also`, the aux-attached `that` parse, unlisted modifiers, ownership cues/blockers, and `This suggests ...` remaining `empty_noun_phrase`.

## Counts-only corpus analysis

The requested after-analysis could not run in this environment: the repository-configured default blob root is absent, and `TEST_DATABASE_URL` is not present in the process environment. An attempt to access the local `.env` variable directly was blocked by the pre-tool sensitive-data guard. No `.env` values or keys were printed. The listener on test port 55433 was present, but no test connection string was available; port 55432 was not used.

| Measure | Before (provided phase-6 baseline) | After |
|---|---:|---:|
| Syntax-path reporting extractions | 342 | Not measured; stored blobs unavailable |
| Lead-in dropped | 125 | Not measured |
| Verb-group words lost (`can`/`also`/etc.) | 20 | Not measured |
| Citation after subject dropped | 4 | Not measured |
| Ownership: subject `we` marked unclear | 160 | Not measured |
| Ownership: `our`, `the present/current` | Not supplied | Not measured |
| Ownership: `their`, prior/previous/earlier | Not supplied | Not measured |
| Ownership: contextual `this`/`these`/`the only` | Not supplied | Not measured |
| Ownership: `et al.` or citation subject | Not supplied | Not measured |
| Rejections: `unlisted_lead_in` | Not tracked | Not measured |
| Rejections: `unlisted_modifier` | Not tracked | Not measured |
| Rejections: `unmatched_content` | Not tracked | Not measured |

Candidate lead-in frequencies from the corpus are unavailable, so no corpus-derived phrase was added to policy. The unapproved lead-in candidate list and counts remain unavailable until the analysis can run. The corpus is one field (federated learning). The 51 stored articles include one exact duplicate (FedQueue, two copies) and a partial duplicate (two versions of a survey); these inflate per-article counts.

## Epistemic findings

Irregular forms inherit their base marker strength: `shown` inherits `show` (`high`), and `proven` inherits `prove` (`absolute`). Common verbs currently unknown unless another declared marker appears include `find/found`, `observe/observed`, `assume/assumed`, `note/noted`, `report/reported`, `argue/argued`, `state/stated`, `claim/claimed`, `propose/proposed`, `reveal/revealed`, `conclude/concluded`, `verify/verified`, and `highlight/highlighted`. No new marker was approved. `None` remains unknown or ambiguous.

The phase-4 A1 aux-attached `that` normalization already passed the snapshot regression for `These findings may indicate that the baseline was undertrained.` No normalization rewrite was needed.

## Verification

Commands were run from `apps/backend` in the specified worktree. The isolated temp paths are under the worktree's `tmp` directory.

- `ruff check --no-cache src tests` — passed.
- `ruff format --check --no-cache src tests` — passed; 287 files already formatted.
- `$env:MYPY_CACHE_DIR = Join-Path $env:TEMP 'aprkb-phase6-mypy-cache'; mypy src/aprkb` — passed, 201 source files.
- `pytest tests/unit -q -p no:cacheprovider --basetemp=../../tmp/phase6-unit-final5` — 534 passed, 1 skipped.
- `$env:NLP_ENGINE = 'regex'; pytest tests/unit -q -p no:cacheprovider --basetemp=../../tmp/phase6-unit-regex-final2` — 534 passed, 1 skipped.
- `pytest tests/unit/mining/test_phase3_syntax.py tests/unit/mining/test_slot_abstraction.py tests/unit/mining/test_phase6_policy_frames.py tests/unit/validation/test_epistemic_markers_policy.py -q -p no:cacheprovider --basetemp=../../tmp/phase6-targeted-final2` — 65 passed.
- `$env:PYTHONPATH = 'src'; & 'D:\6_OJT\aprkb-spacy-spike\tmp\phase3-spacy-venv\Scripts\python.exe' scripts/generate_nlp_token_snapshots.py` — completed. Verified 29 original cases are identical and 28 cases were appended.
- PostgreSQL integration suite under `NLP_ENGINE=regex` and `NLP_ENGINE=spacy` — not run because `TEST_DATABASE_URL` was unavailable through the allowed environment path. No test was pointed at port 55432.
- Counts-only analysis on the 51 stored blobs — not run because the configured blob root was unavailable.

## Open items

- Provide the approved test-only `TEST_DATABASE_URL` in the process environment to run the two PostgreSQL integration modes against `aprkb_test` on port 55433.
- Restore/mount the 51-article blob root to produce the before/after and unapproved-lead-in candidate counts.
- Owner review remains due for the provisional own-study cue list and existing `verb_modifiers` policy list (`TODO(owner, FR-06.2)`).
- Modality is not persisted. `frame_key`/show-shows review merging, synonym expansion, deduplication, and all named out-of-scope work remain deferred.
- Code review found no confirmed P0/P1 defect in the reporting path, ownership rules, policy wiring, validators, or regressions. Review caught a possible regex modality false positive from scanning arbitrary nearby words; this was fixed by reading only the located literal modifier-plus-verb string, with a regression where `may` occurs in the subject. Follow-up review confirmed the fix. Review also noted the same two unavailable verification areas listed above.
