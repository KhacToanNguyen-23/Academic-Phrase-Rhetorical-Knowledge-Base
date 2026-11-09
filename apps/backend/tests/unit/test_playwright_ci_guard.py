"""The CI gate must detect a green-looking E2E run with skipped cases."""

import runpy
from pathlib import Path

import pytest

check_results = runpy.run_path(
    str(Path(__file__).resolve().parents[4] / "scripts/ci/check-playwright-results.py")
)["check_results"]


@pytest.mark.parametrize(
    "xml,expected",
    [
        ("<testsuites><testsuite><testcase name='ok'/></testsuite></testsuites>", 0),
        ("<testsuite><testcase name='ok'/></testsuite>", 0),
        ("<testsuites/>", 1),
        ("<testsuite><testcase name='not-run'><skipped/></testcase></testsuite>", 1),
        ("<testsuite><testcase name='bad'><failure/></testcase></testsuite>", 1),
        ("<testsuite><testcase name='error'><error/></testcase></testsuite>", 1),
        ("<testsuite>", 1),
    ],
)
def test_ci_guard_rejects_empty_skipped_and_failed_results(tmp_path, xml, expected):
    path = tmp_path / "results.xml"
    path.write_text(xml, encoding="utf-8")
    assert check_results(path) == expected


def test_ci_guard_requires_a_result_file(tmp_path):
    assert check_results(tmp_path / "missing.xml") == 1
