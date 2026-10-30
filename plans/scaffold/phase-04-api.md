# Phase 04 - API and review

Stories: P1 recommendation/validation and permissions. Dependencies: 01-03.

## Tasks

1. Map every method/path/role in PRD section 7 into existing routers under /v1. Stop mounting routes outside scaffold scope while preserving old code where appropriate. Implement public /v1/health with DB check, response request IDs and standard errors.
2. Add request/response schemas and service/repository methods for taxonomy, patterns, journals, feedback, overrides, API keys, review queue and job status. Implement explicitly required behavior; only unimplemented endpoints return 501. Expose no update/delete pattern-version route.
3. Load PatternView once per recommendation request, execute pipeline, persist log and return PRD schema. Run validation pipeline and audit write requests transactionally, including recommendation log writes.
4. Record review decisions; only two rounds of approval permit creation of a version from a candidate. Protect against concurrent duplicate promotion; mining must never publish directly.

## Verification

- Compare OpenAPI against all routes in section 7. Verify 401/403, role hierarchy, request IDs and error format.
- Integration test recommendation seed excludes draft, retired and proprietary entries and returns breakdown and fallback tier; test validation, audit and route immutability.
- Test one approval does not create a version; two approvals do; rejection and concurrent decisions cannot bypass the two-round rule.

## Review additions

- Verify audit events for successful writes commit atomically with data changes; define behavior for rejected or 501 requests separately, and distinguish read-only POSTs from state changes.
