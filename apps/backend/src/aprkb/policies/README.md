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
frames. Its seven phrases were owner-approved on 2026-11-05; matching strips
surrounding whitespace, drops one trailing comma and case-folds. Keep the list
versioned and do not add mining-derived values. See [ADR-0012](../../../../../doc/adr/0012-slot-abstractor-frames-and-ownership.md).

`slot_abstraction.yaml` contains provisional ownership tiers by determiner and head noun;
its lists carry `TODO(owner, FR-06.2)`. `lexicon/epistemic_markers.yaml` separates strength
markers from `neutral_verbs`: neutral means `epistemic_strength=None`, not a fifth strength
level. The neutral verb list is provisional and carries `TODO(owner, FR-06.2)`.

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
