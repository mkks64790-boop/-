import { getJSON, postJSON, toErrorMessage } from "./api.js";
import {
  $,
  artifactTypeLabel,
  escapeHtml,
  formatBytes,
  formatDateTime,
  jobTypeLabel,
  renderPathLine,
  renderStagePill,
  renderStatusPill,
  showToast,
  stageText,
  statusText,
  strategyLabel,
} from "./ui.js";

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

function actionButton(action, label, disabled) {
  return `<button class="ghost-btn" type="button" data-action="${action}" ${disabled ? "disabled" : ""}>${label}</button>`;
}

function artifactDownloadLabel(item) {
  if (item.artifact_type === "cover_master") return "下载 final_master.wav";
  if (item.artifact_type === "train_model_pth") return "下载 .pth";
  if (item.artifact_type === "train_model_index") return "下载 .index";
  return "下载产物";
}

function renderJobMeta(job, failedLog = null) {
  const blocks = [];
  if (isFailedStatus(job.status) && failedLog) {
    blocks.push(`
      <div class="error-callout">
        <strong>最后失败阶段：${escapeHtml(stageText(failedLog.stage_name))}</strong>
        ${renderPathLine(failedLog.message || job.error_log || "没有记录到失败摘要。", { mono: false })}
      </div>
    `);
  }

  const items = [
    ["Job ID", `<div class="meta-value mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</div>`],
    ["任务类型", escapeHtml(jobTypeLabel(job.job_type))],
    ["策略", escapeHtml(strategyLabel(job.strategy_key))],
    ["任务状态", renderStatusPill(job.status)],
    ["当前阶段", renderStagePill(job.current_stage, job.status)],
    ["音色名称", escapeHtml(job.voice_name || "-")],
    ["模型 ID", `<div class="meta-value mono" title="${escapeHtml(job.voice_model_id || "-")}">${escapeHtml(job.voice_model_id || "-")}</div>`],
    ["输入路径", renderPathLine(job.input_path || "-")],
    ["工作目录", renderPathLine(job.output_root || "-")],
    ["创建时间", escapeHtml(formatDateTime(job.created_at))],
    ["更新时间", escapeHtml(formatDateTime(job.updated_at))],
    ["错误摘要", renderPathLine(job.error_log || "-", { mono: false, subtle: !job.error_log })],
  ];

  blocks.push(...items.map(([label, value]) => `
    <div class="meta-card">
      <div class="meta-label">${label}</div>
      <div class="meta-value">${value}</div>
    </div>
  `));

  $("jobMetaGrid").innerHTML = blocks.join("");
}

function renderActionBar(job) {
  const finalArtifacts = (state.lastArtifacts || []).filter(item => item.is_final);
  const studioArtifact = finalArtifacts.find(item => item.artifact_type === "cover_master") || null;
  const downloadButtons = finalArtifacts.map(item => `
    <button
      class="ghost-btn"
      type="button"
      data-artifact-download="true"
      data-artifact-id="${escapeHtml(item.artifact_id || "")}"
      data-artifact-url="${escapeHtml(item.download_url || "")}"
    >${artifactDownloadLabel(item)}</button>
  `);

  const isFailed = isFailedStatus(job.status);
  const isPending = isPendingStatus(job.status);
  const canOpenStudio = job.job_type === "cover" && isCompletedStatus(job.status) && Boolean(studioArtifact);
  const studioButton = canOpenStudio
    ? `<button
        class="ghost-btn"
        type="button"
        data-open-studio="true"
        data-job-id="${escapeHtml(job.job_id)}"
        data-artifact-id="${escapeHtml(studioArtifact?.artifact_id || "")}"
      >进入 Studio</button>`
    : "";

  $("jobActionBar").innerHTML = [
    studioButton,
    ...downloadButtons,
    actionButton("retry", "重试", !isFailed),
    actionButton("requeue", "重新入队", !(isFailed || isPending)),
    actionButton("cancel", "取消", !isPending),
  ].filter(Boolean).join("");
}

function renderDatasets(items) {
  const container = $("jobDatasetsList");
  if (!items.length) {
    container.innerHTML = `<div class="detail-empty">当前任务没有关联数据集。</div>`;
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
      ${renderPathLine(item.root_path || "-")}
    </div>
  `).join("");
}

function renderArtifacts(items) {
  const container = $("jobArtifactsList");
  if (!items.length) {
    container.innerHTML = `<div class="detail-empty">当前还没有登记产物。</div>`;
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
}

function logToneClass(status) {
  if (status === "failed" || status === "失败") return "failed";
  if (status === "completed" || status === "完成") return "completed";
  return "started";
}

function renderLogs(items) {
  const container = $("jobStageLogsList");
  if (!items.length) {
    container.innerHTML = `<div class="detail-empty">当前还没有阶段日志。</div>`;
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
}

function openArtifactUrl(artifactUrl) {
  window.open(artifactUrl.startsWith("http") ? artifactUrl : `${window.location.origin}${artifactUrl}`, "_blank");
}

function renderEmptyDetail() {
  $("jobDetailTitle").textContent = "请选择一个任务";
  $("jobActionBar").innerHTML = "";
  $("jobMetaGrid").innerHTML = `<div class="meta-card empty">选中任务后，这里会显示状态、阶段、路径和错误摘要。</div>`;
  $("jobDatasetsList").innerHTML = `<div class="detail-empty">当前任务没有关联数据集。</div>`;
  $("jobArtifactsList").innerHTML = `<div class="detail-empty">当前还没有登记产物。</div>`;
  $("jobStageLogsList").innerHTML = `<div class="detail-empty">当前还没有阶段日志。</div>`;
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

    $("jobDetailTitle").textContent = job.job_id;
    state.lastArtifacts = artifacts.artifacts || [];
    state.lastDetailJobId = jobId;
    state.lastDetailSignature = buildJobSignature(job);

    renderJobMeta(job, failedLog);
    renderActionBar(job);
    renderArtifacts(state.lastArtifacts);
    renderLogs(stageLogs);
    renderDatasets(datasets.items || []);

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

  if (items.length && !items.some(item => item.job_id === state.selectedJobId)) {
    state.selectedJobId = items[0].job_id;
  }

  if (!items.length) {
    state.selectedJobId = null;
  }

  const listSignature = buildJobsSignature(items);
  const selectionSignature = state.selectedJobId || "";
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
    return;
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
}

export function initJobs() {
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

  $("jobActionBar").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]");
    const artifactButton = event.target.closest("button[data-artifact-download]");
    const studioButton = event.target.closest("button[data-open-studio]");

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
}
