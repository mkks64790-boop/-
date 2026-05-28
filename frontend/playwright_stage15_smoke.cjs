const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE_URL = "http://127.0.0.1:8000/";
const SHOTS_DIR = path.join(__dirname, "..", "stage15-shots");

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function expect(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function waitForSelectedJob(page, jobId) {
  await page.waitForFunction(
    expected => document.querySelector(".job-row.is-active")?.dataset.jobId === expected,
    jobId,
  );
  await page.waitForFunction(
    expected => document.getElementById("jobDetailTitle")?.textContent === expected,
    jobId,
  );
}

async function waitForModelValue(page, value) {
  await page.waitForFunction(
    expected => document.getElementById("coverModelSelect")?.value === expected,
    value,
  );
}

async function launchBrowser() {
  return chromium.launch({
    headless: true,
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
}

async function main() {
  ensureDir(SHOTS_DIR);
  const browser = await launchBrowser();
  const errors = [];

  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } });
    page.on("console", msg => {
      if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
    });
    page.on("pageerror", err => errors.push(`pageerror: ${err.message}`));

    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(SHOTS_DIR, "desktop.png"), fullPage: true });

    const requiredIds = [
      "taskCenter",
      "entryCenter",
      "modelPanel",
      "diagnosticsPanel",
    ];
    for (const id of requiredIds) {
      expect(await page.locator(`#${id}`).count(), `missing section: ${id}`);
    }

    const initialJobId = await page.locator(".job-row").first().getAttribute("data-job-id");
    expect(initialJobId, "task list is empty");

    const rowCount = await page.locator(".job-row").count();
    const selectedRowIndex = rowCount > 1 ? 1 : 0;
    const targetJobId = await page.locator(".job-row").nth(selectedRowIndex).getAttribute("data-job-id");
    await page.locator(".job-row").nth(selectedRowIndex).click();
    await waitForSelectedJob(page, targetJobId);
    const selectedJobId = await page.locator(".job-row.is-active").getAttribute("data-job-id");
    expect(selectedJobId, "job selection did not stick");
    expect(await page.locator("#jobDetailTitle").textContent(), "job detail title missing");
    expect(await page.locator("#jobDetailTitle").textContent() === selectedJobId, "job detail did not switch with selection");

    const modelSelect = page.locator("#coverModelSelect");
    const initialModelValue = await modelSelect.inputValue();
    const optionValues = await modelSelect.locator("option").evaluateAll(nodes => nodes.map(node => node.value).filter(Boolean));
    if (optionValues.length > 1) {
      const target = optionValues[optionValues.length - 1];
      await modelSelect.selectOption(target);
      await waitForModelValue(page, target);
      expect(await modelSelect.inputValue() === target, "model select did not switch");
    }

    await page.locator("#jobsRefreshBtn").click();
    await waitForSelectedJob(page, selectedJobId);
    expect(await page.locator(".job-row.is-active").getAttribute("data-job-id") === selectedJobId, "selected job lost after refresh");
    expect(await page.locator("#jobDetailTitle").textContent() === selectedJobId, "detail title changed after refresh");

    await page.locator("#modelsRefreshBtn").click();
    const expectedModel = optionValues.length > 1 ? optionValues[optionValues.length - 1] : initialModelValue;
    if (expectedModel) {
      await waitForModelValue(page, expectedModel);
    }
    expect(await modelSelect.inputValue(), "model select empty after refresh");
    if (optionValues.length > 1) {
      expect(await modelSelect.inputValue() === optionValues[optionValues.length - 1], "selected model lost after refresh");
    } else {
      expect(await modelSelect.inputValue() === initialModelValue, "single model selection changed unexpectedly");
    }

    await page.locator("#diagnosticsRefreshBtn").click();
    expect(await page.locator("#diagRvcStatus").textContent(), "diagnostics missing RVC status");
    expect(await page.locator("#diagGuidance .guidance-item").count() > 0, "diagnostics guidance missing");
    expect(await page.locator("#jobActionBar button").count() > 0, "job actions missing");

    const autoRefreshInput = page.locator("#singleTrainVoiceNameInput");
    await autoRefreshInput.click();
    await autoRefreshInput.fill("stage15-auto-refresh-check");
    await page.waitForTimeout(16000);
    expect(await autoRefreshInput.inputValue() === "stage15-auto-refresh-check", "auto refresh interrupted form input");
    await waitForSelectedJob(page, selectedJobId);
    if (expectedModel) {
      expect(await modelSelect.inputValue() === expectedModel, "auto refresh reset selected model");
    }

    const narrow = await browser.newPage({ viewport: { width: 980, height: 1280 } });
    narrow.on("console", msg => {
      if (msg.type() === "error") errors.push(`console-narrow: ${msg.text()}`);
    });
    narrow.on("pageerror", err => errors.push(`pageerror-narrow: ${err.message}`));
    await narrow.goto(BASE_URL, { waitUntil: "networkidle" });
    await narrow.screenshot({ path: path.join(SHOTS_DIR, "narrow.png"), fullPage: true });
    const narrowWidth = await narrow.evaluate(() => document.documentElement.scrollWidth);
    expect(narrowWidth <= 1010, `narrow layout overflows horizontally: ${narrowWidth}`);
    expect(await narrow.locator("#taskCenter").count(), "narrow layout missing task center");
    expect(await narrow.locator("#modelPanel").count(), "narrow layout missing model panel");
    expect(await narrow.locator("#diagnosticsPanel").count(), "narrow layout missing diagnostics panel");

    if (errors.length) {
      throw new Error(errors.join(" | "));
    }

    console.log("STAGE15_PLAYWRIGHT_SMOKE PASS");
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error("STAGE15_PLAYWRIGHT_SMOKE FAIL");
  console.error(err.stack || err.message || err);
  process.exit(1);
});
