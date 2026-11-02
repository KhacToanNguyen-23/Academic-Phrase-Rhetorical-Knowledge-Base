# Acceptance tests

`test_at_01_...py` through `test_at_12_...py` preserve the original PRD acceptance-case identifiers. AT-01, AT-02, AT-04, and AT-05 reuse the Phase 04/05 PostgreSQL integration tests because the scaffold covers those behaviors. The remaining cases stay skipped with `TODO(owner)` because their acceptance conditions are incomplete or the corresponding feature is outside scaffold scope.

| Case | Current scaffold coverage |
| --- | --- |
| AT-01 | Passing: approved/provenance filtering; proprietary internal-use items carry `license_flag` — recommendation integration |
| AT-02 | Passing: V02 blocks `proves` with `single_study` — Phase 04 validation integration |
| AT-03 | Skipped: journal-specific fallback constraints need more criteria |
| AT-04 | Passing: an article source outage fails the import job; local recommendations still answer — corpus import integration |
| AT-05 | Passing: a non-mining license rejects ingestion before extraction — Phase 05 integration |
| AT-06 | Skipped: full confirmed-guideline conflict handling is not covered |
| AT-07 | Skipped: novelty/literature evidence conditions need more criteria |
| AT-08 | Skipped: writer preview is outside backend scaffold scope |
| AT-09 | Skipped: approved-version editing acceptance is not fully covered |
| AT-10 | Skipped: journal genre fingerprinting is outside scaffold scope |
| AT-11 | Skipped: writer-facing provenance display is outside backend scaffold scope |
| AT-12 | Skipped: source role terminology and denial-audit behavior need clarification |

Run the complete acceptance collection with `make test` and a dedicated `TEST_DATABASE_URL` ending in `/aprkb_test`.
