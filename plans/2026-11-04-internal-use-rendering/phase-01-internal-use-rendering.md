# Phase 1: Align internal-use eligibility

Status: implemented and verified. Focused unit checks and the 31-test PostgreSQL pattern/render API suite passed, including configured internal-use permission and rejection after revocation.

## Implementation

1. In `apps/backend/src/aprkb/modules/patterns/read_model.py`, make the display-only source predicate match recommendation eligibility: authored, or mined with `allows_display` or the configured internal-use flag. Preserve approval and exactly-one-provenance checks. Keep source-type checking fail-closed; do not admit arbitrary source types through a license alone.
2. In `apps/backend/src/aprkb/modules/composition/router.py`, accept FastAPI `Request` and obtain `frozenset(request.app.state.policy_bundle.license.internal_use_codes)`. Pass it into `composition/service.py`'s `render_pattern`, which forwards it to `patterns.service.get_renderable_version`. Use an optional empty-set default only where needed for existing internal callers; the HTTP path must always supply the runtime policy.
3. In `apps/backend/src/aprkb/modules/patterns/router.py`, pass that same runtime policy through the client branch of `get_versions`; extend `patterns/service.py`'s `renderable_pattern_versions` to forward it into `get_renderable_version`. Confirm other pattern list/detail/version-detail routes already pass the policy and retain their behavior.
4. Leave recommendation license eligibility unchanged unless a small shared pure predicate is demonstrably needed; avoid a new abstraction for two simple boolean checks. Keep response permission metadata accurate.
5. In `README.md`, document that the entire app is for internal use, so a configured internal-use license permits phrase display and rendering despite public-display denial. Clarify that unpermitted sources remain excluded. Update the comment in `apps/backend/src/aprkb/policies/license_policy.yaml` if it no longer accurately describes the approved scope; do not change the list of permitted license codes.

## Regression coverage

- Extend `apps/backend/tests/unit/patterns/test_read_model.py` with mined-source cases: display false + internal permission true accepted; display false + internal permission false rejected; display true accepted; missing/ambiguous provenance, unknown source type, and unapproved status rejected. Verify the raw display permission stays false and internal flag stays true for the exception case.
- Add focused composition service/router forwarding coverage in the existing appropriate tests or a minimal unit test module. Verify the policy supplied by the route reaches the pattern read service, rather than just testing a boolean predicate in isolation.
- Extend `apps/backend/tests/integration/api/test_routes.py` with an isolated approved mined pattern using a configured internal-use license (currently PROPRIETARY) whose `allows_display` is false. Assert successful recommendation, pattern list/detail/current version detail/version list, and `/v1/render` using the issued recommendation. Include a denied source not on the internal-use list and preserve wrong-client/stale/unapproved rejection coverage. Work carefully around existing uncommitted edits in this file.

## Verification

From repository root, use `apps/backend/.venv/Scripts/python.exe -m pytest apps/backend/tests/unit/patterns/test_read_model.py apps/backend/tests/unit/composition apps/backend/tests/unit/recommendation -q` with a fresh writable `--basetemp` when necessary. Run the affected API integration tests against the existing isolated `aprkb_test` fixture when `TEST_DATABASE_URL` is available. Run Ruff on edited Python files. Review the final diff for policy propagation and unrelated changes.

Accepted when every plan acceptance criterion has fresh test evidence, or an explicit infrastructure limitation is recorded without a false passing claim.
