# Brainstorm: Mining slot abstraction and conservative phrase variants

**Date:** 2026-10-30

## Ideas Explored

- **Regex-only:** reproducible baseline for citations/numbers/statistics; insufficient for noun phrases such as `retrieval accuracy`.
- **Regex + spaCy:** preferred experimental engine for syntactic spans, with explicit dependency/model versions and no silent fallback. Syntax is evidence, not semantic certainty.
- **Whole-sentence frames:** useful context/baseline but long and specific; likely fewer reusable repeated phrases.
- **Formulaic prefixes + sentence context:** user's preferred hypothesis; evaluate candidate spans separately from their contextual sentence.
- **Clause segmentation:** deferred until simpler units have been compared.
- **Broad versus conservative NP spans:** compare experimentally. Positional slot IDs avoid making cue-word guesses part of clustering identity.
- **Reviewed lexical classes:** chosen for reporting-verb equivalence and narrow determiner normalization. Unknown forms remain literal; subject-head classes default to empty.
- **Broad keys, unrestricted lemmatization, WordNet, and edit distance:** rejected for automatic synonym equivalence because they lose protected distinctions or do not establish synonymy.
- **Corpus statistics/Jaccard:** useful for offline proposals, never automatic lexicon changes. Scientific NER/LLMs are future work; only a disabled null assistant interface is proposed now.

## User's Direction

The governing rule is **“Khi không chắc chắn, phải tách cluster, không được gộp.”** False merges can assign incorrect shared `epistemic_strength` and `allowed_sections`; false splits remain repairable by reviewers.

- Dataset first: self-authored examples, two independent human annotations, adjudication, then policy comparisons and ADR.
- Compare sentence/prefix units and alternative slot boundaries. Preserve surface frames, source context, and slot offsets.
- Separate clusters by intent, effective strength, reporting tense, or slot structure. `past`, `present`, and `present_perfect` differ. Active/passive may be variants when argument roles align.
- Normalize reporting verbs using reviewed, complement-sensitive synonym classes with explicit surface forms; unknown items do not alias automatically.
- Normalize determiners narrowly; retain subject heads, leaving `results`, `findings`, and `data` separate by default. Prior-study and own-study attribution must differ.
- Assign review-group keys without deleting different variants. Consolidate only verbatim duplicates with lossless per-occurrence provenance.
- Use `family_id` only for analysis/display. Keep citations through filtering and interpret their grammatical role during abstraction.
- Report merge precision as primary, recall/coverage alongside it, and four lexicon ablations. Synonym proposals never change YAML; AI cannot approve a synonym or count as an editor.

## Narrowed Direction

Choose **B: regex + spaCy** as the principal engine, and retain **A: regex-only** as baseline. Prefer prefix candidates alongside sentence context, subject to measured results. Start planning with the annotation protocol and draft dataset rather than algorithm implementation.

Compare broad NP slots with conservative spans that retain protected rhetorical modifiers. Use positional slot identities as the baseline and treat semantic names as review metadata.

Preserve reporting tense/effective strength and accept only explicit supported voice transformations. Keep a full structural key explanation alongside a bounded, versioned digest.

## Repository Findings

- `MiningItem` has only text/source IDs; candidate spans and metadata must be added end to end.
- `SentenceFilter` removes citations and rebuilds items, destroying offsets and potentially future metadata.
- Move/epistemic stages are stubs; they cannot supply reliable intent/strength. Gold-conditioned key evaluation must be distinguished from real pipeline behavior.
- Candidate persistence has clustering fields, but the draft/writer path omits them. `cluster_key` is limited to 255 characters.
- One candidate slots object cannot preserve different source originals/offsets after blindly unioning sentence IDs.
- Policy versions currently require semver strings; the discussion's integer versions need adaptation.
- The user's working tree contains article-source work and `0002_article_source`; preserve those edits and follow the real migration head later.
- The current scaffold excludes these algorithms. Update capability claims and ADR only in the later implementation; this brainstorm writes planning artifacts only.

## Corrections to the Attached Task

1. Preserve citations through filtering; retain a placeholder for essential citation complements.
2. Replace automatic normalized-frame merging with key assignment and lossless verbatim-only consolidation.
3. Preserve each occurrence's slots; do not keep only the first duplicate's originals/offsets.
4. Keep unknown intent/strength/tense explicit. Do not fabricate classification output to populate a key.
5. Bare `the/this/these` cannot establish own-study attribution; require context or retain literal text.
6. A class-strength field alone cannot detect semantic misclassification of `show`; cross-check reviewed marker mappings and require human approval.
7. Ignoring slot names must still preserve repeated-slot bindings and slot structure.
8. Mining preserves candidate surface text; the later review path creates `PhraseVariant` records.
9. Agent-written draft annotations do not constitute approved two-editor gold or a production-quality benchmark.
10. Keep the assistant disabled/null and exported synonym examples masked.
11. Distinguish genuinely non-applicable reporting metadata for non-reporting prefixes from unknown classifier output; only explicit applicability rules/annotations can authorize the former.
12. A field named `frame` can still contain unchanged or partially masked source text. Export examples only from self-authored fixtures or reviewed/licensed display-eligible masked frames; withhold uncertain examples.

The contextual guard for ambiguous `the/this/these` is an assistant-proposed refinement, not a literal restatement of the user's determiner table; it is left explicit for confirmation in the spec. Also, lemmatization alone collapses inflections such as `showed/show`; it does not establish synonymy between `suggest/indicate` or `showed/suggest`.

## Open Questions

The user subsequently resolved the protocol, thresholds, and ownership guard directly in the spec:

- Roles are **Language Editor A/B**, matching System Design §7.3 (PDF p. 10) and the two-editor validation requirement in PRD FR-06.6 (PDF p. 5). Serialization handles are `language-editor-a`, `language-editor-b`, and independent `adj-c`; real-person mappings stay outside Git. A third independent adjudicator and the two-person consensus fallback are protocol proposals, not explicit requirements of FR-06.6.
- The agreement target **κ ≥ 0.70** is derived from System Design §8.1 (PDF p. 10), whose phrase-approval KPI specifies Cohen's κ or Krippendorff's α at 0.7 as a proposed experimental goal. It was not invented during this discussion. Choosing κ per metadata field, linear strength weights, cluster pairwise F1 0.80, blindness, and mandatory re-annotation are this extension's operational design choices. Slot spans use exact agreement; applicability/undefined cases are handled separately.
- Target split is 70/30 by complete family/context groups. Development gates: exact slot F1 0.80, frame exact match 0.70, coverage 0.80, and no-phrase false-positive rate at most 0.10. Overlap F1 and whole-set extra-candidate rate remain reported diagnostics. Hard protection/offset/grouping/determinism invariants still apply.
- Choose maximal exact slot F1, preferring simpler configurations within 0.02. Prefix replacement must preserve frame score and lose no more than 0.05 coverage. Held-out is scored once with the same strict thresholds; the file's previous 0.05 threshold exemption was removed to match the user's stated rejection rule.
- `our`, `the present`, and `the current` are unconditional own-study markers. `the/this/these` need an own-study cue, no citation/prior cue, and a same-section window of one previous sentence. Gold includes all four context/boundary probes.
- A new scope prerequisite keeps implementation/evaluation tooling behind an owner-approved M2 change to the authoritative PRD/README/ADR. The existing optional `nlp` extra is the only spaCy installation path. Default regex tests remain independent of that extra. Assistant technical review recommends this limited M2 extension; it does not constitute owner approval.
- ADR-0006 should record the scope/protocol decision first; evaluated extraction-policy adoption is a later dated decision. This resolves the prior before/after-evaluation timing conflict.

Remaining owner actions: assign real people to handles externally, approve the M2 scope change, and record the frozen protocol/configuration before opening held-out data. The phrase-unit/slot-width winner remains an intentionally scheduled experiment.

The spec now includes a rule-group source matrix and explicit requirement/KPI/design labels. PRD FR-06.3 requires confidence and reviewer confirmation for clustering; it does not prescribe the proposed lexical-class/key algorithm. PRD FR-06.6 requires two-editor validation agreement and disagreement/adjudication reporting; extending that count to lexicon PR approvals is an extension policy. Extraction frame exact match 0.70 remains a proposed metric and must not be confused with the document's agreement KPI at the same numeric value.

## Risks

1. Ownership, effective-strength, or voice mistakes cause unsafe false merges. Preserve literal/isolated keys on uncertainty and include explicit negative pairs.
2. Statistical parsing/handwritten vocabulary can miss scientific language; small synthetic data can hide errors and cannot justify production claims.
3. Consolidation loses provenance without occurrence-level mappings; policy/model changes make keys incomparable without configuration fingerprints.

## Handoff

Spec: `plans/mining-slot-abstraction/spec.md`.

Next: `$bb-plan plans/mining-slot-abstraction/spec.md`, starting with protocol/draft data. No implementation, approved annotations, ADR acceptance, or commits were performed in this brainstorm.
