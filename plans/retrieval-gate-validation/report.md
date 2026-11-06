# Retrieval, gates and validation implementation report

Date: 2026-11-05

## Scope and data contract

Tasks 2.1, 2.2 and 2.4 implemented. Task 2.3 adds characterization and an owner-decision reproduction; runtime Evidence behavior is unchanged. Task 2.5 is excluded at the user's request. Task 2.6 was measured; caching remains optional and deferred.

Source of truth: `SCAFFOLD_PRD.md` §§4.3–4.6 and §6, packaged runtime YAML and seeded RefEnum order. `EVIDENCE_CONTRACT.md` explicitly states that its proposed matrix/defaults are unapproved. No proposed fields, defaults or mappings were introduced.

`UsageConstraint.allowed_genres` is JSONB NOT NULL in the existing migration. The outer join can still produce SQL NULL when there is no usage row. SQL eligibility accepts that case, `[]`, or JSONB containment of the requested genre. No column, migration, request field or response field was added. All three child associations remain keyed by pattern **version** UUID, preserving query order and existing provenance/license mapping. Full read-model snapshots cover every dataclass field, including internal `provenance_count`; this internal count is intentionally not a new response field. No schema field was identified for deletion in this scoped change.

## Observable behavior

- Recommendation repository requests approved rows and optional genre eligibility in SQL. Existing approval/retired and other gates remain intact. Integration compares candidate reads against the prior status/genre predicates and compares optimized API items with the previous retrieval behavior.
- Draft/retired rows no longer reach pipeline exclusion counters. The changed integration expectation documents why `GATE_APPROVAL` is zero. Direct pipeline gate tests retain their rejection-count assertions. `apps/web/src/features/playground/components/WriterResults.tsx` consumes only `GATE_EVIDENCE`, so its displayed hidden count is unaffected by the approval telemetry change.
- The two requested Vietnamese warnings are returned and logged in the existing warnings list. Blank intent/move/section values normalize to absent values so SQL, gates and warnings agree. Query already strips whitespace. The broad-context warning does not override other filters, gates or limit.

## Task 2.3: owner decision required

Both stored labels are absent (`epistemic_strength=None`, `claim_type=None`). Observed runtime behavior:

| Request/text context | EvidenceGate | EvidenceScorer | V02 |
|---|---|---|---|
| No request claim or evidence; text has `suggest` | pass (evidence filtering disabled) | None | BLOCK |
| No request claim; `single_study`; text has `suggest` | reject | None | BLOCK |
| Request claim `causal`; `single_study`; text has `suggest` | reject (missing stored strength) | None | PASS |
| No request claim; `single_study`; text `A relationship was observed.` | reject | None | PASS (no marker found) |

`None` is the documented unavailable scorer signal, not zero or an exception. Gate checks stored labels; V02 infers marker strength from text and passes marker-free text. These input differences explain the implementation behavior but do not resolve the requested BR-03 consistency decision. No labels were inferred or policy changed.

Local issue reproduction: `tests/unit/test_policy_consistency.py::test_unlabelled_marker_free_gate_and_v02_agree`, marked `xfail(strict=True, raises=AssertionError)` pending owner decision. It will XPASS-fail when the behavior changes, requiring review of the expectation. From `apps/backend`, run:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_policy_consistency.py::test_unlabelled_marker_free_gate_and_v02_agree --runxfail -q
```

Verified outcome: one deliberate failure, `False == (Severity.PASS == Severity.PASS)`. Eight ordinary characterization cases pass. Owner must decide how unlabelled patterns, absent request evidence and marker-free validation should relate; this report records the issue locally, without opening an external issue.

## Temporary benchmark (Task 2.2)

Windows, Python 3.13.16; 5,000 ORM pattern/version rows, one source, one variant and one affinity per version. The exact pre-change read model was loaded from Git HEAD and compared to the changed implementation. Both consumed identical preloaded/mock SQL results. Three paired runs; dataclass serialization/comparison is outside the timed interval. Entire serialized outputs were equal on every run. Temporary benchmark code is excluded from Git.

| Run | Before (seconds) | After (seconds) |
|---|---:|---:|
| 1 | 75.483216 | 0.309308 |
| 2 | 77.808598 | 0.176833 |
| 3 | 86.728644 | 0.185222 |
| Median | 77.808598 | 0.185222 |

This measures read-model assembly, not DB/network latency or production throughput. It is not a p95 retrieval measurement; Task 2.5 is excluded.

## Optional policy-cache measurement (Task 2.6)

Disposable local PostgreSQL, existing small seed, in-process ASGI HTTP requests including recommendation log/audit commit. One warm-up followed by 20 requests:

- Median total request: 30.308 ms.
- Median `reference_strengths`: 2.186 ms.
- Median `EvidencePolicy.from_reference_enums`: 0.0326 ms.
- Combined measured time / total measured request time: 7.259%.

The local small-seed measurement exceeds 5%, but does not establish benefit on realistic retrieval loads. No cache added: this task is optional, and TTL plus same-version RefEnum invalidation remain unspecified. Evidence matrix version alone does not distinguish RefEnum updates within that version. Preserve per-request freshness until that design is selected.

## Verification

- PostgreSQL: disposable `pgvector/pgvector:pg16`, loopback port 55439, database `aprkb_test`, fixture-managed isolated schemas. Existing database/container untouched.
- Targeted API/read-contract integration: 37 passed.
- Unit suite: 460 passed, 1 deliberate xfail.
- Ruff check and formatting: passed; mypy: no issues in 192 source files; `git diff --check`: passed.
- Full backend suite against disposable PostgreSQL: 544 passed, 8 skipped, 1 deliberate xfail in 120.51 seconds. The skips are existing TODO acceptance cases AT-03 and AT-06 through AT-12; no PostgreSQL tests were skipped for missing database access. Existing warnings concern the pack `register` field and Starlette deprecations.
- Independent final code review: prior blank-context inconsistency corrected; no remaining correctness blockers reported. Reviewer inspected the diff and relied on the test evidence above.

Full-suite command from repository root (with TEST_DATABASE_URL pointing to the disposable test instance):

```powershell
apps/backend/.venv/Scripts/python.exe -m pytest apps/backend/tests -q --basetemp=.pytest_cache/task2-full-temp
```

Sandboxed Windows asyncio hangs during its local socket-pair initialization; tests run with escalation. Shared system pytest temp permissions required a workspace-local `--basetemp`. These are execution-environment workarounds, not repository configuration changes.
