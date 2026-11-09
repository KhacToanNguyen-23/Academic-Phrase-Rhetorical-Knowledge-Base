"""Loopback-only SLR list mock for manual retry tests; never returns real articles.

Run from apps/backend:
  .venv/Scripts/python.exe ../../scripts/manual/job_source.py --delay 20
  .venv/Scripts/python.exe ../../scripts/manual/job_source.py --status 429 --fail-first 2
"""

import argparse
import json
import os
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def make_server(
    *, port: int, status: int, fail_first: int | None, delay: float, retry_after: int
) -> ThreadingHTTPServer:
    lock = threading.Lock()
    counter = 0

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            # Never log request headers, credentials or query contents.
            pass

        def do_GET(self) -> None:
            nonlocal counter
            path = urlsplit(self.path).path
            if path == "/health":
                self.respond(200, {"ready": True})
                return
            if path != "/public/v1/repository/works":
                self.respond(404, {"isSuccess": False})
                return
            with lock:
                counter += 1
                number = counter
            result = status if fail_first is None or number <= fail_first else 200
            print(
                f"{datetime.now(UTC).isoformat()} request={number} status={result} "
                f"delay={delay}s",
                flush=True,
            )
            time.sleep(delay)
            payload = (
                {"isSuccess": True, "data": {"items": [], "page": {}}}
                if result == 200
                else {"isSuccess": False, "error": {"code": "MANUAL_TEST_FAILURE"}}
            )
            self.respond(result, payload)

        def respond(self, status_code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            try:
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if status_code in {429, 503}:
                    self.send_header("Retry-After", str(retry_after))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                print(
                    "Client disconnected (expected when killing a test worker).",
                    flush=True,
                )

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=65534)
    parser.add_argument("--status", type=int, choices=(200, 403, 429, 503), default=200)
    parser.add_argument("--fail-first", type=int)
    parser.add_argument("--delay", type=float, default=0)
    parser.add_argument("--retry-after", type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 0 <= args.delay <= 120:
        parser.error("port must be 1..65535 and delay 0..120 seconds")
    if args.retry_after < 0 or (args.fail_first is not None and args.fail_first < 0):
        parser.error("retry-after and fail-first must be nonnegative")
    server = make_server(
        port=args.port,
        status=args.status,
        fail_first=args.fail_first,
        delay=args.delay,
        retry_after=args.retry_after,
    )
    print(
        f"Mock source ready: http://127.0.0.1:{args.port} PID={os.getpid()} "
        "(empty batches only; Ctrl+C to stop)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
