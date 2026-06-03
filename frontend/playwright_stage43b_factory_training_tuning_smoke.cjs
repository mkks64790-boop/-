const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const STAGE41_COVER_JOB_ID = "task_stage41_ce1b32f2";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage43b_factory_training_tuning.png`;
const BROWSER_FALLBACKS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const executablePath = BROWSER_FALLBACKS.find(path => fs.existsSync(path));
    if (!executablePath) throw error;
    return chromium.launch({ headless: true, executablePath });
  }
}

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

function observe(page, pageErrors, unsafeCalls) {
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    const method = request.method();
    if (/\/api\/process\//.test(url) || (method === "POST" && /\/api\/train\b/.test(url))) {
      unsafeCalls.push(`${method} ${url}`);
    }
  });
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const browser = await launchBrowser();
  const pageErrors = [];
  const unsafeCalls = [];

  const dashboard = await browser.newPage({ viewport: { width: 1440, height: 1120 } });
  observe(dashboard, pageErrors, unsafeCalls);
  await gotoPage(dashboard, "/");
  await dashboard.waitForSelector("#taskCenter", { timeout: 15000 });
  const stage41Contract = await dashboard.evaluate(async jobId => {
    const response = await fetch(`/api/jobs/${jobId}`);
    return response.ok ? response.json() : null;
  }, STAGE41_COVER_JOB_ID);
  await dashboard.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, STAGE41_COVER_JOB_ID);
  await dashboard.waitForTimeout(1400);
  const dashboardState = await dashboard.evaluate(() => ({
    actionText: document.querySelector("#jobActionBar")?.innerText || "",
    hasStudioButton: Boolean(document.querySelector("#jobActionBar [data-open-studio]")),
    hasDownloadButton: Boolean(document.querySelector("#jobActionBar [data-artifact-download]")),
    coverCreateDisabled: Boolean(document.querySelector("#coverCreateBtn")?.disabled),
  }));
  await dashboard.close();

  const factory = await browser.newPage({ viewport: { width: 1440, height: 1280 } });
  observe(factory, pageErrors, unsafeCalls);
  await gotoPage(factory, "/factory");
  await factory.waitForSelector("#factoryRvcModelsPanel", { timeout: 15000 });
  await factory.waitForSelector("#factoryTrainingTuningPanel", { timeout: 15000 });
  const factoryInitial = await factory.evaluate(() => ({
    hasRvcPanel: Boolean(document.querySelector("#factoryRvcModelsPanel")),
    hasSearch: Boolean(document.querySelector("#factoryRvcModelSearchInput")),
    hasRegisteredFilter: Boolean(document.querySelector("#factoryRvcRegisteredFilter")),
    hasIndexFilter: Boolean(document.querySelector("#factoryRvcIndexFilter")),
    rvcRenderedCount: document.querySelectorAll("#factoryRvcModelsList .factory-rvc-model-item").length,
    rvcSummary: document.querySelector("#factoryRvcModelsSummary")?.innerText || "",
    hasImportButton: Boolean(document.querySelector("#factoryRvcModelsList [data-import-rvc-model]:not([disabled])")),
    presetCount: document.querySelectorAll("#factoryTrainingPresetGrid [data-training-preset]").length,
    presetText: document.querySelector("#factoryTrainingPresetGrid")?.innerText || "",
    estimateText: document.querySelector("#factoryTrainingEstimateResult")?.innerText || "",
  }));

  await factory.fill("#factoryRvcModelSearchInput", "D_");
  await factory.click("#factoryRvcModelSearchBtn");
  await factory.waitForTimeout(900);
  const firstImport = await factory.$("#factoryRvcModelsList [data-import-rvc-model]:not([disabled])");
  if (firstImport) {
    await firstImport.click();
    await factory.waitForTimeout(900);
  }
  await factory.click('[data-training-preset="quality"]');
  await factory.fill("#factoryTrainingDurationInput", "60");
  await factory.click("#factoryTrainingEstimateBtn");
  await factory.waitForTimeout(900);
  const factoryAfter = await factory.evaluate(() => ({
    rvcRenderedCount: document.querySelectorAll("#factoryRvcModelsList .factory-rvc-model-item").length,
    pageInfo: document.querySelector("#factoryRvcModelsPageInfo")?.innerText || "",
    activePreset: document.querySelector("#factoryTrainingPresetGrid .is-active")?.innerText || "",
    estimateText: document.querySelector("#factoryTrainingEstimateResult")?.innerText || "",
  }));
  await factory.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  await factory.close();

  const mobile = await browser.newPage({ viewport: { width: 900, height: 1050 } });
  observe(mobile, pageErrors, unsafeCalls);
  await gotoPage(mobile, "/factory");
  await mobile.waitForSelector("#factoryTrainingTuningPanel", { timeout: 15000 });
  const mobileState = await mobile.evaluate(() => ({
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    rvcRenderedCount: document.querySelectorAll("#factoryRvcModelsList .factory-rvc-model-item").length,
    presetCount: document.querySelectorAll("#factoryTrainingPresetGrid [data-training-preset]").length,
  }));
  await mobile.close();
  await browser.close();

  const failures = [];
  const canOpenStudio = Boolean(stage41Contract?.can_open_studio || stage41Contract?.studio_url);
  if (canOpenStudio && !dashboardState.hasStudioButton) failures.push("Stage41 cover can open Studio but Dashboard has no Studio button");
  if (!canOpenStudio && !/等待|登记|Studio/.test(dashboardState.actionText)) failures.push("Stage41 cover lacks explicit waiting-for-artifact state");
  if (!dashboardState.coverCreateDisabled) failures.push("Dashboard cover create became enabled without file");
  if (!factoryInitial.hasRvcPanel || !factoryInitial.hasSearch || !factoryInitial.hasRegisteredFilter || !factoryInitial.hasIndexFilter) {
    failures.push("Factory RVC model search/filter UI incomplete");
  }
  if (factoryInitial.rvcRenderedCount > 8 || factoryAfter.rvcRenderedCount > 8) failures.push("RVC model list rendered more than one page");
  if (factoryInitial.presetCount !== 3) failures.push(`training preset count is not 3: ${factoryInitial.presetCount}`);
  if (!/快速|均衡|高质量/.test(factoryInitial.presetText)) failures.push("training preset copy missing");
  if (!/GPU|预计|Epochs|Batch/i.test(factoryAfter.estimateText)) failures.push("training estimate did not render risk/time details");
  if (mobileState.viewportOverflow) failures.push("mobile Factory viewport overflows horizontally");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unexpected train/cover execution calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    stage41Contract: stage41Contract ? {
      job_id: stage41Contract.job_id,
      status: stage41Contract.status,
      can_open_studio: stage41Contract.can_open_studio || false,
      studio_url: stage41Contract.studio_url || "",
      final_artifact_download_url: stage41Contract.final_artifact_download_url || "",
    } : null,
    dashboardState,
    factoryInitial,
    factoryAfter,
    mobileState,
    pageErrors,
    unsafeCalls,
    screenshot: SCREENSHOT_PATH,
  }, null, 2));

  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
