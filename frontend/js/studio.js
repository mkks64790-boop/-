import { getJSON, postJSON, toErrorMessage } from "./api.js";
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
  effectExportApiAvailable: false,
  effectExportInFlight: false,
};

const controlBindings = [
  { inputId: "studioVolume", valueId: "studioVolumeValue", format: value => `${value}%` },
];

function isCompletedStatus(status) {
  return status === "completed" || status === "完成";
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

function renderJobModelSourceLine(job = {}) {
  const sourceSummary = jobModelSourceSummary(job);
  const sourceJobId = job.voice_model_source_job_id || "";
  return `
    <div class="studio-inline-note">
      ${renderModelOriginPill(job.voice_model_origin_kind || "")}
      <span>${escapeHtml(sourceSummary)}</span>
      ${sourceJobId ? `<span class="mono">${escapeHtml(sourceJobId)}</span>` : ""}
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

function canExportEffectRackDraft() {
  return Boolean(
    state.effectExportApiAvailable &&
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
  button.textContent = state.effectExportInFlight ? "正在导出草稿..." : "导出处理版草稿";

  if (state.effectExportInFlight) {
    hint.textContent = "正在请求后端登记处理版草稿；当前仍是 copy-only，不执行真实 DSP/VST。";
  } else if (!state.effectExportApiAvailable) {
    hint.textContent = "后端 API 暂不可用，无法导出处理版草稿。";
  } else if (!state.sourceTrackId || !state.selectedJob?.job_id) {
    hint.textContent = "需要从带 Track 和 Job 的 Studio 版本进入，才能登记处理版草稿。";
  } else if (!state.sourceArtifactId || !state.selectedArtifact?.download_url) {
    hint.textContent = "当前没有可播放 artifact，暂不能导出处理版草稿。";
  } else {
    hint.textContent = "当前导出为 copy-only 草稿：会登记新版本，但暂不执行真实 DSP/VST。";
  }
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
        <div class="studio-effect-slot-note">草稿参数会随导出请求保存到新 artifact metadata；当前导出只复制源音频，不执行真实 DSP/VST。</div>
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

function renderTrackVersionBadges(job = {}) {
  const { isCurrent, isLatest, isHistory, isMaster } = getTrackVersionMeta(job);
  const parts = [];
  if (isCurrent) parts.push('<span class="tag success">当前试听</span>');
  if (isLatest) parts.push('<span class="tag success">最新版本</span>');
  if (isHistory) parts.push('<span class="tag warn">历史版本</span>');
  if (isMaster) parts.push('<span class="tag master">当前主成品</span>');
  return parts.join(" ");
}

function artifactTypeText(type = "") {
  if (type === "cover_master") return "原始翻唱成品";
  if (type === "studio_effect_draft_master") return "处理版草稿";
  return type || "成品版本";
}

function processingModeText(mode = "", artifactType = "") {
  if (mode === "original_cover" || artifactType === "cover_master") return "原始成品";
  if (mode === "copy_only_no_dsp") return "仅登记草稿，未执行真实 DSP/VST";
  return mode || "处理方式未标注";
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
      : "当前没有可试听成品。先回到 Dashboard 完成一个 cover job。";
    return;
  }

  const fileName = basename(artifact?.file_path || "final_master.wav");
  const label = job.voice_name || job.job_id;
  summary.textContent = `当前已载入：${label} / ${fileName} · 状态：${isCompletedStatus(job.status) ? "完成" : job.status || "-"}`;
}

function renderCurrentMasterCard() {
  const card = $("studioCurrentMasterCard");
  if (!card) return;

  const title = $("studioCurrentMasterTitle");
  const summary = $("studioCurrentMasterSummary");
  const meta = $("studioCurrentMasterMeta");
  const openBtn = $("studioCurrentMasterOpenBtn");
  const downloadBtn = $("studioCurrentMasterDownloadBtn");
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
  const typeText = artifactTypeText(master.artifact_type || master.final_artifact_type);
  const modeText = processingModeText(master.processing_mode || master.final_artifact_processing_mode, master.artifact_type || master.final_artifact_type);
  title.textContent = name;
  title.title = name;
  summary.textContent = `${typeText} · ${modeText}`;
  meta.innerHTML = `
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
    title.textContent = "当前不是从 Factory 曲目位进入";
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
    : "当前成品未关联 Factory 曲目";
  summary.textContent = hasFactorySource
    ? `这是 ${voiceLabel} 的翻唱成品，当前载入 ${fileName}，模型来源已跟随成品一起带入 Studio。`
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
  const note = loadJobNote(job.job_id);
  const isMaster = Boolean(job.is_current_master) || isCurrentMasterVersion(job.job_id, artifactId);
  const isCurrent = state.selectedJobId === job.job_id && (!artifactId || artifactId === state.sourceArtifactId);
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
          ${isCurrent ? '<span class="tag success">当前正在播放</span>' : ""}
          ${renderTrackVersionBadges(job)}
        </div>
      </div>
      <div class="studio-history-note ${processingMode === "copy_only_no_dsp" ? "" : "is-empty"}">
        <strong>${escapeHtml(typeText)}</strong>
        <span>${escapeHtml(modeText)}</span>
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
    list.innerHTML = `<div class="studio-resource-empty">当前没有来源 Track，上方保持普通 Studio 兼容模式。</div>`;
    summary.textContent = "只有从 Factory 曲目位进入，才会出现当前曲目的版本账本。";
    updateGlobalLibraryHint();
    syncTrackHistoryDrawer();
    renderCurrentMasterCard();
    return;
  }

  panel.hidden = false;
  updateGlobalLibraryHint();

  if (!state.trackHistory.length) {
    summary.textContent = "当前来源 Track 还没有可回放的 Studio 版本。";
    list.innerHTML = `<div class="studio-resource-empty">这个来源 Track 还没有更多已完成版本，可先回到 Factory 继续创建新版本。</div>`;
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
    const ledger = await getJSON(`/api/tracks/${trackId}/studio-versions?limit=50&offset=0`);
    state.trackHistoryTrackId = trackId;
    state.versionLedgerAvailable = true;
    state.versionLedgerFallbackReason = "";
    state.currentMasterJobId = ledger.current_master_job_id || "";
    state.currentMasterArtifactId = ledger.current_master_artifact_id || "";
    state.currentMasterVersion = ledger.current_master || (ledger.items || []).find(item => item.is_current_master) || null;
    state.studioVersions = ledger.items || [];
    state.trackHistory = state.studioVersions;
    renderTrackHistory();
    return state.trackHistory;
  } catch (error) {
    try {
      const response = await getJSON(`/api/tracks/${trackId}/jobs?limit=50&offset=0`);
      state.trackHistoryTrackId = trackId;
      state.versionLedgerAvailable = false;
      state.versionLedgerFallbackReason = toErrorMessage(error);
      state.currentMasterJobId = response.current_master_job_id || "";
      state.currentMasterArtifactId = response.current_master_artifact_id || "";
      state.currentMasterVersion = response.current_master || null;
      state.studioVersions = [];
      state.trackHistory = sortTrackHistory((response.items || []).filter(isTrackHistoryEligible));
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
      showToast(`Studio 读取当前曲目版本失败：${toErrorMessage(fallbackError)}`, "error");
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
    : `<div class="studio-resource-empty">还没有已完成的翻唱成品。先回到 Dashboard 创建并完成一个 cover job，再进入修音室。</div>`;

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
  $("studioTrackKicker").textContent = "等待选择 cover 成品";
  $("studioTrackTitle").textContent = "请选择一个已完成的翻唱任务";
  $("studioTrackSubline").textContent = "可从右侧资源列表选取，也可在 Dashboard 任务详情里点击“进入 Studio”。";
  $("studioCurrentFileName").textContent = "当前文件：-";
  $("studioCurrentDuration").textContent = "时长：-";
  $("studioCurrentJobId").textContent = "Job：-";
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
  $("studioTechnicalSummary").textContent = "默认收起 job / artifact 路径、长 ID、阶段日志等工程字段。";
  renderTrackHistory();
  renderCurrentMasterCard();
  renderJobNoteEditor(null);
  renderEffectRack();
  drawWaveform();
  setStudioStatus("等待载入成品资源", "warning");
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
  technicalSummary.textContent = "默认收起 job / artifact 路径、长 ID、阶段日志等工程字段。";
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
  });
  if (hasTrackHistory && isHistory && isMaster && !isLatest) {
    versionHint.hidden = false;
    versionHint.textContent = `当前试听不是这个 Track 的最新版本，但它已经被设为当前主成品。最新版本是 ${latestLabel}。`;
  } else if (hasTrackHistory && isLatest && isMaster) {
    versionHint.hidden = false;
    versionHint.textContent = "当前试听既是最新版本，也是这个 Track 的当前主成品。";
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
  $("studioSummaryText").textContent = hasTrackHistory && master?.job_id
    ? `当前围绕任务 ${job.job_id} 的最终成品继续工作。当前主成品是 ${masterLabel}，所用模型${jobModelSourceSummary(job)}。`
    : `当前围绕任务 ${job.job_id} 的最终成品继续工作，可直接下载原始成品；所用模型${jobModelSourceSummary(job)}。`;
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
    showToast("当前主成品已切换，Factory 和 Studio 会同步采用这个版本。", "success");
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
  $("studioCurrentJobId").textContent = `Job：${job.job_id}`;
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
      getJSON(`/api/jobs/${jobId}/stage-logs`).catch(() => ({ stage_logs: [] })),
    ]);

    const artifact = pickPlayableArtifact(jobId, artifactResp.artifacts || [], artifactId);
    state.stageLogs = stageLogsResp.stage_logs || [];
    state.selectedJob = job;
    state.selectedArtifact = artifact;
    renderResourcePicker();
    renderJobMeta(job, artifact);
    syncPlayerUi(job, artifact);
    const context = resolveFactoryContext(job);
    updateQuery(jobId, artifact?.artifact_id || "", context.trackId, context.batchId);
    await refreshTrackHistory(context.trackId, { force: state.trackHistoryTrackId !== context.trackId });
    renderTrackHistory();
    renderArtifactSummary(job, artifact);
  } catch (error) {
    showToast(`Studio 载入任务失败：${toErrorMessage(error)}`, "error");
    setStudioStatus("成品载入失败", "danger");
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
    const response = await getJSON("/api/jobs?job_type=cover&limit=100&offset=0");
    const jobs = (response.items || [])
      .filter(job => job.job_type === "cover" && isCompletedStatus(job.status))
      .sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")));

    state.jobs = jobs;

    const params = new URLSearchParams(window.location.search);
    const requestedJobId = params.get("job_id") || "";
    const requestedArtifactId = params.get("artifact_id") || "";
    const nextJobId = state.selectedJobId || requestedJobId || jobs[0]?.job_id || "";

    if (!jobs.length && !nextJobId) {
      renderResourcePicker();
      await setStudioLibraryCollapsed(false, { immediate: true });
      renderEmptyStudio();
      return;
    }

    renderResourcePicker();
    await setStudioLibraryCollapsed(getStudioLibraryCollapsed(), { immediate: true });
    await loadJob(nextJobId, { artifactId: requestedArtifactId });
  } catch (error) {
    showToast(`Studio 读取成品列表失败：${toErrorMessage(error)}`, "error");
    $("studioResourceCount").textContent = "成品资源读取失败";
    $("studioLibrarySummary").textContent = "成品资源读取失败，请稍后重试。";
    $("studioResourceSelect").innerHTML = `<option value="">资源读取失败</option>`;
    $("studioResourceList").innerHTML = `<div class="studio-resource-empty">成品资源读取失败，请回到 Dashboard 确认至少存在一个已完成的 cover job。</div>`;
    await setStudioLibraryCollapsed(false, { immediate: true });
    renderEmptyStudio();
  }
}

async function refreshEffectRackExportAvailability() {
  try {
    await getJSON("/api/health");
    state.effectExportApiAvailable = true;
  } catch {
    state.effectExportApiAvailable = false;
  }
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
    const payload = await postJSON("/api/studio/effect-rack/export", {
      track_id: state.sourceTrackId,
      source_job_id: state.selectedJob.job_id,
      source_artifact_id: state.sourceArtifactId,
      effect_rack: state.effectRackState,
      export_profile: "studio_balanced",
      note: normalizeJobNote(noteInput?.value || ""),
    });
    showToast("已生成处理版草稿；当前未执行真实 DSP/VST", "success");
    if (payload?.studio_url) {
      window.location.href = payload.studio_url;
      return;
    }
    await loadJob(state.selectedJob.job_id, { artifactId: payload?.artifact_id || state.sourceArtifactId });
  } catch (error) {
    showToast(`处理版草稿导出失败：${effectExportErrorMessage(error)}`, "error");
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

  $("studioJobNoteInput").addEventListener("input", () => {
    persistCurrentJobNote();
  });

  $("studioJobNoteSaveBtn").addEventListener("click", () => {
    persistCurrentJobNote({ showFeedback: true });
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
