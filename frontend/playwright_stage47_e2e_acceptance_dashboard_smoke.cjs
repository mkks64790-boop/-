const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const DASHBOARD_SCREENSHOT = `${SCREENSHOT_DIR}/stage47_e2e_acceptance_dashboard.png`;
const FACTORY_SCREENSHOT = `${SCREENSHOT_DIR}/stage47_e2e_acceptance_factory.png`;
const STAGE47_EXPECTED_MODEL_NAME = "朱朱_stage47_single_long";
const BROWSER_FALLBACKS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const executablePath = BROWSER_FALLBACKS.find(candidate => fs.existsSync(candidate));
    if (!executablePath) throw error;
    return chromium.launch({ headless: true, executablePath });
  }
}

async function fetchJson(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  const text = await response.text();
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${text.slice(0, 500)}`);
  return JSON.parse(text);
}

function searchText(value = {}) {
  if (!value) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function hasStage47Hint(value = {}) {
  const text = searchText(value);
  return /stage[\s_-]*47/i.test(text) || text.includes(STAGE47_EXPECTED_MODEL_NAME);
}

function normalizeModelsPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.models)) return payload.models;
  if (Array.isArray(payload?.value)) return payload.value;
  return [];
}

function isCompleted(status = "") {
  return status === "completed" || status === "完成";
}

function parseDateValue(value) {
  if (!value) return 0;
  const timestamp = new Date(String(value).replace(" ", "T")).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function sortByNewest(items = []) {
  return [...items].sort((left, right) => {
    const leftTime = parseDateValue(left.updated_at || left.created_at);
    const rightTime = parseDateValue(right.updated_at || right.created_at);
    return rightTime - leftTime;
  });
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

function isStage47TrainingJob(job = {}, models = []) {
  const sourceJobIds = new Set(models.map(model => model.source_job_id).filter(Boolean));
  return (job.job_type === "train" || /^train/i.test(String(job.job_id || "")))
    && (hasStage47Hint(job) || sourceJobIds.has(job.job_id));
}

function isStage47CoverJob(job = {}, models = []) {
  const modelIds = new Set(models.map(model => model.model_id).filter(Boolean));
  return (job.job_type === "cover" || job.job_kind === "cover" || /^cover/i.test(String(job.job_id || "")))
    && (hasStage47Hint(job) || modelIds.has(job.voice_model_id) || modelIds.has(job.model_id));
}

function pickCoverArtifact(artifacts = []) {
  return (
    artifacts.find(item => item.artifact_type === "cover_master" && item.is_final) ||
    artifacts.find(item => item.artifact_type === "cover_master") ||
    artifacts.find(item => item.is_final) ||
    null
  );
}

function artifactPlaybackUrl(artifact = null, coverJob = null) {
  return artifact?.download_url || artifact?.play_url || artifact?.url || coverJob?.final_artifact_download_url || coverJob?.download_url || "";
}

async function getRealStage47State() {
  const jobsResp = await fetchJson("/api/jobs?limit=100&offset=0");
  const modelsPayload = await fetchJson("/api/models");
  const jobs = Array.isArray(jobsResp?.items) ? jobsResp.items : [];
  const models = normalizeModelsPayload(modelsPayload);
  const stage47Models = sortByNewest(models.filter(isStage47Model));
  const model = stage47Models[0] || null;
  const trainingJob = sortByNewest(jobs.filter(job => isStage47TrainingJob(job, stage47Models)))[0] || null;
  let coverJob = sortByNewest(jobs.filter(job => isStage47CoverJob(job, stage47Models)))[0] || null;
  let artifacts = [];
  let artifact = null;

  if (coverJob?.job_id) {
    coverJob = await fetchJson(`/api/jobs/${encodeURIComponent(coverJob.job_id)}`).catch(() => coverJob);
    const artifactResp = await fetchJson(`/api/jobs/${encodeURIComponent(coverJob.job_id)}/artifacts`).catch(() => ({ artifacts: [] }));
    artifacts = artifactResp.artifacts || [];
    artifact = pickCoverArtifact(artifacts);
  }

  const playbackUrl = artifactPlaybackUrl(artifact, coverJob);
  const studioReady = Boolean(playbackUrl && coverJob && (coverJob.can_open_studio || coverJob.studio_url || artifact?.artifact_id));
  return {
    jobs,
    model,
    trainingJob,
    coverJob,
    artifacts,
    artifact,
    playbackUrl,
    studioReady,
  };
}

async function gotoPage(page, pathName) {
  await page.goto(`${BASE_URL}${pathName}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2400);
}

async function waitForFactoryStage47Assets(page, real) {
  await page.waitForFunction(
    ({ hasExpectedModel, modelId, modelName, expectedModelName }) => {
      const summary = document.querySelector("#factoryModelAssetsSummary")?.innerText || "";
      const text = document.querySelector("#factoryModelAssetsList")?.innerText || "";
      const content = `${summary}\n${text}`;

      if (hasExpectedModel) {
        return (
          (modelId && content.includes(modelId)) ||
          (modelName && content.includes(modelName)) ||
          content.includes(expectedModelName) ||
          text.includes("Stage47 实训模型") ||
          /Stage47 实训模型\s*[1-9]\d*\s*个/.test(summary)
        );
      }

      return /Stage47 实训模型\s*0\s*个/.test(summary);
    },
    {
      hasExpectedModel: Boolean(real.model),
      modelId: real.model?.model_id || "",
      modelName: real.model?.model_name || "",
      expectedModelName: STAGE47_EXPECTED_MODEL_NAME,
    },
    { timeout: 30000 },
  );
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const real = await getRealStage47State();
  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const pageErrors = [];
  const unsafeCalls = [];

  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/train\b|\/api\/process\/|\/cover-jobs\b|\/api\/cover\b|\/api\/upload_task\b|\/rvc\/infer\b|\/infer\b/i.test(url)) {
      unsafeCalls.push(`${request.method()} ${url}`);
    }
  });
  page.on("dialog", dialog => dialog.dismiss());

  await gotoPage(page, "/");
  await page.waitForSelector("#stage47E2ePanel", { timeout: 15000 });
  const expectedDashboardText = real.coverJob?.job_id
    || real.model?.model_id
    || real.model?.model_name
    || real.trainingJob?.job_id
    || "等待地基生成真实闭环";
  await page.waitForFunction(
    expected => (document.querySelector("#stage47E2ePanel")?.innerText || "").includes(expected),
    expectedDashboardText,
    { timeout: 20000 },
  );
  const dashboard = await page.evaluate(() => ({
    text: document.querySelector("#stage47E2ePanel")?.innerText || "",
    summary: document.querySelector("#stage47E2eSummary")?.innerText || "",
    training: document.querySelector("#stage47TrainingJobValue")?.innerText || "",
    model: document.querySelector("#stage47ModelValue")?.innerText || "",
    cover: document.querySelector("#stage47CoverJobValue")?.innerText || "",
    studio: document.querySelector("#stage47StudioValue")?.innerText || "",
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));
  await page.screenshot({ path: DASHBOARD_SCREENSHOT, fullPage: true });

  await gotoPage(page, "/factory#factoryModelAssetsDrawer");
  await page.waitForSelector("#factoryModelAssetsDrawer", { timeout: 15000 });
  await waitForFactoryStage47Assets(page, real);
  const factory = await page.evaluate(() => ({
    summary: document.querySelector("#factoryModelAssetsSummary")?.innerText || "",
    text: document.querySelector("#factoryModelAssetsList")?.innerText || "",
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));
  await page.screenshot({ path: FACTORY_SCREENSHOT, fullPage: true });

  let studio = null;
  if (real.studioReady && real.coverJob?.job_id) {
    const studioUrl = real.coverJob.studio_url || `/studio?job_id=${encodeURIComponent(real.coverJob.job_id)}${real.artifact?.artifact_id ? `&artifact_id=${encodeURIComponent(real.artifact.artifact_id)}` : ""}`;
    await gotoPage(page, studioUrl);
    await page.waitForSelector("#studioAudio", { timeout: 15000 });
    studio = await page.evaluate(() => ({
      text: document.body.innerText || "",
      audioSrc: document.querySelector("#studioAudio")?.currentSrc || document.querySelector("#studioAudio")?.src || "",
      downloadHref: document.querySelector("#studioSummaryDownloadBtn")?.href || document.querySelector("#studioDownloadBtn")?.href || "",
      playDisabled: Boolean(document.querySelector("#studioPlayToggleBtn")?.disabled),
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    }));
  }

  await page.setViewportSize({ width: 900, height: 1050 });
  await gotoPage(page, "/");
  const mobile = await page.evaluate(() => ({
    hasPanel: Boolean(document.querySelector("#stage47E2ePanel")),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));

  await browser.close();

  const failures = [];
  const hasAnyStage47 = Boolean(real.trainingJob || real.model || real.coverJob);
  if (!dashboard.text.includes("Stage47")) failures.push("Dashboard Stage47 panel missing text");
  if (dashboard.overflow) failures.push("Dashboard desktop viewport overflows horizontally");
  if (!hasAnyStage47) {
    if (!dashboard.summary.includes("等待地基生成真实闭环")) failures.push("empty real state does not render waiting message");
    if (/可进入 Studio|Stage47 短 smoke \/ 完整 cover/.test(dashboard.text)) failures.push("empty real state claims Stage47 Studio success");
    if (dashboard.training !== "-" || dashboard.model !== "-" || dashboard.cover !== "-") failures.push("empty real state renders fake Stage47 ids");
  }
  if (real.trainingJob && !dashboard.training.includes(real.trainingJob.job_id)) failures.push(`real Stage47 training job not rendered: ${real.trainingJob.job_id}`);
  if (real.model && !(dashboard.model.includes(real.model.model_id) || dashboard.model.includes(real.model.model_name))) failures.push(`real Stage47 model not rendered: ${real.model.model_id}`);
  if (real.coverJob && !dashboard.cover.includes(real.coverJob.job_id)) failures.push(`real Stage47 cover job not rendered: ${real.coverJob.job_id}`);
  if (real.coverJob && isCompleted(real.coverJob.status) && !real.playbackUrl && !dashboard.studio.includes("后端缺少播放 URL")) {
    failures.push("completed Stage47 cover without artifact URL is not labeled as backend missing playback URL");
  }
  if (real.studioReady && !dashboard.studio.includes("可进入 Studio")) failures.push("real playable Stage47 cover does not mark Studio ready");

  if (real.model) {
    if (!factory.text.includes("Stage47 实训模型")) failures.push("Factory does not tag real Stage47 model");
    if (!factory.text.includes("pth：") || !factory.text.includes("index：") || !factory.text.includes("cover：")) {
      failures.push("Factory Stage47 model facts are incomplete");
    }
  } else if (!/Stage47 实训模型 0 个/.test(factory.summary)) {
    failures.push("Factory does not honestly show zero Stage47 models");
  }
  if (factory.overflow) failures.push("Factory desktop viewport overflows horizontally");

  if (real.studioReady) {
    if (!studio?.text.includes("Stage47 短 smoke / 完整 cover")) failures.push("Studio does not mark Stage47 cover scope");
    if (!studio?.audioSrc && !studio?.downloadHref) failures.push("Studio playable artifact has no audio/download URL");
    if (studio?.playDisabled) failures.push("Studio play button is disabled for real Stage47 playable artifact");
    if (studio?.overflow) failures.push("Studio desktop viewport overflows horizontally");
  }
  if (!mobile.hasPanel) failures.push("mobile Dashboard Stage47 panel missing");
  if (mobile.overflow) failures.push("mobile Dashboard viewport overflows horizontally");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe training/RVC/cover calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    realApi: {
      trainingJobId: real.trainingJob?.job_id || "",
      modelId: real.model?.model_id || "",
      modelName: real.model?.model_name || "",
      coverJobId: real.coverJob?.job_id || "",
      coverStatus: real.coverJob?.status || "",
      artifactId: real.artifact?.artifact_id || "",
      playbackUrl: real.playbackUrl || "",
      studioReady: real.studioReady,
    },
    dashboard,
    factory,
    studio,
    mobile,
    pageErrors,
    unsafeCalls,
    screenshots: {
      dashboard: DASHBOARD_SCREENSHOT,
      factory: FACTORY_SCREENSHOT,
    },
  }, null, 2));

  if (failures.length) throw new Error(failures.join("; "));
})();
