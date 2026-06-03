const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const DASHBOARD_SCREENSHOT = `${SCREENSHOT_DIR}/stage50_review_routing_dashboard.png`;
const STUDIO_SCREENSHOT = `${SCREENSHOT_DIR}/stage50_review_routing_studio.png`;
const FACTORY_SCREENSHOT = `${SCREENSHOT_DIR}/stage50_review_routing_factory.png`;
const STAGE47_JOB_ID = "task_b2272d133fff";
const STAGE47_ARTIFACT_ID = "art_f99f7e4afb10";
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

function pickStudioTarget(queuePayload = {}) {
  const items = Array.isArray(queuePayload.items) ? queuePayload.items : [];
  const item = items.find(candidate => candidate.quality_verdict !== "blocked_auto" && candidate.studio_url && candidate.artifact_id)
    || items.find(candidate => candidate.quality_verdict !== "blocked_auto" && candidate.job_id && candidate.artifact_id)
    || items.find(candidate => candidate.studio_url && candidate.artifact_id)
    || items.find(candidate => candidate.job_id && candidate.artifact_id)
    || null;
  if (item) {
    return {
      jobId: item.job_id,
      artifactId: item.artifact_id,
      studioUrl: item.studio_url || `/studio?job_id=${encodeURIComponent(item.job_id)}&artifact_id=${encodeURIComponent(item.artifact_id)}`,
    };
  }
  return {
    jobId: STAGE47_JOB_ID,
    artifactId: STAGE47_ARTIFACT_ID,
    studioUrl: `/studio?job_id=${encodeURIComponent(STAGE47_JOB_ID)}&artifact_id=${encodeURIComponent(STAGE47_ARTIFACT_ID)}`,
  };
}

async function collectPageState(page) {
  return page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    bodyText: document.body.innerText,
    reviewQueuePanel: Boolean(document.querySelector("#dashboardReviewQueuePanel")),
    reviewQueueStatus: document.querySelector("#dashboardReviewQueueStatus")?.innerText || "",
    studioNextAction: Boolean(document.querySelector("#studioReviewNextAction")),
    studioRouteLabel: document.querySelector("#studioReviewRouteLabel")?.innerText || "",
    factoryRoutingPanel: Boolean(document.querySelector("#factoryReviewRoutingPanel")),
    factoryRoutingSummary: document.querySelector("#factoryReviewRoutingSummary")?.innerText || "",
    factoryRoutingBodyHidden: Boolean(document.querySelector("#factoryReviewRoutingBody")?.hidden),
  }));
}

async function waitForLoadedText(page, selector, pattern, label) {
  await page.waitForFunction(
    ({ selector, source }) => {
      const text = document.querySelector(selector)?.innerText || "";
      return new RegExp(source).test(text) && !text.includes("正在读取");
    },
    { selector, source: pattern.source },
    { timeout: 30000 },
  ).catch(error => {
    throw new Error(`${label} did not finish loading: ${error.message}`);
  });
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const queuePayload = await fetchJson("/api/reviews/artifacts?limit=100");
  const target = pickStudioTarget(queuePayload);

  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const pageErrors = [];
  const unsafeCalls = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/train\b|\/api\/process\/|\/cover-jobs\b|\/api\/cover\b|\/api\/upload_task\b|\/rvc\/infer\b|\/infer\b|\/api\/separation\/eval\/run\b/i.test(url)) {
      unsafeCalls.push(`${request.method()} ${url}`);
    }
  });

  await page.goto(BASE_URL, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#dashboardReviewQueuePanel", { timeout: 20000 });
  await waitForLoadedText(page, "#dashboardReviewQueueStatus", /Quality gate|Real review queue|已读取|队列为空|真实验收队列为空|读取失败|等待后端契约/, "Dashboard review queue");
  const dashboard = await collectPageState(page);
  await page.screenshot({ path: DASHBOARD_SCREENSHOT, fullPage: true });

  await page.goto(`${BASE_URL}${target.studioUrl}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#studioReviewPanel:not([hidden])", { timeout: 20000 });
  await page.waitForSelector("#studioReviewNextAction", { timeout: 15000 });
  await page.waitForFunction(() => (document.querySelector("#studioReviewRouteLabel")?.innerText || "").includes("："), null, { timeout: 15000 });
  const studio = await collectPageState(page);
  await page.screenshot({ path: STUDIO_SCREENSHOT, fullPage: true });

  await page.goto(`${BASE_URL}/factory`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#factoryReviewRoutingPanel", { timeout: 20000 });
  await waitForLoadedText(page, "#factoryReviewRoutingSummary", /Quality gate|真实验收队列|读取失败|不伪造候选/, "Factory review routing");
  const beforeToggle = await collectPageState(page);
  await page.click("#factoryReviewRoutingToggleBtn");
  await page.waitForFunction(() => !document.querySelector("#factoryReviewRoutingBody")?.hidden, null, { timeout: 10000 });
  const factory = await collectPageState(page);
  await page.screenshot({ path: FACTORY_SCREENSHOT, fullPage: true });

  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(BASE_URL, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#dashboardReviewQueuePanel", { timeout: 20000 });
  const mobileDashboard = await collectPageState(page);
  await page.goto(`${BASE_URL}/factory`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#factoryReviewRoutingPanel", { timeout: 20000 });
  const mobileFactory = await collectPageState(page);
  await browser.close();

  const failures = [];
  if (!dashboard.reviewQueuePanel) failures.push("Dashboard review queue panel missing");
  if (!dashboard.reviewQueueStatus.includes("/api/reviews/artifacts") && !/Quality gate|已读取|真实验收|队列为空/.test(dashboard.reviewQueueStatus)) {
    failures.push("Dashboard review queue status does not prove real API usage");
  }
  if (!studio.studioNextAction || !studio.studioRouteLabel.trim()) failures.push("Studio next action missing");
  if (!factory.factoryRoutingPanel) failures.push("Factory review routing panel missing");
  if (beforeToggle.factoryRoutingBodyHidden !== true) failures.push("Factory review routing body should be collapsed by default");
  if (factory.factoryRoutingBodyHidden) failures.push("Factory review routing body did not expand");
  if ([dashboard, studio, factory, mobileDashboard, mobileFactory].some(state => state.overflow)) failures.push("horizontal overflow detected");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    target,
    queueSummary: queuePayload.summary || {},
    dashboard,
    studio,
    factory,
    mobileDashboard,
    mobileFactory,
    screenshots: {
      dashboard: DASHBOARD_SCREENSHOT,
      studio: STUDIO_SCREENSHOT,
      factory: FACTORY_SCREENSHOT,
    },
    pageErrors,
    unsafeCalls,
  }, null, 2));

  if (failures.length) throw new Error(failures.join("; "));
})();
