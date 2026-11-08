# Phase 4 report — parser fixes, constructions, and article trial

Date: 2026-11-04  
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike`

## Implemented

- Normalized `mark` and subject dependencies attached one level below clause auxiliaries, shared by the syntax consumers. The phase-3 nested-relative-clause regression remains rejected.
- Added a policy-gated imperative path and aggregate `imperative_accepted` counter.
- Added three closed-world construction families over stored token features. Construction frame validation now compiles constrained templates: literals are escaped, and only declared positional slots and single-word alternatives are interpreted.
- Kept the reporting-verb path first; construction matching receives only its misses. Mining code remains independent of spaCy.
- Extracted shared ingest preparation: parser → section detector → analyzer called once per section. Both worker `_ingest` and the trial use it; the trial creates `MiningItem` with the detected `section_code` and within-section previous-sentence context.
- Added aggregate-only article trial with a rights preflight. It matches every file's blob key to an article with `allows_mining=true` before opening content.
- Added opt-in Windows-only `--dump <path>` for owner review. It accepts only a new path under the Git-ignored worktree `tmp/`, locks that directory for the run, and writes accepted imperative and coordinated-reporting sentences there. The report remains aggregate-only.
- Documented the phase-3 modal/epistemic observations without changing their behavior.

## Article trial

The trial read 10 Markdown files from `apps/backend/data/blobs/articles` after the database preflight. The matching article rows use license code `DEV-UNVERIFIED` and have `allows_mining=true`. That metadata flag is not a legal-rights determination. No source text or per-article output was written to the report.

Environment: `en_core_web_sm` model `3.8.0`, spaCy `3.8.18`, construction registry `0.1.0`.

| Measure | Count |
|---|---:|
| Files / sentences | 10 / 5,321 |
| Excluded by section | 2,049 |
| Filter kept | 2,316 |
| Imperatives accepted | 16 |
| Reporting extraction | 116 |
| Coordinated reporting verbs | 7 |
| Invalid-token fallbacks | 0 |
| Construction matches: author_action | 8 |
| Construction matches: relation_role | 0 |
| Construction matches: performance | 0 |

Filter rejections: excluded section 2,049; caption 1; length 258; math 351; no finite verb 185; numeric 60; root not verbal 71; table row 30.

Extraction rejections: coordinated reporting verbs 7; empty noun phrase 9; no reporting verb 2,008; no subject 19; no `that` 151; subject not nominal 5; subject too long 1. Construction rejections: coordinated construction 20; missing child 106; no anchor 2,036; unmatched content 38.

These counts describe this file set only. The opt-in dump at `tmp/phase4-manual-review-20261104.txt` contains 23 records: 16 imperative labels and 7 coordinated-reporting labels. Its sentence contents are not included in this report. The owner has not reviewed the dump, so an imperative false-positive estimate is not available. The owner has not set a coordination threshold, so that policy decision remains open. The zero matches in two construction groups are coverage observations, not evidence that those patterns do not occur in other articles.

## Trial command

From `apps/backend` in the worktree, `DATABASE_URL` was set from the non-secret `.env.example` connection string with the local database port set to `55432`; the dedicated model environment was used:

```powershell
& '..\..\tmp\phase3-spacy-venv\Scripts\python.exe' scripts/mining_trial_report.py `
  'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/apps/backend/data/blobs/articles' `
  --blob-root 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/apps/backend/data/blobs' `
  --model en_core_web_sm `
  --dump '..\..\tmp\phase4-manual-review-20261104.txt'
```

The script prints aggregate counts and model/license metadata only. It checks database mining rights before reading the files. The optional local dump is not printed.

## Verification

Commands: `uv run --no-sync pytest tests/unit -q -p no:cacheprovider`; `NLP_ENGINE=regex uv run --no-sync pytest tests/integration/corpus/test_ingestion_jobs.py -q -p no:cacheprovider`; and the same PostgreSQL command with `NLP_ENGINE=spacy` through `tmp/phase3-spacy-venv/Scripts/python.exe`. Unit suite after the shared ingest refactor: 444 passed, 1 skipped. PostgreSQL corpus-ingest integration after the refactor: 11 passed in regex mode and 11 passed in spaCy mode. Ruff and formatting passed; mypy reported no issues in 185 source files. The broader PostgreSQL integration suite passed 70 tests per mode before the shared-helper refactor and was not rerun in full afterward; those earlier runs each emitted three Starlette deprecation warnings.

## Open owner decisions

- Manually review the 16 imperative acceptances and estimate false positives.
- Set a coordination threshold before deciding whether the 7 observed coordinated reporting cases should be supported.
- Review construction coverage on additional suitable articles before expanding the registry.
- Modal tense remains regex-derived for `might have suggested`; a modal + `have` + participle could instead be treated as `present_perfect`. `epistemic_strength=None` for mixed strength cues is intentional for now.
