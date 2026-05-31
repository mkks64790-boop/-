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
const TRACK_POLL_INTERVAL_MS = 4000;

const TRACK_STATUS_META = {
  imported: { label: "已导入", className: "pending" },
  draft: { label: "草稿", className: "pending" },
  lyrics_ready: { label: "歌词就绪", className: "success" },
  cover_pending: { label: "翻唱排队", className: "pending" },
  cover_processing: { label: "翻唱处理中", className: "active" },
  cover_ready: { label: "成品就绪", className: "success" },
  cover_failed: { label: "翻唱失败", className: "failed" },
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
  selectedCoverModelId: "",
  trackPollTimer: 0,
  trackPollInFlight: false,
  renderedTrackId: "",
  lyricDraftDirty: false,
  drawerCollapsed: {
    batches: false,
    asset: Boolean(loadUiState(FACTORY_ASSET_COLLAPSED_KEY, false)),
    lyrics: Boolean(loadUiState(FACTORY_LYRICS_COLLAPSED_KEY, true)),
    jobs: Boolean(loadUiState(FACTORY_JOBS_COLLAPSED_KEY, true)),
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
  return `
    <div class="factory-inline-note">
      ${renderModelOriginPill(job.voice_model_origin_kind || "")}
      <span>${escapeHtml(sourceSummary)}</span>
      ${sourceJobId ? `<span class="mono">${escapeHtml(sourceJobId)}</span>` : ""}
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
    hint.textContent = "当前没有可用模型，请先回到 Dashboard 导入或重扫模型。";
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
    hint.textContent = "先选择一个曲目，再从当前 track 直接发起 cover job。";
    return;
  }

  if (hasActive) {
    hint.textContent = "当前曲目已有进行中的关联任务，Factory 会自动刷新状态。";
    return;
  }

  hint.textContent = `将直接复用 ${basename(track.source_audio_path || "")} 创建 cover job，不再重复上传源音频。`;
}

function buildTrackJobSummary(job) {
  if (isCompletedStatus(job.status)) {
    return job.can_open_studio
      ? "成品已就绪，可直接进入 Studio 或下载最终成品。"
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
        ${completed.can_open_studio ? `<button class="primary-btn warm" type="button" data-studio-url="${escapeHtml(completed.studio_url || "")}">进入 Studio</button>` : ""}
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
                ? escapeHtml(`当前仍按最新完成版本 ${fallbackLabel} 作为默认工作流；如需固定较旧版本，请进入 Studio 手动指定当前主成品。`)
                : "这个 Track 还没有可指定的完成态成品，先跑通至少一个 cover 版本。"
            }
          </p>
        </div>
        <div class="detail-summary-badges">
          <span class="tag warn">未指定</span>
        </div>
      </div>
      <div class="detail-summary-foot">
        ${latestCompleted ? "未手动指定时，Factory / Studio 仍会优先按最新完成版本继续工作。" : "完成后即可在 Studio 历史区切换真正采用的版本。"}
      </div>
      ${
        latestCompleted
          ? `
            <div class="panel-actions">
              ${latestCompleted.can_open_studio ? `<button class="ghost-btn" type="button" data-studio-url="${escapeHtml(latestCompleted.studio_url || "")}">进入 Studio 指定主成品</button>` : ""}
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
              ? `当前采用的是手动指定版本 ${masterLabel}。它不是最新完成版本，但会被 Factory 和 Studio 视为这个 Track 的当前主成品。`
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
      ${master.can_open_studio ? `<button class="primary-btn warm" type="button" data-studio-url="${escapeHtml(master.studio_url || "")}">进入 Studio</button>` : ""}
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
    summary.textContent = "当前还没有关联任务，可先选择模型并发起一个 cover job。";
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
        ${job.can_open_studio ? `<button class="ghost-btn" type="button" data-studio-url="${escapeHtml(job.studio_url || "")}">进入 Studio</button>` : ""}
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
      ? "最新成品已就绪，可直接进入 Studio 或下载。"
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
        ? `当前任务正在 ${stageText(active.current_stage || "pending")}，Factory 会自动刷新当前曲目状态。`
        : completed
          ? "最新成品已就绪，可直接进入 Studio 或下载。"
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
      key: null,
      openLabel: "收起批次 ▴",
      closedLabel: "展开批次 ▾",
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
      getJSON(`/api/tracks/${trackId}/jobs?limit=10&offset=0`),
    ]);

    if (state.selectedTrackId !== trackId) return;
    state.trackDetail = trackDetail;
    state.trackJobs = jobPayload.items || [];
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
  state.summary = await getJSON("/api/factory/summary");
  setSummary(state.summary);
}

async function loadCoverModels() {
  const models = await getJSON("/api/models");
  state.coverModels = Array.isArray(models) ? models : [];
  const nextValue = state.coverModels.some(item => item.model_id === state.selectedCoverModelId)
    ? state.selectedCoverModelId
    : state.coverModels[0]?.model_id || "";
  state.selectedCoverModelId = nextValue;
  renderTrackCoverControls();
}

async function loadBatches({ keepSelection = true } = {}) {
  const response = await getJSON("/api/batches?limit=100&offset=0");
  state.batches = response.items || [];
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
    await setFactoryDrawerCollapsed("batches", false, { immediate: true });
  }
}

async function loadBatch(batchId, { preserveTrack = true } = {}) {
  if (!batchId) return;
  const previousTrackId = state.selectedTrackId;
  state.selectedBatchId = batchId;
  state.batchDetail = await getJSON(`/api/batches/${batchId}`);
  renderBatchList();
  renderTracks();
  await setFactoryDrawerCollapsed("batches", true, { immediate: true });

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
    setFactoryStatus("正在刷新 Factory 数据", "warning");
    await loadSummary();
    await loadCoverModels();
    await loadBatches({ keepSelection: true });
    if (!activeTrackJob()) {
      setFactoryStatus("Factory 已同步", "success");
    }
  } catch (error) {
    setFactoryStatus("Factory 加载失败", "danger");
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
    showToast(payload.message || "翻唱任务已创建，Factory 会自动刷新状态", "success");
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
  await Promise.all([
    setFactoryDrawerCollapsed("batches", state.drawerCollapsed.batches, { immediate: true }),
    setFactoryDrawerCollapsed("asset", state.drawerCollapsed.asset, { immediate: true }),
    setFactoryDrawerCollapsed("lyrics", state.drawerCollapsed.lyrics, { immediate: true }),
    setFactoryDrawerCollapsed("jobs", state.drawerCollapsed.jobs, { immediate: true }),
  ]);
  renderBatchList();
  renderTracks();
  renderTrackDetail();
  await refreshAll();
});
