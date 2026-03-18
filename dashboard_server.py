from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from prosperity.backtest import (
    load_equity_curve,
    load_fills,
    load_result_index,
    run_directory_backtest,
)

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "dashboard"


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
            return
        if parsed.path == "/api/results":
            self._handle_results_api(parsed)
            return
        if parsed.path == "/api/equity":
            self._handle_equity_api(parsed)
            return
        if parsed.path == "/api/fills":
            self._handle_fills_api(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/backtest":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            payload = self._read_json()
            data_dir = self._resolve_path(payload.get("dataDir", "imcdata"))
            output_dir = self._resolve_path(payload.get("outputDir", "outputs/imcdata"))
            result = run_directory_backtest(data_dir=data_dir, output_dir=output_dir)
            self._send_json(result)
        except Exception as exc:  # pragma: no cover - user-facing error path
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_results_api(self, parsed) -> None:
        try:
            query = parse_qs(parsed.query)
            output_dir = self._resolve_path(query.get("outputDir", ["outputs/imcdata"])[0])
            payload = load_result_index(output_dir)
            self._send_json(payload)
        except Exception as exc:  # pragma: no cover - user-facing error path
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_equity_api(self, parsed) -> None:
        try:
            query = parse_qs(parsed.query)
            output_dir = self._resolve_path(query.get("outputDir", ["outputs/imcdata"])[0])
            label = query["label"][0]
            payload = {"label": label, "points": load_equity_curve(output_dir, label)}
            self._send_json(payload)
        except Exception as exc:  # pragma: no cover - user-facing error path
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_fills_api(self, parsed) -> None:
        try:
            query = parse_qs(parsed.query)
            output_dir = self._resolve_path(query.get("outputDir", ["outputs/imcdata"])[0])
            label = query["label"][0]
            limit = int(query.get("limit", ["50"])[0])
            payload = {"label": label, "fills": load_fills(output_dir, label, limit=limit)}
            self._send_json(payload)
        except Exception as exc:  # pragma: no cover - user-facing error path
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _serve_static(self, relative_path: str) -> None:
        target = (STATIC_DIR / relative_path).resolve()
        if STATIC_DIR not in target.parents and target != STATIC_DIR:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        mime_type, _ = mimetypes.guess_type(target.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        return candidate.resolve()

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local backtest dashboard.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind the dashboard server to.")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive shutdown path
        print("\nStopping dashboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
