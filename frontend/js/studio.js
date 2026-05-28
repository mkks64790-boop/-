import { getJSON, toErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  formatDateTime,
  renderPathLine,
  renderStagePill,
  renderStatusPill,
  showToast,
} from "./ui.js";

const state = {
  jobs: [],
  selectedJobId: "",
  selectedJob: null,
  selectedArtifact: null,
  waveformBars: [],
  rafId: 0,
};

const controlBindings = [
  { inputId: "studioVolume", valueId: "studioVolumeValue", format: value => `${value}%` },
  { inputId: "studioPresence", valueId: "studioPresenceValue", format: value => String(value) },
  { inputId: "studioWarmth", valueId: "studioWarmthValue", format: value => String(value) },
  { inputId: "studioSpace", valueId: "studioSpaceValue", format: value => `${value}%` },
  { inputId: "studioForward", valueId: "studioForwardValue", format: value => String(value) },
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

function renderResourcePicker() {
  $("studioResourceCount").textContent = state.jobs.length
    ? `共 ${state.jobs.length} 个可试听成品`
    : "当前没有可进入修音室的 cover 成品";

  $("studioResourceSelect").innerHTML = state.jobs.length
    ? state.jobs.map(job => `
        <option value="${escapeHtml(job.job_id)}" ${job.job_id === state.selectedJobId ? "selected" : ""}>
          ${escapeHtml(job.voice_name || job.job_id)} · ${escapeHtml(job.job_id)}
        </option>
      `).join("")
    : `<option value="">暂无可用成品</option>`;

  $("studioResourceList").innerHTML = state.jobs.length
    ? state.jobs.map(buildResourceCard).join("")
    : `<div class="studio-resource-empty">还没有已完成的翻唱成品。先回到 Dashboard 创建并完成一个 cover job，再进入修音室。</div>`;
}

function renderEmptyStudio() {
  state.selectedJob = null;
  state.selectedArtifact = null;
  state.selectedJobId = "";
  state.waveformBars = [];
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
  setActionLink("studioDownloadBtn", "", false);
  setActionLink("studioExportDraftBtn", "", false);
  setActionLink("studioOpenArtifactBtn", "", false);
  $("studioMetaGrid").innerHTML = `
    <div class="meta-card"><div class="meta-label">当前状态</div><div class="meta-value">未载入</div></div>
    <div class="meta-card"><div class="meta-label">最终阶段</div><div class="meta-value">-</div></div>
    <div class="meta-card"><div class="meta-label">创建时间</div><div class="meta-value">-</div></div>
    <div class="meta-card"><div class="meta-label">工作目录</div><div class="meta-value mono">-</div></div>
  `;
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

function updateQuery(jobId, artifactId = "") {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  if (artifactId) params.set("artifact_id", artifactId);
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

function syncPlayerUi(job, artifact) {
  const audio = $("studioAudio");
  const playUrl = toAbsoluteUrl(artifact?.download_url || `/api/download/${job.job_id}`);
  const fileName = basename(artifact?.file_path || "final_master.wav");

  state.selectedArtifact = artifact;
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
    const [job, artifactResp] = await Promise.all([
      getJSON(`/api/jobs/${jobId}`),
      getJSON(`/api/jobs/${jobId}/artifacts`),
    ]);

    const artifact = pickPlayableArtifact(jobId, artifactResp.artifacts || [], artifactId);
    state.selectedJob = job;
    renderJobMeta(job, artifact);
    syncPlayerUi(job, artifact);
    updateQuery(jobId, artifact?.artifact_id || "");
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

    if (!jobs.length) {
      renderResourcePicker();
      renderEmptyStudio();
      return;
    }

    const nextJobId = jobs.some(job => job.job_id === state.selectedJobId)
      ? state.selectedJobId
      : jobs.some(job => job.job_id === requestedJobId)
        ? requestedJobId
        : jobs[0].job_id;

    renderResourcePicker();
    await loadJob(nextJobId, { artifactId: requestedArtifactId });
  } catch (error) {
    showToast(`Studio 读取成品列表失败：${toErrorMessage(error)}`, "error");
    $("studioResourceCount").textContent = "成品资源读取失败";
    $("studioResourceSelect").innerHTML = `<option value="">资源读取失败</option>`;
    $("studioResourceList").innerHTML = `<div class="studio-resource-empty">成品资源读取失败，请回到 Dashboard 确认至少存在一个已完成的 cover job。</div>`;
    renderEmptyStudio();
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

document.addEventListener("DOMContentLoaded", async () => {
  bindAudioEvents();
  bindResourceEvents();
  bindControlEvents();
  renderEmptyStudio();
  await refreshResources();
});
