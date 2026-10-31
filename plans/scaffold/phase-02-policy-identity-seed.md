# Phase 02 - Policy, identity, audit and seed

Stories: P1 startup and access control; P2 interfaces. Dependencies: 01.

## Tasks

1. Place versioned YAML from PRD section 8 in the backend package. Validate all policy schemas with Pydantic at startup and reject invalid configuration. Implement EvidencePolicy using reference-enum ordering and the draft matrix, plus epistemic lexicon and cached guideline placeholder with TODO(owner).
2. Implement API key hashing, active client lookup, exact role hierarchy and require_role dependency. Provide admin bootstrap and key lifecycle, exposing plaintext only once, and never logging secrets.
3. Record audit events in the same transaction as data changes. Add request IDs and the standard error envelope; capture actor and before/after without secrets or full text.
4. Seed reference enums and licenses, published taxonomy, and approximately six self-authored patterns as specified in section 9. Ensure reruns do not create duplicates. Expose seed and bootstrap-key commands from root.

## Verification

- Unit test valid/invalid policies and evidence matrix; run seed twice and compare counts and stable identities.
- Integration test missing/invalid/inactive key yields 401, insufficient role 403, admin bootstrap, plaintext returned only once, and audit rollback with the data transaction.

## Review additions

- Audit successful state changes in the same transaction. Define and test separately how failed requests, 501 responses and read-only POSTs are treated; do not claim that a rolled-back transaction persists its audit event.
- Validate unknown reference enum values and empty active scorer weights explicitly; fail closed where authorization or evidence decisions are uncertain. Document the chosen API error.
