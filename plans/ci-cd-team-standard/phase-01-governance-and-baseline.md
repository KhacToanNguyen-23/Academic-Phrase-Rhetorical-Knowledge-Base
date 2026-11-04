# Phase 01 — Governance and Baseline

## Goal

Turn delivery expectations into owned repository policy before modifying execution pipelines.

## Work

1. Inventory current CI check names, average duration, skip counts, flaky tests, Docker build behavior, deployment actors, registry, database migration process, and `BLOB_DIR` topology.
2. Add `.github/CODEOWNERS` coverage for workflows, Dockerfiles, migrations, `infra/`, policies, dependency lockfiles, and runbooks. Use real team handles confirmed by the repository administrator—never placeholders that silently fail.
3. Add a PR template requiring scope, risk tier, linked issue, verification evidence, migration/rollback impact, secrets/data-handling impact, and docs updates.
4. Write `doc/runbooks/ci.md` with required check names, local equivalents, failure ownership, rerun rules, flaky-test quarantine, and escalation.
5. Draft migration and rollback runbooks before CD work. Explicitly state that Alembic downgrade is not automatically safe and that forward-fix is preferred unless a tested downgrade exists.
6. Update `README.md` with the team delivery contract and runbook links.
7. Configure a ruleset/protected branch only after Phase 02 check names exist; record the intended settings now: PR-only changes, required status checks, stale approval dismissal, CODEOWNER review, conversation resolution, and administrator policy.
8. Define a break-glass/bypass policy: smallest possible actor list, incident/change approval, time limit, mandatory audit evidence, post-use review, and immediate restoration of normal protection.

## Intended Files

- `.github/CODEOWNERS` (new)
- `.github/pull_request_template.md` (new)
- `doc/runbooks/ci.md` (new)
- `doc/runbooks/migrations.md` (new)
- `doc/runbooks/rollback.md` (new)
- `README.md` (update)

## Acceptance Criteria

- Every high-risk path has at least one confirmed owner and owner review is testable on a draft PR.
- PR template contains explicit migration, rollback, secret, blob, and verification sections.
- CI runbook maps every planned required GitHub check to one local command and one owning team/role.
- Flaky tests cannot be silently retried into green: quarantine requires an issue, named owner, expiry date, and non-blocking classification.
- Migration runbook documents current/target revision capture, single-head preflight, backup/restore responsibility, worker drain decision, and recovery paths.
- Rollback runbook distinguishes application image rollback from database recovery.
- Repository administrator signs off the intended branch protection settings.
- A disposable branch/PR proves the staged ruleset before default-branch enforcement; evidence covers required-check failure, stale approvals, owner review, and recovery from a renamed/missing check.
- The runbook includes a check-rename checklist that updates workflow job names, documented required checks, and ruleset configuration in one reviewed change.
- Break-glass use cannot be silent: actor, approver, reason, start/end time, affected commit, and restoration evidence are retained.

## Verification

```bash
git diff --check
rg -n "migration|rollback|BLOB_DIR|CODEOWNERS|required check" README.md doc .github
```

Manual evidence: draft PR screenshots/export showing CODEOWNER routing and template rendering. Branch protection is not enabled until Phase 02 check names are stable.

## Dependencies and Risks

- Depends on named maintainers and a GitHub administrator.
- Risk: invalid CODEOWNERS handles create false assurance. Validate using an actual draft PR.
- Risk: enabling protection too early can deadlock merges. Stage rules in audit mode or apply after Phase 02.

