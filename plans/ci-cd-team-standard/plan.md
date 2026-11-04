# CI/CD Team Standard Plan

Mode: `--hard`
Risk: high-risk — changes to CI/CD, production images, secrets, migrations, and rollback can interrupt service or corrupt production state.
Status: Draft for team validation; no CI/CD implementation is authorized by this plan alone.
Source of truth: `SCAFFOLD_PRD.md` and repository `AGENTS.md` override older product documents.

## Outcome

Create an enforceable delivery standard that every contributor follows:

1. Pull requests cannot merge unless deterministic backend and frontend CI checks pass.
2. API and worker are launched from the same immutable backend image digest, with different commands.
3. A documented decision gate selects the production deployment track without assuming Dokploy/VPS or Azure/Kubernetes.
4. The chosen CD track uses explicit migration, health, rollback, blob durability, secret, and approval controls.
5. Governance files and runbooks make the standard repeatable by team members rather than dependent on one operator.

## Scope Challenge

- Exists: `.github/workflows/ci.yml` already runs backend lint/tests/migrations and frontend type-check/build; `apps/backend/Dockerfile` is an initial API image, not yet a production contract.
- Minimum: harden and enforce CI, then produce one backend image contract, then stop at a platform decision gate before track-specific CD.
- Complexity: Hard. This spans repository policy, GitHub controls, containers, database migrations, persistent blobs, secrets, production rollout, and rollback.
- Tests: default; CI configuration tests and smoke checks are specified per phase.
- Tasks: default; implementation task hydration belongs to `$bb-cook --hard`, not this planning step.

## Non-negotiable Architecture Invariants

- Keep the Python package at `apps/backend/src/aprkb` and tests under `apps/backend/tests`.
- Keep router → service → repository/model layering and existing audit/provenance rules.
- PostgreSQL remains the only database and job queue. Do not introduce Redis or Celery.
- The production API and PostgreSQL-polling worker must run the exact same immutable backend image digest; only entry commands differ.
- `BLOB_DIR` must be durable and shared/readable by every API and worker replica that needs corpus blobs. A replica-local filesystem is not a valid multi-replica production design.
- Mining rights checks remain before blob reads/parsing. Secrets, full article text, and manuscript contents must not enter logs, artifacts, or audit snapshots.
- Append-only pattern versions and transactional audit behavior must remain unchanged.
- Do not add the admin console, production NLP extraction, taxonomy publishing, or excluded evaluation algorithms.
- Seed content remains self-authored.

## Delivery Sequence and Gates

| Phase | Purpose | Entry gate | Exit gate |
|---|---|---|---|
| 01 | Team governance and baseline | Current repository inventory confirmed | Owners, PR rules, runbooks, and measurable baseline approved |
| 02 | Enforced core CI | Phase 01 policy approved | Core backend/frontend checks are deterministic and protected; no image-contract dependency yet |
| 03 | Production container contract | Phase 02 stable | One immutable backend image passes API/worker smoke tests; image-contract check is then added to the ruleset |
| 04 | Deployment decision gate | Production owner supplies platform facts | One track and its storage/migration/approval contract are recorded |
| 05 | Track-specific CD and rollout | Phase 04 decision record approved | Staging proves deploy/migrate/rollback; production uses controlled promotion |

Phases must be completed in order. The first cook handoff is limited to Phases 01–03. It must stop before Phase 04, collect owner inputs, and obtain approval of the completed ADR. A second explicit cook handoff may then implement Phase 05. Phase 05 must not be implemented from placeholders or guessed platform details.

## Phase Files

- [Phase 01 — Governance and baseline](phase-01-governance-and-baseline.md)
- [Phase 02 — Enforced CI](phase-02-enforced-ci.md)
- [Phase 03 — Production container contract](phase-03-production-container-contract.md)
- [Phase 04 — Deployment decision gate](phase-04-deployment-decision-gate.md)
- [Phase 05 — Track-specific CD and rollout](phase-05-track-specific-cd-and-rollout.md)

## Intended Repository Changes

This is the union of intended files; exact platform-specific paths are selected only in Phase 04.

| Path | Intended change |
|---|---|
| `.github/workflows/ci.yml` | Add explicit frontend lint, timeouts/concurrency, deterministic permissions, staged Playwright jobs, image build/smoke validation, and clear required-check names. |
| `.github/CODEOWNERS` | Require review from owners for workflows, Dockerfiles, migrations, infrastructure, policies, and dependency lockfiles. |
| `.github/pull_request_template.md` | Require risk, migration, rollback, observability, security/data-handling, and verification declarations. |
| `.github/workflows/cd-*.yml` | Added only after Phase 04; build/publish once, promote immutable digest, gate migration/deploy/rollback by environment. |
| `apps/backend/Dockerfile` | Pin controlled build inputs, use a non-root runtime, and support API/worker commands from one image. |
| `apps/backend/.dockerignore` | Match the `apps/backend` build context; exclude secrets, local blobs, caches, tests/artifacts not needed at runtime, and developer files. |
| `apps/web/package.json` | Add stable CI scripts and staged Playwright suites/tags if needed. |
| `apps/web/playwright.config.*` | Define retries, traces/screenshots, web server/base URL, and CI-safe timeouts; create only if absent. |
| `apps/web/e2e/*.spec.ts` | Classify smoke vs broader E2E coverage; stabilize without expanding product scope. |
| `docker-compose.yml` | Keep local development semantics; document or add safe API/worker command examples only if useful, never treat local volumes as production storage. |
| `Makefile` | Add developer commands that mirror required CI and container smoke checks. |
| `README.md` | Document required checks, delivery flow, image contract, local verification, and pointers to runbooks. |
| `doc/runbooks/ci.md` | Explain failures, reruns, flaky-test handling, required checks, and escalation. |
| `doc/runbooks/deploy.md` | Track-specific deploy, verification, promotion, and audit procedure. |
| `doc/runbooks/migrations.md` | Preflight, backup/restore responsibility, forward-fix/rollback policy, compatibility rules, and failure recovery. |
| `doc/runbooks/rollback.md` | Image rollback, migration-aware decision tree, worker draining, blob verification, and incident handoff. |
| `doc/adr/ci-cd-platform.md` | Record Phase 04 decisions, rejected alternatives, owners, and review date. |
| platform-selected manifests/config | Added only for the chosen track; no dual scaffolding by default. |

## Dependencies

- GitHub administrator able to configure branch protection/rulesets and environments.
- Named CODEOWNERS and production approvers.
- Container registry with immutable digest support and retention policy.
- Dedicated `aprkb_test` PostgreSQL for CI; staging and production databases must be distinct.
- Production database backup/restore owner and tested recovery objective.
- Durable shared storage design for `BLOB_DIR`, with permissions and backup lifecycle.
- Platform-specific credentials delivered through environment-scoped secret storage, never repository files.
- Staging environment representative enough to run API, worker, PostgreSQL queue, migrations, and blob smoke tests.

## Validated Deployment Inputs (2026-11-04)

- Hosting target: a self-managed homeserver.
- Runtime scope: backend API, PostgreSQL-polling worker, and frontend are all hosted on that homeserver.
- Release control: CI validation and image build/publish run automatically; production deployment requires a named human approval. Revisit full autodeploy only after staging and rollback evidence meets the Phase 05 exit criteria.
- Current image evidence: the inspected Docker daemon contains local-only `aprkb-backend:latest`, `aprkb-worker:latest`, and `aprkb-frontend:latest` images. Their names have no registry namespace and no verified remote registry digest. The repository contains no publish workflow or registry variables, so Docker Hub, GHCR, or ACR usage is not yet established.
- Registry recommendation: prefer GHCR for this GitHub-hosted repository unless the homeserver already has an approved Docker Hub convention. Phase 04 must record the final choice and immutable digest/retention policy before CD implementation.
- Deployment adapter: Docker Compose on the homeserver. The production Compose artifact must define frontend, API, worker, and their shared persistent storage; deployment transport/authentication still requires an explicit approved design.
- Storage remains unresolved: identify the actual durable host path or volume shared by API and worker for `BLOB_DIR`, plus backup/restore ownership, before Phase 05.

## Global Acceptance Criteria

- A new contributor can follow documented commands and reproduce all required PR checks.
- Protected branches reject direct pushes and reject merges when any required check or required owner review is missing.
- CI uses a database named `aprkb_test`; logs demonstrate it never targets production.
- Frontend lint is blocking with zero errors; the existing warning is either fixed or explicitly time-boxed before enabling zero-warning policy.
- Playwright adoption is staged: deterministic smoke tests become blocking first; broader or flaky coverage remains non-blocking with an owner and deadline.
- A single commit produces one backend image digest that successfully runs both the API and worker commands.
- The runtime container is non-root, contains no repository `.env`, local `data/blobs`, or development credentials, and exposes a working health/readiness contract.
- Deployment never rebuilds between staging and production; promotion references the tested digest.
- Migration preflight proves a single Alembic head and records current/target revisions. Migration execution is serialized and happens once per release, never independently in each API/worker replica.
- Each schema change has an explicit expand/contract compatibility matrix for N-1, N, and target schema. Staging must run the N-1 image against the target schema and pass defined API/worker smoke checks, or the release is classified roll-forward-only and requires an approved downtime/drain/recovery plan.
- Every release records commit SHA, image digest, migration revision, actor/approver, environment, and result.
- Rollback rehearsal demonstrates restoration of the previous image digest and a migration-safe recovery decision; database downgrade is never assumed safe.
- API and worker can both access the same expected durable blob in staging without placing article/manuscript contents in logs.

## Verification Commands

Commands are run from repository root unless noted:

```bash
make lint
make test
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
docker build -f apps/backend/Dockerfile -t aprkb-backend:ci apps/backend
docker image inspect aprkb-backend:ci
```

Implementation must add documented smoke commands for both image entrypoints and the chosen deployment platform. PostgreSQL-backed checks must set `TEST_DATABASE_URL` to a dedicated database named `aprkb_test`. If Docker, PostgreSQL, or the platform is unavailable, the exact unrun command and reason must be reported.

## Risks and Controls

| Risk | Control |
|---|---|
| CI passes while integration tests skip | Fail CI if PostgreSQL integration tests unexpectedly skip; publish a test summary showing collected/passed/skipped counts. |
| Workflow supply-chain compromise | Pin third-party actions to reviewed commit SHAs with update ownership and scheduled review. |
| Secret leakage | Environment-scoped least-privilege credentials, masked output, no secret-bearing debug dumps, fork PRs receive no deploy credentials. |
| Migration outage or irreversible data loss | Compatibility review, one serialized migrator, backup/restore owner, pre/post checks, and forward-fix-first recovery. |
| API/worker version skew | Deploy both from one digest and verify running digests before completing rollout. |
| Worker processes jobs during incompatible migration | Define drain/pause/resume procedure for PostgreSQL polling and validate queue recovery. |
| Blob loss or split-brain | Shared durable storage, readiness/preflight check, backup policy, and cross-process read smoke test. |
| E2E flakiness blocks delivery | Quarantine policy with owner/deadline; only proven smoke specs become required initially. |
| Branch rules drift from workflow names | Document exact required check names and audit rulesets quarterly or after workflow renames. |
| Platform guessed too early | Phase 04 is a hard stop; no track-specific files before the ADR is approved. |
| Concurrent production deployments | Environment concurrency lock plus human approval and one migration lease/job per release. |
| Branch protection bypass or check rename deadlock | Stage ruleset changes on a disposable branch/PR, audit exact check names, and document time-bound break-glass actors, approval, audit, and restoration. |

## Out of Scope

- Choosing Dokploy/VPS versus Azure/Kubernetes without production-owner input.
- Implementing both deployment tracks “just in case.”
- Changing application features, NLP algorithms, taxonomy publication, recommendation behavior, or the PostgreSQL queue model.
- Adding Redis, Celery, or a second database/job queue.
- Re-architecting `BLOB_DIR` into an object-store adapter unless separately specified and proven necessary for the selected platform.
- Production data migration beyond the release-safe Alembic process.
- Admin console or frontend product expansion.

## Validation Questions Before Implementation

Resolved:

1. Target host: self-managed homeserver for frontend, API, and worker.
2. Release policy: automatic CI/build/publish with human-approved production deployment.
3. Existing Docker images are local `latest` builds, not verified registry artifacts.

Still required at the Phase 04 hard stop:

1. Will the registry be GHCR or Docker Hub, and what retention/immutability policy applies?
2. Confirm the production Compose storage choice: a named volume such as `aprkb_blobs`, or an explicit homeserver directory such as `/srv/aprkb/blobs`, mounted into both API and worker at the same container path.
3. What are the acceptable downtime, rollback, backup/restore, and migration compatibility targets?

## Handoff

First handoff—implement Phases 01–03 only, then stop:

```text
$bb-cook --hard plans/ci-cd-team-standard/plan.md
```

The cook task must explicitly exclude Phases 04–05. Phase 04 is a human decision/ADR gate, not an implementation phase. After its inputs are supplied and the ADR is approved, create a second cook task scoped only to Phase 05. Do not reuse an unattended Phase 01–03 cook session to cross this gate.

