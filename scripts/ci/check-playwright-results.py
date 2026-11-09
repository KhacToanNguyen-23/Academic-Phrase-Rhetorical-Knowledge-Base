"""Fail CI when Playwright silently skips tests or produces no runnable cases."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check_results(path: Path) -> int:
    try:
        cases = list(ET.parse(path).iter("testcase"))
    except (OSError, ET.ParseError) as error:
        print(
            f"::error::Cannot read Playwright JUnit results: {error}", file=sys.stderr
        )
        return 1
    skipped = [
        case.attrib.get("name", "unknown")
        for case in cases
        if case.find("skipped") is not None
    ]
    failed = [
        case.attrib.get("name", "unknown")
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    ]
    if not cases or skipped or failed:
        print(
            f"::error::Playwright requires nonempty results with zero skips/failures. "
            f"Collected={len(cases)}, skipped={skipped}, failed={failed}",
            file=sys.stderr,
        )
        return 1
    print(f"Playwright: {len(cases)} tests passed with zero skips/failures.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check-playwright-results.py <junit.xml>")
    raise SystemExit(check_results(Path(sys.argv[1])))
