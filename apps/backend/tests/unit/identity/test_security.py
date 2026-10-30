from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from aprkb.core.deps import get_current_client
from aprkb.core.security import require_role, role_allows
from aprkb.modules.identity.models import ApiClient


def test_role_hierarchy_is_exact_and_unknown_roles_fail_closed() -> None:
    allowed = {
        "admin": {"admin", "curator", "reviewer", "client"},
        "curator": {"curator", "reviewer", "client"},
        "reviewer": {"reviewer", "client"},
        "client": {"client"},
    }

    for actor_role, required_roles in allowed.items():
        for required_role in allowed:
            assert role_allows(actor_role, required_role) is (required_role in required_roles)
    assert not role_allows("reviewer", "curator")
    assert not role_allows("unknown", "client")
    assert not role_allows("admin", "unknown")


def test_require_role_rejects_reviewer_for_curator_route() -> None:
    app = FastAPI()
    reviewer = ApiClient(
        name="test reviewer",
        key_hash="not-a-real-key-hash",
        key_prefix="aprkb_test",
        role="reviewer",
        is_active=True,
    )

    curator_guard = require_role("curator")

    @app.get("/curator")
    async def curator_route(
        _client: Annotated[ApiClient, Depends(curator_guard)],
    ) -> dict[str, bool]:
        return {"ok": True}

    app.dependency_overrides[get_current_client] = lambda: reviewer
    response = TestClient(app).get("/curator")

    assert response.status_code == 403
