"""Check source pages with GET; distinguish blocked checks from broken links."""

import argparse
import json
from pathlib import Path

import httpx


def classify(status: int) -> str:
    if 200 <= status < 400:
        return "REACHABLE"
    if status in (401, 403, 429):
        return "BLOCKED"
    if status in (404, 410):
        return "BROKEN"
    return "HTTP_ERROR"


def check_link(client: httpx.Client, url: str) -> dict:
    try:
        # HEAD can be refused independently of browser page access. Stream only
        # a small HTML prefix; do not download linked images or video assets.
        with client.stream("GET", url) as response:
            result = {
                "url": url,
                "method": "GET",
                "status": response.status_code,
                "final_url": str(response.url),
                "result": classify(response.status_code),
            }
            if result["result"] == "BLOCKED":
                prefix = bytearray()
                for chunk in response.iter_bytes():
                    prefix.extend(chunk[: 2048 - len(prefix)])
                    if len(prefix) >= 2048:
                        break
                result["reason"] = prefix.decode("utf-8", errors="replace")
            return result
    except httpx.HTTPError as error:
        return {"url": url, "result": "NETWORK_ERROR", "reason": type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    credits = json.loads(
        (root / "apps/web/src/features/landing/assets/credits.json").read_text(encoding="utf-8")
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=20,
        headers={"User-Agent": "AcademicPhraseKBLinkAudit/1.0"},
    ) as client:
        results = [check_link(client, credit["page"]) for credit in credits]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                status: sum(row["result"] == status for row in results)
                for status in {row["result"] for row in results}
            }
        )
    )
    # A blocked/network check is inconclusive, never a green link acceptance.
    return (
        1
        if any(row["result"] in {"BROKEN", "HTTP_ERROR"} for row in results)
        else 2
        if any(row["result"] != "REACHABLE" for row in results)
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
