# Phase 05 — Track-Specific CD and Rollout

## Goal

Implement only the selected deployment track, prove it in staging, and roll out production controls gradually.

## Work

1. Add a release workflow that triggers only from an approved source (protected default branch, signed/reviewed release tag, or manual promotion as selected in the ADR).
2. Build the backend image once from a reviewed commit, scan/test it, publish it, resolve its immutable registry digest, and retain provenance. Do not rebuild for production. Verify the registry digest equals the desired and running platform digests for both API and worker; application metadata supplies only the commit SHA mapping.
3. Deploy the same digest to staging API and worker with distinct commands. Bind environment-scoped configuration and durable shared `BLOB_DIR` without rendering secrets to logs.
4. Run preflight: verify expected database identity, current/target Alembic revisions, single head, backup readiness, blob availability, deployment lock, and compatible application/migration sequence.
   For every schema change, the release record must contain a matrix with rows `N-1 image`, `N image`, and `target image`, columns `current schema`, `expanded/target schema`, `API read/write smoke`, `worker claim/complete smoke`, and `rollback eligibility`, and an explicit pass/fail/not-applicable result for every cell.
5. Use a mandatory worker drain protocol before incompatible migrations: prevent all workers from claiming new PostgreSQL jobs; inventory in-flight job IDs/counts without payload text; allow completion up to a declared timeout; after timeout use the existing safe lease/recovery semantics or an approved manual recovery path; prove zero active claims before migration; record queued/in-flight/completed/recovered counts; resume claims only after schema/application verification.
6. Run staging smoke tests for API health, authentication-safe endpoints, job polling, audit behavior, and a synthetic release-scoped shared-blob sentinel. The sentinel contains no corpus/manuscript data, uses least-privilege API/worker identities, has a unique release ID, records create/read/delete results without content, and is deleted on success, failure, and rollback via finally/cleanup handling.
7. Require approval according to ADR, then promote the exact staging-tested digest to production using environment concurrency protection configured to queue rather than cancel active production releases (`cancel-in-progress: false`). Also acquire an independent PostgreSQL advisory/release lock around migration and release-critical state changes; workflow concurrency alone is insufficient.
8. Record release evidence: commit, digest, revisions, actor/approver, timings, smoke results, and rollback target.
9. Implement rollback workflow/runbook that restores the previous image digest and applies a migration-aware decision tree. Never run an untested database downgrade automatically.
10. Conduct a game day in staging: failed migration, failed API readiness, worker termination/restart, blob unavailable, and previous-digest rollback.

## Intended Files

Final names depend on Phase 04. Expected categories:

- `.github/workflows/cd-<selected-track>.yml`
- selected platform manifest/compose/Helm/Dokploy configuration only
- `doc/runbooks/deploy.md`
- `doc/runbooks/migrations.md`
- `doc/runbooks/rollback.md`
- `README.md`
- environment configuration templates containing names/defaults only, never secret values

## Rollout Stages

1. **Shadow:** build/publish and generate evidence, no deployment.
2. **Staging manual:** deploy/migrate/verify with explicit approval; rehearse rollback.
3. **Production manual:** promote exact digest with named approver and monitored window.
4. **Selective automation:** automate staging and low-risk promotion steps only after success/error metrics meet the agreed threshold.
5. **Steady state:** periodic ruleset, credential, action-pin, restore, and rollback audits.

## Acceptance Criteria

- Release workflow cannot run from an untrusted fork or unprotected commit and has least-privilege permissions.
- Published artifact is addressed by digest; staging and production evidence show no rebuild, and registry, promoted target, desired API/worker specs, and running API/worker status all show the same digest. Application metadata shows the corresponding commit SHA only.
- Two simultaneous production attempts result in one active release and one queued attempt; an active production release is never cancelled by a newer run, and migrations never run concurrently.
- Production concurrency queues the second attempt with `cancel-in-progress: false`; a PostgreSQL advisory/release lock independently prevents concurrent migration/release-critical execution.
- A deliberately failing staging migration prevents application promotion and leaves an actionable, non-secret audit trail.
- Failed readiness prevents traffic completion and triggers the documented recovery path.
- Previous-digest application rollback completes within the approved target; migration compatibility decision is recorded.
- Worker resumes PostgreSQL polling after rollout without duplicate queue infrastructure.
- Before migration, worker evidence proves new claims are disabled, in-flight jobs reached completion or approved timeout recovery, and queue counts reconcile; after rollout, claims resume and queue progress is demonstrated.
- API and worker both pass the synthetic release-scoped durable blob sentinel check; lifecycle evidence shows create/read/delete using least privilege and no sentinel content or sensitive data in logs. Blob unavailability blocks or degrades release exactly as documented.
- For every schema-changing release, staging evidence records a compatibility matrix and a successful N-1 image against target-schema smoke run; otherwise the approved release classification is roll-forward-only with explicit downtime/drain/recovery evidence.
- Production release evidence contains commit SHA, digest, database revisions, actor/approver, timestamps, and smoke results.
- Runbooks are executed by a team member other than the author during staging rehearsal.

## Verification

Baseline commands remain mandatory:

```bash
make lint
make test
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```

The Phase 04 ADR must add exact selected-platform validation commands, dry-run/render checks, registry/desired/running digest comparison, migration status, DB advisory-lock proof, worker drain/queue reconciliation, release-scoped shared-blob lifecycle, N-1/schema compatibility, and rollback rehearsal. Evidence must redact secrets and corpus/manuscript content.

## Dependencies and Risks

- Depends on approved Phase 04 ADR, registry, staging environment, durable blob storage, database backup/restore owner, and environment approvers.
- Migration rollback may be impossible; favor backward-compatible expand/contract changes and forward-fix plans.
- Automatic promotion remains disabled until staging and rollback evidence meets agreed thresholds.
- Do not couple deploy success solely to API liveness; verify worker, database revision, queue progress, and blob access.

