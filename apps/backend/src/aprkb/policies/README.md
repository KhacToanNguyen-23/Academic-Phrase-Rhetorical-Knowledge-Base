# Runtime policies

`evidence_matrix.yaml` and `lexicon/epistemic_markers.yaml` are the backend's
single runtime sources for the MVP evidence check:

- The matrix maps a claim type and declared evidence level to the maximum
  permitted claim strength. Missing cells use `default_max_strength: low`;
  unknown claim/evidence codes fail closed.
- The lexicon maps wording in a sentence to a claim-strength level. `markers` is shared by
  V02 and mining; `validator_only_markers` is read only by V02 and `mining_only_markers` only
  by the mining `EpistemicTagger`. `neutral_verbs` is mining-only.
- The seeded `RefEnum` order defines how strengths compare. Do not duplicate
  ordering or matrix comparisons in a gate, scorer, API route, or UI.
- `EvidencePolicy` is the shared comparison implementation. Both the
  recommendation `EvidenceGate` and validation rule V02 must call it.

This MVP configuration follows `SCAFFOLD_PRD.md` §4.6 and §8. The scaffold
labels the matrix and lexicon provisional and leaves claim types/cells for
domain review. The files are therefore runtime configuration, not final
scientific guidance.

`lexicon/lead_ins.yaml` is a separate closed list for syntax-path reporting
frames and literal hybrid leads. Version 0.2.0 adds `for example` and
`in contrast` for the frame-quality cases; matching strips surrounding
whitespace, drops one trailing comma and case-folds. Keep the list versioned
and do not add mining-derived values. See [ADR-0012](../../../../../doc/adr/0012-slot-abstractor-frames-and-ownership.md).

`slot_abstraction.yaml` contains provisional ownership tiers by determiner and head noun;
its lists carry `TODO(owner, FR-06.2)`. `lexicon/epistemic_markers.yaml` separates strength
markers from `neutral_verbs`. The syntax-first scorer now decides applicability from the parsed
claim complement or configured relational object; the old neutral list no longer vetoes a
syntactically valid claim. Its mining-only `neutral_verbs` list now blocks automatic AI
activation for matching OOV predicates; the list remains subject to owner review.

Syntax-valid OOV predicates are assessed in two separate model passes. Automatic activation
requires exact tier agreement and both confidence values at or above
`epistemic_scoring.yaml:oov_activation_confidence_threshold` (0.90 by default). The confidence
value is the model's estimate, not a statistically calibrated probability. Locked neutral verbs
are held for curator review and are never auto-activated.

`EVIDENCE_CONTRACT.md` is a broader, unapproved proposal. It is not loaded by
the application and must not be treated as a second runtime policy. If the
group approves it later, migrate the approved decisions into the versioned
runtime files and update their consumers together.


`constructions.yaml` v0.3.0 declares generic `author_action` adjuncts and the exact literal
subject allowlist: `we`, `this paper`, `this study`, and `this article`. Only the last three
subjects were added in Phase 9.1; the Phase 8 anchor and adjunct lists are unchanged. The
preposition, purpose-dependency and literal `in this ...` object lists remain provisional
(`TODO(owner, FR-06.2)`). Dynamic frame validation derives regular anchor forms from registered
lemmas and accepts only the resulting masked-frame grammar; other constructions keep their
declared templates. See [ADR-0013](../../../../../doc/adr/0013-author-action-adjuncts.md).

`construction_verb_groups.yaml` v0.1.0 is a separate provisional list for candidate discourse
modifiers and auxiliaries on `author_action`. The matcher requires the listed dependency role,
part of speech and surface position before preserving a token literally. Main-verb `have` is not
accepted as an auxiliary. These lists carry `TODO(owner, FR-06.2)` and do not add anchors or
predicate adjunct prepositions. Object-internal prepositional phrases remain inside the direct
object slot; only predicate-level prepositions are checked against the construction adjunct list.
See [ADR-0013](../../../../../doc/adr/0013-author-action-adjuncts.md).

`hybrid_constructions.yaml` v0.9.1 is a separate provisional policy for the eight Tier 2 families,
Meta-NP heads/connectors, boundary setting, content thresholds, and literal-word limits. A hybrid
frame is the pattern core of the main clause, not the whole sentence: trailing clauses and slot-free
lead adjuncts are cut, and a family's trigger word must stay inside the core. The engine retains
leads from `lexicon/lead_ins.yaml`, rejects slot edges that split a modifier from its head, rejects
capitalized sentence joins after a slot, and requires `min_fixed_content_tokens: 1` (provisional,
`TODO(owner, FR-06.2)`). It does not alter Tier 1 policy versions or cluster keys. The engine is
open-world but limited to configured family IDs, dependency shapes, three positional slots, and a
token-feature Purity Gate; see
[ADR-0014](../../../../../doc/adr/0014-hybrid-slot-engine.md).

Since v0.5.0, `hybrid_constructions.yaml` also lists `dangling_tail_words` and
`abbreviation_markers`. Both are closed grammar lists and stay provisional under `TODO(owner)`.
`is_safe_hybrid_frame` uses them, so a version bump leaves older pending hybrid candidates unsafe.
