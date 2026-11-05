# Seed data

These development seeds are deliberately small and self-authored:

- `reference_enums.json`: evidence, epistemic strength, claim type, roles, and sample license enums.
- `taxonomy.json`: a published `0.1.0` draft with self-authored genre/section compatibility and INTRO/DISCUSSION paths. Compatibility needs taxonomy-owner review (`TODO(owner)`).
- `patterns.json`: legacy development fixtures retained for reference only. The Online initializer no longer loads these patterns; Phrasebank Basic content comes exclusively from `apps/backend/src/aprkb/seeds/phrasebank_basic.json`.

The backend command `python -m aprkb.seeds.load` loads these files in reference enum, taxonomy, then pattern order. It is safe to rerun. Do not add text copied from Academic Phrasebank or copyrighted corpora.
