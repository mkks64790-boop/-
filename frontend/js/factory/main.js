import { getJSON, postForm, postJSON, toErrorMessage } from "../api.js";
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
  showToast,
  slideToggle,
  stageText,
} from "../ui.js";

const FACTORY_ASSET_COLLAPSED_KEY = "feishark_ui_factory_asset_collapsed";
const FACTORY_LYRICS_COLLAPSED_KEY = "feishark_ui_factory_lyrics_collapsed";
const FACTORY_JOBS_COLLAPSED_KEY = "feishark_ui_factory_jobs_collapsed";
const FACTORY_BATCHES_COLLAPSED_KEY = "feishark_ui_factory_batches_collapsed";
const FACTORY_MODEL_ASSETS_COLLAPSED_KEY = "feishark_ui_factory_model_assets_collapsed";
const FACTORY_REVIEW_ROUTING_COLLAPSED_KEY = "feishark_ui_factory_review_routing_collapsed";
const FACTORY_MATERIAL_LIBRARY_COLLAPSED_KEY = "feishark_ui_factory_material_library_collapsed";
const TRAINING_PRESET_STORAGE_KEY = "feishark.training-preset-key";
const TEST_RECORDS_VISIBLE_KEY = "feishark_ui_show_test_records";
const TEST_RECORDS_EVENT = "feishark:test-records-visibility-changed";
const TRACK_POLL_INTERVAL_MS = 4000;
const RVC_MODELS_PAGE_SIZE = 8;
const FACTORY_REVIEW_ROUTING_VISIBLE_LIMIT = 10;
const SEPARATION_EVAL_LIMIT = 1;
const SEPARATION_EVAL_CLIP_SECONDS = 45;
const SEPARATION_METRIC_KEYS = [
  "peak_db",
  "rms_db",
  "clipping_risk",
  "high_freq_energy_ratio",
  "zero_crossing_rate",
  "noise_risk",
  "suspected_causes",
  "next_step",
];
const SEPARATION_METRIC_LABELS = {
  peak_db: "peak_db",
  rms_db: "rms_db",
  clipping_risk: "clipping_risk",
  high_freq_energy_ratio: "high_freq_energy_ratio",
  zero_crossing_rate: "zero_crossing_rate",
  noise_risk: "noise_risk",
  suspected_causes: "suspected_causes",
  next_step: "next_step",
};
const TRAINING_PRESET_COPY = {
  fast_preview: {
    title: "快速预览",
    description: "先听方向，不追求极致质量。",
  },
  balanced: {
    title: "均衡推荐",
    description: "默认建议，适合普通单文件训练。",
  },
  quality: {
    title: "高质量慢速",
    description: "更耗时，显存和时间风险更高。",
  },
};

const TRACK_STATUS_META = {
  imported: { label: "已导入", className: "pending" },
  draft: { label: "草稿", className: "pending" },
  lyrics_ready: { label: "歌词就绪", className: "success" },
  cover_pending: { label: "翻唱排队", className: "pending" },
  cover_processing: { label: "翻唱处理中", className: "active" },
  cover_ready: { label: "成品就绪", className: "success" },
  cover_failed: { label: "翻唱失败", className: "failed" },
};

const REVIEW_VERDICT_LABELS = {
  unreviewed: "未验收",
  needs_work: "需返工",
  usable: "可用候选",
  release_candidate: "候选成品",
  rejected: "废弃",
};

const REVIEW_VERDICT_CLASS = {
  unreviewed: "pending",
  needs_work: "failed",
  usable: "success",
  release_candidate: "success",
  rejected: "failed",
};

const ARTIFACT_QUALITY_LABELS = {
  reviewable: "Can review",
  needs_manual_quality_check: "Manual QC",
  blocked_auto: "Auto blocked",
};

const ARTIFACT_QUALITY_CLASS = {
  reviewable: "success",
  needs_manual_quality_check: "pending",
  blocked_auto: "failed",
};

const MATERIAL_LIBRARY_WAITING_MESSAGE = "等待地基接口：/api/material-library/summary、/api/material-library/items 暂不可用。";

const MATERIAL_PURPOSE_META = {
  dry_training: {
    label: "干声训练基准",
    badge: "训练/调音基准",
    tone: "success",
  },
  separation_mix: {
    label: "分离评测混音",
    badge: "可做短片段分离评测",
    tone: "success",
  },
  cover_source: {
    label: "翻唱源候选",
    badge: "仅人工确认后用于翻唱",
    tone: "pending",
  },
  isolated: {
    label: "隔离/废弃素材",
    badge: "隔离，不参与自动流程",
    tone: "failed",
  },
  unknown: {
    label: "待人工归类",
    badge: "待人工确认用途",
    tone: "pending",
  },
};

const AUDIT_ACTION_META = {
  track_cover_job_create: "已创建翻唱任务",
  track_cover_job_complete: "成品已登记",
  track_cover_job_fail: "翻唱任务失败",
  track_master_set: "已切换当前主成品",
};

const ACTIVE_STATUSES = new Set([
  "pending",
  "queued",
  "processing",
  "started",
  "running",
  "分离中",
  "修音中",
  "变声中",
  "混音中",
  "切片中",
  "训练中",
]);

const ACTIVE_STAGES = new Set([
  "pending",
  "cover_preflight",
  "cover_split",
  "cover_pitch",
  "cover_voice",
  "cover_mix",
  "train_preprocess",
  "train_pitch_extract",
  "train_feature_extract",
  "train_core",
  "train_index",
  "train_register_model",
]);

const state = {
  batches: [],
  summary: null,
  selectedBatchId: "",
  selectedTrackId: "",
  batchDetail: null,
  trackDetail: null,
  trackJobs: [],
  coverModels: [],
  modelSummary: null,
  engines: null,
  enginesUnavailable: "",
  rvcModels: [],
  rvcModelsTotal: 0,
  rvcModelsOffset: 0,
  rvcModelsUnavailable: "",
  materialLibrary: {
    summary: {},
    items: [],
    unavailable: MATERIAL_LIBRARY_WAITING_MESSAGE,
    loaded: false,
  },
  trainingPresets: [],
  selectedTrainingPresetKey: "balanced",
  trainingEstimate: null,
  trainingTuningUnavailable: "",
  separationSources: [],
  separationRuns: [],
  selectedSeparationRunId: "",
  selectedSeparationRun: null,
  separationRunDetails: {},
  separationDurationRows: [],
  selectedSeparationItemIndex: 0,
  separationUnavailable: "",
  separationPostUnavailable: "后端未开放浏览器执行分离，请用 CLI 执行短片段质检。",
  separationRunInFlight: false,
  reviewRouting: {
    items: [],
    summary: {},
    unavailable: "",
    loaded: false,
  },
  selectedCoverModelId: "",
  trackPollTimer: 0,
  trackPollInFlight: false,
  renderedTrackId: "",
  lyricDraftDirty: false,
  drawerCollapsed: {
    batches: Boolean(loadUiState(FACTORY_BATCHES_COLLAPSED_KEY, true)),
    asset: Boolean(loadUiState(FACTORY_ASSET_COLLAPSED_KEY, false)),
    lyrics: Boolean(loadUiState(FACTORY_LYRICS_COLLAPSED_KEY, true)),
    jobs: Boolean(loadUiState(FACTORY_JOBS_COLLAPSED_KEY, true)),
    modelAssets: Boolean(loadUiState(FACTORY_MODEL_ASSETS_COLLAPSED_KEY, true)),
    reviewRouting: Boolean(loadUiState(FACTORY_REVIEW_ROUTING_COLLAPSED_KEY, true)),
    materialLibrary: Boolean(loadUiState(FACTORY_MATERIAL_LIBRARY_COLLAPSED_KEY, true)),
  },
};

function renderTrackStatusPill(status) {
  const meta = TRACK_STATUS_META[status] || { label: status || "-", className: "pending" };
  return `<span class="status-pill ${meta.className}">${escapeHtml(meta.label)}</span>`;
}

function setFactoryStatus(text, tone = "warning") {
  $("factoryStatusText").textContent = text;
  $("factoryStatusDot").className = `dot ${tone}`;
}

function setSummary(summary = null) {
  $("factoryBatchCount").textContent = String(summary?.batch_count || 0);
  $("factoryTrackCount").textContent = String(summary?.track_count || 0);
  $("factoryLyricCount").textContent = String(summary?.timeline_count || 0);
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

function safeCount(value) {
  const count = Number(value);
  return Number.isFinite(count) ? Math.max(0, count) : 0;
}

function factoryHiddenTestCount(batchResponse = {}) {
  return safeCount(batchResponse.hidden_test_count ?? batchResponse.hidden_test_batch_count)
    + safeCount(state.summary?.hidden_test_track_count)
    + safeCount(state.modelSummary?.hidden_test_model_count ?? state.modelSummary?.hidden_test_count);
}

function renderTestRecordsToggle(hiddenCount = 0) {
  const anchor = $("factoryBatchesDrawer") || $("factoryRvcModelsPanel");
  if (!anchor) return;
  let toggle = document.getElementById("factoryTestRecordsToggle");
  if (!toggle) {
    toggle = document.createElement("div");
    toggle.id = "factoryTestRecordsToggle";
    toggle.className = "test-record-toggle";
    anchor.insertAdjacentElement("beforebegin", toggle);
  }

  const visible = getShowTestRecords();
  toggle.innerHTML = `
    <label class="test-record-toggle-label">
      <input id="factoryShowTestRecords" type="checkbox" ${visible ? "checked" : ""}>
      <span>显示测试记录</span>
    </label>
    <span class="test-record-toggle-note">${
      visible
        ? "当前包含 smoke / stage / test / self_check / playwright 批次和模型。"
        : `默认隐藏测试批次和模型${hiddenCount ? `，已隐藏 ${hiddenCount} 条。` : "。"}`
    }</span>
  `;
  $("factoryShowTestRecords")?.addEventListener("change", event => {
    saveShowTestRecords(event.target.checked);
    refreshAll().catch(() => {});
  });
}

function normalizeEnginePayload(payload = null) {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  const list = payload.engines || payload.items || [];
  const keyed = ["rvc", "uvr", "svc", "svt"]
    .filter(key => payload[key])
    .map(key => ({ engine_key: key, ...payload[key] }));
  return [...list, ...keyed];
}

function engineLabel(engine = {}) {
  const key = String(engine.engine_key || engine.key || engine.name || engine.type || "").toLowerCase();
  if (key.includes("uvr")) return "UVR 分离器";
  if (key.includes("svc") || key.includes("svt")) return "SVC/SVT 备用引擎";
  if (key.includes("rvc")) return "RVC WebUI";
  return engine.label || engine.name || "Local AI Engine";
}

function engineTone(engine = {}) {
  const status = String(engine.status || engine.state || "").toLowerCase();
  if (engine.online === true || engine.configured === true || ["online", "ready", "ok", "available"].includes(status)) return "success";
  if (engine.online === false || engine.configured === false || ["offline", "missing", "error", "unavailable"].includes(status)) return "failed";
  return "pending";
}

function engineSummaryLine(engine = {}) {
  const parts = [];
  if (engine.online != null) parts.push(engine.online ? "在线" : "未在线");
  if (engine.configured != null) parts.push(engine.configured ? "已配置" : "未配置");
  if (engine.model_count != null) parts.push(`模型 ${engine.model_count}`);
  if (engine.external_unregistered_count != null) parts.push(`外部未登记 ${engine.external_unregistered_count}`);
  if (engine.root || engine.root_path || engine.base_url) parts.push(engine.root || engine.root_path || engine.base_url);
  return parts.join(" · ") || engine.message || engine.status || "等待引擎状态";
}

function renderEngineManager() {
  const summary = $("factoryEngineSummary");
  const grid = $("factoryEngineGrid");
  if (!summary || !grid) return;

  if (state.enginesUnavailable) {
    summary.textContent = state.enginesUnavailable;
    grid.innerHTML = ["RVC WebUI", "UVR 分离器", "SVC/SVT 备用引擎"].map(label => `
      <div class="engine-manager-card muted">
        <div class="engine-manager-card-head">
          <strong>${escapeHtml(label)}</strong>
          <span class="status-pill pending">等待地基接口</span>
        </div>
        <div class="engine-manager-line">/api/engines 暂不可用，当前仅保留产品入口。</div>
      </div>
    `).join("");
    return;
  }

  const engines = normalizeEnginePayload(state.engines);
  summary.textContent = engines.length
    ? `已读取 ${engines.length} 个本地 AI 引擎适配器。`
    : "未读取到引擎适配器；等待地基接口返回 RVC / UVR / SVC 状态。";
  grid.innerHTML = engines.length
    ? engines.map(engine => `
      <div class="engine-manager-card">
        <div class="engine-manager-card-head">
          <strong>${escapeHtml(engineLabel(engine))}</strong>
          <span class="status-pill ${engineTone(engine)}">${escapeHtml(engine.status || engine.state || (engine.online ? "online" : "unknown"))}</span>
        </div>
        <div class="engine-manager-line">${escapeHtml(engineSummaryLine(engine))}</div>
        ${engine.root || engine.root_path ? renderPathLine(engine.root || engine.root_path, { subtle: false }) : ""}
      </div>
    `).join("")
    : `
      <div class="engine-manager-card muted">
        <div class="engine-manager-card-head">
          <strong>RVC / UVR / SVC</strong>
          <span class="status-pill pending">等待扫描</span>
        </div>
        <div class="engine-manager-line">未收到引擎状态，不假定任何引擎可用。</div>
      </div>
    `;
}

function shortToken(value = "", head = 12) {
  const text = String(value || "");
  return text.length > head ? `${text.slice(0, head)}...` : text;
}

function reviewSummaryFromItem(item = {}) {
  return item.review_summary
    || item.listening_review_summary
    || item.final_artifact_review_summary
    || {};
}

function qualitySummaryFromItem(item = {}) {
  return item.quality_summary
    || item.final_artifact_quality_summary
    || {};
}

function normalizeReviewRoutingPayload(payload = {}) {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray(payload.items)
      ? payload.items
      : Array.isArray(payload.artifacts)
        ? payload.artifacts
        : [];
  const items = rawItems.map(item => {
    const summary = reviewSummaryFromItem(item);
    const qualitySummary = qualitySummaryFromItem(item);
    const verdict = item.review_verdict || summary.verdict || "unreviewed";
    const qualityVerdict = item.quality_verdict || qualitySummary.quality_verdict || qualitySummary.verdict || "needs_manual_quality_check";
    const qualityFlags = Array.isArray(item.quality_flags)
      ? item.quality_flags
      : Array.isArray(qualitySummary.quality_flags)
        ? qualitySummary.quality_flags
        : Array.isArray(qualitySummary.flags)
          ? qualitySummary.flags
          : [];
    const jobId = item.job_id || "";
    const artifactId = item.artifact_id || item.final_artifact_id || "";
    const studioUrl = item.studio_url || (jobId ? `/studio?${new URLSearchParams({
      job_id: jobId,
      ...(artifactId ? { artifact_id: artifactId } : {}),
    }).toString()}` : "");
    return {
      ...item,
      reviewSummary: summary,
      qualitySummary,
      verdict,
      qualityVerdict,
      qualityFlags,
      qualityReason: item.quality_reason || qualitySummary.quality_reason || qualitySummary.reason || "",
      jobId,
      artifactId,
      title: item.file_name || item.name || basename(item.file_path || item.download_url || jobId),
      studioUrl,
      downloadUrl: item.download_url || item.final_artifact_download_url || (
        jobId && artifactId ? `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactId)}/download` : ""
      ),
      createdAt: item.created_at || item.updated_at || summary.reviewed_at || "",
    };
  });
  const summary = payload.summary || {};
  const count = key => Number(summary[key] ?? items.filter(item => item.verdict === key).length) || 0;
  return {
    items,
    summary: {
      total: Number(summary.total ?? items.length) || 0,
      unreviewed: count("unreviewed"),
      needs_work: count("needs_work"),
      usable: count("usable"),
      release_candidate: count("release_candidate"),
      rejected: count("rejected"),
      quality_reviewable: Number(summary.quality_reviewable ?? summary.quality?.reviewable ?? items.filter(item => item.qualityVerdict === "reviewable").length) || 0,
      quality_manual_check: Number(summary.quality_manual_check ?? summary.quality_needs_manual_quality_check ?? summary.quality?.needs_manual_quality_check ?? items.filter(item => item.qualityVerdict === "needs_manual_quality_check").length) || 0,
      quality_blocked: Number(summary.quality_blocked ?? summary.quality_blocked_auto ?? summary.quality?.blocked_auto ?? items.filter(item => item.qualityVerdict === "blocked_auto").length) || 0,
    },
  };
}

function reviewRoutingUnavailableMessage(error) {
  return `验收路由读取失败：${toErrorMessage(error)}；不伪造候选成品。`;
}

function renderReviewBadge(verdict = "unreviewed") {
  return `<span class="status-pill ${REVIEW_VERDICT_CLASS[verdict] || "pending"}">${escapeHtml(REVIEW_VERDICT_LABELS[verdict] || verdict)}</span>`;
}

function renderQualityBadge(qualityVerdict = "needs_manual_quality_check") {
  return `<span class="status-pill ${ARTIFACT_QUALITY_CLASS[qualityVerdict] || "pending"}">${escapeHtml(ARTIFACT_QUALITY_LABELS[qualityVerdict] || qualityVerdict)}</span>`;
}

function renderFactoryReviewRoutingItem(item = {}) {
  const durationText = item.qualitySummary?.duration_sec != null ? `${item.qualitySummary.duration_sec}s` : "duration ?";
  const qualityFlags = item.qualityFlags?.length ? item.qualityFlags.join(", ") : (item.qualityReason || "no quality flags");
  const title = item.title || item.jobId || "未命名成品";
  return `
    <article class="factory-item factory-review-routing-item">
      <div class="factory-item-title">
        <strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong>
        <span class="factory-review-badges">${renderQualityBadge(item.qualityVerdict)}${renderReviewBadge(item.verdict)}</span>
      </div>
      <div class="factory-item-meta">
        <span class="mono" title="${escapeHtml(item.jobId || "-")}">Job ${escapeHtml(shortToken(item.jobId || "-"))}</span>
        <span class="mono" title="${escapeHtml(item.artifactId || "-")}">Artifact ${escapeHtml(shortToken(item.artifactId || "-"))}</span>
        <span title="${escapeHtml(qualityFlags)}">Quality ${escapeHtml(durationText)}</span>
        <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
      </div>
      <div class="panel-actions">
        ${item.studioUrl ? `<button class="primary-btn warm" type="button" data-studio-url="${escapeHtml(item.studioUrl)}">进入录音棚</button>` : ""}
        ${item.downloadUrl ? `<button class="ghost-btn" type="button" data-download-url="${escapeHtml(item.downloadUrl)}">下载</button>` : ""}
        ${item.jobId ? `<a class="ghost-btn" href="/#taskCenter" title="${escapeHtml(item.jobId)}">查看来源 job</a>` : ""}
      </div>
    </article>
  `;
}

function renderFactoryReviewRoutingGroup(elementId, summaryId, items, emptyText) {
  const list = $(elementId);
  const summary = $(summaryId);
  if (!list || !summary) return;
  summary.textContent = `${items.length} 条`;
  list.innerHTML = items.length
    ? items.slice(0, FACTORY_REVIEW_ROUTING_VISIBLE_LIMIT).map(renderFactoryReviewRoutingItem).join("")
    : `<div class="detail-empty inline">${escapeHtml(emptyText)}</div>`;
}

function renderFactoryReviewRouting() {
  const panel = $("factoryReviewRoutingPanel");
  if (!panel) return;
  const { items, summary, unavailable, loaded } = state.reviewRouting;
  const actionableItems = items.filter(item => item.qualityVerdict !== "blocked_auto");
  $("factoryReviewRoutingMetrics").innerHTML = `
    <span>Can review: ${loaded && !unavailable ? Number(summary.quality_reviewable || 0) : "-"}</span>
    <span>Manual QC: ${loaded && !unavailable ? Number(summary.quality_manual_check || 0) : "-"}</span>
    <span>Auto blocked: ${loaded && !unavailable ? Number(summary.quality_blocked || 0) : "-"}</span>
  `;
  $("factoryReviewRoutingSummary").textContent = unavailable
    ? unavailable
    : loaded
      ? `Quality gate ${summary.total || items.length || 0} items: ${summary.quality_reviewable || 0} reviewable, ${summary.quality_manual_check || 0} manual QC, ${summary.quality_blocked || 0} blocked.`
      : "正在读取真实 /api/reviews/artifacts...";

  if (unavailable) {
    ["factoryReleaseCandidateList", "factoryNeedsWorkList", "factoryUnreviewedList"].forEach(id => {
      $(id).innerHTML = `<div class="detail-empty inline">${escapeHtml(unavailable)}</div>`;
    });
    return;
  }

  const releaseCandidates = actionableItems.filter(item => item.verdict === "release_candidate" || item.verdict === "usable");
  const needsWork = actionableItems.filter(item => item.verdict === "needs_work");
  const unreviewed = actionableItems.filter(item => item.verdict === "unreviewed");
  renderFactoryReviewRoutingGroup("factoryReleaseCandidateList", "factoryReleaseCandidateSummary", releaseCandidates, "当前没有候选成品。");
  renderFactoryReviewRoutingGroup("factoryNeedsWorkList", "factoryNeedsWorkSummary", needsWork, "当前没有需返工成品。");
  renderFactoryReviewRoutingGroup("factoryUnreviewedList", "factoryUnreviewedSummary", unreviewed, "当前没有未验收成品。");
}

async function loadFactoryReviewRouting() {
  try {
    const payload = await getJSON("/api/reviews/artifacts?limit=100");
    const normalized = normalizeReviewRoutingPayload(payload);
    state.reviewRouting.items = normalized.items;
    state.reviewRouting.summary = normalized.summary;
    state.reviewRouting.unavailable = "";
    state.reviewRouting.loaded = true;
  } catch (error) {
    state.reviewRouting.items = [];
    state.reviewRouting.summary = {};
    state.reviewRouting.unavailable = reviewRoutingUnavailableMessage(error);
    state.reviewRouting.loaded = true;
  }
  renderFactoryReviewRouting();
}

function normalizeMaterialLibrarySummary(payload = null) {
  if (!payload) return {};
  if (Array.isArray(payload)) return { total: payload.length };
  return {
    ...payload,
    ...(payload.summary && typeof payload.summary === "object" ? payload.summary : {}),
  };
}

function normalizeStringList(value) {
  if (Array.isArray(value)) return value.map(item => String(item || "").trim()).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function normalizeMaterialLibraryItems(payload = null) {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.materials)
        ? payload.materials
        : Array.isArray(payload?.sources)
          ? payload.sources
          : [];
  return items.map((item, index) => {
    const path = item.path || item.file_path || item.source_path || item.local_path || "";
    return {
      ...item,
      material_id: item.material_id || item.id || item.source_id || path || `material_${index}`,
      title: item.title || item.name || item.filename || basename(path) || `素材 ${index + 1}`,
      path,
      duration_seconds: item.duration_seconds ?? item.duration_sec ?? item.duration ?? item.seconds,
      source_group: item.source_group || item.library_key || item.library || item.root_key || "",
      material_role: item.material_role || item.role || item.type || "",
      material_profile: item.material_profile || item.profile || "",
      license_status: item.license_status || item.license || item.authorization_status || "",
      training_candidate_allowed: optionalBooleanValue(item.training_candidate_allowed),
      separation_eval_allowed: optionalBooleanValue(item.separation_eval_allowed),
      risk_flags: normalizeStringList(item.risk_flags || item.flags || item.blockers),
      route_hint: item.training_route_hint || item.route_hint || item.next_step || item.description || "",
      quarantine_reason: item.quarantine_reason || item.exclusion_reason || item.reject_reason || item.reason || "",
    };
  });
}

function materialLibraryPurpose(item = {}) {
  const text = [
    item.purpose,
    item.usage,
    item.material_purpose,
    item.material_usage,
    item.library_purpose,
    item.material_role,
    item.material_profile,
    item.source_group,
    item.status,
    item.state,
  ].filter(Boolean).join(" ").toLowerCase();
  if (item.separation_eval_allowed === true) return "separation_mix";
  if (item.training_candidate_allowed === true) return "dry_training";
  if (/cover_source|cover source|cover-source|翻唱源/.test(text)) return "cover_source";
  if (/dry|vocal|training|baseline|sonovox/.test(text)) return "dry_training";
  if (/separation|eval|clean_song|project_input|mix/.test(text) && !/dj|finished|master/.test(text)) return "separation_mix";
  if (/isolat|exclude|quarantine|discard|reject|blocked|deprecated|legacy|dj|finished|master|risk/.test(text)) return "isolated";
  if (item.risk_flags?.length || item.quarantine_reason) return "isolated";
  return "unknown";
}

function materialLibraryCount(summary = {}, keys = [], fallback = 0) {
  const buckets = [
    summary,
    summary.counts,
    summary.totals,
    summary.by_purpose,
    summary.purpose_counts,
    summary.by_usage,
    summary.usage_counts,
    summary.by_role,
    summary.role_counts,
  ].filter(bucket => bucket && typeof bucket === "object");
  for (const bucket of buckets) {
    for (const key of keys) {
      const value = bucket[key];
      if (Array.isArray(value)) return value.length;
      const number = Number(value);
      if (Number.isFinite(number)) return number;
    }
  }
  return fallback;
}

function materialLibraryStats() {
  const { summary, items } = state.materialLibrary;
  const purposeCounts = items.reduce((counts, item) => {
    const purpose = materialLibraryPurpose(item);
    counts[purpose] = (counts[purpose] || 0) + 1;
    return counts;
  }, {});
  return {
    total: materialLibraryCount(summary, ["total", "total_items", "item_count", "material_count"], items.length),
    dryTraining: materialLibraryCount(summary, ["dry_training", "dry_vocal", "dry_vocal_count", "training_baseline", "training_candidate", "training_candidates", "training_candidate_count"], purposeCounts.dry_training || 0),
    separationMix: materialLibraryCount(summary, ["separation_mix", "separation_eval", "separation_eval_candidate", "separation_eval_candidates", "separation_candidates", "separation_benchmark_count"], purposeCounts.separation_mix || 0),
    coverSource: materialLibraryCount(summary, ["cover_source", "cover_sources", "cover_source_count", "cover_source_candidate", "cover_source_candidates"], purposeCounts.cover_source || 0),
    isolated: materialLibraryCount(summary, ["isolated", "excluded", "excluded_candidates", "quarantine", "quarantined", "quarantined_count", "discarded", "rejected"], purposeCounts.isolated || 0),
  };
}

function renderMaterialLibraryItem(item = {}) {
  const purpose = materialLibraryPurpose(item);
  const meta = MATERIAL_PURPOSE_META[purpose] || MATERIAL_PURPOSE_META.unknown;
  const reason = item.quarantine_reason || item.risk_flags?.join(" / ") || item.route_hint || "";
  return `
    <article class="factory-material-item">
      <div class="factory-item-title">
        <strong title="${escapeHtml(item.title)}">${escapeHtml(item.title || "素材")}</strong>
        <span class="status-pill ${meta.tone}">${escapeHtml(meta.badge)}</span>
      </div>
      <div class="factory-item-meta">
        <span>${escapeHtml(meta.label)}</span>
        ${item.duration_seconds != null ? `<span>${escapeHtml(item.duration_seconds)} 秒</span>` : ""}
        ${item.source_group ? `<span>${escapeHtml(item.source_group)}</span>` : ""}
        ${item.material_role ? `<span>${escapeHtml(separationMaterialRoleLabel(item.material_role))}</span>` : ""}
        ${item.license_status ? `<span>${escapeHtml(item.license_status)}</span>` : ""}
        ${item.material_id ? `<span class="mono">${escapeHtml(shortToken(item.material_id, 18))}</span>` : ""}
      </div>
      ${reason ? `<p>${escapeHtml(reason)}</p>` : ""}
      ${item.path ? renderPathLine(item.path, { subtle: true }) : ""}
    </article>
  `;
}

function renderMaterialLibrary() {
  const summaryElement = $("factoryMaterialLibrarySummary");
  const statsElement = $("factoryMaterialLibraryStats");
  const list = $("factoryMaterialLibraryList");
  if (!summaryElement || !statsElement || !list) return;

  const { summary, items, unavailable, loaded } = state.materialLibrary;
  const hasSummary = Object.keys(summary || {}).length > 0;
  const stats = materialLibraryStats();
  const hasData = hasSummary || items.length > 0;
  summaryElement.textContent = hasData
    ? `授权素材库只读：共 ${stats.total} 个，训练基准 ${stats.dryTraining} 个，翻唱源 ${stats.coverSource} 个，分离评测混音 ${stats.separationMix} 个，隔离/废弃 ${stats.isolated} 个。${unavailable ? ` ${unavailable}` : ""}`
    : loaded
      ? (unavailable || MATERIAL_LIBRARY_WAITING_MESSAGE)
      : "等待 /api/material-library/summary 和 /api/material-library/items，只读展示素材去向。";

  statsElement.innerHTML = [
    ["全部素材", stats.total],
    ["干声训练基准", stats.dryTraining],
    ["翻唱源候选", stats.coverSource],
    ["分离评测混音", stats.separationMix],
    ["隔离/废弃素材", stats.isolated],
  ].map(([label, value]) => `
    <div class="factory-material-stat">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");

  list.innerHTML = items.length
    ? items.slice(0, 8).map(renderMaterialLibraryItem).join("")
    : `<div class="detail-empty inline">${escapeHtml(unavailable || MATERIAL_LIBRARY_WAITING_MESSAGE)} 新接口接入前，下方“分离评测候选”仍读取 Stage52 /api/separation/eval/sources。</div>`;
}

async function loadMaterialLibrary() {
  const [summaryResult, itemsResult] = await Promise.allSettled([
    getJSON("/api/material-library/summary"),
    getJSON("/api/material-library/items"),
  ]);
  const unavailable = [];

  if (summaryResult.status === "fulfilled") {
    state.materialLibrary.summary = normalizeMaterialLibrarySummary(summaryResult.value);
  } else {
    state.materialLibrary.summary = {};
    unavailable.push("/api/material-library/summary");
  }

  if (itemsResult.status === "fulfilled") {
    state.materialLibrary.items = normalizeMaterialLibraryItems(itemsResult.value);
  } else {
    state.materialLibrary.items = [];
    unavailable.push("/api/material-library/items");
  }

  state.materialLibrary.unavailable = unavailable.length
    ? `等待地基接口：${unavailable.join("、")} 暂不可用。`
    : "";
  state.materialLibrary.loaded = true;
  renderMaterialLibrary();
}

function optionalBooleanValue(value) {
  if (value === true || value === false) return value;
  if (value === "true" || value === "1") return true;
  if (value === "false" || value === "0") return false;
  return null;
}

function normalizeSeparationSources(payload = null) {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.sources)
      ? payload.sources
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.candidates)
          ? payload.candidates
          : [];
  return items.map((item, index) => ({
    ...item,
    source_id: item.source_id || item.id || item.path || item.file_path || `source_${index}`,
    title: item.title || item.name || item.filename || basename(item.path || item.file_path || ""),
    duration_seconds: item.duration_seconds ?? item.duration ?? item.seconds,
    source_group: item.source_group || "unknown",
    library_key: item.library_key || "",
    material_role: item.material_role || item.role || "unknown",
    material_profile: item.material_profile || item.profile || "needs_manual_review",
    training_route_hint: item.training_route_hint || item.next_step || "",
    license_status: item.license_status || "",
    risk_flags: Array.isArray(item.risk_flags) ? item.risk_flags : [],
    separation_eval_allowed: optionalBooleanValue(item.separation_eval_allowed),
    training_candidate_allowed: optionalBooleanValue(item.training_candidate_allowed),
  }));
}

function normalizeSeparationRuns(payload = null) {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.runs)
      ? payload.runs
      : Array.isArray(payload?.items)
        ? payload.items
        : [];
  return items.map((item, index) => ({
    ...item,
    run_id: item.run_id || item.id || item.eval_run_id || `run_${index}`,
  }));
}

function separationRunId(run = {}) {
  return run.run_id || run.id || run.eval_run_id || "";
}

function separationRunStatus(run = {}) {
  return run.status || run.state || run.result || "unknown";
}

function separationRunItems(run = {}) {
  const manifestItems = Array.isArray(run.manifest?.items) ? run.manifest.items : [];
  const directItems = Array.isArray(run.items) ? run.items : [];
  const reports = Array.isArray(run.reports) ? run.reports : [];
  const items = manifestItems.length ? manifestItems : directItems;
  if (items.length) {
    return items.map((item, index) => ({
      ...item,
      report: item.report || reports[index] || item.quality_report || {},
      item_index: Number(item.item_index ?? item.index ?? index),
    }));
  }
  if (reports.length) {
    return reports.map((report, index) => ({
      ok: report.ok,
      report,
      products: report.products || {},
      source: { path: report.source_path || "" },
      item_index: index,
    }));
  }
  return [];
}

function selectedSeparationItem(run = {}) {
  const items = separationRunItems(run);
  if (!items.length) return null;
  const index = Math.min(Math.max(0, Number(state.selectedSeparationItemIndex) || 0), items.length - 1);
  return items[index] || items[0];
}

function separationItemTitle(item = {}, index = 0) {
  return item.title
    || item.source?.file_name
    || basename(item.source?.path || item.source_path || item.report?.source_path || item.item_dir || "")
    || `item ${index + 1}`;
}

function separationRiskTone(value = "") {
  const key = String(value || "").toLowerCase();
  if (["low", "pass", "ok", "safe", "false", "none"].includes(key)) return "success";
  if (["high", "fail", "danger", "true", "yes"].includes(key)) return "failed";
  return "pending";
}

function firstString(...values) {
  return values.find(value => typeof value === "string" && value.trim()) || "";
}

function safeAudioUrl(value = "") {
  const url = String(value || "").trim();
  if (!url) return "";
  if (url.startsWith("/") || url.startsWith("http://") || url.startsWith("https://")) return url;
  return "";
}

function artifactUrl(run = {}, role = "") {
  const artifacts = run.artifacts || run.artifact_urls || run.outputs || run.files || run.products || {};
  const roleArtifact = artifacts?.[role] || artifacts?.[`${role}_audio`] || artifacts?.[`${role}_path`] || {};
  if (typeof roleArtifact === "string") return safeAudioUrl(roleArtifact);
  return safeAudioUrl(firstString(
    run[`${role}_url`],
    run[`${role}_download_url`],
    run[`${role}_file_url`],
    run[`${role}_audio_url`],
    roleArtifact.url,
    roleArtifact.download_url,
    roleArtifact.file_url,
    roleArtifact.audio_url,
  ));
}

function separationAudioUrl(run = {}, role = "") {
  const item = selectedSeparationItem(run);
  const target = item || run;
  if (role === "original") {
    return safeAudioUrl(firstString(
      target.original_url,
      target.original_download_url,
      target.excerpt_url,
      target.excerpt_download_url,
      target.input_url,
      target.input_download_url,
      artifactUrl(target, "original"),
      artifactUrl(target, "original_excerpt"),
      artifactUrl(target, "excerpt"),
      artifactUrl(target, "input"),
      artifactUrl(run, "original"),
      artifactUrl(run, "original_excerpt"),
    ));
  }
  if (role === "vocal") return artifactUrl(target, "vocal") || artifactUrl(target, "vocals") || artifactUrl(run, "vocal");
  if (role === "instrumental") return artifactUrl(target, "instrumental") || artifactUrl(target, "accompaniment") || artifactUrl(target, "instrument") || artifactUrl(run, "instrumental");
  return "";
}

function qualityReport(run = {}) {
  const item = selectedSeparationItem(run);
  return item?.report || run.quality_report || run.metrics || run.report || run.analysis || {};
}

function metricValue(run = {}, key = "") {
  const report = qualityReport(run);
  if (report[key] != null) return report[key];
  if (report.metrics?.[key] != null) return report.metrics[key];
  if (report.metrics && typeof report.metrics === "object") {
    const values = Object.entries(report.metrics)
      .map(([name, metrics]) => metrics && typeof metrics === "object" && metrics[key] != null ? `${name}: ${metrics[key]}` : "")
      .filter(Boolean);
    if (values.length) return values;
  }
  if (run[key] != null) return run[key];
  return null;
}

function productLocalPath(run = {}, role = "") {
  const item = selectedSeparationItem(run);
  const report = item?.report || {};
  const products = item?.products || report.products || {};
  const keys = role === "original"
    ? ["original", "original_excerpt", "excerpt", "input"]
    : role === "vocal"
      ? ["vocal", "vocals"]
      : ["instrumental", "accompaniment", "instrument"];
  for (const key of keys) {
    if (typeof products[key] === "string" && products[key]) return products[key];
  }
  return "";
}

function durationMismatchLine(run = {}) {
  const metrics = qualityReport(run).metrics || {};
  const durations = Object.entries(metrics)
    .map(([name, item]) => ({ name, duration: Number(item?.duration_seconds) }))
    .filter(item => Number.isFinite(item.duration) && item.duration > 0);
  if (durations.length < 2) return "";
  const min = Math.min(...durations.map(item => item.duration));
  const max = Math.max(...durations.map(item => item.duration));
  if (max - min < 1) return "";
  return durations.map(item => `${item.name}: ${item.duration}s`).join("；");
}

function firstSeparationReport(run = {}) {
  const item = separationRunItems(run)[0] || selectedSeparationItem(run);
  return item?.report || {};
}

function durationRowFromRun(run = {}) {
  const runId = separationRunId(run);
  const report = firstSeparationReport(run);
  const metrics = report.metrics || {};
  const originalDuration = Number(metrics.original_excerpt?.duration_seconds ?? metrics.original?.duration_seconds ?? 0);
  const vocalDuration = Number(metrics.vocal?.duration_seconds ?? metrics.vocals?.duration_seconds ?? 0);
  const instrumentalDuration = Number(metrics.instrumental?.duration_seconds ?? metrics.accompaniment?.duration_seconds ?? 0);
  const computedRatio = originalDuration > 0
    ? Math.min(vocalDuration || originalDuration, instrumentalDuration || originalDuration) / originalDuration
    : null;
  const durationRatio = Number(report.duration_ratio ?? run.duration_ratio ?? computedRatio);
  const risk = report.duration_mismatch_risk || run.duration_mismatch_risk || (durationRatio < 0.95 ? "high" : "pass");
  const blockTraining = Boolean(run.manifest?.block_training ?? run.block_training ?? report.block_training ?? risk === "high");
  return {
    runId,
    clipSeconds: Number(run.manifest?.clip_seconds ?? run.clip_seconds ?? 0),
    originalDuration,
    vocalDuration,
    instrumentalDuration,
    durationRatio,
    risk,
    blockTraining,
  };
}

function formatDuration(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? `${number.toFixed(number % 1 ? 3 : 0)}s` : "-";
}

function formatRatio(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(4) : "-";
}

function currentUnlockRun() {
  return state.selectedSeparationRun
    || state.separationRunDetails[state.selectedSeparationRunId]
    || state.separationRunDetails[separationRunId(state.separationRuns[0] || {})]
    || null;
}

function formatMetricValue(value) {
  if (value == null || value === "") return "等待数据";
  if (Array.isArray(value)) return value.length ? value.join("；") : "无";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function renderSeparationUnlockDashboard() {
  const card = $("factorySeparationUnlockCard");
  const status = $("factorySeparationUnlockStatus");
  const reason = $("factorySeparationUnlockReason");
  const grid = $("factorySeparationUnlockGrid");
  const note = $("factorySeparationUnlockNote");
  if (!card || !status || !reason || !grid || !note) return;

  const run = currentUnlockRun();
  const row = run ? durationRowFromRun(run) : null;
  const riskHigh = row?.risk === "high" || Number(row?.durationRatio) < 0.95;
  const locked = Boolean(row?.blockTraining || riskHigh);
  card.classList.toggle("is-locked", locked);
  card.classList.toggle("is-unlocked", Boolean(row && !locked));
  status.textContent = locked ? "训练锁定" : "可尝试短训练冒烟";
  reason.textContent = row
    ? locked
      ? `原因：${riskHigh ? "duration mismatch high" : "BLOCK_TRAINING=true"}`
      : "原因：三段对照均通过；仍需短训练 smoke 另行验收。"
    : "等待真实 run 指标。";
  grid.innerHTML = row
    ? `
      <div><span>run_id</span><strong class="mono">${escapeHtml(row.runId)}</strong></div>
      <div><span>duration_ratio</span><strong class="${Number(row.durationRatio) >= 0.95 ? "success" : "failed"}">${escapeHtml(formatRatio(row.durationRatio))}</strong></div>
      <div><span>BLOCK_TRAINING</span><strong class="${row.blockTraining ? "failed" : "success"}">${row.blockTraining ? "true" : "false"}</strong></div>
    `
    : `
      <div><span>run_id</span><strong>-</strong></div>
      <div><span>duration_ratio</span><strong>-</strong></div>
      <div><span>BLOCK_TRAINING</span><strong>-</strong></div>
    `;
  note.textContent = "BLOCK_TRAINING=false 只代表分离时长门槛通过；恢复训练还需要短训练 smoke 另行验收。";
}

function renderSeparationDurationTable() {
  const summary = $("factorySeparationDurationSummary");
  const body = $("factorySeparationDurationTable");
  if (!summary || !body) return;

  const rows = [...state.separationDurationRows]
    .filter(row => row.runId)
    .sort((a, b) => (a.clipSeconds || 999) - (b.clipSeconds || 999) || a.runId.localeCompare(b.runId));
  const clipSet = new Set(rows.map(row => Number(row.clipSeconds)));
  summary.textContent = rows.length
    ? `已读取 ${rows.length} 条真实 duration 证据；clip 覆盖：${[...clipSet].filter(Boolean).join(" / ")} 秒。`
    : "等待真实 run duration 证据。";
  body.innerHTML = rows.length
    ? rows.map(row => {
      const pass = Number(row.durationRatio) >= 0.95 && row.risk !== "high";
      return `
        <tr class="${pass ? "is-pass" : "is-risk"}">
          <td class="mono">${escapeHtml(row.runId)}</td>
          <td>${escapeHtml(row.clipSeconds || "-")}s</td>
          <td>${escapeHtml(formatDuration(row.originalDuration))}</td>
          <td>${escapeHtml(formatDuration(row.vocalDuration))}</td>
          <td>${escapeHtml(formatDuration(row.instrumentalDuration))}</td>
          <td><strong>${escapeHtml(formatRatio(row.durationRatio))}</strong></td>
          <td><span class="status-pill ${pass ? "success" : "failed"}">${escapeHtml(row.risk || (pass ? "pass" : "high"))}</span></td>
        </tr>
      `;
    }).join("")
    : `<tr><td colspan="7">等待真实 run duration 证据。</td></tr>`;
}

function separationSourceGroupLabel(source = {}) {
  const labels = {
    sonovox_demo: "Sonovox 干声库",
    authorized_dry_vocal: "授权干声库",
    project_input: "项目输入",
    legacy_test_music: "历史测试音乐",
    legacy_fallback: "历史兜底目录",
  };
  return labels[source.source_group] || source.source_group || "未知来源";
}

function separationMaterialRoleLabel(role = "") {
  const labels = {
    dry_vocal: "干声",
    backing: "伴奏",
    clean_song: "干净歌曲",
    cover_source: "翻唱源候选",
    finished_mix: "成品混音",
    dj_mix: "DJ/混音",
    unknown: "用途未确认",
  };
  return labels[role] || role || "用途未确认";
}

function renderSeparationCandidates() {
  const summary = $("factorySeparationCandidatesSummary");
  const list = $("factorySeparationCandidatesList");
  if (!summary || !list) return;

  const separationAllowed = state.separationSources.filter(source => source.separation_eval_allowed === true).length;
  const trainingAllowed = state.separationSources.filter(source => source.training_candidate_allowed === true).length;
  summary.textContent = state.separationSources.length
    ? `已读取 ${state.separationSources.length} 个授权/质检素材；可分离 ${separationAllowed} 个，训练基准 ${trainingAllowed} 个。`
    : state.separationUnavailable || "等待地基接口";
  list.innerHTML = state.separationSources.length
    ? state.separationSources.slice(0, 5).map(source => `
      <div class="separation-candidate-item">
        <strong>${escapeHtml(source.title || "候选音频")}</strong>
        <div class="factory-item-meta">
          ${source.duration_seconds != null ? `<span>${escapeHtml(source.duration_seconds)} 秒</span>` : ""}
          <span>${escapeHtml(separationSourceGroupLabel(source))}</span>
          <span>${escapeHtml(separationMaterialRoleLabel(source.material_role))}</span>
          <span class="status-pill ${source.separation_eval_allowed === true ? "success" : "pending"}">${source.separation_eval_allowed === true ? "可跑 UVR 短片段" : "不跑分离"}</span>
          ${source.training_candidate_allowed === true ? `<span class="status-pill success">训练/调音基准</span>` : ""}
          ${source.risk_flags.length ? `<span class="status-pill failed">风险：${escapeHtml(source.risk_flags.join(" / "))}</span>` : ""}
          ${source.source_id ? `<span class="mono">${escapeHtml(source.source_id)}</span>` : ""}
        </div>
        ${source.training_route_hint ? `<small>${escapeHtml(source.training_route_hint)}</small>` : ""}
        ${source.path || source.file_path ? renderPathLine(source.path || source.file_path, { subtle: true }) : ""}
      </div>
    `).join("")
    : `<div class="detail-empty inline">等待地基接口：授权/质检素材暂不可用；不会默认扫描历史 D 盘测试音乐。</div>`;
}

function renderSeparationRuns() {
  const summary = $("factorySeparationRunsSummary");
  const list = $("factorySeparationRunsList");
  if (!summary || !list) return;

  summary.textContent = state.separationRuns.length
    ? `已读取 ${state.separationRuns.length} 条最近 eval run。`
    : "暂无 eval run";
  list.innerHTML = state.separationRuns.length
    ? state.separationRuns.map(run => {
      const runId = separationRunId(run);
      const active = runId === state.selectedSeparationRunId;
      const risk = metricValue(run, "noise_risk") || run.noise_risk || "";
      return `
        <button class="separation-run-item ${active ? "is-active" : ""}" type="button" data-separation-run="${escapeHtml(runId)}">
          <span>
            <strong>${escapeHtml(run.title || run.source_title || runId || "eval run")}</strong>
            <small>${escapeHtml(formatDateTime(run.created_at || run.updated_at || run.finished_at || ""))}</small>
          </span>
          <span class="status-pill ${separationRiskTone(risk || separationRunStatus(run))}">${escapeHtml(risk || separationRunStatus(run))}</span>
        </button>
      `;
    }).join("")
    : `<div class="detail-empty inline">暂无 eval run。地基完成后会显示最近的短片段质检记录。</div>`;
}

function renderSeparationPlayers() {
  const summary = $("factorySeparationPlayersSummary");
  const itemsList = $("factorySeparationItemsList");
  const grid = $("factorySeparationPlayersGrid");
  if (!summary || !grid) return;

  const run = state.selectedSeparationRun || {};
  const runId = separationRunId(run);
  if (!runId) {
    summary.textContent = "选择一个 run 后试听原曲、人声、伴奏。";
    if (itemsList) itemsList.innerHTML = "";
    grid.innerHTML = `<div class="detail-empty inline separation-empty-state">尚未选择真实 run，暂无三轨结果。</div>`;
    return;
  }

  const items = separationRunItems(run);
  const selectedItem = selectedSeparationItem(run);
  if (itemsList) {
    itemsList.innerHTML = items.length > 1
      ? items.map((item, index) => `
        <button class="separation-item-chip ${index === state.selectedSeparationItemIndex ? "is-active" : ""}" type="button" data-separation-item-index="${index}">
          ${escapeHtml(separationItemTitle(item, index))}
        </button>
      `).join("")
      : "";
  }

  const tracks = [
    { key: "original", title: "原曲 excerpt", allowDownload: false },
    { key: "vocal", title: "分离人声 vocal", allowDownload: true },
    { key: "instrumental", title: "分离伴奏 instrumental", allowDownload: true },
  ];
  summary.textContent = `当前 run：${runId}${selectedItem ? ` / ${separationItemTitle(selectedItem, state.selectedSeparationItemIndex)}` : ""}。播放器不会自动播放。`;
  grid.innerHTML = tracks.map(track => {
    const url = separationAudioUrl(run, track.key);
    const localPath = productLocalPath(run, track.key);
    return `
      <div class="separation-player-card">
        <div class="separation-player-head">
          <strong>${escapeHtml(track.title)}</strong>
          ${track.allowDownload && url ? `<button class="ghost-btn drawer-toggle-btn" type="button" data-download-url="${escapeHtml(url)}">下载产物</button>` : ""}
        </div>
        ${url
          ? `<audio id="separation${track.key[0].toUpperCase()}${track.key.slice(1)}Audio" class="studio-audio" controls preload="metadata" src="${escapeHtml(url)}"></audio>`
          : `<div class="detail-empty inline separation-url-missing">
              后端缺少播放 URL：${escapeHtml(track.title)} 目前不能在浏览器试听。
              ${localPath ? `<div class="path-line subtle"><span class="path-text">${escapeHtml(localPath)}</span></div>` : ""}
            </div>`}
      </div>
    `;
  }).join("");
}

function renderSeparationMetrics() {
  const summary = $("factorySeparationMetricsSummary");
  const grid = $("factorySeparationMetrics");
  if (!summary || !grid) return;

  const run = state.selectedSeparationRun || {};
  const runId = separationRunId(run);
  if (!runId) {
    summary.textContent = "指标不写死 PASS，按真实 run report 原样展示。";
    grid.innerHTML = `<div class="detail-empty inline">等待地基接口：run report 暂不可用。</div>`;
    return;
  }

  const risk = metricValue(run, "noise_risk");
  const durationMismatch = durationMismatchLine(run);
  const blockTraining = ["high", "medium"].includes(String(risk || "").toLowerCase())
    ? `BLOCK_TRAINING：noise_risk=${formatMetricValue(risk)}，先听分离三轨并排查 UVR。`
    : "";
  summary.textContent = risk ? `当前电流音风险：${formatMetricValue(risk)}` : "当前 run 尚未返回 noise_risk。";
  grid.innerHTML = SEPARATION_METRIC_KEYS.map(key => {
    const value = metricValue(run, key);
    const tone = ["noise_risk", "clipping_risk"].includes(key) ? separationRiskTone(value) : "pending";
    return `
      <div class="separation-metric-card">
        <span>${escapeHtml(SEPARATION_METRIC_LABELS[key])}</span>
        <strong class="${tone}">${escapeHtml(formatMetricValue(value))}</strong>
      </div>
    `;
  }).join("") + `
    <div class="separation-note-card">
      <strong>排查提示</strong>
      <p>高频噪声偏高：可能是 UVR 模型、采样率或输入压缩导致。</p>
      <p>削波风险：可能是原曲或分离输出电平过高。</p>
      <p>采样率异常：建议统一转 44.1k/48k 后再分离。</p>
      ${durationMismatch ? `<p>duration mismatch：${escapeHtml(durationMismatch)}</p>` : ""}
      ${blockTraining ? `<p>${escapeHtml(blockTraining)}</p>` : ""}
    </div>
  `;
}

function renderSeparationLab() {
  const summary = $("factorySeparationLabSummary");
  const runBtn = $("factorySeparationRunBtn");
  if (summary) {
    summary.textContent = state.separationUnavailable
      ? state.separationUnavailable
      : state.separationPostUnavailable
        ? state.separationPostUnavailable
        : "已连接分离质检接口；运行只裁剪 45 秒短片段，不训练，不跑 RVC。";
  }
  if (runBtn) {
    runBtn.disabled = Boolean(state.separationUnavailable || state.separationPostUnavailable || state.separationRunInFlight);
    runBtn.textContent = state.separationRunInFlight
      ? "正在提交 45 秒短片段质检..."
      : state.separationPostUnavailable
        ? "后端未开放浏览器执行分离，请用 CLI 执行短片段质检"
      : "只裁剪 45 秒短片段，不跑整首歌";
  }
  renderSeparationUnlockDashboard();
  renderSeparationDurationTable();
  renderSeparationCandidates();
  renderSeparationRuns();
  renderSeparationPlayers();
  renderSeparationMetrics();
}

function applySeparationPostCapability(...payloads) {
  const capability = payloads
    .filter(Boolean)
    .map(payload => payload.browser_execute_enabled
      ?? payload.post_run_enabled
      ?? payload.can_execute_from_browser
      ?? payload.capabilities?.browser_execute
      ?? payload.capabilities?.post_run
      ?? null)
    .find(value => value !== null);

  state.separationPostUnavailable = capability === true
    ? ""
    : "后端未开放浏览器执行分离，请用 CLI 执行短片段质检。";
}

async function loadSeparationRunDetail(runId = "") {
  if (!runId) return;
  const fallback = state.separationRuns.find(run => separationRunId(run) === runId) || null;
  try {
    state.selectedSeparationRun = await getJSON(`/api/separation/eval/runs/${encodeURIComponent(runId)}`);
    state.separationRunDetails[runId] = state.selectedSeparationRun;
  } catch {
    state.selectedSeparationRun = fallback;
  }
  state.selectedSeparationItemIndex = 0;
  renderSeparationLab();
}

async function loadSeparationDurationRows() {
  const runIds = state.separationRuns.map(run => separationRunId(run)).filter(Boolean).slice(0, 12);
  const details = await Promise.all(runIds.map(async runId => {
    try {
      const detail = await getJSON(`/api/separation/eval/runs/${encodeURIComponent(runId)}`);
      state.separationRunDetails[runId] = detail;
      return detail;
    } catch {
      return state.separationRunDetails[runId] || null;
    }
  }));
  state.separationDurationRows = details
    .filter(Boolean)
    .map(durationRowFromRun)
    .filter(row => row.runId);
}

async function loadSeparationLab() {
  let unavailable = "";
  let sourcesPayload = null;
  let runsPayload = null;
  try {
    sourcesPayload = await getJSON("/api/separation/eval/sources");
    state.separationSources = normalizeSeparationSources(sourcesPayload);
  } catch (error) {
    state.separationSources = [];
    unavailable = "等待地基接口：/api/separation/eval/sources 暂不可用。";
  }

  try {
    runsPayload = await getJSON("/api/separation/eval/runs");
    state.separationRuns = normalizeSeparationRuns(runsPayload);
  } catch (error) {
    state.separationRuns = [];
    unavailable = unavailable
      ? `${unavailable} /api/separation/eval/runs 暂不可用。`
      : "等待地基接口：/api/separation/eval/runs 暂不可用。";
  }

  state.separationUnavailable = unavailable;
  applySeparationPostCapability(sourcesPayload, runsPayload);
  await loadSeparationDurationRows();
  if (!state.selectedSeparationRunId || !state.separationRuns.some(run => separationRunId(run) === state.selectedSeparationRunId)) {
    state.selectedSeparationRunId = separationRunId(state.separationRuns[0] || {});
  }
  if (state.selectedSeparationRunId) {
    await loadSeparationRunDetail(state.selectedSeparationRunId);
  } else {
    state.selectedSeparationRun = null;
    renderSeparationLab();
  }
}

async function handleSeparationEvalRun() {
  if (state.separationUnavailable || state.separationPostUnavailable || state.separationRunInFlight) return;
  state.separationRunInFlight = true;
  renderSeparationLab();
  try {
    const payload = await postJSON("/api/separation/eval/run", {
      limit: SEPARATION_EVAL_LIMIT,
      clip_seconds: SEPARATION_EVAL_CLIP_SECONDS,
    });
    const run = payload.run || payload.item || payload;
    const runId = separationRunId(run);
    if (runId) {
      state.selectedSeparationRunId = runId;
      state.selectedSeparationRun = run;
    }
    showToast("已提交 45 秒短片段分离质检，不会训练或 RVC 推理。", "success");
    await loadSeparationLab();
  } catch (error) {
    state.separationPostUnavailable = [405, 501, 503].includes(Number(error?.status))
      ? "后端未开放浏览器执行分离，请用 CLI 执行短片段质检。"
      : `浏览器执行分离暂不可用：${toErrorMessage(error)}。`;
    showToast(state.separationPostUnavailable, "info");
    renderSeparationLab();
  } finally {
    state.separationRunInFlight = false;
    renderSeparationLab();
  }
}

function booleanFilterValue(value = "") {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

function getRvcFilterState() {
  return {
    q: $("factoryRvcModelSearchInput")?.value.trim() || "",
    registered: booleanFilterValue($("factoryRvcRegisteredFilter")?.value || ""),
    hasIndex: booleanFilterValue($("factoryRvcIndexFilter")?.value || ""),
  };
}

function rvcModelMatchesFilters(model, filters) {
  const q = filters.q.toLowerCase();
  const searchable = [
    model.label,
    model.model_key,
    model.pth_name,
    model.pth_path,
    model.index_name,
    model.index_path,
    model.registered_model_id,
    model.registered_model_name,
  ].filter(Boolean).join(" ").toLowerCase();
  if (q && !searchable.includes(q)) return false;
  if (filters.registered !== null && Boolean(model.registered) !== filters.registered) return false;
  if (filters.hasIndex !== null && Boolean(model.index_exists || model.index_path) !== filters.hasIndex) return false;
  return true;
}

function normalizeRvcModelsPayload(payload = {}) {
  const models = Array.isArray(payload)
    ? payload
    : Array.isArray(payload.items)
      ? payload.items
      : Array.isArray(payload.models)
        ? payload.models
        : [];
  const serverPaged = Boolean(payload.items || payload.offset != null || payload.limit != null || payload.total_count != null);
  return {
    models,
    total: Number(payload.total_count ?? payload.model_count ?? models.length) || 0,
    serverPaged,
  };
}

function renderRvcModelsPanel() {
  const summary = $("factoryRvcModelsSummary");
  const list = $("factoryRvcModelsList");
  const pageInfo = $("factoryRvcModelsPageInfo");
  const prevBtn = $("factoryRvcModelsPrevBtn");
  const nextBtn = $("factoryRvcModelsNextBtn");
  if (!summary || !list || !pageInfo || !prevBtn || !nextBtn) return;

  if (state.rvcModelsUnavailable) {
    summary.textContent = state.rvcModelsUnavailable;
    list.innerHTML = `<div class="detail-empty inline">等待地基接口：RVC 模型列表暂不可用。</div>`;
    pageInfo.textContent = "第 1 页";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    return;
  }

  const total = state.rvcModelsTotal || state.rvcModels.length;
  const pageIndex = Math.floor(state.rvcModelsOffset / RVC_MODELS_PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / RVC_MODELS_PAGE_SIZE));
  const registeredCount = state.rvcModels.filter(item => item.registered).length;
  const unregisteredCount = Math.max(0, total - registeredCount);
  summary.textContent = `已读取 ${total} 个外部 RVC 模型；当前页 ${state.rvcModels.length} 个，未登记约 ${unregisteredCount} 个。`;
  pageInfo.textContent = `第 ${pageIndex} / ${pageCount} 页`;
  prevBtn.disabled = state.rvcModelsOffset <= 0;
  nextBtn.disabled = state.rvcModelsOffset + RVC_MODELS_PAGE_SIZE >= total;

  list.innerHTML = state.rvcModels.length
    ? state.rvcModels.map(model => {
      const registered = Boolean(model.registered);
      const indexReady = Boolean(model.index_exists || model.index_path);
      return `
        <div class="factory-rvc-model-item">
          <div class="factory-item-title">
            <strong title="${escapeHtml(model.label || model.model_key || model.pth_name || "")}">${escapeHtml(model.label || model.model_key || model.pth_name || "RVC model")}</strong>
            <span class="status-pill ${registered ? "success" : "pending"}">${registered ? "已登记" : "未登记"}</span>
          </div>
          <div class="factory-item-meta">
            <span>${indexReady ? "有 index" : "无 index"}</span>
            ${model.registered_model_id ? `<span class="mono">${escapeHtml(model.registered_model_id)}</span>` : ""}
            ${model.paired_by ? `<span>${escapeHtml(model.paired_by)}</span>` : ""}
          </div>
          ${renderPathLine(model.pth_path || model.pth_name || "-", { subtle: !model.pth_path })}
          ${model.index_path ? renderPathLine(model.index_path, { subtle: false }) : ""}
          <div class="panel-actions">
            <button
              class="ghost-btn drawer-toggle-btn"
              type="button"
              data-import-rvc-model="${escapeHtml(model.model_key || model.label || "")}"
              ${registered ? "disabled aria-disabled=\"true\"" : ""}
            >${registered ? "已登记到肥鲨" : "登记到肥鲨"}</button>
          </div>
        </div>
      `;
    }).join("")
    : `<div class="detail-empty inline">当前筛选条件下没有 RVC 模型。</div>`;
}

async function loadRvcModels({ resetPage = false } = {}) {
  if (resetPage) state.rvcModelsOffset = 0;
  const filters = getRvcFilterState();
  const params = new URLSearchParams({
    limit: String(RVC_MODELS_PAGE_SIZE),
    offset: String(state.rvcModelsOffset),
  });
  if (filters.q) params.set("q", filters.q);
  if (filters.registered !== null) params.set("registered", String(filters.registered));
  if (filters.hasIndex !== null) params.set("has_index", String(filters.hasIndex));
  params.set("include_test_data", getShowTestRecords() ? "true" : "false");
  params.set("include_smoke", getShowTestRecords() ? "true" : "false");

  try {
    const payload = await getJSON(`/api/engines/rvc/models?${params.toString()}`);
    const normalized = normalizeRvcModelsPayload(payload);
    const filtered = filterTestRecords(normalized.models.filter(model => rvcModelMatchesFilters(model, filters)));
    state.rvcModels = normalized.serverPaged
      ? filtered
      : filtered.slice(state.rvcModelsOffset, state.rvcModelsOffset + RVC_MODELS_PAGE_SIZE);
    state.rvcModelsTotal = normalized.serverPaged ? normalized.total : filtered.length;
    state.rvcModelsUnavailable = "";
  } catch (error) {
    state.rvcModels = [];
    state.rvcModelsTotal = 0;
    state.rvcModelsUnavailable = "等待地基接口：/api/engines/rvc/models 暂不可用。";
  }
  renderRvcModelsPanel();
}

function findRvcModelByKey(key = "") {
  return state.rvcModels.find(model => String(model.model_key || model.label || "") === key) || null;
}

async function handleImportRvcModel(key = "") {
  const model = findRvcModelByKey(key);
  if (!model || model.registered) return;
  try {
    await postJSON("/api/models/import-rvc", {
      model_name: model.label || model.model_key || model.pth_name,
      pth_path: model.pth_path,
      index_path: model.index_path || "",
      source: "external_rvc",
    });
    showToast("RVC 模型已登记到肥鲨模型库", "success");
    await Promise.all([loadCoverModels(), loadRvcModels()]);
  } catch (error) {
    showToast(`等待地基接口：RVC 模型登记暂不可用（${toErrorMessage(error)}）`, "info");
  }
}

function fallbackTrainingPresets() {
  return [
    {
      preset_key: "fast_preview",
      epochs: 20,
      batch_size: 4,
      sample_rate: "40k",
      f0: true,
      index: false,
      gpu_risk: "low",
      estimated_minutes: 25,
    },
    {
      preset_key: "balanced",
      epochs: 50,
      batch_size: 4,
      sample_rate: "40k",
      f0: true,
      index: true,
      gpu_risk: "medium",
      estimated_minutes: 60,
    },
    {
      preset_key: "quality",
      epochs: 100,
      batch_size: 2,
      sample_rate: "48k",
      f0: true,
      index: true,
      gpu_risk: "high",
      estimated_minutes: 120,
    },
  ];
}

function normalizeTrainingPresets(payload = null) {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.presets)
      ? payload.presets
      : Array.isArray(payload?.items)
        ? payload.items
        : [];
  const normalized = items.map(item => ({
    ...item,
    preset_key: item.preset_key || item.key || item.name || "",
    f0: item.f0 ?? item.f0_enabled,
    index: item.index ?? item.index_enabled,
    gpu_risk: item.gpu_risk || item.gpu_risk_label,
    estimated_runtime: item.estimated_runtime || item.estimated_runtime_label,
  })).filter(item => item.preset_key);
  return normalized.length ? normalized : fallbackTrainingPresets();
}

function selectedTrainingPreset() {
  return state.trainingPresets.find(item => item.preset_key === state.selectedTrainingPresetKey)
    || state.trainingPresets[0]
    || fallbackTrainingPresets()[1];
}

function saveTrainingPresetKey(key) {
  state.selectedTrainingPresetKey = key || "balanced";
  try {
    window.localStorage.setItem(TRAINING_PRESET_STORAGE_KEY, state.selectedTrainingPresetKey);
  } catch {
    // Ignore storage failures.
  }
  document.dispatchEvent(new CustomEvent("feishark:training-preset-changed", { detail: { presetKey: state.selectedTrainingPresetKey } }));
}

function loadStoredTrainingPresetKey() {
  try {
    return window.localStorage.getItem(TRAINING_PRESET_STORAGE_KEY) || "balanced";
  } catch {
    return "balanced";
  }
}

function buildFactoryTrainingConfig() {
  const preset = selectedTrainingPreset();
  return {
    preset_key: preset.preset_key,
    epochs: Number(preset.epochs),
    batch_size: Number(preset.batch_size),
    sample_rate: String(preset.sample_rate || "40k"),
    f0_enabled: Boolean(preset.f0_enabled ?? preset.f0 ?? true),
    index_enabled: Boolean(preset.index_enabled ?? preset.index ?? true),
    gpu_risk_label: preset.gpu_risk_label || preset.gpu_risk || "中",
    estimated_runtime_label: preset.estimated_runtime_label || preset.estimated_runtime || `${preset.estimated_minutes || "-"} 分钟`,
    source: "factory_training_tuning",
  };
}

function trainingRiskLabel(value = "") {
  const key = String(value || "").toLowerCase();
  if (["low", "safe"].includes(key)) return "低";
  if (["high", "danger"].includes(key)) return "高";
  return key ? value : "中";
}

function renderTrainingTuning() {
  const grid = $("factoryTrainingPresetGrid");
  const summary = $("factoryTrainingTuningSummary");
  const result = $("factoryTrainingEstimateResult");
  if (!grid || !summary || !result) return;

  summary.textContent = state.trainingTuningUnavailable
    ? `${state.trainingTuningUnavailable} 当前显示产品侧默认预设。`
    : "已读取训练预设；只做估算和解释，不自动创建训练 job。";

  grid.innerHTML = state.trainingPresets.map(preset => {
    const copy = TRAINING_PRESET_COPY[preset.preset_key] || { title: preset.label || preset.preset_key, description: preset.description || "训练预设" };
    const active = preset.preset_key === state.selectedTrainingPresetKey;
    return `
      <button class="training-preset-card ${active ? "is-active" : ""}" type="button" data-training-preset="${escapeHtml(preset.preset_key)}">
        <strong>${escapeHtml(copy.title)}</strong>
        <span>${escapeHtml(copy.description)}</span>
        <small>${escapeHtml(preset.epochs ?? "-")} epochs · batch ${escapeHtml(preset.batch_size ?? "-")} · ${escapeHtml(preset.sample_rate ?? "-")}</small>
      </button>
    `;
  }).join("");

  const preset = selectedTrainingPreset();
  const config = buildFactoryTrainingConfig();
  const estimate = state.trainingEstimate || {};
  const runtime = estimate.estimated_runtime_label || estimate.estimated_minutes || estimate.minutes || config.estimated_runtime_label;
  const gpuRisk = estimate.gpu_risk_label || estimate.gpu_risk || estimate.risk || config.gpu_risk_label;
  result.innerHTML = `
    <div class="training-estimate-grid">
      <div><span>Preset</span><strong>${escapeHtml(TRAINING_PRESET_COPY[preset.preset_key]?.title || preset.preset_key)}</strong></div>
      <div><span>Epochs</span><strong>${escapeHtml(config.epochs ?? "-")}</strong></div>
      <div><span>Batch</span><strong>${escapeHtml(config.batch_size ?? "-")}</strong></div>
      <div><span>Sample Rate</span><strong>${escapeHtml(config.sample_rate ?? "-")}</strong></div>
      <div><span>f0</span><strong>${config.f0_enabled ? "开启" : "关闭"}</strong></div>
      <div><span>Index</span><strong>${config.index_enabled ? "生成" : "不生成"}</strong></div>
      <div><span>GPU 风险</span><strong>${escapeHtml(trainingRiskLabel(gpuRisk))}</strong></div>
      <div><span>预计耗时</span><strong>${escapeHtml(runtime)}</strong></div>
    </div>
    <pre class="training-config-payload mono">${escapeHtml(JSON.stringify(config, null, 2))}</pre>
    <div class="training-estimate-note">${escapeHtml(estimate.explanation || estimate.message || "这是调参预估，不会创建训练 job。")}</div>
  `;
}

async function loadTrainingPresets() {
  state.selectedTrainingPresetKey = loadStoredTrainingPresetKey();
  try {
    const payload = await getJSON("/api/training/presets");
    state.trainingPresets = normalizeTrainingPresets(payload);
    state.trainingTuningUnavailable = "";
  } catch (error) {
    state.trainingPresets = fallbackTrainingPresets();
    state.trainingTuningUnavailable = "等待地基接口：/api/training/presets 暂不可用。";
  }
  if (!state.trainingPresets.some(item => item.preset_key === state.selectedTrainingPresetKey)) {
    saveTrainingPresetKey(state.trainingPresets[0]?.preset_key || "balanced");
  }
  renderTrainingTuning();
}

function localTrainingEstimate() {
  const preset = selectedTrainingPreset();
  const fileCount = Math.max(1, Number($("factoryTrainingFileCountInput")?.value || 1));
  const durationMinutes = Math.max(1, Number($("factoryTrainingDurationInput")?.value || 45));
  const gpuGb = Number($("factoryTrainingGpuInput")?.value || 0);
  const baseMinutes = Number(preset.estimated_minutes || 45);
  const durationFactor = Math.max(0.5, durationMinutes / 45);
  const fileFactor = fileCount > 1 ? 1.15 : 1;
  const estimated = Math.round(baseMinutes * durationFactor * fileFactor);
  const gpuRisk = gpuGb && gpuGb < 8 ? "high" : (preset.gpu_risk || "medium");
  return {
    estimated_minutes: estimated,
    gpu_risk: gpuRisk,
    explanation: "地基 estimate 接口暂不可用，当前为产品侧粗估；不会创建训练 job。",
  };
}

async function handleTrainingEstimate() {
  const preset = selectedTrainingPreset();
  try {
    state.trainingEstimate = await postJSON("/api/training/estimate", {
      preset_key: preset.preset_key,
      file_count: Math.max(1, Number($("factoryTrainingFileCountInput")?.value || 1)),
      duration_seconds: Math.max(1, Number($("factoryTrainingDurationInput")?.value || 45)) * 60,
      gpu_label: $("factoryTrainingGpuInput")?.value ? `${$("factoryTrainingGpuInput").value}GB` : "",
    });
    showToast("训练风险和耗时已估算", "success");
  } catch (error) {
    state.trainingEstimate = localTrainingEstimate();
    showToast(`等待地基接口：训练估算暂不可用（${toErrorMessage(error)}）`, "info");
  }
  renderTrainingTuning();
}

function updateQuery() {
  const params = new URLSearchParams();
  if (state.selectedBatchId) params.set("batch_id", state.selectedBatchId);
  if (state.selectedTrackId) params.set("track_id", state.selectedTrackId);
  const query = params.toString();
  window.history.replaceState(null, "", query ? `/factory?${query}` : "/factory");
}

function parsePlatforms(value) {
  return value
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

function parseTitles(value) {
  return value
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean);
}

function currentDocument(trackDetail) {
  const currentId = trackDetail?.lyrics?.current_lyric_document_id || "";
  const documents = trackDetail?.lyrics?.documents || [];
  return documents.find(item => item.lyric_document_id === currentId) || documents[0] || null;
}

function currentTimeline(trackDetail) {
  const currentId = trackDetail?.lyrics?.current_timeline_version_id || "";
  const versions = trackDetail?.lyrics?.versions || [];
  return versions.find(item => item.timeline_id === currentId) || versions[0] || null;
}

function basename(value = "") {
  return String(value).split(/[\\/]/).filter(Boolean).pop() || value || "-";
}

function isCompletedStatus(status) {
  return status === "completed" || status === "完成" || status === "已完成";
}

function isFailedStatus(status) {
  return status === "failed" || status === "失败";
}

function isCancelledStatus(status) {
  return status === "cancelled" || status === "已取消";
}

function isPendingStatus(status) {
  return status === "pending" || status === "queued";
}

function isActiveJob(job = {}) {
  if (!job?.job_id) return false;
  if (isCompletedStatus(job.status) || isFailedStatus(job.status) || isCancelledStatus(job.status)) {
    return false;
  }
  return ACTIVE_STATUSES.has(job.status || "") || ACTIVE_STAGES.has(job.current_stage || "");
}

function latestTrackJob() {
  return (state.trackJobs || [])[0] || null;
}

function latestCompletedCoverJob() {
  return (state.trackJobs || []).find(job => (
    (job.job_kind === "cover" || job.job_type === "cover")
    && isCompletedStatus(job.status)
    && (job.can_open_studio || job.final_artifact_download_url)
  )) || null;
}

function currentMasterJob() {
  const masterFromDetail = state.trackDetail?.current_master;
  if (masterFromDetail?.job_id) {
    return masterFromDetail;
  }
  return (state.trackJobs || []).find(job => job.is_current_master) || null;
}

function activeTrackJob() {
  return (state.trackJobs || []).find(isActiveJob) || null;
}

function renderTrackRoleTags(job = {}) {
  const parts = [];
  if (job.is_current_master) {
    parts.push('<span class="tag master">当前主成品</span>');
  }
  if (job === latestCompletedCoverJob()) {
    parts.push('<span class="tag success">最新完成版本</span>');
  }
  return parts.join("");
}

function updateFactoryTrackInBatch(trackDetail) {
  if (!trackDetail?.track_id || !state.batchDetail?.tracks) return;
  state.batchDetail.tracks = state.batchDetail.tracks.map(track => (
    track.track_id === trackDetail.track_id
      ? { ...track, status: trackDetail.status, title: trackDetail.title, artist: trackDetail.artist }
      : track
  ));
}

function renderMetaCard(label, value, { path = false, mono = false } = {}) {
  const body = path
    ? renderPathLine(value || "-", { subtle: !value })
    : `<div class="meta-value ${mono ? "mono" : ""}" title="${escapeHtml(value || "-")}">${escapeHtml(value || "-")}</div>`;
  return `
    <div class="meta-card">
      <div class="meta-label">${escapeHtml(label)}</div>
      ${body}
    </div>
  `;
}

function trackJobSourceSummary(job = {}) {
  if (/checkpoint.*恢复|恢复登记|recovered/i.test(String(job.voice_model_source_summary || ""))) {
    return "音色来源：checkpoint 恢复模型";
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

function renderTrackJobSourceLine(job = {}) {
  const sourceSummary = trackJobSourceSummary(job);
  const sourceJobId = job.voice_model_source_job_id || "";
  const recovered = /checkpoint.*恢复|恢复登记|recovered/i.test(String(job.voice_model_source_summary || ""));
  return `
    <div class="factory-inline-note">
      ${renderModelOriginPill(job.voice_model_origin_kind || "")}
      <span>${escapeHtml(sourceSummary)}</span>
      ${sourceJobId ? `<span class="mono">${escapeHtml(sourceJobId)}</span>` : ""}
      ${recovered ? '<span class="tag checkpoint">checkpoint 恢复</span>' : ""}
    </div>
  `;
}

function renderBatchList() {
  const root = $("factoryBatchesList");
  if (!state.batches.length) {
    root.innerHTML = `<div class="detail-empty inline">当前还没有 batch。先在左侧创建一个批次。</div>`;
    return;
  }

  root.innerHTML = state.batches.map(batch => `
    <button class="factory-item ${batch.batch_id === state.selectedBatchId ? "is-active" : ""}" type="button" data-batch-id="${escapeHtml(batch.batch_id)}">
      <div class="factory-item-title">
        <strong>${escapeHtml(batch.batch_name || batch.batch_id)}</strong>
        ${renderStatusPill(batch.status || "draft")}
      </div>
      <div class="factory-item-meta">
        <span class="mono">${escapeHtml(batch.batch_id)}</span>
        <span>${escapeHtml(formatDateTime(batch.created_at))}</span>
        <span>tracks ${escapeHtml(String(batch.track_count || 0))}</span>
      </div>
    </button>
  `).join("");
}

function renderTracks() {
  const batch = state.batchDetail;
  $("factoryBatchTitle").textContent = batch ? (batch.batch_name || batch.batch_id) : "尚未选择批次";
  $("factoryBatchHint").textContent = batch
    ? `${batch.track_count || 0} 首曲目，输出目录 ${batch.output_root || "-"}`
    : "选择一个批次继续";
  $("factoryTrackHint").textContent = batch
    ? `当前批次共有 ${batch.track_count || 0} 首曲目`
    : "导入后在这里选择曲目";

  const root = $("factoryTracksList");
  const tracks = batch?.tracks || [];
  if (!tracks.length) {
    root.innerHTML = `<div class="detail-empty inline">当前批次还没有曲目。导入音频后，这里会出现 track 列表。</div>`;
    return;
  }

  root.innerHTML = tracks.map(track => `
    <button class="factory-item ${track.track_id === state.selectedTrackId ? "is-active" : ""}" type="button" data-track-id="${escapeHtml(track.track_id)}">
      <div class="factory-item-title">
        <strong>${escapeHtml(track.title || track.track_id)}</strong>
        ${renderTrackStatusPill(track.status || "imported")}
      </div>
      <div class="factory-item-meta">
        <span>${escapeHtml(track.artist || "Unknown Artist")}</span>
        <span class="mono">${escapeHtml(track.track_id)}</span>
      </div>
      ${renderPathLine(track.source_audio_path || "-", { subtle: true })}
    </button>
  `).join("");
}

function renderTrackCoverControls() {
  const select = $("factoryCoverModelSelect");
  const button = $("factoryCreateCoverJobBtn");
  const hint = $("factoryCoverJobHint");
  const models = state.coverModels || [];

  if (!models.length) {
    select.innerHTML = `<option value="">当前没有可用模型</option>`;
    select.disabled = true;
    button.disabled = true;
    hint.textContent = "当前没有可用模型，请先回到工作台导入或重扫模型。";
    return;
  }

  const currentValue = models.some(item => item.model_id === state.selectedCoverModelId)
    ? state.selectedCoverModelId
    : models[0].model_id;
  state.selectedCoverModelId = currentValue;

  select.innerHTML = models.map(model => `
    <option value="${escapeHtml(model.model_id)}" ${model.model_id === currentValue ? "selected" : ""}>
      ${escapeHtml(model.model_name || model.model_id)}
    </option>
  `).join("");
  select.disabled = false;

  const track = state.trackDetail;
  const hasActive = Boolean(activeTrackJob());
  const canCreate = Boolean(track && state.selectedCoverModelId && !hasActive);
  button.disabled = !canCreate;

  if (!track) {
    hint.textContent = "先选择一个曲目，再从当前曲目直接发起翻唱任务。";
    return;
  }

  if (hasActive) {
    hint.textContent = "当前曲目已有进行中的关联任务，工厂会自动刷新状态。";
    return;
  }

  hint.textContent = `将直接复用 ${basename(track.source_audio_path || "")} 创建翻唱任务，不再重复上传源音频。`;
}

function buildTrackJobSummary(job) {
  if (isCompletedStatus(job.status)) {
    return job.can_open_studio
      ? "成品已就绪，可直接进入录音棚 或下载最终成品。"
      : "任务已完成。";
  }
  if (isFailedStatus(job.status)) {
    const failedStage = stageText(job.current_stage || "failed");
    return `任务失败，最后停在 ${failedStage}${job.error_summary ? `：${job.error_summary}` : ""}`;
  }
  if (isPendingStatus(job.status)) {
    return "任务已入队，正在等待算力释放。";
  }
  return job.latest_stage_message || `任务进行中，当前阶段 ${stageText(job.current_stage || "-")}`;
}

function renderTrackOutcome() {
  const root = $("factoryTrackOutcomeCard");
  const completed = latestCompletedCoverJob();
  const active = activeTrackJob();
  const latest = latestTrackJob();

  if (!state.selectedTrackId || (!completed && !active && !latest)) {
    root.hidden = true;
    root.innerHTML = "";
    return;
  }

  root.hidden = false;
  if (completed) {
    root.className = "factory-outcome-card is-ready";
    root.innerHTML = `
      <div>
        <p class="detail-summary-eyebrow">最新成品已就绪</p>
        <strong>${escapeHtml(completed.voice_name || completed.voice_model_id || completed.job_id)}</strong>
        ${renderTrackJobSourceLine(completed)}
        <p>${escapeHtml(buildTrackJobSummary(completed))}</p>
      </div>
      <div class="panel-actions">
        ${completed.can_open_studio ? `<button class="primary-btn warm" type="button" data-studio-url="${escapeHtml(completed.studio_url || "")}">进入录音棚</button>` : ""}
        ${completed.final_artifact_download_url ? `<button class="ghost-btn" type="button" data-download-url="${escapeHtml(completed.final_artifact_download_url)}">下载成品</button>` : ""}
      </div>
    `;
    return;
  }

  if (active) {
    root.className = "factory-outcome-card is-active";
    root.innerHTML = `
      <div>
        <p class="detail-summary-eyebrow">任务正在推进</p>
        <strong>${escapeHtml(active.voice_name || active.voice_model_id || active.job_id)}</strong>
        ${renderTrackJobSourceLine(active)}
        <p>${escapeHtml(buildTrackJobSummary(active))}</p>
      </div>
      <div class="factory-mini-meta">
        ${renderStatusPill(active.status || "pending")}
        ${renderStagePill(active.current_stage || "pending", active.status || "")}
      </div>
    `;
    return;
  }

  root.className = `factory-outcome-card ${isFailedStatus(latest.status) ? "is-failed" : ""}`;
  root.innerHTML = `
    <div>
      <p class="detail-summary-eyebrow">最近任务</p>
      <strong>${escapeHtml(latest.voice_name || latest.voice_model_id || latest.job_id)}</strong>
      ${renderTrackJobSourceLine(latest)}
      <p>${escapeHtml(buildTrackJobSummary(latest))}</p>
    </div>
    <div class="factory-mini-meta">
      ${renderStatusPill(latest.status || "pending")}
      ${renderStagePill(latest.current_stage || "pending", latest.status || "")}
    </div>
  `;
}

function renderCurrentMasterCard() {
  const root = $("factoryCurrentMasterCard");
  const track = state.trackDetail;
  const master = currentMasterJob();
  const latestCompleted = latestCompletedCoverJob();

  if (!root) return;

  if (!track) {
    root.hidden = true;
    root.innerHTML = "";
    return;
  }

  root.hidden = false;

  if (!master) {
    const fallbackLabel = latestCompleted?.voice_name || latestCompleted?.voice_model_id || latestCompleted?.job_id || "";
    root.className = "detail-summary-card factory-master-card is-empty";
    root.innerHTML = `
      <div class="detail-summary-head">
        <div class="detail-summary-head-copy">
          <p class="detail-summary-eyebrow">当前主成品</p>
          <h3 class="detail-summary-title">当前尚未指定主成品</h3>
          <p class="detail-summary-text">
            ${
              latestCompleted
                ? escapeHtml(`当前仍按最新完成版本 ${fallbackLabel} 作为默认工作流；如需固定较旧版本，请进入录音棚手动指定当前主成品。`)
                : "这个 Track 还没有可指定的完成态成品，先跑通至少一个 cover 版本。"
            }
          </p>
        </div>
        <div class="detail-summary-badges">
          <span class="tag warn">未指定</span>
        </div>
      </div>
      <div class="detail-summary-foot">
        ${latestCompleted ? "未手动指定时，工厂 / 录音棚 仍会优先按最新完成版本继续工作。" : "完成后即可在录音棚历史区切换真正采用的版本。"}
      </div>
      ${
        latestCompleted
          ? `
            <div class="panel-actions">
              ${latestCompleted.can_open_studio ? `<button class="ghost-btn" type="button" data-studio-url="${escapeHtml(latestCompleted.studio_url || "")}">进入录音棚指定主成品</button>` : ""}
              ${latestCompleted.final_artifact_download_url ? `<button class="ghost-btn" type="button" data-download-url="${escapeHtml(latestCompleted.final_artifact_download_url)}">下载当前默认成品</button>` : ""}
            </div>
          `
          : ""
      }
    `;
    return;
  }

  const masterLabel = master.voice_name || master.voice_model_id || master.job_id;
  const latestLabel = latestCompleted?.voice_name || latestCompleted?.voice_model_id || latestCompleted?.job_id || "";
  const differsFromLatest = Boolean(
    latestCompleted?.job_id
    && master.job_id
    && latestCompleted.job_id !== master.job_id,
  );

  root.className = "detail-summary-card factory-master-card";
  root.innerHTML = `
    <div class="detail-summary-head">
      <div class="detail-summary-head-copy">
        <p class="detail-summary-eyebrow">当前主成品</p>
        <h3 class="detail-summary-title">${escapeHtml(masterLabel)}</h3>
        <p class="detail-summary-text">
          ${escapeHtml(
            differsFromLatest
              ? `当前采用的是手动指定版本 ${masterLabel}。它不是最新完成版本，但会被工厂和录音棚视为这个曲目的当前主成品。`
              : `当前采用的是 ${masterLabel}，它就是这个 Track 现在正式使用的主成品。`,
          )}
        </p>
      </div>
      <div class="detail-summary-badges">
        <span class="tag master">当前主成品</span>
        ${differsFromLatest ? '<span class="tag warn">已手动固定</span>' : '<span class="tag success">与最新版本一致</span>'}
      </div>
    </div>
    <div class="factory-master-grid">
      ${renderMetaCard("音色 / 版本", masterLabel)}
      ${renderMetaCard("来源任务", master.job_id || "-", { mono: true })}
      ${renderMetaCard("模型来源", trackJobSourceSummary(master))}
      ${renderMetaCard("创建时间", formatDateTime(master.created_at))}
      ${renderMetaCard("最终成品", basename(master.final_artifact_path || "final_master.wav"))}
    </div>
    ${
      differsFromLatest
        ? `<div class="factory-master-compare">最新完成版本仍是 ${escapeHtml(latestLabel)}，但当前采用版本已切换为 ${escapeHtml(masterLabel)}。</div>`
        : `<div class="factory-master-compare">最新完成版本与当前主成品一致，无需额外切换。</div>`
    }
    <div class="panel-actions">
      ${master.can_open_studio ? `<button class="primary-btn warm" type="button" data-studio-url="${escapeHtml(master.studio_url || "")}">进入录音棚</button>` : ""}
      ${master.final_artifact_download_url ? `<button class="ghost-btn" type="button" data-download-url="${escapeHtml(master.final_artifact_download_url)}">下载主成品</button>` : ""}
    </div>
  `;
}

function renderTrackJobs() {
  const root = $("factoryTrackJobsList");
  const summary = $("factoryTrackJobsSummary");

  if (!state.selectedTrackId) {
    summary.textContent = "先选择一个曲目，再查看关联任务";
    root.innerHTML = `<div class="detail-empty inline">当前还没有选中曲目。</div>`;
    renderTrackOutcome();
    return;
  }

  const jobs = state.trackJobs || [];
  if (!jobs.length) {
    summary.textContent = "当前还没有关联任务，可先选择模型并发起一个翻唱任务。";
    root.innerHTML = `<div class="detail-empty inline">这个 track 还没有创建过任务。</div>`;
    renderTrackOutcome();
    return;
  }

  const latest = jobs[0];
  const active = activeTrackJob();
  summary.textContent = active
    ? `自动刷新中：${stageText(active.current_stage || "pending")}`
    : `最近 ${jobs.length} 条关联任务，最新状态 ${latest.status || "-"}`;

  root.innerHTML = jobs.map(job => `
    <div class="artifact-item ${job.has_final_artifact ? "is-final" : ""}" data-track-job-id="${escapeHtml(job.job_id)}">
      <div class="artifact-item-head">
        <strong>${escapeHtml(job.voice_name || job.voice_model_id || job.job_id)}</strong>
        ${renderStatusPill(job.status || "pending")}
      </div>
      <div class="artifact-meta">
        <span>${escapeHtml(job.job_kind || job.job_type || "job")}</span>
        <span class="mono" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</span>
        <span>${escapeHtml(formatDateTime(job.created_at))}</span>
      </div>
      <div class="factory-mini-meta">
        ${renderStagePill(job.current_stage || "pending", job.status || "")}
        ${renderTrackRoleTags(job)}
      </div>
      ${renderTrackJobSourceLine(job)}
      ${renderPathLine(buildTrackJobSummary(job), { mono: false, subtle: !job.error_summary })}
      <div class="panel-actions">
        ${job.can_open_studio ? `<button class="ghost-btn" type="button" data-studio-url="${escapeHtml(job.studio_url || "")}">进入录音棚</button>` : ""}
        ${job.final_artifact_download_url ? `<button class="ghost-btn" type="button" data-download-url="${escapeHtml(job.final_artifact_download_url)}">下载成品</button>` : ""}
      </div>
    </div>
  `).join("");
  renderTrackOutcome();
}

function renderTrackAssetSummary() {
  const track = state.trackDetail;
  const active = activeTrackJob();
  const completed = latestCompletedCoverJob();
  const summary = $("factoryAssetSummary");
  const grid = $("factoryTrackAssetGrid");

  if (!track) {
    summary.textContent = "先选择一个曲目，再查看来源音频、当前状态和可执行动作。";
    grid.innerHTML = `<div class="detail-empty inline">当前还没有选中曲目。</div>`;
    return;
  }

  summary.textContent = active
    ? `当前曲目正在 ${stageText(active.current_stage || "pending")}，无需手动刷新。`
    : completed
      ? "最新成品已就绪，可直接进入录音棚 或下载。"
      : "当前曲目可继续整理歌词，或选择模型创建翻唱任务。";

  grid.innerHTML = [
    renderMetaCard("标题", track.title || track.track_id),
    renderMetaCard("作者", track.artist || "Unknown Artist"),
    renderMetaCard("Track ID", track.track_id, { mono: true }),
    renderMetaCard("当前状态", TRACK_STATUS_META[track.status]?.label || track.status || "已导入"),
    renderMetaCard("来源音频", track.source_audio_path || "-", { path: true }),
    renderMetaCard("批次", track.batch_name || track.batch_id || "-", { mono: true }),
  ].join("");
}

function renderLyricsAssetSummary() {
  const track = state.trackDetail;
  const doc = currentDocument(track);
  const timeline = currentTimeline(track);
  const docs = track?.lyrics?.documents || [];
  const versions = track?.lyrics?.versions || [];
  const summary = $("factoryLyricsSummary");
  const grid = $("factoryLyricsMetaGrid");

  if (!track) {
    summary.textContent = "先选择一个曲目，再编辑歌词草稿或生成时间轴版本。";
    grid.innerHTML = `<div class="detail-empty inline">当前还没有选中曲目。</div>`;
    return;
  }

  summary.textContent = timeline
    ? `当前时间轴 ${timeline.timeline_id}，可继续晋级或生成新版本。`
    : doc
      ? "已有歌词草稿，下一步可生成时间轴版本。"
      : "尚未生成歌词资产，可先创建草稿。";

  grid.innerHTML = [
    renderMetaCard("当前歌词文档", doc?.lyric_document_id || "尚未生成", { mono: Boolean(doc) }),
    renderMetaCard("当前时间轴", timeline?.timeline_id || "尚未生成", { mono: Boolean(timeline) }),
    renderMetaCard("歌词文档数", `${docs.length} 个`),
    renderMetaCard("时间轴版本数", `${versions.length} 个`),
  ].join("");
}

function renderTrackDetail() {
  const track = state.trackDetail;
  const active = activeTrackJob();
  const completed = latestCompletedCoverJob();
  const latest = latestTrackJob();
  $("factoryTrackTitle").textContent = track ? (track.title || track.track_id) : "请选择一个曲目";
  $("factoryTrackSubtitle").textContent = track
    ? `${track.title || track.track_id}${track.artist ? ` / ${track.artist}` : ""}`
    : "暂无载入曲目";
  $("factoryTrackMeta").textContent = track
    ? (
      active
        ? `当前任务正在 ${stageText(active.current_stage || "pending")}，工厂会自动刷新当前曲目状态。`
        : completed
          ? "最新成品已就绪，可直接进入录音棚 或下载。"
          : isFailedStatus(latest?.status || "")
            ? buildTrackJobSummary(latest)
            : `批次 ${track.batch_name || track.batch_id} · 创建于 ${formatDateTime(track.created_at)}`
    )
    : "导入后点击曲目，继续处理歌词并发起真实任务。";
  $("factoryTrackStatus").innerHTML = track ? renderTrackStatusPill(track.status || "imported") : "";
  $("factoryTrackLyricState").textContent = track?.lyrics?.current_timeline_version_id
    ? `当前时间轴：${track.lyrics.current_timeline_version_id}`
    : "尚未生成时间轴版本";
  $("factoryTrackPath").innerHTML = renderPathLine(track?.source_audio_path || "-", { subtle: !track?.source_audio_path });

  const doc = currentDocument(track);
  const textArea = $("factoryLyricText");
  const trackId = track?.track_id || "";
  if (!track) {
    textArea.value = "";
    state.renderedTrackId = "";
    state.lyricDraftDirty = false;
  } else if (state.renderedTrackId !== trackId || !state.lyricDraftDirty) {
    textArea.value = doc?.text_content || "";
    state.renderedTrackId = trackId;
    state.lyricDraftDirty = false;
  }

  renderTrackAssetSummary();
  renderLyricsAssetSummary();
  renderTrackCoverControls();
  renderTrackJobs();
  renderCurrentMasterCard();
  renderLyricVersions();
  renderAuditEvents();
  syncTrackPolling();
}

function renderLyricVersions() {
  const root = $("factoryLyricVersions");
  const track = state.trackDetail;
  if (!track) {
    root.innerHTML = `<div class="detail-empty inline">先选择一个曲目，再查看歌词文档和时间轴版本。</div>`;
    return;
  }

  const docs = track.lyrics?.documents || [];
  const versions = track.lyrics?.versions || [];
  const currentTimelineId = track.lyrics?.current_timeline_version_id || "";

  const docsHtml = docs.length
    ? docs.map(doc => `
        <div class="artifact-item">
          <div class="artifact-item-head">
            <strong>${escapeHtml(doc.title || doc.lyric_document_id)}</strong>
            <span class="artifact-chip pending">${escapeHtml(doc.source || "draft")}</span>
          </div>
          <div class="artifact-meta">
            <span class="mono" title="${escapeHtml(doc.lyric_document_id)}">${escapeHtml(doc.lyric_document_id)}</span>
            <span>${escapeHtml(formatDateTime(doc.created_at))}</span>
            <span>${escapeHtml(String(doc.structure?.line_count || 0))} lines</span>
          </div>
        </div>
      `).join("")
    : `<div class="detail-empty inline">当前还没有歌词文档。</div>`;

  const versionsHtml = versions.length
    ? versions.map(version => `
        <div class="artifact-item ${version.timeline_id === currentTimelineId ? "is-final" : ""}">
          <div class="artifact-item-head">
            <strong>${escapeHtml(version.version_label || version.timeline_id)}</strong>
            <span class="artifact-chip ${version.timeline_id === currentTimelineId ? "success" : "pending"}">
              ${version.timeline_id === currentTimelineId ? "当前版本" : escapeHtml(version.status || "draft")}
            </span>
          </div>
          <div class="artifact-meta">
            <span class="mono" title="${escapeHtml(version.timeline_id)}">${escapeHtml(version.timeline_id)}</span>
            <span>${escapeHtml(version.engine || "-")}</span>
            <span>${escapeHtml(formatDateTime(version.created_at))}</span>
          </div>
          ${renderPathLine(version.lrc_path || "-", { subtle: true })}
          <div class="panel-actions">
            <button
              class="ghost-btn"
              type="button"
              data-promote-timeline="${escapeHtml(version.timeline_id)}"
              ${version.timeline_id === currentTimelineId ? "disabled" : ""}
            >晋级为当前版本</button>
          </div>
        </div>
      `).join("")
    : `<div class="detail-empty inline">当前还没有时间轴版本。</div>`;

  root.innerHTML = `
    <div class="detail-section-compact">
      <div class="detail-section-head"><h4>歌词文档</h4></div>
      <div class="detail-list">${docsHtml}</div>
    </div>
    <div class="detail-section-compact">
      <div class="detail-section-head"><h4>时间轴版本</h4></div>
      <div class="detail-list">${versionsHtml}</div>
    </div>
  `;
}

function renderAuditEvents() {
  const root = $("factoryAuditList");
  const track = state.trackDetail;
  const auditEvents = track?.audit_events || [];
  if (!auditEvents.length) {
    root.innerHTML = `<div class="detail-empty inline">当前曲目还没有审计事件。</div>`;
    return;
  }

  root.innerHTML = auditEvents.map(item => `
    <div class="log-item completed">
      <strong>${escapeHtml(AUDIT_ACTION_META[item.action] || item.action)}</strong>
      <div class="log-meta">
        <span>${escapeHtml(item.entity_type || "track")}</span>
        <span class="mono" title="${escapeHtml(item.entity_id || "")}">${escapeHtml(item.entity_id || "")}</span>
        <span>${escapeHtml(formatDateTime(item.created_at))}</span>
      </div>
    </div>
  `).join("");
}

async function setFactoryDrawerCollapsed(kind, collapsed, { immediate = false } = {}) {
  const config = {
    asset: {
      drawerId: "factoryAssetDrawer",
      bodyId: "factoryAssetBody",
      buttonId: "factoryAssetToggleBtn",
      key: FACTORY_ASSET_COLLAPSED_KEY,
      openLabel: "收起曲目资产 ▴",
      closedLabel: "展开曲目资产 ▾",
    },
    lyrics: {
      drawerId: "factoryLyricsDrawer",
      bodyId: "factoryLyricsBody",
      buttonId: "factoryLyricsToggleBtn",
      key: FACTORY_LYRICS_COLLAPSED_KEY,
      openLabel: "收起歌词资产 ▴",
      closedLabel: "展开歌词资产 ▾",
    },
    jobs: {
      drawerId: "factoryJobsDrawer",
      bodyId: "factoryJobsBody",
      buttonId: "factoryJobsToggleBtn",
      key: FACTORY_JOBS_COLLAPSED_KEY,
      openLabel: "收起关联任务 ▴",
      closedLabel: "展开关联任务 ▾",
    },
    batches: {
      drawerId: "factoryBatchesDrawer",
      bodyId: "factoryBatchesBody",
      buttonId: "factoryBatchesToggleBtn",
      key: FACTORY_BATCHES_COLLAPSED_KEY,
      openLabel: "收起批次 ▴",
      closedLabel: "展开批次 ▾",
    },
    modelAssets: {
      drawerId: "factoryModelAssetsDrawer",
      bodyId: "factoryModelAssetsBody",
      buttonId: "factoryModelAssetsToggleBtn",
      key: FACTORY_MODEL_ASSETS_COLLAPSED_KEY,
      openLabel: "收起模型资产 ▴",
      closedLabel: "展开模型资产 ▾",
    },
    reviewRouting: {
      drawerId: "factoryReviewRoutingPanel",
      bodyId: "factoryReviewRoutingBody",
      buttonId: "factoryReviewRoutingToggleBtn",
      key: FACTORY_REVIEW_ROUTING_COLLAPSED_KEY,
      openLabel: "收起验收列表 ▴",
      closedLabel: "展开验收列表 ▾",
    },
    materialLibrary: {
      drawerId: "factoryMaterialLibraryDrawer",
      bodyId: "factoryMaterialLibraryBody",
      buttonId: "factoryMaterialLibraryToggleBtn",
      key: FACTORY_MATERIAL_LIBRARY_COLLAPSED_KEY,
      openLabel: "收起素材库 ▴",
      closedLabel: "展开素材库 ▾",
    },
  }[kind];
  if (!config) return;

  const drawer = $(config.drawerId);
  const body = $(config.bodyId);
  const button = $(config.buttonId);
  if (!drawer || !body || !button) return;

  state.drawerCollapsed[kind] = Boolean(collapsed);
  if (config.key) saveUiState(config.key, state.drawerCollapsed[kind]);
  drawer.dataset.collapsed = String(state.drawerCollapsed[kind]);
  drawer.classList.toggle("is-collapsed", state.drawerCollapsed[kind]);
  button.setAttribute("aria-expanded", String(!state.drawerCollapsed[kind]));
  button.textContent = state.drawerCollapsed[kind] ? config.closedLabel : config.openLabel;

  if (immediate || body.hidden === state.drawerCollapsed[kind]) {
    body.hidden = state.drawerCollapsed[kind];
    return;
  }

  await slideToggle(body, !state.drawerCollapsed[kind]);
}

function stopTrackPolling() {
  if (state.trackPollTimer) {
    window.clearTimeout(state.trackPollTimer);
    state.trackPollTimer = 0;
  }
}

function scheduleTrackPolling() {
  stopTrackPolling();
  const active = activeTrackJob();
  if (!state.selectedTrackId || !active || document.hidden) {
    return;
  }

  state.trackPollTimer = window.setTimeout(() => {
    refreshSelectedTrack({ source: "poll" }).catch(error => {
      console.warn("[Factory] track auto refresh failed", error);
      scheduleTrackPolling();
    });
  }, TRACK_POLL_INTERVAL_MS);
}

function syncTrackPolling() {
  const active = activeTrackJob();
  if (!active) {
    stopTrackPolling();
    if (state.selectedTrackId) {
      setFactoryStatus("当前曲目已同步", "success");
    }
    return;
  }

  setFactoryStatus(`自动观察中 · ${stageText(active.current_stage || "pending")}`, "warning");
  if (!state.trackPollTimer && !state.trackPollInFlight) {
    scheduleTrackPolling();
  }
}

async function refreshSelectedTrack({ source = "manual" } = {}) {
  const trackId = state.selectedTrackId;
  if (!trackId || state.trackPollInFlight) return;

  state.trackPollInFlight = true;
  try {
    const [trackDetail, jobPayload] = await Promise.all([
      getJSON(`/api/tracks/${trackId}`),
      getJSON(`/api/tracks/${trackId}/jobs${buildQuery(withTestRecordParams({ limit: 10, offset: 0 }))}`),
    ]);

    if (state.selectedTrackId !== trackId) return;
    state.trackDetail = trackDetail;
    state.trackJobs = filterTestRecords(jobPayload.items || []);
    updateFactoryTrackInBatch(trackDetail);
    renderTracks();
    renderTrackDetail();
    updateQuery();
    if (source !== "poll") {
      setFactoryStatus("当前曲目已刷新", "success");
    }
  } finally {
    state.trackPollInFlight = false;
    if (state.selectedTrackId === trackId) {
      scheduleTrackPolling();
    }
  }
}

async function loadSummary() {
  state.summary = await getJSON(`/api/factory/summary${buildQuery(withTestRecordParams({}))}`);
  setSummary(state.summary);
}

async function loadEngines() {
  try {
    state.engines = await getJSON("/api/engines");
    state.enginesUnavailable = "";
  } catch (error) {
    state.engines = null;
    state.enginesUnavailable = "等待地基接口：/api/engines 暂不可用。";
  }
  renderEngineManager();
}

async function loadCoverModels() {
  const modelParams = withTestRecordParams({});
  const [modelsPayload, modelSummary] = await Promise.all([
    getJSON(`/api/models${buildQuery(modelParams)}`),
    getJSON(`/api/models/summary${buildQuery(modelParams)}`).catch(() => null),
  ]);
  const models = Array.isArray(modelsPayload)
    ? modelsPayload
    : Array.isArray(modelsPayload?.items)
      ? modelsPayload.items
      : Array.isArray(modelsPayload?.models)
        ? modelsPayload.models
        : [];
  state.modelSummary = modelSummary;
  state.coverModels = filterTestRecords(models);
  const nextValue = state.coverModels.some(item => item.model_id === state.selectedCoverModelId)
    ? state.selectedCoverModelId
    : state.coverModels[0]?.model_id || "";
  state.selectedCoverModelId = nextValue;
  renderTrackCoverControls();
  renderModelAssetsDrawer();
}

function isStage47FactoryModel(model = {}) {
  const text = [
    model.model_id,
    model.model_name,
    model.source_job_id,
    model.source_summary,
    model.resolved_pth_path,
    model.resolved_index_path,
  ].filter(Boolean).join(" ");
  return /stage[\s_-]*47/i.test(text) || text.includes("朱朱_stage47_single_long");
}

function renderStage47ModelFacts(model = {}) {
  if (!isStage47FactoryModel(model)) return "";
  const pthReady = Boolean(model.pth_exists || model.exists || model.resolved_pth_path);
  const indexReady = Boolean(model.index_exists || model.index_path || model.resolved_index_path);
  return `
    <div class="stage47-model-facts">
      <span>pth：${pthReady ? "存在" : "缺失"}</span>
      <span>index：${indexReady ? "存在" : "缺失"}</span>
      <span>cover：${model.usable ? "可用" : "不可用"}</span>
      ${model.source_job_id ? `<span class="mono">source ${escapeHtml(model.source_job_id)}</span>` : ""}
    </div>
  `;
}

function renderModelAssetsDrawer() {
  const summary = $("factoryModelAssetsSummary");
  const list = $("factoryModelAssetsList");
  if (!summary || !list) return;
  const models = state.coverModels || [];
  const usableCount = models.filter(model => model.usable).length;
  const stage47Count = models.filter(isStage47FactoryModel).length;
  summary.textContent = `已读取 ${models.length} 个模型资产，其中 ${usableCount} 个可用于翻唱；Stage47 实训模型 ${stage47Count} 个。`;
  list.innerHTML = models.length
    ? models.map(model => {
      const stage47 = isStage47FactoryModel(model);
      return `
      <div class="factory-item">
        <div class="factory-item-title">
          <strong>${escapeHtml(model.model_name || model.model_id)}</strong>
          <span class="factory-item-badges">
            ${stage47 ? '<span class="tag stage47">Stage47 实训模型</span>' : ""}
            ${renderStatusPill(model.usable ? "completed" : "failed")}
          </span>
        </div>
        <div class="factory-item-meta">
          ${renderModelOriginPill(model.origin_kind || "")}
          <span class="mono">${escapeHtml(model.model_id)}</span>
          ${model.source_job_id ? `<span class="mono">${escapeHtml(model.source_job_id)}</span>` : ""}
        </div>
        <div class="detail-note model-source-summary">${escapeHtml(model.source_summary || "模型来源未标注")}</div>
        ${renderStage47ModelFacts(model)}
      </div>
    `;
    }).join("")
    : `<div class="detail-empty inline">当前没有可展示的模型资产。</div>`;
}

async function loadBatches({ keepSelection = true } = {}) {
  const response = await getJSON(`/api/batches${buildQuery(withTestRecordParams({ limit: 100, offset: 0 }))}`);
  const rawBatches = response.items || [];
  state.batches = filterTestRecords(rawBatches);
  const hiddenCount = factoryHiddenTestCount(response) || Math.max(0, rawBatches.length - state.batches.length);
  renderTestRecordsToggle(hiddenCount);
  renderBatchList();

  const params = new URLSearchParams(window.location.search);
  const requestedBatchId = params.get("batch_id") || "";
  const nextBatchId = keepSelection && state.batches.some(item => item.batch_id === state.selectedBatchId)
    ? state.selectedBatchId
    : state.batches.some(item => item.batch_id === requestedBatchId)
      ? requestedBatchId
      : state.batches[0]?.batch_id || "";

  if (nextBatchId) {
    await loadBatch(nextBatchId, { preserveTrack: keepSelection });
  } else {
    stopTrackPolling();
    state.selectedBatchId = "";
    state.batchDetail = null;
    state.selectedTrackId = "";
    state.trackDetail = null;
    state.trackJobs = [];
    renderTracks();
    renderTrackDetail();
    await setFactoryDrawerCollapsed("batches", state.drawerCollapsed.batches, { immediate: true });
  }
}

async function loadBatch(batchId, { preserveTrack = true } = {}) {
  if (!batchId) return;
  const previousTrackId = state.selectedTrackId;
  state.selectedBatchId = batchId;
  state.batchDetail = await getJSON(`/api/batches/${batchId}${buildQuery(withTestRecordParams({}))}`);
  try {
    const tracksPayload = await getJSON(`/api/batches/${batchId}/tracks${buildQuery(withTestRecordParams({}))}`);
    const tracks = Array.isArray(tracksPayload)
      ? tracksPayload
      : Array.isArray(tracksPayload?.items)
        ? tracksPayload.items
        : Array.isArray(tracksPayload?.tracks)
          ? tracksPayload.tracks
          : null;
    if (tracks) state.batchDetail.tracks = tracks;
  } catch {
    // Older backends still embed tracks on the batch detail response.
  }
  if (Array.isArray(state.batchDetail?.tracks)) {
    state.batchDetail.tracks = filterTestRecords(state.batchDetail.tracks);
  }
  renderBatchList();
  renderTracks();
  await setFactoryDrawerCollapsed("batches", state.drawerCollapsed.batches, { immediate: true });

  const params = new URLSearchParams(window.location.search);
  const requestedTrackId = params.get("track_id") || "";
  const tracks = state.batchDetail?.tracks || [];
  const nextTrackId = preserveTrack && tracks.some(item => item.track_id === state.selectedTrackId)
    ? state.selectedTrackId
    : tracks.some(item => item.track_id === requestedTrackId)
      ? requestedTrackId
      : tracks[0]?.track_id || "";

  if (nextTrackId) {
    if (previousTrackId && previousTrackId !== nextTrackId) {
      stopTrackPolling();
    }
    await loadTrack(nextTrackId);
  } else {
    stopTrackPolling();
    state.selectedTrackId = "";
    state.trackDetail = null;
    state.trackJobs = [];
    renderTrackDetail();
    updateQuery();
  }
}

async function loadTrack(trackId) {
  if (!trackId) return;
  if (state.selectedTrackId && state.selectedTrackId !== trackId) {
    stopTrackPolling();
  }
  state.selectedTrackId = trackId;
  await refreshSelectedTrack({ source: "load" });
}

async function refreshAll() {
  try {
    stopTrackPolling();
    setFactoryStatus("正在刷新工厂数据", "warning");
    await loadSummary();
    await loadEngines();
    await loadRvcModels();
    await loadFactoryReviewRouting();
    await loadMaterialLibrary();
    await loadSeparationLab();
    await loadTrainingPresets();
    await loadCoverModels();
    await loadBatches({ keepSelection: true });
    if (!activeTrackJob()) {
      setFactoryStatus("工厂已同步", "success");
    }
  } catch (error) {
    setFactoryStatus("工厂加载失败", "danger");
    showToast(`Factory 加载失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleCreateBatch(event) {
  event.preventDefault();
  const batchName = $("factoryBatchNameInput").value.trim();
  if (!batchName) {
    showToast("请先填写批次名称", "info");
    return;
  }

  try {
    const batch = await postJSON("/api/batches", {
      batch_name: batchName,
      target_platforms: parsePlatforms($("factoryBatchPlatformsInput").value),
    });
    $("factoryCreateBatchForm").reset();
    showToast(`已创建 batch：${batch.batch_name || batch.batch_id}`, "success");
    state.selectedBatchId = batch.batch_id;
    await refreshAll();
  } catch (error) {
    showToast(`创建 batch 失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleImportTracks(event) {
  event.preventDefault();
  if (!state.selectedBatchId) {
    showToast("请先选择一个 batch", "info");
    return;
  }

  const input = $("factoryTrackFilesInput");
  if (!input.files?.length) {
    showToast("请先选择要导入的音频文件", "info");
    return;
  }

  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }
  formData.append("titles_json", JSON.stringify(parseTitles($("factoryTrackTitlesInput").value)));
  formData.append("artist", $("factoryTrackArtistInput").value.trim());
  formData.append("notes", $("factoryTrackNotesInput").value.trim());
  formData.append("metadata_json", JSON.stringify({ source: "factory_ui" }));

  try {
    const payload = await postForm(`/api/batches/${state.selectedBatchId}/tracks/import`, formData);
    $("factoryImportTracksForm").reset();
    showToast(`已导入 ${payload.imported_count} 首曲目`, "success");
    await loadSummary();
    await loadBatch(state.selectedBatchId, { preserveTrack: false });
    const firstTrackId = payload.imported_tracks?.[0]?.track_id || "";
    if (firstTrackId) {
      await loadTrack(firstTrackId);
    }
  } catch (error) {
    showToast(`导入曲目失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleCreateCoverJob() {
  if (!state.selectedTrackId) {
    showToast("请先选择一个曲目", "info");
    return;
  }
  if (!state.selectedCoverModelId) {
    showToast("请先选择一个可用模型", "info");
    return;
  }

  try {
    const payload = await postJSON(`/api/tracks/${state.selectedTrackId}/cover-jobs`, {
      model_id: state.selectedCoverModelId,
    });
    showToast(payload.message || "翻唱任务已创建，工厂会自动刷新状态", "success");
    await loadTrack(state.selectedTrackId);
  } catch (error) {
    showToast(`创建翻唱任务失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleExtractLyrics() {
  if (!state.selectedTrackId) {
    showToast("请先选择一个曲目", "info");
    return;
  }

  try {
    const payload = await postJSON(`/api/tracks/${state.selectedTrackId}/lyrics/extract`, {
      lyric_text: $("factoryLyricText").value,
      source: "factory_manual_seed",
      metadata: { source: "factory_ui" },
    });
    const document = payload.lyric_document || currentDocument({ lyrics: payload });
    if (document?.text_content) {
      $("factoryLyricText").value = document.text_content;
    }
    state.lyricDraftDirty = false;
    showToast("歌词草稿已生成", "success");
    await loadTrack(state.selectedTrackId);
    await loadSummary();
  } catch (error) {
    showToast(`生成歌词草稿失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleAlignLyrics() {
  if (!state.selectedTrackId) {
    showToast("请先选择一个曲目", "info");
    return;
  }

  try {
    state.lyricDraftDirty = false;
    await postJSON(`/api/tracks/${state.selectedTrackId}/lyrics/align`, {
      lyric_text: $("factoryLyricText").value,
      metadata: { source: "factory_ui" },
    });
    showToast("歌词时间轴版本已生成", "success");
    await loadTrack(state.selectedTrackId);
    await loadSummary();
  } catch (error) {
    showToast(`生成时间轴版本失败：${toErrorMessage(error)}`, "error");
  }
}

async function handlePromoteTimeline(timelineId) {
  if (!state.selectedTrackId || !timelineId) return;
  try {
    await postJSON(`/api/tracks/${state.selectedTrackId}/lyrics/${timelineId}/promote`, {});
    showToast("当前歌词版本已晋级", "success");
    await loadTrack(state.selectedTrackId);
  } catch (error) {
    showToast(`晋级版本失败：${toErrorMessage(error)}`, "error");
  }
}

function openRelativeUrl(relativeUrl) {
  if (!relativeUrl) return;
  const url = relativeUrl.startsWith("http") ? relativeUrl : `${window.location.origin}${relativeUrl}`;
  window.open(url, "_blank");
}

function bindEvents() {
  $("factoryRefreshBtn").addEventListener("click", () => refreshAll());
  $("factoryEngineScanBtn").addEventListener("click", async () => {
    const button = $("factoryEngineScanBtn");
    button.disabled = true;
    try {
      await postJSON("/api/engines/scan?force=true", {});
      showToast("Local AI Engine 已重新扫描", "success");
      await loadEngines();
      await loadRvcModels();
    } catch (error) {
      state.engines = null;
      state.enginesUnavailable = "等待地基接口：/api/engines/scan 暂不可用。";
      renderEngineManager();
      showToast(`引擎扫描暂不可用：${toErrorMessage(error)}`, "info");
    } finally {
      button.disabled = false;
    }
  });
  $("factoryRvcModelsRefreshBtn").addEventListener("click", () => loadRvcModels({ resetPage: true }).catch(() => {}));
  $("factoryRvcModelSearchBtn").addEventListener("click", () => loadRvcModels({ resetPage: true }).catch(() => {}));
  $("factoryRvcModelSearchInput").addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadRvcModels({ resetPage: true }).catch(() => {});
    }
  });
  $("factoryRvcRegisteredFilter").addEventListener("change", () => loadRvcModels({ resetPage: true }).catch(() => {}));
  $("factoryRvcIndexFilter").addEventListener("change", () => loadRvcModels({ resetPage: true }).catch(() => {}));
  $("factoryRvcModelsPrevBtn").addEventListener("click", () => {
    state.rvcModelsOffset = Math.max(0, state.rvcModelsOffset - RVC_MODELS_PAGE_SIZE);
    loadRvcModels().catch(() => {});
  });
  $("factoryRvcModelsNextBtn").addEventListener("click", () => {
    state.rvcModelsOffset += RVC_MODELS_PAGE_SIZE;
    loadRvcModels().catch(() => {});
  });
  $("factoryRvcModelsList").addEventListener("click", event => {
    const button = event.target.closest("[data-import-rvc-model]");
    if (!button || button.disabled) return;
    handleImportRvcModel(button.dataset.importRvcModel || "").catch(() => {});
  });
  $("factorySeparationReloadBtn").addEventListener("click", () => loadSeparationLab().catch(() => {}));
  $("factoryReviewRoutingRefreshBtn")?.addEventListener("click", () => loadFactoryReviewRouting().catch(() => {}));
  $("factoryReviewRoutingToggleBtn")?.addEventListener("click", () => {
    setFactoryDrawerCollapsed("reviewRouting", !state.drawerCollapsed.reviewRouting).catch(() => {});
  });
  $("factoryMaterialLibraryRefreshBtn")?.addEventListener("click", () => loadMaterialLibrary().catch(() => {}));
  $("factoryMaterialLibraryToggleBtn")?.addEventListener("click", () => {
    setFactoryDrawerCollapsed("materialLibrary", !state.drawerCollapsed.materialLibrary).catch(() => {});
  });
  $("factorySeparationRunBtn").addEventListener("click", () => handleSeparationEvalRun().catch(() => {}));
  $("factorySeparationRunsList").addEventListener("click", event => {
    const button = event.target.closest("[data-separation-run]");
    if (!button) return;
    state.selectedSeparationRunId = button.dataset.separationRun || "";
    loadSeparationRunDetail(state.selectedSeparationRunId).catch(() => {});
  });
  $("factorySeparationItemsList").addEventListener("click", event => {
    const button = event.target.closest("[data-separation-item-index]");
    if (!button) return;
    state.selectedSeparationItemIndex = Number(button.dataset.separationItemIndex || 0);
    renderSeparationLab();
  });
  $("factoryTrainingPresetsReloadBtn").addEventListener("click", () => loadTrainingPresets().catch(() => {}));
  $("factoryTrainingPresetGrid").addEventListener("click", event => {
    const button = event.target.closest("[data-training-preset]");
    if (!button) return;
    saveTrainingPresetKey(button.dataset.trainingPreset || "balanced");
    state.trainingEstimate = null;
    renderTrainingTuning();
  });
  $("factoryTrainingEstimateBtn").addEventListener("click", () => handleTrainingEstimate().catch(() => {}));
  $("factoryReloadTracksBtn").addEventListener("click", () => {
    if (state.selectedBatchId) loadBatch(state.selectedBatchId, { preserveTrack: true }).catch(() => {});
  });
  $("factoryReloadTrackBtn").addEventListener("click", () => {
    if (state.selectedTrackId) refreshSelectedTrack({ source: "manual" }).catch(() => {});
  });
  $("factoryCreateBatchForm").addEventListener("submit", handleCreateBatch);
  $("factoryImportTracksForm").addEventListener("submit", handleImportTracks);
  $("factoryExtractLyricsBtn").addEventListener("click", handleExtractLyrics);
  $("factoryAlignLyricsBtn").addEventListener("click", handleAlignLyrics);
  $("factoryCreateCoverJobBtn").addEventListener("click", handleCreateCoverJob);
  $("factoryLyricText").addEventListener("input", () => {
    state.lyricDraftDirty = true;
  });
  $("factoryCoverModelSelect").addEventListener("change", event => {
    state.selectedCoverModelId = event.target.value || "";
    renderTrackCoverControls();
  });

  $("factoryAssetToggleBtn").addEventListener("click", () => {
    setFactoryDrawerCollapsed("asset", !state.drawerCollapsed.asset).catch(() => {});
  });
  $("factoryLyricsToggleBtn").addEventListener("click", () => {
    setFactoryDrawerCollapsed("lyrics", !state.drawerCollapsed.lyrics).catch(() => {});
  });
  $("factoryJobsToggleBtn").addEventListener("click", () => {
    setFactoryDrawerCollapsed("jobs", !state.drawerCollapsed.jobs).catch(() => {});
  });
  $("factoryBatchesToggleBtn").addEventListener("click", () => {
    setFactoryDrawerCollapsed("batches", !state.drawerCollapsed.batches).catch(() => {});
  });
  $("factoryModelAssetsToggleBtn").addEventListener("click", () => {
    setFactoryDrawerCollapsed("modelAssets", !state.drawerCollapsed.modelAssets).catch(() => {});
  });

  $("factoryBatchesList").addEventListener("click", event => {
    const button = event.target.closest("[data-batch-id]");
    if (!button) return;
    stopTrackPolling();
    loadBatch(button.dataset.batchId, { preserveTrack: false }).catch(error => {
      showToast(`加载批次失败：${toErrorMessage(error)}`, "error");
    });
  });

  $("factoryTracksList").addEventListener("click", event => {
    const button = event.target.closest("[data-track-id]");
    if (!button) return;
    loadTrack(button.dataset.trackId).catch(error => {
      showToast(`加载曲目失败：${toErrorMessage(error)}`, "error");
    });
  });

  $("factoryLyricVersions").addEventListener("click", event => {
    const button = event.target.closest("[data-promote-timeline]");
    if (!button) return;
    handlePromoteTimeline(button.dataset.promoteTimeline);
  });

  document.addEventListener("click", event => {
    const studioButton = event.target.closest("[data-studio-url]");
    if (studioButton) {
      window.location.href = studioButton.dataset.studioUrl;
      return;
    }

    const downloadButton = event.target.closest("[data-download-url]");
    if (downloadButton) {
      openRelativeUrl(downloadButton.dataset.downloadUrl);
    }
  });

  window.addEventListener("beforeunload", stopTrackPolling);
  window.addEventListener("storage", event => {
    if (event.key === TEST_RECORDS_VISIBLE_KEY) {
      renderTestRecordsToggle();
      refreshAll().catch(() => {});
    }
  });
  document.addEventListener(TEST_RECORDS_EVENT, () => {
    renderTestRecordsToggle();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopTrackPolling();
    } else {
      syncTrackPolling();
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  renderTestRecordsToggle();
  await Promise.all([
    setFactoryDrawerCollapsed("batches", state.drawerCollapsed.batches, { immediate: true }),
    setFactoryDrawerCollapsed("asset", state.drawerCollapsed.asset, { immediate: true }),
    setFactoryDrawerCollapsed("lyrics", state.drawerCollapsed.lyrics, { immediate: true }),
    setFactoryDrawerCollapsed("jobs", state.drawerCollapsed.jobs, { immediate: true }),
    setFactoryDrawerCollapsed("modelAssets", state.drawerCollapsed.modelAssets, { immediate: true }),
    setFactoryDrawerCollapsed("reviewRouting", state.drawerCollapsed.reviewRouting, { immediate: true }),
    setFactoryDrawerCollapsed("materialLibrary", state.drawerCollapsed.materialLibrary, { immediate: true }),
  ]);
  renderEngineManager();
  renderFactoryReviewRouting();
  renderMaterialLibrary();
  renderModelAssetsDrawer();
  renderRvcModelsPanel();
  renderSeparationLab();
  state.trainingPresets = fallbackTrainingPresets();
  renderTrainingTuning();
  renderBatchList();
  renderTracks();
  renderTrackDetail();
  await refreshAll();
});
