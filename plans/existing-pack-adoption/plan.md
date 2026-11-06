# Shared Phrasebank initialization

Mode: --fast
Risk: normal — orchestrates existing validated imports; no schema or endpoint changes. Actual initialization writes data only when explicitly invoked.
Status: implemented and verified; changes uncommitted.

Spec check: P1 stories and measurable dry-run/rollback/compatibility criteria established. Earlier generic `prepare-pack` prototype was removed after scope clarification.

- [x] Implement a strict path manifest and `init-phrasebank` command that reuses existing pattern/reference/mapping importers.
- [x] Allow existing reference importers to participate in a caller-owned transaction; retain standalone commit/default mapping behavior.
- [x] Document the manifest, prerequisites, explicit mapping input and preserved behavior.
- [x] Verify combined success/API filters, dry-run, all-or-nothing failure and repeat import; run existing regression suites and review.

Actual database transfer, automatic initialization, pipeline consolidation outside Phrasebank, and exclusive-writer enforcement remain out of scope.

## Verification

- 96 existing compatibility unit tests passed (pack validator/service, reference library, patterns, recommendations).
- 15 final manifest/reference API/pack-round-trip tests passed using isolated `aprkb_test` schemas. Covers both API filter sources, repeat import, explicit category/heading mappings, no hidden default mappings, and rollback of failed/dry-run changes.
- Ruff and formatting passed; mypy found no issues in the five changed source files; OpenAPI unchanged. Code review found no actionable defects.
- One existing Pydantic warning about the pack `register` field remains. No live app data was initialized or migrated.

## Session Notes

Last active: 2026-11-04 (Asia/Bangkok).
Scope decision: both Phrasebank sources and filter mappings use one manifest; keep existing contracts, APIs and standalone defaults.
Next action: use the documented preview/apply commands with real team inputs when ready. No further implementation is required for this scope.
