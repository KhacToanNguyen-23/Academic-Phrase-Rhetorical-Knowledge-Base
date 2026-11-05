# Phase 2: Filter Phrasebank before result limits

Status: implemented and verified. Boundary API regressions and all 9 Phrasebank Edge tests passed; web build/typecheck and backend checks passed. Independent of deferred phase 3 import discovery.

## Confirmed issue

`apps/web/src/features/phrasebank/source-registry.ts` fetches only 200 AP-RKB patterns or 50 Manchester query hits. `PhrasebankPage.tsx` applies section/intent predicates afterward. Matching entries beyond those unfiltered caps disappear. This is a retrieval-order defect; duplicate ingestion has not been shown to cause it.

## Smallest complete approach

1. Add optional `q` browsing search to `apps/backend/src/aprkb/modules/patterns/router.py` and forward through `patterns/service.py` into `patterns/read_model.py`. Use a separate browsing-search argument from the recommendation loader's token-based `query` so recommendation semantics remain unchanged. Preserve the frontend's current case-insensitive substring search over canonical frame, intent code, and joined allowed sections. For client display-only reads the loader already builds eligible rows before slicing: apply browsing search to those eligible rows before the final offset/limit slice. Existing section and intent predicates already run before limits. Keep curator behavior consistent if the new parameter is accepted there.
2. Add optional `section` and `intent` parameters to `reference_library/router.py` and `service.py`. Extend `reference_library/repository.py` to permit an uncapped query result for this mapped-search path. Load matching rows in deterministic existing order, resolve mapping metadata with the same precedence as today (heading intent section first, category section fallback), filter section/intent and phrase kind, then slice to the requested output cap. This bounded reference-library implementation avoids duplicating mapping rules in a complex SQL query; assess matched-row volume during verification. Do not merely increase the old cap. Keep the default unfiltered API's note/phrase behavior compatible; request phrase-only browsing explicitly if necessary.
3. In `source-registry.ts`, pass AP-RKB `q`, `section`, and `intent` to the API and Manchester section/intent to its API. In `PhrasebankPage.tsx`, fetch filtered results when query or taxonomy filters change; include all selected filters in React Query keys. Do not derive filtered results from the initial capped cache. Keep the unfiltered category landing view and provenance source separation intact.
4. State the existing source-specific result cap in the results UI (for example “Showing up to 50 matching results”). This is a focused correctness fix, not a complete pagination system. Avoid claiming the capped count is the total matching count. Review the existing unmapped-item count text: filtered responses cannot supply a global hidden count; remove that claim for filtered search or label its limited scope accurately.
5. Regenerate `packages/contracts/openapi/openapi.json` and `apps/web/src/shared/api/schema.d.ts` after the optional query additions, preserving unrelated user edits. Update README filter behavior.

## Verification

- PostgreSQL API fixtures with more than 200 approved AP-RKB patterns, where the only keyword+section+intent match is beyond row 200; assert it is returned under a small limit.
- More than 50 Manchester query hits with the only selected section+intent match after hit 50; assert it is returned. Include heading-intent override, category-section fallback, unmapped exclusion, combined filters, and deterministic ordering.
- Extend `apps/web/e2e/phrasebank.spec.ts` to verify changed filters refetch with their parameters, search combines filters, source switching works, no false empty state arises from old capped data, and result-cap text is accurate.
- Run affected backend unit/API suites, web type checks, focused Phrasebank e2e, and lint. Report unavailable database/browser infrastructure explicitly.

Accepted when predicates precede the result cap on both sources and fresh boundary regressions verify the previously invisible matches.
