import { ApiError, getJSON, patchJSON, postJSON, toErrorMessage } from "./api.js";
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
const JOB_TRAINING_CONFIG_STATE_KEY = "feishark_ui_task_training_config_collapsed";
const JOB_LOGS_STATE_KEY = "feishark_ui_task_logs_collapsed";
const MEMORY_FULL_STATE_KEY = "feishark_ui_memory_full_collapsed";
const TEST_RECORDS_VISIBLE_KEY = "feishark_ui_show_test_records";
const TEST_RECORDS_EVENT = "feishark:test-records-visibility-changed";
const STAGE56_RVC_SMOKE_MODEL_ID = "v_d4d7e1c1";
const STAGE47_EXPECTED_MODEL_NAME = "朱朱_stage47_single_long";
const MEMORY_STAGE47_NEEDLES = [
  STAGE56_RVC_SMOKE_MODEL_ID,
  "朱朱_stage47_single_long",
  "task_b2272d133fff",
  "BLOCK_TRAINING=false",
  "Stage47 Studio scope",
];
const REVIEW_QUEUE_VISIBLE_COUNT = 3;
const MEMORY_RECENT_VISIBLE_COUNT = 6;
const SMOKE_ONLY_REVIEW_NOTE = "stage49 browser smoke only - not a human quality verdict";

const REVIEW_VERDICT_LABELS = {
  unreviewed: "未验收",
  needs_work: "需返工",
  usable: "可用候选",
  release_candidate: "候选成品",
  rejected: "废弃",
};

const ARTIFACT_QUALITY_LABELS = {
  reviewable: "Can review",
  needs_manual_quality_check: "Manual QC",
  blocked_auto: "Auto blocked",
};

const ARTIFACT_QUALITY_CLASSES = {
  reviewable: "success",
  needs_manual_quality_check: "pending",
  blocked_auto: "failed",
};

const REVIEW_ROUTE_LABELS = {
  needs_human_review: "继续人工试听",
  route_to_rework: "回 Factory 调分离 / 重跑 cover",
  route_to_candidate_pool: "保留为可用候选",
  route_to_release_candidate: "送入 Factory 候选成品",
  route_to_archive_or_rerun: "标记废弃，建议重跑",
};

const TRAIN_STAGE_FLOW = {
  single_long_preprocess: [
    "train_upload",
    "train_preflight",
    "train_dataset_prepare",
    "train_preprocess",
    "train_pitch_extract",
    "train_feature_extract",
    "train_core",
    "train_index",
    "train_register_model",
  ],
  multi_clean_direct: [
    "train_upload",
    "train_preflight",
    "train_dataset_prepare",
    "train_direct_prepare",
    "train_pitch_extract",
    "train_feature_extract",
    "train_core",
    "train_index",
    "train_register_model",
  ],
};

const TRAIN_STAGE_NOTES = {
  train_upload: "接收训练素材",
  train_preflight: "环境与素材预检",
  train_dataset_prepare: "建立训练数据集",
  train_preprocess: "长素材切片预处理",
  train_direct_prepare: "多文件直接整理",
  train_pitch_extract: "提取 F0 / pitch",
  train_feature_extract: "提取音频特征",
  train_core: "执行 RVC 训练",
  train_index: "生成检索索引",
  train_register_model: "登记模型资产",
};

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
  trainLifecycleByJob: new Map(),
  trainLifecycleToastAt: new Map(),
  trainingRecoveryByJob: new Map(),
  jobArtifactsCollapsed: true,
  stage47Acceptance: {
    unavailable: "",
    trainingJob: null,
    model: null,
    coverJob: null,
    coverArtifact: null,
    coverArtifacts: [],
    studioReady: false,
    studioUrl: "",
  },
  trainingObserver: {
    unavailable: "",
    observer: null,
    loaded: false,
  },
  reviewQueue: {
    items: [],
    summary: {},
    unavailable: "",
    loaded: false,
  },
  memoryLab: {
    items: [],
    summary: null,
    unavailable: "",
    loaded: false,
    selectedMemoryId: "",
    fullListCollapsed: Boolean(loadUiState(MEMORY_FULL_STATE_KEY, true)),
    filters: {
      q: "",
      category: "",
      tag: "",
    },
    rescanInFlight: false,
  },
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

function isActiveTrainingStatus(status) {
  return ["running", "processing", "训练中", "进行中", "处理中"].includes(status || "");
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

function summarizeVisibleJobs(items = []) {
  const summary = {
    pending_count: 0,
    processing_count: 0,
    failed_count: 0,
    completed_count: 0,
  };
  for (const job of items) {
    if (isFailedStatus(job.status)) summary.failed_count += 1;
    else if (isCompletedStatus(job.status)) summary.completed_count += 1;
    else if (isPendingStatus(job.status)) summary.pending_count += 1;
    else if (isActiveTrainingStatus(job.status) || ["processing", "running", "started"].includes(String(job.status || "").toLowerCase())) {
      summary.processing_count += 1;
    }
  }
  return summary;
}

function renderTestRecordsToggle(hiddenCount = 0) {
  const anchor = $("jobsFilterForm");
  if (!anchor) return;
  let toggle = document.getElementById("dashboardTestRecordsToggle");
  if (!toggle) {
    toggle = document.createElement("div");
    toggle.id = "dashboardTestRecordsToggle";
    toggle.className = "test-record-toggle";
    anchor.insertAdjacentElement("afterend", toggle);
  }

  const visible = getShowTestRecords();
  toggle.innerHTML = `
    <label class="test-record-toggle-label">
      <input id="dashboardShowTestRecords" type="checkbox" ${visible ? "checked" : ""}>
      <span>显示测试记录</span>
    </label>
    <span class="test-record-toggle-note">${
      visible
        ? "当前包含 smoke / stage / test / self_check / playwright 记录。"
        : `默认隐藏测试记录${hiddenCount ? `，已隐藏 ${hiddenCount} 条。` : "。"}`
    }</span>
  `;
  $("dashboardShowTestRecords")?.addEventListener("change", event => {
    saveShowTestRecords(event.target.checked);
    refreshJobs({ forceDetail: true }).catch(error => {
      showToast(`测试记录开关刷新失败：${toErrorMessage(error)}`, "error");
    });
  });
}

function syncTestPanelsVisibility() {
  const visible = getShowTestRecords();
  [
    "stage47E2ePanel",
    "trainingObserverPanel",
    "dashboardReviewQueuePanel",
    "memoryLabPanel",
  ].forEach(id => {
    const panel = $(id);
    if (panel) panel.hidden = !visible;
  });
}

function stage47SearchText(value = {}) {
  if (!value) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function hasStage47Hint(value = {}) {
  const text = stage47SearchText(value);
  return /stage[\s_-]*47/i.test(text) || text.includes(STAGE47_EXPECTED_MODEL_NAME);
}

function trainingObserverCoverModelId(observer = null) {
  if (!observer) return "";
  const directCandidates = [
    observer.generated_model_id,
    observer.model_id,
    observer.voice_model_id,
    observer.registered_model_id,
    observer.model?.model_id,
    observer.model_registration?.model_id,
    observer.model_registration_result?.model_id,
  ].filter(Boolean);
  if (directCandidates.length) return directCandidates[0];

  const observerText = stage47SearchText(observer);
  const stage56Hints = [
    STAGE56_RVC_SMOKE_MODEL_ID,
    STAGE47_EXPECTED_MODEL_NAME,
    "train_7f4d6b4e611e",
  ];
  return stage56Hints.some(hint => observerText.includes(hint)) ? STAGE56_RVC_SMOKE_MODEL_ID : "";
}

function normalizeModelsPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.models)) return payload.models;
  if (Array.isArray(payload?.value)) return payload.value;
  return [];
}

function isStage47Model(model = {}) {
  return hasStage47Hint([
    model.model_id,
    model.model_name,
    model.source_job_id,
    model.source_summary,
    model.resolved_pth_path,
    model.resolved_index_path,
  ].filter(Boolean).join(" "));
}

function isTrainJob(job = {}) {
  return job.job_type === "train" || /^train/i.test(String(job.job_id || ""));
}

function isCoverJob(job = {}) {
  return job.job_type === "cover" || job.job_kind === "cover" || /^cover/i.test(String(job.job_id || ""));
}

function stage47ModelIds(models = []) {
  return new Set(models.map(model => model.model_id).filter(Boolean));
}

function isStage47TrainingJob(job = {}, models = []) {
  const sourceJobIds = new Set(models.map(model => model.source_job_id).filter(Boolean));
  return isTrainJob(job) && (hasStage47Hint(job) || sourceJobIds.has(job.job_id));
}

function isStage47CoverJob(job = {}, models = []) {
  const modelIds = stage47ModelIds(models);
  return isCoverJob(job) && (
    hasStage47Hint(job) ||
    modelIds.has(job.voice_model_id) ||
    modelIds.has(job.model_id) ||
    modelIds.has(job.voice_model?.model_id)
  );
}

function sortByNewest(items = []) {
  return [...items].sort((left, right) => {
    const leftTime = parseDateValue(left.updated_at || left.created_at);
    const rightTime = parseDateValue(right.updated_at || right.created_at);
    if (rightTime !== leftTime) return rightTime - leftTime;
    return String(right.job_id || right.model_id || "").localeCompare(String(left.job_id || left.model_id || ""));
  });
}

function getStage47JobPhase(job = null) {
  if (!job) return "pending";
  if (isFailedStatus(job.status)) return "failed";
  if (isCompletedStatus(job.status)) return "success";
  if (isPendingStatus(job.status)) return "pending";
  return "running";
}

function stage47PhaseLabel(phase = "pending") {
  return {
    pending: "pending",
    running: "running",
    success: "success",
    failed: "failed",
    blocked: "blocked",
  }[phase] || phase;
}

function stage47PhaseClass(phase = "pending") {
  return {
    pending: "pending",
    running: "active",
    success: "success",
    failed: "failed",
    blocked: "blocked",
  }[phase] || "pending";
}

function renderStage47PhasePill(phase = "pending") {
  return `<span class="status-pill ${stage47PhaseClass(phase)}">${escapeHtml(stage47PhaseLabel(phase))}</span>`;
}

function pickStage47CoverArtifact(artifacts = []) {
  const unique = [];
  const seen = new Set();
  for (const artifact of artifacts || []) {
    const key = `${artifact.artifact_type}|${artifact.file_path}|${artifact.artifact_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(artifact);
  }
  return (
    unique.find(item => item.artifact_type === "cover_master" && item.is_final) ||
    unique.find(item => item.artifact_type === "cover_master") ||
    unique.find(item => item.is_final) ||
    null
  );
}

function artifactPlaybackUrl(artifact = null, coverJob = null) {
  return (
    artifact?.download_url ||
    artifact?.play_url ||
    artifact?.url ||
    coverJob?.final_artifact_download_url ||
    coverJob?.download_url ||
    ""
  );
}

function stage47StudioUrl(coverJob = null, artifact = null) {
  if (coverJob?.studio_url) return coverJob.studio_url;
  if (!coverJob?.job_id) return "";
  const params = new URLSearchParams({ job_id: coverJob.job_id });
  if (artifact?.artifact_id) params.set("artifact_id", artifact.artifact_id);
  return `/studio?${params.toString()}`;
}

async function loadStage47Acceptance(pageItems = []) {
  const next = {
    unavailable: "",
    trainingJob: null,
    model: null,
    coverJob: null,
    coverArtifact: null,
    coverArtifacts: [],
    studioReady: false,
    studioUrl: "",
  };

  try {
    const [jobsResp, modelsPayload] = await Promise.all([
      getJSON(`/api/jobs${buildQuery(withTestRecordParams({ limit: 100, offset: 0 }))}`).catch(() => ({ items: pageItems || [] })),
      getJSON("/api/models").catch(() => []),
    ]);
    const jobs = Array.isArray(jobsResp?.items) ? jobsResp.items : (pageItems || []);
    const models = normalizeModelsPayload(modelsPayload);
    const stage47Models = sortByNewest(models.filter(isStage47Model));
    next.model = stage47Models[0] || null;

    const trainingJobs = sortByNewest(jobs.filter(job => isStage47TrainingJob(job, stage47Models)));
    next.trainingJob = trainingJobs[0] || null;

    if (!next.trainingJob && next.model?.source_job_id) {
      const sourceJob = jobs.find(job => job.job_id === next.model.source_job_id)
        || await getJSON(`/api/jobs/${encodeURIComponent(next.model.source_job_id)}`).catch(() => null);
      if (sourceJob) next.trainingJob = sourceJob;
    }

    const coverJobs = sortByNewest(jobs.filter(job => isStage47CoverJob(job, stage47Models)));
    next.coverJob = coverJobs[0] || null;

    if (next.coverJob?.job_id) {
      const [coverDetail, artifactPayload] = await Promise.all([
        getJSON(`/api/jobs/${encodeURIComponent(next.coverJob.job_id)}`).catch(() => next.coverJob),
        getJSON(`/api/jobs/${encodeURIComponent(next.coverJob.job_id)}/artifacts`).catch(() => ({ artifacts: [] })),
      ]);
      next.coverJob = coverDetail || next.coverJob;
      next.coverArtifacts = artifactPayload.artifacts || [];
      next.coverArtifact = pickStage47CoverArtifact(next.coverArtifacts);
      const hasPlayback = Boolean(artifactPlaybackUrl(next.coverArtifact, next.coverJob));
      next.studioUrl = hasPlayback ? stage47StudioUrl(next.coverJob, next.coverArtifact) : "";
      next.studioReady = Boolean(hasPlayback && (next.coverJob.can_open_studio || next.coverJob.studio_url || next.coverArtifact?.artifact_id));
    }
  } catch (error) {
    next.unavailable = `Stage47 真实状态读取失败：${toErrorMessage(error)}`;
  }

  state.stage47Acceptance = next;
  renderStage47Acceptance();
}

function stage47Value(value = "") {
  return value ? escapeHtml(value) : "-";
}

function renderStage47Acceptance() {
  const panel = $("stage47E2ePanel");
  if (!panel) return;
  const data = state.stage47Acceptance;
  const training = data.trainingJob;
  const model = data.model;
  const cover = data.coverJob;
  const artifact = data.coverArtifact;
  const hasAny = Boolean(training || model || cover);
  const missingPlayback = Boolean(cover && isCompletedStatus(cover.status) && !artifactPlaybackUrl(artifact, cover));

  $("stage47TrainingJobValue").textContent = training?.job_id || "-";
  $("stage47ModelValue").textContent = model?.model_id || model?.model_name || "-";
  $("stage47CoverJobValue").textContent = cover?.job_id || "-";
  $("stage47StudioValue").textContent = data.studioReady ? "可进入录音棚" : (missingPlayback ? "后端缺少播放 URL" : "未就绪");

  if (data.unavailable) {
    $("stage47E2eSummary").textContent = data.unavailable;
  } else if (!hasAny) {
    $("stage47E2eSummary").textContent = "等待地基生成真实闭环：当前真实 API 中尚未发现 Stage47 训练任务 / 模型 / 翻唱任务。";
  } else {
    $("stage47E2eSummary").textContent = "已读取真实 Stage47 候选，只展示 API 证明过的训练、模型、翻唱与录音棚状态。";
  }

  const trainingPhase = getStage47JobPhase(training);
  const modelPhase = model ? "success" : (training && isCompletedStatus(training.status) ? "blocked" : trainingPhase === "failed" ? "blocked" : "pending");
  const coverPhase = cover ? getStage47JobPhase(cover) : (model ? "blocked" : "pending");
  const artifactPhase = artifactPlaybackUrl(artifact, cover)
    ? "success"
    : (cover && isCompletedStatus(cover.status) ? "blocked" : coverPhase === "running" ? "running" : "pending");
  const studioPhase = data.studioReady ? "success" : (artifact || missingPlayback ? "blocked" : "pending");
  const steps = [
    { label: "训练输入", phase: training ? "success" : "pending", note: training?.input_path || "等待单文件干声训练 job" },
    { label: "训练 job", phase: trainingPhase, note: training?.job_id || "未发现 Stage47 training job" },
    { label: "新模型", phase: modelPhase, note: model?.model_name || "未发现 Stage47 新模型" },
    { label: "翻唱任务", phase: coverPhase, note: cover?.job_id || "未发现 Stage47 翻唱任务" },
    { label: "最终音频", phase: artifactPhase, note: artifactPlaybackUrl(artifact, cover) || (missingPlayback ? "后端缺少播放 URL" : "等待 cover_master artifact") },
    { label: "Studio 试听", phase: studioPhase, note: data.studioReady ? "Stage47 短 smoke / 完整 cover" : "等待可播放成品" },
  ];
  $("stage47E2eSteps").innerHTML = steps.map(item => `
    <div class="stage47-step ${escapeHtml(item.phase)}">
      <div class="stage47-step-head">
        <strong>${escapeHtml(item.label)}</strong>
        ${renderStage47PhasePill(item.phase)}
      </div>
      <span title="${escapeHtml(item.note)}">${escapeHtml(item.note)}</span>
    </div>
  `).join("");

  const failedJob = [cover, training].find(job => job && isFailedStatus(job.status));
  const failure = $("stage47E2eFailure");
  if (failedJob) {
    failure.hidden = false;
    failure.innerHTML = `
      <strong>失败原因</strong>
      <span>${escapeHtml(failedJob.error_log || failedJob.error_message || "真实 API 未返回失败原因，请打开任务详情查看阶段日志。")}</span>
    `;
  } else {
    failure.hidden = true;
    failure.innerHTML = "";
  }

  const links = [];
  if (training?.job_id) {
    links.push(`<button class="ghost-btn" type="button" data-stage47-focus-job="${escapeHtml(training.job_id)}">查看训练 job</button>`);
  }
  if (model?.model_id) {
    links.push(`<a class="ghost-btn" href="/factory#factoryModelAssetsDrawer">打开工厂模型库</a>`);
  }
  if (cover?.job_id) {
    links.push(`<button class="ghost-btn" type="button" data-stage47-focus-job="${escapeHtml(cover.job_id)}">查看翻唱任务</button>`);
  }
  if (data.studioReady && data.studioUrl) {
    links.push(`<a class="primary-btn" href="${escapeHtml(data.studioUrl)}">进入录音棚试听</a>`);
  }
  $("stage47E2eLinks").innerHTML = links.join("");
}

function trainingObserverUnavailableMessage(error) {
  if (error instanceof ApiError && error.status === 404) {
    return "等待后端契约：/api/training/observer/latest 暂不可用。";
  }
  return `训练观察读取失败：${toErrorMessage(error)}`;
}

async function loadTrainingObserver() {
  try {
    const payload = await getJSON("/api/training/observer/latest");
    state.trainingObserver.observer = payload.observer || null;
    state.trainingObserver.unavailable = payload.ok === false ? (payload.message || "尚未发现可观察训练任务。") : "";
    state.trainingObserver.loaded = true;
  } catch (error) {
    state.trainingObserver.observer = null;
    state.trainingObserver.unavailable = trainingObserverUnavailableMessage(error);
    state.trainingObserver.loaded = true;
  }
  renderTrainingObserver();
}

function renderTrainingObserver() {
  const panel = $("trainingObserverPanel");
  if (!panel) return;
  const observer = state.trainingObserver.observer;
  const unavailable = state.trainingObserver.unavailable;
  const loaded = state.trainingObserver.loaded;
  const summary = $("trainingObserverSummary");
  const links = $("trainingObserverLinks");
  const observerCoverModelId = trainingObserverCoverModelId(observer);
  $("trainingObserverJobValue").textContent = observer?.job_id || "-";
  $("trainingObserverStageValue").textContent = observer?.current_stage_label || observer?.current_stage || "-";
  $("trainingObserverProgressValue").textContent = observer?.stage_progress?.label || "-";
  $("trainingObserverModelValue").textContent = observer?.model_registration_label || observerCoverModelId || "未登记";

  if (unavailable) {
    summary.textContent = unavailable;
  } else if (!observer) {
    summary.textContent = loaded ? "尚未发现可观察训练任务。" : "正在读取最新训练状态...";
  } else {
    summary.textContent = `${observer.voice_name || "训练任务"} · ${statusText(observer.status)} · ${observer.next_step || ""}`;
  }

  const lastLog = observer?.last_stage_log;
  $("trainingObserverLog").innerHTML = observer
    ? `
      <div><strong>最近日志</strong> ${escapeHtml(lastLog?.stage_name || "-")} / ${escapeHtml(lastLog?.status || "-")}</div>
      <div>${escapeHtml(lastLog?.message || "暂无阶段日志消息")}</div>
      <div>最近更新时间：${escapeHtml(formatDateTime(observer.last_stage_log_at || observer.updated_at || observer.heartbeat_at || ""))}</div>
    `
    : `<div class="detail-empty inline">${escapeHtml(unavailable || "等待训练任务产生后显示观察信息。")}</div>`;

  const actionLinks = [];
  if (observer?.job_id) {
    actionLinks.push(`<button class="ghost-btn" type="button" data-training-observer-focus-job="${escapeHtml(observer.job_id)}">查看任务详情</button>`);
  }
  if (observerCoverModelId) {
    actionLinks.push(`<button class="ghost-btn" type="button" data-open-training-observer-model="${escapeHtml(observerCoverModelId)}">查看模型</button>`);
    actionLinks.push(`<button class="primary-btn warm" type="button" data-send-model-cover="${escapeHtml(observerCoverModelId)}">用该模型翻唱</button>`);
  }
  links.innerHTML = actionLinks.join("");
}

function basename(value = "") {
  if (!value) return "";
  return String(value).split(/[\\/]/).pop() || String(value);
}

function shortToken(value = "", head = 12) {
  const text = String(value || "");
  return text.length > head ? `${text.slice(0, head)}...` : text;
}

function reviewQueueUnavailableMessage(error) {
  if (error instanceof ApiError && error.status === 404) {
    return "等待后端契约：/api/reviews/artifacts 返回 404，当前不伪造验收队列。";
  }
  return `验收队列读取失败：${toErrorMessage(error)}`;
}

function reviewSummaryFromItem(item = {}) {
  return item.review_summary
    || item.listening_review_summary
    || item.final_artifact_review_summary
    || item.summary
    || {};
}

function qualitySummaryFromItem(item = {}) {
  return item.quality_summary
    || item.final_artifact_quality_summary
    || {};
}

function normalizeReviewQueuePayload(payload = {}) {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray(payload.items)
      ? payload.items
      : Array.isArray(payload.artifacts)
        ? payload.artifacts
        : Array.isArray(payload.results)
          ? payload.results
          : [];
  const items = rawItems.map(item => {
    const reviewSummary = reviewSummaryFromItem(item);
    const qualitySummary = qualitySummaryFromItem(item);
    const verdict = item.review_verdict || item.verdict || reviewSummary.verdict || "unreviewed";
    const qualityVerdict = item.quality_verdict || qualitySummary.quality_verdict || qualitySummary.verdict || "needs_manual_quality_check";
    const qualityFlags = Array.isArray(item.quality_flags)
      ? item.quality_flags
      : Array.isArray(qualitySummary.quality_flags)
        ? qualitySummary.quality_flags
        : Array.isArray(qualitySummary.flags)
          ? qualitySummary.flags
          : [];
    const route = item.review_route || item.route || reviewSummary.route || "";
    const jobId = item.job_id || item.jobId || item.source_job_id || "";
    const artifactId = item.artifact_id || item.artifactId || item.final_artifact_id || "";
    const fileName = item.file_name || item.filename || item.name || item.display_name || basename(item.file_path || item.download_url || "");
    const studioUrl = item.studio_url || (jobId ? `/studio?${new URLSearchParams({
      job_id: jobId,
      ...(artifactId ? { artifact_id: artifactId } : {}),
    }).toString()}` : "");
    const downloadUrl = item.download_url || item.final_artifact_download_url || (
      jobId && artifactId ? `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactId)}/download` : ""
    );
    return {
      ...item,
      reviewSummary,
      qualitySummary,
      verdict,
      qualityVerdict,
      qualityFlags,
      qualityReason: item.quality_reason || qualitySummary.quality_reason || qualitySummary.reason || "",
      route,
      jobId,
      artifactId,
      fileName,
      studioUrl,
      downloadUrl,
      createdAt: item.created_at || item.updated_at || reviewSummary.reviewed_at || "",
      priority: Number(reviewSummary.priority ?? item.priority ?? 0),
      isHumanReviewed: Boolean(reviewSummary.is_human_reviewed),
    };
  });
  const summary = payload.summary || {};
  const count = key => Number(summary[key] ?? items.filter(item => item.verdict === key).length) || 0;
  const qualityCount = key => Number(
    summary[`quality_${key}`]
      ?? summary.quality?.[key]
      ?? items.filter(item => item.qualityVerdict === key).length
  ) || 0;
  return {
    items,
    summary: {
      total: Number(summary.total ?? summary.total_count ?? items.length) || 0,
      unreviewed: count("unreviewed"),
      needs_work: count("needs_work"),
      usable: count("usable"),
      release_candidate: count("release_candidate"),
      rejected: count("rejected"),
      quality_reviewable: qualityCount("reviewable"),
      quality_manual_check: Number(summary.quality_manual_check ?? summary.quality_needs_manual_quality_check ?? items.filter(item => item.qualityVerdict === "needs_manual_quality_check").length) || 0,
      quality_blocked: Number(summary.quality_blocked ?? summary.quality_blocked_auto ?? items.filter(item => item.qualityVerdict === "blocked_auto").length) || 0,
    },
  };
}

function sortReviewQueueItems(items = []) {
  return [...items].sort((left, right) => {
    const qualityRank = { reviewable: 3, needs_manual_quality_check: 2, blocked_auto: 0 };
    const quality = Number(qualityRank[right.qualityVerdict] || 1) - Number(qualityRank[left.qualityVerdict] || 1);
    if (quality) return quality;
    const priority = Number(right.priority || 0) - Number(left.priority || 0);
    if (priority) return priority;
    return parseDateValue(right.createdAt) - parseDateValue(left.createdAt);
  });
}

function reviewVerdictClass(verdict = "unreviewed") {
  return {
    unreviewed: "pending",
    needs_work: "failed",
    usable: "success",
    release_candidate: "success",
    rejected: "failed",
  }[verdict] || "pending";
}

function renderReviewVerdictBadge(verdict = "unreviewed") {
  return `<span class="artifact-chip ${reviewVerdictClass(verdict)}">${escapeHtml(REVIEW_VERDICT_LABELS[verdict] || verdict || "未验收")}</span>`;
}

function renderArtifactQualityBadge(qualityVerdict = "needs_manual_quality_check") {
  const label = ARTIFACT_QUALITY_LABELS[qualityVerdict] || qualityVerdict || "Manual QC";
  const className = ARTIFACT_QUALITY_CLASSES[qualityVerdict] || "pending";
  return `<span class="artifact-chip ${className}">${escapeHtml(label)}</span>`;
}

function renderReviewActionLink(href = "", label = "", className = "ghost-btn") {
  if (!href) {
    return `<span class="${escapeHtml(className)} is-disabled" aria-disabled="true">${escapeHtml(label)}</span>`;
  }
  return `<a class="${escapeHtml(className)}" href="${escapeHtml(href)}"${label.includes("下载") ? ' target="_blank"' : ""}>${escapeHtml(label)}</a>`;
}

function renderDashboardReviewItem(item = {}) {
  const qualityVerdict = item.qualityVerdict || "needs_manual_quality_check";
  const blockedByQuality = qualityVerdict === "blocked_auto";
  const durationText = item.qualitySummary?.duration_sec != null ? `${item.qualitySummary.duration_sec}s` : "duration ?";
  const qualityFlags = item.qualityFlags?.length ? item.qualityFlags.join(", ") : (item.qualityReason || "no quality flags");
  const title = item.fileName || item.jobId || "未命名成品";
  const jobLabel = item.jobId ? `Job · ${shortToken(item.jobId)}` : "Job · -";
  const routeLabel = REVIEW_ROUTE_LABELS[item.route] || "等待 review_route";
  const smokeOnly = item.reviewSummary?.notes_preview === SMOKE_ONLY_REVIEW_NOTE || item.reviewSummary?.notes === SMOKE_ONLY_REVIEW_NOTE;
  return `
    <article class="review-queue-item">
      <div class="review-queue-item-head">
        <div>
          <strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong>
          <span class="mono" title="${escapeHtml(item.jobId || "-")}">${escapeHtml(jobLabel)}</span>
        </div>
        <div class="review-queue-badge-row">
          ${renderArtifactQualityBadge(qualityVerdict)}
          ${renderReviewVerdictBadge(item.verdict)}
        </div>
      </div>
      <div class="review-queue-meta">
        <span title="${escapeHtml(item.artifactId || "-")}">Artifact · ${escapeHtml(shortToken(item.artifactId || "-"))}</span>
        <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
        <span title="${escapeHtml(qualityFlags)}">Quality · ${escapeHtml(durationText)}</span>
        <span>${escapeHtml(routeLabel)}</span>
        ${smokeOnly ? "<span>浏览器 smoke，不是人工验收</span>" : ""}
      </div>
      <div class="panel-actions review-queue-actions">
        ${blockedByQuality ? '<span class="ghost-btn is-disabled" aria-disabled="true">被质量门禁拦截</span>' : renderReviewActionLink(item.studioUrl, "进入录音棚 A/B", "primary-btn warm")}
        ${renderReviewActionLink(item.downloadUrl, "下载", "ghost-btn")}
      </div>
    </article>
  `;
}

function renderDashboardReviewQueue() {
  const panel = $("dashboardReviewQueuePanel");
  if (!panel) return;
  const { items, summary, unavailable, loaded } = state.reviewQueue;
  const sorted = sortReviewQueueItems(items);
  const listenable = sorted.filter(item => item.qualityVerdict !== "blocked_auto");
  const visibleSource = listenable.length ? listenable : sorted;
  const visible = visibleSource.slice(0, REVIEW_QUEUE_VISIBLE_COUNT);
  const qualityStatusText = `Quality gate: ${summary.quality_reviewable || 0} reviewable, ${summary.quality_manual_check || 0} manual QC, ${summary.quality_blocked || 0} auto blocked. Showing ${visible.length} listenable items.`;

  $("dashboardReviewUnreviewedValue").textContent = loaded && !unavailable ? String(summary.quality_reviewable || 0) : "-";
  $("dashboardReviewNeedsWorkValue").textContent = loaded && !unavailable ? String(summary.quality_manual_check || 0) : "-";
  $("dashboardReviewCandidateValue").textContent = loaded && !unavailable ? String(summary.quality_blocked || 0) : "-";
  $("dashboardReviewQueueStatus").textContent = unavailable
    ? unavailable
    : loaded
      ? (items.length ? qualityStatusText : "Real review queue is empty; no fake success list is rendered.")
      : "正在读取真实 /api/reviews/artifacts...";
  $("dashboardReviewQueueList").innerHTML = unavailable
    ? `<div class="detail-empty inline">${escapeHtml(unavailable)}</div>`
    : visible.length
      ? visible.map(renderDashboardReviewItem).join("")
      : `<div class="detail-empty inline">${loaded ? "没有待处理成品；不会伪造成功队列。" : "等待真实验收队列。"}</div>`;
}

async function loadReviewQueue() {
  try {
    const payload = await getJSON(`/api/reviews/artifacts${buildQuery(withTestRecordParams({ limit: 100 }))}`);
    const normalized = normalizeReviewQueuePayload(payload);
    state.reviewQueue.items = normalized.items;
    state.reviewQueue.summary = normalized.summary;
    state.reviewQueue.unavailable = "";
    state.reviewQueue.loaded = true;
  } catch (error) {
    state.reviewQueue.items = [];
    state.reviewQueue.summary = {};
    state.reviewQueue.unavailable = reviewQueueUnavailableMessage(error);
    state.reviewQueue.loaded = true;
  }
  renderDashboardReviewQueue();
}

function parseMemoryTags(memory = {}) {
  const raw = memory.tags_json ?? memory.tags ?? memory.tag ?? [];
  if (Array.isArray(raw)) return raw.map(item => String(item)).filter(Boolean);
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.map(item => String(item)).filter(Boolean);
    } catch {
      return raw.split(/[,\s，、]+/).map(item => item.trim()).filter(Boolean);
    }
  }
  return [];
}

function normalizeMemoryItems(payload = {}) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.memories)) return payload.memories;
  if (Array.isArray(payload.value)) return payload.value;
  return [];
}

function memoryId(memory = {}) {
  return memory.memory_id || memory.id || "";
}

function memorySearchText(memory = {}) {
  return [
    memoryId(memory),
    memory.category,
    memory.title,
    memory.summary,
    memory.source_type,
    memory.source_path,
    memory.source_stage,
    memory.importance,
    parseMemoryTags(memory).join(" "),
    stage47SearchText(memory.metadata_json || memory.metadata || ""),
  ].filter(Boolean).join(" ");
}

function isStage47Memory(memory = {}) {
  const text = memorySearchText(memory);
  return /stage[\s_-]*47/i.test(text) || MEMORY_STAGE47_NEEDLES.some(needle => text.includes(needle));
}

function memoryUpdatedTime(memory = {}) {
  return parseDateValue(memory.updated_at || memory.created_at);
}

function sortMemories(items = []) {
  return [...items].sort((left, right) => {
    const pinnedCompare = Number(Boolean(right.pinned)) - Number(Boolean(left.pinned));
    if (pinnedCompare) return pinnedCompare;
    const importanceCompare = Number(right.importance || 0) - Number(left.importance || 0);
    if (importanceCompare) return importanceCompare;
    return memoryUpdatedTime(right) - memoryUpdatedTime(left);
  });
}

function summarizeMemoryApiError(error) {
  if (error instanceof ApiError && error.status === 404) {
    return "Memory API 未开放：/api/memory* 返回 404，等待地基 Stage48A 接入。";
  }
  return `Memory API 读取失败：${toErrorMessage(error)}`;
}

function getMemorySummaryValue(summary = {}, keys = [], fallback = 0) {
  for (const key of keys) {
    if (summary?.[key] != null) return summary[key];
  }
  return fallback;
}

function collectMemoryOptions(items = [], key = "category") {
  const values = new Set();
  for (const item of items) {
    if (key === "tag") {
      parseMemoryTags(item).forEach(tag => values.add(tag));
    } else if (item[key]) {
      values.add(String(item[key]));
    }
  }
  return [...values].sort((left, right) => left.localeCompare(right));
}

function updateMemorySelectOptions(selectId, values = [], currentValue = "") {
  const select = $(selectId);
  if (!select) return;
  const nextValues = currentValue && !values.includes(currentValue) ? [currentValue, ...values] : values;
  select.innerHTML = `<option value="">全部</option>${nextValues.map(value => `
    <option value="${escapeHtml(value)}" ${value === currentValue ? "selected" : ""}>${escapeHtml(value)}</option>
  `).join("")}`;
}

function filteredMemoryItems() {
  const { q, category, tag } = state.memoryLab.filters;
  const needle = q.trim().toLowerCase();
  return sortMemories(state.memoryLab.items).filter(memory => {
    if (category && String(memory.category || "") !== category) return false;
    if (tag && !parseMemoryTags(memory).includes(tag)) return false;
    if (needle && !memorySearchText(memory).toLowerCase().includes(needle)) return false;
    return true;
  });
}

function renderMemoryPath(path = "", expanded = false) {
  if (!path) return `<div class="memory-lab-path subtle">source_path：-</div>`;
  return `
    <div class="memory-lab-path ${expanded ? "expanded" : ""}" title="${escapeHtml(path)}">
      <span>source_path：</span><span class="mono">${escapeHtml(path)}</span>
    </div>
  `;
}

function renderMemoryTags(memory = {}) {
  const tags = parseMemoryTags(memory);
  if (!tags.length) return "";
  return `<div class="memory-lab-tags">${tags.slice(0, 8).map(tag => `<span class="tag warn">${escapeHtml(tag)}</span>`).join("")}</div>`;
}

function renderMemoryCard(memory = {}, { compact = false } = {}) {
  const id = memoryId(memory);
  const selected = id && state.memoryLab.selectedMemoryId === id;
  const tags = parseMemoryTags(memory);
  const title = memory.title || id || "未命名 memory";
  const summary = memory.summary || "真实 API 未返回摘要。";
  const showDetail = selected && !compact;
  return `
    <article class="memory-lab-item ${selected ? "is-active" : ""} ${memory.pinned ? "is-pinned" : ""} ${compact ? "is-compact" : ""}" data-memory-id="${escapeHtml(id)}">
      <div class="memory-lab-item-head">
        <button class="memory-lab-open-btn" type="button" data-memory-open="${escapeHtml(id)}" title="${escapeHtml(title)}">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(memory.category || "uncategorized")} · ${escapeHtml(memory.source_stage || "stage 未标注")}${memory.importance != null ? ` · importance ${escapeHtml(memory.importance)}` : ""}</span>
        </button>
        <button class="ghost-btn drawer-toggle-btn memory-pin-btn" type="button" data-memory-pin="${escapeHtml(id)}">
          ${memory.pinned ? "Unpin" : "Pin"}
        </button>
      </div>
      <p>${escapeHtml(summary)}</p>
      ${showDetail ? `
        <div class="memory-lab-meta">
          <span class="mono">${escapeHtml(id || "-")}</span>
          <span>${escapeHtml(formatDateTime(memory.updated_at || memory.created_at || ""))}</span>
          ${memory.importance != null ? `<span>importance ${escapeHtml(memory.importance)}</span>` : ""}
          ${tags[0] ? `<span>tag ${escapeHtml(tags[0])}</span>` : ""}
        </div>
        ${renderMemoryPath(memory.source_path || "", true)}
        <div class="memory-lab-detail">
          ${renderMemoryTags(memory)}
          <pre class="mono">${escapeHtml(stage47SearchText(memory.metadata_json || memory.metadata || "").slice(0, 1200) || "metadata：-")}</pre>
        </div>
      ` : ""}
    </article>
  `;
}

function renderMemoryTimeline(items = []) {
  const timeline = $("memoryLabTimeline");
  if (!timeline) return;
  const groups = new Map();
  for (const item of items) {
    const stage = item.source_stage || "stage 未标注";
    groups.set(stage, (groups.get(stage) || 0) + 1);
  }
  const entries = [...groups.entries()].sort((left, right) => String(right[0]).localeCompare(String(left[0])));
  const visibleEntries = entries.slice(0, 8);
  $("memoryLabTimelineSummary").textContent = entries.length
    ? `${entries.length} 个阶段，显示最新 ${visibleEntries.length} 个`
    : "暂无阶段";
  timeline.innerHTML = entries.length
    ? visibleEntries.map(([stage, count]) => `
      <div class="memory-lab-timeline-item">
        <strong class="mono">${escapeHtml(stage)}</strong>
        <span>${count} 条 memory</span>
      </div>
    `).join("") + (entries.length > visibleEntries.length
      ? `<div class="memory-lab-timeline-more">还有 ${entries.length - visibleEntries.length} 个阶段，使用搜索或筛选查看。</div>`
      : "")
    : `<div class="detail-empty inline">等待真实 memory 阶段索引。</div>`;
}

function syncMemoryFullDrawer() {
  const drawer = $("memoryLabFullDrawer");
  const body = $("memoryLabFullBody");
  const button = $("memoryLabFullToggleBtn");
  if (!drawer || !body || !button) return;
  const collapsed = Boolean(state.memoryLab.fullListCollapsed);
  drawer.dataset.collapsed = String(collapsed);
  drawer.classList.toggle("is-collapsed", collapsed);
  body.hidden = collapsed;
  button.setAttribute("aria-expanded", String(!collapsed));
  button.textContent = collapsed ? "展开完整列表 ▾" : "收起完整列表 ▴";
}

function renderMemoryLab() {
  const panel = $("memoryLabPanel");
  if (!panel) return;

  const summary = state.memoryLab.summary || {};
  const items = state.memoryLab.items || [];
  const filtered = filteredMemoryItems();
  const recent = filtered.slice(0, MEMORY_RECENT_VISIBLE_COUNT);
  const pinned = filtered.filter(item => item.pinned);
  const stage47 = sortMemories(items.filter(isStage47Memory));
  const total = getMemorySummaryValue(summary, ["total_count", "memory_count", "count"], items.length);
  const pinnedCount = getMemorySummaryValue(summary, ["pinned_count", "pinned"], items.filter(item => item.pinned).length);
  const latestStage = summary.latest_stage || summary.latest_source_stage || items[0]?.source_stage || "-";
  const ready = Boolean(state.memoryLab.loaded && !state.memoryLab.unavailable);

  $("memoryLabStatus").textContent = state.memoryLab.unavailable
    ? state.memoryLab.unavailable
    : (ready ? `已读取真实 Memory API：${total} 条 memory，当前筛选 ${filtered.length} 条。` : "正在读取真实 Memory API...");
  $("memoryLabTotalValue").textContent = ready ? String(total) : "-";
  $("memoryLabPinnedValue").textContent = ready ? String(pinnedCount) : "-";
  $("memoryLabLatestStageValue").textContent = ready ? String(latestStage || "-") : "-";
  $("memoryLabStage47Value").textContent = ready ? (stage47.length ? `${stage47.length} 条` : "未发现") : "未确认";
  $("memoryLabStage47Summary").textContent = stage47.length
    ? "已从真实 memory 中发现 Stage47 关键线索。"
    : (state.memoryLab.unavailable ? "等待地基开放真实 Memory API。" : "真实 memory 中尚未发现 Stage47 关键卡。");
  $("memoryLabPinnedSummary").textContent = pinned.length ? `${pinned.length} 条 pinned` : "暂无 pinned memory";
  $("memoryLabRecentSummary").textContent = filtered.length ? `显示最近 ${recent.length} / ${filtered.length} 条` : "当前筛选为空";
  $("memoryLabListSummary").textContent = filtered.length
    ? `完整列表 ${filtered.length} / ${items.length} 条，默认收起并限制高度滚动。`
    : "当前筛选为空";

  updateMemorySelectOptions("memoryLabCategoryFilter", collectMemoryOptions(items, "category"), state.memoryLab.filters.category);
  updateMemorySelectOptions("memoryLabTagFilter", collectMemoryOptions(items, "tag"), state.memoryLab.filters.tag);

  $("memoryLabStage47List").innerHTML = stage47.length
    ? stage47.slice(0, 3).map(item => renderMemoryCard(item, { compact: true })).join("")
    : `<div class="detail-empty inline">${state.memoryLab.unavailable ? "Memory API 未开放，不能伪造 Stage47 memory。" : "未检索到 v_d4d7e1c1 / 朱朱_stage47_single_long / task_b2272d133fff / BLOCK_TRAINING=false。"}</div>`;
  $("memoryLabPinnedList").innerHTML = pinned.length
    ? pinned.slice(0, 3).map(item => renderMemoryCard(item, { compact: true })).join("")
    : `<div class="detail-empty inline">暂无 pinned memory。</div>`;
  $("memoryLabRecentList").innerHTML = recent.length
    ? recent.map(item => renderMemoryCard(item, { compact: true })).join("")
    : `<div class="detail-empty inline">${state.memoryLab.unavailable ? "等待真实 Memory API。" : "当前筛选没有匹配 memory。"}</div>`;
  $("memoryLabList").innerHTML = filtered.length
    ? filtered.slice(0, 30).map(item => renderMemoryCard(item)).join("")
    : `<div class="detail-empty inline">${state.memoryLab.unavailable ? "等待真实 Memory API。" : "当前筛选没有匹配 memory。"}</div>`;
  renderMemoryTimeline(items);
  syncMemoryFullDrawer();

  const rescanBtn = $("memoryLabRescanBtn");
  if (rescanBtn) {
    rescanBtn.disabled = state.memoryLab.rescanInFlight;
    rescanBtn.textContent = state.memoryLab.rescanInFlight ? "扫描中..." : "重新扫描";
  }
}

async function loadMemoryLab() {
  try {
    const [summary, payload] = await Promise.all([
      getJSON("/api/memory/summary"),
      getJSON("/api/memory?limit=100&offset=0"),
    ]);
    state.memoryLab.summary = summary || {};
    state.memoryLab.items = normalizeMemoryItems(payload);
    state.memoryLab.unavailable = "";
    state.memoryLab.loaded = true;
  } catch (error) {
    state.memoryLab.summary = null;
    state.memoryLab.items = [];
    state.memoryLab.unavailable = summarizeMemoryApiError(error);
    state.memoryLab.loaded = true;
  }
  renderMemoryLab();
}

async function rescanMemoryLab() {
  if (state.memoryLab.rescanInFlight) return;
  state.memoryLab.rescanInFlight = true;
  renderMemoryLab();
  try {
    await postJSON("/api/memory/rescan", {});
    showToast("记忆实验室已完成重新扫描", "success");
  } catch (error) {
    state.memoryLab.unavailable = summarizeMemoryApiError(error);
    showToast(state.memoryLab.unavailable, "info");
  } finally {
    state.memoryLab.rescanInFlight = false;
  }
  await loadMemoryLab();
}

async function toggleMemoryPin(targetMemoryId = "") {
  const memory = state.memoryLab.items.find(item => memoryId(item) === targetMemoryId);
  if (!memory) return;
  try {
    await patchJSON(`/api/memory/${encodeURIComponent(targetMemoryId)}`, { pinned: !Boolean(memory.pinned) });
    showToast(memory.pinned ? "Memory 已取消 pinned" : "Memory 已 pinned", "success");
    await loadMemoryLab();
  } catch (error) {
    showToast(`pin/unpin 失败：${toErrorMessage(error)}`, "error");
  }
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

function getJobTrainingConfigCollapsed() {
  return Boolean(loadUiState(JOB_TRAINING_CONFIG_STATE_KEY, true));
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

function uniqueJobArtifacts(items = []) {
  const seen = new Set();
  return [...(items || [])].filter(item => {
    const key = `${item.artifact_type}|${item.file_path}|${item.artifact_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function pickCoverMasterArtifact(items = []) {
  const unique = uniqueJobArtifacts(items);
  return (
    unique.find(item => item.artifact_type === "cover_master" && item.is_final) ||
    unique.find(item => item.artifact_type === "cover_master") ||
    null
  );
}

function coverMissingArtifactMessage(job = null, stageLogs = []) {
  const latest = getLatestItem(stageLogs, item => item.created_at || item.updated_at);
  const stageName = latest?.stage_name || job?.current_stage || "cover_upload";
  const stageStatus = latest?.status || job?.status || "";
  const statusPart = stageStatus ? ` / ${statusText(stageStatus)}` : "";
  return `当前还没有 cover_master 最终产物，卡在 ${stageText(stageName)}${statusPart}。`;
}

function collectJobLogText(job = {}, stageLogs = []) {
  return [
    job.error_log || "",
    ...(stageLogs || []).map(item => `${item.stage_name || ""} ${item.status || ""} ${item.message || ""} ${item.detail_json || ""}`),
  ].join("\n");
}

function extractExpNames(text = "") {
  return [...new Set((String(text).match(/feishark_v_[A-Za-z0-9_]+/g) || []))];
}

function hasCheckpointHint(text = "") {
  return /(?:G|D)_\d+\.pth|e\d+_s\d+\.pth|checkpoint/i.test(String(text));
}

function truncateText(value = "", maxLength = 160) {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function isNoisyLogMessage(value = "") {
  return /command|traceback|futurewarning|warning|torch|timed out|subprocess|python/i.test(String(value || ""));
}

function summarizeLogMessage(value = "") {
  const text = String(value || "").trim();
  if (!text) return "没有附加说明。";
  if (/timed out after\s+3600\s+seconds/i.test(text)) {
    return "核心训练超过 3600 秒保护时限，后端已停止等待。";
  }
  if (/FutureWarning/i.test(text)) {
    return "包含 FutureWarning，完整内容已收纳到原文。";
  }
  return truncateText(text, 160);
}

function formatStageLogRaw(item = {}) {
  const blocks = [];
  if (item.message) blocks.push(String(item.message));
  if (item.detail_json) {
    if (typeof item.detail_json === "string") {
      blocks.push(item.detail_json);
    } else {
      blocks.push(JSON.stringify(item.detail_json, null, 2));
    }
  }
  return blocks.join("\n\n").trim();
}

function analyzeTrainingFailure(job = {}, stageLogs = []) {
  if (job.job_type !== "train" || !isFailedStatus(job.status)) {
    return null;
  }

  const text = collectJobLogText(job, stageLogs);
  const lower = text.toLowerCase();
  const expNames = extractExpNames(text);
  const duplicateExp = expNames.length > 1;
  const timedOut = /timed out after\s+3600\s+seconds/i.test(text);
  const manualStop = /manual|manually|stopped|terminated|killed|keyboardinterrupt|人工|手动|中断/.test(lower);
  const scriptException = /traceback|exception|error|failed|train\.py/i.test(lower);
  const checkpointDetected = hasCheckpointHint(text);

  let kind = "unknown";
  let title = "未知失败";
  let summary = "训练失败原因还没有结构化字段，当前只能基于阶段日志做兼容判断。";

  if (timedOut) {
    kind = "timeout";
    title = "训练超时";
    summary = "核心训练超过后端保护时限，不是显存炸掉。当前模型尚未完成索引和登记。";
  } else if (duplicateExp) {
    kind = "duplicate_exp";
    title = "重复派发 / 多 exp_name 风险";
    summary = "检测到同一任务生成了多个 RVC 实验名，疑似重复派发/恢复冲突。修复前不要直接重试。";
  } else if (manualStop) {
    kind = "manual_stop";
    title = "人工停止 / 进程中断";
    summary = "检测到训练进程可能被人工停止或中断，当前模型尚未完成索引和登记。";
  } else if (scriptException) {
    kind = "script_exception";
    title = "RVC 脚本异常";
    summary = "RVC 训练脚本返回异常，需先查看原文确认具体原因。";
  }

  if (duplicateExp) {
    summary = `${summary} 检测到同一任务生成了多个 RVC 实验名，疑似重复派发/恢复冲突，修复前不要直接重试。`;
  }

  const highRiskRetry = timedOut || manualStop || duplicateExp || kind === "unknown";
  return { kind, title, summary, expNames, duplicateExp, timedOut, manualStop, scriptException, checkpointDetected, highRiskRetry };
}

function shouldGuardFailedTrainRetry(job = {}, stageLogs = []) {
  const analysis = analyzeTrainingFailure(job, stageLogs);
  return Boolean(analysis?.highRiskRetry);
}

function canShowTrainLifecycleToast(jobId, status) {
  const key = `${jobId}|${status}`;
  const now = Date.now();
  const lastAt = state.trainLifecycleToastAt.get(key) || 0;
  if (now - lastAt < 15000) return false;
  state.trainLifecycleToastAt.set(key, now);
  return true;
}

function announceTrainingLifecycleTransitions(items = []) {
  const next = new Map();
  for (const job of items) {
    if (job.job_type !== "train" || !job.job_id) continue;
    const previous = state.trainLifecycleByJob.get(job.job_id);
    next.set(job.job_id, { status: job.status || "", current_stage: job.current_stage || "" });

    if (!previous || !isActiveTrainingStatus(previous.status)) continue;
    if (isCompletedStatus(job.status) && canShowTrainLifecycleToast(job.job_id, "completed")) {
      showToast("训练完成，模型已登记。", "success");
    } else if (isFailedStatus(job.status) && canShowTrainLifecycleToast(job.job_id, "failed")) {
      showToast("训练失败，已停止，请查看失败诊断。", "error");
    }
  }
  state.trainLifecycleByJob = next;
}

function shouldShowTrainingRecovery(job = {}) {
  return job.job_type === "train" && isFailedStatus(job.status) && job.current_stage === "train_core";
}

function parseEpochValue(value) {
  if (value == null) return 0;
  const match = String(value).match(/\d+/);
  return match ? Number(match[0]) : 0;
}

function normalizeRecoveryCandidate(candidate = {}, fallback = {}) {
  const expName = candidate.exp_name || candidate.experiment_name || candidate.name || fallback.exp_name || "";
  const highestEpoch = parseEpochValue(
    candidate.highest_epoch ?? candidate.max_epoch ?? candidate.epoch ?? candidate.best_epoch ?? fallback.highest_epoch,
  );
  const featureCount = Number(
    candidate.feature_count ?? candidate.features_count ?? candidate.feature_rows ?? fallback.feature_count ?? 0,
  ) || 0;
  const indexFeasible = candidate.index_feasible ?? candidate.can_build_index ?? fallback.index_feasible ?? false;
  return {
    expName,
    highestEpoch,
    featureCount,
    indexFeasible: Boolean(indexFeasible),
    weightPath: candidate.weight_path || candidate.pth_path || candidate.checkpoint_path || fallback.weight_path || "",
    reason: candidate.reason || candidate.status || fallback.reason || "",
    raw: candidate,
  };
}

function normalizeTrainingRecovery(payload = {}) {
  const candidateSources = []
    .concat(payload.candidates || [])
    .concat(payload.recovery_candidates || [])
    .concat(payload.checkpoints || [])
    .concat(payload.experiments || []);

  const explicitRecommended =
    payload.recommended_candidate ||
    payload.recommended_checkpoint ||
    payload.recommended ||
    payload.checkpoint ||
    null;

  if (explicitRecommended) candidateSources.unshift(explicitRecommended);
  if (!candidateSources.length && (payload.exp_name || payload.can_recover)) {
    candidateSources.push(payload);
  }

  const seen = new Set();
  const candidates = candidateSources
    .map(item => normalizeRecoveryCandidate(item, payload))
    .filter(item => item.expName || item.highestEpoch || item.featureCount)
    .filter(item => {
      const key = `${item.expName}|${item.highestEpoch}|${item.featureCount}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((left, right) => {
      if (left.indexFeasible !== right.indexFeasible) return Number(right.indexFeasible) - Number(left.indexFeasible);
      if (left.highestEpoch !== right.highestEpoch) return right.highestEpoch - left.highestEpoch;
      return right.featureCount - left.featureCount;
    });

  const recommended = candidates[0] || null;
  return {
    canRecover: Boolean(payload.can_recover) && Boolean(recommended),
    dryRun: Boolean(payload.dry_run),
    reason: payload.reason || payload.message || payload.detail || "",
    status: payload.status || "",
    recommended,
    candidates,
    raw: payload,
  };
}

function getRecoveryModelId(result = {}) {
  return result.model_id || result.generated_model_id || result.recovered_model_id || result.model?.model_id || "";
}

function getJobCheckpointInspection(job = {}) {
  return job.checkpoint_inspection || job.error_summary?.checkpoint || null;
}

function isCheckpointRecoveredJob(job = {}) {
  return job.job_type === "train" &&
    Boolean(job.generated_model_id) &&
    (job.current_stage === "train_checkpoint_recover" ||
      /checkpoint.*恢复|恢复登记|recovered/i.test(String(job.generated_model_summary || "")));
}

function getRecoveredEpoch(job = {}) {
  const inspection = getJobCheckpointInspection(job);
  return parseEpochValue(inspection?.highest_epoch || job.recovered_epoch || "");
}

function getTrainingRecoveryState(jobId) {
  return state.trainingRecoveryByJob.get(jobId) || { status: "idle" };
}

function renderCandidateMeta(candidate = null) {
  if (!candidate) return "";
  return `
    <div class="checkpoint-recovery-grid">
      <div><span>推荐实验</span><strong class="mono">${escapeHtml(candidate.expName || "-")}</strong></div>
      <div><span>最高 epoch</span><strong>e${escapeHtml(candidate.highestEpoch || "-")}</strong></div>
      <div><span>特征数</span><strong>${escapeHtml(candidate.featureCount || "-")}</strong></div>
      <div><span>状态</span><strong>${candidate.indexFeasible ? "可构建 index / 可登记模型" : "暂不能构建 index"}</strong></div>
    </div>
  `;
}

function renderCheckpointRecoveryCard(job = {}, recoveryState = null) {
  if (isCheckpointRecoveredJob(job)) {
    const inspection = getJobCheckpointInspection(job);
    const epoch = getRecoveredEpoch(job);
    const modelId = job.generated_model_id || "";
    return `
      <div class="checkpoint-recovery-card success">
        <div class="checkpoint-recovery-head">
          <strong>已从 checkpoint 恢复</strong>
          <span>失败训练已补齐 index / model register，可用于后续试听 / 翻唱验证。</span>
        </div>
        <div class="checkpoint-recovery-grid">
          <div><span>来源实验</span><strong class="mono">${escapeHtml(inspection?.exp_name || "-")}</strong></div>
          <div><span>恢复 epoch</span><strong>${epoch ? `e${escapeHtml(epoch)}` : "-"}</strong></div>
          <div><span>模型</span><strong>${escapeHtml(job.generated_model_name || modelId || "-")}</strong></div>
          <div><span>状态</span><strong>${job.generated_model_usable ? "模型库可用" : "已登记，待校验"}</strong></div>
        </div>
        <div class="checkpoint-recovery-model mono">${escapeHtml(modelId || "-")}</div>
        ${renderRecoveredModelAcceptanceGuide()}
        <div class="panel-actions">
          ${modelId ? `<button class="ghost-btn" type="button" data-open-recovered-model="${escapeHtml(modelId)}">去模型库查看</button>` : ""}
          ${modelId ? `<button class="primary-btn warm" type="button" data-send-recovered-model-cover="${escapeHtml(modelId)}">送入 AI 翻唱</button>` : ""}
          ${modelId ? `<button class="ghost-btn" type="button" data-copy-model-id="${escapeHtml(modelId)}">复制模型 ID</button>` : ""}
        </div>
      </div>
    `;
  }

  if (!shouldShowTrainingRecovery(job)) return "";

  const current = recoveryState || getTrainingRecoveryState(job.job_id);
  if (current.status === "success") {
    const modelId = getRecoveryModelId(current.result);
    return `
      <div class="checkpoint-recovery-card success">
        <div class="checkpoint-recovery-head">
          <strong>模型已从 checkpoint 恢复登记</strong>
          <span>可用于后续试听 / 翻唱验证。</span>
        </div>
        ${modelId ? `<div class="checkpoint-recovery-model mono">${escapeHtml(modelId)}</div>` : ""}
        <div class="panel-actions">
          ${modelId ? `<button class="ghost-btn" type="button" data-open-recovered-model="${escapeHtml(modelId)}">去模型库查看</button>` : ""}
          ${modelId ? `<button class="primary-btn warm" type="button" data-send-recovered-model-cover="${escapeHtml(modelId)}">送入 AI 翻唱</button>` : ""}
        </div>
      </div>
    `;
  }

  if (current.status === "loading" || current.status === "idle") {
    return `
      <div class="checkpoint-recovery-card">
        <div class="checkpoint-recovery-head">
          <strong>checkpoint 恢复登记</strong>
          <span>正在检查可恢复 checkpoint...</span>
        </div>
      </div>
    `;
  }

  if (current.status === "unavailable") {
    return `
      <div class="checkpoint-recovery-card muted">
        <div class="checkpoint-recovery-head">
          <strong>恢复能力待后端就绪</strong>
          <span>${escapeHtml(current.message || "checkpoint recovery API 暂不可用。")}</span>
        </div>
        <button class="ghost-btn" type="button" disabled aria-disabled="true">等待后端恢复接口</button>
      </div>
    `;
  }

  const recovery = current.recovery;
  const candidate = recovery?.recommended || null;
  const canRegister = Boolean(recovery?.canRecover) && !recovery?.dryRun && candidate?.indexFeasible;
  const buttonLabel = candidate?.highestEpoch
    ? `从 e${candidate.highestEpoch} checkpoint 恢复登记模型`
    : "从 checkpoint 恢复登记模型";

  if (!canRegister) {
    return `
      <div class="checkpoint-recovery-card muted">
        <div class="checkpoint-recovery-head">
          <strong>${recovery?.dryRun ? "checkpoint 恢复预演" : "暂不可恢复 checkpoint"}</strong>
          <span>${escapeHtml(recovery?.reason || "后端返回当前任务暂不能恢复登记。")}</span>
        </div>
        ${renderCandidateMeta(candidate)}
        <button class="ghost-btn" type="button" disabled aria-disabled="true">${escapeHtml(buttonLabel)}</button>
      </div>
    `;
  }

  const otherCandidates = (recovery.candidates || []).slice(1);
  return `
    <div class="checkpoint-recovery-card ready">
      <div class="checkpoint-recovery-head">
        <strong>可恢复 checkpoint</strong>
        <span>这不会重新训练，只会使用已有 checkpoint 构建 index 并登记模型。</span>
      </div>
      ${renderCandidateMeta(candidate)}
      ${candidate.weightPath ? `<div class="checkpoint-recovery-path mono" title="${escapeHtml(candidate.weightPath)}">${escapeHtml(candidate.weightPath)}</div>` : ""}
      ${otherCandidates.length ? `
        <details class="checkpoint-candidate-drawer">
          <summary>查看其它候选 (${otherCandidates.length})</summary>
          <div class="checkpoint-candidate-list">
            ${otherCandidates.map(item => `
              <div class="checkpoint-candidate-item">
                <strong class="mono">${escapeHtml(item.expName || "-")}</strong>
                <span>e${escapeHtml(item.highestEpoch || "-")} · 特征 ${escapeHtml(item.featureCount || "-")} · ${item.indexFeasible ? "可构建 index" : "不可构建 index"}</span>
              </div>
            `).join("")}
          </div>
        </details>
      ` : ""}
      <div class="panel-actions">
        <button class="primary-btn warm" type="button" data-action="checkpoint-register" data-job-id="${escapeHtml(job.job_id)}">
          ${escapeHtml(buttonLabel)}
        </button>
      </div>
    </div>
  `;
}

function updateTrainingRecoveryCard(job = {}) {
  const slot = $("trainingRecoveryCardSlot");
  if (!slot || (!shouldShowTrainingRecovery(job) && !isCheckpointRecoveredJob(job))) return;
  slot.innerHTML = renderCheckpointRecoveryCard(job);
}

function renderRecoveredModelAcceptanceGuide() {
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

function setJobTrainingConfigCollapsed(collapsed, { immediate = false } = {}) {
  return setDrawerState({
    drawerId: "jobTrainingConfigDrawer",
    bodyId: "jobTrainingConfigBody",
    buttonId: "jobTrainingConfigToggleBtn",
    storageKey: JOB_TRAINING_CONFIG_STATE_KEY,
    collapsed,
    expandedLabel: "收起训练配置 ▴",
    collapsedLabel: "展开训练配置 ▾",
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

  if (isCheckpointRecoveredJob(job)) {
    return `这次训练曾在核心训练阶段失败，但已经从 checkpoint 恢复登记为模型 ${job.generated_model_name || job.generated_model_id}，可用于后续试听 / 翻唱验证。`;
  }

  if (isCompletedStatus(job.status)) {
    if (job.job_type === "cover") return "这是一个已完成的翻唱任务，可下载成品或进入录音棚继续处理。";
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
  if (isCheckpointRecoveredJob(job)) {
    return "下一步：去模型库查看恢复模型，或一键送入 AI 翻唱入口；不会自动提交翻唱任务。";
  }

  if (isCompletedStatus(job.status)) {
    if (job.job_type === "cover") return "下一步：进入录音棚 或下载 final_master.wav。";
    if (job.job_type === "train") return "下一步：去模型库查看生成模型，或直接送入 AI 翻唱。";
    if (job.generated_model_id) return "下一步：在模型库打开生成模型，或下载 .pth / .index。";
    return "下一步：下载 .pth / .index。";
  }

  if (isFailedStatus(job.status)) {
    if (job.job_type === "train") return "下一步：查看技术详情错误原文，确认 RVC 训练窗口是否报错，再决定重试。";
    return "下一步：优先重试，必要时查看技术详情中的错误原文。";
  }

  if (isPendingStatus(job.status)) {
    return "下一步：等待算力释放，必要时可取消。";
  }

  if (job.job_type === "train") {
    const stageNextSteps = {
      train_upload: "下一步：训练素材接收后会进入训练预检。",
      train_preflight: "下一步：训练预检通过后会准备训练数据集。",
      train_dataset_prepare: "下一步：数据集准备完成后会进入预处理或直通整理。",
      train_preprocess: "下一步：切片/重采样完成后进入 Pitch 提取。",
      train_direct_prepare: "下一步：多文件整理完成后进入 Pitch 提取。",
      train_pitch_extract: "下一步：Pitch 提取完成后进入特征提取。",
      train_feature_extract: "下一步：特征提取完成后进入核心训练。",
      train_core: "下一步：核心训练完成后会自动进入索引训练，请不要关闭训练进程。",
      train_index: "下一步：索引训练完成后会登记模型到模型库。",
      train_register_model: "下一步：模型登记完成后，可在模型库查看并送入翻唱。",
    };
    return stageNextSteps[job.current_stage] || "下一步：等待当前训练阶段完成，详情可看训练路线图。";
  }

  return "下一步：等待当前阶段完成。";
}

function resolveTrainRouteKey(job = {}, stageLogs = []) {
  if (job.strategy_key === "multi_clean_direct") return "multi_clean_direct";
  if (job.strategy_key === "single_long_preprocess") return "single_long_preprocess";
  const stageNames = new Set((stageLogs || []).map(item => item.stage_name));
  if (stageNames.has("train_direct_prepare")) return "multi_clean_direct";
  return "single_long_preprocess";
}

function getTrainRoadmapStatus(stageName, index, stages, job, stageLogs = []) {
  const logsForStage = stageLogs.filter(item => item.stage_name === stageName);
  const hasFailedLog = logsForStage.some(item => isFailedStatus(item.status));
  if (hasFailedLog) return "failed";

  const currentStage = job.current_stage || "";
  const currentIndex = stages.indexOf(currentStage);
  const hasCompletedLog = logsForStage.some(item => isCompletedStatus(item.status));
  if (hasCompletedLog || (isCompletedStatus(job.status) && index <= currentIndex)) return "done";

  if (currentStage === stageName) {
    return isFailedStatus(job.status) ? "failed" : "current";
  }

  if (isPendingStatus(job.status) && index === 0) return "current";
  if (currentIndex > index) return "done";
  return "todo";
}

function getTrainStageProgress(stages, job, stageLogs = []) {
  const statuses = stages.map((stageName, index) => getTrainRoadmapStatus(stageName, index, stages, job, stageLogs));
  const currentIndex = statuses.findIndex(status => status === "current" || status === "failed");
  const doneCount = statuses.filter(status => status === "done").length;
  const reachedCount = isCompletedStatus(job.status)
    ? stages.length
    : currentIndex >= 0
      ? Math.max(doneCount, currentIndex + 1)
      : doneCount;
  return `${Math.max(0, reachedCount)} / ${stages.length}`;
}

function renderCoreTrainingGuard(job) {
  if (job.job_type !== "train" || job.current_stage !== "train_core" || !isActiveTrainingStatus(job.status)) {
    return "";
  }

  return `
    <div class="train-core-guard">
      <strong>核心训练是最长阶段，可能长时间停在这里。</strong>
      <p>只要 RVC 训练窗口、CPU/GPU 或 RVC logs 仍在更新，就不是卡死。不要关闭训练进程。</p>
      <ol>
        <li>短时间不跳阶段是正常的。</li>
        <li>如果 20-30 分钟没有任何 RVC 日志更新、CPU/GPU 也几乎不动，再怀疑卡住。</li>
        <li>如果失败，任务会进入失败态并显示错误摘要。</li>
      </ol>
    </div>
  `;
}

function renderRecentStageLogDigest(stageLogs = []) {
  const recent = [...(stageLogs || [])].slice(-5);
  if (!recent.length) return "";

  return `
    <div class="train-stage-log-digest">
      <strong>最近阶段日志</strong>
      <div class="train-stage-log-digest-list">
        ${recent.map(item => `
          <div class="train-stage-log-digest-item">
            <span>${escapeHtml(formatDateTime(item.created_at))}</span>
            <span>${escapeHtml(stageText(item.stage_name))}</span>
            <span>
              ${escapeHtml(summarizeLogMessage(item.message || statusText(item.status)))}
              ${isNoisyLogMessage(item.message) ? '<em>查看完整日志</em>' : ""}
            </span>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderTrainingFailureDiagnosis(job, stageLogs = []) {
  const analysis = analyzeTrainingFailure(job, stageLogs);
  if (!analysis) return "";

  const expNameLine = analysis.expNames.length
    ? `<div class="training-failure-exp">实验名：${analysis.expNames.map(escapeHtml).join("、")}</div>`
    : "";
  const checkpointLine = analysis.checkpointDetected
    ? '<div class="training-failure-hint">检测到 checkpoint / 权重线索；若地基支持 checkpoint 恢复，可从已有权重继续索引 / 登记。</div>'
    : "";
  const duplicateLine = analysis.duplicateExp
    ? '<div class="training-failure-risk">检测到同一任务生成多个 RVC 实验名，疑似重复派发 / 恢复冲突。修复前不要直接重试。</div>'
    : "";

  return `
    <div class="training-failure-card ${escapeHtml(analysis.kind)}">
      <div class="training-failure-head">
        <strong>${escapeHtml(analysis.title)}</strong>
        <span>${analysis.highRiskRetry ? "高风险，先修复再重试" : "可查看原文后判断重试"}</span>
      </div>
      <p>${escapeHtml(analysis.summary)}</p>
      ${expNameLine}
      ${checkpointLine}
      ${duplicateLine}
    </div>
  `;
}

function renderTrainFailureRecoveryAdvice(job, stageLogs = []) {
  if (job.job_type !== "train" || !isFailedStatus(job.status) || job.current_stage !== "train_core") {
    return "";
  }
  const analysis = analyzeTrainingFailure(job, stageLogs);
  const expText = analysis?.expNames?.length
    ? `检测到实验名：${analysis.expNames.join("、")}。`
    : "";
  return `
    <div class="train-recovery-advice">
      <strong>核心训练失败后不会自动生成可用模型。</strong>
      <span>必须完成 index 和 model register 后，模型才会进入模型库。${escapeHtml(expText)}若地基支持 checkpoint 恢复，可以从已有权重继续索引 / 登记。</span>
    </div>
  `;
}

function renderTrainStageRoadmap(job, stageLogs = []) {
  if (job.job_type !== "train") return "";

  const routeKey = resolveTrainRouteKey(job, stageLogs);
  const stages = TRAIN_STAGE_FLOW[routeKey] || TRAIN_STAGE_FLOW.single_long_preprocess;
  const currentStage = stageText(job.current_stage || "pending");
  const routeLabel = routeKey === "multi_clean_direct" ? "多文件直通训练路线" : "单长素材预处理训练路线";
  const progressText = getTrainStageProgress(stages, job, stageLogs);

  return `
    <div class="train-stage-roadmap" data-route="${escapeHtml(routeKey)}">
      <div class="train-stage-roadmap-head">
        <strong>训练阶段路线图</strong>
        <span>${escapeHtml(routeLabel)} · 当前：${escapeHtml(currentStage)} · 阶段进度 ${escapeHtml(progressText)}</span>
      </div>
      <div class="train-stage-roadmap-note">阶段进度不等于训练 epoch 百分比。</div>
      <div class="train-stage-roadmap-list">
        ${stages.map((stageName, index) => {
          const status = getTrainRoadmapStatus(stageName, index, stages, job, stageLogs);
          return `
            <div class="train-stage-step ${status}" data-train-stage="${escapeHtml(stageName)}">
              <span class="train-stage-step-index">${index + 1}</span>
              <div>
                <strong>${escapeHtml(stageText(stageName))}</strong>
                <span>${escapeHtml(TRAIN_STAGE_NOTES[stageName] || stageName)}</span>
              </div>
            </div>
          `;
        }).join("")}
      </div>
      ${renderCoreTrainingGuard(job)}
      ${renderTrainFailureRecoveryAdvice(job, stageLogs)}
      ${renderRecentStageLogDigest(stageLogs)}
    </div>
  `;
}

function renderJobSummary(job, failedLog = null, stageLogs = []) {
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
    ${renderTrainingFailureDiagnosis(job, stageLogs)}
    <div id="trainingRecoveryCardSlot">${renderCheckpointRecoveryCard(job)}</div>
    ${renderTrainStageRoadmap(job, stageLogs)}
  `;
}

async function loadTrainingRecovery(job = {}) {
  if (!shouldShowTrainingRecovery(job)) return;
  if (getTrainingRecoveryState(job.job_id).status === "success") {
    updateTrainingRecoveryCard(job);
    return;
  }

  state.trainingRecoveryByJob.set(job.job_id, { status: "loading" });
  updateTrainingRecoveryCard(job);

  try {
    const payload = await getJSON(`/api/jobs/${encodeURIComponent(job.job_id)}/training-recovery`);
    state.trainingRecoveryByJob.set(job.job_id, {
      status: "ready",
      recovery: normalizeTrainingRecovery(payload),
    });
  } catch (error) {
    state.trainingRecoveryByJob.set(job.job_id, {
      status: "unavailable",
      message: "恢复能力待后端就绪，当前不会触发登记动作。",
      error,
    });
  }

  updateTrainingRecoveryCard(job);
}

async function registerTrainingRecovery(jobId) {
  if (!jobId) return;
  const ok = window.confirm("这不会重新训练，只会用已有 checkpoint 构建 index 并登记模型。确认继续？");
  if (!ok) return;

  try {
    const result = await postJSON(`/api/jobs/${encodeURIComponent(jobId)}/training-recovery/register`, {});
    state.trainingRecoveryByJob.set(jobId, { status: "success", result });
    showToast("模型已从 checkpoint 恢复登记", "success");
    document.dispatchEvent(new CustomEvent("feishark:models-changed"));
    await loadJobDetail(jobId, { preserveScroll: true });
  } catch (error) {
    showToast(`checkpoint 恢复登记失败：${toErrorMessage(error)}`, "error");
    const job = { job_id: jobId, job_type: "train", status: "failed", current_stage: "train_core" };
    state.trainingRecoveryByJob.set(jobId, {
      status: "unavailable",
      message: `恢复登记暂不可用：${toErrorMessage(error)}`,
      error,
    });
    updateTrainingRecoveryCard(job);
  }
}

function ensureCoverModelOption(select, modelId) {
  if (!select || !modelId) return false;
  const hasOption = Array.from(select.options || []).some(option => option.value === modelId);
  if (!hasOption) {
    const option = document.createElement("option");
    option.value = modelId;
    option.textContent = `${modelId} - training observer pending registry`;
    option.dataset.stage56Injected = "true";
    option.dataset.stage57ObserverInjected = "true";
    option.dataset.pendingRegistry = "true";
    select.appendChild(option);
  }
  select.value = modelId;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  return select.value === modelId;
}

function sendModelToCover(modelId) {
  if (!modelId) return;
  const select = $("coverModelSelect");
  const selected = ensureCoverModelOption(select, modelId);
  document.querySelector('[data-mobile-tab-target="dashboard"]')?.click();
  document.getElementById("entryCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
  select?.focus?.({ preventScroll: true });
  showToast(
    selected
      ? `已将模型 ${modelId} 填入 AI 翻唱入口，可上传歌曲进行翻唱验证`
      : `请手动确认模型 ${modelId} 是否已进入 AI 翻唱入口`,
    selected ? "success" : "info",
  );
}

async function copyModelId(modelId) {
  if (!modelId) return;
  try {
    await navigator.clipboard.writeText(modelId);
    showToast("模型 ID 已复制", "success");
  } catch {
    showToast(`模型 ID：${modelId}`, "info");
  }
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
    const inspection = getJobCheckpointInspection(job);
    cards.splice(3, 0, renderDetailCard("生成模型", [
      renderDetailRow("模型 ID", `<div class="mono" title="${escapeHtml(job.generated_model_id)}">${escapeHtml(job.generated_model_id)}</div>`),
      renderDetailRow("模型名称", escapeHtml(job.generated_model_name || "-")),
      renderDetailRow("当前状态", escapeHtml(job.generated_model_usable ? "已入库，可用于翻唱" : "已入库，待检查文件状态")),
      isCheckpointRecoveredJob(job) ? renderDetailRow("恢复来源", "checkpoint 恢复") : "",
      inspection?.exp_name ? renderDetailRow("来源实验", `<div class="mono" title="${escapeHtml(inspection.exp_name)}">${escapeHtml(inspection.exp_name)}</div>`) : "",
      isCheckpointRecoveredJob(job) ? renderDetailRow("恢复 epoch", escapeHtml(getRecoveredEpoch(job) ? `e${getRecoveredEpoch(job)}` : "-")) : "",
    ]));
  }

  $("jobMetaGrid").innerHTML = cards.join("");
}

function parseJobMetadata(job = {}) {
  if (job.metadata && typeof job.metadata === "object") return job.metadata;
  const raw = job.metadata_json || job.metadata || "";
  if (!raw || typeof raw !== "string") return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function getJobTrainingConfig(job = {}) {
  const metadata = parseJobMetadata(job);
  return job.training_config
    || metadata.training_config
    || metadata.training_config_json
    || metadata.runtime_training_config
    || {};
}

function renderJobTrainingConfig(job = {}) {
  const drawer = $("jobTrainingConfigDrawer");
  const summary = $("jobTrainingConfigSummary");
  const list = $("jobTrainingConfigList");
  if (!drawer || !summary || !list) return;

  if (job.job_type !== "train") {
    drawer.hidden = true;
    return;
  }
  drawer.hidden = false;

  const config = getJobTrainingConfig(job);
  const hasConfig = Boolean(config && Object.keys(config).length);
  const presetKey = config.preset_key || "旧任务 / 默认配置";
  summary.textContent = hasConfig
    ? `${presetKey} · ${config.epochs ?? "-"} epochs · batch ${config.batch_size ?? "-"} · ${config.sample_rate ?? "-"}`
    : "旧任务 / 默认配置。";

  list.innerHTML = `
    ${renderDetailRow("训练预设", escapeHtml(presetKey))}
    ${renderDetailRow("epochs", escapeHtml(config.epochs ?? "-"))}
    ${renderDetailRow("batch_size", escapeHtml(config.batch_size ?? "-"))}
    ${renderDetailRow("sample_rate", escapeHtml(config.sample_rate ?? "-"))}
    ${renderDetailRow("f0_enabled", escapeHtml(config.f0_enabled == null ? "-" : (config.f0_enabled ? "true" : "false")))}
    ${renderDetailRow("index_enabled", escapeHtml(config.index_enabled == null ? "-" : (config.index_enabled ? "true" : "false")))}
  `;
  setJobTrainingConfigCollapsed(true, { immediate: true }).catch(() => {});
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
        <span>${escapeHtml(item.stage_name || "-")}</span>
        <span>${escapeHtml(statusText(item.status))}</span>
        <span>${escapeHtml(formatDateTime(item.created_at))}</span>
      </div>
      <p class="stage-log-summary">${escapeHtml(summarizeLogMessage(item.message || statusText(item.status)))}</p>
      ${formatStageLogRaw(item) ? `
        <details class="stage-log-raw-drawer">
          <summary>查看原文</summary>
          <pre class="stage-log-raw mono">${escapeHtml(formatStageLogRaw(item))}</pre>
        </details>
      ` : ""}
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

function renderArtifacts(items, job = null, stageLogs = []) {
  const container = $("jobArtifactsList");
  if (!items.length) {
    const emptyMessage = job?.job_type === "cover"
      ? coverMissingArtifactMessage(job, stageLogs)
      : "当前还没有登记产物。";
    container.innerHTML = `<div class="detail-empty inline">${escapeHtml(emptyMessage)}</div>`;
    $("jobArtifactsSummary").textContent = emptyMessage;
    setJobArtifactsCollapsed(true, { immediate: true }).catch(() => {});
    return;
  }

  const orderedItems = uniqueJobArtifacts(items)
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

function renderActionBar(job, stageLogs = []) {
  const uniqueArtifacts = uniqueJobArtifacts(state.lastArtifacts || []);
  const finalArtifacts = uniqueArtifacts
    .filter(item => item.is_final)
    .filter((item, index, array) => array.findIndex(other => other.artifact_type === item.artifact_type && other.file_path === item.file_path) === index);

  const studioArtifact = pickCoverMasterArtifact(uniqueArtifacts);
  const trainPthArtifact = finalArtifacts.find(item => item.artifact_type === "train_model_pth") || null;
  const trainIndexArtifact = finalArtifacts.find(item => item.artifact_type === "train_model_index") || null;
  const actions = [];

  if (job.job_type === "cover" && !isCompletedStatus(job.status) && !studioArtifact) {
    actions.push(`<div class="detail-action-hint">${escapeHtml(coverMissingArtifactMessage(job, stageLogs))}</div>`);
  }

  if (isCompletedStatus(job.status) && job.job_type === "cover") {
    const canOpenStudio = Boolean(job.can_open_studio || job.studio_url || studioArtifact);
    const studioUrl = job.studio_url || "";
    const finalDownloadUrl = job.final_artifact_download_url || studioArtifact?.download_url || "";
    if (canOpenStudio) {
      actions.push(`
        <button
          class="primary-btn warm"
          type="button"
          data-open-studio="true"
          data-job-id="${escapeHtml(job.job_id)}"
          data-studio-url="${escapeHtml(studioUrl)}"
          data-artifact-id="${escapeHtml(studioArtifact?.artifact_id || "")}"
        >进入录音棚</button>
      `);
    } else {
      actions.push(`<div class="detail-action-hint">${escapeHtml(coverMissingArtifactMessage(job, stageLogs))}</div>`);
    }
    if (finalDownloadUrl && !studioArtifact) {
      actions.push(`<button class="ghost-btn" type="button" data-artifact-download="true" data-artifact-url="${escapeHtml(finalDownloadUrl)}">下载最终成品</button>`);
    }
    if (studioArtifact) {
      const downloadableStudioArtifact = {
        ...studioArtifact,
        download_url: studioArtifact.download_url || (studioArtifact.artifact_id ? "" : `/api/download/${job.job_id}`),
      };
      actions.push(renderArtifactButton(downloadableStudioArtifact, { label: "下载成品" }));
    }
    if (canOpenStudio && !studioArtifact && !finalDownloadUrl) {
      actions.push(`<div class="detail-action-hint">${escapeHtml(coverMissingArtifactMessage(job, stageLogs))}</div>`);
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
      actions.push(`
        <button
          class="ghost-btn"
          type="button"
          data-send-model-cover="${escapeHtml(job.generated_model_id)}"
        >送入 AI 翻唱</button>
      `);
      actions.push(`
        <button
          class="ghost-btn"
          type="button"
          data-copy-model-id="${escapeHtml(job.generated_model_id)}"
        >复制模型 ID</button>
      `);
    }
  } else if (isFailedStatus(job.status)) {
    if (shouldGuardFailedTrainRetry(job, stageLogs)) {
      actions.push(`
        <button
          class="ghost-btn danger"
          type="button"
          disabled
          aria-disabled="true"
          title="先修地基，不要再次启动同一训练，避免重复派发。"
        >修复后重试</button>
        <div class="detail-action-hint danger">先修地基，不要再次启动同一训练，避免重复派发。</div>
      `);
    } else {
      actions.push(`<button class="primary-btn warm" type="button" data-action="retry">重试</button>`);
    }
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
  $("jobTrainingConfigDrawer").hidden = true;
  $("jobTrainingConfigSummary").textContent = "旧任务 / 默认配置。";
  $("jobTrainingConfigList").innerHTML = `<div class="detail-empty inline">当前任务没有训练配置。</div>`;
  $("jobStageLogsSummary").textContent = "默认收起完整时间线，只保留最近阶段摘要。";
  $("jobStageLogsList").innerHTML = `<div class="detail-empty inline">当前还没有阶段日志。</div>`;
  $("jobTechnicalBody").hidden = true;
  $("jobTechnicalDrawer").dataset.collapsed = "true";
  $("jobTechnicalToggleBtn").setAttribute("aria-expanded", "false");
  $("jobTechnicalToggleBtn").textContent = "展开技术详情 ▾";
  $("jobTrainingConfigBody").hidden = true;
  $("jobTrainingConfigDrawer").dataset.collapsed = "true";
  $("jobTrainingConfigToggleBtn").setAttribute("aria-expanded", "false");
  $("jobTrainingConfigToggleBtn").textContent = "展开训练配置 ▾";
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

    renderJobSummary(job, failedLog, stageLogs);
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

    renderActionBar(job, stageLogs);
    renderArtifacts(state.lastArtifacts, job, stageLogs);
    renderJobStageLogs(stageLogs, job);
    renderDatasetList(datasets.items || []);
    renderJobCoreInfo(job);
    renderJobTrainingConfig(job);
    renderJobTechnical(job, failedLog);
    await loadTrainingRecovery(job);

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
  const query = buildQuery(withTestRecordParams({ ...state.filters, limit: state.limit, offset: state.offset }));
  const [jobsResp, summary] = await Promise.all([
    getJSON(`/api/jobs${query}`),
    getJSON(`/api/jobs/summary${buildQuery(withTestRecordParams({}))}`),
  ]);

  const rawItems = jobsResp.items || [];
  const items = filterTestRecords(rawItems);
  const responseHiddenCount = Number(jobsResp.hidden_test_count ?? summary?.hidden_test_count);
  const hiddenCount = Number.isFinite(responseHiddenCount)
    ? responseHiddenCount
    : Math.max(0, rawItems.length - items.length);
  renderTestRecordsToggle(hiddenCount);
  syncTestPanelsVisibility();
  renderSummary(getShowTestRecords() ? summary : summarizeVisibleJobs(items));

  announceTrainingLifecycleTransitions(items);
  await loadStage47Acceptance(items);
  await loadTrainingObserver();
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
  renderTestRecordsToggle();
  syncTestPanelsVisibility();
  setJobArtifactsCollapsed(true, { immediate: true }).catch(() => {});
  setJobTechnicalCollapsed(getJobTechnicalCollapsed(), { immediate: true }).catch(() => {});
  setJobLogsCollapsed(getJobLogsCollapsed(), { immediate: true }).catch(() => {});
  renderStage47Acceptance();
  renderTrainingObserver();
  renderDashboardReviewQueue();
  loadReviewQueue().catch(error => {
    state.reviewQueue.unavailable = reviewQueueUnavailableMessage(error);
    state.reviewQueue.loaded = true;
    renderDashboardReviewQueue();
  });
  loadStage47Acceptance([]).catch(error => {
    state.stage47Acceptance.unavailable = `Stage47 真实状态读取失败：${toErrorMessage(error)}`;
    renderStage47Acceptance();
  });
  loadTrainingObserver().catch(error => {
    state.trainingObserver.unavailable = trainingObserverUnavailableMessage(error);
    state.trainingObserver.loaded = true;
    renderTrainingObserver();
  });
  renderMemoryLab();
  loadMemoryLab().catch(error => {
    state.memoryLab.unavailable = summarizeMemoryApiError(error);
    renderMemoryLab();
  });

  $("stage47RefreshBtn")?.addEventListener("click", () => {
    refreshJobs({ forceDetail: true }).catch(error => {
      showToast(`Stage47 闭环刷新失败：${toErrorMessage(error)}`, "error");
    });
  });

  $("trainingObserverRefreshBtn")?.addEventListener("click", () => {
    loadTrainingObserver().catch(error => {
      state.trainingObserver.unavailable = trainingObserverUnavailableMessage(error);
      state.trainingObserver.loaded = true;
      renderTrainingObserver();
    });
  });

  $("dashboardReviewQueueRefreshBtn")?.addEventListener("click", () => {
    loadReviewQueue().catch(error => {
      state.reviewQueue.unavailable = reviewQueueUnavailableMessage(error);
      state.reviewQueue.loaded = true;
      renderDashboardReviewQueue();
    });
  });

  $("stage47E2eLinks")?.addEventListener("click", async event => {
    const button = event.target.closest("button[data-stage47-focus-job]");
    if (!button) return;
    const jobId = button.dataset.stage47FocusJob || "";
    if (!jobId) return;
    state.offset = 0;
    state.selectedJobId = jobId;
    document.getElementById("taskCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
    await refreshJobs({ focusJobId: jobId, forceDetail: true });
  });

  $("trainingObserverLinks")?.addEventListener("click", async event => {
    const focusButton = event.target.closest("button[data-training-observer-focus-job]");
    if (focusButton) {
      const jobId = focusButton.dataset.trainingObserverFocusJob || "";
      if (!jobId) return;
      state.offset = 0;
      state.selectedJobId = jobId;
      document.getElementById("taskCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
      await refreshJobs({ focusJobId: jobId, forceDetail: true });
      return;
    }

    const modelButton = event.target.closest("button[data-open-training-observer-model]");
    if (modelButton) {
      const modelId = modelButton.dataset.openTrainingObserverModel || "";
      if (!modelId) return;
      document.querySelector('[data-mobile-tab-target="models"]')?.click();
      document.getElementById("modelPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.dispatchEvent(new CustomEvent("feishark:focus-model", { detail: { modelId } }));
      return;
    }

    const sendModelButton = event.target.closest("button[data-send-model-cover]");
    if (sendModelButton) {
      sendModelToCover(sendModelButton.dataset.sendModelCover || "");
    }
  });

  $("memoryLabRefreshBtn")?.addEventListener("click", () => loadMemoryLab().catch(() => {}));
  $("memoryLabRescanBtn")?.addEventListener("click", () => rescanMemoryLab().catch(() => {}));
  $("memoryLabFilterForm")?.addEventListener("submit", event => {
    event.preventDefault();
    renderMemoryLab();
  });
  $("memoryLabSearchInput")?.addEventListener("input", event => {
    state.memoryLab.filters.q = event.target.value || "";
    renderMemoryLab();
  });
  $("memoryLabCategoryFilter")?.addEventListener("change", event => {
    state.memoryLab.filters.category = event.target.value || "";
    renderMemoryLab();
  });
  $("memoryLabTagFilter")?.addEventListener("change", event => {
    state.memoryLab.filters.tag = event.target.value || "";
    renderMemoryLab();
  });
  $("memoryLabResetBtn")?.addEventListener("click", () => {
    state.memoryLab.filters = { q: "", category: "", tag: "" };
    $("memoryLabSearchInput").value = "";
    renderMemoryLab();
  });
  $("memoryLabPanel")?.addEventListener("click", event => {
    const openButton = event.target.closest("[data-memory-open]");
    if (openButton) {
      const id = openButton.dataset.memoryOpen || "";
      state.memoryLab.selectedMemoryId = state.memoryLab.selectedMemoryId === id ? "" : id;
      renderMemoryLab();
      return;
    }

    const pinButton = event.target.closest("[data-memory-pin]");
    if (pinButton) {
      toggleMemoryPin(pinButton.dataset.memoryPin || "").catch(() => {});
    }
  });

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

  window.addEventListener("storage", event => {
    if (event.key === TEST_RECORDS_VISIBLE_KEY) {
      renderTestRecordsToggle();
      syncTestPanelsVisibility();
      refreshJobs({ forceDetail: true }).catch(() => {});
    }
  });

  document.addEventListener(TEST_RECORDS_EVENT, () => {
    renderTestRecordsToggle();
    syncTestPanelsVisibility();
  });

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

    if (event.target.closest("#jobTrainingConfigToggleBtn")) {
      setJobTrainingConfigCollapsed(!getJobTrainingConfigCollapsed()).catch(() => {});
      return;
    }

    if (event.target.closest("#jobStageLogsToggleBtn")) {
      setJobLogsCollapsed(!getJobLogsCollapsed()).catch(() => {});
      return;
    }

    const recoveryButton = event.target.closest('button[data-action="checkpoint-register"]');
    if (recoveryButton) {
      registerTrainingRecovery(recoveryButton.dataset.jobId || state.selectedJobId).catch(() => {});
      return;
    }

    const openRecoveredModelButton = event.target.closest("button[data-open-recovered-model]");
    if (openRecoveredModelButton) {
      const modelId = openRecoveredModelButton.dataset.openRecoveredModel || "";
      if (!modelId) return;
      document.querySelector('[data-mobile-tab-target="models"]')?.click();
      document.getElementById("modelPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.dispatchEvent(new CustomEvent("feishark:focus-model", { detail: { modelId } }));
      return;
    }

    const sendRecoveredModelButton = event.target.closest("button[data-send-recovered-model-cover]");
    if (sendRecoveredModelButton) {
      sendModelToCover(sendRecoveredModelButton.dataset.sendRecoveredModelCover || "");
      return;
    }

    const copyModelButton = event.target.closest("button[data-copy-model-id]");
    if (copyModelButton) {
      copyModelId(copyModelButton.dataset.copyModelId || "").catch(() => {});
      return;
    }
  });

  $("jobActionBar").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]");
    const artifactButton = event.target.closest("button[data-artifact-download]");
    const studioButton = event.target.closest("button[data-open-studio]");
    const modelButton = event.target.closest("button[data-open-model]");
    const sendModelButton = event.target.closest("button[data-send-model-cover]");
    const copyModelButton = event.target.closest("button[data-copy-model-id]");

    if (studioButton) {
      if (studioButton.dataset.studioUrl) {
        window.location.href = studioButton.dataset.studioUrl;
        return;
      }
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

    if (sendModelButton) {
      sendModelToCover(sendModelButton.dataset.sendModelCover || "");
      return;
    }

    if (copyModelButton) {
      await copyModelId(copyModelButton.dataset.copyModelId || "");
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
