# PDF import, duplicate checks and metadata

The Corpus Import page at `/import` supports local text-layer PDFs in addition
to SLR imports. Files are parsed locally by pypdf; no file is sent to an external
metadata/OCR service. Apply migration `0014_pdf_import` before deploying API and
worker from the same revision, and keep the normal worker running.

## User flow

1. Select a PDF and explicitly declare a supported mining license. Unknown or
   non-mining licenses do not permit preview/extraction.
2. Preview PDF properties, first-page DOI candidates, page count and duplicate
   evidence. Preview creates no blob, Article or Job.
3. Review/edit title, DOI, authors, publication year, journal, genre and source
   URL. Unknown bibliographic values stay blank. Author names use semicolons in
   the form; commas are not automatically interpreted as author separators.
4. Confirm the reviewed metadata and processing rights. Import repeats duplicate
   checks under the existing corpus transaction lock, including concurrent imports.
5. A queued ingest job creates sections/sentences with global character offsets
   and physical PDF page numbers. The extraction viewer shows the page number.
   `succeeded` means ready for extraction, not approved for canonical publishing.

PDF title/author properties are unverified suggestions. A DOI appearing on the
first page is not automatically selected: it might identify a cited paper.
PDF creation/modification dates are never used as publication dates. No journal,
genre, author list or license is invented from a filename or a source filter.
The selected journal/genre must exist in the local database.

## Duplicate policy

- Source ID and normalized DOI retain their existing shared import/upload checks.
- SHA-256 of file bytes catches the same file under a different filename.
- `pdf_text_sha256` catches identical complete extracted PDF text in differently
  packaged PDFs (for example, changed document properties). This applies to both
  SLR PDF import and manual PDF upload. Headings are included. Only NFC canonical
  Unicode normalization and whitespace folding are applied: case, numbers,
  exponents and punctuation are preserved.
- Normalized title matches remain review hints. They do not automatically merge
  papers, overwrite original metadata, or combine provenance.
- Confirmed upload duplicates return 409 with `duplicate_article`, the matching
  article ID/status and reason (`doi`, `file_sha256`, `pdf_text_sha256`). They
  create neither a second blob nor a second ingest job. Use the existing article
  and inspect its job if ingestion previously failed.
- This is exact text identity, not semantic/fuzzy duplication. Edited text,
  OCR variants or PDF/Markdown renditions without a common DOI can still need
  human review. A shared DOI remains the existing work-identity policy; this
  change does not introduce automatic edition merging or multi-artifact work graphs.

Existing PDFs receive text fingerprints lazily under the same corpus lock when
an allowed import/preview encounters them. Unreadable/missing legacy blobs are
skipped with metadata-only warnings. The first check can read many old files;
preview and rejected uploads roll back their lazy backfills. No historical
metadata is silently rewritten from extracted PDF properties.

## Metadata stored

| Fields | Origin and validation |
|---|---|
| title, DOI | Reviewed title required; DOI optional, syntax-checked and normalized |
| authors | Reviewed list, bounded names; no automatic splitting on commas |
| publication_year | Optional reviewed integer, 1000–3000; not a PDF creation date |
| journal_id, genre_id | Optional IDs validated against local reference records |
| source_url | Optional HTTP(S) URL, recorded only; never fetched automatically |
| byte/text hashes | Server-computed identity keys, not editable in metadata JSON |
| page_count, parser_version | Server-computed extraction provenance |
| metadata_provenance | Original suggestions, confirmed fields, reviewer ID/time and method |
| ArticleSection.page_number | Physical page number for each extracted section |

`GET /v1/admin/corpus/articles/{id}/metadata` exposes the stored reviewed metadata
to curator/admin clients. This release supports review before import; it does
not add unrestricted metadata editing, DOI enrichment from OpenAlex/Crossref or
backfill missing SLR author/year/journal metadata from import filters.

## API

- `POST /v1/admin/corpus/pdf/preview`: multipart `file`, `license_code`.
- `POST /v1/admin/corpus/articles`: multipart PDF `file`, `license_code`,
  `metadata_reviewed=true`, `metadata_json` containing:

```json
{
  "title": "Reviewed paper title",
  "doi": "10.1234/example",
  "authors": ["First Author", "Second Author"],
  "publication_year": 2026,
  "journal_id": null,
  "genre_id": null,
  "source_url": null
}
```

The existing title/DOI multipart fields still work for non-PDF formats. PDF
clients must supply reviewed metadata; conflicting duplicate field values are
rejected. PDF bytes disguised with a text extension are rejected. PDFs have
a bounded read; defaults are 50 MiB upload size, 300 pages, 2,000,000 extracted characters and a
20 MiB decompressed content stream per page. Override `PDF_MAX_UPLOAD_BYTES`,
`PDF_MAX_PAGES`, `PDF_MAX_TEXT_CHARS`, `PDF_MAX_PAGE_STREAM_BYTES` as needed.

## Parser limits and rollout

Image-only/scanned pages need OCR first (`pdf_ocr_required`). Encrypted PDFs need
an unencrypted permitted copy (`pdf_encrypted`). Malformed PDFs and parser limits
return actionable 422 errors; upload size returns 413. These errors create no
new document/job through the manual upload flow. Blank separator pages are
allowed and do not renumber later page references. Low-text pages produce a
preview warning rather than an invented confidence score.

Text-layer reading and common heading segmentation are heuristic. Multi-column
ordering, equations, complex layouts and section confidence still need corpus
QC. This is not a TEI/GROBID implementation; XML/JATS remains a separate stub.
See [pypdf text-extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

Migration adds nullable provenance fields plus empty JSON defaults; it does not
delete existing records. Downgrade drops the new PDF metadata/page fields, so
prefer a forward fix once reviewed metadata exists. Drain API/worker writers
before schema rollback. Blobs remain under the same opaque `articles/` keys in
`BLOB_DIR`; duplicate rejection compensates newly written blobs as before.

## Verification

Backend tests generate self-authored text/image-only/encrypted PDF fixtures and
use isolated PostgreSQL schemas. Coverage includes full ingest, page offsets,
metadata review, creation-date exclusion, byte/text/DOI duplicates, changed
scientific text, concurrent uploads, legacy backfill, title hints, SLR/upload
cross-dedup, rights rejection, invalid metadata and resource limits.

The live browser fixture supports `PDF_IMPORT_LIVE=1`: it runs the real worker
against its isolated schema and disposable blob directory. Start
`scripts/manual/online_ranking_live_server.py` with that flag, point Vite at port
8016, and run `playwright test --config=playwright.full.config.ts e2e/pdf-import.spec.ts`
with the same flag. CI enables it and rejects skipped E2E tests.
