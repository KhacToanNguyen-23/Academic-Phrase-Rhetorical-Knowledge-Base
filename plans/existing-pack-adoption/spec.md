# Spec: Shared Phrasebank initialization

Date: 2026-11-04 (Asia/Bangkok)
Status: User-confirmed scope implemented and verified.

## Problem statement

The team wants both Phrasebank sources and their search/section/intent filter data initialized through one entry point, while preserving other workflows. Reuse the existing AP-RKB pack and Manchester import contracts.

## User stories

- **[P1]** As a team member, I want one `data_init.json` manifest to identify both Phrasebank sources and reviewed reference mappings so setup is repeatable.
  Accepted when: `init-phrasebank --file <manifest>` imports the unchanged pattern pack, collection JSON, and mapping file into their existing tables.
- **[P1]** As a maintainer, I want a preview and all-or-nothing import so a broken mapping cannot leave partially updated Phrasebank data.
  Accepted when: dry-run and failures leave zero lasting changes; apply commits both datasets and mappings together.
- **[P1]** As an app user, I want existing behavior preserved.
  Accepted when: existing APIs/filter regressions and standalone importer tests pass without endpoint/schema changes.

## Requirements

1. Manifest version `1` requires relative `pattern_pack`, `reference_library`, and `reference_mappings` paths inside the manifest directory; reject unknown fields or versions.
2. Reuse existing validators/importers, stable pattern IDs, rights/approval rules and mapping semantics. No new universal content format.
3. Expose one existing-CLI command with `--file` and `--dry-run`. Use the configured destination database; perform no automatic startup imports.
4. Load Manchester category/heading mapping inputs explicitly, without checked-in mapping defaults in this combined path. Preserve existing standalone defaults and compatible stored mappings.
5. Preserve acquisition, raw article storage, mining, reviews, Writer, runtime reads, and other modules. Published reference taxonomy is a prerequisite.

## Success criteria

- [x] Combined import supplies both sources and mapped filter results through existing APIs.
- [x] Preview, invalid pack and invalid mapping tests demonstrate no lasting partial changes.
- [x] Repeated initialization creates no duplicate patterns or reference collections.
- [x] Existing pack, reference, read/filter, CLI checks and documentation remain compatible.

## Out of scope

Live data transfer, database clearing/migration, automatic file watching, changing approval meanings, universal JSON, retirement/rollback implementation, or disabling legacy writers.

## Assumptions

The team distributes the manifest and its referenced existing-format files together. A single initialization flow does not require flattening both incompatible datasets into one payload.
