import { getJSON, postJSON, toErrorMessage } from "./api.js";
import {
  $,
  artifactTypeLabel,
  escapeHtml,
  formatBytes,
  formatDateTime,
  loadUiState,
  jobTypeLabel,
  renderPathLine,
  renderStagePill,
  renderStatusPill,
  saveUiState,
  showToast,
  slideToggle,
  stageText,
  statusText,
  strategyLabel,
} from "./ui.js";

const JOB_TECHNICAL_STATE_KEY = "feishark_ui_task_technical_collapsed";
const JOB_LOGS_STATE_KEY = "feishark_ui_task_logs_collapsed";

const state = {
  limit: 8,
  offset: 0,
  selectedJobId: null,
  filters: {},
  lastArtifacts: [],
  lastDetailSignature: "",
  lastDetailJobId: null,
  lastJobsSignature: "",
  lastSummarySignature: "",
  lastRenderedSelection: null,
  lastTrainRegistrySignature: "",
  lastAnnouncedTrainModelSignature: "",
  jobArtifactsCollapsed: true,
};

function isFailedStatus(status) {
  return status === "failed" || status === "失败";
}

function isPendingStatus(status) {
  return status === "pending" || status === "queued";
}

function isCompletedStatus(status) {
  return status === "completed" || status === "完成";
}

function buildJobSignature(job) {
  return [
    job.job_id,
    job.status || "",
    job.current_stage || "",
    job.updated_at || "",
    job.error_log || "",
    job.voice_model_id || "",
    job.generated_model_id || "",
  ].join("|");
}

function buildJobsSignature(items) {
  return items.map(buildJobSignature).join("||");
}

function filtersFromForm() {
  return {
    job_type: $("jobsFilterType").value,
    status: $("jobsFilterStatus").value,
    strategy_key: $("jobsFilterStrategy").value,
    voice_name: $("jobsFilterVoiceName").value.trim(),
  };
}

function buildQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  return search.toString() ? `?${search.toString()}` : "";
}

function renderSummary(summary) {
  const signature = JSON.stringify(summary || {});
  if (signature === state.lastSummarySignature) return;
  $("summaryPending").textContent = summary.pending_count ?? 0;
  $("summaryProcessing").textContent = summary.processing_count ?? 0;
  $("summaryFailed").textContent = summary.failed_count ?? 0;
  $("summaryCompleted").textContent = summary.completed_count ?? 0;
  state.lastSummarySignature = signature;
}

function renderJobsTable(items) {
  const body = $("jobsTableBody");
  if (!items.length) {
    body.innerHTML = `<tr><td colspan="7" class="table-placeholder">当前筛选条件下没有任务。</td></tr>`;
    return;
  }

  body.innerHTML = items.map(job => `
    <tr
      class="job-row ${state.selectedJobId === job.job_id ? "is-active" : ""} ${isFailedStatus(job.status) ? "is-failed" : ""}"
      data-job-id="${escapeHtml(job.job_id)}"
    >
      <td class="mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</td>
      <td>${escapeHtml(jobTypeLabel(job.job_type))}</td>
      <td>${escapeHtml(strategyLabel(job.strategy_key))}</td>
      <td>${renderStatusPill(job.status)}</td>
      <td>${renderStagePill(job.current_stage, job.status)}</td>
      <td title="${escapeHtml(job.voice_name || "-")}">${escapeHtml(job.voice_name || "-")}</td>
      <td>${escapeHtml(formatDateTime(job.created_at))}</td>
    </tr>
  `).join("");
}

function artifactDownloadLabel(item) {
  if (item.artifact_type === "cover_master") return "下载 final_master.wav";
  if (item.artifact_type === "train_model_pth") return "下载 .pth";
  if (item.artifact_type === "train_model_index") return "下载 .index";
  return "下载产物";
}

function getJobTechnicalCollapsed() {
  return Boolean(loadUiState(JOB_TECHNICAL_STATE_KEY, true));
}

function getJobLogsCollapsed() {
  return Boolean(loadUiState(JOB_LOGS_STATE_KEY, true));
}

function parseDateValue(value) {
  if (!value) return 0;
  const timestamp = new Date(String(value).replace(" ", "T")).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function getLatestItem(items, selector) {
  return [...(items || [])].reduce((latest, item) => {
    if (!latest) return item;
    return parseDateValue(selector(item)) >= parseDateValue(selector(latest)) ? item : latest;
  }, null);
}

async function setDrawerState({
  drawerId,
  bodyId,
  buttonId,
  storageKey,
  collapsed,
  expandedLabel,
  collapsedLabel,
  immediate = false,
}) {
  const drawer = $(drawerId);
  const body = $(bodyId);
  const button = $(buttonId);
  if (!drawer || !body || !button) return;

  saveUiState(storageKey, collapsed);
  drawer.dataset.collapsed = String(collapsed);
  drawer.classList.toggle("is-collapsed", collapsed);
  button.setAttribute("aria-expanded", String(!collapsed));
  button.textContent = collapsed ? collapsedLabel : expandedLabel;

  if (immediate || body.hidden === collapsed) {
    body.hidden = collapsed;
    return;
  }

  await slideToggle(body, !collapsed);
}

function setJobTechnicalCollapsed(collapsed, { immediate = false } = {}) {
  return setDrawerState({
    drawerId: "jobTechnicalDrawer",
    bodyId: "jobTechnicalBody",
    buttonId: "jobTechnicalToggleBtn",
    storageKey: JOB_TECHNICAL_STATE_KEY,
    collapsed,
    expandedLabel: "收起技术详情 ▴",
    collapsedLabel: "展开技术详情 ▾",
    immediate,
  });
}

function setJobLogsCollapsed(collapsed, { immediate = false } = {}) {
  return setDrawerState({
    drawerId: "jobStageLogsDrawer",
    bodyId: "jobStageLogsBody",
    buttonId: "jobStageLogsToggleBtn",
    storageKey: JOB_LOGS_STATE_KEY,
    collapsed,
    expandedLabel: "收起阶段日志 ▴",
    collapsedLabel: "展开阶段日志 ▾",
    immediate,
  });
}

async function setJobArtifactsCollapsed(collapsed, { immediate = false } = {}) {
  const drawer = $("jobArtifactsDrawer");
  const body = $("jobArtifactsBody");
  const button = $("jobArtifactsToggleBtn");
  if (!drawer || !body || !button) return;

  state.jobArtifactsCollapsed = Boolean(collapsed);
  drawer.dataset.collapsed = String(state.jobArtifactsCollapsed);
  drawer.classList.toggle("is-collapsed", state.jobArtifactsCollapsed);
  button.setAttribute("aria-expanded", String(!state.jobArtifactsCollapsed));
  button.textContent = state.jobArtifactsCollapsed ? "展开产物 ▾" : "收起产物 ▴";

  if (immediate || body.hidden === state.jobArtifactsCollapsed) {
    body.hidden = state.jobArtifactsCollapsed;
    return;
  }

  await slideToggle(body, !state.jobArtifactsCollapsed);
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
  const content = rows.filter(Boolean).join("");
  return `
    <div class="meta-card detail-meta-card ${wide ? "wide" : ""}">
      <div class="detail-meta-title">${escapeHtml(title)}</div>
      <div class="detail-meta-lines">
        ${content || `<div class="detail-empty inline">暂无内容。</div>`}
      </div>
    </div>
  `;
}

function getJobDisplayName(job) {
  return job.voice_name || job.voice_model_id || job.job_id || "未命名任务";
}

function getJobSummaryText(job, failedLog = null) {
  const stage = stageText(job.current_stage);
  const typeLabel = jobTypeLabel(job.job_type);

  if (isCompletedStatus(job.status)) {
    if (job.job_type === "cover") return "这是一个已完成的翻唱任务，可下载成品或进入 Studio 继续处理。";
    if (job.generated_model_id) {
      return `这是一个已完成的训练任务，生成模型 ${job.generated_model_id} 已入库，可去模型库查看或直接下载产物。`;
    }
    return "这是一个已完成的训练任务，可下载 .pth 和 .index 继续使用。";
  }

  if (isFailedStatus(job.status)) {
    const failedStage = stageText(failedLog?.stage_name || job.current_stage);
    return `这是一个失败任务，最后失败在“${failedStage}”阶段。`;
  }

  if (isPendingStatus(job.status)) {
    return `这是一个排队中的${typeLabel}任务，正在等待算力释放。`;
  }

  return `这是一个正在进行中的${typeLabel}任务，当前停在“${stage}”阶段。`;
}

function getJobNextStepText(job) {
  if (isCompletedStatus(job.status)) {
    if (job.job_type === "cover") return "下一步：进入 Studio 或下载 final_master.wav。";
    if (job.generated_model_id) return "下一步：在模型库打开生成模型，或下载 .pth / .index。";
    return "下一步：下载 .pth / .index。";
  }

  if (isFailedStatus(job.status)) {
    return "下一步：优先重试，必要时查看技术详情中的错误原文。";
  }

  if (isPendingStatus(job.status)) {
    return "下一步：等待算力释放，必要时可取消。";
  }

  return "下一步：等待当前阶段完成。";
}

function renderJobSummary(job, failedLog = null) {
  const displayName = escapeHtml(getJobDisplayName(job));
  $("jobDetailTitle").textContent = getJobDisplayName(job);
  $("jobDetailTitle").title = job.job_id || getJobDisplayName(job);
  $("jobSummaryCard").innerHTML = `
    <div class="detail-summary-head">
      <div class="detail-summary-head-copy">
        <p class="detail-summary-eyebrow">任务摘要</p>
        <h4 class="detail-summary-title" title="${displayName}">${displayName}</h4>
        <div class="detail-summary-subline mono" title="${escapeHtml(job.job_id)}">任务 ID · ${escapeHtml(job.job_id)}</div>
      </div>
      <div class="detail-summary-badges">
        <span class="detail-summary-chip type">${escapeHtml(jobTypeLabel(job.job_type))}</span>
        ${renderStatusPill(job.status)}
        ${renderStagePill(job.current_stage, job.status)}
      </div>
    </div>
    <p class="detail-summary-text">${escapeHtml(getJobSummaryText(job, failedLog))}</p>
    <div class="detail-summary-foot">${escapeHtml(getJobNextStepText(job))}</div>
  `;
}

function renderJobCoreInfo(job) {
  const cards = [
    renderDetailCard("任务概览", [
      renderDetailRow("任务 ID", `<div class="mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</div>`),
      renderDetailRow("任务类型", escapeHtml(jobTypeLabel(job.job_type))),
      renderDetailRow("策略", escapeHtml(strategyLabel(job.strategy_key))),
    ]),
    renderDetailCard("当前进度", [
      renderDetailRow("当前状态", renderStatusPill(job.status)),
      renderDetailRow("当前阶段", renderStagePill(job.current_stage, job.status)),
      renderDetailRow("下一步", escapeHtml(getJobNextStepText(job))),
    ]),
    renderDetailCard("音色 / 模型", [
      renderDetailRow("音色名称", escapeHtml(job.voice_name || "-")),
      renderDetailRow("模型 ID", `<div class="mono" title="${escapeHtml(job.voice_model_id || "-")}">${escapeHtml(job.voice_model_id || "-")}</div>`),
    ]),
    renderDetailCard("输入与输出", [
      renderDetailRow("输入摘要", renderPathLine(job.input_path || "-", { subtle: !job.input_path })),
      renderDetailRow("工作目录", renderPathLine(job.output_root || "-", { subtle: !job.output_root })),
      renderDetailRow("创建时间", escapeHtml(formatDateTime(job.created_at))),
      renderDetailRow("更新时间", escapeHtml(formatDateTime(job.updated_at))),
    ], { wide: true }),
  ];

  if (job.job_type === "train" && job.generated_model_id) {
    cards.splice(3, 0, renderDetailCard("生成模型", [
      renderDetailRow("模型 ID", `<div class="mono" title="${escapeHtml(job.generated_model_id)}">${escapeHtml(job.generated_model_id)}</div>`),
      renderDetailRow("模型名称", escapeHtml(job.generated_model_name || "-")),
      renderDetailRow("当前状态", escapeHtml(job.generated_model_usable ? "已入库，可用于翻唱" : "已入库，待检查文件状态")),
    ]));
  }

  $("jobMetaGrid").innerHTML = cards.join("");
}

function renderJobTechnical(job, failedLog = null) {
  const rows = [
    renderDetailRow("输入路径", renderPathLine(job.input_path || "-", { subtle: !job.input_path })),
    renderDetailRow("工作目录", renderPathLine(job.output_root || "-", { subtle: !job.output_root })),
    renderDetailRow("原始状态", escapeHtml(job.status || "-")),
    renderDetailRow("原始阶段", escapeHtml(job.current_stage || "-")),
    renderDetailRow("原始策略键", escapeHtml(job.strategy_key || "-")),
    renderDetailRow("音色模型 ID", `<div class="mono" title="${escapeHtml(job.voice_model_id || "-")}">${escapeHtml(job.voice_model_id || "-")}</div>`),
  ];

  if (failedLog?.message || job.error_log) {
    rows.push(renderDetailRow("错误原文", renderPathLine(failedLog?.message || job.error_log || "没有记录到错误原文。", { mono: false })));
  }

  $("jobTechnicalSummary").textContent = failedLog?.message || job.error_log
    ? "完整路径、原始状态和错误原文默认收纳在这里。"
    : "完整路径、原始状态和调试字段默认收纳在这里。";
  $("jobTechnicalList").innerHTML = rows.join("");
  setJobTechnicalCollapsed(getJobTechnicalCollapsed(), { immediate: true }).catch(() => {});
}

function logToneClass(status) {
  if (status === "failed" || status === "失败") return "failed";
  if (status === "completed" || status === "完成") return "completed";
  return "started";
}

function renderJobStageLogs(items, job = null) {
  const container = $("jobStageLogsList");
  const latest = getLatestItem(items, item => item.created_at);
  const latestStage = stageText(latest?.stage_name || job?.current_stage || "pending");
  const latestTime = formatDateTime(latest?.created_at || job?.updated_at || "");
  $("jobStageLogsSummary").textContent = `最近阶段：${latestStage} · 共 ${items.length} 条日志 · 最近更新时间：${latestTime}`;

  if (!items.length) {
    container.innerHTML = `<div class="detail-empty inline">当前还没有阶段日志。</div>`;
    setJobLogsCollapsed(getJobLogsCollapsed(), { immediate: true }).catch(() => {});
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="log-item ${logToneClass(item.status)}">
      <strong>${escapeHtml(stageText(item.stage_name))}</strong>
      <div class="log-meta">
        <span>${escapeHtml(statusText(item.status))}</span>
        <span>${escapeHtml(formatDateTime(item.created_at))}</span>
      </div>
      ${renderPathLine(item.message || "没有附加说明。", { mono: false, subtle: !item.message })}
    </div>
  `).join("");
  setJobLogsCollapsed(getJobLogsCollapsed(), { immediate: true }).catch(() => {});
}

function renderDatasetList(items) {
  const container = $("jobDatasetsList");
  if (!items.length) {
    container.innerHTML = `<div class="detail-empty inline">当前任务没有关联数据集。</div>`;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="dataset-item">
      <strong>${escapeHtml(item.dataset_name || item.dataset_id)}</strong>
      <div class="dataset-meta">
        <span>${escapeHtml(strategyLabel(item.strategy_key))}</span>
        <span>${escapeHtml(`${item.file_count} 个文件`)}</span>
        <span>${escapeHtml(formatBytes(item.total_bytes))}</span>
      </div>
      ${renderPathLine(item.root_path || "-", { subtle: !item.root_path })}
    </div>
  `).join("");
}

function renderArtifacts(items) {
  const container = $("jobArtifactsList");
  if (!items.length) {
    container.innerHTML = `<div class="detail-empty inline">当前还没有登记产物。</div>`;
    $("jobArtifactsSummary").textContent = "当前还没有登记产物。";
    setJobArtifactsCollapsed(true, { immediate: true }).catch(() => {});
    return;
  }

  const seen = new Set();
  const orderedItems = [...items]
    .filter(item => {
      const key = `${item.artifact_type}|${item.file_path}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((left, right) => {
      if (left.is_final !== right.is_final) return right.is_final - left.is_final;
      return String(left.stage_name || "").localeCompare(String(right.stage_name || ""));
    });

  $("jobArtifactsSummary").textContent = orderedItems.length > 1
    ? `共 ${orderedItems.length} 个产物，默认收起列表。`
    : "当前任务只有 1 个产物，保持紧凑显示。";

  container.innerHTML = orderedItems.map(item => `
    <div class="artifact-item ${item.is_final ? "is-final" : ""}">
      <div class="artifact-item-head">
        <strong>${escapeHtml(artifactTypeLabel(item.artifact_type))}</strong>
        ${item.is_final ? '<span class="artifact-chip success">主产物</span>' : '<span class="artifact-chip pending">中间产物</span>'}
      </div>
      <div class="artifact-meta">
        <span>${escapeHtml(stageText(item.stage_name))}</span>
        <span>${escapeHtml(formatBytes(item.file_size))}</span>
      </div>
      ${renderPathLine(item.file_path)}
      ${(item.download_url || item.artifact_id) ? `
        <div class="panel-actions">
          <button
            class="ghost-btn"
            type="button"
            data-artifact-download="true"
            data-artifact-id="${escapeHtml(item.artifact_id || "")}"
            data-artifact-url="${escapeHtml(item.download_url || "")}"
          >${artifactDownloadLabel(item)}</button>
        </div>
      ` : ""}
    </div>
  `).join("");
  setJobArtifactsCollapsed(orderedItems.length > 1, { immediate: true }).catch(() => {});
}

function renderArtifactButton(item, { primary = false, label = null } = {}) {
  return `
    <button
      class="${primary ? "primary-btn warm" : "ghost-btn"}"
      type="button"
      data-artifact-download="true"
      data-artifact-id="${escapeHtml(item.artifact_id || "")}"
      data-artifact-url="${escapeHtml(item.download_url || "")}"
    >${escapeHtml(label || artifactDownloadLabel(item))}</button>
  `;
}

function renderActionBar(job) {
  const finalArtifacts = (state.lastArtifacts || [])
    .filter(item => item.is_final)
    .filter((item, index, array) => array.findIndex(other => other.artifact_type === item.artifact_type && other.file_path === item.file_path) === index);

  const studioArtifact = finalArtifacts.find(item => item.artifact_type === "cover_master") || null;
  const trainPthArtifact = finalArtifacts.find(item => item.artifact_type === "train_model_pth") || null;
  const trainIndexArtifact = finalArtifacts.find(item => item.artifact_type === "train_model_index") || null;
  const actions = [];

  if (isCompletedStatus(job.status) && job.job_type === "cover") {
    if (studioArtifact) {
      actions.push(`
        <button
          class="primary-btn warm"
          type="button"
          data-open-studio="true"
          data-job-id="${escapeHtml(job.job_id)}"
          data-artifact-id="${escapeHtml(studioArtifact.artifact_id || "")}"
        >进入 Studio</button>
      `);
    }
    if (studioArtifact) {
      actions.push(renderArtifactButton(studioArtifact, { label: "下载成品" }));
    }
  } else if (isCompletedStatus(job.status) && job.job_type === "train") {
    if (trainPthArtifact) {
      actions.push(renderArtifactButton(trainPthArtifact, { primary: true, label: "下载 .pth" }));
    }
    if (trainIndexArtifact) {
      actions.push(renderArtifactButton(trainIndexArtifact, { label: "下载 .index" }));
    }
    if (job.generated_model_id) {
      actions.push(`
        <button
          class="ghost-btn"
          type="button"
          data-open-model="true"
          data-model-id="${escapeHtml(job.generated_model_id)}"
        >在模型库打开</button>
      `);
    }
  } else if (isFailedStatus(job.status)) {
    actions.push(`<button class="primary-btn warm" type="button" data-action="retry">重试</button>`);
  } else if (isPendingStatus(job.status)) {
    actions.push(`<button class="ghost-btn danger" type="button" data-action="cancel">取消</button>`);
  }

  $("jobActionBar").innerHTML = actions.length
    ? actions.join("")
    : `<div class="detail-action-hint">当前没有可执行主操作。</div>`;
}

function openArtifactUrl(artifactUrl) {
  window.open(artifactUrl.startsWith("http") ? artifactUrl : `${window.location.origin}${artifactUrl}`, "_blank");
}

function renderEmptyDetail() {
  $("jobDetailTitle").textContent = "请选择一个任务";
  $("jobDetailTitle").title = "";
  $("jobActionBar").innerHTML = "";
  $("jobSummaryCard").innerHTML = `
    <div class="detail-summary-head">
      <div class="detail-summary-head-copy">
        <p class="detail-summary-eyebrow">任务摘要</p>
        <h4 class="detail-summary-title">选中一个任务后再继续</h4>
        <div class="detail-summary-subline">这里会先告诉你它是什么、现在到哪一步、下一步该做什么。</div>
      </div>
    </div>
    <p class="detail-summary-text">当前没有选中的任务。</p>
    <div class="detail-summary-foot">先在左侧任务列表里点一个任务。</div>
  `;
  $("jobMetaGrid").innerHTML = `
    <div class="meta-card detail-meta-card wide">
      <div class="detail-meta-title">核心信息</div>
      <div class="detail-meta-lines">
        <div class="detail-empty inline">选中任务后，这里会显示核心信息、输入输出和时间。</div>
      </div>
    </div>
  `;
  $("jobDatasetsList").innerHTML = `<div class="detail-empty inline">当前任务没有关联数据集。</div>`;
  $("jobArtifactsList").innerHTML = `<div class="detail-empty inline">当前还没有登记产物。</div>`;
  $("jobArtifactsSummary").textContent = "未选中任务，产物列表默认收起。";
  setJobArtifactsCollapsed(true, { immediate: true }).catch(() => {});
  $("jobTechnicalSummary").textContent = "完整路径、原始状态和错误原文默认收纳在这里。";
  $("jobTechnicalList").innerHTML = `<div class="detail-empty inline">当前没有可展示的技术详情。</div>`;
  $("jobStageLogsSummary").textContent = "默认收起完整 timeline，只保留最近阶段摘要。";
  $("jobStageLogsList").innerHTML = `<div class="detail-empty inline">当前还没有阶段日志。</div>`;
  $("jobTechnicalBody").hidden = true;
  $("jobTechnicalDrawer").dataset.collapsed = "true";
  $("jobTechnicalToggleBtn").setAttribute("aria-expanded", "false");
  $("jobTechnicalToggleBtn").textContent = "展开技术详情 ▾";
  $("jobStageLogsBody").hidden = true;
  $("jobStageLogsDrawer").dataset.collapsed = "true";
  $("jobStageLogsToggleBtn").setAttribute("aria-expanded", "false");
  $("jobStageLogsToggleBtn").textContent = "展开阶段日志 ▾";
}

async function loadJobDetail(jobId, { preserveScroll = true } = {}) {
  const detailPanel = $("jobDetailPanel");
  const scrollTop = preserveScroll ? (detailPanel?.scrollTop || 0) : 0;

  try {
    const [job, artifacts, logs, datasets] = await Promise.all([
      getJSON(`/api/jobs/${jobId}`),
      getJSON(`/api/jobs/${jobId}/artifacts`),
      getJSON(`/api/jobs/${jobId}/stage-logs`),
      getJSON(`/api/datasets?job_id=${encodeURIComponent(jobId)}&limit=20&offset=0`),
    ]);

    const stageLogs = logs.stage_logs || [];
    const failedLog = [...stageLogs].reverse().find(item => item.status === "failed" || item.status === "失败");

    renderJobSummary(job, failedLog);
    state.lastArtifacts = artifacts.artifacts || [];
    state.lastDetailJobId = jobId;
    state.lastDetailSignature = buildJobSignature(job);

    if (job.job_type === "train" && isCompletedStatus(job.status) && job.generated_model_id) {
      const announceSignature = `${job.job_id}|${job.generated_model_id}|${job.updated_at || ""}`;
      if (announceSignature !== state.lastAnnouncedTrainModelSignature) {
        state.lastAnnouncedTrainModelSignature = announceSignature;
        document.dispatchEvent(new CustomEvent("feishark:train-model-registered", {
          detail: { jobId: job.job_id, modelId: job.generated_model_id },
        }));
      }
    }

    renderActionBar(job);
    renderArtifacts(state.lastArtifacts);
    renderJobStageLogs(stageLogs, job);
    renderDatasetList(datasets.items || []);
    renderJobCoreInfo(job);
    renderJobTechnical(job, failedLog);

    if (detailPanel && preserveScroll) {
      detailPanel.scrollTop = scrollTop;
    }
  } catch (error) {
    showToast(`任务详情加载失败：${toErrorMessage(error)}`, "error");
  }
}

async function runJobAction(action) {
  if (!state.selectedJobId) return;

  try {
    const result = await postJSON(`/api/jobs/${state.selectedJobId}/${action}`);
    const humanAction = action === "retry" ? "重试" : action === "requeue" ? "重新入队" : "取消";
    const queueHint =
      result.queue_state === "waiting_for_compute_slot"
        ? "，任务会继续排队等待算力释放"
        : result.queue_state === "dispatch_requested"
          ? "，系统已经尝试安全派发"
          : "";
    showToast(`${humanAction}成功：${result.message || result.status || "已处理"}${queueHint}`, "success");
    await refreshJobs({ focusJobId: state.selectedJobId, forceDetail: true });
  } catch (error) {
    const humanAction = action === "retry" ? "重试" : action === "requeue" ? "重新入队" : "取消";
    showToast(`${humanAction}失败：${toErrorMessage(error)}`, "error");
  }
}

export async function refreshJobs({ focusJobId = null, forceDetail = false } = {}) {
  state.filters = filtersFromForm();
  const query = buildQuery({ ...state.filters, limit: state.limit, offset: state.offset });
  const [jobsResp, summary] = await Promise.all([
    getJSON(`/api/jobs${query}`),
    getJSON("/api/jobs/summary"),
  ]);

  renderSummary(summary);

  const items = jobsResp.items || [];
  const page = Math.floor(state.offset / state.limit) + 1;
  $("jobsPageInfo").textContent = `第 ${page} 页`;

  if (focusJobId) {
    state.selectedJobId = focusJobId;
  }

  if (items.length && !items.some(item => item.job_id === state.selectedJobId) && !focusJobId) {
    state.selectedJobId = items[0].job_id;
  }

  if (!items.length) {
    state.selectedJobId = null;
  }

  const listSignature = buildJobsSignature(items);
  const selectionSignature = state.selectedJobId || "";
  const trainRegistrySignature = items
    .filter(item => item.job_type === "train" && (item.current_stage === "train_register_model" || isCompletedStatus(item.status)))
    .map(item => [item.job_id, item.status || "", item.current_stage || "", item.updated_at || ""].join("|"))
    .join("||");
  const modelsMayBeStale = Boolean(trainRegistrySignature) && trainRegistrySignature !== state.lastTrainRegistrySignature;
  state.lastTrainRegistrySignature = trainRegistrySignature;
  const shouldRenderList =
    listSignature !== state.lastJobsSignature ||
    selectionSignature !== state.lastRenderedSelection;

  if (shouldRenderList) {
    renderJobsTable(items);
    state.lastJobsSignature = listSignature;
    state.lastRenderedSelection = selectionSignature;
  }

  if (!state.selectedJobId) {
    renderEmptyDetail();
    state.lastDetailJobId = null;
    state.lastDetailSignature = "";
    return { items, selectedJobId: "", modelsMayBeStale };
  }

  const currentListJob = items.find(item => item.job_id === state.selectedJobId);
  const nextSignature = currentListJob ? buildJobSignature(currentListJob) : "";
  const shouldReloadDetail =
    forceDetail ||
    state.lastDetailJobId !== state.selectedJobId ||
    (nextSignature && nextSignature !== state.lastDetailSignature);

  if (shouldReloadDetail) {
    await loadJobDetail(state.selectedJobId, { preserveScroll: true });
  }

  return {
    items,
    selectedJobId: state.selectedJobId,
    modelsMayBeStale,
  };
}

export function initJobs() {
  setJobArtifactsCollapsed(true, { immediate: true }).catch(() => {});
  setJobTechnicalCollapsed(getJobTechnicalCollapsed(), { immediate: true }).catch(() => {});
  setJobLogsCollapsed(getJobLogsCollapsed(), { immediate: true }).catch(() => {});

  $("jobsFilterForm").addEventListener("submit", async event => {
    event.preventDefault();
    state.offset = 0;
    await refreshJobs({ forceDetail: true });
  });

  $("jobsResetBtn").addEventListener("click", async () => {
    $("jobsFilterType").value = "";
    $("jobsFilterStatus").value = "";
    $("jobsFilterStrategy").value = "";
    $("jobsFilterVoiceName").value = "";
    state.offset = 0;
    await refreshJobs({ forceDetail: true });
  });

  $("jobsRefreshBtn").addEventListener("click", () => refreshJobs({ forceDetail: true }));

  $("jobsPrevBtn").addEventListener("click", async () => {
    state.offset = Math.max(0, state.offset - state.limit);
    await refreshJobs();
  });

  $("jobsNextBtn").addEventListener("click", async () => {
    state.offset += state.limit;
    await refreshJobs();
  });

  $("jobsTableBody").addEventListener("click", async event => {
    const row = event.target.closest(".job-row");
    if (!row) return;
    state.selectedJobId = row.dataset.jobId;
    await refreshJobs({ forceDetail: true });
  });

  $("jobDetailPanel").addEventListener("click", event => {
    if (event.target.closest("#jobArtifactsToggleBtn")) {
      setJobArtifactsCollapsed(!state.jobArtifactsCollapsed).catch(() => {});
      return;
    }

    if (event.target.closest("#jobTechnicalToggleBtn")) {
      setJobTechnicalCollapsed(!getJobTechnicalCollapsed()).catch(() => {});
      return;
    }

    if (event.target.closest("#jobStageLogsToggleBtn")) {
      setJobLogsCollapsed(!getJobLogsCollapsed()).catch(() => {});
    }
  });

  $("jobActionBar").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]");
    const artifactButton = event.target.closest("button[data-artifact-download]");
    const studioButton = event.target.closest("button[data-open-studio]");
    const modelButton = event.target.closest("button[data-open-model]");

    if (studioButton) {
      const jobId = studioButton.dataset.jobId || state.selectedJobId;
      if (!jobId) return;
      const params = new URLSearchParams({ job_id: jobId });
      if (studioButton.dataset.artifactId) {
        params.set("artifact_id", studioButton.dataset.artifactId);
      }
      window.location.href = `/studio?${params.toString()}`;
      return;
    }

    if (artifactButton) {
      const artifactUrl = artifactButton.dataset.artifactUrl;
      if (artifactUrl) {
        openArtifactUrl(artifactUrl);
        return;
      }

      const artifactId = artifactButton.dataset.artifactId;
      if (artifactId && state.selectedJobId) {
        window.open(`${window.location.origin}/api/jobs/${state.selectedJobId}/artifacts/${artifactId}/download`, "_blank");
        return;
      }
    }

    if (modelButton) {
      const modelId = modelButton.dataset.modelId || "";
      if (!modelId) return;
      document.querySelector('[data-mobile-tab-target="models"]')?.click();
      document.getElementById("modelPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.dispatchEvent(new CustomEvent("feishark:focus-model", { detail: { modelId } }));
      return;
    }

    if (!button) return;
    await runJobAction(button.dataset.action);
  });

  $("jobArtifactsList").addEventListener("click", event => {
    const button = event.target.closest("button[data-artifact-download]");
    if (!button || !state.selectedJobId) return;

    const artifactUrl = button.dataset.artifactUrl;
    if (artifactUrl) {
      openArtifactUrl(artifactUrl);
      return;
    }

    const artifactId = button.dataset.artifactId;
    if (artifactId) {
      window.open(`${window.location.origin}/api/jobs/${state.selectedJobId}/artifacts/${artifactId}/download`, "_blank");
      return;
    }

    window.open(`${window.location.origin}/api/download/${state.selectedJobId}`, "_blank");
  });

  document.addEventListener("feishark:focus-job", async event => {
    const jobId = event.detail?.jobId || "";
    if (!jobId) return;
    document.querySelector('[data-mobile-tab-target="dashboard"]')?.click();
    document.getElementById("taskCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
    state.offset = 0;
    state.selectedJobId = jobId;
    await refreshJobs({ focusJobId: jobId, forceDetail: true });
  });
}
