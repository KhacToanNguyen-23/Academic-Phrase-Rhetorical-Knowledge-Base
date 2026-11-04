# Filter correctness and internal-use rendering

Mode: --fast
Risk: normal — existing filter and license business logic; optional API query additions, no authentication or database schema changes for phases 1–2. Reclassify phase 3 after its scope is known.
Status: phases 1–2 implemented and verified; import-flow follow-up deferred.

## Decision and scope

The entire app is for internal use. A mined phrase whose source license code is explicitly permitted by `license_policy.yaml`'s `internal_use_codes` may be recommended, read, and rendered even when `License.allows_display` is false. Public-display permission does not veto an explicit internal-use permission. Preserve phrases already allowed by display permission and authored sources. Do not allow every restricted license merely because the application is internal.

Keep the stored `license_allows_display` value truthful and keep `license_flag` as the indication of a configured internal-use exception. Keep current-version, approval, single-provenance, recommendation ownership, slot validation, and remaining recommendation gates intact.

## Existing gap

Recommendations already accept `row.license_allows_display or row.license_flag`. `patterns/read_model.py` calculates the internal-use flag but its `display_only` filter ignores it. `composition/router.py` and `composition/service.py` do not pass the runtime internal-use policy to the pattern read service. The client pattern-version list has the same missing propagation in `patterns/router.py` and `patterns/service.py`.

## Phase

- [x] Phase 1: [Align eligibility and verify the complete flow](phase-01-internal-use-rendering.md)
- [x] Phase 2: [Filter Phrasebank before result limits](phase-02-phrasebank-filtering.md)

Deferred follow-up: [Canonical JSON import discovery](phase-03-canonical-import-discovery.md). The user explicitly deferred this work because the teammate's context and filename are unknown. It is not an active implementation phase or a blocker for phases 1–2.

## Acceptance criteria

1. An approved, current mined phrase with one source, `allows_display=false`, and a configured internal-use license appears in recommendations and client pattern reads and successfully renders using a recommendation issued to that client.
2. An otherwise identical phrase with no display permission and no configured internal-use permission remains excluded and cannot render.
3. Displayable mined phrases and authored phrases retain existing behavior. Approval/current-version/provenance/client-ownership checks still reject invalid cases.
4. All affected routes use the runtime policy bundle rather than hard-coded license names or a service-local policy reload.
5. README explains the decision using the rationale: “The entire app is for internal use.”
6. A matching AP-RKB phrase beyond the first 200 unfiltered patterns and a Manchester phrase beyond the first 50 unfiltered query hits appear when their section/intent filters are selected. Keyword, section, and intent predicates combine before limits.
7. Filter changes refetch with distinct query keys, and the UI clearly states that results are capped.

## Validation and handoff

Run focused read-model, composition, recommendation, and reference-library tests plus PostgreSQL regressions for recommend → detail → render and filtering beyond the old caps. If the isolated database is unavailable, report that limitation. Phase 2 adds optional query parameters: regenerate OpenAPI and frontend types while preserving existing unrelated contract edits. Execute phases 1–2 only; import-flow work remains deferred.

Implementation command: `$bb-cook --fast plans/2026-11-04-internal-use-rendering/plan.md`. Even with fast workflow, run the focused regression checks above before claiming the change works.

## Scope exclusions

No full pagination system, global permission bypass, new licensing schema, UI licensing-notice system, deployment, commit, or push is included. Existing output caps remain but apply after filtering and are disclosed. Preserve unrelated uncommitted work. Do not consolidate all database ingress paths until phase 3 scope is confirmed.

## Verification evidence

- Backend unit suites (patterns, composition, recommendation, reference library, policies): 167 passed. Reference service fixture correction rechecked: 4 passed.
- PostgreSQL API suites on isolated `aprkb_test` schemas: 31 pattern/render tests passed; 3 reference-library tests passed. Includes internal-use recommendation → reads → render, revoked permission rejection, and matches beyond the old 200/50 limits.
- Phrasebank browser suite using installed Edge: 9 passed. Screenshot output now uses the portable `test-results/phrasebank-screens` path.
- Web production build and typecheck passed. ESLint: no errors, one existing `OnlineWriterPage.tsx` hook dependency warning. Ruff checks and formatting passed; code review found no actionable runtime defects.
- Generated OpenAPI and frontend types include the optional browsing query parameters.

## Session Notes

**Last active:** 2026-11-04 (Asia/Bangkok)
**Phase in progress:** none
**Status:** Both authorized fixes implemented and verified; changes remain uncommitted.

### Decisions made this session

- Internal-use exceptions remain explicit license codes; public-display metadata stays truthful.
- Search and mapping predicates run before existing output caps; no full pagination feature was added.
- The ambiguous canonical JSON import request remains deferred by the user.

### Next immediate action

No implementation work remains for phases 1–2. Await user direction for commit/push or the deferred import-flow discussion.
