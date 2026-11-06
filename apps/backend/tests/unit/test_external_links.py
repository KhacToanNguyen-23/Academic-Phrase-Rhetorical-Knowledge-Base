"""The manual link checker must not label robots-policy blocks as broken/pass."""

import runpy
from pathlib import Path

import httpx
import pytest

check_link = runpy.run_path(
    str(Path(__file__).resolve().parents[4] / "scripts/manual/check_external_links.py")
)["check_link"]


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, "REACHABLE"),
        (204, "REACHABLE"),
        (401, "BLOCKED"),
        (403, "BLOCKED"),
        (429, "BLOCKED"),
        (404, "BROKEN"),
        (410, "BROKEN"),
        (500, "HTTP_ERROR"),
    ],
)
def test_link_status_is_not_confused_with_policy_or_server_error(status, expected):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(status, text="Please respect our robot policy")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_link(client, "https://source.example/file")
    assert result["result"] == expected
    assert result["status"] == status
    if expected == "BLOCKED":
        assert "robot policy" in result["reason"]


def test_link_redirect_is_followed_to_real_target():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(302, headers={"Location": "/new"})
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = check_link(client, "https://source.example/old")
    assert result["result"] == "REACHABLE"
    assert result["final_url"] == "https://source.example/new"


def test_link_timeout_is_inconclusive():
    def handler(request):
        raise httpx.ReadTimeout("fixture timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_link(client, "https://source.example/file")
    assert result["result"] == "NETWORK_ERROR"
    assert result["reason"] == "ReadTimeout"
