# Runtime policies

`evidence_matrix.yaml` and `lexicon/epistemic_markers.yaml` are the backend's
single runtime sources for the MVP evidence check:

- The matrix maps a claim type and declared evidence level to the maximum
  permitted claim strength. Missing cells use `default_max_strength: low`;
  unknown claim/evidence codes fail closed.
- The lexicon maps wording in a sentence to a claim-strength level for V02.
- The seeded `RefEnum` order defines how strengths compare. Do not duplicate
  ordering or matrix comparisons in a gate, scorer, API route, or UI.
- `EvidencePolicy` is the shared comparison implementation. Both the
  recommendation `EvidenceGate` and validation rule V02 must call it.

This MVP configuration follows `SCAFFOLD_PRD.md` §4.6 and §8. The scaffold
labels the matrix and lexicon provisional and leaves claim types/cells for
domain review. The files are therefore runtime configuration, not final
scientific guidance.

`EVIDENCE_CONTRACT.md` is a broader, unapproved proposal. It is not loaded by
the application and must not be treated as a second runtime policy. If the
group approves it later, migrate the approved decisions into the versioned
runtime files and update their consumers together.
