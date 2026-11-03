# ADR-0001: Modular monolith with PostgreSQL polling worker

- **Status:** Accepted for the scaffold
- **Date:** 2026-10-30
- **Supersedes:** the earlier Celery/Redis worker choice in this ADR

## Context

AP-RKB is small enough to keep its API and background processing in one Python package. The scaffold PRD chooses PostgreSQL as the database and job queue (D3), with local blob storage (D4). A Redis broker and Celery runtime would add services that the scaffold no longer needs.

## Decision

- Keep one Python package, `aprkb`, with the FastAPI API and a separate worker process.
- Keep domain code in `apps/backend/src/aprkb/modules/<domain>/` and route writes through module services.
- Persist jobs in PostgreSQL. Workers claim jobs with `SELECT ... FOR UPDATE SKIP LOCKED`, record attempts and status, and recover stale locks after a bounded lease.
- Keep successful job effects and terminal status in one transaction. A worker holds the job row lock while executing that transaction so stale recovery cannot run the same active job concurrently.
- Store uploaded blobs locally through the `BlobStore` interface at `BLOB_DIR`; default is `./data/blobs`.
- Do not add Redis, Celery, MinIO, or deployment infrastructure to the scaffold.

## Consequences

- The API and worker share schemas, models, and domain services without becoming separate deployable services.
- PostgreSQL is required for API persistence and background jobs.
- Text ingestion is available in the scaffold; JATS and PDF adapters remain explicit TODO stubs.
- If upload database persistence fails, the just-written blob is removed. If the worker crashes during a database transaction, the transaction rolls back; after the lease expires, another worker can reclaim the job.
- The worker currently treats handler errors as terminal and records a sanitized error; retry policy is not inferred from the original product requirements.

## References

- [Scaffold PRD](../../SCAFFOLD_PRD.md), decisions D3/D4 and section 6.3
- [Backend implementation](../../apps/backend/README.md)
- [PostgreSQL decision](0002-postgresql.md)
