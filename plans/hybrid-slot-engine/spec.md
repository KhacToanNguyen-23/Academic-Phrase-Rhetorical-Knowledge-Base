# Spec: Hybrid Slot Engine for Mining

**Date:** 2026-11-06
**Status:** Draft, pending scope approval (FR-16)

---

## Problem Statement

The current mining stage uses a conservative regex extractor and rejects academic constructions outside its narrow reporting-verb pattern. Add dependency-aware Tier 2 extraction while preserving Tier 1 behavior. A generated candidate enters the existing pending-candidate workflow; human approval creates the approved database record.

## User Stories

- **[P1]** As a mining pipeline maintainer, I want the existing Tier 1 output to remain authoritative so that approved regression behavior cannot be changed by new tiers.
  Accepted when: a Tier 1 result returns immediately; Tier 2 runs only when both Tier 1 matchers return `None`, the hybrid switch is enabled, and compatible analysis is present; the 42-case set remains exact and the other 16 baseline cases remain passing.

- **[P1]** As a user, I want dependency-aware construction candidates with accurate source offsets so that longer academic sentences can be abstracted without losing their slot boundaries.
  Accepted when: token features are passed from persisted `SentenceAnalysis`; each of seven Tier 2 families has at least three authored positive and three negative fixtures; every accepted span maps to the original sentence and passes Frame Invariant and Purity Gate.

- **[P1]** As a mining maintainer, I want Meta-Academic heads separated from their domain complements so that reusable academic frame vocabulary remains literal while domain phrases become slots.
  Accepted when: configured head/connector patterns preserve directly attached `relcl`/`acl` in the domain slot, repair boundaries against original surface text, and reject ambiguous attachments.

- **[P2]** As an operator, I want a single on/off switch for the hybrid engine so that I can disable it immediately if it misbehaves.
  Accepted when: with the switch off, output is byte-for-byte Tier 1-only for every input; with it on, Tier 2 runs only after a Tier 1 double no-match. Candidates reach only the existing pending queue, and no source sentences are logged.

## Functional Requirements

1. **FR-01 — Tier 1 oracle:** The current regex `SlotAbstractor` is the behavior oracle. `ReportingExtractor` and `ConstructionMatcher` do not currently exist as separate classes. Introduce only the minimum internal seam needed for ordered Tier 1 matching; preserve `_extract` behavior and the public `extractability_reason(text)` API.
2. **FR-02 — Strict fallback:** A Tier 1 match returns immediately. If both Tier 1 matchers return `None`, `HybridSlotEngine` may run only when the hybrid switch is enabled and valid `SentenceAnalysis` is present. Every current Tier 1 rejection may be considered by Tier 2, regardless of rejection reason; the engine must pass its own family and Frame/Purity checks. Tier 1 results are never mutated or overwritten.
3. **FR-03 — Analysis transport and storage:** Add nullable `Sentence.analysis JSONB` using the existing `SentenceAnalysis` serialization and `Article.analysis_info JSONB` using `NlpEngineInfo`. Pass sentence analysis through mining into optional `MiningItem.analysis` so `SlotAbstractor.process(batch)` keeps its signature. Missing, malformed, schema-mismatched, or unsupported model-version analysis produces deterministic Tier 1-only behavior with a non-sensitive diagnostic reason; never run a hidden second spaCy parse.
4. **FR-04 — Exact input alignment:** Require `analysis.char_start == item.char_start`, `analysis.char_end == item.char_start + len(item.text)`, sentence-relative token offsets within `item.text`, contiguous token indices, and valid sentence-local heads. On mismatch, skip hybrid extraction and retain Tier 1 behavior.
5. **FR-05 — Tier 2 families:** Implement seven configured families only: passive academic, extraposed `it`, copular/definitional, discourse gap, participial lead-in, comparative/correlation, and reporting-spine (long-subject `subject + reporting verb + that + clause`, reusing the reporting-verb policy and covering sentences Tier 1 rejects for `subject_too_long`). Each family declares dependency constraints, surface/lemma anchors, slot strategy, and at least three self-authored positive plus three negative fixtures.
6. **FR-06 — Bottom-up Meta-NP:** Before family matching, build a deterministic dependency child index and visit NP heads bottom-up. Unpack only configured Meta-Academic head + connector patterns. Keep the head/connector in the literal frame; put the domain complement in the slot, including directly attached `relcl`/`acl`. Ambiguous attachments yield no proposal.
7. **FR-07 — Subtree and boundary repair:** Collect argument subtrees from `dep`/`head`/`pos`; prune unrelated clauses and pre-comma discourse frontiers; repair slot edges against original character spans. Regex protects existing token spans and cannot retroactively re-tokenize spaCy output. Keep returned offsets source-relative and exact.
8. **FR-08 — Slot contract:** Reuse existing `SlotType` values only: noun phrases map to `NOUN_PHRASE`, finite clauses to `CLAUSE`, and explicit own/prior determiner splits to the corresponding determiner type. Use at most three slots in this release, named `X`, `Y`, `Z` in source order. Reject proposals needing another type or a fourth slot. Do not widen `CandidateWriter` to accept arbitrary masked frames; accept hybrid results only after policy and FrameValidator approval.
9. **FR-09 — Metadata contract:** Populate `tense`, `ownership`, and `slot_binding_fingerprint` on every accepted Tier 2 `MiningItem` before clustering. Present-perfect requires finite present `have` plus a participial predicate; otherwise use unambiguous finite present/past, and map modal/future, conflicting, or missing evidence to `UNKNOWN`. Derive ownership using existing determiner cues and previous-sentence blockers; otherwise use `UNCLEAR`. Compute the fingerprint as Tier 1 does: sort slot names, collapse whitespace, case-fold slot text, join entries with `\x1f`, then SHA-256. Carry internal `construction_id` and `canonical_skeleton` on `MiningItem`; the existing `CandidateDraft` persists the resulting cluster key.
10. **FR-10 — Frame Invariant and Purity Gate:** Frame Invariant passes only if slot spans are in-bounds, non-overlapping, ordered, and replacing them with placeholders reconstructs the emitted frame exactly. Purity uses only rules checkable from token features and the source text; it needs no hand-written vocabulary list. Reject any literal token that is `PROPN`, part of a citation, a number, year or percentage, or an all-caps acronym. Function words (determiners, adpositions, auxiliaries, particles, conjunctions, pronouns, by `pos`) always pass. Count `NOUN`, `VERB`, `ADJ`, and `ADV` literal tokens as content; require at least three, including a `VERB`, `ADJ`, or Meta-Academic noun. A family may configure a lower minimum in `constructions.yaml` (reporting-spine uses one, the reporting verb). Reject adjacent slots. Literal words that are merely unfamiliar do not fail the gate; they are flagged on the pending candidate for the reviewer. Building a frequency-based academic word list is future work, not part of this release.
11. **FR-11 — Canonical skeleton and clustering:** Preserve `surface_frame` for display. `canonical_skeleton` is the masked frame with its finite root replaced by the lemma and configured auxiliary/adverb variation omitted. It never changes tense, ownership, slots, or offsets. Tier 2 cluster material includes policy version, construction ID, canonical skeleton, tense, epistemic strength, ownership, slot-type signature, and binding fingerprint. Tier 1 cluster keys remain unchanged.
12. **FR-12 — Candidate approval:** Use the existing workflow: `CandidateWriter` persists a validated candidate with `status=pending`; the existing approval operation creates the approved phrase record. Approval is the only human action required; it is not a labeling/correction study. Do not introduce another reviewer or pre-approval annotation step.
13. **FR-13 — Hybrid switch:** Add one boolean setting, `hybrid_enabled`, default `false`. When false, only Tier 1 runs. When true, Tier 2 applies only after strict Tier 1 double no-match with compatible analysis. There is no shadow mode; the existing pending-candidate queue is the review point before anything is approved into the database.
14. **FR-14 — Tier 3 deferral:** Do not implement Tier 3 in this release. Specify its acceptance gate, candidate-volume controls, and independent feature flag in a later spec before enabling it.
15. **FR-15 — Regression contract:** Run the existing 42 reporting-verb/tense and 16 other cases (including the seven rejection cases) without analysis; Tier 1 outputs and rejections must stay exact. These tests protect Tier 1 only and place no constraint on Tier 2. Analyzed fixtures for the seven rejection inputs record the expected Tier 2 outcome listed below.
16. **FR-16 — Scope and migration prerequisite:** This feature expands current scaffold scope, which defers production NLP extraction. Before implementation, approve and document a scope exception in `SCAFFOLD_PRD.md` and `CLAUDE.md`. Reconcile the currently untracked `apps/backend/src/aprkb/nlp/` spike with the feature branch, inspect the live Alembic graph, and add a reversible migration from its current head for sentence-analysis storage.

## Tier 2 Acceptance Examples

Each positive example below is a required authored fixture. Add at least two more positive and two more negative fixtures per family. Slot IDs follow source order; periods remain literal unless included in a slot span. Negative examples are tested against the named family only; another family may match independently.
| Family | Positive input → expected frame | Slot values | Negative example |
|---|---|---|---|
| Passive academic | `Samples were consistently and carefully preprocessed using the proposed filter.` → `[X] were consistently and carefully preprocessed using [Y].` | X=`Samples`; Y=`the proposed filter` | `Researchers used the proposed filter.` |
| Extraposed `it` | `It is practically necessary to inspect the output of the proposed filter.` → `It is practically necessary to inspect [X].` | X=`the output of the proposed filter` | `It is necessary.` |
| Copular/definitional | `The most important methodological limitation of this approach is a substantial increase in runtime.` → `The most important methodological limitation of [X] is [Y].` | X=`this approach`; Y=`a substantial increase in runtime` | `This approach increases runtime.` |
| Discourse gap | `However, remarkably little attention has been paid to this limitation.` → `However, remarkably little attention has been paid to [X].` | X=`this limitation` | `Attention has been paid to this limitation.` |
| Participial lead-in | `Motivated by earlier failures, researchers therefore propose a more reliable filter.` → `Motivated by [X], [Y] therefore propose [Z].` | X=`earlier failures`; Y=`researchers`; Z=`a more reliable filter` | `Researchers therefore propose a more reliable filter.` |
| Comparative/correlation | `The new model consistently and significantly outperforms the baseline in retrieval accuracy.` → `[X] consistently and significantly outperforms [Y] in [Z].` | X=`The new model`; Y=`the baseline`; Z=`retrieval accuracy` | `The new model is fast.` |
| Reporting-spine | `The carefully designed mock retrieval experiment with several independent checks reveals that the mock system improves quality.` → `[X] reveals that [Y].` | X=`The carefully designed mock retrieval experiment with several independent checks`; Y=`the mock system improves quality` | `The mock system improves retrieval quality today.` |

The positive examples must pass the Purity Gate and the family's content-token minimum. The negative examples must produce no Tier 2 proposal. They are self-authored test sentences, not source-corpus examples.

The seven existing Tier 1 rejection inputs are recorded as analyzed fixtures with the Tier 2 outcome below. “Double no-match” permits the engine to inspect an item but does not bypass family matching or validation.

| Existing rejection input | Tier 2 expectation in this release |
|---|---|
| `The mock system improves retrieval quality today.` | No matching configured family. |
| `Our results reveal the mock system improves retrieval quality.` | No matching configured family. |
| `Reveal that the mock system improves retrieval quality.` | No supported subject/frame family. |
| `The carefully designed mock retrieval experiment with several independent checks reveals that the mock system improves quality.` | Reporting-spine family matches: `[X] reveals that [Y].` |
| `Our results reveal that cold.` | No matching configured family; short complement remains rejected. |
| `That approach shows a gain.` | No matching configured family. |
| `These reveal that the mock system improves retrieval quality.` | No supported subject/frame family. |

## Non-Functional Requirements

- **Determinism:** Identical input text, token features, policy version, and stored NLP model metadata produce identical candidate frames, spans, and tier selection.
- **Offsets:** Every returned slot range is sentence-relative in its input and converts exactly to the existing occurrence offset contract.
- **Performance:** Ingest performs at most one spaCy analysis per sentence; mining consumes stored features and never loads/runs the model. The dependency pass is linear in token count; family matching is bounded by seven configured families. Record a p95 baseline and budget before enabling the hybrid switch.
- **Version safety:** Unknown analysis schema/model versions fail closed to Tier 1-only behavior with a non-sensitive reason. Policy versions are included in Tier 2 cluster keys.
- **Quality target:** At least 90% slot/frame correctness and 80% rhetorical usefulness remain desired targets. They are not verified by the final approval action alone and cannot be release gates until an approved gold set or separately authorized annotation study exists.
- **Privacy:** Do not log or store raw source text in diagnostics or logs. Continue using typed public slot values and private source offsets.
- **Compatibility:** Tier 1 output, slot definitions, tense, ownership, fingerprint, and cluster inputs remain unchanged on a positive Tier 1 match.

## Success Criteria

- [ ] 42 identified Tier 1 reporting-verb cases match exact current frame and tense outputs.
- [ ] All 16 additional current regression cases retain their expected accepted/rejected behavior.
- [ ] Control-flow verification proves Tier 2 does not run after a Tier 1 match and runs only on Tier 1 double no-match with compatible analysis.
- [ ] Every accepted Tier 2 candidate passes structural validation, metadata derivation, and exact offset reconstruction.
- [ ] Existing 42 + 16 Tier 1 tests pass without attached analysis; each Tier 2 family has at least 3 positive and 3 negative analyzed fixtures.
- [ ] With `hybrid_enabled=false`, output is byte-for-byte Tier 1-only for every input.
- [ ] Alembic migration upgrades and downgrades cleanly from the actual current head; analysis-version mismatch fails closed.
- [ ] The 90%/80% semantic targets remain future goals until approved gold labels exist; do not add a human annotation step to runtime.

## Out of Scope

- Automatic move classification (a future feature after human-approved labels and quality evidence exist) or automatic approval.
- Changing Tier 1 extraction semantics to improve coverage; only the smallest delegation seam required by `SlotAbstractor` may be introduced.
- Re-running spaCy in the hybrid stage when persisted analysis is missing.
- Tier 3 academic skeleton projection in this release.
- Claiming measured 90%/80% semantic quality from database approval rates alone.
- Adding a human annotation or correction step before the final approve-and-save action.

## Assumptions

- Current `SlotAbstractor` is the compatibility oracle even though separate Tier 1 matcher classes do not exist yet.
- The existing `SentenceAnalysis` token contract is the intended analysis format, but it must first be wired into ingest and mining; current source says the feature spike is not wired.
- Missing token analysis leaves the pipeline at Tier 1 output/rejection and reports a diagnostic reason without adding a hidden NLP call.
- Current tests construct `MiningItem` without analysis; they protect Tier 1 behavior. Separate analyzed fixtures define new Tier 2 behavior.
- `CandidateWriter` keeps the existing pending-candidate persistence flow; final approval creates the approved phrase record.
- Tier 3 is an architectural future tier only; it is not implemented or enabled in this release.

## Implementation Prerequisites

- `CLAUDE.md` and `SCAFFOLD_PRD.md` currently defer production NLP extraction. This feature requires an explicit scope exception before implementation.
- The current `nlp/` spike is untracked on `feat/ui-redesign`; reconcile its ownership and branch before relying on it.
- Sentence analysis storage requires a reversible migration. Inspect current Alembic heads first; do not assume a single head from filenames.
- `CandidateWriter` currently validates only the curated reporting-frame grammar. Extend it narrowly to accept a Tier 2 result only with validated construction-policy identity and at most `X/Y/Z` slots.

## Proposed Architecture and Rollout

`SlotAbstractor` remains a pipeline stage and coordinator. Its Tier 1 path is authoritative and returns immediately on a match. When `hybrid_enabled` is true, only a Tier 1 double no-match with compatible analysis enters `HybridSlotEngine`. The engine consumes `MiningItem.analysis`, performs bottom-up Meta-NP collapse/unpacking, then tries Tier 2 templates. Tier 3 is deferred.

Recommended module boundary: start with a small `modules/mining/hybrid_slot_engine.py` and typed proposal/result structures; split span collection, policy matching, and validation into separate files only when their size warrants it. Add `policies/constructions.yaml`; extend `slot_abstraction.yaml` for shared Meta-NP and boundary settings. Persist `SentenceAnalysis` on `Sentence`, pass it through mining, and retain compatible `NlpEngineInfo` before enabling the hybrid engine.

Rollout order:

1. **Foundation:** record the production-NLP scope exception and reconcile the NLP spike; run the 42 + 16 Tier 1 tests as baseline; inspect Alembic heads, persist sentence analysis and model metadata, pass optional analysis through `MiningItem`, verify offset/version fail-closed behavior, and add the `hybrid_enabled` switch (default off).
2. **Build all seven Tier 2 families together:** typed policy schemas, the narrowly authorized `CandidateWriter` path, Meta-NP collapse, subtree collection, boundary repair, Frame Invariant and Purity Gate, with 3 positive and 3 negative authored fixtures per family.
3. **Run and fix:** enable `hybrid_enabled` on real data, review the pending queue, measure p95, and fix the most frequent errors first. Keep Tier 3 out of scope.

See the brainstorm report at `plans/reports/261106-hybrid-slot-engine-brainstorm.md` for the draft YAML and worked `MiningItem` example.
