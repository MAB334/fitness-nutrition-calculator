from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from http import HTTPStatus
import json
from urllib.parse import parse_qs

from pydantic import ValidationError

from nutrition_app.core.config import load_settings
from nutrition_app.db.catalog import CatalogRepository
from nutrition_app.schemas.api import BulkResolveRequest, DaySummaryRequest
from nutrition_app.services.nutrition import NutritionService
from nutrition_app.services.portions import suggest_portions


@dataclass(frozen=True)
class ResponsePayload:
    status: int
    content_type: str
    body: bytes


@lru_cache(maxsize=1)
def get_services() -> tuple[CatalogRepository, NutritionService]:
    settings = load_settings()
    catalog = CatalogRepository(settings.db_path)
    nutrition = NutritionService(catalog)
    return catalog, nutrition


def json_response(payload: dict, status: HTTPStatus = HTTPStatus.OK) -> ResponsePayload:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return ResponsePayload(status=int(status), content_type="application/json; charset=utf-8", body=body)


def serialize_food(record) -> dict:
    payload = record.to_summary_dict()
    for key in ("energy_kcal_100g", "protein_g_100g", "fat_g_100g", "carb_g_100g", "fiber_g_100g", "sodium_mg_100g"):
        value = payload.get(key)
        if isinstance(value, float):
            payload[key] = round(value, 1)
    payload["portions"] = [option.to_dict() for option in suggest_portions(record)]
    return payload


def handle_health() -> ResponsePayload:
    return json_response({"ok": True})


def handle_food_search(query_string: str) -> ResponsePayload:
    params = parse_qs(query_string)
    query = params.get("q", [""])[0]
    try:
        limit = int(params.get("limit", ["12"])[0])
    except ValueError:
        limit = 12
    catalog, _ = get_services()
    items = [serialize_food(record) for record in catalog.search_foods(query, limit)]
    return json_response({"items": items, "query": query})


def handle_day_summary(raw_body: bytes) -> ResponsePayload:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        request_model = DaySummaryRequest.model_validate(payload)
        _, nutrition = get_services()
        summary = nutrition.build_day_summary(request_model)
    except json.JSONDecodeError:
        return json_response({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
    except ValidationError as exc:
        return json_response({"error": "Invalid request", "details": exc.errors()}, status=HTTPStatus.BAD_REQUEST)
    except LookupError as exc:
        return json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
    return json_response(summary)


def handle_bulk_resolve(raw_body: bytes) -> ResponsePayload:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        request_model = BulkResolveRequest.model_validate(payload)
        _, nutrition = get_services()
        resolved = nutrition.resolve_bulk_entries(request_model)
    except json.JSONDecodeError:
        return json_response({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
    except ValidationError as exc:
        return json_response({"error": "Invalid request", "details": exc.errors()}, status=HTTPStatus.BAD_REQUEST)
    return json_response(resolved)
