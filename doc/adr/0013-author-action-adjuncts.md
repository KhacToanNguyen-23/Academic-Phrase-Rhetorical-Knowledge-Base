# ADR-0013: Generic adjuncts in author-action frames

- Status: implementation spans phases 8, 9.1 and 8.1; Phase 8.1 acceptance is pending mandatory regression.
- Date: 2026-11-05
- Requirements: FR-05, FR-06.2.

## Context

The phase-4 `author_action` rule matched only a subject, anchor and object. Most measured
`we` + action-root cases include a prepositional or purpose adjunct. Adding words to the
literal lexicon would not recover the missing slot structure and could silently admit new
frame text.

## Decisions

1. Construction registry version is 0.3.0. The provisional `author_action` anchor list is
   `propose`, `present`, `introduce`, `develop`, `use`, `compare`, `conduct`, `evaluate`,
   `provide`, `consider`, and `implement` (`TODO(owner, FR-06.2)`). Forms are selected by the
   syntax lemma and frame validation derives regular present/past forms from those lemmas;
   no phrasing-specific verb templates are maintained.
2. `author_action.adjuncts` defines the closed preposition list (`in`, `for`, `with`, `as`,
   `on`, `by`), purpose dependencies (`advcl`, `xcomp`), a maximum of two adjunct slots, and
   the literal objects allowed after `in` (`paper`, `study`, `work`, `article`, `research`).
   These lists are provisional (`TODO(owner, FR-06.2)`). The preposition stays literal and
   its object subtree becomes the next slot. The listed `in this ...` phrase stays wholly
   literal. A purpose clause is accepted only with a child `aux` or `mark` token whose lemma
   is `to`; `to` stays literal and the remaining verb phrase becomes a clause slot.
3. A PP is a construction adjunct only when its `prep` node is directly attached to the anchor.
   Prepositions anywhere inside the direct-object subtree remain part of slot `X`, regardless
   of their lemma; nested PPs inside an adjunct object's subtree remain in that adjunct slot.
   This corrects the Phase 8 implementation bug. The matcher does not infer unsupported
   dependency relations. Slots are `X` for the direct object, then `Y` and `Z` in surface order.
4. The masked frame is the original sentence with exactly the selected slot spans replaced,
   preserving all other characters, punctuation and literal function words (ADR-0008). The
   author-action validator checks a closed grammar built from the registry lists and anchor
   lemmas. Unsupported predicate dependents and prepositions reject as `unsupported_adjunct`;
   purpose dependencies without the required `to` reject as `ambiguous_dependency`; invalid
   spans and unsafe boundaries have separate reasons. A third adjunct is `too_many_adjuncts`.
   Coordination rejects as `unsupported_coordination`. No unknown content is dropped or
   converted into a slot by guesswork.
5. Rules without `adjuncts` keep their existing matcher and template validation. Reporting
   extraction still precedes the construction registry. Tense, strength, ownership and
   sentence-level cluster-key dimensions follow phase 7; construction cluster keys carry the
   bumped registry version. This phase adds no persistence, API or database field.
6. Phase 8.1 corrects an implementation bug in object preposition classification. ADR-0008's
   source-preserving frame contract does not require rejection of object-internal prepositional
   phrases: they remain inside the direct-object `X` span. Only predicate-level PPs are checked
   against the closed adjunct list. Unsupported predicate-level PPs remain rejected.
7. Phase 8.1 keeps modifier and auxiliary candidates in the separate versioned
   `construction_verb_groups.yaml` policy. A candidate is preserved only when dependency, POS
   and surface position agree with the policy. These policy lists are provisional and carry
   `TODO(owner, FR-06.2)`; they do not expand anchors or predicate adjuncts.
8. The original 42 Phase 7 `author_action` instances remain mandatory regression targets.
   Each comparison records source identity and phase output hashes for Phase 7, Phase 8 and
   Phase 8.1. All 42 must be restored under the agreed compatibility contract, the 14 approved
   Phase 8 improvements must remain, and new regressions are not accepted. Each rejection must
   retain a deterministic reason. No source or frame text is stored in the comparison.
9. Phase 9.1 adds the exact literal subject list `we`, `this paper`, `this study`, `this article`
   to `author_action`, without changing its anchor or adjunct inventories. The complete active
   `nsubj` content must case-fold to one listed phrase; its source span remains literal and is
   never made a slot. Other subjects reject as `unsupported_subject`; `nsubjpass` rejects as
   `unsupported_voice`. The existing Phase 7 Tier A rule assigns OWN to the three self-reference
   subjects. Passive voice, copula `be`, `it`, and other `this ...` subjects remain unsupported.

## Consequences and limits

- The anchor, preposition, purpose-dependency and literal-phrase inventories need owner review
  and carry `TODO(owner, FR-06.2)`.
- The candidate modifier-position and auxiliary lists in `construction_verb_groups.yaml` need
  owner review and carry `TODO(owner, FR-06.2)`.
- Passive voice, `it` subjects, copula `be`, unlisted `this ...` subjects, and unlisted adjunct
  types remain unsupported. Frames retain source casing because slots are replaced in-place.
- Aggregate corpus counts describe only the supplied rights-checked field set; they are not
  an independent benchmark. No article sentence or frame sample is committed.
