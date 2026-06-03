import { getJSON, postJSON, toErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  formatDateTime,
  loadUiState,
  modelMaterialProfileLabel,
  modelOriginLabel,
  renderModelOriginPill,
  renderModelStatePill,
  renderPathLine,
  saveUiState,
  showToast,
  slideToggle,
  stageText,
  statusText,
  strategyLabel,
} from "./ui.js";

const MODELS_INVENTORY_STATE_KEY = "feishark_ui_models_inventory_collapsed";
const MODEL_TECHNICAL_STATE_KEY = "feishark_ui_model_technical_collapsed";
const TEST_RECORDS_VISIBLE_KEY = "feishark_ui_show_test_records";
const TEST_RECORDS_EVENT = "feishark:test-records-visibility-changed";
const COVER_MODEL_PENDING_REGISTRY_LABEL = "training observer pending registry";

const state = {
  selectedModelId: null,
  selectedCoverModelId: null,
  allModels: [],
  usableModels: [],
  lastDetailSignature: "",
  lastListSignature: "",
  lastRenderedSelection: null,
};

function modelMetadata(model = {}) {
  if (model.metadata && typeof model.metadata === "object") return model.metadata;
  if (!model.metadata_json) return {};
  try {
    return JSON.parse(model.metadata_json);
  } catch {
    return {};
  }
}

function isCheckpointRecoveredModel(model = {}) {
  const metadata = modelMetadata(model);
  return Boolean(metadata.recovered_from_checkpoint) ||
    /checkpoint.*恢复|恢复登记|recovered/i.test(String(model.source_summary || ""));
}

function recoveredExpName(model = {}) {
  return modelMetadata(model).recovered_exp_name || "";
}

function recoveredEpoch(model = {}) {
  return modelMetadata(model).recovered_epoch || "";
}

function renderRecoveredAcceptanceGuide() {
  return `
    <div class="recovered-acceptance-guide">
      <strong>恢复模型验收</strong>
      <ol>
        <li>选择歌曲</li>
        <li>创建 AI 翻唱</li>
        <li>完成后打开 Studio 试听</li>
      </ol>
    </div>
  `;
}

function buildModelSignature(model) {
  return [
    model.model_id,
    model.usable ? "1" : "0",
    model.default_pitch ?? "",
    model.resolved_source || "",
    model.resolved_pth_path || "",
    model.resolved_index_path || model.index_path || "",
    model.origin_kind || "",
    model.source_job_id || "",
    model.source_summary || "",
    model.updated_at || "",
  ].join("|");
}

function renderFlag(label, tone = "") {
  return `<span class="artifact-chip ${tone}">${escapeHtml(label)}</span>`;
}

function getShowTestRecords() {
  return Boolean(loadUiState(TEST_RECORDS_VISIBLE_KEY, false));
}

function saveShowTestRecords(value) {
  saveUiState(TEST_RECORDS_VISIBLE_KEY, Boolean(value));
  document.dispatchEvent(new CustomEvent(TEST_RECORDS_EVENT, { detail: { visible: Boolean(value) } }));
}

function withTestRecordParams(params = {}) {
  const visible = getShowTestRecords();
  return {
    ...params,
    include_test_data: visible ? "true" : "false",
    include_smoke: visible ? "true" : "false",
  };
}

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  return search.toString() ? `?${search.toString()}` : "";
}

function recordSearchText(value = {}) {
  if (!value) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function isTestRecord(value = {}) {
  const text = recordSearchText(value);
  return /(?:^|[\s_\-./\\])(?:smoke|self[_-]?check|playwright|test)(?:$|[\s_\-./\\])/i.test(text)
    || /stage[\s_\-]*\d+/i.test(text);
}

function filterTestRecords(items = []) {
  return getShowTestRecords() ? items : items.filter(item => !isTestRecord(item));
}

function renderTestRecordsToggle(hiddenCount = 0) {
  const anchor = $("modelsSummary");
  if (!anchor) return;
  let toggle = document.getElementById("modelsTestRecordsToggle");
  if (!toggle) {
    toggle = document.createElement("div");
    toggle.id = "modelsTestRecordsToggle";
    toggle.className = "test-record-toggle";
    anchor.insertAdjacentElement("afterend", toggle);
  }

  const visible = getShowTestRecords();
  toggle.innerHTML = `
    <label class="test-record-toggle-label">
      <input id="modelsShowTestRecords" type="checkbox" ${visible ? "checked" : ""}>
      <span>显示测试记录</span>
    </label>
    <span class="test-record-toggle-note">${
      visible
        ? "当前包含 smoke / stage / test / self_check / playwright 模型记录。"
        : `默认隐藏测试模型${hiddenCount ? `，已隐藏 ${hiddenCount} 条。` : "。"}`
    }</span>
  `;
  $("modelsShowTestRecords")?.addEventListener("change", event => {
    saveShowTestRecords(event.target.checked);
    refreshModels().catch(() => {});
  });
}

function getModelsInventoryCollapsed() {
  return Boolean(loadUiState(MODELS_INVENTORY_STATE_KEY, true));
}

async function setModelsInventoryCollapsed(collapsed, { immediate = false } = {}) {
  const drawer = $("modelsInventoryDrawer");
  const body = $("modelsInventoryBody");
  const button = $("modelsInventoryToggleBtn");
  if (!drawer || !body || !button) return;

  saveUiState(MODELS_INVENTORY_STATE_KEY, collapsed);
  drawer.dataset.collapsed = String(collapsed);
  drawer.classList.toggle("is-collapsed", collapsed);
  button.setAttribute("aria-expanded", String(!collapsed));
  button.textContent = collapsed ? "展开模型库存 ▾" : "收起模型库存 ▴";

  const alreadyCollapsed = body.hidden;
  if (immediate || alreadyCollapsed === collapsed) {
    body.hidden = collapsed;
    return;
  }

  await slideToggle(body, !collapsed);
}

function getModelTechnicalCollapsed() {
  return Boolean(loadUiState(MODEL_TECHNICAL_STATE_KEY, true));
}

async function setModelTechnicalCollapsed(collapsed, { immediate = false } = {}) {
  const drawer = $("modelTechnicalDrawer");
  const body = $("modelTechnicalBody");
  const button = $("modelTechnicalToggleBtn");
  if (!drawer || !body || !button) return;

  saveUiState(MODEL_TECHNICAL_STATE_KEY, collapsed);
  drawer.dataset.collapsed = String(collapsed);
  drawer.classList.toggle("is-collapsed", collapsed);
  button.setAttribute("aria-expanded", String(!collapsed));
  button.textContent = collapsed ? "展开技术详情 ▾" : "收起技术详情 ▴";

  if (immediate || body.hidden === collapsed) {
    body.hidden = collapsed;
    return;
  }

  await slideToggle(body, !collapsed);
}

function getOriginSummary(model) {
  if (isCheckpointRecoveredModel(model)) {
    const exp = recoveredExpName(model);
    const epoch = recoveredEpoch(model);
    return `从失败训练恢复登记，已完成 index/model register，可用于翻唱验证。${exp ? `来源实验 ${exp}` : ""}${epoch ? ` / e${epoch}` : ""}`;
  }
  return model.source_summary || (
    model.origin_kind === "trained_local"
      ? `来自训练任务 ${model.source_job_id || "-"}`
      : model.origin_kind === "rescanned_local"
        ? "来自本地目录扫描"
        : "来自外部导入"
  );
}

function getUnavailableReason(model) {
  if (model.usable) return "";
  if (model.resolved_source === "not_found") {
    return "当前 .pth 或 .index 路径无效，需要修正路径后才能用于翻唱。";
  }
  if (model.exists) {
    return "模型记录已登记，但文件还没有通过当前环境校验。";
  }
  return "模型记录还不完整，暂时不能送入翻唱入口。";
}

function getModelHeadline(model) {
  if (isCheckpointRecoveredModel(model) && model.usable) {
    return "从失败训练恢复登记，已完成 index/model register，可用于翻唱验证。";
  }
  if (model.usable) {
    if (model.origin_kind === "trained_local" && model.source_job_id) {
      return `当前模型已可用于翻唱，来源于训练任务 ${model.source_job_id}。`;
    }
    return "当前模型已可用于翻唱，可直接在创建入口使用。";
  }
  if (model.origin_kind === "trained_local" && model.source_job_id) {
    return `当前模型来自训练任务 ${model.source_job_id}，但权重路径还没有通过校验。`;
  }
  if (model.exists) return "当前模型已登记，但路径或文件状态异常，暂时不能用于翻唱。";
  return "当前模型记录不完整，需要重新导入或重扫。";
}

function getModelNextStep(model) {
  if (isCheckpointRecoveredModel(model) && model.usable) {
    return "下一步：可一键送入翻唱入口做试听验证，或回看来源训练任务。";
  }
  if (model.usable) return "下一步：可一键送入翻唱入口，或回看来源训练任务。";
  if (model.origin_kind === "trained_local" && model.source_job_id) return "下一步：先回看来源训练任务，再检查当前 .pth / .index 路径。";
  if (model.exists) return "下一步：检查 .pth / .index 路径，或重新扫描模型目录。";
  return "下一步：补齐 .pth / .index 后重新导入模型。";
}

function getModelHumanStatus(model) {
  if (isCheckpointRecoveredModel(model) && model.usable) return "checkpoint 恢复，可用于翻唱";
  if (model.usable) return "已可用于翻唱";
  if (model.exists) return "已登记，待修复";
  return "记录不完整";
}

function renderModelCard(model) {
  const recovered = isCheckpointRecoveredModel(model);
  const epoch = recoveredEpoch(model);
  return `
    <button
      class="model-item ${state.selectedModelId === model.model_id ? "is-active" : ""} ${model.usable ? "" : "is-unusable"} ${recovered ? "is-checkpoint-recovered" : ""}"
      type="button"
      data-model-id="${escapeHtml(model.model_id)}"
    >
      <div class="model-card-head">
        <div>
          <strong>${escapeHtml(model.model_name)}</strong>
          <div class="model-mini-id mono" title="${escapeHtml(model.model_id)}">${escapeHtml(model.model_id)}</div>
        </div>
        ${renderModelStatePill(model)}
      </div>
      <div class="model-meta">
        <span>${escapeHtml(modelOriginLabel(model.origin_kind))}</span>
        <span>默认音高 ${escapeHtml(model.default_pitch)}</span>
        ${model.source_strategy_key ? `<span>${escapeHtml(strategyLabel(model.source_strategy_key))}</span>` : ""}
      </div>
      <div class="model-badges">
        ${renderModelOriginPill(model.origin_kind)}
        ${recovered ? `<span class="tag checkpoint">checkpoint 恢复</span>` : ""}
        ${recovered && epoch ? `<span class="tag checkpoint">e${escapeHtml(epoch)}</span>` : ""}
        ${recovered && model.source_job_id ? `<span class="tag checkpoint mono">${escapeHtml(model.source_job_id)}</span>` : ""}
        ${renderFlag(model.usable ? "可用于翻唱" : "当前不可用", model.usable ? "success" : "failed")}
      </div>
      <div class="detail-note model-source-summary" title="${escapeHtml(getOriginSummary(model))}">${escapeHtml(getOriginSummary(model))}</div>
      ${renderPathLine(model.resolved_pth_path || "-", { subtle: true })}
    </button>
  `;
}

function renderDetailRow(label, valueHtml) {
  return `
    <div class="detail-meta-row">
      <span class="detail-meta-key">${escapeHtml(label)}</span>
      <div class="detail-meta-value">${valueHtml}</div>
    </div>
  `;
}

function renderDetailCard(title, rows = [], { wide = false } = {}) {
  return `
    <div class="meta-card detail-meta-card ${wide ? "wide" : ""}">
      <div class="detail-meta-title">${escapeHtml(title)}</div>
      <div class="detail-meta-lines">
        ${rows.filter(Boolean).join("") || `<div class="detail-empty inline">暂无内容。</div>`}
      </div>
    </div>
  `;
}

function renderDetailText(value, { subtle = false } = {}) {
  const classes = ["detail-note", subtle ? "is-subtle" : ""].filter(Boolean).join(" ");
  return `<div class="${classes}" title="${escapeHtml(value || "-")}">${escapeHtml(value || "-")}</div>`;
}

function renderEmptyModelDetail(message = "点击一个模型即可查看详情。") {
  $("modelDetailCard").innerHTML = `
    <div class="detail-summary-card">
      <div class="detail-summary-head">
        <div class="detail-summary-head-copy">
          <p class="detail-summary-eyebrow">模型判定</p>
          <h4 class="detail-summary-title">模型详情会显示在这里</h4>
          <div class="detail-summary-subline">${escapeHtml(message)}</div>
        </div>
      </div>
      <p class="detail-summary-text">这里会先告诉你模型能不能用于翻唱、它来自哪里，以及下一步最合理的动作。</p>
    </div>
  `;
}

function renderModelDetail(model) {
  const resolvedIndexPath = model.resolved_index_path || model.index_path || "-";
  const sourceSummary = getOriginSummary(model);
  const recovered = isCheckpointRecoveredModel(model);
  const expName = recoveredExpName(model);
  const epoch = recoveredEpoch(model);
  $("modelDetailCard").innerHTML = `
    <div class="detail-summary-card">
      <div class="detail-summary-head">
        <div class="detail-summary-head-copy">
          <p class="detail-summary-eyebrow">模型判定</p>
          <h4 class="detail-summary-title" title="${escapeHtml(model.model_name)}">${escapeHtml(model.model_name)}</h4>
          <div class="detail-summary-subline mono" title="${escapeHtml(model.model_id)}">${escapeHtml(model.model_id)}</div>
        </div>
        <div class="detail-summary-badges">
          ${renderModelOriginPill(model.origin_kind)}
          ${recovered ? `<span class="tag checkpoint">checkpoint 恢复</span>` : ""}
          ${recovered && epoch ? `<span class="tag checkpoint">e${escapeHtml(epoch)}</span>` : ""}
          ${renderModelStatePill(model)}
        </div>
      </div>
      <p class="detail-summary-text">${escapeHtml(getModelHeadline(model))}</p>
      <div class="detail-summary-foot">${escapeHtml(getModelNextStep(model))}</div>
      ${recovered ? renderRecoveredAcceptanceGuide() : ""}
      ${!model.usable ? `<div class="detail-inline-callout">${escapeHtml(getUnavailableReason(model))}</div>` : ""}
      <div class="panel-actions">
        ${model.usable ? `<button class="primary-btn warm" type="button" id="modelUseForCoverBtn">用于翻唱</button>` : ""}
        ${model.source_job_id ? `<button class="ghost-btn" type="button" id="modelSourceJobBtn" data-source-job-id="${escapeHtml(model.source_job_id)}">查看来源任务</button>` : ""}
        <button class="ghost-btn" type="button" id="modelJumpDiagnosticsBtn">查看诊断</button>
      </div>
    </div>

    <div class="detail-meta detail-meta-product">
      ${renderDetailCard("核心信息", [
        renderDetailRow("模型 ID", `<div class="mono" title="${escapeHtml(model.model_id)}">${escapeHtml(model.model_id)}</div>`),
        renderDetailRow("默认音高", escapeHtml(model.default_pitch ?? "-")),
        renderDetailRow("当前状态", escapeHtml(getModelHumanStatus(model))),
        renderDetailRow("更新时间", escapeHtml(formatDateTime(model.updated_at))),
      ])}
      ${renderDetailCard("来源信息", [
        renderDetailRow("来源类型", escapeHtml(modelOriginLabel(model.origin_kind))),
        recovered ? renderDetailRow("恢复来源", "checkpoint 恢复") : "",
        recovered && expName ? renderDetailRow("恢复实验", `<div class="mono" title="${escapeHtml(expName)}">${escapeHtml(expName)}</div>`) : "",
        recovered && epoch ? renderDetailRow("恢复 epoch", escapeHtml(`e${epoch}`)) : "",
        renderDetailRow("来源摘要", renderDetailText(sourceSummary)),
        model.source_strategy_key ? renderDetailRow("训练策略", escapeHtml(strategyLabel(model.source_strategy_key))) : "",
        model.source_material_profile ? renderDetailRow("素材画像", escapeHtml(modelMaterialProfileLabel(model.source_material_profile))) : "",
        model.source_file_count ? renderDetailRow("文件数量", escapeHtml(`${model.source_file_count} 个文件`)) : "",
        model.source_duration_label ? renderDetailRow("素材时长", escapeHtml(model.source_duration_label)) : "",
        model.source_dataset_id ? renderDetailRow("数据集 ID", `<div class="mono" title="${escapeHtml(model.source_dataset_id)}">${escapeHtml(model.source_dataset_id)}</div>`) : "",
        model.source_job_id ? renderDetailRow("来源任务", `<div class="mono" title="${escapeHtml(model.source_job_id)}">${escapeHtml(model.source_job_id)}</div>`) : "",
      ], { wide: true })}
      ${renderDetailCard("当前判定", [
        renderDetailRow("是否可用", model.usable ? "是" : "否"),
        renderDetailRow("来源任务状态", model.source_job_status ? escapeHtml(statusText(model.source_job_status)) : renderDetailText("无来源任务", { subtle: true })),
        renderDetailRow("来源任务阶段", model.source_job_current_stage ? escapeHtml(stageText(model.source_job_current_stage)) : renderDetailText("无来源任务", { subtle: true })),
        renderDetailRow("来源任务创建时间", model.source_job_created_at ? escapeHtml(formatDateTime(model.source_job_created_at)) : renderDetailText("无来源任务", { subtle: true })),
      ])}
      ${renderDetailCard("当前解析结果", [
        renderDetailRow("当前 .pth", renderPathLine(model.resolved_pth_path || model.pth_path || "-", { subtle: !(model.resolved_pth_path || model.pth_path) })),
        renderDetailRow("当前 .index", renderPathLine(resolvedIndexPath, { subtle: resolvedIndexPath === "-" })),
      ], { wide: true })}
    </div>

    <div class="detail-drawer" id="modelTechnicalDrawer" data-collapsed="true">
      <div class="detail-section-head detail-drawer-head">
        <div>
          <h4>技术详情</h4>
          <div class="detail-drawer-summary">原始登记路径、解析来源和后端状态默认收在这里。</div>
        </div>
        <button
          class="ghost-btn drawer-toggle-btn"
          id="modelTechnicalToggleBtn"
          type="button"
          aria-controls="modelTechnicalBody"
          aria-expanded="false"
        >展开技术详情 ▾</button>
      </div>
      <div class="detail-drawer-body" id="modelTechnicalBody" hidden>
        <div class="detail-meta detail-meta-product">
          ${renderDetailCard("原始字段", [
            renderDetailRow("解析来源", escapeHtml(model.resolved_source || "-")),
            renderDetailRow("解析索引来源", escapeHtml(model.resolved_index_source || "-")),
            renderDetailRow("后端状态", escapeHtml(model.status || "-")),
          ])}
          ${renderDetailCard("登记路径", [
            renderDetailRow("登记 .pth", renderPathLine(model.pth_path || "-", { subtle: !model.pth_path })),
            renderDetailRow("登记 .index", renderPathLine(model.index_path || "-", { subtle: !model.index_path })),
          ], { wide: true })}
        </div>
      </div>
    </div>
  `;

  setModelTechnicalCollapsed(getModelTechnicalCollapsed(), { immediate: true }).catch(() => {});
}

async function loadModelDetail(modelId, { force = false } = {}) {
  try {
    const detail = await getJSON(`/api/models/${modelId}`);
    const signature = buildModelSignature(detail);
    if (!force && state.selectedModelId === modelId && state.lastDetailSignature === signature) {
      return detail;
    }
    state.selectedModelId = modelId;
    state.lastDetailSignature = signature;
    renderModelDetail(detail);
    return detail;
  } catch (error) {
    showToast(`模型详情加载失败：${toErrorMessage(error)}`, "error");
    return null;
  }
}

function updateCoverModelSelect(usableModels) {
  const select = $("coverModelSelect");
  if (!select) return;
  const previousValue = state.selectedCoverModelId || select.value;
  const injectedOptions = Array.from(select.options || [])
    .filter(option => option.dataset.stage56Injected === "true" || option.dataset.stage57ObserverInjected === "true")
    .map(option => ({
      value: option.value,
      label: option.textContent || `${option.value} - ${COVER_MODEL_PENDING_REGISTRY_LABEL}`,
    }))
    .filter(option => option.value);
  const pendingOption = injectedOptions.find(option => option.value === previousValue) || null;
  if (!usableModels.length) {
    if (pendingOption) {
      select.innerHTML = `
        <option
          value="${escapeHtml(pendingOption.value)}"
          data-stage56-injected="true"
          data-stage57-observer-injected="true"
          data-pending-registry="true"
        >${escapeHtml(pendingOption.label)}</option>
      `;
      select.value = pendingOption.value;
      state.selectedCoverModelId = pendingOption.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    select.innerHTML = `<option value="">当前没有可用模型</option>`;
    select.value = "";
    state.selectedCoverModelId = "";
    return;
  }

  const optionsHtml = usableModels.map(model => `
    <option
      value="${escapeHtml(model.model_id)}"
      data-checkpoint-recovered="${isCheckpointRecoveredModel(model) ? "true" : "false"}"
      data-recovered-epoch="${escapeHtml(recoveredEpoch(model))}"
    >${escapeHtml(model.model_name)} · ${escapeHtml(model.model_id)}</option>
  `);
  const hasRealPrevious = usableModels.some(model => model.model_id === previousValue);
  if (!hasRealPrevious && pendingOption) {
    optionsHtml.push(`
      <option
        value="${escapeHtml(pendingOption.value)}"
        data-stage56-injected="true"
        data-stage57-observer-injected="true"
        data-pending-registry="true"
      >${escapeHtml(pendingOption.label)}</option>
    `);
  }
  select.innerHTML = optionsHtml.join("");

  const nextValue = hasRealPrevious
    ? previousValue
    : pendingOption
      ? pendingOption.value
    : usableModels[0].model_id;
  select.value = nextValue;
  state.selectedCoverModelId = nextValue;
  if (nextValue !== previousValue) {
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function renderPanelSummary(panelModels, usableModels) {
  $("modelsSummary").textContent = `当前显示 ${panelModels.length} 个模型，其中 ${usableModels.length} 个已经达到可用于翻唱的状态。`;
  $("modelsInventorySummary").textContent = `已登记 ${panelModels.length} 个 / 可用 ${usableModels.length} 个`;
  const notice = $("modelPanelNotice");
  if (usableModels.length) {
    notice.textContent = `翻唱入口当前可直接使用 ${usableModels.length} 个模型。只有“可用”模型会进入翻唱下拉框。`;
    notice.className = "availability-note success";
  } else {
    notice.textContent = "当前没有可用模型。请先导入正确的 .pth / .index，或重新扫描 shared_data/weights。";
    notice.className = "availability-note danger";
  }
}

function renderModelList(panelModels) {
  const listSignature = panelModels.map(buildModelSignature).join("||");
  const selectionSignature = state.selectedModelId || "";
  const shouldRender =
    listSignature !== state.lastListSignature ||
    selectionSignature !== state.lastRenderedSelection;

  if (!shouldRender) return;

  $("modelsList").innerHTML = panelModels.length
    ? panelModels.map(renderModelCard).join("")
    : `<div class="detail-empty">当前筛选条件下没有模型。</div>`;

  state.lastListSignature = listSignature;
  state.lastRenderedSelection = selectionSignature;
}

function notifyModelsChanged() {
  document.dispatchEvent(new CustomEvent("feishark:models-changed"));
}

function switchToDashboardIfNeeded() {
  document.querySelector('[data-mobile-tab-target="dashboard"]')?.click();
}

function switchToModelsTabIfNeeded() {
  document.querySelector('[data-mobile-tab-target="models"]')?.click();
}

async function useModelForCover() {
  const modelId = state.selectedModelId;
  const model = state.allModels.find(item => item.model_id === modelId);
  if (!model || !model.usable) {
    showToast(getUnavailableReason(model || {}), "error");
    return;
  }

  const select = $("coverModelSelect");
  if (select) {
    select.value = model.model_id;
    state.selectedCoverModelId = model.model_id;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  switchToDashboardIfNeeded();
  $("entryCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
  $("coverModelSelect")?.focus?.({ preventScroll: true });
  showToast(
    isCheckpointRecoveredModel(model)
      ? "已选择恢复模型，可上传歌曲进行翻唱验证"
      : `已将模型 ${model.model_name} 选入翻唱入口`,
    "success",
  );
}

async function focusModelById(modelId, { scroll = true, force = true } = {}) {
  if (!modelId) return false;
  switchToModelsTabIfNeeded();
  state.selectedModelId = modelId;
  renderModelList(state.allModels);
  const detail = await loadModelDetail(modelId, { force });
  if (detail && scroll) {
    $("modelPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return Boolean(detail);
}

export async function refreshModels() {
  const includeUnavailable = $("modelsIncludeUnavailable").checked;

  try {
    state.selectedCoverModelId = state.selectedCoverModelId || $("coverModelSelect").value || "";
    const modelParams = withTestRecordParams({ include_unavailable: includeUnavailable ? "true" : "false" });
    const [modelsPayload, modelSummary] = await Promise.all([
      getJSON(`/api/models${buildQuery(modelParams)}`),
      getJSON(`/api/models/summary${buildQuery(modelParams)}`).catch(() => null),
    ]);
    const rawModels = Array.isArray(modelsPayload)
      ? modelsPayload
      : Array.isArray(modelsPayload?.items)
        ? modelsPayload.items
        : Array.isArray(modelsPayload?.models)
          ? modelsPayload.models
          : [];
    const panelModels = filterTestRecords(rawModels);
    const usableModels = panelModels.filter(model => model.usable);
    const summaryHiddenCount = Number(modelSummary?.hidden_test_model_count ?? modelSummary?.hidden_test_count);
    const hiddenCount = Number.isFinite(summaryHiddenCount)
      ? summaryHiddenCount
      : Math.max(0, rawModels.length - panelModels.length);
    renderTestRecordsToggle(hiddenCount);

    state.allModels = panelModels;
    state.usableModels = usableModels;

    renderPanelSummary(panelModels, usableModels);
    updateCoverModelSelect(usableModels);

    if (state.selectedModelId && !panelModels.some(model => model.model_id === state.selectedModelId)) {
      state.selectedModelId = panelModels[0]?.model_id || null;
      state.lastDetailSignature = "";
    } else if (!state.selectedModelId && panelModels.length) {
      state.selectedModelId = panelModels[0].model_id;
    }

    renderModelList(panelModels);

    if (!panelModels.length) {
      renderEmptyModelDetail("当前没有可查看的模型详情。");
      state.lastDetailSignature = "";
      return;
    }

    await loadModelDetail(state.selectedModelId, { force: false });
  } catch (error) {
    $("modelsList").innerHTML = `<div class="detail-empty">模型面板加载失败。</div>`;
    renderEmptyModelDetail("模型面板加载失败。");
    showToast(`模型列表加载失败：${toErrorMessage(error)}`, "error");
  }
}

export function initModels() {
  renderTestRecordsToggle();
  setModelsInventoryCollapsed(getModelsInventoryCollapsed(), { immediate: true }).catch(() => {});
  setModelTechnicalCollapsed(getModelTechnicalCollapsed(), { immediate: true }).catch(() => {});

  $("modelsRefreshBtn").addEventListener("click", () => refreshModels());
  $("modelsIncludeUnavailable").addEventListener("change", () => refreshModels());
  window.addEventListener("storage", event => {
    if (event.key === TEST_RECORDS_VISIBLE_KEY) {
      renderTestRecordsToggle();
      refreshModels().catch(() => {});
    }
  });
  document.addEventListener(TEST_RECORDS_EVENT, () => {
    renderTestRecordsToggle();
  });
  $("modelsInventoryToggleBtn").addEventListener("click", () => {
    const nextCollapsed = !getModelsInventoryCollapsed();
    setModelsInventoryCollapsed(nextCollapsed).catch(() => {});
  });

  $("coverModelSelect").addEventListener("change", event => {
    state.selectedCoverModelId = event.target.value;
  });

  $("modelsRescanBtn").addEventListener("click", async () => {
    try {
      const result = await postJSON("/api/models/rescan");
      showToast(`模型重扫完成：共 ${result.model_count} 个，可用 ${result.usable_count} 个。`, "success");
      await refreshModels();
      notifyModelsChanged();
    } catch (error) {
      showToast(`模型重扫失败：${toErrorMessage(error)}`, "error");
    }
  });

  $("modelImportForm").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const payload = {
        model_name: $("modelImportName").value.trim(),
        pth_path: $("modelImportPth").value.trim(),
        index_path: $("modelImportIndex").value.trim(),
        default_pitch: Number($("modelImportPitch").value || 0),
      };
      const result = await postJSON("/api/models/import", payload);
      showToast(`模型已导入：${result.model_name}，当前${result.usable ? "可用" : "不可用"}。`, result.usable ? "success" : "info");
      state.selectedModelId = result.model_id;
      await refreshModels();
      notifyModelsChanged();
    } catch (error) {
      showToast(`模型导入失败：${toErrorMessage(error)}`, "error");
    }
  });

  $("modelsList").addEventListener("click", async event => {
    const card = event.target.closest("[data-model-id]");
    if (!card) return;
    state.selectedModelId = card.dataset.modelId;
    renderModelList(state.allModels);
    await loadModelDetail(card.dataset.modelId, { force: true });
  });

  $("modelDetailCard").addEventListener("click", event => {
    if (event.target.closest("#modelJumpDiagnosticsBtn")) {
      $("diagnosticsPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (event.target.closest("#modelTechnicalToggleBtn")) {
      setModelTechnicalCollapsed(!getModelTechnicalCollapsed()).catch(() => {});
      return;
    }

    if (event.target.closest("#modelUseForCoverBtn")) {
      useModelForCover().catch(() => {});
      return;
    }

    const sourceJobBtn = event.target.closest("#modelSourceJobBtn");
    if (sourceJobBtn) {
      const sourceJobId = sourceJobBtn.dataset.sourceJobId || "";
      if (!sourceJobId) return;
      switchToDashboardIfNeeded();
      $("taskCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId: sourceJobId } }));
    }
  });

  document.addEventListener("feishark:focus-model", event => {
    const modelId = event.detail?.modelId || "";
    focusModelById(modelId, { scroll: true, force: true }).catch(() => {});
  });
}

export function getSelectedCoverModelId() {
  return $("coverModelSelect").value || state.selectedCoverModelId || "";
}

export function getModelsState() {
  return {
    allModels: state.allModels,
    usableModels: state.usableModels,
    usableCount: state.usableModels.length,
    selectedModelId: state.selectedModelId,
  };
}
