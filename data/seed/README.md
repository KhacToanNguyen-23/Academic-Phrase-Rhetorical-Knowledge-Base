# Seed data

These development seeds are deliberately small and self-authored:

- `reference_enums.json`: evidence, epistemic strength, claim type, roles, and sample license enums.
- `taxonomy.json`: the provisional `0.1.0` release with INTRO, METHODS, and DISCUSSION paths. The Methods starter paths follow the approved RMB taxonomy; remaining compatibility rules need taxonomy-owner review (`TODO(owner)`).
- `patterns.json`: nine generic academic phrase frames covering approval, three claim-strength levels, provenance, and section gating. The authored frames include low and moderate evidence-compatible examples for both current intents.
- `academic_phrases.json`: APB phrase seed records with explicit section/category mappings. Each category mapping must also provide an `intent_code` that already exists under that section in `taxonomy.json`; seeding fails closed when no such Intent exists.

The backend command `python -m aprkb.seeds.load` loads these files in reference enum, taxonomy, catalog, then content order. It is safe to rerun. Production reference initialization deliberately does not load authored phrase content; promote these records later through a reviewed, versioned production data release after the taxonomy owner confirms the taxonomy release and the data owner confirms authorship and rights.
