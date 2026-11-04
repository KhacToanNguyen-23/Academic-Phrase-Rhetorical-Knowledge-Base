# Phase 04 — Deployment Decision Gate

## Goal

Collect production facts, select exactly one deployment track, and record the operational contract before any CD workflow or manifest is implemented.

## Confirmed Inputs

- The target is a self-managed homeserver hosting frontend, backend API, and the PostgreSQL-polling worker.
- The deployment controller is Docker Compose.
- CI validation and image build/publish should be automatic; production deployment should require human approval initially.
- Inspected APRKB images are local-only `latest` tags with no registry namespace or verified remote digest. Registry publication is therefore a new capability, not an existing contract.
- GHCR is the default recommendation because the source repository is on GitHub, but the ADR must compare it with any established Docker Hub convention before selecting one.
- The durable shared `BLOB_DIR` path or named volume remains a blocking input. The production Compose file must mount the same storage into API and worker at the same container path.

## Required Inputs

The production owner must provide and approve:

1. Current platform and target: Dokploy/VPS, Azure/Kubernetes, or another named platform.
2. Container registry, immutable tag/digest support, authentication method, retention, and vulnerability scanning expectations.
3. Environment topology: staging/production, API/worker replica counts, ingress/TLS/DNS ownership, and deployment approval policy.
4. PostgreSQL ownership, connectivity, backup/restore mechanism, maintenance window, and migration lock/serialization capability.
5. Durable shared `BLOB_DIR` implementation, access mode for API/worker replicas, permissions, capacity, backup/restore, and failure behavior.
6. Secret store and identity model; prefer short-lived workload/OIDC credentials over long-lived repository secrets when supported.
7. SLOs: allowed downtime, health-check timeout, rollback target, data recovery objective, and incident escalation contacts.
8. Whether production promotion is automatic from `main` or requires a named approver after staging evidence.
9. Frontend delivery ownership: artifact/build source, hosting target, configuration injection, cache/CDN invalidation, promotion trigger, smoke test, and rollback owner. If frontend deployment is intentionally excluded, the ADR must name a separate approved plan/owner and state that backend CD does not imply full-system deployment.

## Decision Record

Create `doc/adr/ci-cd-platform.md` containing:

- chosen track and why it matches the existing deployed system;
- alternatives considered and rejected;
- build-once/promote-by-digest model;
- API/worker same-digest deployment mapping;
- PostgreSQL migrator ownership and worker drain/resume rules;
- durable blob mapping and backup responsibility;
- secret/identity boundaries;
- staging and production approval gates;
- rollback and forward-fix policy;
- owners and a review date.
- frontend artifact/promotion/rollback contract, or an explicit separately owned plan reference.

## Track Contracts to Evaluate

### Dokploy/VPS candidate

- GitHub Actions publishes one digest; Dokploy deploys API and worker services from that digest with distinct commands.
- Host/shared volume or supported durable storage must be mounted consistently into both services; document single-host failure and backup implications.
- Migration runs as a one-shot, serialized release command before traffic promotion/worker resume.
- Webhook or platform token is environment-scoped and protected by GitHub Environment approval.

### Azure/Kubernetes candidate

- GitHub Actions publishes one digest to the selected registry; manifests/Helm reference digest, not mutable tag.
- API Deployment and worker Deployment use the same digest with different commands.
- Migration uses a one-shot Job with release serialization; application rollout waits for success.
- `BLOB_DIR` requires a storage class/access mode that supports the actual replica topology; validate ReadWriteMany semantics or constrain replicas with an explicit accepted risk.
- Prefer workload identity/OIDC and environment approvals; define namespace, resource, probe, and rollback ownership.

These are evaluation criteria, not authorization to create both tracks.

## Intended Files

- `doc/adr/ci-cd-platform.md` (new)
- `doc/runbooks/deploy.md` (outline/update)
- `doc/runbooks/migrations.md` (platform decisions)
- `doc/runbooks/rollback.md` (platform decisions)
- No `.github/workflows/cd-*.yml` or platform manifest changes until approval

## Acceptance Criteria

- ADR has no unresolved placeholders for platform, registry, storage, secrets, migration actor, approver, or rollback owner.
- A staging topology diagram/table maps API, worker, PostgreSQL, registry, and durable blob storage.
- Security review confirms least-privilege identity and that PRs/forks cannot access deploy credentials.
- Database owner approves backup/restore and serialized migration procedure.
- API and worker owners approve same-digest and shared-blob requirements.
- Production owner explicitly signs off automatic versus manual promotion.
- Frontend deploy ownership and artifact promotion/rollback are concrete, or the ADR explicitly scopes them to a separately approved plan with owner and deadline.
- Phase 05 file paths and verification commands can be named concretely from the selected track.

## Verification

```bash
git diff --check
rg -n "TODO|TBD|placeholder|Dokploy|Azure|Kubernetes|BLOB_DIR|migration|rollback" doc/adr/ci-cd-platform.md doc/runbooks
```

The gate fails if mutually exclusive platform choices remain unresolved or if a production credential/storage design is assumed rather than evidenced.

## Dependencies and Risks

- Requires human production/platform ownership; this cannot be inferred from repository files.
- No CD implementation may proceed while this gate is open.
- If shared durable filesystem semantics cannot be met, pause and specify a separate blob-store architecture change; do not hide replica-local storage behind deployment configuration.

