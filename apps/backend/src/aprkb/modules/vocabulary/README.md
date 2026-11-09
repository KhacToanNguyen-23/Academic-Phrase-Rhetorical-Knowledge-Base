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
- `GET /v1/vocabulary/filter-options`
- `GET /v1/vocabulary/lemmas/{lemma_id}`
- `POST /v1/admin/vocabulary/imports`
- `GET /v1/admin/vocabulary/imports`

## Research field filter

The Lemmas tab filters by the nine academic fields in the imported vocabulary.
A lemma matches when its stored domain tags include the selected field or its
relative usage ratio for that field is above 1.0. This combines with the other
lemma filters and uses data already in PostgreSQL.

## Local research field pilot

The original sampled-paper lookup remains available through the lemmas API for
clients that use `research_group`. The following setup builds local evidence for
that API.

1. Import the vocabulary and apply database migrations.
2. Select two contrasting fields, such as Computer Science and Medicine. Use the SLR
   import profiles to find papers and allow them to finish ingesting. Verify each
   paper's primary field and optional subfield against its OpenAlex or SLR metadata.
   Use comparable samples of English-language papers with mining permission.
3. Make a local JSON manifest containing one entry for each sampled paper. Use the
   local `articles.id` UUID and the numeric portions of the OpenAlex taxonomy IDs.
   The SLR importer does not store the taxonomy assignments on local article rows.
   Add at least two papers per group to make a match possible.

   ```json
   {
     "papers": [
       {
         "article_id": "00000000-0000-0000-0000-000000000001",
         "field_id": "17",
         "field_name": "Computer Science",
         "subfield_id": "1702",
         "subfield_name": "Artificial Intelligence"
       }
     ]
   }
   ```

4. Replace the example UUID, add the rest of the sample, and run this command from the
   repository root against the pilot database.

   ```powershell
   uv run --directory apps/backend python -m aprkb.cli build-vocabulary-research C:/path/pilot.json
   ```

The builder takes at most 1,000 papers across at least two fields. A match means the
exact, case-insensitive lemma spelling occurs in at least two papers in the group
and in a larger share of that group's papers than of the remaining sampled papers.
The builder skips spellings that have multiple part-of-speech entries. It counts
documents once per lemma, and the UI shows the numerator and sample size. The result
is specific to the supplied sample.

Each successful run replaces the prior pilot in a single transaction. The snapshot
contains group labels and aggregate counts. Keep the manifest locally for
reproducibility. Vocabulary browsing reads the snapshot from PostgreSQL.
