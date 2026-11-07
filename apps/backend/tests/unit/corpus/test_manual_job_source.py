"""Smoke-check the operator's fault simulator over actual loopback HTTP."""

import json
import runpy
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "status,fail_first,expected",
    [
        (200, None, [200]),
        (429, 2, [429, 429, 200]),
        (503, 1, [503, 200]),
        (403, None, [403]),
    ],
)
def test_manual_source_modes(status, fail_first, expected):
    script = Path(__file__).resolve().parents[5] / "scripts/manual/job_source.py"
    make_server = runpy.run_path(str(script))["make_server"]
    server = make_server(port=0, status=status, fail_first=fail_first, delay=0, retry_after=7)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        actual = []
        for _ in expected:
            try:
                response = urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/public/v1/repository/works?limit=1",
                    timeout=3,
                )
            except urllib.error.HTTPError as error:
                response = error
            with response:
                actual.append(response.code)
                data = json.loads(response.read())
                if response.code in (429, 503):
                    assert response.headers["Retry-After"] == "7"
                if response.code == 200:
                    assert data["data"]["items"] == []
        assert actual == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
