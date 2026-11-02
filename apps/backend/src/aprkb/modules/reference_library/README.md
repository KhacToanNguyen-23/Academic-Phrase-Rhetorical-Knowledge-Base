# Reference library

The Manchester JSON is removable demo data held in isolated `reference_*` tables. The importer is strict and idempotent, keeps page provenance and source block identifiers, and never copies entry text into audit events. `REFERENCE_LIBRARY_ENABLED` defaults to `false`. The source API returns empty category and search responses after purge while the AP-RKB pattern API remains independent.

The mapping layer relates a reference category or heading to AP-RKB taxonomy. It does not create or update `phrase_patterns`, `PatternVersion`, `PhraseVariant`, `UsageConstraint`, or `EvidenceProvenance`. Mapping rows start as `proposed`; an owner can review them through the exported template and import command. Heading maps are Intent-level groups. A category can map to a Section or General function. ArticleGenre remains independent of the Section > Move > Step > Intent hierarchy and is not inferred from reference categories.

## Import and mapping commands

```powershell
cd apps/backend
uv run aprkb import-reference-library --file PATH
uv run aprkb export-reference-mapping-template
uv run aprkb import-reference-mapping --file PATH
```

The mapping template contains only category and heading titles plus empty target fields. `import-reference-mapping` checks that each key/title still exists, validates section and intent codes against the current taxonomy, and idempotently upserts populated rows; blank target rows are no-ops. The seed mapping file beside this module contains only proposed category-to-Section mappings backed by existing seed codes. No General function code exists in the current seed taxonomy; adding those mappings is `TODO(owner)`.

## JSON-to-domain mapping

| JSON field | Reference table column | Document entity or role |
|---|---|---|
| `pages.title` | `reference_categories.title` | Display label for a Section or General function group |
| `pages.source_url` | `reference_categories.source_url` | ProvenanceSource source URI |
| `pages.resolved_url` | `reference_categories.resolved_url` | ProvenanceSource resolved source URI |
| `pages.captured_at` | `reference_categories.captured_at` | ProvenanceSource capture time |
| `pages.html_sha256` | `reference_categories.html_sha256` | ProvenanceSource content fingerprint |
| `pages.source_category` | `reference_categories.source_category` | ProvenanceSource source category; analogous to `PatternVersion.source_category` after curation |
| `pages.license_status` | `reference_categories.license_status` | License/provenance metadata; not an approval decision |
| `pages.rights_status` | `reference_categories.rights_status` | Provenance and rights state |
| `pages.status` | `reference_categories.status` | Demo source lifecycle state |
| `pages.note` | `reference_categories.note` | Short internal provenance note; never a phrase body |
| `pages.extraction_method` | `reference_categories.extraction_method` | Extraction provenance |
| `blocks.block_id` | `reference_entries.block_id` | Stable source-block provenance identifier |
| `blocks.heading` | `reference_entries.heading` | Displayed heading; an Intent mapping is separate and reviewable |
| paragraph `lines` | `reference_entries.text` | Reference-only note; not a PhrasePattern or PhraseVariant |
| table `rows` | `reference_entries.cells` | Display-only phrase pattern row and alternatives; not an AP-RKB PhrasePattern/PhraseVariant |
| mapping target | `reference_taxonomy_map.target_kind/target_code` | Reviewed Section, Intent, or General function alignment |

The category API exposes per-page provenance, block IDs, category Section/General function mapping, heading Intent mapping, and review status. Its `note` is the short internal page comment from the JSON, not entry text.

## Removing demo data

From the backend environment connected to the intended demo database:

```powershell
cd apps/backend
uv run aprkb purge-reference-library
Remove-Item Env:REFERENCE_LIBRARY_ENABLED -ErrorAction SilentlyContinue
```

Also remove any `REFERENCE_LIBRARY_ENABLED` override from that environment's `.env` file so the default remains disabled. Purge removes the source, categories, entries, and their mapping rows through foreign-key cascades. It does not touch AP-RKB patterns or taxonomy. After purge, with the flag enabled for a check, category listing and search return HTTP 200 with an empty reference source; `/v1/patterns` continues to serve AP-RKB data. With the flag unset, the reference routes are hidden and the page retains its disabled state.

## Verification boundary

PostgreSQL integration tests require `TEST_DATABASE_URL` to name only the dedicated `aprkb_test` database. Do not run migrations or imports against a real or demo database while working on this module. Migration `0006_reference_library` is unreleased and may be edited in place before the owner rebuilds the demo database.
