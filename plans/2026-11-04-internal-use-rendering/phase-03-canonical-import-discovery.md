# Phase 3: Discover and standardize the canonical JSON import flow

Status: deferred by the user; do not execute as part of the active plan. Revisit after phases 1 and 2 only when the user supplies more context or requests discovery.

## User direction

Standardize scraping/import through one `data_innit` JSON artifact. The exact filename/path and whether this applies only to scraped Phrasebank data or all database imports are unresolved. Repository file discovery has not found a `data_innit` or `data_init` artifact. Do not invent its schema or replace existing ingestion paths based on its name.

## Discovery inventory

- Scraped Manchester data: README documents external `collection.json` loaded via `import-reference-library --file`; trace CLI → reference-library importer → database and identify the scraping producer/source repository.
- Seed JSON under `data/seed`: reference enums, taxonomy, and authored bootstrap data, with a distinct bootstrap purpose.
- Offline packs: `import-pack` validation/import contract.
- Corpus uploads and SLR ingestion: article ingestion and mining inputs.
- Human-reviewed candidate promotion: approved pattern publication, a distinct lifecycle stage.

These are legitimate distinct pipelines until evidence establishes overlap. The phase 2 filter-order defect is independently confirmed; multiple import paths are not a proven cause.

## Required contract decisions

1. Obtain the exact canonical JSON path or example and its producer, schema/version, stable identifiers, taxonomy mappings, provenance, licenses, and intended dataset coverage.
2. Confirm whether only scraped Phrasebank ingestion must converge or every database import is in scope. If broader, separate phase plans by dataset rather than forcing unrelated entities into one untyped JSON.
3. Trace each in-scope writer and define one documented entry point, validation, deterministic ordering, transaction/failure behavior, and repeat-import/update semantics. Decide how existing records remain compatible before any replacement or migration.
4. Produce a concrete implementation plan and reclassify risk if data migration or irreversible cleanup is required. Do not delete data, disable endpoints, or rewrite imported records during discovery.

## Acceptance criteria for discovery

A verified canonical artifact contract, an evidence-based ingress diagram/inventory, a precise list of paths to consolidate versus retain, and fixture-based verification requirements for repeat import, duplicate handling, provenance/rights retention, taxonomy mapping, and rollback. Implementation remains pending those decisions; phases 1–2 can proceed independently.
