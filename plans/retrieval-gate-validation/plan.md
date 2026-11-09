# Retrieval, gates and validation

Date: 2026-11-05
Mode: scoped
Risk: normal — read-path optimization and additive warnings; no schema or policy changes.
Status: scoped implementation verified; Evidence decision, pg_trgm and optional cache deferred.

## Scope and document alignment

- Task 2.1: retrieve only approved recommendation candidates and push genre eligibility into SQL. Preserve ApprovalGate and RetiredGate, all other gates, and final recommendation items.
- Task 2.2: group sources, variants and affinities by `pattern_version_id`, preserving existing query order and every PatternRead field.
- Task 2.3: characterize missing labels across EvidenceGate, EvidenceScorer and V02; report contradictions without changing Evidence policy.
- Task 2.4: add the two requested Vietnamese warnings without new request/response fields.
- Task 2.5: excluded by user; no pg_trgm migration, threshold or retrieval change.
- Task 2.6: optional measurement only if feasible; no cache without measured cost and a supported policy-version invalidation contract.

`SCAFFOLD_PRD.md` §§4.3–4.6 documents the existing pattern/version/usage entities and RefEnum ordering. §§5–6 require preloaded read-only views, gates before ranking, and shared EvidencePolicy for gate/V02. Scorer `None` means unavailable and is deliberately omitted from score aggregation. BR-01 remains enforced by ApprovalGate even after SQL filtering.

`EVIDENCE_CONTRACT.md` explicitly labels itself an unapproved proposal, not runtime policy. Do not implement its proposed fields, missing-evidence cap, missing-claim defaults, or severity rules. Runtime YAML and seeded reference enums remain authoritative.

No AGENTS.md was found in the repository or checked ancestor paths. Apply existing repository rules: YAGNI, KISS, deterministic results, verification before completion.

## Phases

- [x] 1. Establish baseline: inspect schema, migrations, docs and consumers; capture original recommendation items/read-model output and 5,000-pattern read-model timing with a temporary benchmark.
- [x] 2. Group read-model associations once by version UUID. Verify complete output equivalence, grouping isolation, missing groups, multi-source behavior and ordered child lists. Record temporary benchmark method and before/after timing in the final report.
- [x] 3. Pass `status="approved"` and optional genre through recommendation repository. JSONB eligibility is allowed genres containing the requested genre, `[]`, or SQL NULL (including an absent outer-joined usage row). Handle legacy JSON null consistently if encountered without making schema nullable. Preserve other read-model callers. Test real PostgreSQL candidate-count reduction and item equivalence against the previous Python genre predicate.
- [x] 4. Add missing-context and missing-section warnings. Test absent/empty context, normalized blank query, and fully supplied requests through API integration tests.
- [x] 5. Add policy-consistency characterization tests for both missing labels, with/without request claim/evidence and marker/no-marker text. V02 accepts textual claim/evidence context rather than pattern labels: distinguish this input difference explicitly. If a genuine same-context mismatch appears, record a failing reproduction and owner decision needed; do not adjust policy.
- [x] 6. Run targeted and broader relevant tests, lint/type checks, and independent code review; document skipped requirements, unavailable DB tests and remaining policy questions.

## Risks and acceptance notes

- `UsageConstraint.allowed_genres` is JSONB, declared NOT NULL in migration 0001 and modeled as `list[str]`; missing outer-joined usage produces SQL NULL. Do not add fields or loosen schema nullability merely to test SQL NULL behavior.
- Filtering status before gates removes draft/retired exclusion telemetry. API integration currently expects positive GATE_APPROVAL and must change with an explanatory comment. Direct pipeline gate tests must stay intact. `WriterResults.tsx` currently displays only GATE_EVIDENCE, so its displayed hidden count should not change.
- Group by version UUID, never pattern UUID. Preserve ordered source lists because exactly one provenance determines display/license mappings; multiple sources must retain existing fail-closed handling.
- Missing labels are currently represented as None in read views; do not infer labels, defaults or scores from an unapproved proposal. Gate rejection and scorer None are compatible with the documented unavailable-score contract; V02 may differ for marker-free text because it inspects text rather than metadata.
- Requested no-context warning says all approved patterns, but remaining filters/gates and limit can still reduce returned items. Use the exact requested wording and document this limitation instead of changing retrieval semantics.
- PostgreSQL acceptance uses only dedicated aprkb_test isolated-schema fixtures. If not available, explicitly report tests skipped rather than claiming DB behavior verified.
- No automatic schema cleanup: report questionable/unconsumed fields with evidence before proposing deletion.

