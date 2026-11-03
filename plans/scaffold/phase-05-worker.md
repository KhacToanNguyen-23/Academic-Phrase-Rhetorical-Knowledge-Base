# Phase 05 - Ingestion and worker

Stories: P1 upload to candidate. Dependencies: 01-04.

## Tasks

1. Implement local BlobStore with safe keys, minimal text parser, JATS/PDF parser stubs as scoped, regex sentence splitter preserving offsets, and section detector stub with requirement ID.
2. Upload persists blob, article and ingest job and returns 202; mine endpoint enqueues a mine job after appropriate ingestion readiness. Check license before processing and persist rejection reason; never log complete article text.
3. Implement PostgreSQL polling with SELECT FOR UPDATE SKIP LOCKED, claim/commit/attempt/status/error handling and explicit stale-lock recovery and idempotency to prevent duplicate candidates. Remove Redis/Celery runtime dependency. Ingest and mine handlers use service/module ports.
4. Candidate writer requires source_sentence_ids and writes pending candidates only; mining does not write phrase_patterns or pattern_versions.

## Verification

- Test original text offsets, license refusal and missing source IDs; two workers cannot claim the same job; failures are recorded without hanging transactions.
- Integration test upload .txt -> ingest -> mine -> at least one candidate with sources, with no new pattern/version; use a real worker and isolated PostgreSQL.

## Review additions

- Choose and test a deterministic response when mining is requested before ingest completes (for example 409); this is an implementation decision, not a PRD requirement.
- Keep locking and recovery to the minimum needed for safe polling; document any stale-lock recovery and retry decisions without inventing a business retry policy.
