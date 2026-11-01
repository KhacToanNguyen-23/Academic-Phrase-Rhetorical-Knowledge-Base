# Phase 05 — Runtime mining

Status: implemented; unit tests pass. PostgreSQL upload/ingest/mine integration awaits `TEST_DATABASE_URL` for `aprkb_test`.
Gate: G1 approved. Execute phases 04 → 05 → 06.

Regex-only sentence extraction with fixed conservative span policy, positional slots, protected wording and offsets. spaCy/NER deferred TODO(owner, FR-06.2).

Use TDD and self-authored fixtures. No new endpoints, pattern/version writes, raw source in public outputs/logs/audit, or fabricated classifier output. Verify offsets, tense/strength/ownership negative pairs, policy validity, and upload → ingest → mine integration.
