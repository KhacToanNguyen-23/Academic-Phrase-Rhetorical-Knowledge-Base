# Internal reference library

This module stores a read-only external reference collection in dedicated tables. It does not connect to `phrase_patterns`, mining, recommendation, rendering, or validation. The API is hidden unless `REFERENCE_LIBRARY_ENABLED=true`; import and purge remain CLI-only.

The importer validates structure, hashes the input bytes, replaces a source by name in one transaction, and writes counts and the hash to audit without source text. Source categories are classified by `categories.yaml`; unmatched titles are functions. Keep the source notice visible and preserve the captured order of pages, headings, entries, and phrase rows.

The Alembic revision `0006_reference_library` currently follows `0005_candidate_occurrences`. Re-point `down_revision` to the merged migration head when integrating concurrent migration branches.
