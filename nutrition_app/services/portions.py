from __future__ import annotations

from dataclasses import dataclass
import re

from nutrition_app.db.catalog import FoodRecord


WEIGHT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|KG|千克|公斤|g|G|克|ml|ML|毫升|l|L|升)")
SERVING_RE = re.compile(
    r"(?P<count>\d+(?:\.\d+)?)\s*(?P<label>个|枚|只|片|块|勺|杯|盒|袋|包|瓶|碗|份|桶|支|根|条|颗)"
    r"(?:\s*\((?P<grams>\d+(?:\.\d+)?)\s*(?:g|G|克|ml|ML|毫升)\))?"
)


@dataclass(frozen=True)
class PortionOption:
    key: str
    label: str
    grams_per_unit: float
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "grams_per_unit": round(self.grams_per_unit, 1),
            "aliases": list(self.aliases),
        }


def normalize_weight_to_grams(value: float, unit: str) -> float:
    if unit in {"kg", "KG", "千克", "公斤", "l", "L", "升"}:
        return value * 1000
    return value


def extract_weight_grams(text: str | None) -> float | None:
    if not text:
        return None
    match = WEIGHT_RE.search(text)
    if not match:
        return None
    return normalize_weight_to_grams(float(match.group("value")), match.group("unit"))


def infer_package_label(food: FoodRecord) -> str:
    text = " ".join(filter(None, [food.name, food.category_sub, food.category_top, food.brand])).lower()
    if any(token in text for token in ("奶", "饮料", "果汁", "豆浆", "酸奶", "咖啡", "水")):
        if "瓶" in text:
            return "瓶"
        if "袋" in text:
            return "袋"
        return "盒"
    if any(token in text for token in ("面包", "吐司", "饼干", "麦片", "燕麦", "蛋白粉", "米糊", "藕粉", "坚果")):
        return "袋" if "袋" in text else "包"
    return "份"


def infer_name_portions(food: FoodRecord) -> list[PortionOption]:
    text = " ".join(filter(None, [food.name, food.category_top, food.category_sub, food.brand]))
    options: list[PortionOption] = []

    def add(key: str, label: str, grams_per_unit: float, aliases: tuple[str, ...] = ()) -> None:
        options.append(PortionOption(key=key, label=label, grams_per_unit=grams_per_unit, aliases=aliases))

    if food.food_type == "dish_recipe":
        add("serving", "份", 180, ("盘",))
        if any(token in text for token in ("饭", "面", "粉", "粥", "汤")):
            add("bowl", "碗", 260)

    if "鸡蛋" in text or food.name == "蛋":
        add("piece", "个", 50, ("枚", "只"))
    if any(token in text for token in ("米饭", "粥", "面条", "粉", "炒饭", "盖饭")):
        add("bowl", "碗", 150)
    if any(token in text for token in ("燕麦", "麦片")):
        add("bowl", "碗", 40)
    if any(token in text for token in ("燕麦", "麦片", "米糊", "藕粉", "蛋白粉", "乳清", "增肌粉", "豆奶粉", "奶粉")):
        add("scoop", "勺", 10, ("匙",))
        add("serving", "份", 30, ("包",))
    if any(token in text for token in ("牛奶", "豆浆", "酸奶", "果汁", "饮料", "咖啡", "椰子水")):
        add("cup", "杯", 250, ("盒", "瓶"))
    if any(token in text for token in ("面包", "吐司")):
        add("slice", "片", 35)
        add("piece", "个", 70)
    if any(token in text for token in ("鸡胸", "牛排", "豆腐", "鱼排", "虾仁")):
        add("serving", "份", 120, ("块", "包"))
    if any(token in text for token in ("坚果", "花生", "杏仁", "核桃")):
        add("handful", "把", 25)
        add("bag", "袋", 30, ("包",))
    if any(token in text for token in ("苹果", "香蕉", "橙", "梨")):
        add("piece", "个", 150)
    return options


def parse_source_specific_portions(food: FoodRecord) -> list[PortionOption]:
    options: list[PortionOption] = []
    category_sub = food.category_sub or ""

    for match in SERVING_RE.finditer(category_sub):
        count = float(match.group("count"))
        label = match.group("label")
        grams = match.group("grams")
        if grams:
            grams_per_unit = float(grams) / max(count, 1)
            key = f"serving:{label}"
            aliases = ("份",) if label != "份" else ()
            options.append(PortionOption(key=key, label=label, grams_per_unit=grams_per_unit, aliases=aliases))
            return options

    size_grams = extract_weight_grams(category_sub)
    if size_grams:
        package_label = infer_package_label(food)
        options.append(PortionOption(key=f"package:{package_label}", label=package_label, grams_per_unit=size_grams, aliases=("份",)))
    return options


def dedupe_portions(options: list[PortionOption]) -> list[PortionOption]:
    deduped: list[PortionOption] = []
    seen: set[tuple[str, int]] = set()
    for option in options:
        marker = (option.key, round(option.grams_per_unit))
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(option)
    return deduped


def suggest_portions(food: FoodRecord) -> list[PortionOption]:
    options = parse_source_specific_portions(food) + infer_name_portions(food)
    if not options:
        options = [PortionOption(key="serving", label="份", grams_per_unit=100, aliases=("个", "包", "盒"))]
    if not any(option.key == "gram" for option in options):
        options.append(PortionOption(key="gram", label="克", grams_per_unit=1, aliases=("g",)))
    return dedupe_portions(options)


def resolve_portion(food: FoodRecord, quantity: float, unit_text: str | None = None, unit_key: str | None = None) -> PortionOption:
    del quantity
    options = suggest_portions(food)
    if unit_key:
        for option in options:
            if option.key == unit_key:
                return option
    normalized = (unit_text or "").strip()
    if normalized:
        for option in options:
            if normalized == option.label or normalized in option.aliases:
                return option
        if normalized in {"克", "g", "G"}:
            return PortionOption(key="gram", label="克", grams_per_unit=1, aliases=("g",))
    return options[0]
