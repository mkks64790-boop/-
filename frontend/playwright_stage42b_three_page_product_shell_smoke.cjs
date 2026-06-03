const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const STAGE41_COVER_JOB_ID = "task_stage41_ce1b32f2";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage42b_three_page_product_shell.png`;
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

async function gotoProductPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
}

async function newObservedPage(browser, viewport, pageErrors, unsafeCalls) {
  const context = await browser.newContext({ viewport });
  return newObservedPageInContext(context, pageErrors, unsafeCalls);
}

async function newObservedPageInContext(context, pageErrors, unsafeCalls) {
  const page = await context.newPage();
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    const method = request.method();
    if (/\/api\/process\//.test(url) || (method === "POST" && /\/api\/train\b/.test(url))) {
      unsafeCalls.push(`${method} ${url}`);
    }
  });
  return page;
}

async function inspectOptionalStage41Cover(page) {
  return page.evaluate(async jobId => {
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) return { available: false, status: response.status };
      const job = await response.json();
      const status = String(job.status || "").toLowerCase();
      const completed = status === "completed" || job.status === "完成" || job.status === "已完成";
      return {
        available: true,
        jobType: job.job_type || "",
        status: job.status || "",
        completed,
        canOpenStudio: Boolean(job.can_open_studio || job.final_artifact_download_url),
      };
    } catch (error) {
      return { available: false, error: String(error) };
    }
  }, STAGE41_COVER_JOB_ID);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const browser = await launchBrowser();
  const pageErrors = [];
  const unsafeCalls = [];

  let page = await newObservedPage(browser, { width: 1440, height: 1120 }, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/");
  await page.waitForSelector("#taskCenter", { timeout: 10000 });
  const dashboard = await page.evaluate(() => ({
    hasTaskCenter: Boolean(document.querySelector("#taskCenter")),
    hasCreateCenter: Boolean(document.querySelector("#entryCenter")),
    hasCoverEntry: Boolean(document.querySelector("#coverCreateForm")),
    hasSingleTrainEntry: Boolean(document.querySelector("#singleTrainCreateForm")),
    hasMultiTrainEntry: Boolean(document.querySelector("#multiTrainCreateForm")),
    coverCreateDisabled: Boolean(document.querySelector("#coverCreateBtn")?.disabled),
    artifactsHidden: Boolean(document.querySelector("#jobArtifactsBody")?.hidden),
    technicalHidden: Boolean(document.querySelector("#jobTechnicalBody")?.hidden),
    stageLogsHidden: Boolean(document.querySelector("#jobStageLogsBody")?.hidden),
    modelInventoryHidden: Boolean(document.querySelector("#modelsInventoryBody")?.hidden),
    diagnosticsTextLength: document.querySelector("#diagnosticsPanel")?.innerText.length || 0,
  }));

  const stage41 = await inspectOptionalStage41Cover(page);
  let stage41StudioAction = { checked: false };
  if (stage41.available && stage41.jobType === "cover" && stage41.completed && stage41.canOpenStudio) {
    await page.evaluate(jobId => {
      document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
    }, STAGE41_COVER_JOB_ID);
    await page.waitForTimeout(1200);
    stage41StudioAction = await page.evaluate(() => ({
      checked: true,
      actionText: document.querySelector("#jobActionBar")?.innerText || "",
      hasStudioButton: Boolean(document.querySelector("#jobActionBar [data-open-studio]")),
    }));
  }
  await page.close();

  page = await newObservedPage(browser, { width: 1440, height: 1120 }, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/factory");
  await page.waitForSelector("#factoryEnginePanel", { timeout: 10000 });
  await page.waitForTimeout(1000);
  const factoryBeforeScan = await page.evaluate(() => ({
    hasEnginePanel: Boolean(document.querySelector("#factoryEnginePanel")),
    hasScanButton: Boolean(document.querySelector("#factoryEngineScanBtn")),
    engineSummary: document.querySelector("#factoryEngineSummary")?.innerText || "",
    engineCardCount: document.querySelectorAll("#factoryEngineGrid .engine-manager-card").length,
    engineText: document.querySelector("#factoryEngineGrid")?.innerText || "",
    modelAssetsCollapsed: document.querySelector("#factoryModelAssetsDrawer")?.dataset.collapsed || "",
    modelAssetsHidden: Boolean(document.querySelector("#factoryModelAssetsBody")?.hidden),
  }));
  await page.click("#factoryEngineScanBtn");
  await page.waitForFunction(() => !document.querySelector("#factoryEngineScanBtn")?.disabled, null, { timeout: 6000 }).catch(() => {});
  const factoryAfterScan = await page.evaluate(() => ({
    scanButtonDisabled: Boolean(document.querySelector("#factoryEngineScanBtn")?.disabled),
    engineSummary: document.querySelector("#factoryEngineSummary")?.innerText || "",
    engineCardCount: document.querySelectorAll("#factoryEngineGrid .engine-manager-card").length,
    engineText: document.querySelector("#factoryEngineGrid")?.innerText || "",
  }));
  await page.close();

  page = await newObservedPage(browser, { width: 1440, height: 1120 }, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/studio");
  await page.waitForSelector("#studioEffectRack", { timeout: 10000 });
  await page.waitForTimeout(1000);
  const studio = await page.evaluate(() => ({
    hasPlayer: Boolean(document.querySelector("#studioAudio")),
    hasResourcePicker: Boolean(document.querySelector("#studioResourceSelect")),
    hasEffectRack: Boolean(document.querySelector("#studioEffectRack")),
    hasExportButton: Boolean(document.querySelector("#studioEffectRackExportBtn")),
    libraryCollapsed: document.querySelector("#studioLibraryDrawer")?.dataset.collapsed || "",
    libraryHidden: Boolean(document.querySelector("#studioLibraryBody")?.hidden),
    technicalCollapsed: document.querySelector("#studioTechnicalDrawer")?.dataset.collapsed || "",
    technicalHidden: Boolean(document.querySelector("#studioTechnicalBody")?.hidden),
    statusText: document.querySelector("#studioStatusText")?.innerText || "",
    trackTitle: document.querySelector("#studioTrackTitle")?.innerText || "",
  }));

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  await page.close();

  const mobileDashboardContext = await browser.newContext({ viewport: { width: 900, height: 1050 } });
  page = await newObservedPageInContext(mobileDashboardContext, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/");
  await page.waitForSelector(".mobile-tabbar", { timeout: 10000 });
  await page.click('[data-mobile-tab-target="models"]');
  await page.waitForTimeout(300);
  const storedMobileTab = await page.evaluate(() => window.localStorage.getItem("feishark.mobile-tab") || "");
  await page.close();
  page = await newObservedPageInContext(mobileDashboardContext, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/");
  await page.waitForSelector(".mobile-tabbar", { timeout: 10000 });
  const mobileDashboard = await page.evaluate(() => ({
    hasTabbar: Boolean(document.querySelector(".mobile-tabbar")),
    activeTab: document.body.dataset.mobileTab || "",
    storedMobileTab: window.localStorage.getItem("feishark.mobile-tab") || "",
    modelInventoryHidden: Boolean(document.querySelector("#modelsInventoryBody")?.hidden),
    stageLogsHidden: Boolean(document.querySelector("#jobStageLogsBody")?.hidden),
    artifactsHidden: Boolean(document.querySelector("#jobArtifactsBody")?.hidden),
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));
  mobileDashboard.storedBeforeReopen = storedMobileTab;
  await page.close();
  await mobileDashboardContext.close();

  page = await newObservedPage(browser, { width: 900, height: 1050 }, pageErrors, unsafeCalls);
  await gotoProductPage(page, "/factory");
  await page.waitForSelector("#factoryModelAssetsDrawer", { timeout: 10000 });
  const mobileFactory = await page.evaluate(() => ({
    modelAssetsCollapsed: document.querySelector("#factoryModelAssetsDrawer")?.dataset.collapsed || "",
    modelAssetsHidden: Boolean(document.querySelector("#factoryModelAssetsBody")?.hidden),
    engineGridColumns: getComputedStyle(document.querySelector("#factoryEngineGrid")).gridTemplateColumns,
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));
  await page.close();

  await browser.close();

  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unexpected job execution calls: ${unsafeCalls.join(" | ")}`);
  if (!dashboard.hasTaskCenter || !dashboard.hasCreateCenter) failures.push("Dashboard task/create centers missing");
  if (!dashboard.hasCoverEntry || !dashboard.hasSingleTrainEntry || !dashboard.hasMultiTrainEntry) {
    failures.push("Dashboard cover/train creation entries incomplete");
  }
  if (!dashboard.coverCreateDisabled) failures.push("Cover create button should stay disabled without a selected audio file");
  if (!dashboard.artifactsHidden || !dashboard.technicalHidden || !dashboard.stageLogsHidden) {
    failures.push("Dashboard long detail drawers are not collapsed by default");
  }
  if (!dashboard.modelInventoryHidden) failures.push("Dashboard model inventory should remain collapsed by default");
  if (stage41StudioAction.checked && !stage41StudioAction.hasStudioButton) {
    failures.push("Stage41 completed cover is available but Dashboard did not expose Studio entry");
  }
  if (!factoryBeforeScan.hasEnginePanel || !factoryBeforeScan.hasScanButton) failures.push("Factory Engine Manager shell missing");
  if (factoryBeforeScan.engineCardCount < 1) failures.push("Factory Engine Manager did not render any status/fallback card");
  if (!factoryBeforeScan.modelAssetsHidden || factoryBeforeScan.modelAssetsCollapsed !== "true") {
    failures.push("Factory model assets drawer should be collapsed by default");
  }
  if (factoryAfterScan.scanButtonDisabled) failures.push("Factory engine scan button stayed disabled");
  if (factoryAfterScan.engineCardCount < 1) failures.push("Factory Engine Manager lost cards after scan");
  if (!studio.hasPlayer || !studio.hasResourcePicker || !studio.hasEffectRack || !studio.hasExportButton) {
    failures.push("Studio product shell player/resource/effect-rack controls missing");
  }
  if (!studio.libraryHidden || studio.libraryCollapsed !== "true") failures.push("Studio library drawer should stay collapsed by default");
  if (!studio.technicalHidden || studio.technicalCollapsed !== "true") failures.push("Studio technical drawer should stay collapsed by default");
  if (!mobileDashboard.hasTabbar || mobileDashboard.activeTab !== "models") {
    failures.push(`Mobile Dashboard tab state was not preserved after refresh: ${mobileDashboard.activeTab}`);
  }
  if (!mobileDashboard.modelInventoryHidden || !mobileDashboard.stageLogsHidden || !mobileDashboard.artifactsHidden) {
    failures.push("Mobile Dashboard drawers did not remain collapsed after refresh");
  }
  if (mobileDashboard.viewportOverflow || mobileFactory.viewportOverflow) failures.push("Mobile viewport has horizontal overflow");
  if (!mobileFactory.modelAssetsHidden || mobileFactory.modelAssetsCollapsed !== "true") {
    failures.push("Mobile Factory model assets drawer did not remain collapsed");
  }

  console.log(JSON.stringify({
    dashboard,
    stage41,
    stage41StudioAction,
    factoryBeforeScan,
    factoryAfterScan,
    studio,
    mobileDashboard,
    mobileFactory,
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
