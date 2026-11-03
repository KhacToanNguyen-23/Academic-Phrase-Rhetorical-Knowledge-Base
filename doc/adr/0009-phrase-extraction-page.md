# ADR-0009: Phrase extraction page and approved phrase store

Status: Accepted by owner on 2026-11-02 for the internal tool.

## Context

AP-RKB is an internal tool. A base phrasebank supplies generic phrases; corpus mining exists to find phrases a particular journal uses, as input for a later journal fingerprint (`TODO(owner, FR-07.6)`). Until now a curator had to queue mining per article through the API and review candidates through `/v1/admin/review-queue`, which has no UI, needs two review rounds, and cannot promote a candidate without an intent that mining does not assign.

## Decision

- Add an `/extract` page. After an import run finishes, the Import page links to it. A **batch is one import run**: `articles.import_batch_id` holds the id of the first import job and continuation jobs inherit it. Older articles have no batch and appear as "Không thuộc batch".
- The page can select several batches, queue mining for the selection (`POST /v1/admin/corpus/mine`, built on the existing idempotent `enqueue_mining`), open each article's text, and list the mined phrases next to the articles.
- **One reviewer** accepts or rejects each phrase. Accepting inserts an append-only row into `approved_phrases` (frame, slots, source sentence ids, article, journal if known) and sets the candidate to `accepted`. It does **not** create a `PhrasePattern`, so it needs no intent and does not reach the Library or recommendations. Rejecting sets the candidate to `rejected`.
- The existing two-round review (`/v1/admin/review-queue`) is unchanged and still the only path that creates patterns. Candidates accepted on the new page leave that queue because they are no longer `pending`.

## Safety

- Mining rights are rechecked at decision time: every source sentence must exist and belong to an article whose license allows mining; otherwise accepting returns 409. The article text and phrase sources are returned only for mining-licensed articles.
- Slot schema and masked-frame safety use the same checks as the review service. Rejecting stays possible for blocked phrases.
- Decisions are audited in the same transaction. Audit snapshots hold ids and statuses, never sentence text.
- Roles: reading and deciding need `reviewer`; queueing mining needs `curator`.

## Limits

- This replaces the two-reviewer protocol for mined phrases by owner choice; it gives no inter-reviewer agreement.
- Mining still extracts only the rule-based reporting-verb frame (ADR-0007), so few phrases appear until the phrase segmenter and parser-based slot extraction exist.
- `journal_id` is null for articles imported before journal mapping exists, so `approved_phrases.journal_id` is nullable.
- Per-article phrase counts treat a candidate as belonging to every article that contributed a source sentence.
