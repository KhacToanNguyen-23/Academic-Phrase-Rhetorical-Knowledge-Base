# Seed data

These development seeds are deliberately small and self-authored:

- `reference_enums.json`: evidence, epistemic strength, claim type, roles, and sample license enums.
- `taxonomy.json`: a published `0.1.0` draft with INTRO and DISCUSSION paths. `TODO(owner)`: replace with the approved taxonomy.
- `patterns.json`: nine generic academic phrase frames covering approval, three claim-strength levels, provenance, and section gating. The authored frames include low and moderate evidence-compatible examples for both current intents.

The backend command `python -m aprkb.seeds.load` loads these files in reference enum, taxonomy, then pattern order. It is safe to rerun. Do not add text copied from Academic Phrasebank or copyrighted corpora.
