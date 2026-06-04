import { getJSON, patchJSON, postJSON, toErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  formatDateTime,
  loadUiState,
  modelOriginLabel,
  renderPathLine,
  renderModelOriginPill,
  renderStagePill,
  renderStatusPill,
  saveUiState,
  stageText,
  showToast,
  slideToggle,
} from "./ui.js";

const STUDIO_LIBRARY_STATE_KEY = "feishark_ui_studio_library_collapsed";
const STUDIO_TRACK_HISTORY_STATE_KEY = "feishark_ui_studio_track_history_collapsed";
const STUDIO_TECHNICAL_STATE_KEY = "feishark_ui_studio_technical_collapsed";
const STUDIO_JOB_NOTE_KEY_PREFIX = "feishark_studio_job_note_";
const STUDIO_EFFECT_RACK_STATE_PREFIX = "feishark_studio_effect_rack_";
const TEST_RECORDS_VISIBLE_KEY = "feishark_ui_show_test_records";
const TEST_RECORDS_EVENT = "feishark:test-records-visibility-changed";
const RENDER_ENGINE_COPY_ONLY = "copy_only";
const RENDER_ENGINE_FFMPEG_V0 = "ffmpeg_dsp_v0";
const STAGE47_STUDIO_HINTS = [
  "stage47",
  "stage_47",
  "stage-47",
  "朱朱_stage47_single_long",
  "v_d4d7e1c1",
  "train_7f4d6b4e611e",
  "task_b2272d133fff",
  "art_f99f7e4afb10",
];
const SMOKE_ONLY_REVIEW_NOTE = "stage49 browser smoke only - not a human quality verdict";
const REVIEW_ROUTE_BY_VERDICT = {
  unreviewed: "needs_human_review",
  needs_work: "route_to_rework",
  usable: "route_to_candidate_pool",
  release_candidate: "route_to_release_candidate",
  rejected: "route_to_archive_or_rerun",
};
const REVIEW_ROUTE_META = {
  needs_human_review: {
    label: "继续人工试听",
    description: "先用 A/B 面板听完当前成品和原始输入，再保存人工结论。",
  },
  route_to_rework: {
    label: "回工厂调分离 / 重跑翻唱",
    description: "当前成品需要返工，下一步应回到工厂检查分离、模型或重跑翻唱。",
  },
  route_to_candidate_pool: {
    label: "保留为可用候选",
    description: "当前成品可用但还不是发布候选，先收进候选池继续对比。",
  },
  route_to_release_candidate: {
    label: "送入工厂候选成品",
    description: "当前成品可作为发布候选，下一步回工厂进入候选成品管理。",
  },
  route_to_archive_or_rerun: {
    label: "标记废弃，建议重跑",
    description: "当前成品不建议继续修，回工厂重新选择处理路线。",
  },
};

const DEFAULT_EFFECT_RACK_STATE = [
  {
    id: "eq",
    label: "EQ 均衡",
    enabled: false,
    status: "draft",
    params: { low: 0, mid: 0, high: 0 },
  },
  {
    id: "compressor",
    label: "Compressor 压缩",
    enabled: false,
    status: "draft",
    params: { threshold: -18, ratio: 3 },
  },
  {
    id: "reverb",
    label: "Reverb 空间",
    enabled: false,
    status: "draft",
    params: { mix: 10 },
  },
  {
    id: "limiter",
    label: "Limiter 限幅",
    enabled: true,
    status: "draft",
    params: { ceiling: -1 },
  },
];

const state = {
  jobs: [],
  trackHistory: [],
  studioVersions: [],
  versionLedgerAvailable: false,
  versionLedgerFallbackReason: "",
  trackHistoryTrackId: "",
  currentMasterVersion: null,
  currentMasterJobId: "",
  currentMasterArtifactId: "",
  selectedJobId: "",
  selectedJob: null,
  selectedArtifact: null,
  sourceFactoryUrl: "",
  sourceTrackId: "",
  sourceBatchId: "",
  sourceArtifactId: "",
  stageLogs: [],
  waveformBars: [],
  rafId: 0,
  libraryCollapsed: true,
  trackHistoryCollapsed: true,
  technicalCollapsed: true,
  effectRackState: [],
  effectRackStorageKey: "",
  effectRackCapabilities: null,
  effectRackCapabilitiesError: "",
  selectedRenderEngine: RENDER_ENGINE_COPY_ONLY,
  effectExportApiAvailable: false,
  effectExportInFlight: false,
  listeningReview: null,
  listeningReviewInFlight: false,
};

const controlBindings = [
  { inputId: "studioVolume", valueId: "studioVolumeValue", format: value => `${value}%` },
];

function isCompletedStatus(status) {
  return status === "completed" || status === "完成";
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
  const anchor = $("studioLibraryDrawer");
  if (!anchor) return;
  let toggle = document.getElementById("studioTestRecordsToggle");
  if (!toggle) {
    toggle = document.createElement("div");
    toggle.id = "studioTestRecordsToggle";
    toggle.className = "test-record-toggle";
    anchor.insertAdjacentElement("beforebegin", toggle);
  }

  const visible = getShowTestRecords();
  toggle.innerHTML = `
    <label class="test-record-toggle-label">
      <input id="studioShowTestRecords" type="checkbox" ${visible ? "checked" : ""}>
      <span>显示测试记录</span>
    </label>
    <span class="test-record-toggle-note">${
      visible
        ? "当前包含 smoke / stage / test / self_check / playwright 试听成品。"
        : `默认隐藏测试试听成品${hiddenCount ? `，已隐藏 ${hiddenCount} 条。` : "。"}`
    }</span>
  `;
  $("studioShowTestRecords")?.addEventListener("change", event => {
    saveShowTestRecords(event.target.checked);
    refreshResources().catch(() => {});
  });
}

function toAbsoluteUrl(path) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${window.location.origin}${path}`;
}

function basename(value) {
  if (!value) return "-";
  return String(value).split(/[\\/]/).pop() || value;
}

function jobModelSourceSummary(job = {}) {
  if (/checkpoint.*恢复|恢复登记|recovered/i.test(String(job.voice_model_source_summary || ""))) {
    return "checkpoint 恢复 / e90";
  }
  if (job.voice_model_source_summary) {
    return job.voice_model_source_summary;
  }
  if (job.voice_model_origin_kind === "trained_local" && job.voice_model_source_job_id) {
    return `来自本地训练任务 ${job.voice_model_source_job_id}`;
  }
  if (job.voice_model_origin_kind) {
    return modelOriginLabel(job.voice_model_origin_kind);
  }
  return "模型来源未标注";
}

function isStage47StudioJob(job = {}, artifact = {}) {
  const text = [
    job.job_id,
    job.voice_name,
    job.voice_model_id,
    job.generated_model_id,
    job.generated_model_name,
    job.generated_model_summary,
    job.voice_model_source_summary,
    job.voice_model_source_job_id,
    job.voice_model_source_strategy_key,
    job.voice_model_source_material_profile,
    job.output_root,
    artifact.artifact_id,
    artifact.artifact_type,
    artifact.file_name,
    artifact.filename,
    artifact.name,
    artifact.display_name,
    artifact.file_path,
    artifact.download_url,
    artifact.metadata_json,
  ].filter(Boolean).join(" ");
  const normalized = text.toLowerCase();
  return /stage[\s_-]*47/i.test(text)
    || STAGE47_STUDIO_HINTS.some(hint => normalized.includes(hint.toLowerCase()));
}

function renderJobModelSourceLine(job = {}) {
  const sourceSummary = jobModelSourceSummary(job);
  const sourceJobId = job.voice_model_source_job_id || "";
  const recovered = /checkpoint.*恢复|recovered/i.test(sourceSummary);
  const stage47 = isStage47StudioJob(job);
  return `
    <div class="studio-inline-note">
      ${renderModelOriginPill(job.voice_model_origin_kind || "")}
      <span>${escapeHtml(sourceSummary)}</span>
      ${sourceJobId ? `<span class="mono">${escapeHtml(sourceJobId)}</span>` : ""}
      ${recovered ? '<span class="tag checkpoint">checkpoint 恢复</span>' : ""}
      ${stage47 ? '<span class="tag stage47">Stage47 短 smoke / 完整 cover</span>' : ""}
    </div>
  `;
}

function jobNoteKey(jobId = "") {
  return `${STUDIO_JOB_NOTE_KEY_PREFIX}${jobId}`;
}

function normalizeJobNote(note = "") {
  return String(note || "").trim().slice(0, 240);
}

function loadJobNote(jobId = "") {
  if (!jobId) return "";
  return normalizeJobNote(loadUiState(jobNoteKey(jobId), ""));
}

function saveJobNote(jobId = "", note = "") {
  if (!jobId) return "";
  const normalized = normalizeJobNote(note);
  saveUiState(jobNoteKey(jobId), normalized);
  return normalized;
}

function normalizeReviewScore(value, fallback = 0) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 1 || number > 5) return fallback;
  return Math.round(number);
}

function setReviewScoreControl(inputId, valueId, value) {
  const input = $(inputId);
  const output = $(valueId);
  if (!input || !output) return;
  const normalized = normalizeReviewScore(value, 0);
  input.value = normalized ? String(normalized) : "0";
  output.textContent = normalized ? `${normalized}/5` : "未评";
}

function syncReviewScoreLabels() {
  [
    ["studioReviewOverallScore", "studioReviewOverallValue"],
    ["studioReviewVocalScore", "studioReviewVocalValue"],
    ["studioReviewNoiseScore", "studioReviewNoiseValue"],
    ["studioReviewMixScore", "studioReviewMixValue"],
  ].forEach(([inputId, valueId]) => {
    const input = $(inputId);
    const output = $(valueId);
    if (!input || !output) return;
    const score = normalizeReviewScore(input.value, 0);
    output.textContent = score ? `${score}/5` : "未评";
  });
}

function reviewVerdictLabel(verdict = "unreviewed") {
  const labels = {
    unreviewed: "未验收",
    needs_work: "需返工",
    usable: "可用",
    release_candidate: "候选成品",
    rejected: "废弃",
  };
  return labels[verdict] || labels.unreviewed;
}

function reviewRouteFromVerdict(verdict = "unreviewed") {
  return REVIEW_ROUTE_BY_VERDICT[verdict] || REVIEW_ROUTE_BY_VERDICT.unreviewed;
}

function reviewSummaryFromPayload(payload = null, artifact = null, review = {}) {
  const fromPayload = payload?.review_summary
    || payload?.listening_review_summary
    || payload?.summary
    || {};
  const fromArtifact = artifact?.listening_review_summary || {};
  const verdict = review.verdict || fromPayload.verdict || fromArtifact.verdict || "unreviewed";
  const route = fromPayload.route || fromArtifact.route || reviewRouteFromVerdict(verdict);
  return {
    ...fromArtifact,
    ...fromPayload,
    verdict,
    route,
    is_human_reviewed: Boolean(fromPayload.is_human_reviewed ?? fromArtifact.is_human_reviewed),
  };
}

function renderReviewActionButton(href = "", label = "", className = "ghost-btn") {
  if (!href) {
    return `<span class="${escapeHtml(className)} is-disabled" aria-disabled="true">${escapeHtml(label)}</span>`;
  }
  return `<a class="${escapeHtml(className)}" href="${escapeHtml(href)}">${escapeHtml(label)}</a>`;
}

function renderStudioReviewNextAction(job = null, artifact = null, payload = null, review = {}) {
  const label = $("studioReviewRouteLabel");
  const actions = $("studioReviewNextActions");
  const smokeNote = $("studioReviewSmokeNote");
  if (!label || !actions || !smokeNote) return;

  if (!job?.job_id || !artifact?.artifact_id) {
    label.textContent = "载入可验收成品后显示下一步。";
    actions.innerHTML = `<span class="detail-action-hint">当前没有可路由成品。</span>`;
    smokeNote.hidden = true;
    return;
  }

  const summary = reviewSummaryFromPayload(payload, artifact, review);
  const route = summary.route || reviewRouteFromVerdict(summary.verdict);
  const meta = REVIEW_ROUTE_META[route] || REVIEW_ROUTE_META.needs_human_review;
  const factoryUrl = state.sourceFactoryUrl || job.factory_url || buildFactoryUrl(state.sourceBatchId, state.sourceTrackId);
  const downloadUrl = artifact.download_url || `/api/jobs/${job.job_id}/artifacts/${artifact.artifact_id}/download`;
  const notes = String(review.notes || summary.notes_preview || "");
  const isSmokeOnly = notes.includes(SMOKE_ONLY_REVIEW_NOTE);

  label.textContent = `${meta.label}：${meta.description}`;
  smokeNote.hidden = !isSmokeOnly;
  actions.innerHTML = [
    route === "needs_human_review"
      ? `<span class="detail-action-hint">继续使用上方 A/B 播放器人工判断，不会自动启动重任务。</span>`
      : "",
    route === "route_to_rework"
      ? renderReviewActionButton(factoryUrl, "回工厂返工", "primary-btn warm")
      : "",
    route === "route_to_candidate_pool"
      ? `<span class="detail-action-hint">已保留为可用候选；可继续对比其它版本。</span>`
      : "",
    route === "route_to_release_candidate"
      ? renderReviewActionButton(factoryUrl, "送入工厂候选成品", "primary-btn warm")
      : "",
    route === "route_to_archive_or_rerun"
      ? renderReviewActionButton(factoryUrl, "回工厂重跑", "ghost-btn danger")
      : "",
    renderReviewActionButton(toAbsoluteUrl(downloadUrl), "下载当前成品", "ghost-btn"),
  ].filter(Boolean).join("");
}

function renderListeningReviewPanel(job = null, artifact = null, payload = null) {
  const panel = $("studioReviewPanel");
  if (!panel) return;
  const hasArtifact = Boolean(job?.job_id && artifact?.artifact_id);
  panel.hidden = !hasArtifact;
  if (!hasArtifact) {
    state.listeningReview = null;
    const sourceAudio = $("studioReviewSourceAudio");
    if (sourceAudio) {
      sourceAudio.removeAttribute("src");
      sourceAudio.load();
    }
    renderStudioReviewNextAction(null, null);
    return;
  }

  const review = payload?.review || state.listeningReview?.review || {};
  state.listeningReview = payload || { review };
  $("studioReviewVerdict").value = review.verdict || "unreviewed";
  setReviewScoreControl("studioReviewOverallScore", "studioReviewOverallValue", review.overall_score);
  setReviewScoreControl("studioReviewVocalScore", "studioReviewVocalValue", review.vocal_score);
  setReviewScoreControl("studioReviewNoiseScore", "studioReviewNoiseValue", review.noise_score);
  setReviewScoreControl("studioReviewMixScore", "studioReviewMixValue", review.mix_score);
  $("studioReviewNotes").value = review.notes || "";
  const sourceUrl = toAbsoluteUrl(`/api/jobs/${job.job_id}/source-audio/download`);
  const sourceAudio = $("studioReviewSourceAudio");
  if (sourceAudio && sourceAudio.src !== sourceUrl) {
    sourceAudio.src = sourceUrl;
    sourceAudio.load();
  }
  setActionLink("studioReviewSourceDownloadBtn", sourceUrl, true);
  $("studioReviewState").textContent = review.reviewed_at
    ? `已保存：${formatDateTime(review.reviewed_at)} · ${reviewVerdictLabel(review.verdict)}`
    : "尚未保存试听验收。";
  renderStudioReviewNextAction(job, artifact, payload, review);
}

function collectListeningReviewPayload() {
  const score = id => {
    const value = normalizeReviewScore($(id)?.value, 0);
    return value || null;
  };
  return {
    verdict: $("studioReviewVerdict")?.value || "unreviewed",
    overall_score: score("studioReviewOverallScore"),
    vocal_score: score("studioReviewVocalScore"),
    noise_score: score("studioReviewNoiseScore"),
    mix_score: score("studioReviewMixScore"),
    notes: normalizeJobNote($("studioReviewNotes")?.value || ""),
  };
}

async function refreshListeningReview(job = state.selectedJob, artifact = state.selectedArtifact) {
  if (!job?.job_id || !artifact?.artifact_id) {
    renderListeningReviewPanel(null, null);
    return;
  }
  try {
    const payload = await getJSON(`/api/jobs/${job.job_id}/artifacts/${artifact.artifact_id}/review`);
    renderListeningReviewPanel(job, artifact, payload);
  } catch {
    renderListeningReviewPanel(job, artifact, { review: {} });
  }
}

async function saveListeningReview() {
  if (!state.selectedJob?.job_id || !state.selectedArtifact?.artifact_id || state.listeningReviewInFlight) return;
  state.listeningReviewInFlight = true;
  $("studioReviewSaveBtn").disabled = true;
  $("studioReviewState").textContent = "正在保存试听验收...";
  try {
    const payload = await patchJSON(
      `/api/jobs/${state.selectedJob.job_id}/artifacts/${state.selectedArtifact.artifact_id}/review`,
      collectListeningReviewPayload(),
    );
    renderListeningReviewPanel(state.selectedJob, state.selectedArtifact, payload);
    showToast("试听验收已保存到成品 metadata", "success");
  } catch (error) {
    $("studioReviewState").textContent = `保存失败：${toErrorMessage(error)}`;
    showToast(`试听验收保存失败：${toErrorMessage(error)}`, "error");
  } finally {
    state.listeningReviewInFlight = false;
    $("studioReviewSaveBtn").disabled = false;
  }
}

function effectRackStorageKey(trackId = "", jobId = "", artifactId = "") {
  return [
    STUDIO_EFFECT_RACK_STATE_PREFIX,
    trackId || "no-track",
    jobId || "no-job",
    artifactId || "no-artifact",
  ].join("");
}

function cloneEffectRackState(source = DEFAULT_EFFECT_RACK_STATE) {
  return source.map(slot => ({
    ...slot,
    params: { ...slot.params },
  }));
}

function normalizeEffectRackState(stateValue = DEFAULT_EFFECT_RACK_STATE) {
  const source = Array.isArray(stateValue) && stateValue.length
    ? stateValue
    : DEFAULT_EFFECT_RACK_STATE;
  return cloneEffectRackState(DEFAULT_EFFECT_RACK_STATE).map(defaultSlot => {
    const existing = source.find(slot => slot.id === defaultSlot.id) || {};
    return {
      ...defaultSlot,
      enabled: Boolean(existing.enabled ?? defaultSlot.enabled),
      status: typeof existing.status === "string" ? existing.status : defaultSlot.status,
      params: { ...defaultSlot.params, ...(existing.params || {}) },
    };
  });
}

function loadEffectRackState(storageKey = "") {
  if (!storageKey) return cloneEffectRackState();
  return normalizeEffectRackState(loadUiState(storageKey, DEFAULT_EFFECT_RACK_STATE));
}

function persistEffectRackState() {
  if (!state.effectRackStorageKey) return state.effectRackState;
  saveUiState(state.effectRackStorageKey, state.effectRackState);
  return state.effectRackState;
}

function getEnabledEffectRackCount() {
  return state.effectRackState.filter(slot => slot.enabled).length;
}

function getEffectRackHint() {
  return "当前是 copy-only 后处理参数草稿，导出会登记新版本，但暂不执行真实 DSP/VST。";
}

function getEffectRackControlLabel(slot, paramKey) {
  const map = {
    eq: { low: "低频", mid: "中频", high: "高频" },
    compressor: { threshold: "阈值", ratio: "压缩比" },
    reverb: { mix: "混合度" },
    limiter: { ceiling: "上限" },
  };
  return map[slot.id]?.[paramKey] || paramKey;
}

function getEffectRackControlMeta(slot, paramKey) {
  const meta = {
    eq: {
      low: { min: -6, max: 6, step: 1 },
      mid: { min: -6, max: 6, step: 1 },
      high: { min: -6, max: 6, step: 1 },
    },
    compressor: {
      threshold: { min: -30, max: 0, step: 1 },
      ratio: { min: 1, max: 8, step: 0.1 },
    },
    reverb: {
      mix: { min: 0, max: 100, step: 1 },
    },
    limiter: {
      ceiling: { min: -6, max: 0, step: 0.1 },
    },
  };
  return meta[slot.id]?.[paramKey] || { min: 0, max: 100, step: 1 };
}

function formatEffectRackValue(slot, paramKey, value) {
  if (slot.id === "compressor" && paramKey === "ratio") {
    return `${Number(value).toFixed(1)}x`;
  }
  if (slot.id === "reverb" && paramKey === "mix") {
    return `${value}%`;
  }
  if (slot.id === "limiter" && paramKey === "ceiling") {
    return `${value} dB`;
  }
  return `${value} dB`;
}

function updateEffectRackSummary() {
  const summary = $("studioEffectRackSummary");
  const hint = $("studioEffectRackStateHint");
  if (summary) {
    const enabledCount = getEnabledEffectRackCount();
    summary.textContent = `${enabledCount} 个插件槽启用`;
    summary.className = enabledCount ? "tag success" : "tag warn";
  }
  if (hint) {
    hint.textContent = getEffectRackHint();
  }
  syncEffectRackExportAction();
}

function getRenderEngineCapability(engineId = "") {
  const engines = Array.isArray(state.effectRackCapabilities?.engines)
    ? state.effectRackCapabilities.engines
    : [];
  return engines.find(item => item.id === engineId) || null;
}

function isRenderEngineAvailable(engineId = state.selectedRenderEngine) {
  if (engineId === RENDER_ENGINE_COPY_ONLY) {
    const copyCapability = getRenderEngineCapability(RENDER_ENGINE_COPY_ONLY);
    return copyCapability ? copyCapability.available !== false : true;
  }
  const capability = getRenderEngineCapability(engineId);
  return Boolean(capability?.available);
}

function renderEngineUnavailableReason(engineId = state.selectedRenderEngine) {
  const capability = getRenderEngineCapability(engineId);
  if (capability?.reason) return capability.reason;
  if (capability?.message) return capability.message;
  if (engineId === RENDER_ENGINE_FFMPEG_V0) return "本机未检测到可用 ffmpeg，真实渲染 v0 暂不可用。";
  return "当前输出模式暂不可用。";
}

function renderEngineExportLabel(engineId = state.selectedRenderEngine) {
  return engineId === RENDER_ENGINE_FFMPEG_V0 ? "渲染处理版 v0" : "导出处理版草稿";
}

function renderEngineBusyLabel(engineId = state.selectedRenderEngine) {
  return engineId === RENDER_ENGINE_FFMPEG_V0 ? "正在渲染处理版 v0..." : "正在导出草稿...";
}

function renderEngineHint(engineId = state.selectedRenderEngine) {
  if (engineId === RENDER_ENGINE_FFMPEG_V0) {
    return isRenderEngineAvailable(RENDER_ENGINE_FFMPEG_V0)
      ? "真实渲染 v0 会调用本机 ffmpeg 离线生成新音频；当前不是 VST。"
      : renderEngineUnavailableReason(RENDER_ENGINE_FFMPEG_V0);
  }
  if (state.effectRackCapabilitiesError) {
    return "真实渲染能力暂不可用，可先登记草稿。";
  }
  return "登记草稿会保存参数和版本，不改变真实音频。";
}

function syncRenderModeUi() {
  const copyBtn = $("studioRenderModeCopyBtn");
  const ffmpegBtn = $("studioRenderModeFfmpegBtn");
  const hint = $("studioRenderModeHint");

  if (copyBtn) {
    copyBtn.classList.toggle("is-active", state.selectedRenderEngine === RENDER_ENGINE_COPY_ONLY);
    copyBtn.setAttribute("aria-pressed", String(state.selectedRenderEngine === RENDER_ENGINE_COPY_ONLY));
    copyBtn.disabled = false;
  }
  if (ffmpegBtn) {
    const available = isRenderEngineAvailable(RENDER_ENGINE_FFMPEG_V0);
    ffmpegBtn.classList.toggle("is-active", state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0);
    ffmpegBtn.setAttribute("aria-pressed", String(state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0));
    ffmpegBtn.disabled = !available;
    ffmpegBtn.title = available ? "调用本机 ffmpeg 离线生成新音频，不是 VST。" : renderEngineUnavailableReason(RENDER_ENGINE_FFMPEG_V0);
  }
  if (hint) {
    hint.textContent = renderEngineHint();
  }
}

function setRenderEngine(engineId = RENDER_ENGINE_COPY_ONLY) {
  if (engineId === RENDER_ENGINE_FFMPEG_V0 && !isRenderEngineAvailable(RENDER_ENGINE_FFMPEG_V0)) {
    state.selectedRenderEngine = RENDER_ENGINE_COPY_ONLY;
    showToast(renderEngineUnavailableReason(RENDER_ENGINE_FFMPEG_V0), "info");
  } else {
    state.selectedRenderEngine = engineId === RENDER_ENGINE_FFMPEG_V0 ? RENDER_ENGINE_FFMPEG_V0 : RENDER_ENGINE_COPY_ONLY;
  }
  renderEffectRack();
  syncRenderModeUi();
  syncEffectRackExportAction();
}

function canExportEffectRackDraft() {
  return Boolean(
    state.effectExportApiAvailable &&
    isRenderEngineAvailable(state.selectedRenderEngine) &&
    state.sourceTrackId &&
    state.selectedJob?.job_id &&
    state.sourceArtifactId &&
    state.selectedArtifact?.download_url,
  );
}

function syncEffectRackExportAction() {
  const button = $("studioEffectRackExportBtn");
  const hint = $("studioEffectRackExportHint");
  if (!button || !hint) return;

  const canExport = canExportEffectRackDraft() && !state.effectExportInFlight;
  button.disabled = !canExport;
  button.classList.toggle("is-disabled", !canExport);
  button.textContent = state.effectExportInFlight ? renderEngineBusyLabel() : renderEngineExportLabel();

  if (state.effectExportInFlight) {
    hint.textContent = state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0
      ? "正在请求后端生成 ffmpeg v0 渲染版；当前不是 VST。"
      : "正在请求后端登记处理版草稿；当前仍是 copy-only，不执行真实 DSP/VST。";
  } else if (!state.effectExportApiAvailable) {
    hint.textContent = state.effectRackCapabilitiesError
      ? "真实渲染能力暂不可用，可先登记草稿。"
      : "后端 API 暂不可用，无法导出处理版。";
  } else if (!isRenderEngineAvailable(state.selectedRenderEngine)) {
    hint.textContent = renderEngineUnavailableReason(state.selectedRenderEngine);
  } else if (!state.sourceTrackId || !state.selectedJob?.job_id) {
    hint.textContent = "需要从带曲目和任务的录音棚版本进入，才能导出处理版。";
  } else if (!state.sourceArtifactId || !state.selectedArtifact?.download_url) {
    hint.textContent = "当前没有可播放产物，暂不能导出处理版。";
  } else if (state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0) {
    hint.textContent = "当前导出会调用本机 ffmpeg 离线生成新音频；当前不是 VST 插件。";
  } else {
    hint.textContent = "当前导出为仅复制草稿：会登记新版本，但暂不执行真实 DSP/VST 处理。";
  }
  syncRenderModeUi();
}

function renderEffectRack() {
  const list = $("studioEffectRackList");
  if (!list) return;

  if (!state.effectRackState.length) {
    list.innerHTML = `<div class="studio-resource-empty">暂无后处理插件槽。</div>`;
    updateEffectRackSummary();
    return;
  }

  list.innerHTML = state.effectRackState.map(slot => {
    const controls = Object.entries(slot.params || {}).map(([paramKey, value]) => {
      const meta = getEffectRackControlMeta(slot, paramKey);
      return `
        <label class="studio-effect-param">
          <span>${escapeHtml(getEffectRackControlLabel(slot, paramKey))}</span>
          <input
            type="range"
            min="${meta.min}"
            max="${meta.max}"
            step="${meta.step}"
            value="${escapeHtml(value)}"
            data-effect-slot-param="${escapeHtml(slot.id)}"
            data-effect-param-key="${escapeHtml(paramKey)}"
          >
          <strong>${escapeHtml(formatEffectRackValue(slot, paramKey, value))}</strong>
        </label>
      `;
    }).join("");

    const slotNote = state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0
      ? "参数会随请求保存到新 artifact metadata；真实渲染 v0 会调用本机 ffmpeg，不是 VST。"
      : "草稿参数会随导出请求保存到新 artifact metadata；当前导出只复制源音频，不执行真实 DSP/VST。";
    return `
      <article class="studio-effect-slot ${slot.enabled ? "is-enabled" : ""}">
        <div class="studio-effect-slot-head">
          <div>
            <strong>${escapeHtml(slot.label)}</strong>
            <div class="studio-inline-note">状态：${escapeHtml(slot.status)} · ${slot.enabled ? "已启用" : "已关闭"}</div>
          </div>
          <label class="studio-effect-toggle">
            <input
              type="checkbox"
              data-effect-slot-toggle="${escapeHtml(slot.id)}"
              ${slot.enabled ? "checked" : ""}
            >
            <span>开关</span>
          </label>
        </div>
        <div class="studio-effect-slot-note">${escapeHtml(slotNote)}</div>
        <div class="studio-effect-param-grid">
          ${controls}
        </div>
      </article>
    `;
  }).join("");

  updateEffectRackSummary();
}

function updateEffectRackStorage() {
  if (!state.effectRackStorageKey) return;
  saveUiState(state.effectRackStorageKey, state.effectRackState);
  renderEffectRack();
}

function effectExportErrorMessage(error) {
  const detail = error?.payload?.detail;
  if (detail && typeof detail === "object") {
    return [detail.code, detail.message].filter(Boolean).join("：") || toErrorMessage(error);
  }
  return toErrorMessage(error);
}

function buildFactoryUrl(batchId = "", trackId = "") {
  if (!batchId && !trackId) return "/factory";
  const params = new URLSearchParams();
  if (batchId) params.set("batch_id", batchId);
  if (trackId) params.set("track_id", trackId);
  const query = params.toString();
  return query ? `/factory?${query}` : "/factory";
}

function formatTime(seconds) {
  const total = Number(seconds || 0);
  if (!Number.isFinite(total) || total <= 0) return "00:00";
  const whole = Math.floor(total);
  const mins = Math.floor(whole / 60);
  const secs = whole % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function hashString(input) {
  let hash = 2166136261;
  for (const char of String(input || "")) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function createWaveBars(seedText, count = 96) {
  let seed = hashString(seedText) || 1;
  const bars = [];
  for (let index = 0; index < count; index += 1) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const normalized = (seed % 1000) / 1000;
    const shaped = 0.24 + Math.abs(Math.sin(index * 0.38 + normalized * 3.14)) * 0.66;
    bars.push(Math.min(0.92, Math.max(0.18, shaped)));
  }
  return bars;
}

function setStudioStatus(text, tone = "warning") {
  $("studioStatusText").textContent = text;
  $("studioStatusDot").className = `dot ${tone}`;
}

function setActionLink(anchorId, href = "", enabled = false) {
  const node = $(anchorId);
  if (!node) return;
  node.href = enabled ? href : "#";
  node.classList.toggle("is-disabled", !enabled);
  node.setAttribute("aria-disabled", String(!enabled));
}

function resolveFactoryContext(job = {}) {
  const params = new URLSearchParams(window.location.search);
  const hasTrackId = Object.prototype.hasOwnProperty.call(job, "track_id");
  const hasBatchId = Object.prototype.hasOwnProperty.call(job, "batch_id");
  const trackId = hasTrackId ? (job.track_id || "") : (params.get("track_id") || "");
  const batchId = hasBatchId ? (job.batch_id || "") : (params.get("batch_id") || "");
  const factoryUrl = job.factory_url || buildFactoryUrl(batchId, trackId);
  return {
    trackId,
    batchId,
    factoryUrl,
  };
}

function isTrackHistoryEligible(job = {}) {
  const isCover = job.job_kind === "cover" || job.job_type === "cover";
  return isCover && isCompletedStatus(job.status) && Boolean(job.can_open_studio || job.final_artifact_download_url);
}

function sortTrackHistory(items = []) {
  return [...items].sort((left, right) => {
    const leftTime = String(left.created_at || "");
    const rightTime = String(right.created_at || "");
    const timeCompare = rightTime.localeCompare(leftTime);
    if (timeCompare !== 0) return timeCompare;
    return String(right.job_id || "").localeCompare(String(left.job_id || ""));
  });
}

function getVersionArtifactId(item = {}) {
  return item.artifact_id || item.final_artifact_id || "";
}

function getLatestTrackHistoryVersionId() {
  const item = state.trackHistory[0] || {};
  return item.version_id || getVersionArtifactId(item) || item.job_id || "";
}

function isCurrentMasterVersion(jobId = "", artifactId = "") {
  if (!jobId || jobId !== state.currentMasterJobId) {
    return false;
  }
  if (!state.currentMasterArtifactId || !artifactId) {
    return true;
  }
  return artifactId === state.currentMasterArtifactId;
}

function getTrackVersionMeta(job = {}) {
  const jobId = job?.job_id || "";
  const artifactId = getVersionArtifactId(job);
  const versionId = job?.version_id || artifactId || jobId;
  const selectedArtifactId = state.selectedArtifact?.artifact_id || state.sourceArtifactId || "";
  const isCurrent = Boolean(jobId) && jobId === state.selectedJobId && (!artifactId || !selectedArtifactId || artifactId === selectedArtifactId);
  const latestVersionId = getLatestTrackHistoryVersionId();
  const isLatest = Boolean(versionId) && versionId === latestVersionId;
  const isHistory = Boolean(versionId) && state.trackHistory.length > 0 && !isLatest;
  const isMaster = Boolean(job?.is_current_master) || isCurrentMasterVersion(jobId, artifactId);
  return { isCurrent, isLatest, isHistory, isMaster };
}

function versionDisplayName(item = {}) {
  return item.voice_name || item.voice_model_id || item.file_name || item.job_id || item.version_id || "未命名版本";
}

function versionStudioUrl(item = {}) {
  if (item.studio_url) return item.studio_url;
  const params = new URLSearchParams();
  if (item.track_id || state.sourceTrackId) params.set("track_id", item.track_id || state.sourceTrackId);
  if (item.job_id) params.set("job_id", item.job_id);
  const artifactId = getVersionArtifactId(item);
  if (artifactId) params.set("artifact_id", artifactId);
  if (state.sourceBatchId) params.set("batch_id", state.sourceBatchId);
  const query = params.toString();
  return query ? `/studio?${query}` : "#";
}

function versionDownloadUrl(item = {}) {
  return toAbsoluteUrl(item.download_url || item.final_artifact_download_url || "");
}

function parseJsonObject(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function getVersionMetadata(item = {}) {
  const artifactId = getVersionArtifactId(item);
  if (
    state.selectedArtifact?.metadata_json &&
    state.selectedJob?.job_id === item.job_id &&
    state.selectedArtifact?.artifact_id === artifactId
  ) {
    return parseJsonObject(state.selectedArtifact.metadata_json);
  }
  return parseJsonObject(item.metadata || item.metadata_json);
}

function effectLabel(effect = {}) {
  const id = typeof effect === "string" ? effect : effect.id;
  const labels = {
    eq: "EQ",
    compressor: "Compressor",
    limiter: "Limiter",
    reverb: "Reverb",
  };
  return labels[id] || id || "";
}

function effectListText(items = []) {
  if (!Array.isArray(items) || !items.length) return "";
  return items.map(effectLabel).filter(Boolean).join("、");
}

function metadataEffectSummaryText(item = {}) {
  const metadata = getVersionMetadata(item);
  const lines = [];
  const applied = effectListText(metadata.applied_effects || item.applied_effects);
  const unsupported = effectListText(metadata.unsupported_effects || item.unsupported_effects);
  if (applied) lines.push(`已应用：${applied}`);
  if (unsupported) lines.push(`暂未支持：${unsupported}`);
  return lines;
}

function artifactTypeText(type = "") {
  if (type === "cover_master") return "原始翻唱成品";
  if (type === "studio_effect_draft_master") return "处理版草稿";
  if (type === "studio_effect_render_master") return "已渲染处理版";
  return type || "成品版本";
}

function processingModeText(mode = "", artifactType = "") {
  if (mode === "original_cover" || artifactType === "cover_master") return "原始成品";
  if (mode === "copy_only_no_dsp") return "仅登记草稿，未执行真实 DSP/VST";
  if (mode === "ffmpeg_dsp_v0") return "ffmpeg v0 已应用";
  return mode || "处理方式未标注";
}

function renderTrackVersionBadges(job = {}) {
  const { isCurrent, isLatest, isHistory, isMaster } = getTrackVersionMeta(job);
  const parts = [];
  if (isCurrent) parts.push('<span class="tag success">当前正在试听</span>');
  if (isLatest) parts.push('<span class="tag success">最新版本</span>');
  if (isHistory) parts.push('<span class="tag warn">历史版本</span>');
  if (isMaster) parts.push('<span class="tag master">当前主成品</span>');
  return parts.join(" ");
}

function updateGlobalLibraryHint() {
  const hint = $("studioGlobalLibraryHint");
  if (!hint) return;
  if (state.sourceTrackId && state.trackHistory.length) {
    hint.textContent = `当前优先围绕这个 Track 的 ${state.trackHistory.length} 个版本工作；全局试听品库保留为次级入口。`;
    return;
  }
  hint.textContent = "全局试听品库，作为次级入口保留";
}

function getStudioLibraryCollapsed() {
  return Boolean(loadUiState(STUDIO_LIBRARY_STATE_KEY, true));
}

function getStudioTrackHistoryCollapsed() {
  return Boolean(loadUiState(STUDIO_TRACK_HISTORY_STATE_KEY, true));
}

function getStudioTechnicalCollapsed() {
  return Boolean(loadUiState(STUDIO_TECHNICAL_STATE_KEY, true));
}

async function setStudioLibraryCollapsed(collapsed, { immediate = false, allowEmptyOpen = false } = {}) {
  const drawer = $("studioLibraryDrawer");
  const body = $("studioLibraryBody");
  const button = $("studioLibraryToggleBtn");
  if (!drawer || !body || !button) return;

  state.libraryCollapsed = Boolean(collapsed);
  saveUiState(STUDIO_LIBRARY_STATE_KEY, state.libraryCollapsed);

  const hasResources = state.jobs.length > 0;
  const effectiveCollapsed = hasResources ? state.libraryCollapsed : false;
  drawer.dataset.collapsed = String(effectiveCollapsed);
  drawer.classList.toggle("is-collapsed", effectiveCollapsed);
  button.setAttribute("aria-expanded", String(!effectiveCollapsed));
  button.disabled = !hasResources && !allowEmptyOpen;
  button.textContent = hasResources
    ? (effectiveCollapsed ? "展开试听品库 ▾" : "收起试听品库 ▴")
    : "试听品库为空";

  const alreadyCollapsed = body.hidden;
  if (immediate || alreadyCollapsed === effectiveCollapsed) {
    body.hidden = effectiveCollapsed;
    return;
  }

  await slideToggle(body, !effectiveCollapsed);
}

async function setDrawerCollapsed(key, collapsed, drawerId, bodyId, buttonId, { immediate = false } = {}) {
  const drawer = $(drawerId);
  const body = $(bodyId);
  const button = $(buttonId);
  if (!drawer || !body || !button) return;

  saveUiState(key, Boolean(collapsed));
  drawer.dataset.collapsed = String(Boolean(collapsed));
  drawer.classList.toggle("is-collapsed", Boolean(collapsed));
  button.setAttribute("aria-expanded", String(!collapsed));
  const openLabel = button.dataset.openLabel || "展开";
  const closeLabel = button.dataset.closeLabel || "收起";
  button.textContent = collapsed ? `${openLabel} ▾` : `${closeLabel} ▴`;
  if (immediate) {
    body.hidden = Boolean(collapsed);
    return;
  }
  await slideToggle(body, !collapsed);
}

function renderCurrentResourceSummary(job = null, artifact = null) {
  const summary = $("studioCurrentResourceSummary");
  if (!summary) return;

  if (!job) {
    summary.textContent = state.jobs.length
      ? "当前未载入成品，保留快速选择和摘要，完整试听品库按需展开。"
      : "当前没有可试听成品。先回到工作台完成一个翻唱任务。";
    return;
  }

  const fileName = basename(artifact?.file_path || "final_master.wav");
  const label = job.voice_name || job.job_id;
  summary.textContent = `当前已载入：${label} / ${fileName} · 状态：${isCompletedStatus(job.status) ? "完成" : job.status || "-"}`;
}

function versionSourceSummary(item = {}) {
  const artifactType = item.artifact_type || item.final_artifact_type || "";
  const processingMode = item.processing_mode || item.final_artifact_processing_mode || "";
  if (artifactType === "cover_master") return "原始翻唱成品";
  if (artifactType === "studio_effect_draft_master") return "处理版草稿，仅登记未渲染";
  if (artifactType === "studio_effect_render_master" || processingMode === "ffmpeg_dsp_v0") return "已渲染处理版，ffmpeg v0";
  return [artifactTypeText(artifactType), processingModeText(processingMode, artifactType)].filter(Boolean).join("，");
}

function isSameVersionIdentity(left = {}, right = {}) {
  const leftArtifactId = getVersionArtifactId(left);
  const rightArtifactId = getVersionArtifactId(right);
  return Boolean(
    left.job_id &&
    right.job_id &&
    left.job_id === right.job_id &&
    (!leftArtifactId || !rightArtifactId || leftArtifactId === rightArtifactId),
  );
}

function renderCurrentMasterCard() {
  const card = $("studioCurrentMasterCard");
  if (!card) return;

  const title = $("studioCurrentMasterTitle");
  const summary = $("studioCurrentMasterSummary");
  const meta = $("studioCurrentMasterMeta");
  const master = state.currentMasterVersion;

  if (!master) {
    title.textContent = "尚未指定当前主成品";
    summary.textContent = state.sourceTrackId
      ? "当前 Track 还没有显式主成品，可在版本抽屉里选择一个版本设为当前主成品。"
      : "载入带 Track 的 Studio 版本后，这里会固定显示当前主成品。";
    meta.innerHTML = `<span>类型：-</span><span>处理：-</span>`;
    setActionLink("studioCurrentMasterOpenBtn", "", false);
    setActionLink("studioCurrentMasterDownloadBtn", "", false);
    return;
  }

  const name = versionDisplayName(master);
  const artifactType = master.artifact_type || master.final_artifact_type || "";
  const processingMode = master.processing_mode || master.final_artifact_processing_mode || "";
  const typeText = artifactTypeText(artifactType);
  const modeText = processingModeText(processingMode, artifactType);
  const playingVersion = {
    job_id: state.selectedJob?.job_id || "",
    artifact_id: state.selectedArtifact?.artifact_id || state.sourceArtifactId || "",
    artifact_type: state.selectedArtifact?.artifact_type || "",
    processing_mode: parseJsonObject(state.selectedArtifact?.metadata_json).processing_mode || "",
    voice_name: state.selectedJob?.voice_name || "",
    voice_model_id: state.selectedJob?.voice_model_id || "",
    file_name: basename(state.selectedArtifact?.file_path || ""),
  };
  const playingLabel = versionDisplayName(playingVersion);
  const summaryParts = [`${versionSourceSummary(master)}。`];
  if (playingVersion.job_id && !isSameVersionIdentity(playingVersion, master)) {
    summaryParts.push(`当前正在试听：${playingLabel}`);
    summaryParts.push(`当前主成品：${name}`);
  }
  const effectLines = metadataEffectSummaryText(master);
  summary.innerHTML = summaryParts.concat(effectLines).map(line => `<div>${escapeHtml(line)}</div>`).join("");
  title.textContent = name;
  title.title = name;
  meta.innerHTML = `
    <span title="${escapeHtml(typeText)}">类型：${escapeHtml(typeText)}</span>
    <span title="${escapeHtml(modeText)}">处理：${escapeHtml(modeText)}</span>
    <span title="${escapeHtml(master.job_id || "-")}">任务：${escapeHtml(master.job_id || "-")}</span>
    <span title="${escapeHtml(getVersionArtifactId(master) || "-")}">Artifact：${escapeHtml(getVersionArtifactId(master) || "-")}</span>
  `;
  setActionLink("studioCurrentMasterOpenBtn", versionStudioUrl(master), true);
  setActionLink("studioCurrentMasterDownloadBtn", versionDownloadUrl(master), Boolean(versionDownloadUrl(master)));
}

function renderSourceContext(job = null, artifact = null) {
  const title = $("studioSourceTitle");
  const summary = $("studioSourceSummary");
  const grid = $("studioSourceMetaGrid");
  const context = resolveFactoryContext(job || {});
  state.sourceFactoryUrl = context.factoryUrl;
  state.sourceTrackId = context.trackId;
  state.sourceBatchId = context.batchId;
  state.sourceArtifactId = artifact?.artifact_id || "";

  const hasFactorySource = Boolean(context.trackId);
  setActionLink("studioFactoryBackBtn", context.factoryUrl, hasFactorySource);
  setActionLink("studioFactoryOpenBtn", context.factoryUrl, hasFactorySource);

  if (!job) {
    title.textContent = "当前不是从工厂曲目位进入";
    summary.textContent = "普通打开 `/studio` 时，仍会保留全局试听品库兼容行为。";
    grid.innerHTML = `
      <div class="meta-card">
        <div class="meta-label">来源 Track</div>
        <div class="meta-value">未关联</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">所属 Batch</div>
        <div class="meta-value">-</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">当前音色</div>
        <div class="meta-value">-</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">当前任务</div>
        <div class="meta-value mono">-</div>
      </div>
    `;
    return;
  }

  const fileName = basename(artifact?.file_path || "final_master.wav");
  const voiceLabel = job.voice_name || job.voice_model_id || "未命名音色";
  const trackTitle = job.track_title || (hasFactorySource ? context.trackId : "未关联 Track");
  const batchLabel = job.batch_name || context.batchId || "-";
  const statusLabel = isCompletedStatus(job.status) ? "完成" : (job.status || "-");

  title.textContent = hasFactorySource
    ? `来源曲目：${trackTitle}`
    : "当前成品未关联工厂曲目";
  summary.textContent = hasFactorySource
    ? `这是 ${voiceLabel} 的翻唱成品，当前载入 ${fileName}，模型来源已跟随成品一起带入录音棚。`
    : `当前载入 ${fileName}，仍可在全局试听品库里继续切换其他已完成成品。`;
  grid.innerHTML = `
    <div class="meta-card">
      <div class="meta-label">来源 Track</div>
      <div class="meta-value" title="${escapeHtml(trackTitle)}">${escapeHtml(trackTitle)}</div>
      ${renderPathLine(context.trackId || "-", { subtle: !context.trackId })}
    </div>
    <div class="meta-card">
      <div class="meta-label">所属 Batch</div>
      <div class="meta-value" title="${escapeHtml(batchLabel)}">${escapeHtml(batchLabel)}</div>
      ${renderPathLine(context.batchId || "-", { subtle: !context.batchId })}
    </div>
    <div class="meta-card">
      <div class="meta-label">当前音色</div>
      <div class="meta-value" title="${escapeHtml(voiceLabel)}">${escapeHtml(voiceLabel)}</div>
      ${renderPathLine(job.voice_model_id || "-", { subtle: !job.voice_model_id })}
      ${renderJobModelSourceLine(job)}
    </div>
      <div class="meta-card">
        <div class="meta-label">当前任务 / Artifact</div>
        <div class="meta-value mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</div>
        ${renderPathLine(artifact?.artifact_id || "-", { subtle: !artifact?.artifact_id })}
        <div class="studio-inline-note">当前成品状态：${escapeHtml(statusLabel)}</div>
      </div>
  `;
}

function buildTrackHistoryItem(job = {}) {
  const voiceLabel = versionDisplayName(job);
  const artifactId = getVersionArtifactId(job);
  const artifactType = job.artifact_type || job.final_artifact_type || "";
  const processingMode = job.processing_mode || job.final_artifact_processing_mode || "";
  const typeText = artifactTypeText(artifactType);
  const modeText = processingModeText(processingMode, artifactType);
  const studioUrl = versionStudioUrl(job);
  const downloadUrl = versionDownloadUrl(job);
  const isMaster = Boolean(job.is_current_master) || isCurrentMasterVersion(job.job_id, artifactId);
  const isCurrent = state.selectedJobId === job.job_id && (!artifactId || artifactId === state.sourceArtifactId);
  const effectLines = metadataEffectSummaryText(job);
  const noteLines = [modeText].concat(effectLines).filter(Boolean);
  return `
    <div class="studio-history-item ${state.selectedJobId === job.job_id ? "is-active" : ""}">
      <div class="studio-history-item-head">
        <div>
          <strong title="${escapeHtml(voiceLabel)}">${escapeHtml(voiceLabel)}</strong>
          <div class="studio-resource-meta">
            <span>${escapeHtml(formatDateTime(job.created_at))}</span>
            <span>${escapeHtml(typeText)}</span>
            <span class="mono" title="${escapeHtml(artifactId || job.job_id || "-")}">${escapeHtml(artifactId || job.job_id || "-")}</span>
          </div>
        </div>
        <div class="studio-history-badges">
          ${renderTrackVersionBadges(job)}
        </div>
      </div>
      <div class="studio-history-note ${noteLines.length ? "" : "is-empty"}">
        <strong>${escapeHtml(typeText)}</strong>
        ${noteLines.map(line => `<span>${escapeHtml(line)}</span>`).join("")}
        ${job.file_path ? `<span class="mono" title="${escapeHtml(job.file_path)}">${escapeHtml(job.file_path)}</span>` : ""}
      </div>
      <div class="studio-history-actions">
        <a class="ghost-btn drawer-toggle-btn" href="${escapeHtml(studioUrl)}" data-track-history-job-id="${escapeHtml(job.job_id)}" data-artifact-id="${escapeHtml(artifactId)}">打开此版本</a>
        <a class="ghost-btn drawer-toggle-btn ${downloadUrl ? "" : "is-disabled"}" href="${escapeHtml(downloadUrl || "#")}" target="_blank" aria-disabled="${downloadUrl ? "false" : "true"}">下载</a>
        ${isMaster
          ? '<span class="tag master">当前主成品</span>'
          : `<button class="ghost-btn drawer-toggle-btn studio-history-master-btn" type="button" data-set-track-master-job-id="${escapeHtml(job.job_id)}" data-artifact-id="${escapeHtml(artifactId)}">设为当前主成品</button>`
        }
      </div>
    </div>
  `;
}

function syncTrackHistoryDrawer({ forceOpen = false } = {}) {
  const drawer = $("studioTrackHistoryDrawer");
  const body = $("studioTrackHistoryBody");
  const button = $("studioTrackHistoryToggleBtn");
  if (!drawer || !body || !button) return;
  const collapsed = forceOpen ? false : state.trackHistoryCollapsed;
  drawer.dataset.collapsed = String(collapsed);
  drawer.classList.toggle("is-collapsed", collapsed);
  body.hidden = collapsed;
  button.disabled = !state.trackHistory.length;
  button.setAttribute("aria-expanded", String(!collapsed));
  button.textContent = state.trackHistory.length
    ? (collapsed ? "展开版本 ▾" : "收起版本 ▴")
    : "版本为空";
}

function renderTrackHistory() {
  const panel = $("studioTrackHistoryPanel");
  const list = $("studioTrackHistoryList");
  const summary = $("studioTrackHistorySummary");
  const fallback = $("studioVersionLedgerFallback");
  if (!panel || !list || !summary) return;
  if (fallback) {
    fallback.hidden = state.versionLedgerAvailable || !state.versionLedgerFallbackReason;
    fallback.textContent = "版本账本暂不可用，已退回旧成品历史。";
  }

  if (!state.sourceTrackId) {
    panel.hidden = true;
    list.innerHTML = `<div class="studio-resource-empty">当前没有来源曲目，上方保持普通录音棚兼容模式。</div>`;
    summary.textContent = "只有从工厂曲目位进入，才会出现当前曲目的版本账本。";
    updateGlobalLibraryHint();
    syncTrackHistoryDrawer();
    renderCurrentMasterCard();
    return;
  }

  panel.hidden = false;
  updateGlobalLibraryHint();

  if (!state.trackHistory.length) {
    summary.textContent = "当前来源曲目还没有可回放的录音棚版本。";
    list.innerHTML = `<div class="studio-resource-empty">这个来源曲目还没有更多已完成版本，可先回到工厂继续创建新版本。</div>`;
    syncTrackHistoryDrawer();
    renderCurrentMasterCard();
    return;
  }

  const latest = state.trackHistory[0];
  const latestLabel = versionDisplayName(latest);
  const currentMaster = state.currentMasterVersion || state.trackHistory.find(job => Boolean(job.is_current_master) || isCurrentMasterVersion(job.job_id, getVersionArtifactId(job)));
  if (currentMaster?.job_id) {
    const masterLabel = versionDisplayName(currentMaster);
    const masterVersionId = currentMaster.version_id || getVersionArtifactId(currentMaster) || currentMaster.job_id;
    const latestVersionId = latest.version_id || getVersionArtifactId(latest) || latest.job_id;
    summary.textContent = masterVersionId === latestVersionId
      ? `共 ${state.trackHistory.length} 个版本，最新版本 ${latestLabel} 也是当前主成品。`
      : `共 ${state.trackHistory.length} 个版本，最新版本是 ${latestLabel}，当前主成品是 ${masterLabel}。`;
  } else {
    summary.textContent = `共 ${state.trackHistory.length} 个版本，最新版本是 ${latestLabel}，尚未手动指定当前主成品。`;
  }
  list.innerHTML = state.trackHistory.map(buildTrackHistoryItem).join("");
  syncTrackHistoryDrawer();
  renderCurrentMasterCard();
}

function buildResourceCard(job) {
  return `
    <button
      class="studio-resource-item ${state.selectedJobId === job.job_id ? "is-active" : ""}"
      type="button"
      data-job-id="${escapeHtml(job.job_id)}"
    >
      <strong>${escapeHtml(job.voice_name || job.job_id)}</strong>
      <div class="studio-resource-meta">
        <span>${escapeHtml(formatDateTime(job.created_at))}</span>
        <span class="mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</span>
      </div>
      ${renderStatusPill(job.status)}
      ${renderPathLine(job.output_root || "-", { subtle: true })}
    </button>
  `;
}

function getVisibleResourceJobs() {
  if (!state.selectedJob?.job_id) {
    return state.jobs;
  }
  if (!getShowTestRecords() && isTestRecord(state.selectedJob)) {
    return state.jobs;
  }
  return state.jobs.some(job => job.job_id === state.selectedJob.job_id)
    ? state.jobs
    : [state.selectedJob, ...state.jobs];
}

async function refreshTrackHistory(trackId = "", { force = false } = {}) {
  if (!trackId) {
    state.trackHistoryTrackId = "";
    state.trackHistory = [];
    state.studioVersions = [];
    state.versionLedgerAvailable = false;
    state.versionLedgerFallbackReason = "";
    state.currentMasterVersion = null;
    state.currentMasterJobId = "";
    state.currentMasterArtifactId = "";
    renderTrackHistory();
    return [];
  }

  if (!force && state.trackHistoryTrackId === trackId && state.trackHistory.length) {
    renderTrackHistory();
    return state.trackHistory;
  }

  try {
    const ledger = await getJSON(`/api/tracks/${trackId}/studio-versions${buildQuery(withTestRecordParams({ limit: 50, offset: 0 }))}`);
    state.trackHistoryTrackId = trackId;
    state.versionLedgerAvailable = true;
    state.versionLedgerFallbackReason = "";
    state.currentMasterJobId = ledger.current_master_job_id || "";
    state.currentMasterArtifactId = ledger.current_master_artifact_id || "";
    const visibleItems = filterTestRecords(ledger.items || []);
    state.currentMasterVersion = ledger.current_master && !isTestRecord(ledger.current_master)
      ? ledger.current_master
      : visibleItems.find(item => item.is_current_master) || null;
    state.studioVersions = visibleItems;
    state.trackHistory = state.studioVersions;
    renderTrackHistory();
    return state.trackHistory;
  } catch (error) {
    try {
      const response = await getJSON(`/api/tracks/${trackId}/jobs${buildQuery(withTestRecordParams({ limit: 50, offset: 0 }))}`);
      state.trackHistoryTrackId = trackId;
      state.versionLedgerAvailable = false;
      state.versionLedgerFallbackReason = toErrorMessage(error);
      state.currentMasterJobId = response.current_master_job_id || "";
      state.currentMasterArtifactId = response.current_master_artifact_id || "";
      state.currentMasterVersion = response.current_master || null;
      state.studioVersions = [];
      state.trackHistory = sortTrackHistory(filterTestRecords(response.items || []).filter(isTrackHistoryEligible));
      renderTrackHistory();
      showToast("版本账本暂不可用，已退回旧成品历史。", "info");
      return state.trackHistory;
    } catch (fallbackError) {
      state.trackHistoryTrackId = trackId;
      state.trackHistory = [];
      state.studioVersions = [];
      state.versionLedgerAvailable = false;
      state.versionLedgerFallbackReason = toErrorMessage(error);
      state.currentMasterVersion = null;
      state.currentMasterJobId = "";
      state.currentMasterArtifactId = "";
      renderTrackHistory();
      showToast(`录音棚读取当前曲目版本失败：${toErrorMessage(fallbackError)}`, "error");
      return [];
    }
  }
}

function renderResourcePicker() {
  const visibleJobs = getVisibleResourceJobs();

  $("studioResourceCount").textContent = visibleJobs.length
    ? `共 ${visibleJobs.length} 个可试听成品`
    : "当前没有可进入修音室的 cover 成品";
  $("studioLibrarySummary").textContent = visibleJobs.length
    ? `已完成 ${visibleJobs.length} 个成品，默认只保留快速选择，完整卡片库按需展开。`
    : "当前没有可展开的试听品库。";

  $("studioResourceSelect").innerHTML = visibleJobs.length
    ? visibleJobs.map(job => `
        <option value="${escapeHtml(job.job_id)}" ${job.job_id === state.selectedJobId ? "selected" : ""}>
          ${escapeHtml(job.voice_name || job.job_id)} · ${escapeHtml(job.job_id)}
        </option>
      `).join("")
    : `<option value="">暂无可用成品</option>`;

  $("studioResourceList").innerHTML = visibleJobs.length
    ? visibleJobs.map(buildResourceCard).join("")
    : `<div class="studio-resource-empty">还没有已完成的翻唱成品。先回到工作台创建并完成一个翻唱任务，再进入修音室。</div>`;

  renderCurrentResourceSummary(state.selectedJob, state.selectedArtifact);
}

function renderJobNoteEditor(job = null) {
  const editor = $("studioJobNoteEditor");
  const input = $("studioJobNoteInput");
  const stateText = $("studioJobNoteState");
  if (!editor || !input || !stateText) return;

  if (!job?.job_id) {
    editor.hidden = true;
    input.value = "";
    stateText.textContent = "备注只保存在本机浏览器。";
    return;
  }

  editor.hidden = false;
  input.value = loadJobNote(job.job_id);
  stateText.textContent = `本机工作备注 · 绑定 ${job.job_id}，刷新后仍会保留。`;
}

function persistCurrentJobNote({ showFeedback = false } = {}) {
  const jobId = state.selectedJob?.job_id || "";
  const input = $("studioJobNoteInput");
  const stateText = $("studioJobNoteState");
  if (!jobId || !input || !stateText) return;

  const saved = saveJobNote(jobId, input.value);
  input.value = saved;
  stateText.textContent = saved
    ? `已保存到本机浏览器 · ${saved.length}/240`
    : "备注已清空，当前版本没有额外说明。";
  renderTrackHistory();
  if (showFeedback) {
    showToast("已保存当前版本备注", "info");
  }
}

function renderEmptyStudio() {
  state.selectedJob = null;
  state.selectedArtifact = null;
  state.selectedJobId = "";
  state.trackHistory = [];
  state.studioVersions = [];
  state.versionLedgerAvailable = false;
  state.versionLedgerFallbackReason = "";
  state.trackHistoryTrackId = "";
  state.currentMasterVersion = null;
  state.currentMasterJobId = "";
  state.currentMasterArtifactId = "";
  state.sourceFactoryUrl = "";
  state.sourceTrackId = "";
  state.sourceBatchId = "";
  state.sourceArtifactId = "";
  state.stageLogs = [];
  state.waveformBars = [];
  state.effectRackStorageKey = effectRackStorageKey("", "", "");
  state.effectRackState = loadEffectRackState(state.effectRackStorageKey);
  renderCurrentResourceSummary(null, null);
  renderSourceContext(null, null);
  $("studioTrackKicker").textContent = "等待选择翻唱成品";
  $("studioTrackTitle").textContent = "请选择一个已完成的翻唱任务";
  $("studioTrackSubline").textContent = "可从右侧资源列表选取，也可在工作台任务详情里点击“进入录音棚”。";
  $("studioCurrentFileName").textContent = "当前文件：-";
  $("studioCurrentDuration").textContent = "时长：-";
  $("studioCurrentJobId").textContent = "任务：-";
  $("studioCurrentTime").textContent = "播放位置：00:00";
  $("studioArtifactStage").textContent = "产物阶段：-";
  $("studioArtifactPath").textContent = "产物路径：-";
  $("studioVersionNote").textContent = "当前还没有载入成品，导出位保持预留。";
  $("studioAudio").removeAttribute("src");
  $("studioAudio").load();
  $("studioPlayToggleBtn").disabled = true;
  $("studioPlayToggleBtn").textContent = "播放";
  syncEffectRackExportAction();
  setActionLink("studioDownloadBtn", "", false);
  setActionLink("studioSummaryDownloadBtn", "", false);
  setActionLink("studioExportDraftBtn", "", false);
  setActionLink("studioOpenArtifactBtn", "", false);
  $("studioMetaGrid").innerHTML = `
    <div class="meta-card"><div class="meta-label">当前状态</div><div class="meta-value">未载入</div></div>
    <div class="meta-card"><div class="meta-label">最终阶段</div><div class="meta-value">-</div></div>
    <div class="meta-card"><div class="meta-label">创建时间</div><div class="meta-value">-</div></div>
    <div class="meta-card"><div class="meta-label">工作目录</div><div class="meta-value mono">-</div></div>
  `;
  $("studioSummaryFileName").textContent = "当前文件：-";
  $("studioSummaryStatusPill").innerHTML = "";
  $("studioSummaryStagePill").innerHTML = "";
  $("studioVersionRolePill").innerHTML = "";
  $("studioVersionHint").hidden = true;
  $("studioVersionHint").textContent = "";
  $("studioSummaryText").textContent = "载入成品后，这里会明确告诉你当前正在围绕哪一个任务和哪一个最终成品继续工作。";
  $("studioArtifactMetaGrid").innerHTML = `
    <div class="meta-card">
      <div class="meta-label">来源任务</div>
      <div class="meta-value mono">-</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">来源音色</div>
      <div class="meta-value">-</div>
    </div>
  `;
  $("studioTechnicalMetaGrid").innerHTML = `
    <div class="meta-card">
      <div class="meta-label">Artifact 路径</div>
      <div class="meta-value mono" id="studioArtifactPath">产物路径：-</div>
    </div>
  `;
  $("studioStageLogList").innerHTML = `<div class="studio-resource-empty">载入成品后显示阶段日志。</div>`;
  $("studioTechnicalSummary").textContent = "默认收起任务 / 产物路径、长 ID、阶段日志等工程字段。";
  renderTrackHistory();
  renderCurrentMasterCard();
  renderJobNoteEditor(null);
  renderListeningReviewPanel(null, null);
  renderEffectRack();
  drawWaveform();
  setStudioStatus("等待载入成品资源", "warning");
}

function renderStudioContractUnavailable({ jobId = "", artifactId = "", error = null } = {}) {
  renderEmptyStudio();
  const message = `Backend restart or UI contract unavailable. Requested job_id=${jobId || "-"} artifact_id=${artifactId || "-"}${error ? `; ${toErrorMessage(error)}` : ""}`;
  $("studioTrackKicker").textContent = "录音棚契约不可用";
  $("studioTrackTitle").textContent = "后端重启或契约更新所需";
  $("studioTrackSubline").textContent = message;
  $("studioSummaryText").textContent = message;
  $("studioCurrentResourceSummary").textContent = message;
  $("studioResourceList").innerHTML = `<div class="studio-resource-empty">${escapeHtml(message)}</div>`;
  $("studioTechnicalSummary").textContent = message;
  $("studioStageLogList").innerHTML = `<div class="studio-resource-empty">${escapeHtml(message)}</div>`;
  setStudioStatus("后端重启 / 契约不可用", "danger");
}

function pickPlayableArtifact(jobId, artifacts, requestedArtifactId = "") {
  const seen = new Set();
  const items = (artifacts || []).filter(item => {
    const key = `${item.artifact_type}|${item.file_path}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (requestedArtifactId) {
    const requested = items.find(item => item.artifact_id === requestedArtifactId);
    if (requested) return requested;
  }

  return (
    items.find(item => item.artifact_type === "cover_master") ||
    items.find(item => item.is_final && basename(item.file_path).toLowerCase() === "final_master.wav") ||
    items.find(item => item.is_final) ||
    {
      artifact_id: "",
      artifact_type: "cover_master",
      stage_name: "cover_mix",
      file_path: "",
      file_size: 0,
      is_final: 1,
      download_url: `/api/download/${jobId}`,
    }
  );
}

function updateQuery(jobId, artifactId = "", trackId = "", batchId = "") {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  if (artifactId) params.set("artifact_id", artifactId);
  if (trackId) params.set("track_id", trackId);
  if (batchId) params.set("batch_id", batchId);
  const query = params.toString();
  const nextUrl = query ? `/studio?${query}` : "/studio";
  window.history.replaceState(null, "", nextUrl);
}

function renderJobMeta(job, artifact) {
  $("studioMetaGrid").innerHTML = `
    <div class="meta-card">
      <div class="meta-label">当前状态</div>
      <div class="meta-value">${renderStatusPill(job.status)}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">最终阶段</div>
      <div class="meta-value">${renderStagePill(artifact?.stage_name || job.current_stage, job.status)}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">创建时间</div>
      <div class="meta-value">${escapeHtml(formatDateTime(job.created_at))}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">工作目录</div>
      <div class="meta-value mono" title="${escapeHtml(job.output_root || "-")}">${escapeHtml(job.output_root || "-")}</div>
    </div>
  `;
}

function renderTechnicalDetails(job, artifact) {
  const metaGrid = $("studioTechnicalMetaGrid");
  const stageLogList = $("studioStageLogList");
  const technicalSummary = $("studioTechnicalSummary");
  if (!metaGrid || !stageLogList || !technicalSummary) return;

  const artifactPath = artifact?.file_path || artifact?.download_url || "-";
  const artifactId = artifact?.artifact_id || "-";
  const voiceSummary = jobModelSourceSummary(job);
  technicalSummary.textContent = "默认收起任务 / 产物路径、长 ID、阶段日志等工程字段。";
  metaGrid.innerHTML = `
    <div class="meta-card">
      <div class="meta-label">Job ID</div>
      <div class="meta-value mono" title="${escapeHtml(job.job_id || "-")}">${escapeHtml(job.job_id || "-")}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">Artifact ID</div>
      <div class="meta-value mono" title="${escapeHtml(artifactId)}">${escapeHtml(artifactId)}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">Source Summary</div>
      <div class="meta-value" title="${escapeHtml(voiceSummary)}">${escapeHtml(voiceSummary)}</div>
    </div>
    <div class="meta-card">
      <div class="meta-label">Artifact Path</div>
      <div class="meta-value mono" id="studioArtifactPath" title="${escapeHtml(artifactPath)}">${escapeHtml(artifactPath)}</div>
    </div>
  `;

  const logs = Array.isArray(state.stageLogs) ? state.stageLogs : [];
  if (!logs.length) {
    stageLogList.innerHTML = `<div class="studio-resource-empty">阶段日志默认折叠，当前没有可显示内容。</div>`;
    return;
  }

  stageLogList.innerHTML = logs.map(log => `
    <div class="studio-stage-log-item">
      <div class="studio-stage-log-head">
        <strong>${escapeHtml(stageText(log.stage_name || ""))}</strong>
        <span class="tag ${log.status === "failed" ? "danger" : log.status === "completed" ? "success" : "warn"}">${escapeHtml(log.status || "-")}</span>
      </div>
      <div class="studio-stage-log-meta">
        <span>${escapeHtml(formatDateTime(log.created_at || log.updated_at || ""))}</span>
        <span class="mono">${escapeHtml(log.stage_name || "-")}</span>
      </div>
      <div class="studio-stage-log-message">${escapeHtml(log.message || log.detail || "无阶段详情")}</div>
    </div>
  `).join("");
}

function renderArtifactSummary(job, artifact) {
  const fileName = basename(artifact?.file_path || "final_master.wav");
  const voiceLabel = job.voice_name || job.voice_model_id || "未命名音色";
  const playUrl = toAbsoluteUrl(artifact?.download_url || `/api/download/${job.job_id}`);
  const stage47 = isStage47StudioJob(job, artifact || {});
  const versionHint = $("studioVersionHint");
  const versionState = getTrackVersionMeta({
    job_id: job.job_id,
    artifact_id: artifact?.artifact_id || "",
  });
  const { isLatest, isHistory, isMaster } = versionState;
  const hasTrackHistory = Boolean(state.sourceTrackId && state.trackHistory.length);
  const latest = hasTrackHistory ? state.trackHistory[0] : null;
  const latestLabel = latest ? (latest.voice_name || latest.voice_model_id || latest.job_id) : "";
  const master = hasTrackHistory
    ? state.trackHistory.find(item => isCurrentMasterVersion(item.job_id, item.final_artifact_id || ""))
    : null;
  const masterLabel = master ? (master.voice_name || master.voice_model_id || master.job_id) : "";

  $("studioSummaryFileName").textContent = `当前文件：${fileName}`;
  $("studioSummaryStatusPill").innerHTML = renderStatusPill(job.status);
  $("studioSummaryStagePill").innerHTML = renderStagePill(artifact?.stage_name || job.current_stage, job.status);
  $("studioVersionRolePill").innerHTML = renderTrackVersionBadges({
    job_id: job.job_id,
    artifact_id: artifact?.artifact_id || "",
  }) + (stage47 ? '<span class="tag stage47">Stage47 短 smoke / 完整 cover</span>' : "");
  if (hasTrackHistory && isHistory && isMaster && !isLatest) {
    versionHint.hidden = false;
    versionHint.textContent = `当前试听不是这个 Track 的最新版本，但它已经被设为当前主成品。最新版本是 ${latestLabel}。`;
  } else if (hasTrackHistory && isLatest && isMaster) {
    versionHint.hidden = false;
    versionHint.textContent = "当前试听既是最新版本，也是这个曲目的当前主成品。";
  } else if (hasTrackHistory && isLatest && master?.job_id && !isMaster) {
    versionHint.hidden = false;
    versionHint.textContent = `当前试听是这个 Track 的最新版本，但当前主成品仍是 ${masterLabel}。`;
  } else if (hasTrackHistory && isHistory && !isLatest) {
    versionHint.hidden = false;
    versionHint.textContent = master?.job_id
      ? `当前试听不是这个 Track 的最新版本。最新版本是 ${latestLabel}，当前主成品是 ${masterLabel}。`
      : `当前试听不是这个 Track 的最新版本。最新版本是 ${latestLabel}，当前尚未手动指定主成品。`;
  } else if (hasTrackHistory && isLatest) {
    versionHint.hidden = false;
    versionHint.textContent = master?.job_id
      ? "当前试听就是这个 Track 的最新完成版本。"
      : "当前试听就是这个 Track 的最新完成版本，当前尚未手动指定主成品。";
  } else {
    versionHint.hidden = true;
    versionHint.textContent = "";
  }
  const stage47Note = stage47 ? "这是 Stage47 短 smoke / 完整 cover 验收入口，不标注为正式成品。" : "";
  $("studioSummaryText").textContent = hasTrackHistory && master?.job_id
    ? `当前围绕任务 ${job.job_id} 的最终成品继续工作。当前主成品是 ${masterLabel}，所用模型${jobModelSourceSummary(job)}。${stage47Note}`
    : `当前围绕任务 ${job.job_id} 的最终成品继续工作，可直接下载原始成品；所用模型${jobModelSourceSummary(job)}。${stage47Note}`;
  $("studioArtifactMetaGrid").innerHTML = `
    <div class="meta-card">
      <div class="meta-label">来源任务</div>
      <div class="meta-value mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</div>
      ${renderPathLine(job.output_root || "-", { subtle: !job.output_root })}
    </div>
    <div class="meta-card">
      <div class="meta-label">来源音色</div>
      <div class="meta-value" title="${escapeHtml(voiceLabel)}">${escapeHtml(voiceLabel)}</div>
      ${renderPathLine(job.voice_model_id || "-", { subtle: !job.voice_model_id })}
    </div>
    <div class="meta-card">
      <div class="meta-label">模型来源</div>
      <div class="meta-value" title="${escapeHtml(jobModelSourceSummary(job))}">${escapeHtml(jobModelSourceSummary(job))}</div>
      ${renderJobModelSourceLine(job)}
    </div>
    ${stage47 ? `
      <div class="meta-card">
        <div class="meta-label">Stage47 验收</div>
        <div class="meta-value">短 smoke / 完整 cover</div>
        <div class="studio-inline-note">用于真实闭环验收，不标注为正式成品。</div>
      </div>
    ` : ""}
  `;
  setActionLink("studioSummaryDownloadBtn", playUrl, true);
  renderJobNoteEditor(job);
}

async function handleSetCurrentMaster(jobId, artifactId = "") {
  if (!state.sourceTrackId || !jobId) {
    showToast("当前没有可设置主成品的来源 Track。", "info");
    return;
  }

  try {
    const payload = await postJSON(`/api/tracks/${state.sourceTrackId}/master`, {
      job_id: jobId,
      artifact_id: artifactId,
    });
    state.currentMasterJobId = payload.current_master_job_id || "";
    state.currentMasterArtifactId = payload.current_master_artifact_id || "";
    state.currentMasterVersion = payload.current_master || state.currentMasterVersion;
    await refreshTrackHistory(state.sourceTrackId, { force: true });
    renderResourcePicker();
    if (state.selectedJob && state.selectedArtifact) {
      renderArtifactSummary(state.selectedJob, state.selectedArtifact);
    }
    renderCurrentMasterCard();
    showToast("当前主成品已切换，工厂和录音棚会同步采用这个版本。", "success");
  } catch (error) {
    showToast(`设置当前主成品失败：${toErrorMessage(error)}`, "error");
  }
}

function syncPlayerUi(job, artifact) {
  const audio = $("studioAudio");
  const playUrl = toAbsoluteUrl(artifact?.download_url || `/api/download/${job.job_id}`);
  const fileName = basename(artifact?.file_path || "final_master.wav");
  const context = resolveFactoryContext(job);

  state.selectedArtifact = artifact;
  state.sourceArtifactId = artifact?.artifact_id || "";
  state.effectRackStorageKey = effectRackStorageKey(context.trackId, job.job_id, state.sourceArtifactId);
  state.effectRackState = loadEffectRackState(state.effectRackStorageKey);
  state.waveformBars = createWaveBars(`${job.job_id}|${fileName}`);

  $("studioTrackKicker").textContent = `Cover 成品 · ${job.job_id}`;
  $("studioTrackTitle").textContent = job.voice_name || fileName || job.job_id;
  $("studioTrackSubline").textContent = artifact?.file_path
    ? `当前载入 ${fileName}，后续可在此基础上接入更细的片段编辑和导出链。`
    : "当前通过兼容下载入口载入 final_master，适合继续试听与后处理设计。";
  $("studioCurrentFileName").textContent = `当前文件：${fileName}`;
  $("studioCurrentJobId").textContent = `任务：${job.job_id}`;
  $("studioArtifactStage").textContent = `产物阶段：${artifact?.stage_name || job.current_stage || "-"}`;
  $("studioArtifactPath").textContent = `产物路径：${artifact?.file_path || playUrl}`;
  $("studioCurrentTime").textContent = "播放位置：00:00";
  $("studioCurrentDuration").textContent = "时长：加载中...";
  $("studioVersionNote").textContent = artifact?.file_path
    ? `当前载入的是 ${fileName}，路径已经切到 job artifact 体系。`
    : "当前通过兼容主下载入口载入原始成品。";
  renderCurrentResourceSummary(job, artifact);
  renderSourceContext(job, artifact);
  renderArtifactSummary(job, artifact);
  renderTechnicalDetails(job, artifact);
  renderEffectRack();
  syncEffectRackExportAction();

  setActionLink("studioDownloadBtn", playUrl, true);
  setActionLink("studioExportDraftBtn", "", false);
  setActionLink("studioOpenArtifactBtn", "", false);

  if (audio.src !== playUrl) {
    audio.src = playUrl;
    audio.load();
  }

  $("studioPlayToggleBtn").disabled = false;
  $("studioPlayToggleBtn").textContent = "播放";
  setStudioStatus(`已载入 ${fileName}`, "success");
  drawWaveform();
}

async function loadJob(jobId, { artifactId = "" } = {}) {
  if (!jobId) {
    renderEmptyStudio();
    return;
  }

  state.selectedJobId = jobId;
  renderResourcePicker();

  try {
    const [job, artifactResp, stageLogsResp] = await Promise.all([
      getJSON(`/api/jobs/${jobId}`),
      getJSON(`/api/jobs/${jobId}/artifacts`),
      getJSON(`/api/jobs/${jobId}/stage-logs${buildQuery(withTestRecordParams({}))}`).catch(() => ({ stage_logs: [] })),
    ]);
    if (!getShowTestRecords() && isTestRecord(job)) {
      renderEmptyStudio();
      renderTestRecordsToggle(1);
      setStudioStatus("测试成品已隐藏，打开“显示测试记录”后可查看", "warning");
      return;
    }

    const artifact = pickPlayableArtifact(jobId, artifactResp.artifacts || [], artifactId);
    state.stageLogs = filterTestRecords(stageLogsResp.stage_logs || []);
    state.selectedJob = job;
    state.selectedArtifact = artifact;
    renderResourcePicker();
    renderJobMeta(job, artifact);
    syncPlayerUi(job, artifact);
    await refreshListeningReview(job, artifact);
    const context = resolveFactoryContext(job);
    updateQuery(jobId, artifact?.artifact_id || "", context.trackId, context.batchId);
    await refreshTrackHistory(context.trackId, { force: state.trackHistoryTrackId !== context.trackId });
    renderTrackHistory();
    renderArtifactSummary(job, artifact);
  } catch (error) {
    showToast(`录音棚载入任务失败：${toErrorMessage(error)}`, "error");
    renderStudioContractUnavailable({ jobId, artifactId, error });
  }
}

function drawWaveform() {
  const canvas = $("studioWaveCanvas");
  if (!canvas) return;

  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.floor(rect.width || 640));
  const height = Math.max(160, Math.floor(rect.height || 192));
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = "rgba(10, 10, 15, 0.98)";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  for (let line = 1; line < 4; line += 1) {
    const y = (height / 4) * line;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  const bars = state.waveformBars.length ? state.waveformBars : createWaveBars("studio-empty");
  const gap = 3;
  const barWidth = Math.max(3, Math.floor((width - gap * (bars.length - 1)) / bars.length));
  const audio = $("studioAudio");
  const progress = audio && audio.duration ? Math.min(1, audio.currentTime / audio.duration) : 0;
  const progressIndex = Math.floor(progress * bars.length);

  bars.forEach((value, index) => {
    const barHeight = Math.max(12, value * (height - 28));
    const x = index * (barWidth + gap);
    const y = (height - barHeight) / 2;
    ctx.fillStyle = index <= progressIndex
      ? "rgba(255, 122, 47, 0.92)"
      : "rgba(180, 188, 208, 0.28)";
    ctx.fillRect(x, y, barWidth, barHeight);
  });

  ctx.fillStyle = "rgba(255, 255, 255, 0.68)";
  ctx.font = '12px "Inter", sans-serif';
  ctx.fillText("Waveform Preview Skeleton", 16, 20);

  if (progress > 0 && progress < 1) {
    const playheadX = Math.min(width - 2, Math.max(2, progress * width));
    ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
    ctx.fillRect(playheadX, 0, 2, height);
  }
}

function stopWaveLoop() {
  if (state.rafId) {
    window.cancelAnimationFrame(state.rafId);
    state.rafId = 0;
  }
}

function startWaveLoop() {
  stopWaveLoop();
  const tick = () => {
    drawWaveform();
    const audio = $("studioAudio");
    if (!audio?.paused && !audio?.ended) {
      state.rafId = window.requestAnimationFrame(tick);
    } else {
      state.rafId = 0;
    }
  };
  state.rafId = window.requestAnimationFrame(tick);
}

function syncAudioMeta() {
  const audio = $("studioAudio");
  $("studioCurrentDuration").textContent = `时长：${audio.duration ? formatTime(audio.duration) : "-"}`;
  $("studioCurrentTime").textContent = `播放位置：${formatTime(audio.currentTime)}`;
  drawWaveform();
}

async function refreshResources() {
  try {
    const response = await getJSON(`/api/jobs${buildQuery(withTestRecordParams({ job_type: "cover", limit: 100, offset: 0 }))}`);
    const rawJobs = (response.items || [])
      .filter(job => job.job_type === "cover" && isCompletedStatus(job.status))
      .sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")));
    const jobs = filterTestRecords(rawJobs);

    state.jobs = jobs;
    const responseHiddenCount = Number(response.hidden_test_count);
    const hiddenCount = Number.isFinite(responseHiddenCount)
      ? responseHiddenCount
      : Math.max(0, rawJobs.length - jobs.length);
    renderTestRecordsToggle(hiddenCount);

    const params = new URLSearchParams(window.location.search);
    const requestedJobId = params.get("job_id") || "";
    const requestedArtifactId = params.get("artifact_id") || "";
    const safeRequestedJobId = !getShowTestRecords() && isTestRecord(requestedJobId) ? "" : requestedJobId;
    const nextJobId = state.selectedJobId || safeRequestedJobId || jobs[0]?.job_id || "";

    if (!jobs.length && !nextJobId) {
      renderResourcePicker();
      await setStudioLibraryCollapsed(true, { immediate: true, allowEmptyOpen: true });
      renderEmptyStudio();
      return;
    }

    renderResourcePicker();
    await setStudioLibraryCollapsed(getStudioLibraryCollapsed(), { immediate: true });
    await loadJob(nextJobId, { artifactId: requestedArtifactId });
  } catch (error) {
    showToast(`录音棚读取成品列表失败：${toErrorMessage(error)}`, "error");
    const params = new URLSearchParams(window.location.search);
    const requestedJobId = params.get("job_id") || "";
    const requestedArtifactId = params.get("artifact_id") || "";
    if (requestedJobId && (getShowTestRecords() || !isTestRecord(requestedJobId))) {
      await loadJob(requestedJobId, { artifactId: requestedArtifactId });
      return;
    }
    $("studioResourceCount").textContent = "成品资源读取失败";
    $("studioLibrarySummary").textContent = "成品资源读取失败，请稍后重试。";
    $("studioResourceSelect").innerHTML = `<option value="">资源读取失败</option>`;
    $("studioResourceList").innerHTML = `<div class="studio-resource-empty">成品资源读取失败，请回到工作台确认至少存在一个已完成的翻唱任务。</div>`;
    await setStudioLibraryCollapsed(true, { immediate: true, allowEmptyOpen: true });
    renderEmptyStudio();
  }
}

async function refreshEffectRackExportAvailability() {
  try {
    const capabilities = await getJSON("/api/studio/effect-rack/capabilities");
    state.effectRackCapabilities = capabilities;
    state.effectRackCapabilitiesError = "";
    state.effectExportApiAvailable = isRenderEngineAvailable(RENDER_ENGINE_COPY_ONLY);
    if (state.selectedRenderEngine === RENDER_ENGINE_FFMPEG_V0 && !isRenderEngineAvailable(RENDER_ENGINE_FFMPEG_V0)) {
      state.selectedRenderEngine = RENDER_ENGINE_COPY_ONLY;
    }
  } catch (error) {
    state.effectRackCapabilities = null;
    state.effectRackCapabilitiesError = toErrorMessage(error);
    state.effectExportApiAvailable = true;
    state.selectedRenderEngine = RENDER_ENGINE_COPY_ONLY;
  }
  syncRenderModeUi();
  syncEffectRackExportAction();
}

async function handleEffectRackExport() {
  if (!canExportEffectRackDraft() || state.effectExportInFlight) {
    syncEffectRackExportAction();
    return;
  }

  state.effectExportInFlight = true;
  syncEffectRackExportAction();

  try {
    const noteInput = $("studioJobNoteInput");
    const renderEngine = state.selectedRenderEngine;
    const payload = await postJSON("/api/studio/effect-rack/export", {
      track_id: state.sourceTrackId,
      source_job_id: state.selectedJob.job_id,
      source_artifact_id: state.sourceArtifactId,
      effect_rack: state.effectRackState,
      export_profile: "studio_balanced",
      render_engine: renderEngine,
      note: normalizeJobNote(noteInput?.value || ""),
    });
    showToast(
      renderEngine === RENDER_ENGINE_FFMPEG_V0
        ? "已生成 ffmpeg v0 渲染版；当前不是 VST"
        : "已生成处理版草稿；当前未执行真实 DSP/VST",
      "success",
    );
    if (payload?.studio_url) {
      window.location.href = payload.studio_url;
      return;
    }
    await loadJob(state.selectedJob.job_id, { artifactId: payload?.artifact_id || state.sourceArtifactId });
  } catch (error) {
    showToast(`处理版导出失败：${effectExportErrorMessage(error)}`, "error");
  } finally {
    state.effectExportInFlight = false;
    syncEffectRackExportAction();
  }
}

function bindAudioEvents() {
  const audio = $("studioAudio");
  const playToggle = $("studioPlayToggleBtn");

  playToggle.addEventListener("click", async () => {
    try {
      if (audio.paused) {
        await audio.play();
      } else {
        audio.pause();
      }
    } catch (error) {
      showToast(`播放失败：${toErrorMessage(error)}`, "error");
    }
  });

  audio.addEventListener("loadedmetadata", syncAudioMeta);
  audio.addEventListener("timeupdate", syncAudioMeta);
  audio.addEventListener("play", () => {
    playToggle.textContent = "暂停";
    startWaveLoop();
  });
  audio.addEventListener("pause", () => {
    playToggle.textContent = audio.currentTime && !audio.ended ? "继续播放" : "播放";
    stopWaveLoop();
    drawWaveform();
  });
  audio.addEventListener("ended", () => {
    playToggle.textContent = "重新播放";
    stopWaveLoop();
    drawWaveform();
  });
  audio.addEventListener("error", () => {
    setStudioStatus("成品音频加载失败", "danger");
  });
}

function bindResourceEvents() {
  window.addEventListener("storage", event => {
    if (event.key === TEST_RECORDS_VISIBLE_KEY) {
      renderTestRecordsToggle();
      refreshResources().catch(() => {});
    }
  });
  document.addEventListener(TEST_RECORDS_EVENT, () => {
    renderTestRecordsToggle();
  });

  $("studioReloadBtn").addEventListener("click", () => {
    if (state.selectedJobId) {
      loadJob(state.selectedJobId).catch(() => {});
      return;
    }
    refreshResources().catch(() => {});
  });

  $("studioResourceSelect").addEventListener("change", event => {
    const jobId = event.target.value;
    if (!jobId) return;
    loadJob(jobId).catch(() => {});
  });

  $("studioResourceList").addEventListener("click", event => {
    const button = event.target.closest("[data-job-id]");
    if (!button) return;
    loadJob(button.dataset.jobId).catch(() => {});
  });

  $("studioTrackHistoryList").addEventListener("click", event => {
    const masterButton = event.target.closest("[data-set-track-master-job-id]");
    if (masterButton) {
      handleSetCurrentMaster(masterButton.dataset.setTrackMasterJobId, masterButton.dataset.artifactId || "").catch(() => {});
      return;
    }
    const button = event.target.closest("[data-track-history-job-id]");
    if (!button) return;
    loadJob(button.dataset.trackHistoryJobId, { artifactId: button.dataset.artifactId || "" }).catch(() => {});
  });

  $("studioLibraryToggleBtn").addEventListener("click", () => {
    const nextCollapsed = !getStudioLibraryCollapsed();
    setStudioLibraryCollapsed(nextCollapsed).catch(() => {});
  });

  $("studioTrackHistoryToggleBtn").addEventListener("click", () => {
    state.trackHistoryCollapsed = !state.trackHistoryCollapsed;
    saveUiState(STUDIO_TRACK_HISTORY_STATE_KEY, state.trackHistoryCollapsed);
    syncTrackHistoryDrawer();
  });

  $("studioTechnicalToggleBtn").addEventListener("click", () => {
    state.technicalCollapsed = !state.technicalCollapsed;
    setDrawerCollapsed(
      STUDIO_TECHNICAL_STATE_KEY,
      state.technicalCollapsed,
      "studioTechnicalDrawer",
      "studioTechnicalBody",
      "studioTechnicalToggleBtn",
      { immediate: false },
    ).catch(() => {});
  });

  $("studioEffectRackExportBtn").addEventListener("click", () => {
    handleEffectRackExport().catch(() => {});
  });

  $("studioRenderModeCopyBtn")?.addEventListener("click", () => {
    setRenderEngine(RENDER_ENGINE_COPY_ONLY);
  });

  $("studioRenderModeFfmpegBtn")?.addEventListener("click", () => {
    setRenderEngine(RENDER_ENGINE_FFMPEG_V0);
  });

  $("studioJobNoteInput").addEventListener("input", () => {
    persistCurrentJobNote();
  });

  $("studioJobNoteSaveBtn").addEventListener("click", () => {
    persistCurrentJobNote({ showFeedback: true });
  });

  [
    "studioReviewOverallScore",
    "studioReviewVocalScore",
    "studioReviewNoiseScore",
    "studioReviewMixScore",
  ].forEach(id => {
    $(id)?.addEventListener("input", syncReviewScoreLabels);
  });

  $("studioReviewVerdict")?.addEventListener("change", () => {
    renderStudioReviewNextAction(state.selectedJob, state.selectedArtifact, null, collectListeningReviewPayload());
  });

  $("studioReviewSaveBtn")?.addEventListener("click", () => {
    saveListeningReview().catch(() => {});
  });
}

function bindControlEvents() {
  controlBindings.forEach(binding => {
    const input = $(binding.inputId);
    const value = $(binding.valueId);
    const sync = () => {
      value.textContent = binding.format(input.value);
      if (binding.inputId === "studioVolume") {
        $("studioAudio").volume = Math.max(0, Math.min(1, Number(input.value) / 100));
      }
    };
    input.addEventListener("input", sync);
    sync();
  });

  const loudness = $("studioLoudnessMode");
  const loudnessValue = $("studioLoudnessValue");
  const syncLoudness = () => {
    loudnessValue.textContent = loudness.options[loudness.selectedIndex]?.textContent || "Studio 平衡";
  };
  loudness.addEventListener("change", syncLoudness);
  syncLoudness();

  state.resizeObserver = new ResizeObserver(() => drawWaveform());
  state.resizeObserver.observe($("studioWaveCanvas"));
}

function bindEffectRackEvents() {
  const list = $("studioEffectRackList");
  if (!list) return;

  const updateParamFromEvent = event => {
    const param = event.target.closest("[data-effect-slot-param]");
    if (!param) return false;
    const slotId = param.dataset.effectSlotParam;
    const key = param.dataset.effectParamKey;
    const slot = state.effectRackState.find(item => item.id === slotId);
    if (!slot) return false;
    const numeric = Number(param.value);
    slot.params[key] = Number.isFinite(numeric) ? numeric : slot.params[key];
    updateEffectRackStorage();
    return true;
  };

  list.addEventListener("change", event => {
    const toggle = event.target.closest("[data-effect-slot-toggle]");
    if (toggle) {
      const slotId = toggle.dataset.effectSlotToggle;
      const slot = state.effectRackState.find(item => item.id === slotId);
      if (!slot) return;
      slot.enabled = Boolean(toggle.checked);
      updateEffectRackStorage();
      return;
    }

    updateParamFromEvent(event);
  });

  list.addEventListener("input", event => {
    updateParamFromEvent(event);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  state.libraryCollapsed = getStudioLibraryCollapsed();
  state.trackHistoryCollapsed = getStudioTrackHistoryCollapsed();
  state.technicalCollapsed = getStudioTechnicalCollapsed();
  await setStudioLibraryCollapsed(state.libraryCollapsed, { immediate: true });
  renderTestRecordsToggle();
  await setDrawerCollapsed(STUDIO_TRACK_HISTORY_STATE_KEY, state.trackHistoryCollapsed, "studioTrackHistoryDrawer", "studioTrackHistoryBody", "studioTrackHistoryToggleBtn", { immediate: true });
  await setDrawerCollapsed(STUDIO_TECHNICAL_STATE_KEY, state.technicalCollapsed, "studioTechnicalDrawer", "studioTechnicalBody", "studioTechnicalToggleBtn", { immediate: true });
  bindAudioEvents();
  bindResourceEvents();
  bindControlEvents();
  bindEffectRackEvents();
  renderEmptyStudio();
  await refreshEffectRackExportAvailability();
  await refreshResources();
});
