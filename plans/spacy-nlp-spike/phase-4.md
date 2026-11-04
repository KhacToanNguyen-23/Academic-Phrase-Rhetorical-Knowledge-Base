# spaCy NLP — phase 4: parse-quirk fix, imperative branch, construction registry, real-article trial

Status: proposed 2026-11-04 from owner decisions; implement in the order A → B → C.
Requirement: `FR-06.2`, `FR-07`.
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike` (phase 3 is commit `28ac884`).
Read first: `phase-3.md`, `doc/adr/0010-spacy-ingest-token-features.md`, the phase-3 report.

## 0. Owner decisions (2026-11-04)

1. Parser work for JATS/PDF is paused until real format counts are known. Articles are converted
   outside the app to plain text or Markdown and uploaded; no parser is built in this phase.
2. "Phrase" means a **discourse functional block**: an internal project concept (a frame with fixed
   anchor words and named slots, tied to a communicative function). Do not copy or closely paraphrase
   Academic Phrasebank entries anywhere (CLAUDE.md). All patterns and examples are self-authored.
3. The scope is extended from reporting-verb frames to three construction groups: **author action**,
   **relation / role**, **performance / evaluation**. PRD, ADR and CLAUDE.md wording must say so.
4. Mining stays free of spaCy. Matching runs on stored `TokenFeature` data with a small pure-Python
   matcher. Patterns live in a versioned YAML registry with named slots and `TODO(owner, FR-06.2)`.
5. Coordinated reporting verbs stay rejected (counted); measure frequency on real articles first.
6. The imperative branch of the finite-verb filter is approved, behind a policy flag, with counters.

Invariants as before: no sentence text, token text or lemma in logs/audit/public output; mining rights
checked before reading blobs; real articles are never committed; regex mode stays unchanged.

## Part A — fixes (small, commit separately)

### A1. Aux-attached `mark` / `nsubj`

Observed parse of `These findings may indicate that the baseline was undertrained.`:
`undertrained` is `ccomp` of ROOT, but `that` (mark) and `baseline` (nsubj) have the auxiliary `was`
(`auxpass`) as head instead of `undertrained`. The strict "direct child of the clause head" check then
returns `no_that`, although the regex path extracts the sentence.

- In `aprkb/nlp/syntax.py` add one normalisation step used by every syntax consumer: a dependent whose
  head is an `aux`/`auxpass`/`cop` token that itself is a child of verb V is treated as a dependent of V.
  Apply it only for `mark` and subject deps, only one level, and only when V is the clause head.
- Keep the phase-3 rule that a `that` inside a relative clause or subject modifier never counts.
- Tests (full `build_stages`, snapshot-based, no spaCy): the sentence above must extract with clause
  `that the baseline was undertrained`; `These findings suggest a model that indicates that noise
  matters.` must still be dropped; the fixture table in the report must no longer list case 7 as
  "only regex".

### A2. Imperative branch in `SentenceFilter`

Current behaviour: the check passes if **any** token is a finite verb or modal (`VerbForm=Fin`), and
the ROOT is VERB/AUX. A bare imperative has an infinitive ROOT, so it passes only when the rest of the
sentence happens to contain a finite verb (`Note that our approach achieves …` passes via `achieves`;
`Consider a graph with n nodes and m edges` passes only because `edges` is mis-tagged as a verb;
`Consider the case of two nodes connected by a single edge.` and `Let x be a real number …` are rejected).

- Extend `SyntaxFilterSettings` (`policies/schemas.py`) and `mining_filter.yaml` (version bump):

  ```yaml
  syntax_filter:
    require_finite_verb: true
    # TODO(owner, FR-07): measure on real articles before keeping.
    allow_imperatives: true
  ```
  Keep the existing schema style (`extra="forbid"`); do not introduce a new top-level `filters:` tree.
- Imperative branch (only when `allow_imperatives`): ROOT has `tag == "VB"` (POS is `VERB`, VB is the
  fine-grained tag), is the first content token or follows at most one short adverbial/discourse token
  plus a comma, has **no** `nsubj`/`nsubjpass` child, and has at least one complement child
  (`dobj`, `ccomp`, `xcomp`, `attr`, `prep`). The complement requirement keeps a mis-tagged one-word
  heading from passing. No hard-coded verb list.
- Counters: add `imperative_accepted` (sentences that would have been `no_finite_verb` but pass) to the
  filter statistics in `modules/mining/stats.py` as an aggregate count. Counts only; never log text.
- Tests: `Let x be a real number in the interval considered here.` and `Consider the case of two nodes
  connected by a single edge.` pass; `A short fragment.`, `1. Introduction`, a one-word heading
  mis-tagged as VB (build tokens by hand) and `Results of the experiment` are still rejected; flag off ⇒
  today's behaviour.

### A3. Modal tense and epistemic strength: document, do not change yet

Findings to record in the report and ADR (no behaviour change in this phase):

- `epistemic_strength` is `None` for `could indicate`, `might have suggested`, `may suggest`
  **by design**: `EpistemicTagger` returns a strength only when exactly one strength class matches
  (`could` is `low`, `indicate` is `moderate`, so the sentence is ambiguous and stays `None`).
  The modal stays literal in the frame, so the cluster key still differs from the unmodalised verb.
- `might have suggested` is labelled `present`: the syntax locator uses the regex baseline for modals
  (documented `TODO(owner, FR-06.2)`). Candidate rule for the owner: modal + `have` + participle ⇒
  `present_perfect`. Put the two options and their effect on the tense/cluster rule in the report.

## Part B — construction registry and token matcher

### B1. Registry (policy YAML)

New file `policies/constructions.yaml`, schema `ConstructionsPolicy` in `policies/schemas.py`, loaded by
the policy bundle, version `0.1.0`, `TODO(owner, FR-06.2)` on every list. A linear token list cannot
express "the object phrase", because noun phrases are not stored. Patterns are therefore
**dependency-anchored**, not token sequences:

```yaml
version: 0.1.0
constructions:
  - id: author_action
    function: author_action          # internal label for the later move classifier (FR-06.3)
    anchor: { lemma: [propose, present, introduce, develop], pos: VERB, dep: ROOT }
    children:
      - { dep: [nsubj], lemma: [we], mode: literal }
      - { dep: [dobj], mode: slot }                      # subtree becomes a slot
    allowed_literal: { prefix_prep_lemmas: [paper, study, work, article, research] }
  - id: relation_role
    function: relation
    anchor: { lemma: [play], pos: VERB, dep: ROOT }
    children:
      - { dep: [nsubj, nsubjpass], mode: slot }
      - { dep: [dobj], lemma: [role], mode: literal, literal_modifiers: [key, crucial, vital, major, central] }
      - { dep: [prep], lemma: [in], mode: literal, then: { dep: [pobj], mode: slot } }
  - id: performance
    function: evaluation
    anchor: { lemma: [improve, enhance, outperform, boost, reduce], pos: VERB, dep: ROOT }
    children:
      - { dep: [nsubj], mode: slot }
      - { dep: [advmod], mode: literal_optional }
      - { dep: [dobj], head_lemma: [accuracy, performance, efficiency], mode: head_literal_modifiers_slot }
```

Spec rules:

- `mode: literal` keeps the token(s) in the frame; `slot` replaces the child's whole subtree with the next
  positional slot (`[X]`, `[Y]`, `[Z]`, as today); `head_literal_modifiers_slot` keeps the head word and
  masks its `compound`/`amod` modifiers (gives `significantly improves [Y] accuracy`).
- **Closed world:** every token that is not the anchor, a matched literal, a slot subtree or punctuation
  must belong to an `allowed_literal` list or the sentence is rejected with `unmatched_content`. This keeps
  free article wording out of frames.
- The examples above are starting points written for this project; extend the lists only with
  self-authored additions. Document that the three groups are a first set, not exhaustive.
- Matching uses `lemma`, `pos`, `dep`, `head` only. Use the shared ROOT selection and the A1 normalisation
  from `aprkb/nlp/syntax.py`. Do not import spaCy anywhere under `modules/mining/`.

### B2. Matcher stage

- `modules/mining/stages/construction_matcher.py` with a pure function
  `match_construction(tokens, text, registry) -> MatchResult | reason`, unit-testable without spaCy.
- Integration: sentences the reporting-verb path rejects are offered to the registry, in registry order,
  first match wins. **Output of the reporting-verb path must stay byte-identical.** Keep
  `SlotAbstractor` untouched or add a thin composing stage; do not duplicate its extraction code.
- Result fields: frame string, slots with `SlotType` and signals (reuse `_definition`), occurrence
  offsets, tense from the verb group (reuse the phase-3 helper), ownership (`OWN` for `we`, otherwise
  `UNCLEAR`), `construction_id` and the registry version.
- Cluster key: add `construction=<id>:<registry version>` to the key material only for matcher output.
  Existing keys must not change.
- Statistics: aggregate counters per construction and per rejection reason
  (`no_anchor`, `missing_child`, `unmatched_content`, `subject_not_allowed`, …). Counts only.

### B3. Safe-frame validation

`is_safe_masked_frame` (`modules/mining/schemas.py`) accepts only the `[x] … that [z]` reporting grammar,
so matcher frames would fail wherever it is used (extraction service). Add
`is_safe_construction_frame(frame, registry)`: the frame must equal a compiled skeleton of a registry
entry (escaped literals plus `[X]`-style slots, optional literals from the allow-lists) and contain no
other bracketed text. Use it next to the existing check; do not weaken the existing one. Test with hand
built frames, including a frame with injected extra bracketed text.

### B4. Docs and scope

- ADR-0011 `construction-registry`: decisions 2–4 above, the closed-world rule, the matcher/stage design,
  and what stays deferred (move classifier, coordination, sub-sentence collocations outside the three
  groups, NER).
- Update `SCAFFOLD_PRD.md` (Vietnamese style), `README.md`, ADR-0007, mining README and the sentence in
  `CLAUDE.md` that currently forbids production NLP extraction, so they describe the owner-approved
  extension and its limits. Keep `TODO(owner, FR-06.2)` markers.

### B5. Tests

- Unit (no spaCy, hand-built or snapshot tokens): for each construction a positive case, a case with an
  unlisted verb (rejected), a case with extra free content (`unmatched_content`), a passive/negated
  variant (decide and document), and a sentence both paths could match (reporting path wins).
- Snapshots: extend `token_snapshots.json` and its generator with the new self-authored sentences.
- Full-pipeline test through `build_stages`; regex mode and `tokens=None` unchanged.
- PostgreSQL integration (regex and spaCy modes) as in earlier phases; list anything not run.

## Part C — real-article trial (counts only)

Goal: measure, on the owner's real articles, what the pipeline actually does, so that coordination,
imperatives and the three construction groups can be judged by frequency.

- Inputs: plain text / Markdown files the owner converted from PDF/XML (parser work is paused). Keep them
  in an untracked directory, for example `data/trial/`, which must be ignored by git; never commit or
  copy article text into reports, tests or logs. State the licence used at upload in the report.
- Add `apps/backend/scripts/mining_trial_report.py`: for a directory of files it runs ingest-equivalent
  splitting with the spaCy engine, the full stage list, and prints **aggregates only**:
  sentences, filter rejections by reason (including `imperative_accepted`), extraction reasons,
  matches per construction, rejection reasons per construction, `coordinated_reporting_verbs` count,
  syntax-invalid-token fallbacks, and engine/model/registry versions.
- Optional second output (stored in the untracked directory): the most frequent masked frames per
  construction, truncated to a maximum literal length, for the owner to inspect. Do not paste it into
  committed files.
- Report `plans/reports/YYMMDD-spacy-phase4-report.md`: methodology, aggregate numbers, the decision
  table for coordination (frequency vs the owner's threshold), imperative branch (accepted vs
  false-positive estimate from a manual sample reviewed by the owner), construction coverage, open items.
  State that the numbers describe this article set only.

## Done when

- A1, A2 (and A3 documentation) merged first as their own commit; `make lint` and `make test` pass
  without spaCy; PostgreSQL integration passes in both modes.
- Part B committed with ADR-0011 and the PRD/CLAUDE.md wording updated; reporting-verb output unchanged.
- Part C script runs on the owner's files; the report contains counts only.
- Leave changes uncommitted for owner review as in earlier phases, unless the owner says otherwise.
