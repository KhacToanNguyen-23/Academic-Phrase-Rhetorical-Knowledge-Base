# Phase 06 - Integration and handoff

Stories: all P1/P2. Dependencies: 01-05.

## Tasks

1. Complete unit/integration tests in PRD section 10, isolated fixtures and 12 acceptance files AT-01 through AT-12. Acceptance cases already covered reuse test logic; incomplete cases remain skipped with TODO(owner), without inventing original acceptance criteria.
2. Complete root Makefile up/down/install/migrate/seed/bootstrap-key/run/worker/test/lint, admin-console README, eval stub/sample, and root/backend READMEs. Update outdated instructions and include the PRD appendix A traceability table.
3. Check that each stub has TODO plus requirement ID, no business weights/thresholds/lexicon are hard-coded, no secrets/full text are logged, and every required endpoint is documented.
4. Run the section 12 DoD from a clean environment: make up, install, migrate, seed, bootstrap-key, lint, test, run; verify /docs, recommendations, validation, and upload -> worker -> candidate. Record actual environment and results; do not delete existing data to simulate cleanliness.

## Verification

- All DoD commands exit successfully, unit/integration pass, and only unimplemented acceptance tests skip; tests do not depend on old seeded state.
- Read actual outputs, inspect the diff and check each section 12 criterion. Report missing verification if Docker, tools or environment are unavailable.

## Review additions

- Exercise PostgreSQL-dependent health, migration, repeated seed, key/RBAC, atomic audit, recommendation, job locking, and upload-to-candidate integration tests. Unskip acceptance cases already covered by the required integration logic; leave unfinished acceptance cases skipped with their required TODO.
