# Academic Phrase Bank

This module exposes APB metadata attached to the current immutable `PatternVersion`. It does not replace the existing `Section -> Move -> Step -> Intent` taxonomy: APB Communicative Functions are a separate, versioned facet.

## Read endpoints

- `GET /v1/academic-phrases/functions`
- `GET /v1/academic-phrases/pragmatic-features`
- `GET /v1/academic-phrases/domains` (versioned options from the vocabulary import policy)
- `GET /v1/academic-phrases` with optional `q`, `function`/`function_version`, `section`, `move`, `step`, `intent`, `genre`, `register`/`register_version`, `domain`, `stance`/`stance_version`, `pragmatic`/`pragmatic_version`, `limit`, and `offset`
- `GET /v1/academic-phrases/{pattern_id}`

Public reads require an approved, currently eligible pattern and a reviewed function link. Curators can inspect linked patterns before review. Combined filters run in the database before pagination. Taxonomy inputs resolve against the current published DB release; clients use codes and labels returned by the APIs, never hard-coded UUIDs.

## Curator metadata write

`POST /v1/admin/academic-phrases/versions/{version_id}/metadata` accepts one metadata envelope for the current version. It requires at least one known Communicative Function and validates supplied Section/Move/Step/genre/register/license references against DB records. Domain codes resolve against `vocabulary_import.yaml`; those codes are provisional and versioned by that policy. Function, pragmatic, and register codes carry versions so reused codes cannot resolve ambiguously. Function links created by this curator action are marked reviewed. A version with existing APB metadata is immutable; create a new pattern version and re-review its APB metadata instead of overwriting the old record.

Examples may be internal original, illustrative synthetic, or licensed. Licensed examples require a source reference and a license that permits display; internal-use-only examples are rejected and never returned to clients. Read responses include the example license code and display permission. Audit events record codes and counts, never example text.

## Reference data and integrations

The versioned function/pragmatic catalog is defined in `apps/backend/src/aprkb/policies/academic_phrase_bank.yaml` and seeded by `init-reference` / the development seed. The initial function catalog remains proposed pending curation. The development seed includes 32 user-authored Methods templates with explicit function and Intent mappings; their draft status keeps them out of public client results until review. No Manchester content is copied into this seed.

VTB Concept/Sense links are deferred until VTB publishes stable identifiers. Offline pack v0.1 remains unchanged; pack v0.2 carries APB labels as proposed annotations in a separate proposal record and never promotes them to reviewed APB metadata on import. See [`doc/academic-phrase-bank-contract.md`](../../../../../../doc/academic-phrase-bank-contract.md) for field mapping and compatibility decisions.
