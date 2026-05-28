const { chromium } = require("playwright");

const BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${BASE_URL}/`;
const STUDIO_URL = `${BASE_URL}/studio`;

function expect(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function launchBrowser() {
  return chromium.launch({
    headless: true,
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
}

async function ensureDashboard(page) {
  await page.goto(DASHBOARD_URL, { waitUntil: "networkidle" });
  await page.waitForSelector("#taskCenter");
  await page.waitForSelector("#entryCenter");
  await page.waitForSelector("#modelPanel");
  await page.waitForSelector("#diagnosticsPanel");
  await page.waitForSelector('.page-nav-link[href="/studio"]');
}

async function openCompletedCoverDetail(page) {
  await page.selectOption("#jobsFilterType", "cover");
  await page.selectOption("#jobsFilterStatus", "完成");
  await page.click("#jobsApplyBtn");

  await page.waitForFunction(() => {
    const placeholder = document.querySelector("#jobsTableBody .table-placeholder");
    const row = document.querySelector("#jobsTableBody .job-row");
    return Boolean(placeholder || row);
  });

  const rowCount = await page.locator("#jobsTableBody .job-row").count();
  expect(rowCount > 0, "no completed cover jobs available for Studio verification");

  const firstRow = page.locator("#jobsTableBody .job-row").first();
  const jobId = await firstRow.getAttribute("data-job-id");
  await firstRow.click();

  await page.waitForFunction(expected => {
    return document.getElementById("jobDetailTitle")?.textContent === expected;
  }, jobId);

  await page.waitForSelector('#jobActionBar button[data-open-studio="true"]');
  return jobId;
}

async function ensureStudioLoaded(page, expectedJobId = "") {
  await page.waitForURL(url => url.pathname === "/studio");
  await page.waitForSelector("#studioResourceSelect");
  await page.waitForSelector("#studioAudio");
  await page.waitForSelector("#studioWaveCanvas");
  await page.waitForSelector("#studioPlayToggleBtn");

  await page.waitForFunction(expected => {
    const current = document.getElementById("studioCurrentJobId")?.textContent || "";
    const title = document.getElementById("studioTrackTitle")?.textContent || "";
    const audio = document.getElementById("studioAudio");
    const hasAudioSource = Boolean(audio?.src);
    if (!expected) {
      return hasAudioSource && title && !title.includes("请选择");
    }
    return current.includes(expected) && hasAudioSource;
  }, expectedJobId);

  const downloadEnabled = await page.locator("#studioDownloadBtn").getAttribute("aria-disabled");
  expect(downloadEnabled === "false", "studio download action is still disabled");
}

async function verifyStudioPlayback(page) {
  const playButton = page.locator("#studioPlayToggleBtn");
  await playButton.click();
  await page.waitForFunction(() => {
    const audio = document.getElementById("studioAudio");
    return Boolean(audio && !audio.paused);
  });
}

async function main() {
  const browser = await launchBrowser();
  const errors = [];

  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
    page.on("console", msg => {
      if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
    });
    page.on("pageerror", err => errors.push(`pageerror: ${err.message}`));

    await ensureDashboard(page);
    const jobId = await openCompletedCoverDetail(page);
    await page.click('#jobActionBar button[data-open-studio="true"]');
    await ensureStudioLoaded(page, jobId);
    await verifyStudioPlayback(page);

    const secondPage = await browser.newPage({ viewport: { width: 1280, height: 960 } });
    secondPage.on("console", msg => {
      if (msg.type() === "error") errors.push(`studio console: ${msg.text()}`);
    });
    secondPage.on("pageerror", err => errors.push(`studio pageerror: ${err.message}`));

    await secondPage.goto(STUDIO_URL, { waitUntil: "networkidle" });
    await secondPage.waitForSelector("#studioResourceSelect");
    await secondPage.waitForSelector(".page-nav-link.is-active[href=\"/studio\"]");

    if (errors.length) {
      throw new Error(errors.join(" | "));
    }

    console.log("STAGE17_PLAYWRIGHT_SMOKE PASS");
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error("STAGE17_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
