# Academic Vocabulary module

The vocabulary module imports copyrighted AVL/COCA workbooks into PostgreSQL and exposes a dictionary-style read API. Source workbooks stay outside Git.

## Tables

| Table | Purpose |
| --- | --- |
| `vocab_lemmas` | Normalized `(word, pos)` identity and source-owned summary fields |
| `vocab_lemma_domain_stats` | Frequency and relative ratio for the nine academic domains |
| `vocab_families` | Word-family aggregate data |
| `vocab_family_members` | Family-to-lemma membership, frequency, category, and domains |
| `vocab_import_runs` | Counts, hash, filename, and bounded parser warnings for each import |

## Sources and commands

The supported sources are `all_words`, `acad_core`, and `families`, described by `policies/vocabulary_import.yaml`. Import with:

```powershell
make vocab-import FILES="D:/6_OJT/allWords.xlsx D:/6_OJT/acadCore.xlsx D:/6_OJT/families.xlsx"
```

The API upload requires `curator` or `admin`. The public dictionary requires `client` or a higher role.

Import `inserted`/`updated` values are aggregate persistence counts for the selected source, including
related rows (domain statistics for `acad_core`, and families/lemmas/members for `families`).

## Endpoints

- `GET /v1/vocabulary/lemmas`
- `GET /v1/vocabulary/letters`
- `GET /v1/vocabulary/lemmas/{lemma_id}`
- `POST /v1/admin/vocabulary/imports`
- `GET /v1/admin/vocabulary/imports`
