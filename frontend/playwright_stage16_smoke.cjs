const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE_URL = "http://127.0.0.1:8000/";
const DESKTOP_SHOT = path.join(__dirname, "..", "stage16_desktop.png");
const MOBILE_SHOT = path.join(__dirname, "..", "stage16_mobile.png");

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

async function launchBrowser() {
  return chromium.launch({
    headless: true,
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
}

async function waitForJob(page, jobId) {
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

async function main() {
  const browser = await launchBrowser();
  const errors = [];

  try {
    const desktop = await browser.newPage({ viewport: { width: 1600, height: 1240 } });
    desktop.on("console", msg => {
      if (msg.type() === "error") errors.push(`desktop console: ${msg.text()}`);
    });
    desktop.on("pageerror", err => errors.push(`desktop pageerror: ${err.message}`));

    await desktop.goto(BASE_URL, { waitUntil: "networkidle" });
    await desktop.waitForSelector("#taskCenter");
    await desktop.waitForSelector("#entryCenter");
    await desktop.waitForSelector("#modelPanel");
    await desktop.waitForSelector("#diagnosticsPanel");

    const jobRows = desktop.locator(".job-row");
    expect(await jobRows.count() > 0, "task list is empty");
    const selectedIndex = Math.min(1, (await jobRows.count()) - 1);
    const selectedJobId = await jobRows.nth(selectedIndex).getAttribute("data-job-id");
    await jobRows.nth(selectedIndex).click();
    await waitForJob(desktop, selectedJobId);

    const modelSelect = desktop.locator("#coverModelSelect");
    const modelOptions = await modelSelect.locator("option").evaluateAll(nodes => nodes.map(node => node.value).filter(Boolean));
    if (modelOptions.length) {
      const target = modelOptions[modelOptions.length - 1];
      await modelSelect.selectOption(target);
      await waitForModelValue(desktop, target);
    }

    await desktop.locator("#jobsRefreshBtn").click();
    await waitForJob(desktop, selectedJobId);
    await desktop.locator("#modelsRefreshBtn").click();
    if (modelOptions.length) {
      await waitForModelValue(desktop, modelOptions[modelOptions.length - 1]);
    }

    const voiceInput = desktop.locator("#singleTrainVoiceNameInput");
    await voiceInput.fill("stage16-refresh-check");
    await desktop.waitForTimeout(16000);
    expect(await voiceInput.inputValue() === "stage16-refresh-check", "desktop refresh interrupted input");

    await desktop.screenshot({ path: DESKTOP_SHOT, fullPage: true });

    const mobile = await browser.newPage({ viewport: { width: 900, height: 1200 } });
    mobile.on("console", msg => {
      if (msg.type() === "error") errors.push(`mobile console: ${msg.text()}`);
    });
    mobile.on("pageerror", err => errors.push(`mobile pageerror: ${err.message}`));

    await mobile.goto(BASE_URL, { waitUntil: "networkidle" });
    await mobile.waitForSelector('[data-mobile-tab-target="dashboard"]');
    await mobile.click('[data-mobile-tab-target="models"]');
    await mobile.waitForFunction(() => document.body.dataset.mobileTab === "models");
    await mobile.click("#modelsRefreshBtn");
    await mobile.waitForFunction(() => document.body.dataset.mobileTab === "models");
    await mobile.click('[data-mobile-tab-target="monitor"]');
    await mobile.waitForFunction(() => document.body.dataset.mobileTab === "monitor");
    await mobile.click('[data-mobile-tab-target="dashboard"]');
    await mobile.waitForFunction(() => document.body.dataset.mobileTab === "dashboard");
    await mobile.screenshot({ path: MOBILE_SHOT, fullPage: true });

    const desktopOverflow = await desktop.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const mobileOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desktopOverflow <= 24, `desktop overflow too large: ${desktopOverflow}`);
    expect(mobileOverflow <= 24, `mobile overflow too large: ${mobileOverflow}`);

    if (errors.length) {
      throw new Error(errors.join(" | "));
    }

    console.log("STAGE16_PLAYWRIGHT_SMOKE PASS");
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error("STAGE16_PLAYWRIGHT_SMOKE FAIL");
  console.error(err.stack || err.message || err);
  process.exit(1);
});
