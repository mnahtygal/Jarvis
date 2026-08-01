"""Small loopback HTTP surface for the isolated worker process."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from core.grounded_sam_contract import grounded_sam_http_status
from .worker import GroundedSamWorker


def make_handler(worker: GroundedSamWorker) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/health":
                self._json(404, {"error": "not_found"})
                return
            self._json(200, worker.health())

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/analyze":
                self._json(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload: Any = json.loads(self.rfile.read(length))
            except Exception:
                self._json(400, {"error": "invalid_json"})
                return
            result = worker.analyze(payload)
            self._json(grounded_sam_http_status(result), result)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def serve(worker: GroundedSamWorker, *, host: str = "127.0.0.1", port: int = 8092) -> None:
    ThreadingHTTPServer((host, port), make_handler(worker)).serve_forever()
