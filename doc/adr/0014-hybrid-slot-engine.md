# ADR-0014: Open-world hybrid slot extraction

- **Status:** Proposed scope exception, implemented behind a disabled switch
- **Date:** 2026-11-06
- **Requirement:** FR-06.2

## Context

The reporting extractor and versioned construction registry intentionally fail closed. The hybrid
tier adds dependency-shaped proposals for eight construction families (seven academic constructions plus a
syntax-only modified active clause). It is configured
separately in `hybrid_constructions.yaml`; Tier 1 policy versions and cluster keys must not change.

## Decision

Keep Tier 1 authoritative. Try Tier 2 only after both existing matchers miss, when
`MINING_HYBRID_ENABLED=true` and usable stored token features are present. Mining never imports or
runs spaCy. Hybrid candidates use the existing pending-candidate queue and all current review
gates.

The hybrid tier is a narrow open-world exception: it can preserve literals outside the curated
Tier 1 frame grammar, limited to eight named dependency families and at most three positional
slots. The Purity Gate rejects proper nouns, digits, citations, and all-caps acronyms. It requires
a minimum number of literal content tokens without an academic word list. Unknown family IDs,
malformed frames, adjacent slots, punctuation glued to a slot, and unsafe literals fail closed.
The eighth family, `hybrid_active_modified`, accepts an active clause only when its verb carries an
adverb or a prepositional phrase. It uses no verb list (owner decision, 2026-11-07): a measured
allowlist of 17 academic verbs yielded 40 candidates and no recurring frame.

Frame quality gates (policy v0.8.1, all vocabulary-free): slots are named X, Y, Z in reading
order; literal text may not keep a topic noun (`max_literal_nouns: 0`, Meta-NP heads exempt);
configured fixed leads stay literal; a slot edge may not split a modifier from its head; a
capitalized function word glued after a slot is rejected; `min_fixed_content_tokens: 1`. A value of 2
was tried and reverted: it kept 21 instead of 102 recurring frames and removed 7 of 11 GOOD frames
in the owner sample. Every frame must pass `is_safe_hybrid_frame` before the engine returns it.

Policy v0.9.0 adds closed verb frames inside `hybrid_active_modified` (`infinitive_verbs`,
`preposition_verbs`, both `TODO(owner)`), clause handling for `It is ADJ ...`, and more Meta-NP heads;
it adds no family. Slots with a lone parenthesis are rejected.

Policy v0.9.1 adds `idiom_frames` (a fixed verb + noun + preposition whose noun stays in the frame),
`worth + V-ing + that`, `serve as`, goal-noun clauses, closing-parenthesis balance for slots, and a
reject rule for subordinate fragments. It adds no family.

Candidates are upserted by `cluster_key` (`uq_candidates_cluster_key`): later sentences with the same
cluster append their sources to the pending candidate instead of adding a review row.

Tier 2 candidate identity includes the family ID and hybrid policy version. The canonical skeleton
is cluster material only; display frame, slot definitions, tense, ownership, and offsets stay with
the mining item.

## Consequences

- The switch defaults off. Enabling it requires spaCy features stored at ingest; regex ingests stay
  Tier 1-only.
- The family and Meta-NP lists remain provisional and carry `TODO(owner, FR-06.2)` pending approval.
- `max_literal_words: 12` and `min_content_tokens: 1` are owner-confirmed (2026-11-07) standard
  parameters of policy v0.3.0, not provisional values.
- Owner acceptance of v0.8.1 (2026-11-07): a fresh 30-frame read scored 26 GOOD, 2 WEAK, 2 BAD.
  No separate hedging or limitation family was added; a 50-article survey found no branch that met
  the volume gate (at least 25 new phrases or 5 frames in two or more articles).
- Rights-checked corpus coverage and candidate volume must be measured before enabling the switch
  outside a controlled review.
- Tier 3, auto-approval, move classification, and a frequency-based academic word list remain out
  of scope.

## Proposed wording for `CLAUDE.md`

> The eight-family hybrid mining tier in ADR-0014 is a narrow, feature-flagged exception to
> general-purpose NLP extraction. It runs only after Tier 1 misses, consumes stored spaCy token
> features, and sends validated candidates to the existing pending review queue. Keep the switch
> disabled by default; do not add Tier 3, auto-approval, or general-purpose extraction.
