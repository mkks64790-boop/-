import { getJSON, toErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  jobTypeLabel,
  renderChecks,
  renderPathLine,
  setEngineChip,
  showToast,
  slideToggle,
  stageText,
  strategyLabel,
} from "./ui.js";

const DETAIL_PANEL_ID = "diagnostics-detail-panel";
const TOGGLE_BUTTON_ID = "diagnosticsDetailToggleBtn";
const READY_NOTE_ID = "diagnosticsReadyNote";
const DIAGNOSTICS_TITLE = "系统预检与可用性";
const DIAGNOSTICS_DETAIL_OPEN = "收起环境依赖详情 ▴";
const DIAGNOSTICS_DETAIL_CLOSED = "环境依赖详情 ▾";

const state = {
  summary: null,
  detailOpen: false,
  shellReady: false,
};

function explainCheck(item) {
  if (!item) return "未知问题";
  return item.label || item.check || "未知问题";
}

function explainCheckDetail(item) {
  if (!item) return "暂无进一步说明。";
  return item.next_step || item.detail || "请根据详细日志继续排查。";
}

function issueTone(item) {
  return item?.needs_external_fix ? "danger" : "warn";
}

function issueSummary(summary) {
  const trainErrors = summary?.train_preflight?.errors || [];
  const coverErrors = summary?.cover_preflight?.errors || [];
  const usableModelCount = Number(summary?.usable_model_count || 0);
  const hasIssue = trainErrors.length > 0 || coverErrors.length > 0 || usableModelCount <= 0;

  return {
    hasIssue,
    trainErrors,
    coverErrors,
    usableModelCount,
  };
}

function buildIssueCard(title, detail, next, tone = "warn") {
  return `
    <div class="guidance-item ${tone}">
      <strong>${escapeHtml(title)}</strong>
      ${renderPathLine(detail, { mono: false, subtle: true })}
      ${renderPathLine(next, { mono: false })}
    </div>
  `;
}

function buildCompactReadyCard() {
  return `
    <div class="guidance-item diagnostics-compact-note success" data-diagnostics-healthy="true">
      <strong>系统环境 100% 就绪</strong>
      <div class="artifact-path subtle"><span class="path-text">可正常创建任务。</span></div>
    </div>
  `;
}

function ensureDiagnosticsShell() {
  if (state.shellReady) return;

  const panel = $("diagnosticsPanel");
  if (!panel) return;

  const title = panel.querySelector(".panel-head h2");
  if (title) {
    title.textContent = DIAGNOSTICS_TITLE;
  }

  const actions = panel.querySelector(".panel-actions");
  if (actions && !$(TOGGLE_BUTTON_ID)) {
    const button = document.createElement("button");
    button.type = "button";
    button.id = TOGGLE_BUTTON_ID;
    button.className = "ghost-btn";
    button.textContent = DIAGNOSTICS_DETAIL_CLOSED;
    button.setAttribute("aria-expanded", "false");
    actions.prepend(button);
  }

  const grid = panel.querySelector(".diagnostic-grid");
  if (grid && !$(READY_NOTE_ID)) {
    const note = document.createElement("div");
    note.id = READY_NOTE_ID;
    note.className = "diagnostics-ready-note";
    note.textContent = "正在读取诊断结果...";
    grid.insertAdjacentElement("afterend", note);
  }

  if (!$(DETAIL_PANEL_ID)) {
    const sections = Array.from(panel.querySelectorAll(".detail-section"));
    if (sections.length) {
      const wrapper = document.createElement("div");
      wrapper.id = DETAIL_PANEL_ID;
      wrapper.className = "diagnostics-detail-panel";
      wrapper.hidden = true;
      sections[0].before(wrapper);
      sections.forEach(section => wrapper.appendChild(section));
    }
  }

  const toggle = $(TOGGLE_BUTTON_ID);
  if (toggle) {
    toggle.addEventListener("click", async () => {
      const nextOpen = !state.detailOpen;
      await setDiagnosticsDetailOpen(nextOpen);
    });
  }

  injectDiagnosticsStyles();
  state.shellReady = true;
}

function injectDiagnosticsStyles() {
  if (document.getElementById("diagnosticsInlineStyles")) return;
  const style = document.createElement("style");
  style.id = "diagnosticsInlineStyles";
  style.textContent = `
    .diagnostics-ready-note {
      margin-top: 10px;
      font-size: 12px;
      line-height: 1.5;
      color: var(--muted);
    }
    .diagnostics-ready-note.warn {
      color: #ffd6ab;
    }
    .diagnostics-ready-note.danger {
      color: #ffd0d8;
    }
    .diagnostics-ready-note.success {
      color: var(--muted);
    }
    .diagnostics-detail-panel {
      overflow: hidden;
    }
    .diagnostics-detail-panel[hidden] {
      display: none !important;
    }
    .diagnostics-compact-note {
      padding: 8px 0;
      border: 0;
      background: transparent;
      box-shadow: none;
      color: var(--muted);
    }
    .diagnostics-compact-note strong {
      display: inline;
      margin: 0;
      font-size: 12px;
      font-weight: 500;
      color: var(--muted);
    }
    .diagnostics-compact-note .artifact-path {
      margin-top: 2px;
      font-size: 12px;
    }
  `;
  document.head.appendChild(style);
}

async function setDiagnosticsDetailOpen(open) {
  const detailPanel = $(DETAIL_PANEL_ID);
  const toggle = $(TOGGLE_BUTTON_ID);
  if (!detailPanel || !toggle) return;

  state.detailOpen = Boolean(open);
  toggle.textContent = state.detailOpen ? DIAGNOSTICS_DETAIL_OPEN : DIAGNOSTICS_DETAIL_CLOSED;
  toggle.setAttribute("aria-expanded", String(state.detailOpen));
  await slideToggle(detailPanel, state.detailOpen);
}

function collectGuidance(summary) {
  const { hasIssue, trainErrors, coverErrors, usableModelCount } = issueSummary(summary);
  if (!hasIssue) {
    return buildCompactReadyCard();
  }

  const blocks = [];
  if (trainErrors.length) {
    const first = trainErrors[0];
    blocks.push(
      buildIssueCard(
        "当前不能稳定训练",
        `训练链路阻塞在：${explainCheck(first)}`,
        explainCheckDetail(first),
        issueTone(first),
      )
    );
  }

  if (usableModelCount <= 0) {
    blocks.push(
      buildIssueCard(
        "当前不能翻唱",
        "系统里还没有可直接用于翻唱的模型。",
        "下一步：导入一个正确的 .pth / .index，或重新扫描模型目录。",
        "danger",
      )
    );
  } else if (coverErrors.length) {
    const first = coverErrors[0];
    blocks.push(
      buildIssueCard(
        "翻唱入口仍有阻塞",
        `翻唱链路阻塞在：${explainCheck(first)}`,
        explainCheckDetail(first),
        issueTone(first),
      )
    );
  }

  return blocks.join("");
}

function renderIssueSummary(summary) {
  const { hasIssue, trainErrors, coverErrors, usableModelCount } = issueSummary(summary);
  const extraIssues = [];

  for (const item of trainErrors) {
    extraIssues.push({
      title: `训练 / ${explainCheck(item)}`,
      detail: item.detail || item.value || "-",
      next: explainCheckDetail(item),
      tone: issueTone(item),
    });
  }
  for (const item of coverErrors) {
    extraIssues.push({
      title: `翻唱 / ${explainCheck(item)}`,
      detail: item.detail || item.value || "-",
      next: explainCheckDetail(item),
      tone: issueTone(item),
    });
  }
  if (usableModelCount <= 0 && !coverErrors.length) {
    extraIssues.push({
      title: "翻唱 / 可用模型",
      detail: "当前可用模型数为 0。",
      next: "请先导入一个正确的 .pth / .index，或重新扫描模型目录。",
      tone: "danger",
    });
  }

  const unique = [];
  const seen = new Set();
  for (const item of extraIssues) {
    const key = `${item.title}|${item.detail}|${item.next}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }

  $("diagGuidance").innerHTML = collectGuidance(summary) + unique.map(item =>
    buildIssueCard(item.title, item.detail, item.next, item.tone)
  ).join("");

  const readyNote = $(READY_NOTE_ID);
  if (!readyNote) return;

  if (hasIssue) {
    readyNote.textContent = "存在阻塞项，展开环境依赖详情可查看原因和下一步建议。";
    readyNote.className = `diagnostics-ready-note ${usableModelCount <= 0 ? "danger" : "warn"}`;
  } else {
    readyNote.textContent = "系统环境已就绪，可以创建训练或翻唱任务。";
    readyNote.className = "diagnostics-ready-note success";
  }
}

function renderMissingDeps(summary) {
  const items = [
    ...(summary.train_preflight?.errors || []),
    ...(summary.cover_preflight?.errors || []),
  ];
  const seen = new Set();
  const tags = [];

  if (!Number(summary.usable_model_count || 0)) {
    tags.push(`<span class="tag danger">当前没有可用模型</span>`);
  }

  for (const item of items) {
    const label = explainCheck(item);
    if (seen.has(label)) continue;
    seen.add(label);
    tags.push(`<span class="tag ${issueTone(item)}">${escapeHtml(label)}</span>`);
  }

  $("diagMissingDeps").innerHTML = tags.length
    ? tags.join("")
    : `<span class="tag success">当前没有显式阻塞项</span>`;
}

function renderFailedJobs(items) {
  $("diagFailedJobs").innerHTML = items.length
    ? items.map(job => `
        <div class="failed-item">
          <strong>${escapeHtml(job.job_id)}</strong>
          <div class="failed-meta">
            <span>${escapeHtml(jobTypeLabel(job.job_type))}</span>
            <span>${escapeHtml(strategyLabel(job.strategy_key || ""))}</span>
            <span>${escapeHtml(stageText(job.current_stage || ""))}</span>
          </div>
          ${renderPathLine(job.error_log || "没有记录到错误摘要。", { mono: false, subtle: !job.error_log })}
        </div>
      `).join("")
    : `<div class="detail-empty">最近没有失败任务。</div>`;
}

export async function refreshDiagnostics(modelId = "v_001") {
  ensureDiagnosticsShell();

  try {
    const data = await getJSON(`/api/diagnostics/summary?model_id=${encodeURIComponent(modelId)}`);
    state.summary = data;
    setEngineChip(Boolean(data.rvc?.online), data.rvc?.base_url || "");
    $("diagRvcStatus").textContent = data.rvc?.online ? "在线" : "未就绪";
    $("diagUsableModelCount").textContent = data.usable_model_count ?? 0;
    renderMissingDeps(data);
    renderChecks($("diagTrainChecks"), data.train_preflight?.checks || []);
    renderChecks($("diagCoverChecks"), data.cover_preflight?.checks || []);
    renderIssueSummary(data);
    renderFailedJobs(data.last_failed_jobs || []);
  } catch (error) {
    showToast(`诊断面板加载失败：${toErrorMessage(error)}`, "error");
  }
}

export function initDiagnostics(getModelId) {
  ensureDiagnosticsShell();
  $("diagnosticsRefreshBtn").addEventListener("click", () => refreshDiagnostics(getModelId()));
}

export function getDiagnosticsState() {
  return state.summary;
}

export function summarizeTrainIssue(summary) {
  const first = summary?.train_preflight?.errors?.[0];
  return first ? explainCheck(first) : "训练预检未通过";
}

export function summarizeCoverIssue(summary) {
  const first = summary?.cover_preflight?.errors?.[0];
  return first ? explainCheck(first) : "翻唱预检未通过";
}
