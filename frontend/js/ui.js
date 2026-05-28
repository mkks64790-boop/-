const toastRoot = () => document.getElementById("toastRoot");

const STATUS_META = {
  pending: { label: "排队中", className: "pending" },
  queued: { label: "排队中", className: "pending" },
  processing: { label: "进行中", className: "active" },
  started: { label: "进行中", className: "active" },
  running: { label: "进行中", className: "active" },
  "分离中": { label: "进行中", className: "active" },
  "修音中": { label: "进行中", className: "active" },
  "变声中": { label: "进行中", className: "active" },
  "混音中": { label: "进行中", className: "active" },
  "切片中": { label: "进行中", className: "active" },
  "训练中": { label: "进行中", className: "active" },
  completed: { label: "完成", className: "success" },
  "完成": { label: "完成", className: "success" },
  failed: { label: "失败", className: "failed" },
  "失败": { label: "失败", className: "failed" },
  cancelled: { label: "已取消", className: "cancelled" },
  "已取消": { label: "已取消", className: "cancelled" },
};

const STAGE_META = {
  pending: "待处理",
  upload: "上传",
  job_dispatch: "任务派发",
  job_control: "任务控制",
  cover_preflight: "翻唱预检",
  cover_split: "人声分离",
  cover_pitch: "音高校正",
  cover_voice: "AI 变声",
  cover_mix: "成品混音",
  train_upload: "训练上传",
  train_preflight: "训练预检",
  train_dataset_prepare: "数据集准备",
  train_preprocess: "预处理",
  train_direct_prepare: "直通整理",
  train_pitch_extract: "Pitch 提取",
  train_feature_extract: "特征提取",
  train_core: "核心训练",
  train_index: "索引训练",
  train_register_model: "模型登记",
  failed: "失败",
  cancelled: "已取消",
  done: "完成",
};

const STRATEGY_META = {
  cover_strategy: "AI 翻唱",
  single_long_preprocess: "单文件训练",
  multi_clean_direct: "多文件精训",
};

const JOB_TYPE_META = {
  cover: "翻唱",
  train: "训练",
};

const ARTIFACT_TYPE_META = {
  cover_master: "最终成品",
  train_model_pth: "模型文件 .pth",
  train_model_index: "索引文件 .index",
  vocal: "人声音轨",
  instrumental: "伴奏音轨",
  fixed: "修音人声",
  transformed: "变声人声",
  cover_vocal: "人声音轨",
  cover_instrumental: "伴奏音轨",
  cover_fixed: "修音人声",
  cover_transformed: "变声人声",
};

export function $(id) {
  return document.getElementById(id);
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function statusText(status) {
  return STATUS_META[status]?.label || status || "-";
}

export function stageText(stage) {
  return STAGE_META[stage] || stage || "-";
}

export function strategyLabel(strategyKey) {
  return STRATEGY_META[strategyKey] || strategyKey || "-";
}

export function jobTypeLabel(jobType) {
  return JOB_TYPE_META[jobType] || jobType || "-";
}

export function artifactTypeLabel(artifactType) {
  return ARTIFACT_TYPE_META[artifactType] || artifactType || "-";
}

export function modelAvailabilityText(model = {}) {
  if (model.usable) return "可用";
  if (model.exists) return "已登记";
  return "不可用";
}

export function modelAvailabilityClass(model = {}) {
  if (model.usable) return "success";
  if (model.exists) return "pending";
  return "failed";
}

export function renderStatusPill(status) {
  const meta = STATUS_META[status] || { label: status || "-", className: "pending" };
  return `<span class="status-pill ${meta.className}">${escapeHtml(meta.label)}</span>`;
}

export function renderStagePill(stage, status = "") {
  let className = "active";
  if (stage === "pending" || status === "pending" || status === "queued") {
    className = "pending";
  } else if (stage === "failed" || status === "失败" || status === "failed") {
    className = "failed";
  } else if (stage === "cancelled" || status === "已取消" || status === "cancelled") {
    className = "cancelled";
  } else if (status === "完成" || status === "completed") {
    className = "success";
  }
  return `<span class="stage-pill ${className}">${escapeHtml(stageText(stage))}</span>`;
}

export function renderModelStatePill(model = {}) {
  return `<span class="status-pill ${modelAvailabilityClass(model)}">${escapeHtml(modelAvailabilityText(model))}</span>`;
}

export function renderPathLine(value, { subtle = false, mono = true, emptyText = "-" } = {}) {
  const text = value || emptyText;
  const classes = [
    "artifact-path",
    "path-line",
    subtle ? "subtle" : "",
    mono ? "mono" : "",
  ].filter(Boolean).join(" ");
  return `<div class="${classes}" title="${escapeHtml(text)}"><span class="path-text">${escapeHtml(text)}</span></div>`;
}

export function showToast(message, kind = "info") {
  const root = toastRoot();
  if (!root) return;
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.textContent = message;
  root.appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

export function renderChecks(container, checks = []) {
  if (!container) return;
  if (!checks.length) {
    container.innerHTML = `<div class="detail-empty">当前没有可展示的检查项。</div>`;
    return;
  }
  container.innerHTML = checks.map(item => {
    const ok = Boolean(item.ok);
    const title = item.label || item.check || "未命名检查";
    return `
      <div class="log-item ${ok ? "completed" : "failed"}">
        <strong>${escapeHtml(title)}</strong>
        <div class="log-meta">
          <span>${ok ? "通过" : "失败"}</span>
          ${item.category ? `<span>${escapeHtml(item.category)}</span>` : ""}
          ${item.value ? `<span class="mono">${escapeHtml(item.value)}</span>` : ""}
        </div>
        ${item.detail ? renderPathLine(item.detail, { subtle: true, mono: false }) : ""}
        ${!ok && item.next_step ? renderPathLine(item.next_step, { mono: false }) : ""}
      </div>
    `;
  }).join("");
}

export function slideToggle(element, expand, duration = 180) {
  if (!element) return Promise.resolve(false);

  const shouldExpand = Boolean(expand);
  if (shouldExpand) {
    element.hidden = false;
    element.style.overflow = "hidden";
    element.style.maxHeight = "0px";
    element.style.opacity = "0";
    element.style.display = "block";
    element.getBoundingClientRect();
    element.style.transition = `max-height ${duration}ms ease, opacity ${duration}ms ease`;
    const targetHeight = `${element.scrollHeight}px`;
    requestAnimationFrame(() => {
      element.style.maxHeight = targetHeight;
      element.style.opacity = "1";
    });

    return new Promise(resolve => {
      window.setTimeout(() => {
        element.style.transition = "";
        element.style.maxHeight = "";
        element.style.overflow = "";
        element.style.opacity = "";
        resolve(true);
      }, duration);
    });
  }

  element.style.overflow = "hidden";
  element.style.maxHeight = `${element.scrollHeight}px`;
  element.style.opacity = "1";
  element.getBoundingClientRect();
  element.style.transition = `max-height ${duration}ms ease, opacity ${duration}ms ease`;
  requestAnimationFrame(() => {
    element.style.maxHeight = "0px";
    element.style.opacity = "0";
  });

  return new Promise(resolve => {
    window.setTimeout(() => {
      element.hidden = true;
      element.style.transition = "";
      element.style.maxHeight = "";
      element.style.overflow = "";
      element.style.opacity = "";
      element.style.display = "";
      resolve(false);
    }, duration);
  });
}

export function setEngineChip(online, baseUrl = "") {
  const chip = $("engineChip");
  const text = $("engineChipText");
  if (!chip || !text) return;
  const dot = chip.querySelector(".dot");
  if (dot) dot.className = `dot ${online ? "success" : "warning"}`;
  text.textContent = online
    ? `RVC 在线${baseUrl ? ` · ${baseUrl}` : ""}`
    : `RVC 未就绪${baseUrl ? ` · ${baseUrl}` : ""}`;
}
