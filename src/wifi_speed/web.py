from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Type
from urllib.parse import parse_qs, urlparse

from wifi_speed.config import Config
from wifi_speed.settings import apply_interval_minutes, settings_payload
from wifi_speed.storage import ResultStore, result_to_dict

logger = logging.getLogger(__name__)
TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


def create_handler(config: Config) -> Type[BaseHTTPRequestHandler]:
    store = ResultStore(config.database_path)

    class WifiSpeedHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            routes: dict[str, Callable[[dict[str, list[str]]], None]] = {
                "/": lambda _q: self._serve_dashboard(),
                "/api/latest": lambda _q: self._serve_latest(),
                "/api/results": self._serve_results,
                "/api/chart": self._serve_chart,
                "/api/summary": self._serve_summary,
                "/api/settings": self._serve_settings,
            }

            handler = routes.get(parsed.path)
            if handler is None:
                self._send_json({"error": "not found"}, status=404)
                return

            query = parse_qs(parsed.query)
            handler(query)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/settings":
                self._send_json({"error": "not found"}, status=404)
                return
            self._update_settings()

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

        def _serve_dashboard(self) -> None:
            body = TEMPLATE_PATH.read_text(encoding="utf-8").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_latest(self) -> None:
            results = store.recent(1)
            if not results:
                self._send_json({"result": None})
                return
            self._send_json({"result": result_to_dict(results[0])})

        def _serve_results(self, query: dict[str, list[str]]) -> None:
            limit = _query_int(query, "limit", 50, minimum=1, maximum=500)
            hours = _query_int(query, "hours", 168, minimum=1, maximum=8760)
            results = store.recent(limit=limit, hours=hours)
            self._send_json({"results": [result_to_dict(r) for r in results]})

        def _serve_chart(self, query: dict[str, list[str]]) -> None:
            limit = _query_int(query, "limit", 200, minimum=1, maximum=500)
            hours = _query_int(query, "hours", 24, minimum=1, maximum=8760)
            results = store.series(hours=hours, limit=limit)
            self._send_json({"results": [result_to_dict(r) for r in results]})

        def _serve_summary(self, query: dict[str, list[str]]) -> None:
            hours = _query_int(query, "hours", 24, minimum=1, maximum=8760)
            self._send_json({"summary": store.summary(hours)})

        def _serve_settings(self, query: dict[str, list[str]]) -> None:
            del query
            current = Config.load(config.config_path)
            self._send_json(settings_payload(current.interval_minutes))

        def _update_settings(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw) if raw else {}
            except (ValueError, json.JSONDecodeError):
                self._send_json({"ok": False, "error": "リクエスト形式が不正です"}, status=400)
                return

            if "interval_minutes" not in payload:
                self._send_json({"ok": False, "error": "interval_minutes が必要です"}, status=400)
                return

            try:
                minutes = int(payload["interval_minutes"])
            except (TypeError, ValueError):
                self._send_json({"ok": False, "error": "interval_minutes は整数で指定してください"}, status=400)
                return

            ok, message = apply_interval_minutes(minutes)
            if not ok:
                self._send_json({"ok": False, "error": message}, status=400)
                return

            config.interval_minutes = minutes
            self._send_json({"ok": True, "message": message, **settings_payload(minutes)})

        def _send_json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return WifiSpeedHandler


def run_server(config: Config) -> None:
    handler = create_handler(config)
    server = ThreadingHTTPServer((config.web_host, config.web_port), handler)
    logger.info("wifi-speed web: http://%s:%s", config.web_host, config.web_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("wifi-speed web: shutdown")
    finally:
        server.server_close()


def _query_int(
    query: dict[str, list[str]],
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = query.get(key, [str(default)])[0]
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))
