# Phase 5 — per-batch frame statistics and journal contrast

Status: proposed 2026-11-04. Can start right after phase 4 part A; it works with today's reporting-verb
frames and gets better when phase 4 part B adds the construction groups.
Requirement: `FR-06.2`. Product goal: find phrases characteristic of one journal (internal tool).
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike`.

## 1. Idea (owner)

Import one batch containing many articles of one journal, extract every phrase, count identical
phrases, and rank them so the owner can see which phrases are characteristic of that journal.

Two corrections already agreed:

1. Raw repeat counts rank generic academic phrases first (`[X] show that [Y].` appears in 7 of 10 trial
   articles from different journals). Count **documents containing the frame** (document frequency),
   each article at most once, and **contrast** a focal batch with a background set.
2. `candidates.cluster_key` cannot be the counting key. It hashes the slot contents, so on the 10-article
   trial 108 extracted sentences produced 108 distinct keys (45 distinct frames). Keep `cluster_key` for
   sentence-level dedup; count with a separate frame key.

## 2. Scope

In scope: a read-only statistics service, a CLI command, a versioned policy for thresholds, tests, docs.
No schema change, no migration, no change to mining output, no new HTTP endpoint (an endpoint and a UI
page are open items for the owner), no article text in any output.

## 3. Data used

No new tables. Everything is derivable from existing rows:

- `candidates.canonical_frame`, `candidates.source_sentence_ids`, `candidates.status`
- `sentences.article_id` → `articles.import_batch_id`, `articles.journal_id`
- `jobs`/batches are not needed.

A candidate with several `source_sentence_ids` counts once per distinct article.
Exclude candidates whose status is rejected by review (list the statuses used in the report); pending
and accepted both count. State the choice in the output header.

## 4. Frame key

`frame_key(canonical_frame) -> str`: casefold, collapse whitespace, strip trailing `. ! ?`. Pure function in
`modules/mining/frame_key.py`, unit-tested. Do **not** merge `show`/`shows` or tenses (owner tense rule:
different tense ⇒ different cluster; number variants are an open question for the owner). Phase 4 part B
adds the construction id as a prefix to this key; leave a documented extension point.

## 5. Statistics service

`modules/extraction/phrase_stats.py` (or `modules/mining/`, follow the existing layering: router → service
→ repository; this phase adds service + repository only).

Inputs:

- `focal`: a selector — `batch_id` or `journal_id` (one of them).
- `background`: a selector — explicit `batch_ids`/`journal_ids`, or `all_other` (every article with
  candidates that is not in the focal set). Background and focal must be disjoint; fail with a clear error
  if they overlap.
- `min_focal_docs` and smoothing taken from the policy file (section 6).

Per frame return:

| Field | Meaning |
|---|---|
| `frame` | the masked frame string (already free of slot content) |
| `df_focal`, `n_focal` | focal articles containing the frame / focal articles with any candidate |
| `df_bg`, `n_bg` | same for the background |
| `occurrences` | total candidates across focal articles |
| `score` | smoothed contrast, see below |
| `sample_sentence_ids` | up to 3 sentence UUIDs from different focal articles, for opening in the review page |

Score (descriptive, not a significance test):

```
p_focal = (df_focal + a) / (n_focal + 2a)
p_bg    = (df_bg    + a) / (n_bg    + 2a)
score   = ln(p_focal / p_bg)
```

Rank by `score` among frames with `df_focal >= min_focal_docs`, ties by `df_focal` then `occurrences`.
Also output a second ranking, `recurrence`, by `df_focal` alone (the owner's original idea), so both views
exist. If `n_focal` is below a warning threshold, or the background is empty, print a clear notice that the
ranking is unstable / that no contrast is possible, and show only the recurrence ranking.

## 6. Policy and CLI

- `policies/phrase_stats.yaml`, version `0.1.0`, schema in `policies/schemas.py`, loaded by the bundle:
  `smoothing_alpha: 0.5`, `min_focal_docs: 2`, `warn_below_focal_articles: 10`, `top_n: 50`, each with
  `TODO(owner, FR-06.2)`.
- CLI: `python -m aprkb.cli phrase-stats --focal-batch <uuid> [--background-batch <uuid> ...|--background
  all-other] [--top 50] [--format table|json]` (same style as `bootstrap-key`/`vocab-import`; add a
  Makefile target `phrase-stats` using `$(UV) run --directory apps/backend`). Output goes to stdout only.
  It prints frames, counts and sentence UUIDs, never sentence text; do not write it to logs.

## 7. Tests

- Unit (no database): `frame_key`; the scoring function (zero background, equal proportions → 0, focal-only
  frame ranks above a common one, smoothing keeps scores finite); selector overlap error; tie ordering.
- PostgreSQL integration (`TEST_DATABASE_URL` → `aprkb_test`): build two batches of synthetic articles,
  sentences and candidates (self-authored), including one article that repeats a frame ten times (counts
  once), two candidates with different slot contents but the same frame (one frame), a rejected candidate
  (excluded), and an empty background. Assert the ranking and the notices.
- No article text from the owner's corpus in tests or fixtures.

## 8. Smoke run on the owner's 10 articles (not a result)

The 10 stored articles come from different journals (two from the same journal, four with no journal
name in the metadata). They cannot show journal-specific phrases. Use them only to prove the pipeline:
run mining on them, then `phrase-stats` with an arbitrary focal subset and `all-other` background, and
report counts. Say plainly in the report that this smoke run makes **no claim about any journal**.
They are, however, a reasonable starting **background corpus** once a real focal batch exists.

## 9. Owner actions for a meaningful result

- One focal batch of **many articles of a single journal**, imported or uploaded with a licence decision
  (SLR import is still fail-closed on licences; manual upload with an explicit licence is the alternative).
- A background of other journals. The more distinct journals and articles, the more stable the ranking.
  Decide the minimum batch size once the first real run shows how unstable small batches are; do not
  claim a threshold in code or docs before then.

## 10. Report and done-when

- Report `plans/reports/YYMMDD-spacy-phase5-report.md`: method, formula, policy values, smoke-run counts,
  tests run, commands, what was not run (PostgreSQL or spaCy if unavailable), open items:
  endpoint/UI, number-variant merging (`show`/`shows`), lemma-level grouping, significance testing,
  per-section statistics, journal selection by `journal_id` once articles carry it.
- `make lint` and `make test` pass without spaCy; integration tests pass on PostgreSQL.
- Docs: add a short section to the mining README and `README.md` describing the command and its limits.
- Leave changes uncommitted for owner review.
