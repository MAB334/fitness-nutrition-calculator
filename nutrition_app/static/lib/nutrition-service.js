const CATALOG_PATH = "/static/data/catalog.min.json";

const FOOD_FIELDS = {
  source: 0,
  source_food_id: 1,
  name: 2,
  alias_name: 3,
  brand: 4,
  category_top: 5,
  category_sub: 6,
  food_type: 7,
  energy_kcal_100g: 8,
  protein_g_100g: 9,
  fat_g_100g: 10,
  carb_g_100g: 11,
  fiber_g_100g: 12,
  sodium_mg_100g: 13,
};

const ACTIVITY_FACTORS = {
  low: 1.3,
  moderate: 1.55,
  high: 1.75,
};

const GOAL_CALORIE_ADJUSTMENT = {
  lose: -350,
  maintain: 0,
  gain: 250,
};

const GOAL_PROTEIN_FACTOR = {
  lose: 1.9,
  maintain: 1.6,
  gain: 1.8,
};

const MEAL_LABELS = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

const MEAL_ALIASES = {
  早餐: "breakfast",
  早饭: "breakfast",
  早: "breakfast",
  午餐: "lunch",
  午饭: "lunch",
  午: "lunch",
  中餐: "lunch",
  中饭: "lunch",
  中: "lunch",
  晚餐: "dinner",
  晚饭: "dinner",
  晚: "dinner",
  加餐: "snack",
  夜宵: "snack",
  宵夜: "snack",
};

const COMMON_QUERY_EXPANSIONS = {
  鸡胸肉: ["鸡胸脯肉", "鸡肉", "鸡柳"],
  鸡蛋: ["蛋", "鸡蛋"],
  米饭: ["白米饭", "米饭(蒸)"],
  燕麦: ["燕麦片"],
  蛋白粉: ["乳清蛋白", "乳清蛋白粉"],
  无糖豆浆: ["豆浆"],
  希腊酸奶: ["酸奶"],
  全麦面包: ["面包", "吐司"],
  西红柿炒蛋: ["番茄炒蛋", "番茄鸡蛋", "西红柿鸡蛋"],
  番茄炒蛋: ["西红柿炒蛋", "西红柿鸡蛋", "番茄鸡蛋"],
  蛋炒饭: ["炒饭"],
  宫保鸡丁: ["宫保鸡丁饭"],
  麻婆豆腐: ["麻婆豆腐饭"],
};

const PROCESSED_KEYWORDS = [
  "干",
  "肠",
  "片",
  "卷",
  "条",
  "丸",
  "酱",
  "卤",
  "烧",
  "烤",
  "火腿",
  "汉堡",
  "饭团",
  "锅巴",
  "薯片",
  "饼干",
  "饮料",
  "奶茶",
  "味",
];

const PACKAGED_HINT_RE = /[0-9a-z]/i;

const WEIGHT_RE =
  /(?<value>\d+(?:\.\d+)?)\s*(?<unit>kg|KG|千克|公斤|g|G|克|ml|ML|毫升|l|L|升)/;

const SERVING_RE =
  /(?<count>\d+(?:\.\d+)?)\s*(?<label>个|枚|只|片|块|勺|条|杯|碗|盒|袋|瓶|份|支|包)(?:\s*\((?<grams>\d+(?:\.\d+)?)\s*(?:g|G|克|ml|ML|毫升)\))?/;

const QUANTITY_TEXT_CHARS =
  "0123456789.０１２３４５６７８９．零〇一二两兩俩三四五六七八九十百千万半壹贰叁肆伍陆陸柒捌玖拾佰仟点點";

const LINE_AMOUNT_RE = new RegExp(
  `(?<amount>[${escapeForCharacterClass(QUANTITY_TEXT_CHARS)}]+)\\s*(?<unit>[^${escapeForCharacterClass(
    QUANTITY_TEXT_CHARS,
  )}\\s]+)?\\s*$`,
);

const CHINESE_DIGIT_VALUES = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  兩: 2,
  俩: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  壹: 1,
  贰: 2,
  叁: 3,
  肆: 4,
  伍: 5,
  陆: 6,
  陸: 6,
  柒: 7,
  捌: 8,
  玖: 9,
};

const CHINESE_UNIT_VALUES = {
  十: 10,
  拾: 10,
  百: 100,
  佰: 100,
  千: 1000,
  仟: 1000,
  万: 10000,
};

const VIRTUAL_FOODS = [
  createVirtualFood({
    source_food_id: "recipe_tomato_egg",
    name: "番茄炒蛋",
    alias_name: "西红柿炒蛋 番茄鸡蛋 西红柿鸡蛋",
    category_top: "家常菜",
    category_sub: "热菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 108,
    protein_g_100g: 6.4,
    fat_g_100g: 7.1,
    carb_g_100g: 4.3,
    fiber_g_100g: 0.8,
    sodium_mg_100g: 210,
  }),
  createVirtualFood({
    source_food_id: "recipe_egg_fried_rice",
    name: "蛋炒饭",
    alias_name: "鸡蛋炒饭 家常蛋炒饭",
    category_top: "主食简餐",
    category_sub: "炒饭",
    food_type: "dish_recipe",
    energy_kcal_100g: 186,
    protein_g_100g: 5.8,
    fat_g_100g: 6.1,
    carb_g_100g: 26.8,
    fiber_g_100g: 0.7,
    sodium_mg_100g: 255,
  }),
  createVirtualFood({
    source_food_id: "recipe_mapo_tofu",
    name: "麻婆豆腐",
    alias_name: "家常麻婆豆腐",
    category_top: "家常菜",
    category_sub: "豆腐菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 126,
    protein_g_100g: 7.9,
    fat_g_100g: 8.3,
    carb_g_100g: 4.9,
    fiber_g_100g: 0.9,
    sodium_mg_100g: 365,
  }),
  createVirtualFood({
    source_food_id: "recipe_kung_pao_chicken",
    name: "宫保鸡丁",
    alias_name: "宫保鸡丁饭 家常宫保鸡丁",
    category_top: "家常菜",
    category_sub: "鸡肉菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 164,
    protein_g_100g: 12.6,
    fat_g_100g: 9.2,
    carb_g_100g: 7.5,
    fiber_g_100g: 0.8,
    sodium_mg_100g: 398,
  }),
  createVirtualFood({
    source_food_id: "recipe_green_pepper_pork",
    name: "青椒肉丝",
    alias_name: "青椒炒肉丝 尖椒肉丝",
    category_top: "家常菜",
    category_sub: "肉菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 143,
    protein_g_100g: 10.7,
    fat_g_100g: 9.1,
    carb_g_100g: 4.8,
    fiber_g_100g: 1.2,
    sodium_mg_100g: 310,
  }),
  createVirtualFood({
    source_food_id: "recipe_yuxiang_pork",
    name: "鱼香肉丝",
    alias_name: "家常鱼香肉丝",
    category_top: "家常菜",
    category_sub: "肉菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 152,
    protein_g_100g: 11.4,
    fat_g_100g: 8.9,
    carb_g_100g: 6.6,
    fiber_g_100g: 1,
    sodium_mg_100g: 335,
  }),
  createVirtualFood({
    source_food_id: "recipe_hot_sour_potato",
    name: "酸辣土豆丝",
    alias_name: "家常土豆丝 土豆丝",
    category_top: "家常菜",
    category_sub: "素菜",
    food_type: "dish_recipe",
    energy_kcal_100g: 92,
    protein_g_100g: 1.9,
    fat_g_100g: 3.8,
    carb_g_100g: 13.2,
    fiber_g_100g: 1.6,
    sodium_mg_100g: 225,
  }),
  createVirtualFood({
    source_food_id: "recipe_braised_beef_noodles",
    name: "红烧牛肉面",
    alias_name: "牛肉面 汤面",
    category_top: "面食",
    category_sub: "汤面",
    food_type: "dish_recipe",
    energy_kcal_100g: 137,
    protein_g_100g: 6.8,
    fat_g_100g: 4.9,
    carb_g_100g: 16.5,
    fiber_g_100g: 0.9,
    sodium_mg_100g: 320,
  }),
];

let catalogPromise = null;
let catalogState = null;

function createVirtualFood(food) {
  return finalizeFoodRecord({
    source: "virtual_recipe",
    brand: null,
    ...food,
  });
}

function escapeForCharacterClass(text) {
  return text.replace(/[\\\]\[]/g, "\\$&");
}

function normalizeSearchText(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function buildDisplayName(food) {
  if (food.brand && !String(food.name).includes(food.brand)) {
    return `${food.brand} ${food.name}`;
  }
  return food.name;
}

function finalizeFoodRecord(food) {
  const display_name = buildDisplayName(food);
  const record = {
    ...food,
    display_name,
  };
  record._name = normalizeSearchText(record.name);
  record._alias = normalizeSearchText(record.alias_name);
  record._brand = normalizeSearchText(record.brand);
  record._category = normalizeSearchText(record.category_top);
  return record;
}

function mapRowToFood(row) {
  const food = {
    source: row[FOOD_FIELDS.source],
    source_food_id: String(row[FOOD_FIELDS.source_food_id]),
    name: row[FOOD_FIELDS.name],
    alias_name: row[FOOD_FIELDS.alias_name],
    brand: row[FOOD_FIELDS.brand],
    category_top: row[FOOD_FIELDS.category_top],
    category_sub: row[FOOD_FIELDS.category_sub],
    food_type: row[FOOD_FIELDS.food_type],
    energy_kcal_100g: row[FOOD_FIELDS.energy_kcal_100g],
    protein_g_100g: row[FOOD_FIELDS.protein_g_100g],
    fat_g_100g: row[FOOD_FIELDS.fat_g_100g],
    carb_g_100g: row[FOOD_FIELDS.carb_g_100g],
    fiber_g_100g: row[FOOD_FIELDS.fiber_g_100g],
    sodium_mg_100g: row[FOOD_FIELDS.sodium_mg_100g],
  };
  return finalizeFoodRecord(food);
}

async function loadCatalogState() {
  if (!catalogPromise) {
    catalogPromise = fetch(CATALOG_PATH)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load catalog: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        const foods = payload.foods.map(mapRowToFood);
        const byId = new Map();
        for (const food of foods) {
          byId.set(buildFoodMarker(food.source, food.source_food_id), food);
        }
        for (const food of VIRTUAL_FOODS) {
          byId.set(buildFoodMarker(food.source, food.source_food_id), food);
        }
        const featured = [...foods]
          .sort((left, right) => {
            const leftType = defaultFoodTypeRank(left.food_type);
            const rightType = defaultFoodTypeRank(right.food_type);
            if (leftType !== rightType) {
              return leftType - rightType;
            }
            return (right.protein_g_100g || 0) - (left.protein_g_100g || 0) || left.display_name.localeCompare(right.display_name, "zh-CN");
          })
          .slice(0, 60);
        catalogState = { foods, byId, featured };
        return catalogState;
      });
  }
  return catalogPromise;
}

function buildFoodMarker(source, sourceFoodId) {
  return `${source}::${sourceFoodId}`;
}

function defaultFoodTypeRank(foodType) {
  return {
    basic_food: 0,
    dish_recipe: 1,
    packaged_food: 1,
    market_food: 2,
  }[foodType] ?? 3;
}

function expandQueryTerms(query) {
  const normalized = normalizeSearchText(query);
  if (!normalized) {
    return [];
  }
  const terms = [normalized];
  for (const [key, expansions] of Object.entries(COMMON_QUERY_EXPANSIONS)) {
    if (normalized === key || normalized.includes(key)) {
      terms.push(...expansions);
    }
  }
  if (normalized.endsWith("片") && normalized.length > 1) {
    terms.push(normalized.slice(0, -1));
  }
  if (normalized.startsWith("无糖") && normalized.length > 2) {
    terms.push(normalized.slice(2));
  }
  return [...new Set(terms.map(normalizeSearchText).filter(Boolean))];
}

function hasPackagedQueryIntent(query) {
  return PACKAGED_HINT_RE.test(normalizeSearchText(query));
}

function hasProcessedQueryIntent(query) {
  const normalized = normalizeSearchText(query);
  return PROCESSED_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

function recordHasProcessedHint(record) {
  const haystack = [record.name, record.alias_name, record.brand, record.category_top, record.category_sub]
    .filter(Boolean)
    .join(" ");
  return PROCESSED_KEYWORDS.some((keyword) => haystack.includes(keyword));
}

function matchRank(record, query, expandedTerms) {
  if (record._name === query) return 0;
  if (record._alias === query) return 1;
  if (record._name.startsWith(query)) return 2;
  if (record._alias.startsWith(query)) return 3;
  if (query && record._name.includes(query)) return 4;
  if (query && record._alias.includes(query)) return 5;
  for (const term of expandedTerms.slice(1)) {
    if (record._name === term) return 6;
    if (record._name.startsWith(term)) return 7;
    if (record._name.includes(term)) return 8;
    if (record._alias.includes(term)) return 9;
  }
  if (query && record._brand.includes(query)) return 10;
  if (query && record._category.includes(query)) return 11;
  return 12;
}

function buildSearchSortKey(record, normalizedQuery, expandedTerms) {
  const packagedIntent = hasPackagedQueryIntent(normalizedQuery);
  const processedQueryIntent = hasProcessedQueryIntent(normalizedQuery);
  const rank = matchRank(record, normalizedQuery, expandedTerms);

  let expandedBasicRank = 1;
  if (!packagedIntent && !processedQueryIntent && record.food_type === "basic_food") {
    for (const term of expandedTerms.slice(1)) {
      if (
        record._name === term ||
        record._alias === term ||
        record._name.startsWith(term) ||
        record._alias.startsWith(term)
      ) {
        expandedBasicRank = 0;
        break;
      }
    }
  }

  let foodTypeRank = defaultFoodTypeRank(record.food_type);
  if (packagedIntent && record.brand && normalizeSearchText(record.display_name).includes(normalizedQuery)) {
    foodTypeRank = Math.max(0, foodTypeRank - 1);
  }
  const processedRank = packagedIntent || processedQueryIntent ? 0 : Number(recordHasProcessedHint(record));
  const sourceRank = record.source === "chinanutri_fq" ? 0 : 1;
  const nameLengthRank =
    normalizedQuery && normalizeSearchText(record.display_name).includes(normalizedQuery)
      ? Math.abs(record.display_name.length - normalizedQuery.length)
      : record.display_name.length;

  return [
    expandedBasicRank,
    rank,
    foodTypeRank,
    processedRank,
    sourceRank,
    nameLengthRank,
    -(record.protein_g_100g || 0),
    record.energy_kcal_100g || 0,
    record.display_name,
  ];
}

function compareSortKeys(left, right) {
  const size = Math.max(left.length, right.length);
  for (let index = 0; index < size; index += 1) {
    const leftValue = left[index];
    const rightValue = right[index];
    if (leftValue === rightValue) {
      continue;
    }
    return leftValue < rightValue ? -1 : 1;
  }
  return 0;
}

function round1(value) {
  return Math.round(Number(value || 0) * 10) / 10;
}

function toFoodSummary(food) {
  return {
    source: food.source,
    source_food_id: food.source_food_id,
    name: food.name,
    alias_name: food.alias_name,
    brand: food.brand,
    category_top: food.category_top,
    category_sub: food.category_sub,
    food_type: food.food_type,
    energy_kcal_100g: round1(food.energy_kcal_100g),
    protein_g_100g: round1(food.protein_g_100g),
    fat_g_100g: round1(food.fat_g_100g),
    carb_g_100g: round1(food.carb_g_100g),
    fiber_g_100g: round1(food.fiber_g_100g),
    sodium_mg_100g: round1(food.sodium_mg_100g),
    display_name: food.display_name,
    portions: suggestPortions(food).map(toPortionSummary),
  };
}

export async function warmupCatalog() {
  await loadCatalogState();
}

export async function searchFoods(query, limit = 12) {
  const catalog = await loadCatalogState();
  const safeLimit = Math.max(1, Math.min(50, Number(limit) || 12));
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return catalog.featured.slice(0, safeLimit).map(toFoodSummary);
  }

  const expandedTerms = expandQueryTerms(normalizedQuery);
  const matches = [];
  const seen = new Set();

  const pushMatch = (food) => {
    const marker = buildFoodMarker(food.source, food.source_food_id);
    if (seen.has(marker)) {
      return;
    }
    seen.add(marker);
    matches.push(food);
  };

  for (const food of catalog.foods) {
    if (
      expandedTerms.some(
        (term) =>
          (food._name && food._name.includes(term)) ||
          (food._alias && food._alias.includes(term)) ||
          (food._brand && food._brand.includes(term)) ||
          (food._category && food._category.includes(term)),
      )
    ) {
      pushMatch(food);
    }
  }

  for (const food of VIRTUAL_FOODS) {
    if (
      expandedTerms.some(
        (term) =>
          food._name.includes(term) ||
          food._alias.includes(term) ||
          food._brand.includes(term) ||
          food._category.includes(term),
      )
    ) {
      pushMatch(food);
    }
  }

  matches.sort((left, right) =>
    compareSortKeys(buildSearchSortKey(left, normalizedQuery, expandedTerms), buildSearchSortKey(right, normalizedQuery, expandedTerms)),
  );

  return matches.slice(0, safeLimit).map(toFoodSummary);
}

export async function getFood(source, sourceFoodId) {
  const catalog = await loadCatalogState();
  return catalog.byId.get(buildFoodMarker(source, String(sourceFoodId))) || null;
}

function normalizeWeightToGrams(value, unit) {
  if (["kg", "KG", "千克", "公斤", "l", "L", "升"].includes(unit)) {
    return value * 1000;
  }
  return value;
}

function extractWeightGrams(text) {
  if (!text) {
    return null;
  }
  const match = String(text).match(WEIGHT_RE);
  if (!match) {
    return null;
  }
  return normalizeWeightToGrams(Number(match.groups.value), match.groups.unit);
}

function inferPackageLabel(food) {
  const text = [food.name, food.category_sub, food.category_top, food.brand].filter(Boolean).join(" ").toLowerCase();
  if (["奶", "饮料", "果汁", "豆浆", "酸奶", "咖啡", "水"].some((token) => text.includes(token))) {
    if (text.includes("瓶")) return "瓶";
    if (text.includes("袋")) return "袋";
    return "盒";
  }
  if (["面包", "吐司", "饼干", "麦片", "燕麦", "蛋白粉", "米糊", "藕粉", "坚果"].some((token) => text.includes(token))) {
    return text.includes("袋") ? "袋" : "包";
  }
  return "份";
}

function inferNamePortions(food) {
  const text = [food.name, food.category_top, food.category_sub, food.brand].filter(Boolean).join(" ");
  const options = [];
  const add = (key, label, grams_per_unit, aliases = []) => {
    options.push({ key, label, grams_per_unit, aliases });
  };

  if (food.food_type === "dish_recipe") {
    add("serving", "份", 180, ["盘"]);
    if (["饭", "面", "粉", "粥", "汤"].some((token) => text.includes(token))) {
      add("bowl", "碗", 260, []);
    }
  }

  if (text.includes("鸡蛋") || food.name === "蛋") {
    add("piece", "个", 50, ["枚", "只"]);
  }
  if (["米饭", "粥", "面条", "粉", "炒饭", "盖饭"].some((token) => text.includes(token))) {
    add("bowl", "碗", 150, []);
  }
  if (["燕麦", "麦片"].some((token) => text.includes(token))) {
    add("bowl", "碗", 40, []);
  }
  if (["燕麦", "麦片", "米糊", "藕粉", "蛋白粉", "乳清", "增肌粉", "豆奶粉", "奶粉"].some((token) => text.includes(token))) {
    add("scoop", "勺", 10, ["匙"]);
    add("serving", "份", 30, ["包"]);
  }
  if (["牛奶", "豆浆", "酸奶", "果汁", "饮料", "咖啡", "椰子水"].some((token) => text.includes(token))) {
    add("cup", "杯", 250, ["盒", "瓶"]);
  }
  if (["面包", "吐司"].some((token) => text.includes(token))) {
    add("slice", "片", 35, []);
    add("piece", "个", 70, []);
  }
  if (["鸡胸", "牛排", "豆腐", "鱼排", "虾仁"].some((token) => text.includes(token))) {
    add("serving", "份", 120, ["块", "包"]);
  }
  if (["坚果", "花生", "杏仁", "核桃"].some((token) => text.includes(token))) {
    add("handful", "把", 25, []);
    add("bag", "袋", 30, ["包"]);
  }
  if (["苹果", "香蕉", "橙", "梨"].some((token) => text.includes(token))) {
    add("piece", "个", 150, []);
  }
  return options;
}

function parseSourceSpecificPortions(food) {
  const options = [];
  const categorySub = String(food.category_sub || "");
  const servingMatch = categorySub.match(SERVING_RE);
  if (servingMatch && servingMatch.groups.grams) {
    const count = Number(servingMatch.groups.count);
    const gramsPerUnit = Number(servingMatch.groups.grams) / Math.max(count, 1);
    const label = servingMatch.groups.label;
    options.push({
      key: `serving:${label}`,
      label,
      grams_per_unit: gramsPerUnit,
      aliases: label === "份" ? [] : ["份"],
    });
    return options;
  }

  const sizeGrams = extractWeightGrams(categorySub);
  if (sizeGrams) {
    const label = inferPackageLabel(food);
    options.push({
      key: `package:${label}`,
      label,
      grams_per_unit: sizeGrams,
      aliases: ["份"],
    });
  }
  return options;
}

function dedupePortions(options) {
  const seen = new Set();
  const deduped = [];
  for (const option of options) {
    const marker = `${option.key}:${Math.round(option.grams_per_unit)}`;
    if (seen.has(marker)) {
      continue;
    }
    seen.add(marker);
    deduped.push(option);
  }
  return deduped;
}

function suggestPortions(food) {
  const options = [...parseSourceSpecificPortions(food), ...inferNamePortions(food)];
  if (!options.length) {
    options.push({
      key: "serving",
      label: "份",
      grams_per_unit: 100,
      aliases: ["个", "包", "盒"],
    });
  }
  if (!options.some((item) => item.key === "gram")) {
    options.push({
      key: "gram",
      label: "克",
      grams_per_unit: 1,
      aliases: ["g", "G"],
    });
  }
  return dedupePortions(options);
}

function toPortionSummary(portion) {
  return {
    key: portion.key,
    label: portion.label,
    grams_per_unit: round1(portion.grams_per_unit),
    aliases: [...portion.aliases],
  };
}

function resolvePortion(food, quantity, { unitText = null, unitKey = null } = {}) {
  void quantity;
  const options = suggestPortions(food);
  if (unitKey) {
    const exact = options.find((item) => item.key === unitKey);
    if (exact) {
      return exact;
    }
  }
  const normalized = String(unitText || "").trim();
  if (normalized) {
    const exact = options.find((item) => item.label === normalized || item.aliases.includes(normalized));
    if (exact) {
      return exact;
    }
    if (["克", "g", "G"].includes(normalized)) {
      return { key: "gram", label: "克", grams_per_unit: 1, aliases: ["g", "G"] };
    }
  }
  return options[0];
}

function normalizeQuantityText(value) {
  return String(value || "")
    .trim()
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 65248))
    .replace(/．/g, ".")
    .replace(/[兩俩]/g, "两")
    .replace(/[點点]/g, ".")
    .toLowerCase();
}

function parseChineseInteger(text) {
  if (!text) {
    return null;
  }
  let total = 0;
  let section = 0;
  let number = 0;
  let seen = false;
  for (const char of text) {
    if (Object.hasOwn(CHINESE_DIGIT_VALUES, char)) {
      number = CHINESE_DIGIT_VALUES[char];
      seen = true;
      continue;
    }
    if (Object.hasOwn(CHINESE_UNIT_VALUES, char)) {
      seen = true;
      const unit = CHINESE_UNIT_VALUES[char];
      if (unit >= 10000) {
        section = (section + number) * unit;
        total += section;
        section = 0;
      } else {
        section += (number || 1) * unit;
      }
      number = 0;
      continue;
    }
    return null;
  }
  return seen ? total + section + number : null;
}

export function parseQuantityText(value) {
  const normalized = normalizeQuantityText(value);
  if (!normalized) {
    return Number.NaN;
  }
  if (/^\d+(?:\.\d+)?$/.test(normalized)) {
    return Number(normalized);
  }
  if (normalized === "半") {
    return 0.5;
  }
  if (normalized.endsWith("半")) {
    const base = parseQuantityText(normalized.slice(0, -1));
    if (Number.isFinite(base)) {
      return base + 0.5;
    }
  }
  if (normalized.includes(".")) {
    const [leftText, rightText] = normalized.split(".", 2);
    const leftValue = leftText ? parseQuantityText(leftText) : 0;
    if (!Number.isFinite(leftValue) || !Number.isInteger(leftValue)) {
      return Number.NaN;
    }
    const digits = [];
    for (const char of rightText) {
      if (/\d/.test(char)) {
        digits.push(char);
        continue;
      }
      if (Object.hasOwn(CHINESE_DIGIT_VALUES, char)) {
        digits.push(String(CHINESE_DIGIT_VALUES[char]));
        continue;
      }
      return Number.NaN;
    }
    return digits.length ? Number(`${leftValue}.${digits.join("")}`) : Number.NaN;
  }
  const integerValue = parseChineseInteger(normalized);
  return integerValue === null ? Number.NaN : integerValue;
}

function multiplyPer100(value, grams) {
  if (value === null || value === undefined) {
    return 0;
  }
  return (Number(value) * Number(grams)) / 100;
}

function emptyTotals() {
  return {
    kcal: 0,
    protein_g: 0,
    fat_g: 0,
    carb_g: 0,
    fiber_g: 0,
    sodium_mg: 0,
  };
}

function addTotals(target, addition) {
  target.kcal += addition.kcal;
  target.protein_g += addition.protein_g;
  target.fat_g += addition.fat_g;
  target.carb_g += addition.carb_g;
  target.fiber_g += addition.fiber_g;
  target.sodium_mg += addition.sodium_mg;
}

function scaleFood(food, grams) {
  return {
    kcal: multiplyPer100(food.energy_kcal_100g, grams),
    protein_g: multiplyPer100(food.protein_g_100g, grams),
    fat_g: multiplyPer100(food.fat_g_100g, grams),
    carb_g: multiplyPer100(food.carb_g_100g, grams),
    fiber_g: multiplyPer100(food.fiber_g_100g, grams),
    sodium_mg: multiplyPer100(food.sodium_mg_100g, grams),
  };
}

function serializeTotals(totals) {
  return {
    kcal: round1(totals.kcal),
    protein_g: round1(totals.protein_g),
    fat_g: round1(totals.fat_g),
    carb_g: round1(totals.carb_g),
    fiber_g: round1(totals.fiber_g),
    sodium_mg: round1(totals.sodium_mg),
  };
}

function estimateTargets(profile) {
  const sexOffset = profile.sex === "male" ? 5 : -161;
  const bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + sexOffset;
  const activityFactor = ACTIVITY_FACTORS[profile.activity_level];
  const tdee = bmr * activityFactor;
  const target_kcal = Math.max(1200, tdee + GOAL_CALORIE_ADJUSTMENT[profile.goal]);
  const target_protein_g = profile.weight_kg * GOAL_PROTEIN_FACTOR[profile.goal];
  const target_fat_g = Math.max(profile.weight_kg * 0.8, (target_kcal * 0.25) / 9);
  const target_carb_g = Math.max(0, (target_kcal - target_protein_g * 4 - target_fat_g * 9) / 4);
  const target_fiber_g = Math.max(20, (target_kcal / 1000) * 14);
  const target_sodium_mg = 2300;
  const bmi = profile.weight_kg / (profile.height_cm / 100) ** 2;
  return {
    bmr: round1(bmr),
    tdee: round1(tdee),
    target_kcal: round1(target_kcal),
    target_protein_g: round1(target_protein_g),
    target_fat_g: round1(target_fat_g),
    target_carb_g: round1(target_carb_g),
    target_fiber_g: round1(target_fiber_g),
    target_sodium_mg: round1(target_sodium_mg),
    bmi: round1(bmi),
    activity_factor: activityFactor,
  };
}

function parseBulkLine(line, defaultMealType) {
  let meal_type = defaultMealType;
  let remaining = String(line || "").trim();

  for (const [alias, nextMealType] of Object.entries(MEAL_ALIASES).sort((left, right) => right[0].length - left[0].length)) {
    if (remaining.startsWith(alias)) {
      const tail = remaining.slice(alias.length).replace(/^[\s:：]+/, "");
      if (tail) {
        meal_type = nextMealType;
        remaining = tail;
        break;
      }
    }
  }

  const amountMatch = remaining.match(LINE_AMOUNT_RE);
  if (!amountMatch) {
    return {
      meal_type,
      quantity: 1,
      unit_text: "",
      query: remaining.replace(/^[\s:：]+|[\s:：]+$/g, ""),
    };
  }

  const amountText = amountMatch.groups.amount;
  const unitText = String(amountMatch.groups.unit || "").trim();
  const query = remaining.slice(0, amountMatch.index).replace(/^[\s:：]+|[\s:：]+$/g, "");
  const quantity = parseQuantityText(amountText);
  const hasSeparator = amountMatch.index > 0 && /\s/.test(remaining[amountMatch.index - 1]);

  if (!Number.isFinite(quantity) || (!unitText && !hasSeparator)) {
    return {
      meal_type,
      quantity: 1,
      unit_text: "",
      query: remaining.replace(/^[\s:：]+|[\s:：]+$/g, ""),
    };
  }
  if (!query) {
    throw new Error("未识别到食物名称");
  }

  return {
    meal_type,
    quantity,
    unit_text: unitText,
    query,
  };
}

export async function resolveBulkEntries(payload) {
  const resolved = [];
  const unresolved = [];

  for (const rawLine of String(payload.text || "").split(/\r?\n/)) {
    const line = rawLine.trim().replace(/\s+/g, " ");
    if (!line) {
      continue;
    }
    try {
      const parsed = parseBulkLine(line, payload.default_meal_type || "breakfast");
      const matches = await searchFoods(parsed.query, 5);
      if (!matches.length) {
        unresolved.push({ raw_line: rawLine, reason: "没找到匹配食物" });
        continue;
      }
      const best = matches[0];
      const portion = resolvePortion(best, parsed.quantity, { unitText: parsed.unit_text });
      const grams = portion.grams_per_unit * parsed.quantity;
      resolved.push({
        raw_line: rawLine,
        meal_type: parsed.meal_type,
        meal_label: MEAL_LABELS[parsed.meal_type],
        quantity: round1(parsed.quantity),
        unit_key: portion.key,
        unit_label: portion.label,
        grams: round1(grams),
        query: parsed.query,
        food: toFoodSummary(best),
        alternatives: matches.slice(1, 3),
      });
    } catch (error) {
      unresolved.push({ raw_line: rawLine, reason: error instanceof Error ? error.message : "解析失败" });
    }
  }

  return { resolved, unresolved };
}

function resolveEntryGrams(food, entry) {
  if (entry.grams !== null && entry.grams !== undefined) {
    return Number(entry.grams);
  }
  const quantity = Number(entry.quantity);
  if (!Number.isFinite(quantity) || quantity <= 0) {
    throw new Error("Missing quantity");
  }
  const portion = resolvePortion(food, quantity, { unitText: entry.unit_label, unitKey: entry.unit_key });
  return portion.grams_per_unit * quantity;
}

export async function buildDaySummary(payload) {
  const profile = payload.profile;
  const entries = Array.isArray(payload.entries) ? payload.entries : [];
  const targets = estimateTargets(profile);
  const mealTotals = {
    breakfast: emptyTotals(),
    lunch: emptyTotals(),
    dinner: emptyTotals(),
    snack: emptyTotals(),
  };
  const mealEntries = {
    breakfast: [],
    lunch: [],
    dinner: [],
    snack: [],
  };
  const totals = emptyTotals();

  for (const entry of entries) {
    const food = await getFood(entry.source, entry.source_food_id);
    if (!food) {
      throw new Error(`Food not found: ${entry.source}/${entry.source_food_id}`);
    }
    const grams = resolveEntryGrams(food, entry);
    const lineTotals = scaleFood(food, grams);
    addTotals(mealTotals[entry.meal_type], lineTotals);
    addTotals(totals, lineTotals);
    mealEntries[entry.meal_type].push({
      entry_id: entry.entry_id,
      meal_type: entry.meal_type,
      grams: round1(grams),
      quantity: entry.quantity === null || entry.quantity === undefined ? null : round1(entry.quantity),
      unit_label: entry.unit_label || null,
      food: toFoodSummary(food),
      totals: serializeTotals(lineTotals),
    });
  }

  const serializedTotals = serializeTotals(totals);
  const differences = {
    kcal: round1(serializedTotals.kcal - targets.target_kcal),
    protein_g: round1(serializedTotals.protein_g - targets.target_protein_g),
    fat_g: round1(serializedTotals.fat_g - targets.target_fat_g),
    carb_g: round1(serializedTotals.carb_g - targets.target_carb_g),
    fiber_g: round1(serializedTotals.fiber_g - targets.target_fiber_g),
    sodium_mg: round1(serializedTotals.sodium_mg - targets.target_sodium_mg),
  };

  return {
    profile,
    targets,
    totals: serializedTotals,
    differences,
    meals: ["breakfast", "lunch", "dinner", "snack"].map((mealType) => ({
      meal_type: mealType,
      label: MEAL_LABELS[mealType],
      totals: serializeTotals(mealTotals[mealType]),
      entries: mealEntries[mealType],
    })),
  };
}
