import { getJSON, postJSON, toErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  formatDateTime,
  modelAvailabilityText,
  renderModelStatePill,
  renderPathLine,
  showToast,
} from "./ui.js";

const state = {
  selectedModelId: null,
  selectedCoverModelId: null,
  allModels: [],
  usableModels: [],
  lastDetailSignature: "",
  lastListSignature: "",
  lastRenderedSelection: null,
};

function buildModelSignature(model) {
  return [
    model.model_id,
    model.usable ? "1" : "0",
    model.default_pitch ?? "",
    model.resolved_source || "",
    model.resolved_pth_path || "",
    model.index_path || "",
    model.exists ? "1" : "0",
  ].join("|");
}

function renderFlag(label, tone = "") {
  return `<span class="artifact-chip ${tone}">${escapeHtml(label)}</span>`;
}

function renderModelCard(model) {
  return `
    <button
      class="model-item ${state.selectedModelId === model.model_id ? "is-active" : ""} ${model.usable ? "" : "is-unusable"}"
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
        <span>存在：${model.exists ? "是" : "否"}</span>
        <span>可用：${model.usable ? "是" : "否"}</span>
        <span>默认音高 ${escapeHtml(model.default_pitch)}</span>
      </div>
      <div class="model-badges">
        ${renderFlag(model.exists ? "已登记" : "未登记", model.exists ? "pending" : "failed")}
        ${renderFlag(model.usable ? "可用于翻唱" : "当前不可用于翻唱", model.usable ? "success" : "failed")}
      </div>
      ${renderPathLine(model.resolved_pth_path || "-", { subtle: true })}
    </button>
  `;
}

function renderModelDetail(model) {
  $("modelDetailCard").innerHTML = `
    <div class="detail-section-head detail-section-head-inline">
      <div>
        <h4>${escapeHtml(model.model_name)}</h4>
        <div class="model-mini-id mono" title="${escapeHtml(model.model_id)}">${escapeHtml(model.model_id)}</div>
      </div>
      ${renderModelStatePill(model)}
    </div>
    <div class="panel-actions">
      <button class="ghost-btn" type="button" id="modelJumpDiagnosticsBtn">查看诊断</button>
    </div>
    <div class="detail-meta">
      <div class="meta-card"><div class="meta-label">模型 ID</div><div class="meta-value mono" title="${escapeHtml(model.model_id)}">${escapeHtml(model.model_id)}</div></div>
      <div class="meta-card"><div class="meta-label">存在</div><div class="meta-value">${model.exists ? "是" : "否"}</div></div>
      <div class="meta-card"><div class="meta-label">可用</div><div class="meta-value">${model.usable ? "是" : "否"}</div></div>
      <div class="meta-card"><div class="meta-label">状态</div><div class="meta-value">${escapeHtml(modelAvailabilityText(model))}</div></div>
      <div class="meta-card"><div class="meta-label">默认音高</div><div class="meta-value">${escapeHtml(model.default_pitch)}</div></div>
      <div class="meta-card"><div class="meta-label">解析来源</div><div class="meta-value">${escapeHtml(model.resolved_source || "-")}</div></div>
      <div class="meta-card"><div class="meta-label">后端状态</div><div class="meta-value">${escapeHtml(model.status || "-")}</div></div>
      <div class="meta-card"><div class="meta-label">更新时间</div><div class="meta-value">${escapeHtml(formatDateTime(model.updated_at))}</div></div>
    </div>
    <div class="detail-section">
      <div class="detail-section-head"><h4>当前解析到的 .pth</h4></div>
      ${renderPathLine(model.resolved_pth_path || "-")}
    </div>
    <div class="detail-section">
      <div class="detail-section-head"><h4>登记路径</h4></div>
      ${renderPathLine(model.pth_path || "-", { subtle: true })}
      ${renderPathLine(model.index_path || "-", { subtle: true })}
    </div>
    <div class="detail-section">
      <div class="detail-section-head"><h4>使用说明</h4></div>
      <div class="detail-empty">
        ${model.usable
          ? "这个模型已经达到可用状态，可以直接用于创建 cover job。"
          : model.exists
            ? "这个模型已经登记，但当前还没有达到可用状态。请优先检查路径、文件完整性和诊断面板。"
            : "这个模型记录还不完整。请先导入正确的 .pth / .index，或重新扫描模型目录。"}
      </div>
    </div>
  `;

  $("modelJumpDiagnosticsBtn").addEventListener("click", () => {
    document.getElementById("diagnosticsPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
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
  const previousValue = state.selectedCoverModelId || select.value;
  if (!usableModels.length) {
    select.innerHTML = `<option value="">当前没有可用模型</option>`;
    select.value = "";
    state.selectedCoverModelId = "";
    return;
  }

  select.innerHTML = usableModels.map(model => `
    <option value="${escapeHtml(model.model_id)}">${escapeHtml(model.model_name)} · ${escapeHtml(model.model_id)}</option>
  `).join("");

  const nextValue = usableModels.some(model => model.model_id === previousValue)
    ? previousValue
    : usableModels[0].model_id;
  select.value = nextValue;
  state.selectedCoverModelId = nextValue;
  if (nextValue !== previousValue) {
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function renderPanelSummary(panelModels, usableModels) {
  $("modelsSummary").textContent = `当前显示 ${panelModels.length} 个模型，其中 ${usableModels.length} 个达到可用状态。`;
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

export async function refreshModels() {
  const includeUnavailable = $("modelsIncludeUnavailable").checked;

  try {
    state.selectedCoverModelId = state.selectedCoverModelId || $("coverModelSelect").value || "";
    const panelModels = await getJSON(`/api/models?include_unavailable=${includeUnavailable ? "true" : "false"}`);
    const usableModels = panelModels.filter(model => model.usable);

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
      $("modelDetailCard").innerHTML = `<div class="detail-empty">当前没有可查看的模型详情。</div>`;
      state.lastDetailSignature = "";
      return;
    }

    await loadModelDetail(state.selectedModelId, { force: false });
  } catch (error) {
    $("modelsList").innerHTML = `<div class="detail-empty">模型面板加载失败。</div>`;
    showToast(`模型列表加载失败：${toErrorMessage(error)}`, "error");
  }
}

function notifyModelsChanged() {
  document.dispatchEvent(new CustomEvent("feishark:models-changed"));
}

export function initModels() {
  $("modelsRefreshBtn").addEventListener("click", () => refreshModels());
  $("modelsIncludeUnavailable").addEventListener("change", () => refreshModels());

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
