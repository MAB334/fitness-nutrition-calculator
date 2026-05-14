import {
  buildDaySummary,
  getFood,
  parseQuantityText,
  resolveBulkEntries,
  searchFoods,
  warmupCatalog,
} from "/static/lib/nutrition-service.js";

const storageKeys = {
  profile: "nutrition-profile",
  entries: "nutrition-entries",
  profileCollapsed: "nutrition-profile-collapsed",
};

const state = {
  profile: {
    sex: "male",
    age: 28,
    height_cm: 170,
    weight_kg: 65,
    activity_level: "moderate",
    goal: "maintain",
  },
  entries: [],
  selectedFood: null,
  editingEntryId: null,
  profileCollapsed: false,
};

const profileCard = document.getElementById("profile-card");
const profileBody = document.getElementById("profile-body");
const profileSummary = document.getElementById("profile-summary");
const profileSummaryText = document.getElementById("profile-summary-text");
const profileStorageNote = document.getElementById("profile-storage-note");
const profileForm = document.getElementById("profile-form");
const searchInput = document.getElementById("food-search-input");
const searchBtn = document.getElementById("food-search-btn");
const searchResults = document.getElementById("search-results");
const recentFoods = document.getElementById("recent-foods");
const commonFoods = document.getElementById("common-foods");
const recentFoodCount = document.getElementById("recent-food-count");
const commonFoodCount = document.getElementById("common-food-count");
const selectedFoodPanel = document.getElementById("selected-food-panel");
const selectedFoodStateLabel = document.getElementById("selected-food-state-label");
const selectedFoodName = document.getElementById("selected-food-name");
const selectedFoodMeta = document.getElementById("selected-food-meta");
const selectedPortionHint = document.getElementById("selected-portion-hint");
const mealTypeSelect = document.getElementById("meal-type-select");
const foodQuantityInput = document.getElementById("food-quantity-input");
const foodUnitSelect = document.getElementById("food-unit-select");
const addFoodBtn = document.getElementById("add-food-btn");
const cancelEditBtn = document.getElementById("cancel-edit-btn");
const summaryMetrics = document.getElementById("summary-metrics");
const targetMetrics = document.getElementById("target-metrics");
const mealGroups = document.getElementById("meal-groups");
const entriesCount = document.getElementById("entries-count");
const saveProfileBtn = document.getElementById("save-profile-btn");
const toggleProfileBtn = document.getElementById("toggle-profile-btn");
const clearEntriesBtn = document.getElementById("clear-entries-btn");
const bulkInput = document.getElementById("bulk-input");
const bulkAddBtn = document.getElementById("bulk-add-btn");
const bulkDefaultMealSelect = document.getElementById("bulk-default-meal-select");
const bulkFeedback = document.getElementById("bulk-feedback");
const bulkPreview = document.getElementById("bulk-preview");
const heroGoalBadge = document.getElementById("hero-goal-badge");
const heroStatus = document.getElementById("hero-status");
const heroKpis = document.getElementById("hero-kpis");
const heroOrbValue = document.getElementById("hero-orb-value");
const heroOrbNote = document.getElementById("hero-orb-note");
const progressList = document.getElementById("progress-list");

function createFallbackPortions(entry) {
  const portions = [];
  if (entry.quantity && entry.unit_label && entry.grams) {
    portions.push({
      key: entry.unit_key || `saved:${entry.unit_label}`,
      label: entry.unit_label,
      grams_per_unit: Number(entry.grams) / Number(entry.quantity),
      aliases: [],
    });
  }
  if (!portions.some((item) => item.key === "gram")) {
    portions.push({ key: "gram", label: "克", grams_per_unit: 1, aliases: ["g", "G"] });
  }
  return portions;
}

function hydratePreview(preview, entry = {}) {
  if (!preview) {
    return null;
  }
  const hydrated = { ...preview };
  if (!Array.isArray(hydrated.portions) || !hydrated.portions.length) {
    hydrated.portions = createFallbackPortions(entry);
  }
  return hydrated;
}

function buildEntryId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `entry-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0";
  }
  return Number(value).toFixed(1).replace(/\.0$/, "");
}

function formatDiff(value, unit) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return `0 ${unit}`;
  }
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : ""}${formatNumber(numeric)} ${unit}`;
}

function goalLabel(goal) {
  return {
    lose: "减脂期",
    maintain: "维持期",
    gain: "增肌期",
  }[goal] || "今日目标";
}

function activityLabel(level) {
  return {
    low: "活动偏低",
    moderate: "活动中等",
    high: "活动偏高",
  }[level] || "活动未设置";
}

function mealLabel(mealType) {
  return {
    breakfast: "早餐",
    lunch: "午餐",
    dinner: "晚餐",
    snack: "加餐",
  }[mealType] || mealType;
}

function prettyFoodType(foodType) {
  return {
    basic_food: "基础食材",
    dish_recipe: "家常菜",
    packaged_food: "包装食品",
    market_food: "商品食物",
  }[foodType] || foodType;
}

function compactCategoryLabel(category) {
  const raw = String(category || "").trim();
  if (!raw) {
    return "";
  }
  const primary = raw.split("-")[0].split("/")[0].trim();
  return primary.length <= 10 ? primary : `${primary.slice(0, 10)}...`;
}

function buildPortionSummary(portions, maxItems = 1) {
  return (portions || [])
    .slice(0, maxItems)
    .map((portion) => `1${portion.label}≈${formatNumber(portion.grams_per_unit)}g`)
    .join(" / ");
}

function buildMetaPrefix(item) {
  const typeLabel = item.food_type === "dish_recipe" ? "家常菜" : prettyFoodType(item.food_type);
  const categoryLabel = compactCategoryLabel(item.category_top);
  if (typeLabel && categoryLabel && typeLabel === categoryLabel) {
    return [typeLabel];
  }
  return [typeLabel, categoryLabel].filter(Boolean);
}

function buildSearchMeta(item) {
  return [...buildMetaPrefix(item), buildPortionSummary(item.portions || [], 1)].filter(Boolean).join(" · ");
}

function buildSelectedMeta(item) {
  return [...buildMetaPrefix(item), `${formatNumber(item.energy_kcal_100g)} kcal/100g`, `P ${formatNumber(item.protein_g_100g)}g`]
    .filter(Boolean)
    .join(" · ");
}

function formatEntryAmount(entry) {
  if (entry.quantity && entry.unit_label) {
    return `${formatNumber(entry.quantity)}${entry.unit_label}`;
  }
  return `${formatNumber(entry.grams)}克`;
}

function loadState() {
  try {
    const savedProfile = JSON.parse(localStorage.getItem(storageKeys.profile) || "null");
    const savedEntries = JSON.parse(localStorage.getItem(storageKeys.entries) || "null");
    if (savedProfile) {
      state.profile = { ...state.profile, ...savedProfile };
    }
    if (Array.isArray(savedEntries)) {
      state.entries = savedEntries.map((entry) => ({
        id: entry.id || buildEntryId(),
        ...entry,
        preview: hydratePreview(entry.preview, entry),
      }));
    }
    state.profileCollapsed = localStorage.getItem(storageKeys.profileCollapsed) === "1";
  } catch (error) {
    console.error(error);
  }
}

function saveProfile(options = {}) {
  const { collapseAfterSave = false } = options;
  state.profile = readProfileForm();
  localStorage.setItem(storageKeys.profile, JSON.stringify(state.profile));
  renderProfileSummary();
  renderProfileStorageNote();
  if (collapseAfterSave) {
    setProfileCollapsed(true);
  }
  void refreshSummary();
}

function saveEntries() {
  localStorage.setItem(storageKeys.entries, JSON.stringify(state.entries));
  renderEntryCollections();
  renderProfileStorageNote();
}

function readProfileForm() {
  const formData = new FormData(profileForm);
  return {
    sex: formData.get("sex"),
    age: Number(formData.get("age")),
    height_cm: Number(formData.get("height_cm")),
    weight_kg: Number(formData.get("weight_kg")),
    activity_level: formData.get("activity_level"),
    goal: formData.get("goal"),
  };
}

function fillProfileForm() {
  for (const [key, value] of Object.entries(state.profile)) {
    const field = profileForm.elements.namedItem(key);
    if (field) {
      field.value = value;
    }
  }
}

function renderProfileSummary() {
  profileSummaryText.textContent = [
    state.profile.sex === "male" ? "男" : "女",
    `${state.profile.age}岁`,
    `${formatNumber(state.profile.height_cm)}cm`,
    `${formatNumber(state.profile.weight_kg)}kg`,
    activityLabel(state.profile.activity_level),
    goalLabel(state.profile.goal),
  ].join(" · ");
}

function renderProfileStorageNote() {
  const entryCount = Array.isArray(state.entries) ? state.entries.length : 0;
  if (entryCount > 0) {
    profileStorageNote.textContent =
      `当前浏览器已自动保存身体参数和 ${entryCount} 条饮食记录；同一设备再次打开会恢复，换浏览器、换设备或清理浏览器数据后不会同步。`;
    return;
  }
  profileStorageNote.textContent =
    "身体参数和饮食记录会自动保存在当前浏览器；同一设备再次打开会恢复，换浏览器、换设备或清理浏览器数据后不会同步。";
}

function renderHistoryGroup(container, countNode, items, emptyText) {
  container.innerHTML = "";
  countNode.textContent = items.length ? `${items.length} 项` : "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "history-empty";
    empty.textContent = emptyText;
    container.appendChild(empty);
    return;
  }

  for (const item of items) {
    const button = document.createElement("button");
    button.className = "history-chip";
    button.type = "button";
    button.textContent = item.label;
    button.addEventListener("click", () => selectFood(item.preview));
    container.appendChild(button);
  }
}

function renderEntryCollections() {
  const recentItems = [];
  const recentSeen = new Set();
  const commonMap = new Map();

  for (let index = state.entries.length - 1; index >= 0; index -= 1) {
    const entry = state.entries[index];
    const preview = hydratePreview(entry.preview, entry);
    if (!preview) {
      continue;
    }
    const key = `${entry.source}:${entry.source_food_id}`;
    if (!recentSeen.has(key)) {
      recentSeen.add(key);
      recentItems.push({
        key,
        label: preview.display_name || preview.name,
        preview,
      });
    }
    const nextCount = commonMap.get(key)?.count || 0;
    commonMap.set(key, {
      key,
      count: nextCount + 1,
      latestIndex: index,
      preview,
    });
  }

  const commonItems = [...commonMap.values()]
    .sort((left, right) => right.count - left.count || right.latestIndex - left.latestIndex)
    .slice(0, 8)
    .map((item) => ({
      key: item.key,
      label: `${item.preview.display_name || item.preview.name} · ${item.count}次`,
      preview: item.preview,
    }));

  renderHistoryGroup(recentFoods, recentFoodCount, recentItems.slice(0, 8), "还没有最近记录。");
  renderHistoryGroup(commonFoods, commonFoodCount, commonItems, "先记几次饮食，这里会自动变成你的常吃清单。");
}

function setProfileCollapsed(collapsed, options = {}) {
  const { persist = true } = options;
  state.profileCollapsed = collapsed;
  profileCard.classList.toggle("profile-card-collapsed", collapsed);
  profileBody.classList.toggle("hidden", collapsed);
  profileSummary.classList.toggle("hidden", !collapsed);
  toggleProfileBtn.textContent = collapsed ? "展开编辑" : "收起";
  toggleProfileBtn.setAttribute("aria-expanded", String(!collapsed));
  saveProfileBtn.classList.toggle("hidden", collapsed);
  if (persist) {
    localStorage.setItem(storageKeys.profileCollapsed, collapsed ? "1" : "0");
  }
}

function renderSearchResults(items) {
  searchResults.innerHTML = "";
  if (!items.length) {
    searchResults.innerHTML = '<p class="empty-state">没有找到匹配食物，换个更短或更具体的关键词试试。</p>';
    return;
  }
  const template = document.getElementById("search-result-template");
  for (const item of items) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".food-name").textContent = item.display_name;
    node.querySelector(".food-meta").textContent = buildSearchMeta(item);
    node.querySelector(".food-macros").textContent = [
      `${formatNumber(item.energy_kcal_100g)} kcal`,
      `P ${formatNumber(item.protein_g_100g)}g`,
      `C ${formatNumber(item.carb_g_100g)}g`,
      `F ${formatNumber(item.fat_g_100g)}g`,
    ].join("  ");
    node.addEventListener("click", () => selectFood(item));
    searchResults.appendChild(node);
  }
}

function renderUnitOptions(portions) {
  foodUnitSelect.innerHTML = "";
  for (const option of portions) {
    const node = document.createElement("option");
    node.value = option.key;
    node.textContent = `${option.label} · 约 ${formatNumber(option.grams_per_unit)}g`;
    foodUnitSelect.appendChild(node);
  }
  if (foodUnitSelect.options.length) {
    foodUnitSelect.selectedIndex = 0;
  }
}

function selectFood(item, options = {}) {
  const {
    editingEntryId = null,
    quantity = "1",
    unitKey = null,
    mealType = null,
    stateLabel = "已选择",
  } = options;
  state.selectedFood = hydratePreview(item, {
    quantity,
    unit_key: unitKey,
    unit_label: null,
    grams: null,
  });
  state.editingEntryId = editingEntryId;
  selectedFoodPanel.classList.remove("hidden");
  selectedFoodStateLabel.textContent = stateLabel;
  selectedFoodName.textContent = state.selectedFood.display_name;
  selectedFoodMeta.textContent = buildSelectedMeta(state.selectedFood);

  renderUnitOptions(state.selectedFood.portions || []);
  if (mealType) {
    mealTypeSelect.value = mealType;
  }
  if (unitKey && [...foodUnitSelect.options].some((option) => option.value === unitKey)) {
    foodUnitSelect.value = unitKey;
  }
  foodQuantityInput.value = String(quantity);
  addFoodBtn.textContent = editingEntryId ? "保存修改" : "加入记录";
  cancelEditBtn.classList.toggle("hidden", !editingEntryId);
  updateSelectedPortionHint();

  requestAnimationFrame(() => {
    selectedFoodPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    foodQuantityInput.focus();
    foodQuantityInput.select();
  });
}

function updateSelectedPortionHint() {
  if (!state.selectedFood) {
    selectedPortionHint.textContent = "数量可填 1、2、1.5、两、半，单位从右侧固定选。";
    return;
  }
  const portion = (state.selectedFood.portions || []).find((item) => item.key === foodUnitSelect.value);
  const quantity = parseQuantityText(foodQuantityInput.value);
  if (!portion) {
    selectedPortionHint.textContent = "先选一个固定单位，再填写数量。";
    return;
  }
  if (!Number.isFinite(quantity) || quantity <= 0) {
    selectedPortionHint.textContent = `数量支持 1、2、1.5、两、半；当前单位 1${portion.label} 约 ${formatNumber(portion.grams_per_unit)}g。`;
    return;
  }
  const grams = quantity * Number(portion.grams_per_unit);
  selectedPortionHint.textContent = `当前将加入 ${formatNumber(quantity)}${portion.label}，约 ${formatNumber(grams)}g。`;
}

function exitEditMode() {
  state.editingEntryId = null;
  if (state.selectedFood) {
    selectFood(state.selectedFood);
  } else {
    selectedFoodStateLabel.textContent = "已选择";
    addFoodBtn.textContent = "加入记录";
    cancelEditBtn.classList.add("hidden");
  }
}

async function beginEditEntry(entryId) {
  const entry = state.entries.find((item) => item.id === entryId);
  if (!entry) {
    return;
  }
  let preview = hydratePreview(entry.preview, entry);
  if (!preview) {
    const food = await getFood(entry.source, entry.source_food_id);
    if (!food) {
      window.alert("这条记录缺少可编辑的食物信息，请先删除后重新添加。");
      return;
    }
    preview = hydratePreview(food, entry);
  }
  selectFood(preview, {
    editingEntryId: entry.id,
    quantity: entry.quantity || 1,
    unitKey: entry.unit_key || null,
    mealType: entry.meal_type,
    stateLabel: "正在编辑",
  });
}

async function searchFoodsAction(query) {
  if (!query.trim()) {
    renderSearchResults(await searchFoods("", 12));
    return;
  }
  const items = await searchFoods(query, 12);
  renderSearchResults(items);
}

async function addSelectedFood() {
  if (!state.selectedFood) {
    return;
  }
  const quantity = parseQuantityText(foodQuantityInput.value);
  const portion = (state.selectedFood.portions || []).find((item) => item.key === foodUnitSelect.value);
  if (!Number.isFinite(quantity) || quantity <= 0 || quantity > 50 || !portion) {
    window.alert("请输入有效数量。支持 1、2、1.5、两、半 这类写法。");
    return;
  }

  addFoodBtn.disabled = true;
  cancelEditBtn.disabled = true;
  try {
    const grams = quantity * Number(portion.grams_per_unit);
    const nextEntry = {
      id: buildEntryId(),
      meal_type: mealTypeSelect.value,
      source: state.selectedFood.source,
      source_food_id: state.selectedFood.source_food_id,
      grams,
      quantity,
      unit_key: portion.key,
      unit_label: portion.label,
      preview: hydratePreview(state.selectedFood, {
        quantity,
        unit_key: portion.key,
        unit_label: portion.label,
        grams,
      }),
    };

    if (state.editingEntryId) {
      nextEntry.id = state.editingEntryId;
      state.entries = state.entries.map((entry) => (entry.id === state.editingEntryId ? nextEntry : entry));
      exitEditMode();
    } else {
      state.entries.push(nextEntry);
    }

    saveEntries();
    await refreshSummary();
  } catch (error) {
    console.error(error);
    window.alert("保存失败，请重试。");
  } finally {
    addFoodBtn.disabled = false;
    cancelEditBtn.disabled = false;
  }
}

function renderBulkPreview(resolved, unresolved) {
  bulkPreview.innerHTML = "";
  bulkPreview.classList.remove("hidden");
  const template = document.getElementById("bulk-preview-template");

  for (const item of resolved) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".bulk-preview-title").textContent = `${mealLabel(item.meal_type)} · ${item.food.display_name}`;
    node.querySelector(".bulk-preview-meta").textContent = `${item.raw_line} → ${formatNumber(item.quantity)}${item.unit_label}，约 ${formatNumber(item.grams)} g`;
    node.querySelector(".bulk-preview-badge").textContent = "已匹配";
    bulkPreview.appendChild(node);
  }

  for (const item of unresolved) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.classList.add("bulk-preview-item-error");
    node.querySelector(".bulk-preview-title").textContent = item.raw_line;
    node.querySelector(".bulk-preview-meta").textContent = item.reason;
    node.querySelector(".bulk-preview-badge").textContent = "失败";
    bulkPreview.appendChild(node);
  }
}

async function addBulkFoods() {
  const text = bulkInput.value.trim();
  if (!text) {
    window.alert("先输入多条食物记录。");
    return;
  }
  bulkAddBtn.disabled = true;
  bulkFeedback.textContent = "解析中...";
  try {
    const payload = await resolveBulkEntries({
      text,
      default_meal_type: bulkDefaultMealSelect.value,
    });
    const resolved = payload.resolved || [];
    const unresolved = payload.unresolved || [];
    renderBulkPreview(resolved, unresolved);

    if (!resolved.length) {
      bulkFeedback.textContent = `0 条加入，${unresolved.length} 条失败`;
      return;
    }

    for (const item of resolved) {
      state.entries.push({
        id: buildEntryId(),
        meal_type: item.meal_type,
        source: item.food.source,
        source_food_id: item.food.source_food_id,
        grams: Number(item.grams),
        quantity: Number(item.quantity),
        unit_key: item.unit_key,
        unit_label: item.unit_label,
        preview: hydratePreview(item.food, {
          quantity: Number(item.quantity),
          unit_key: item.unit_key,
          unit_label: item.unit_label,
          grams: Number(item.grams),
        }),
      });
    }

    saveEntries();
    await refreshSummary();
    bulkFeedback.textContent = `${resolved.length} 条已加入${unresolved.length ? `，${unresolved.length} 条未识别` : ""}`;
    if (!unresolved.length) {
      bulkInput.value = "";
    }
  } catch (error) {
    console.error(error);
    bulkFeedback.textContent = "解析失败";
  } finally {
    bulkAddBtn.disabled = false;
  }
}

function buildMetricCard(label, value) {
  const node = document.createElement("article");
  node.className = "metric-card";
  node.innerHTML = `<p>${label}</p><strong>${value}</strong>`;
  return node;
}

function buildMetricRow(label, value, extra) {
  const node = document.createElement("article");
  node.className = "target-row";
  node.innerHTML = `<p>${label}</p><strong>${value}</strong><span>${extra || ""}</span>`;
  return node;
}

function buildRatio(current, target) {
  const safeTarget = Number(target || 0);
  if (!safeTarget) {
    return 0;
  }
  return Number(current || 0) / safeTarget;
}

function buildHeroMessage(proteinRatio, kcalDiff) {
  if (proteinRatio < 0.65) {
    return "今天的蛋白质还偏低，优先补高蛋白食物会比纠结热量更有效。";
  }
  if (kcalDiff > 220) {
    return "今天热量已经明显超出目标，后面的加餐尽量选更轻一点。";
  }
  if (kcalDiff < -280) {
    return "今天摄入还偏少，如果正在训练，后续可以适当补一点主食或蛋白。";
  }
  return "整体节奏还不错，继续把剩下的餐次按份量记完，结果会更准。";
}

function buildProgressRow(label, current, target, diff, unit, ratio, stateClass) {
  const node = document.createElement("article");
  node.className = `progress-row ${stateClass}`;
  const fillWidth = Math.max(0, Math.min(100, ratio * 100));
  node.innerHTML = `
    <div class="progress-row-head">
      <span class="progress-row-title">${label}</span>
      <span class="progress-row-value">${formatNumber(current)} / ${formatNumber(target)} ${unit} · ${formatDiff(diff, unit)}</span>
    </div>
    <div class="progress-track">
      <div class="progress-fill" style="width:${fillWidth}%"></div>
    </div>
  `;
  return node;
}

function renderHero(totals, targets, differences) {
  heroGoalBadge.textContent = goalLabel(state.profile.goal);
  heroOrbValue.textContent = formatNumber(totals.kcal);
  heroOrbNote.textContent = `目标 ${formatNumber(targets.target_kcal)} kcal`;

  const proteinRatio = buildRatio(totals.protein_g, targets.target_protein_g);
  const kcalDiff = Number(differences.kcal || 0);
  heroStatus.textContent = buildHeroMessage(proteinRatio, kcalDiff);

  const kpis = [
    ["记录数", `${state.entries.length} 项`],
    ["蛋白完成", `${Math.round(proteinRatio * 100)}%`],
    ["已摄入", `${formatNumber(totals.kcal)} kcal`],
    ["目标差值", formatDiff(differences.kcal, "kcal")],
  ];

  heroKpis.innerHTML = "";
  for (const [label, value] of kpis) {
    const node = document.createElement("article");
    node.className = "hero-kpi";
    node.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    heroKpis.appendChild(node);
  }
}

function renderProgress(totals, targets, differences) {
  progressList.innerHTML = "";
  const metrics = [
    ["热量", totals.kcal, targets.target_kcal, differences.kcal, "kcal"],
    ["蛋白质", totals.protein_g, targets.target_protein_g, differences.protein_g, "g"],
    ["碳水", totals.carb_g, targets.target_carb_g, differences.carb_g, "g"],
    ["脂肪", totals.fat_g, targets.target_fat_g, differences.fat_g, "g"],
  ];

  for (const [label, current, target, diff, unit] of metrics) {
    const ratio = buildRatio(current, target);
    const stateClass = ratio > 1.08 ? "over" : ratio < 0.82 ? "under" : "good";
    progressList.appendChild(buildProgressRow(label, current, target, diff, unit, ratio, stateClass));
  }
}

function renderSummary(summary) {
  const totals = summary?.totals || {};
  const targets = summary?.targets || {};
  const differences = summary?.differences || {};

  renderHero(totals, targets, differences);
  renderProgress(totals, targets, differences);

  summaryMetrics.innerHTML = "";
  targetMetrics.innerHTML = "";

  const topMetrics = [
    ["已摄入热量", `${formatNumber(totals.kcal)} kcal`],
    ["蛋白质", `${formatNumber(totals.protein_g)} g`],
    ["碳水", `${formatNumber(totals.carb_g)} g`],
    ["脂肪", `${formatNumber(totals.fat_g)} g`],
  ];

  const targetRows = [
    ["目标热量", `${formatNumber(targets.target_kcal)} kcal`, formatDiff(differences.kcal, "kcal")],
    ["目标蛋白质", `${formatNumber(targets.target_protein_g)} g`, formatDiff(differences.protein_g, "g")],
    ["目标碳水", `${formatNumber(targets.target_carb_g)} g`, formatDiff(differences.carb_g, "g")],
    ["目标脂肪", `${formatNumber(targets.target_fat_g)} g`, formatDiff(differences.fat_g, "g")],
    ["BMI", `${formatNumber(targets.bmi)}`, `${formatNumber(targets.bmr)} BMR / ${formatNumber(targets.tdee)} TDEE`],
  ];

  for (const [label, value] of topMetrics) {
    summaryMetrics.appendChild(buildMetricCard(label, value));
  }
  for (const [label, value, extra] of targetRows) {
    targetMetrics.appendChild(buildMetricRow(label, value, extra));
  }
}

function renderMeals(summary) {
  mealGroups.innerHTML = "";
  const meals = summary?.meals || [];
  let totalEntries = 0;

  for (const meal of meals) {
    totalEntries += meal.entries.length;
    const wrapper = document.createElement("section");
    wrapper.className = "meal-card";

    const header = document.createElement("div");
    header.className = "meal-header";
    header.innerHTML = `<h3>${meal.label}</h3><p>${formatNumber(meal.totals.kcal)} kcal · 蛋白 ${formatNumber(meal.totals.protein_g)} g</p>`;
    wrapper.appendChild(header);

    if (!meal.entries.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "这一餐还没有记录。";
      wrapper.appendChild(empty);
    } else {
      for (const entry of meal.entries) {
        const row = document.createElement("div");
        row.className = "meal-entry";
        row.innerHTML = `
          <div>
            <strong>${entry.food.display_name}</strong>
            <p>${formatEntryAmount(entry)} · 约 ${formatNumber(entry.grams)} g · ${prettyFoodType(entry.food.food_type)}</p>
          </div>
          <div class="entry-metrics">
            <span>${formatNumber(entry.totals.kcal)} kcal</span>
            <span>P ${formatNumber(entry.totals.protein_g)}g</span>
            <div class="entry-actions">
              <button class="edit-link" type="button">编辑</button>
              <button class="danger-link" type="button">删除</button>
            </div>
          </div>
        `;
        row.querySelector(".edit-link").addEventListener("click", () => void beginEditEntry(entry.entry_id));
        row.querySelector(".danger-link").addEventListener("click", () => removeEntry(entry.entry_id));
        wrapper.appendChild(row);
      }
    }

    mealGroups.appendChild(wrapper);
  }

  entriesCount.textContent = `${totalEntries} 项记录`;
}

function removeEntry(entryId) {
  state.entries = state.entries.filter((item) => item.id !== entryId);
  if (state.editingEntryId === entryId) {
    exitEditMode();
  }
  saveEntries();
  void refreshSummary();
}

async function refreshSummary() {
  state.profile = readProfileForm();
  const payload = {
    profile: state.profile,
    entries: state.entries.map((entry) => ({
      entry_id: entry.id,
      meal_type: entry.meal_type,
      source: entry.source,
      source_food_id: entry.source_food_id,
      grams: Number(entry.grams),
      quantity: entry.quantity ? Number(entry.quantity) : null,
      unit_key: entry.unit_key || null,
      unit_label: entry.unit_label || null,
    })),
  };
  const summary = await buildDaySummary(payload);
  renderSummary(summary);
  renderMeals(summary);
}

function bindEvents() {
  searchBtn.addEventListener("click", () => void searchFoodsAction(searchInput.value.trim()));
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void searchFoodsAction(searchInput.value.trim());
    }
  });
  document.querySelectorAll(".tag-btn").forEach((button) => {
    button.addEventListener("click", () => {
      searchInput.value = button.dataset.query;
      void searchFoodsAction(button.dataset.query);
    });
  });
  addFoodBtn.addEventListener("click", () => void addSelectedFood());
  cancelEditBtn.addEventListener("click", exitEditMode);
  foodQuantityInput.addEventListener("input", updateSelectedPortionHint);
  foodQuantityInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void addSelectedFood();
    }
  });
  foodUnitSelect.addEventListener("change", updateSelectedPortionHint);
  bulkAddBtn.addEventListener("click", () => void addBulkFoods());
  saveProfileBtn.addEventListener("click", () => saveProfile({ collapseAfterSave: true }));
  toggleProfileBtn.addEventListener("click", () => setProfileCollapsed(!state.profileCollapsed));
  clearEntriesBtn.addEventListener("click", () => {
    state.entries = [];
    exitEditMode();
    saveEntries();
    void refreshSummary();
  });
  profileForm.addEventListener("change", () => saveProfile());
}

async function init() {
  await warmupCatalog();
  loadState();
  fillProfileForm();
  renderProfileSummary();
  renderProfileStorageNote();
  renderEntryCollections();
  setProfileCollapsed(state.profileCollapsed, { persist: false });
  bindEvents();
  await searchFoodsAction("");
  await refreshSummary();
}

init().catch((error) => {
  console.error(error);
  window.alert("页面初始化失败，请刷新后重试。");
});
