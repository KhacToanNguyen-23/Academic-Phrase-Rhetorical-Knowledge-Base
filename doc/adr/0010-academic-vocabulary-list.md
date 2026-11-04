# ADR-0010: Academic Vocabulary List module

Status: Accepted for the internal tool.

## Context

AP-RKB needs a searchable Academic Vocabulary List (AVL) sourced from the Gardner & Davies AVL 2013 and COCA Academic workbooks. The source workbooks are copyrighted and must remain outside the repository.

## Decision

- AVL is an independent `vocabulary` module. It has no foreign keys to phrase/mining tables and does not import their services.
- Curators import `.xlsx` files through the CLI or `/v1/admin/vocabulary/imports`; the dictionary is read through `/v1/vocabulary/*`.
- The natural key is `(word, pos)`. Imports upsert source-owned columns and never delete lemmas missing from a later workbook.
- Reference data lives in PostgreSQL after a user import, not in YAML. This does not violate the repository convention that mining lexicons live in YAML; the AVL YAML only describes workbook columns, labels, and provisional mappings.
- `VocabLemma` stores the shared lemma identity. `all_words`, `acad_core`, and `families` own different columns so import order does not erase information from another source.

## Copyright and source handling

Gardner & Davies and COCA workbooks are not committed, seeded, or copied into tests. Tests build small self-authored workbooks with `openpyxl`. Real files are read read-only from the external data directory.

## Open TODO(owner) decisions

- Confirm the source meanings of status codes `c` and `y1`.
- Confirm the meanings of PoS codes `u`, `x`, `t`, and `e`.
- Confirm the `Rel → PHIL` and `Fin → BUS` family-domain mappings.
