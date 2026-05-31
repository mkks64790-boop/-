import { getJSON } from "./api.js";
import { refreshDiagnostics, getDiagnosticsState, initDiagnostics } from "./diagnostics.js";
import { initCoverCreate, syncCoverAvailability } from "./cover.js";
import { initJobs, refreshJobs } from "./jobs.js";
import { getModelsState, getSelectedCoverModelId, initModels, refreshModels } from "./models.js";
import { initTrainCreate, syncTrainAvailability } from "./train.js";
import { $, setEngineSummary, showToast } from "./ui.js";

let refreshInFlight = null;
let queuedFocusJobId = null;
let lastEngineSummary = null;
let engineUsageExpanded = false;

const MOBILE_TAB_STORAGE_KEY = "feishark.mobile-tab";
const MOBILE_TABS = new Set(["dashboard", "models", "monitor"]);
let mobileTab = "dashboard";

async function refreshHealth() {
  const data = await getJSON("/api/health");
  lastEngineSummary = data.engine || data.rvc || {};
  setEngineSummary(lastEngineSummary);
  syncEngineActions();
}

function shouldPauseAutoRefresh() {
  if (document.hidden) return true;
  const active = document.activeElement;
  if (!active) return false;
  if (active.closest?.("form")) return true;
  if (active.closest?.("#jobDetailPanel")) return true;
  if (active.closest?.(".mobile-tabbar")) return true;
  const tagName = String(active.tagName || "").toLowerCase();
  return ["input", "textarea", "select", "button"].includes(tagName) || Boolean(active.closest?.("[contenteditable='true']"));
}

function getStoredMobileTab() {
  try {
    const stored = window.localStorage.getItem(MOBILE_TAB_STORAGE_KEY);
    return MOBILE_TABS.has(stored) ? stored : "dashboard";
  } catch {
    return "dashboard";
  }
}

function setMobileTab(tab, { persist = true } = {}) {
  mobileTab = MOBILE_TABS.has(tab) ? tab : "dashboard";
  document.body.dataset.mobileTab = mobileTab;

  const buttons = document.querySelectorAll("[data-mobile-tab-target]");
  buttons.forEach(button => {
    const active = button.dataset.mobileTabTarget === mobileTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  if (persist) {
    try {
      window.localStorage.setItem(MOBILE_TAB_STORAGE_KEY, mobileTab);
    } catch {
      // Ignore storage failures in private browsing modes.
    }
  }
}

function initMobileTabs() {
  setMobileTab(getStoredMobileTab(), { persist: false });

  document.querySelectorAll("[data-mobile-tab-target]").forEach(button => {
    button.addEventListener("click", () => setMobileTab(button.dataset.mobileTabTarget));
  });
}

async function copyEngineAddress() {
  const baseUrl = lastEngineSummary?.base_url || "";
  if (!baseUrl) {
    showToast("当前没有可复制的引擎地址", "info");
    return;
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(baseUrl);
    } else {
      const temp = document.createElement("textarea");
      temp.value = baseUrl;
      temp.setAttribute("readonly", "true");
      temp.style.position = "fixed";
      temp.style.opacity = "0";
      document.body.appendChild(temp);
      temp.select();
      document.execCommand("copy");
      temp.remove();
    }
    showToast("已复制引擎地址", "success");
  } catch {
    showToast("复制失败，请手动复制引擎地址", "error");
  }
}

function syncEngineActions() {
  const openBtn = $("engineOpenBtn");
  const copyBtn = $("engineCopyBtn");
  const toggleBtn = $("engineUsageToggleBtn");
  const panel = $("engineUsagePanel");
  if (openBtn) {
    openBtn.disabled = !lastEngineSummary?.online || !lastEngineSummary?.base_url;
  }
  if (copyBtn) {
    copyBtn.disabled = !lastEngineSummary?.base_url;
  }
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", String(engineUsageExpanded));
    toggleBtn.textContent = engineUsageExpanded ? "收起用途 ▴" : "查看用途 ▾";
  }
  if (panel) {
    panel.hidden = !engineUsageExpanded;
  }
}

async function setEngineUsageExpanded(nextExpanded, { immediate = false } = {}) {
  engineUsageExpanded = Boolean(nextExpanded);
  const panel = $("engineUsagePanel");
  const toggleBtn = $("engineUsageToggleBtn");
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", String(engineUsageExpanded));
    toggleBtn.textContent = engineUsageExpanded ? "收起用途 ▴" : "查看用途 ▾";
  }
  if (!panel) return;
  panel.hidden = !engineUsageExpanded;
  panel.style.maxHeight = "";
  panel.style.overflow = "";
  panel.style.opacity = "";
  panel.style.display = "";
}

function bindEngineActions() {
  $("engineOpenBtn")?.addEventListener("click", () => {
    const baseUrl = lastEngineSummary?.base_url || "";
    if (!lastEngineSummary?.online || !baseUrl) return;
    window.open(baseUrl, "_blank", "noopener,noreferrer");
  });

  $("engineCopyBtn")?.addEventListener("click", () => {
    copyEngineAddress().catch(() => {});
  });

  $("engineUsageToggleBtn")?.addEventListener("click", () => {
    setEngineUsageExpanded(!engineUsageExpanded).catch(() => {});
  });

  setEngineUsageExpanded(false, { immediate: true }).catch(() => {});
}

async function runWorkspaceRefresh(focusJobId = null) {
  await refreshModels();
  const currentModelId = getSelectedCoverModelId() || "v_001";
  const [jobsResult] = await Promise.all([
    refreshJobs({ focusJobId }),
    refreshDiagnostics(currentModelId),
    refreshHealth(),
  ]);
  if (jobsResult?.modelsMayBeStale) {
    await refreshModels();
    await refreshDiagnostics(getSelectedCoverModelId() || "v_001");
  }
  syncCoverAvailability(getDiagnosticsState(), getModelsState());
  await syncTrainAvailability();
}

export async function refreshWorkspace(focusJobId = null) {
  if (refreshInFlight) {
    queuedFocusJobId = focusJobId || queuedFocusJobId;
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    try {
      await runWorkspaceRefresh(focusJobId);
    } finally {
      refreshInFlight = null;
      if (queuedFocusJobId) {
        const nextFocus = queuedFocusJobId;
        queuedFocusJobId = null;
        await refreshWorkspace(nextFocus);
      }
    }
  })();

  return refreshInFlight;
}

function bindWorkspaceEvents() {
  const onJobCreated = async (jobId) => {
    await refreshWorkspace(jobId);
  };

  initMobileTabs();
  bindEngineActions();
  initJobs();
  initModels();
  initDiagnostics(() => getSelectedCoverModelId() || "v_001");
  initCoverCreate(onJobCreated);
  initTrainCreate(onJobCreated);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindWorkspaceEvents();
  document.addEventListener("feishark:models-changed", () => {
    refreshWorkspace().catch(() => {});
  });
  document.addEventListener("feishark:train-model-registered", () => {
    refreshModels()
      .then(() => refreshDiagnostics(getSelectedCoverModelId() || "v_001"))
      .then(() => {
        syncCoverAvailability(getDiagnosticsState(), getModelsState());
      })
      .catch(() => {});
  });
  window.addEventListener("storage", event => {
    if (event.key === MOBILE_TAB_STORAGE_KEY && event.newValue && MOBILE_TABS.has(event.newValue)) {
      setMobileTab(event.newValue, { persist: false });
    }
  });
  await refreshWorkspace().catch(() => {});
  window.setInterval(() => {
    if (shouldPauseAutoRefresh()) return;
    refreshWorkspace().catch(() => {});
  }, 15000);
});
