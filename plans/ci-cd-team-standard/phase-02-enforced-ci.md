# Phase 02 — Enforced CI

## Goal

Make pull-request validation deterministic, complete, least-privileged, and enforceable without adding deployment behavior.

## Work

1. Refactor `.github/workflows/ci.yml` into stable, uniquely named checks with workflow/job timeouts and concurrency cancellation for superseded PR commits.
2. Preserve backend Python 3.12, locked `uv` install, OpenAPI drift check, Ruff, formatting, mypy, Alembic upgrade, and pytest against PostgreSQL `aprkb_test`.
3. Separate PostgreSQL integration collection from intentional incomplete/TODO skips. Add a dedicated marker or explicit test-path command for DB integration tests, first run `pytest --collect-only` to establish a non-zero expected DB test count, then run that set with `TEST_DATABASE_URL` and fail if any test in that DB-required set is skipped. Keep intentional TODO/optional-adapter skips in the broader suite with explicit reasons and report them separately.
4. Add blocking `pnpm lint` before frontend type-check/build. Resolve the known hooks warning or record a short-lived warning budget with owner/deadline; transition to zero warnings.
5. Keep frozen `pnpm-lock.yaml` installation and generated API schema drift check. Decide whether to remove the unused `package-lock.json` in a separate reviewed change so package-manager ambiguity cannot recur.
6. Stage Playwright adoption:
   - Stage A: run current specs in a non-blocking observability job, collect trace/screenshot only on failure, measure flakiness.
   - Stage B: identify minimal deterministic smoke tags/specs and make only those blocking.
   - Stage C: expand required coverage only when a candidate suite has at least 50 consecutive default-branch executions over at least 14 days with at least 99% pass rate and zero unexplained flakes. If its rolling 20-run pass rate drops below 95% or two unexplained flakes occur within 7 days, remove only that suite from required checks, open an owned incident, and keep the last stable smoke set blocking.
7. Pin third-party GitHub Actions to reviewed commit SHAs. Keep top-level permissions `contents: read`; grant additional permissions per job only when justified.
8. Activate branch protection/ruleset with the core Phase 02 check names only. Test failure, cancellation, stale approval, CODEOWNER behavior, check rename, and break-glass restoration using a disposable PR. Phase 03 separately adds the image-contract check after it exists and is green.

## Intended Files

- `.github/workflows/ci.yml`
- `apps/web/package.json`
- `apps/web/playwright.config.ts` (new if needed)
- `apps/web/e2e/phrasebank.spec.ts`
- `apps/web/e2e/writer.spec.ts`
- `Makefile`
- `doc/runbooks/ci.md`
- possibly `apps/web/package-lock.json` removal, only after confirming pnpm is canonical

## Required Check Contract

Use semantic names that remain stable across internal refactors, for example:

- `CI / backend-quality-and-tests`
- `CI / frontend-quality-and-build`
- `CI / frontend-smoke-e2e` (required only at Stage B)
- `CI / backend-image-contract` (created and made required in Phase 03, not Phase 02)

The implementation may choose different names, but the final names must be documented verbatim before ruleset activation.

## Acceptance Criteria

- A PR changing backend code cannot merge when OpenAPI drift, Ruff, formatting, mypy, migration, or pytest fails.
- A PR changing frontend code cannot merge when generated types drift, lint has an error, type-check fails, or build fails.
- CI explicitly demonstrates connection to database `aprkb_test`; a missing PostgreSQL integration environment fails instead of silently producing a reduced test run.
- DB-required collection count is non-zero and recorded; zero collected tests or any skip within the DB-required set fails. Intentional TODO/optional skips remain allowed only outside that set with machine-readable reasons.
- Superseded runs cancel for the same PR branch; production/release workflows are not part of this concurrency group.
- Every job has a timeout and minimal permissions.
- The blocking Playwright smoke set passes repeatedly over the agreed stability window (recommended: 20 consecutive default-branch runs with zero unexplained flakes) before becoming required.
- Fork-origin PRs execute validation without access to deployment secrets.
- Protected branch settings reject a deliberately failing test PR and a PR missing required owner approval.
- Phase 02 exits with only core checks in the ruleset; it has no dependency on a not-yet-created image-contract job.

## Verification

```bash
make lint
make test
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
git diff --check
```

Also inspect at least one GitHub Actions run for test counts, cancellation, timeout declarations, permissions, and absence of secret values.

## Dependencies and Risks

- Depends on Phase 01 owners and ruleset administrator.
- Playwright may require browsers/system packages; use the official supported setup and cache only safe, version-keyed artifacts.
- Do not mark broad E2E required merely because it exists; stability evidence gates enforcement.
- Do not use path filtering that allows cross-contract backend/frontend changes to evade required checks.

