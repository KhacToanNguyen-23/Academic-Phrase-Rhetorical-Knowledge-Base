# Phrasebank initialization

Both Phrasebank sources and their reference filter mappings use one team entry point:

```text
data_init.json
  ├─ existing AP-RKB pattern pack → pattern/version tables
  ├─ existing Manchester collection JSON → reference tables
  └─ reviewed reference mappings → reference taxonomy mappings
                  one transaction
                         ↓
              existing APIs → Phrasebank/search/filters
```

This is a small orchestration manifest, not a new universal content format. It reuses the approved-pattern pack and existing Manchester parser/mapping validation. Raw articles, mining, reviews, Writer, and other ingestion workflows keep their current paths. Existing individual import commands remain available for compatibility; this is the standard team command for initializing Phrasebank.

## Input file

Copy `data/phrasebank-init.example.json` to `data/data_init.json` and edit the paths:

```json
{
  "schema_version": "1",
  "pattern_pack": "packs/release-001",
  "reference_library": "raw/manchester-diverse/collection.json",
  "reference_mappings": "raw/manchester-diverse/mappings.yaml"
}
```

All three inputs are required. Paths are relative to the initialization file and must remain inside its directory; move the complete input folder together between machines. The pattern directory contains the unchanged `manifest.json` and `patterns.json`. The collection is the existing scraped export. Mapping files use the existing `mappings` structure (YAML or equivalent JSON), including reference key/title, target kind/code, review status, mapped-by and note fields. The example's raw inputs are placeholders and are not supplied in git.

The new flow takes reference mapping inputs explicitly from this manifest rather than reading the checked-in default category mapping YAML. Existing database mappings whose identities/titles remain valid are preserved, and supplied mappings update them using the existing mapping rules. Unmapped/null rows retain the legacy no-op behavior; omission or null is not a request to delete an existing reviewed mapping. Supply every mapping needed for a reproducible fresh initialization.

## Run

Use a separately configured staging/test database with migrations and published reference taxonomy already initialized. The existing `init-reference` command can initialize reference data for a new destination; it does not import sample patterns. All commands use that environment's existing `DATABASE_URL`.

From `apps/backend`:

```powershell
uv run python -m aprkb.cli init-phrasebank --file ../../data/data_init.json --dry-run
uv run python -m aprkb.cli init-phrasebank --file ../../data/data_init.json
```

The preview runs both existing imports and validates mappings within one transaction, then rolls it all back. Apply commits only when the entire workflow succeeds. Invalid packs, collection data, or mapping codes leave neither a partially imported pack nor a replaced reference collection. Output reports pattern additions, reference counts, mapping-row count, and whether this was a preview. No initialization is triggered on app startup or by file changes.

Keep `REFERENCE_LIBRARY_ENABLED=true` in the serving environment to expose Manchester routes. The existing taxonomy, pattern, and reference APIs continue supplying the same UI/search/filter behavior. This workflow does not change user-facing endpoints, source separation, licensing, approval rules, result limits, or filter-before-limit fixes.

## Existing behavior retained

- Pattern imports remain additive and idempotent for existing versions; they do not retire omitted patterns.
- Manchester reimport replaces the named collection's entry rows and retains compatible mappings. Entry UUIDs may change, as with the standalone importer.
- Taxonomy data is a prerequisite, not overwritten by this workflow. Pattern section/intent data comes from its pack; Manchester filter associations come from the specified mappings, against the destination taxonomy.
- Existing `export-pack`, `validate-pack`, `import-pack`, `import-reference-library`, and `import-reference-mapping` commands retain their defaults.
- No live database is migrated or cleared merely by installing this command. Future retirement, rollback, additional datasets, or exclusive-writer enforcement require separate scope.
