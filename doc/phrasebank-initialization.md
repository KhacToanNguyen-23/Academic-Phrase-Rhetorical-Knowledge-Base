# Phrasebank initialization

All Phrasebank content sources use one team entry point:

```text
data/phrasebank-init.example.json
  ├─ one AP-RKB pattern source (seed JSON or offline pack) → pattern/version tables
  ├─ APB phrase JSON → pattern/version/APB metadata tables
  └─ optional Manchester collection + reviewed mappings → reference tables
                  one transaction
                         ↓
              existing APIs → Phrasebank/search/filters
```

This is a small orchestration manifest, not a new universal content format. It reuses the existing AP-RKB seed/pack importers, APB seed mapping, and Manchester parser/mapping validation. Raw articles, mining, reviews, Writer, and other ingestion workflows keep their current paths. Existing individual import commands remain available for compatibility; this is the standard team command for initializing Phrasebank.

## Input file

Edit the single manifest at `data/phrasebank-init.example.json`. The checked-in version points at all self-authored phrase sources currently supplied in this repository:

```json
{
  "schema_version": "1",
  "pattern_seed": "seed/patterns.json",
  "academic_phrases": "seed/academic_phrases.json"
}
```

Supply exactly one AP-RKB source: `pattern_seed` for the checked-in self-authored seed JSON, or `pattern_pack` for an existing offline pack directory. `academic_phrases` adds APB records to the same transaction. Manchester inputs are optional; when used, `reference_library` and `reference_mappings` must both be supplied. Mapping files use the existing `mappings` structure (YAML or equivalent JSON), including reference key/title, target kind/code, review status, mapped-by, and note fields. Paths are relative to the initialization file and must remain inside its directory; move the complete input folder together between machines.

The new flow takes reference mapping inputs explicitly from this manifest rather than reading the checked-in default category mapping YAML. Existing database mappings whose identities/titles remain valid are preserved, and supplied mappings update them using the existing mapping rules. Unmapped/null rows retain the legacy no-op behavior; omission or null is not a request to delete an existing reviewed mapping. Supply every mapping needed for a reproducible fresh initialization.

## Run

Use a separately configured staging/test database with migrations and published reference taxonomy already initialized. The existing `init-reference` command can initialize reference data for a new destination; it does not import sample patterns. All commands use that environment's existing `DATABASE_URL`.

From `apps/backend`:

```powershell
uv run python -m aprkb.cli init-phrasebank --file ../../data/phrasebank-init.example.json --dry-run
uv run python -m aprkb.cli init-phrasebank --file ../../data/phrasebank-init.example.json
```

The preview runs every configured source in one transaction, then rolls it all back. Apply commits only when the entire workflow succeeds. Invalid pack/seed data, collection data, or mapping codes leave no partial imports. Output reports AP-RKB pattern/version additions, APB source record count, reference counts, mapping-row count, and whether this was a preview. No initialization is triggered on app startup or by file changes.

Keep `REFERENCE_LIBRARY_ENABLED=true` in the serving environment to expose Manchester routes. The existing taxonomy, pattern, and reference APIs continue supplying the same UI/search/filter behavior. This workflow does not change user-facing endpoints, source separation, licensing, approval rules, result limits, or filter-before-limit fixes.

## Existing behavior retained

- Pattern imports remain additive and idempotent for existing versions; they do not retire omitted patterns.
- Manchester reimport replaces the named collection's entry rows and retains compatible mappings. Entry UUIDs may change, as with the standalone importer.
- Taxonomy data is a prerequisite, not overwritten by this workflow. Pattern section/intent data comes from its pack or seed; APB records resolve their configured sections, functions, and Intents against the destination taxonomy. Manchester filter associations come from the specified mappings, against that taxonomy.
- Existing `export-pack`, `validate-pack`, `import-pack`, `import-reference-library`, and `import-reference-mapping` commands retain their defaults.
- No live database is migrated or cleared merely by installing this command. Future retirement, rollback, additional datasets, or exclusive-writer enforcement require separate scope.
