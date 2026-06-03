const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage48b_memory_lab.png`;
const STAGE47_NEEDLES = [
  "v_d4d7e1c1",
  "朱朱_stage47_single_long",
  "task_b2272d133fff",
  "BLOCK_TRAINING=false",
  "Stage47 Studio scope",
];
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

async function fetchStatus(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  return { status: response.status, ok: response.ok, payload, text };
}

function normalizeItems(payload = {}) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.memories)) return payload.memories;
  if (Array.isArray(payload.value)) return payload.value;
  return [];
}

function memoryText(memory = {}) {
  try {
    return JSON.stringify(memory);
  } catch {
    return String(memory);
  }
}

function isStage47Memory(memory = {}) {
  const text = memoryText(memory);
  return /stage[\s_-]*47/i.test(text) || STAGE47_NEEDLES.some(needle => text.includes(needle));
}

function memoryId(memory = {}) {
  return memory.memory_id || memory.id || "";
}

function summaryTotal(summary = {}, items = []) {
  return Number(summary.total_count ?? summary.memory_count ?? summary.count ?? items.length);
}

async function gotoDashboard(page) {
  await page.goto(`${BASE_URL}/`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForSelector("#memoryLabPanel", { timeout: 15000 });
  await page.waitForTimeout(1800);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const summaryResp = await fetchStatus("/api/memory/summary");
  const memoryResp = await fetchStatus("/api/memory?limit=100&offset=0");
  const memoryApiAvailable = summaryResp.ok && memoryResp.ok;
  const summary = memoryApiAvailable ? (summaryResp.payload || {}) : {};
  const items = memoryApiAvailable ? normalizeItems(memoryResp.payload) : [];
  const stage47Items = items.filter(isStage47Memory);
  const pinCandidate = items.find(item => memoryId(item)) || null;

  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const pageErrors = [];
  const unsafeCalls = [];
  const memoryCalls = [];

  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/memory\b/i.test(url)) {
      memoryCalls.push(`${request.method()} ${url}`);
    }
    if (/\/api\/train\b|\/api\/process\/|\/cover-jobs\b|\/api\/cover\b|\/api\/upload_task\b|\/rvc\/infer\b|\/infer\b/i.test(url)) {
      unsafeCalls.push(`${request.method()} ${url}`);
    }
  });
  page.on("dialog", dialog => dialog.dismiss());

  await gotoDashboard(page);
  await page.waitForFunction(
    available => {
      const text = document.querySelector("#memoryLabStatus")?.innerText || "";
      return available ? text.includes("已读取真实 Memory API") : text.includes("Memory API 未开放");
    },
    memoryApiAvailable,
    { timeout: 20000 },
  );

  const desktop = await page.evaluate(() => ({
    hasEntry: Boolean(document.querySelector('a[href="#memoryLabPanel"]')),
    hasPanel: Boolean(document.querySelector("#memoryLabPanel")),
    status: document.querySelector("#memoryLabStatus")?.innerText || "",
    total: document.querySelector("#memoryLabTotalValue")?.innerText || "",
    pinned: document.querySelector("#memoryLabPinnedValue")?.innerText || "",
    latestStage: document.querySelector("#memoryLabLatestStageValue")?.innerText || "",
    stage47Value: document.querySelector("#memoryLabStage47Value")?.innerText || "",
    stage47Text: document.querySelector("#memoryLabStage47List")?.innerText || "",
    listText: document.querySelector("#memoryLabList")?.innerText || "",
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));

  let search = null;
  let pin = null;
  if (memoryApiAvailable) {
    const searchNeedle = stage47Items[0]?.title || stage47Items[0]?.memory_id || pinCandidate?.title || pinCandidate?.memory_id || "";
    if (searchNeedle) {
      await page.fill("#memoryLabSearchInput", searchNeedle);
      await page.waitForTimeout(500);
      search = await page.evaluate(needle => ({
        needle,
        text: document.querySelector("#memoryLabList")?.innerText || "",
        summary: document.querySelector("#memoryLabListSummary")?.innerText || "",
      }), searchNeedle);
    }

    if (pinCandidate) {
      const id = memoryId(pinCandidate);
      const firstPin = page.locator(`[data-memory-pin="${id}"]`).first();
      await firstPin.click({ timeout: 15000 });
      await page.waitForTimeout(900);
      const afterFirst = await page.evaluate(() => ({
        status: document.querySelector("#memoryLabStatus")?.innerText || "",
        pinned: document.querySelector("#memoryLabPinnedValue")?.innerText || "",
      }));
      await page.locator(`[data-memory-pin="${id}"]`).first().click({ timeout: 15000 });
      await page.waitForTimeout(900);
      pin = { id, afterFirst };
    }
  } else {
    await page.click("#memoryLabRescanBtn", { timeout: 15000 });
    await page.waitForTimeout(900);
  }

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await page.setViewportSize({ width: 900, height: 1050 });
  await gotoDashboard(page);
  const mobile = await page.evaluate(() => ({
    hasPanel: Boolean(document.querySelector("#memoryLabPanel")),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));

  await browser.close();

  const failures = [];
  if (!desktop.hasEntry) failures.push("Memory Lab nav entry missing");
  if (!desktop.hasPanel) failures.push("Memory Lab panel missing");
  if (desktop.overflow) failures.push("desktop Dashboard overflows horizontally");
  if (!mobile.hasPanel) failures.push("mobile Memory Lab panel missing");
  if (mobile.overflow) failures.push("mobile Dashboard overflows horizontally");

  if (memoryApiAvailable) {
    const total = summaryTotal(summary, items);
    if (!Number.isFinite(total)) failures.push("summary total is not numeric");
    if (!desktop.total.includes(String(total))) failures.push(`summary total not rendered: ${total}`);
    if (!stage47Items.length) failures.push("real API did not return required Stage47 memory");
    if (stage47Items.length && !/Stage47|v_d4d7e1c1|朱朱_stage47_single_long|task_b2272d133fff|BLOCK_TRAINING=false/.test(desktop.stage47Text)) {
      failures.push("Stage47 memory not visible in UI");
    }
    if (search?.needle && !search.text.includes(search.needle)) failures.push(`search did not keep matching memory visible: ${search.needle}`);
    if (pinCandidate && !pin) failures.push("pin/unpin flow did not run");
  } else {
    if (!desktop.status.includes("Memory API 未开放")) failures.push("missing API state is not honest");
    if (desktop.total !== "-") failures.push("missing API state renders fake total");
    if (/Stage47\s+关键线索|v_d4d7e1c1|朱朱_stage47_single_long|task_b2272d133fff/.test(desktop.stage47Text)) {
      failures.push("missing API state renders fake Stage47 memory");
    }
  }

  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe training/RVC/cover calls: ${unsafeCalls.join(" | ")}`);
  if (!memoryCalls.length) failures.push("browser did not call real /api/memory endpoints");

  console.log(JSON.stringify({
    realApi: {
      memoryApiAvailable,
      summaryStatus: summaryResp.status,
      memoryStatus: memoryResp.status,
      total: memoryApiAvailable ? summaryTotal(summary, items) : null,
      itemCount: items.length,
      stage47Count: stage47Items.length,
      pinCandidateId: pinCandidate ? memoryId(pinCandidate) : "",
    },
    desktop,
    search,
    pin,
    mobile,
    pageErrors,
    unsafeCalls,
    memoryCalls,
    screenshot: SCREENSHOT_PATH,
  }, null, 2));

  if (failures.length) throw new Error(failures.join("; "));
})();
