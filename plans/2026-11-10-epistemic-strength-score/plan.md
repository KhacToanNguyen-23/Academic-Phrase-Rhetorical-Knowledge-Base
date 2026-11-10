# Epistemic Strength Scoring Engine

Mode: fast --no-task
Risk: normal — changes deterministic mining classification and its policy-driven read-side result; no schema migration or external service.
Status: complete.

## Scope challenge

- Exists: the current `EpistemicTagger` uses policy-backed regex matching, but has no compositional score or dependency traversal.
- Minimum: add a typed scorer for spaCy `Doc`/`Span`, preserve four strength tiers, handle explicit refutation, and expose score/modifier diagnostics.
- Complexity: a focused mining feature with one scorer, tagger integration, tests, and docs.

## Plan

1. Implement `EpistemicScorer` with policy/lexical baselines, primary predicate selection, dependency modifier traversal, score calculation, deterministic tier thresholds, and structured diagnostics.
2. Integrate scoring into the existing epistemic mining stage while preserving offline behavior and the current `Candidate.epistemic_strength` contract. Do not change candidate database schema unless required by the owner's integration choice.
3. Add tests for the six supplied benchmarks plus copular predicates, modals, boosters, negation/refutation, no-marker fallback, deterministic modifier reporting, and missing dependencies.
4. Update versioned policy and mining documentation to explain the score, thresholds, diagnostics, and provisional owner-review items.
5. Run targeted epistemic tests, Ruff, mypy, and the full backend test suite; review the final diff manually.

## Owner decisions

- Possibility-modal conflict: owner chose to force category `low` when a possibility modal is detected; continuous score remains capped at `0.8`.
- Runtime integration: owner chose to keep spaCy optional; scoring runs only when a parsed `Doc`/`Span` is supplied. With no parsed input, strength remains null.

## Completion notes

- Implemented a deterministic policy-driven dependency scorer and mining-stage integration. The scorer reports a `negative_refuted` result separately; the tagger retains that in status and leaves the four-tier stored strength null.
- Updated mining documentation and scorer tests. The scorer's full-backend verification at the initial implementation stage passed (828 passed, 91 skipped).
- Review caught and corrected the `without doubt` classification so the phrase reaches `absolute` from the moderate `doubt` baseline.
- Worker integration now initializes the optional spaCy model and scorer once per worker process, scores sentence Docs before constructing `MiningItem`s, and supplies explicit fallback provenance when spaCy is unavailable. The optional `nlp` extra pins `en_core_web_sm` 3.8.0 and Docker can opt into it with `INSTALL_NLP=true`.
- Worker-integration verification: Ruff, mypy, and `uv lock --check` pass; focused worker/scorer tests passed (23 passed, 1 skipped for the project venv's absent optional model). The direct `SpacyEngine.parse()` path was also checked with the machine's global spaCy 3.8.18 / `en_core_web_sm` 3.8.0.

## Constraints

- Offline and deterministic; no network model download or external inference.
- Keep the exact `Doc`/`Span` scorer API and structured `EpistemicResult`.
- Keep four strength tiers; `negative_refuted` is a special outcome, not a fifth strength tier.
- No database migration unless a decision requires persisting additional output.
