# Verb review queue: deferred spec

Status: **DEFERRED**. Owner decision on 2026-11-05: build this later; abstractor coverage work comes first.
Nothing here is implemented. Requirement IDs: FR-06.2 (epistemic lexicon), TODO(owner) for anything marked below.

## Goal

Let a human classify verbs that mining has seen but the lexicon does not know, on a web page.
Approved verbs become mining data without a code change. The lexicon grows with the corpus instead of
being loaded in one large batch.

## Owner decisions already taken

1. Classification is reviewed by a human on the web. AI may only propose (phase 3), never write.
2. Approved entries live in the database (not YAML), because approval happens on the web.
3. `show` is neutral for mining; V02 keeps it as `high`. Approved queue entries must never change V02
   unless the owner explicitly decides so per verb.

## Proposed design (recommended, awaiting owner confirmation of items marked OPEN)

### Two independent decisions per verb

| Decision | Values | Effect |
|---|---|---|
| Reporting-class membership | member / not a reporting verb / skip | Whether `SlotAbstractor` may extract a sentence with this verb |
| Epistemic class | neutral / low / moderate / high / absolute | `EpistemicTagger` strength and status |

A verb can be a reporting member and still have no epistemic class decided. The queue must allow
deciding one without the other.

### Data model (sketch)

- `verb_lexicon_entry`, append-only. Columns: id, lemma, forms (inflections), reporting_member,
  epistemic_class, scope (`mining` only for now), reviewer_id, decided_at, note, supersedes_id.
- No update or delete. A change is a new row that supersedes the old one, in the same transaction as
  an audit record (project rule: transactional audit writes, append-only versions).
- `verb_queue_item`: lemma, forms seen, document frequency, sentence count, first_seen_at, status
  (pending / decided / dismissed). Counts only. No sentence text and no article text is stored
  (project rule: no article content in logs or audit snapshots).

### How it reaches mining

- The YAML lexicon remains the base (`epistemic_markers.yaml`, reporting verbs in policy YAML).
- At the start of each `mine_article` run, load the YAML base plus active DB entries into one effective
  lexicon and compute a combined version identifier.
- Record that identifier in `policy_versions` and in `cluster_key`, so every run is reproducible even
  though the lexicon grows. A run never sees entries added after it started.
- V02 reads only the YAML `validator_only_markers` and shared `markers`. DB entries are mining-scope.

### Queue generation

- During mining, an unknown verb (status `unknown`, or `no_reporting_verb`/`no_that` for a candidate
  reporting lemma) increments a counter. Only lemma and counts are kept.
- Page orders by document frequency, not sentence count, so one article cannot dominate.

### Web page

- Desktop-first (owner preference). List of pending verbs with counts, two selectors per verb, a
  note field, approve / dismiss. Reviewer identity comes from the existing auth. Router → service →
  repository, same layering as other modules.
- Built on the UI branch after the backend API exists. Frontend work is only started when the owner asks.

## Phases

1. Backend: tables, migration, queue counters, loader merge, effective-lexicon version, tests.
   Runs in the spike worktree.
2. Web review page.
3. Optional AI proposal step, only when the pending list is long enough to justify it. Proposals are
   suggestions stored separately and never applied automatically.

## Constraints to carry into the implementation prompt

- Do not change V02 behavior. Keep the pinned V02 marker test passing.
- No article text in the queue, logs or audit snapshots.
- Integration tests only on `aprkb_test` (port 55433), never on the real database (port 55432).
- Update `CLAUDE.md` wording about vocabularies in YAML. That file is owner-owned: propose the change,
  do not edit it unasked. Add an ADR for the YAML-base-plus-DB-entries split.
- Every incomplete stub keeps `TODO(owner)` and a requirement identifier.
- Regression test for each new rule.

## OPEN (owner to confirm before phase 1)

- OPEN-1: confirm the YAML-base-plus-DB-additions model and the combined version in `cluster_key`.
- OPEN-2: queue ranking by document frequency, and a minimum frequency below which a verb is not queued.
- OPEN-3: whether dismissed verbs can return to the queue later.
- OPEN-4: whether a reviewer may later promote an entry to V02 scope, and how.

## Evidence behind the need (corpus counts, 51 articles, before phase 7)

- 90% of kept sentences end as `no_reporting_verb` (10,958 of 12,178).
- Frequent non-listed verbs among `no_that` rejections: propose 174, report 60, highlight 25,
  conclude 14, verify 8, reveal 9, imply 7. These figures come from the Codex phase 7 report and an
  earlier counts-only script, not from a fresh independent run.
