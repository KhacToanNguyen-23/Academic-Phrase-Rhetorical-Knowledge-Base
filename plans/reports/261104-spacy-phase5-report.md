# Phase 5 report — frame statistics and journal contrast

Date: 2026-11-04  
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike`

## Implemented

- Added a pure frame-key normalizer: casefold, collapse whitespace, and strip terminal `.`, `!`, or `?`. Verb forms and tense remain distinct.
- Added read-only service, repository, `phrase-stats` CLI command, and Makefile target. The repository selects candidate/frame and article membership only; it never selects sentence text. Articles without mining permission are excluded.
- Pending and accepted candidates count; rejected candidates do not. Each candidate counts once per distinct article, and document frequency counts each article at most once per frame.
- Added score `ln(((df_focal + α)/(n_focal + 2α)) / ((df_bg + α)/(n_bg + 2α)))`, plus recurrence ranking. Small focal sets or an empty background suppress contrast ranking and emit a notice.

## Policy

| Setting | Value |
|---|---:|
| Smoothing α | 0.5 |
| Minimum focal documents | 2 |
| Small-focal warning | fewer than 10 articles |
| Default top results | 50 |
| Included statuses | pending, accepted |

These values are provisional and marked `TODO(owner, FR-06.2)` in the versioned policy.

## Smoke-run limitation

The backend contains 10 mining-allowed article files used for the Phase 4 trial. Their article records have no `import_batch_id` or `journal_id`, so the selector-based CLI cannot define an arbitrary focal subset for these records. No Phase 5 CLI smoke ranking was produced and no article records were modified to manufacture selectors. The service and CLI are covered by unit and PostgreSQL integration tests; this file set does not support a journal-specific claim.

The sample is also too small for stable contrast. A useful run needs a focal batch from one journal plus a background set with other journals.

## Verification

Full backend unit suite after the shared ingest refactor: 444 passed, 1 skipped. The broader PostgreSQL integration suite passed 70 tests in regex and 70 in spaCy mode before that refactor. Afterward, the corpus-ingest integration file passed 11 tests in each mode. Ruff and formatting passed, mypy reported no issues in 185 source files, and `git diff --check` found no whitespace errors.

## Open items

- Endpoint and UI for viewing rankings.
- Owner decision on merging number variants such as `show` and `shows`.
- Lemma-level grouping, significance testing, and per-section statistics.
- Journal selection once imported articles carry `journal_id`.
