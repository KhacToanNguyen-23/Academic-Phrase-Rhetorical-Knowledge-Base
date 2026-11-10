# Seed data

These development seeds are deliberately small and self-authored:

- `reference_enums.json`: evidence, epistemic strength, claim type, roles, and sample license enums.
- `taxonomy.json`: a published `0.1.0` draft with self-authored genre/section compatibility and INTRO/DISCUSSION paths. The Online initializer additionally publishes release `0.2.0` = this file plus the Methods move generated from `apps/backend/src/aprkb/seeds/phrasebank_basic.json`. Compatibility needs taxonomy-owner review (`TODO(owner)`).
- `patterns.json`: legacy development fixtures. `run_seed` no longer loads them; Phrasebank Basic content comes from `apps/backend/src/aprkb/seeds/phrasebank_basic.json`. They remain importable through the `pattern_seed` field of the `init-phrasebank` manifest.
- `academic_phrases.json`: APB phrase seed records with explicit section/category mappings. Each category mapping must provide an `intent_code` that already exists in the `0.2.0` Online taxonomy (the `METHODS_*` intents generated from Phrasebank Basic); seeding fails closed when no such Intent exists.
- `academic_phrase_facets.json`: DEV MOCK stance/register/domain labels for the APB filters (`TODO(owner)`); applied only by `run_seed`, never to imported sources or production.

The backend command `python -m aprkb.seeds.load` loads these files in reference enum, taxonomy, catalog, then content order. It is safe to rerun. Production reference initialization deliberately does not load authored phrase content; promote these records later through a reviewed, versioned production data release after the taxonomy owner confirms the taxonomy release and the data owner confirms authorship and rights.
