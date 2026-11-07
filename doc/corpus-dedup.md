# Corpus / SLR import duplicate detection

Scope: external corpus imports and the manual corpus upload API. Journals are unchanged.

## Decisions

1. Match `(source, external_id)` or normalized DOI against the entire corpus before
   downloading content. Match all ingest states, including pending and failed.
2. Normalize DOI by trimming whitespace, decoding URL escapes, removing the DOI
   resolver URL or `doi:` prefix, and lowercasing. Preserve suffix punctuation.
   Invalid/missing DOI values do not become identity keys.
3. After download, compare SHA-256 of the exact file bytes before storing a blob,
   creating an article, or enqueueing ingestion. Manual uploads use the same checks.
4. Normalized titles are review hints only: Unicode normalization, case folding,
   punctuation/whitespace normalization, then an indexed hash of the normalized title.
   A matching title with different bytes is still imported and reported for review.
   This deliberately replaces the previous automatic rejection on title alone.
   No fuzzy matching or automatic version merging is performed.
5. Import results and the page audit event include `duplicates` and
   `suspected_duplicates`, with reason, incoming title/ID, existing article ID,
   title, source and ingest status. SLR Import displays these details per page;
   continuation jobs retain their own results, accessible through the existing button.
6. Duplicate uploads return HTTP 409 with `error.details.code=duplicate_article`
   and the same match evidence. Optional multipart `doi` identifies uploaded papers
   across sources. No new blob or ingestion job is created on rejection.

If an existing article failed ingestion, retain that article and retry its ingestion
job through the existing operational procedure; importing again never creates a copy.
This change does not add a retry control or silently retry old jobs.

## Migration and existing data

Run `python -m alembic upgrade head` from `apps/backend` before starting the new API
and workers. Migration `0011_corpus_dedup` backfills DOI/title keys, preserves raw
metadata and every existing record, and creates non-unique indexes so legacy
duplicates do not prevent deployment. It does not merge or delete old duplicates.

Old file hashes are populated lazily from the configured blob store on a content
check. The first successful write can therefore read many old files. Missing blobs
are logged and skipped; they cannot establish a file match. A rejected upload rolls
back its lazy backfill too. Byte hashes alone do not identify equivalent renditions. PDF imports now additionally
check full extracted-text identity; see [PDF import](pdf-import.md). Edited text,
PDF/Markdown renditions without a common DOI, or missing blobs still require review.

A PostgreSQL transaction advisory lock serializes corpus import pages and uploads,
covering check, legacy hash backfill and insertion. This trades parallel import
throughput for a consistent lock order and prevents concurrent API/worker writes
from inserting copies. All API/worker processes must run this version; direct SQL
or other writers bypassing these checks are outside this guarantee. Existing raw
DOI and source-ID unique constraints remain in place.

## Verification

Regression coverage includes DOI variants across sources, failed-ingest matches,
same-page and repeated imports, exact-file copies, duplicate uploads, legacy hash
backfill, title-only review hints, concurrent pages, invalid-fetch retry, migration
upgrade/downgrade with legacy duplicate DOI forms, and browser rendering of evidence.
