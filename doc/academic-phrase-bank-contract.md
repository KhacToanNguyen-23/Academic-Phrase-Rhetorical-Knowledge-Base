# Academic Phrase Bank data contract

**Status:** Draft for implementation review  
**Date:** 2026-11-09  
**Scope:** APB data and browsing in the existing Phrasebank area

This document maps the APB specification to the current repository and records the compatibility boundaries for implementation. It does not change the Offline pack contract or introduce Writer integration.

## Existing repository contract

The current rhetorical taxonomy is `Section -> Move -> Step -> Intent`. `PhrasePattern.intent_id` references an `Intent`; the corresponding `Step` and `Move` are resolved through the taxonomy foreign keys. The published taxonomy API returns database IDs, stable codes, labels, and taxonomy version. Pattern packs use the full natural-key intent path and its `taxonomy_version` rather than database UUIDs.

The checked-in taxonomy seed is explicitly provisional. APB records must therefore resolve references against the active database taxonomy release. Do not hard-code UUIDs or treat translated UI labels as keys. Do not add APB links to a taxonomy code until that code resolves in the selected release.

## APB field mapping

| APB requirement | Current storage | Contract decision |
|---|---|---|
| Canonical template and typed slots | `PatternVersion.canonical_frame`, `PatternVersion.slots` | Reuse when the template follows the existing pattern lifecycle. Preserve append-only versions. |
| Template identity and lifecycle | `PhrasePattern` | Reuse the current stable identity and status lifecycle; no duplicate phrase row for each function or section. |
| Communicative Function Family and Function | None | Add an APB-owned, versioned function catalog. Keep its codes distinct from Move/Step/Intent codes. |
| Function-to-template mapping | None | Add a many-to-many association at `PatternVersion` level so a revised version can retain its own labels. |
| Move/Step applicability | Indirectly available through the single `Intent` on `PhrasePattern` | Add explicit version-level links to existing `Move` and/or `Step` rows where APB applicability differs from the single pattern intent. Validate that a linked Step belongs to the linked Move. |
| Section and genre constraints | `UsageConstraint.allowed_sections`, `allowed_genres` | Reuse for existing hard eligibility constraints. APB usage profiles may add context-specific records, but must not change current recommendation gate meanings. Resolve section codes to actual taxonomy rows when creating APB profile links. |
| Register | `PhraseVariant.register` | Reuse for variant-level register. Add profile-level register only when the APB specification requires applicability independent of a particular variant. |
| Epistemic strength and claim type | `PatternVersion.epistemic_strength`, `claim_type` | Reuse these existing labels; do not treat them as a complete substitute for APB pragmatic facets. |
| Stance, hedging, boosting, engagement, contrast, transition | None as structured APB labels | Add validated APB pragmatic facets with stable codes. Do not infer them from phrase text at read time. |
| Discipline/domain | `DisciplineAffinity` | Reuse existing affinity and score where it has the same meaning. Add no second domain mapping until the owner confirms the authoritative domain codes and taxonomy version. |
| Examples, counterexamples, and caveats | No APB-specific entities | Add versioned, self-authored example/caveat records. Do not store copyrighted source sentences or article text in these records. |
| Provenance and rights | `EvidenceProvenance`, `License` | Reuse existing source/license references where sufficient. APB publication must continue to fail closed when provenance or rights are unknown. |
| VTB Concept/Sense link | VTB currently stores lemmas and word families only | Defer semantic links. Do not substitute a lemma string for a Concept/Sense ID. Activate only after the VTB owner supplies a stable ID and API contract. |
| Search and display labels | Current pattern/reference APIs | Add APB read/filter contracts using stable codes; display labels come from the API/database, not frontend mock data. |

## Proposed relation semantics

- One canonical `PhrasePattern` may have multiple Communicative Functions across its versions.
- Function links, Move/Step applicability, usage profiles, pragmatic facets, examples, and caveats attach to a specific `PatternVersion` so readers can retrieve the classification that was reviewed for that version.
- APB Communicative Function answers “what communicative purpose does this template serve?” Existing Move/Step/Intent answers “where does this contribution fit in the rhetorical structure?” They are related labels, not synonyms.
- A usage profile describes a valid context using approved codes (for example genre, section, language, register, and discipline). Multiple profiles may apply to one version without copying the template.
- VTB references remain nullable and absent until stable Concept/Sense keys exist.

## Offline pack boundary

Offline pack v0.1 remains unchanged. Its strict schema requires the existing intent path and transfers the current PhrasePattern graph only. APB metadata is not encoded by repurposing `IntentPath`.

The offline producer owner confirmed that APB labels must round-trip. Pack v0.2 adds a typed `apb` object to a pattern version while preserving v0.1 validation/import/export. Imported offline labels are stored as proposals in a separate table; they do not create reviewed APB links or become publicly visible. Stable function/pragmatic codes and versions, taxonomy paths, and domain codes are used instead of database foreign-key IDs. Generation cannot create curator approval, provenance, rights, or Concept/Sense links.

## Seed and curation constraints

- APB Function codes and examples are self-authored and marked provisional until reviewed.
- Do not map to provisional rhetorical codes unless those codes exist in the selected database taxonomy release; record the release version used.
- The current development seed contains 32 user-authored Methods templates. Keep them draft until reviewed; do not copy Manchester Academic Phrasebank content into APB seed data.
- Reuse existing curator/API boundaries where feasible. This contract does not authorize a new admin console or a general taxonomy-publishing system.

## Approved working decisions before schema migration

1. Use the current database taxonomy only by resolving stable codes against the selected release. Its current seed remains provisional; do not create APB mappings that rely on unapproved labels.
2. Do not transfer APB metadata through the Offline pack for this delivery. Keep v0.1 unchanged unless its owner separately requests round-tripping.
3. Defer VTB Concept/Sense links until stable identifiers and an API contract are available.
4. Use the existing curator role and approval gates. Do not add an admin console.

The Communicative Function code set remains an APB-owned versioned catalog. Any initial examples are provisional and self-authored pending curator review.

