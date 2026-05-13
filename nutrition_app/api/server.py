from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from nutrition_app.core.config import Settings, load_settings
from nutrition_app.db.catalog import CatalogRepository
from nutrition_app.schemas.api import BulkResolveRequest, DaySummaryRequest
from nutrition_app.services.nutrition import NutritionService
from nutrition_app.services.portions import suggest_portions


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    catalog: CatalogRepository
    nutrition: NutritionService


class NutritionHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, app_context: AppContext):
        super().__init__(server_address, handler_class)
        self.app_context = app_context


class NutritionHandler(BaseHTTPRequestHandler):
    server: NutritionHTTPServer
    server_version = "NutritionTracker/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._serve_static_file("index.html")
            return
        if parsed.path.startswith("/static/"):
            self._serve_static_file(parsed.path.removeprefix("/static/"))
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/foods/search":
            self._handle_food_search(parsed.query)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/day-summary":
            self._handle_day_summary()
            return
        if parsed.path == "/api/foods/bulk-resolve":
            self._handle_bulk_resolve()
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_food_search(self, query_string: str) -> None:
        params = parse_qs(query_string)
        query = params.get("q", [""])[0]
        try:
            limit = int(params.get("limit", ["18"])[0])
        except ValueError:
            limit = 18
        items = [self._serialize_food(record) for record in self.server.app_context.catalog.search_foods(query, limit)]
        self._send_json({"items": items, "query": query})

    def _handle_day_summary(self) -> None:
        try:
            payload = self._read_json()
            request_model = DaySummaryRequest.model_validate(payload)
            summary = self.server.app_context.nutrition.build_day_summary(request_model)
        except ValidationError as exc:
            self._send_json({"error": "Invalid request", "details": exc.errors()}, status=HTTPStatus.BAD_REQUEST)
            return
        except LookupError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(summary)

    def _handle_bulk_resolve(self) -> None:
        try:
            payload = self._read_json()
            request_model = BulkResolveRequest.model_validate(payload)
            resolved = self.server.app_context.nutrition.resolve_bulk_entries(request_model)
        except ValidationError as exc:
            self._send_json({"error": "Invalid request", "details": exc.errors()}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(resolved)

    def _serve_static_file(self, relative_path: str) -> None:
        safe_path = Path(relative_path).name if ".." in relative_path else relative_path.lstrip("/")
        file_path = self.server.app_context.settings.static_dir / safe_path
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "Static file not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw_body.decode("utf-8"))

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _serialize_food(record) -> dict:
        payload = record.to_summary_dict()
        for key in ("energy_kcal_100g", "protein_g_100g", "fat_g_100g", "carb_g_100g", "fiber_g_100g", "sodium_mg_100g"):
            value = payload.get(key)
            if isinstance(value, float):
                payload[key] = round(value, 1)
        payload["portions"] = [option.to_dict() for option in suggest_portions(record)]
        return payload


def build_app_context(settings: Settings | None = None) -> AppContext:
    active_settings = settings or load_settings()
    catalog = CatalogRepository(active_settings.db_path)
    nutrition = NutritionService(catalog)
    return AppContext(settings=active_settings, catalog=catalog, nutrition=nutrition)


def run_server(host: str | None = None, port: int | None = None) -> None:
    settings = load_settings()
    if host:
        settings = Settings(db_path=settings.db_path, host=host, port=settings.port, static_dir=settings.static_dir)
    if port:
        settings = Settings(db_path=settings.db_path, host=settings.host, port=port, static_dir=settings.static_dir)
    app_context = build_app_context(settings)
    server = NutritionHTTPServer((settings.host, settings.port), NutritionHandler, app_context)
    print(f"Nutrition app running on http://{settings.host}:{settings.port}")
    server.serve_forever()
