# ADR-0015: Metric & Measurement catalog

Status: proposed; implemented locally behind `MEASUREMENT_ENABLED` (default off).

## Context

The Academic Phrase core answers "how to write" (hedging, stance, transitions,
Methods/Results moves). Task 3 adds the complementary "how to measure" knowledge:

- **metric**: an indicator such as accuracy or Cohen's kappa;
- **method**: a measurement method such as a 5-point Likert questionnaire;
- **protocol**: a data-collection procedure such as a pre-test/post-test design.

The PRD and System Design v1.0 do not define this domain. It touches three existing
requirements:

- FR-02.1: patterns have typed slots;
- FR-07.5 / AT-08: render must never fabricate slot content;
- FR-08.2: validation must flag invented metrics without auto-generating evidence.

## Decision

1. The new `measurement` module is a separate domain. Its tables never enter
   `phrase_patterns`, ranking, recommendations, render or pack export. Validate only
   reads it for the report-only FR-08.2 check (decision 6).
2. The catalog is self-authored JSON (`data/seed/measurement_catalog.json`) with
   definitions written for this project. Nothing is copied from textbooks or
   standards.
3. The bridge to phrases is a reviewed **slot link**: an entry, a pattern and a slot
   name. For example, `likert_5_point` can be linked to the `{instrument}` slot of a
   Methods pattern. A curator proposes the link and a curator approves it. Only
   approved links are public. Approved links are shown as optional **suggestions**
   for that slot and are never auto-filled.
4. Vocabularies (kinds, relations, link statuses) live in versioned
   `policies/measurement.yaml`, marked `TODO(owner)`.
5. Read routes require a client key. Import and link review require the curator role.
   All routes return 404 when the feature flag is off. `measurement-purge` (CLI only)
   removes all catalog rows, slot links and import runs in one audited transaction.
6. FR-08.2, report-only: while the flag is on, `/v1/validate` lists catalog metrics that
   the sentence names (by name or alias) but the writer's slots or context do not. They
   appear in `metric_warnings` and `warnings`. They never change rule outcomes, severity
   or `complete`, and nothing is generated. Acronyms match case-sensitively; terms shorter
   than `metric_check_min_term_length` are ignored. It cannot detect metrics missing from
   the catalog, and common-word names such as "precision" can raise false warnings.

## Deferred

- Mining measurement mentions from `METHODS` sections. If added later, it must be
  rule-based, run in shadow mode, be license-gated before blob reads, and produce
  draft provenance only. There is no provenance table until that producer exists.
- Discipline-specific catalogs.

## Consequences

The phrase core stays unchanged when the flag is off, and the migration only adds
tables. Removing the domain requires dropping the four `measurement_*` tables.
