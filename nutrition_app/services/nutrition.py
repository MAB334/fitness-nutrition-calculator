from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
import re

from nutrition_app.db.catalog import CatalogRepository, FoodRecord
from nutrition_app.schemas.api import BulkResolveRequest, DaySummaryRequest, MealEntryInput, ProfileInput
from nutrition_app.services.portions import resolve_portion


ACTIVITY_FACTORS = {
    "low": 1.3,
    "moderate": 1.55,
    "high": 1.75,
}

GOAL_CALORIE_ADJUSTMENT = {
    "lose": -350,
    "maintain": 0,
    "gain": 250,
}

GOAL_PROTEIN_FACTOR = {
    "lose": 1.9,
    "maintain": 1.6,
    "gain": 1.8,
}

MEAL_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}

MEAL_ALIASES = {
    "早餐": "breakfast",
    "早饭": "breakfast",
    "早": "breakfast",
    "午餐": "lunch",
    "午饭": "lunch",
    "午": "lunch",
    "中餐": "lunch",
    "中饭": "lunch",
    "中": "lunch",
    "晚餐": "dinner",
    "晚饭": "dinner",
    "晚": "dinner",
    "加餐": "snack",
    "夜宵": "snack",
    "宵夜": "snack",
}

QUANTITY_TEXT_CHARS = "0123456789.０１２３４５６７８９．零〇一二两兩俩倆三四五六七八九十百千万半壹贰叁肆伍陆陸柒捌玖拾佰仟点點"
LINE_AMOUNT_RE = re.compile(
    rf"(?P<amount>[{re.escape(QUANTITY_TEXT_CHARS)}]+)\s*(?P<unit>[^{re.escape(QUANTITY_TEXT_CHARS)}\s]+)?\s*$"
)
ASCII_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９．", "0123456789.")
CHINESE_DIGIT_VALUES = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "兩": 2,
    "俩": 2,
    "倆": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "壹": 1,
    "贰": 2,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "陸": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
}
CHINESE_UNIT_VALUES = {
    "十": 10,
    "拾": 10,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
    "万": 10000,
    "萬": 10000,
}


def round1(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def multiply_per_100(value: float | None, grams: float) -> float:
    if value is None:
        return 0.0
    scaled = Decimal(str(value)) * Decimal(str(grams)) / Decimal("100")
    return float(scaled)


def normalize_quantity_text(value: str) -> str:
    return (
        value.strip()
        .translate(ASCII_DIGIT_TRANSLATION)
        .replace("兩", "两")
        .replace("俩", "两")
        .replace("倆", "两")
        .replace("點", ".")
        .replace("点", ".")
        .replace("．", ".")
        .lower()
    )


def parse_chinese_integer(text: str) -> int | None:
    if not text:
        return None
    total = 0
    section = 0
    number = 0
    seen = False
    for char in text:
        if char in CHINESE_DIGIT_VALUES:
            number = CHINESE_DIGIT_VALUES[char]
            seen = True
            continue
        if char in CHINESE_UNIT_VALUES:
            seen = True
            unit = CHINESE_UNIT_VALUES[char]
            if unit >= 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
            continue
        return None
    if not seen:
        return None
    return total + section + number


def parse_quantity_text(value: str) -> float | None:
    normalized = normalize_quantity_text(value)
    if not normalized:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return float(normalized)
    if normalized == "半":
        return 0.5
    if normalized.endswith("半"):
        base = parse_quantity_text(normalized[:-1])
        if base is not None:
            return base + 0.5
    if "." in normalized:
        left_text, right_text = normalized.split(".", 1)
        left_value = parse_quantity_text(left_text) if left_text else 0.0
        if left_value is None or int(left_value) != left_value:
            return None
        digits: list[str] = []
        for char in right_text:
            if char.isdigit():
                digits.append(char)
                continue
            if char in CHINESE_DIGIT_VALUES:
                digits.append(str(CHINESE_DIGIT_VALUES[char]))
                continue
            return None
        if not digits:
            return None
        return float(f"{int(left_value)}.{''.join(digits)}")
    integer_value = parse_chinese_integer(normalized)
    if integer_value is None:
        return None
    return float(integer_value)


@dataclass(frozen=True)
class MacroTotals:
    kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    fiber_g: float = 0.0
    sodium_mg: float = 0.0

    def to_dict(self) -> dict:
        return {key: round1(value) for key, value in asdict(self).items()}

    def add(self, other: "MacroTotals") -> "MacroTotals":
        return MacroTotals(
            kcal=self.kcal + other.kcal,
            protein_g=self.protein_g + other.protein_g,
            fat_g=self.fat_g + other.fat_g,
            carb_g=self.carb_g + other.carb_g,
            fiber_g=self.fiber_g + other.fiber_g,
            sodium_mg=self.sodium_mg + other.sodium_mg,
        )


def scale_food(food: FoodRecord, grams: float) -> MacroTotals:
    return MacroTotals(
        kcal=multiply_per_100(food.energy_kcal_100g, grams),
        protein_g=multiply_per_100(food.protein_g_100g, grams),
        fat_g=multiply_per_100(food.fat_g_100g, grams),
        carb_g=multiply_per_100(food.carb_g_100g, grams),
        fiber_g=multiply_per_100(food.fiber_g_100g, grams),
        sodium_mg=multiply_per_100(food.sodium_mg_100g, grams),
    )


def estimate_targets(profile: ProfileInput) -> dict:
    sex_offset = 5 if profile.sex == "male" else -161
    bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + sex_offset
    activity_factor = ACTIVITY_FACTORS[profile.activity_level]
    tdee = bmr * activity_factor
    target_kcal = max(1200.0, tdee + GOAL_CALORIE_ADJUSTMENT[profile.goal])
    protein_g = profile.weight_kg * GOAL_PROTEIN_FACTOR[profile.goal]
    fat_g = max(profile.weight_kg * 0.8, target_kcal * 0.25 / 9)
    carb_g = max(0.0, (target_kcal - protein_g * 4 - fat_g * 9) / 4)
    fiber_g = max(20.0, target_kcal / 1000 * 14)
    sodium_mg = 2300.0
    bmi = profile.weight_kg / ((profile.height_cm / 100) ** 2)
    return {
        "bmr": round1(bmr),
        "tdee": round1(tdee),
        "target_kcal": round1(target_kcal),
        "target_protein_g": round1(protein_g),
        "target_fat_g": round1(fat_g),
        "target_carb_g": round1(carb_g),
        "target_fiber_g": round1(fiber_g),
        "target_sodium_mg": round1(sodium_mg),
        "bmi": round1(bmi),
        "activity_factor": activity_factor,
    }


class NutritionService:
    def __init__(self, catalog: CatalogRepository) -> None:
        self.catalog = catalog

    def resolve_bulk_entries(self, payload: BulkResolveRequest) -> dict:
        resolved: list[dict] = []
        unresolved: list[dict] = []
        for raw_line in payload.text.splitlines():
            line = " ".join(raw_line.split())
            if not line:
                continue
            parsed = self._parse_bulk_line(line, payload.default_meal_type)
            matches = self.catalog.search_foods(parsed["query"], limit=5)
            if not matches:
                unresolved.append({"raw_line": raw_line, "reason": "没找到匹配食物"})
                continue
            best = matches[0]
            portion = resolve_portion(best, parsed["quantity"], unit_text=parsed["unit_text"])
            grams = portion.grams_per_unit * parsed["quantity"]
            resolved.append(
                {
                    "raw_line": raw_line,
                    "meal_type": parsed["meal_type"],
                    "meal_label": MEAL_LABELS[parsed["meal_type"]],
                    "quantity": round1(parsed["quantity"]),
                    "unit_key": portion.key,
                    "unit_label": portion.label,
                    "grams": round1(grams),
                    "query": parsed["query"],
                    "food": best.to_summary_dict(),
                    "alternatives": [item.to_summary_dict() for item in matches[1:3]],
                }
            )
        return {
            "resolved": resolved,
            "unresolved": unresolved,
        }

    def build_day_summary(self, payload: DaySummaryRequest) -> dict:
        targets = estimate_targets(payload.profile)
        meal_totals: dict[str, MacroTotals] = {key: MacroTotals() for key in MEAL_LABELS}
        meal_entries: dict[str, list[dict]] = {key: [] for key in MEAL_LABELS}
        daily_totals = MacroTotals()

        for entry in payload.entries:
            food = self.catalog.get_food(entry.source, entry.source_food_id)
            if food is None:
                raise LookupError(f"Food not found: {entry.source}/{entry.source_food_id}")
            grams = self._resolve_entry_grams(food, entry)
            line_totals = scale_food(food, grams)
            meal_totals[entry.meal_type] = meal_totals[entry.meal_type].add(line_totals)
            daily_totals = daily_totals.add(line_totals)
            meal_entries[entry.meal_type].append(self._build_entry_item(entry, food, line_totals, grams))

        differences = {
            "kcal": round1(daily_totals.kcal - targets["target_kcal"]),
            "protein_g": round1(daily_totals.protein_g - targets["target_protein_g"]),
            "fat_g": round1(daily_totals.fat_g - targets["target_fat_g"]),
            "carb_g": round1(daily_totals.carb_g - targets["target_carb_g"]),
            "fiber_g": round1(daily_totals.fiber_g - targets["target_fiber_g"]),
            "sodium_mg": round1(daily_totals.sodium_mg - targets["target_sodium_mg"]),
        }
        meals = [
            {
                "meal_type": meal_type,
                "label": MEAL_LABELS[meal_type],
                "totals": meal_totals[meal_type].to_dict(),
                "entries": meal_entries[meal_type],
            }
            for meal_type in ("breakfast", "lunch", "dinner", "snack")
        ]
        return {
            "profile": payload.profile.model_dump(),
            "targets": targets,
            "totals": daily_totals.to_dict(),
            "differences": differences,
            "meals": meals,
        }

    @staticmethod
    def _build_entry_item(entry: MealEntryInput, food: FoodRecord, line_totals: MacroTotals, grams: float) -> dict:
        return {
            "entry_id": entry.entry_id,
            "meal_type": entry.meal_type,
            "grams": round1(grams),
            "quantity": round1(entry.quantity) if entry.quantity is not None else None,
            "unit_label": entry.unit_label,
            "food": food.to_summary_dict(),
            "totals": line_totals.to_dict(),
        }

    @staticmethod
    def _parse_bulk_line(line: str, default_meal_type: str) -> dict:
        meal_type = default_meal_type
        remaining = line.strip()
        for alias, alias_meal_type in sorted(MEAL_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if remaining.startswith(alias):
                tail = remaining[len(alias):].lstrip(" :：-")
                if tail:
                    meal_type = alias_meal_type
                    remaining = tail
                    break

        amount_match = LINE_AMOUNT_RE.search(remaining)
        if amount_match is None:
            return {
                "meal_type": meal_type,
                "quantity": 1.0,
                "unit_text": "",
                "query": remaining.strip(" :：-"),
            }

        amount_text = amount_match.group("amount")
        unit_text = (amount_match.group("unit") or "").strip()
        query = remaining[: amount_match.start()].strip(" :：-")
        quantity = parse_quantity_text(amount_text)
        has_separator = amount_match.start() > 0 and remaining[amount_match.start() - 1].isspace()
        if quantity is None or (not unit_text and not has_separator):
            return {
                "meal_type": meal_type,
                "quantity": 1.0,
                "unit_text": "",
                "query": remaining.strip(" :：-"),
            }
        if not query:
            raise ValueError("未识别食物名")
        return {
            "meal_type": meal_type,
            "quantity": quantity,
            "unit_text": unit_text,
            "query": query,
        }

    @staticmethod
    def _resolve_entry_grams(food: FoodRecord, entry: MealEntryInput) -> float:
        if entry.grams is not None:
            return float(entry.grams)
        if entry.quantity is None:
            raise ValueError("Missing quantity")
        portion = resolve_portion(food, float(entry.quantity), unit_text=entry.unit_label, unit_key=entry.unit_key)
        return portion.grams_per_unit * float(entry.quantity)
