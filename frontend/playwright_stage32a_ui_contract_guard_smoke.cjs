const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9253;

const ROOT = path.join(__dirname, "..");
const FILES = {
  dashboardHtml: path.join(__dirname, "index.html"),
  dashboardJobs: path.join(__dirname, "js", "jobs.js"),
  dashboardModels: path.join(__dirname, "js", "models.js"),
  factoryHtml: path.join(__dirname, "factory.html"),
  factoryJs: path.join(__dirname, "js", "factory", "main.js"),
  studioHtml: path.join(__dirname, "studio.html"),
  studioJs: path.join(__dirname, "js", "studio.js"),
};

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function read(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
  }
  return payload;
}

async function waitForDebugger(timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const version = await fetchJson(`http://127.0.0.1:${REMOTE_DEBUG_PORT}/json/version`);
      if (version.webSocketDebuggerUrl) return version;
    } catch {
      // Chrome may still be booting.
    }
    await delay(250);
  }
  throw new Error("Chrome remote debugger did not become ready in time");
}

async function listTargets() {
  return fetchJson(`http://127.0.0.1:${REMOTE_DEBUG_PORT}/json/list`);
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      const socket = new WebSocket(this.wsUrl);
      const onError = event => reject(new Error(`CDP websocket error: ${event?.message || "unknown"}`));

      socket.addEventListener("open", () => {
        socket.removeEventListener("error", onError);
        this.ws = socket;
        resolve();
      });

      socket.addEventListener("message", event => {
        const payload = JSON.parse(event.data);
        if (payload.id && this.pending.has(payload.id)) {
          const { resolve: resolvePending, reject: rejectPending } = this.pending.get(payload.id);
          this.pending.delete(payload.id);
          if (payload.error) {
            rejectPending(new Error(payload.error.message || JSON.stringify(payload.error)));
          } else {
            resolvePending(payload.result || {});
          }
        }
      });

      socket.addEventListener("error", onError);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(message);
    });
  }

  async evaluate(expression, { awaitPromise = true } = {}) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise,
      returnByValue: true,
    });
    return result.result?.value;
  }

  async waitFor(expression, timeoutMs = 20000, label = expression) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const value = await this.evaluate(expression);
        if (value) return value;
      } catch {
        // Ignore transient runtime errors while the page settles.
      }
      await delay(250);
    }
    throw new Error(`Timed out waiting for: ${label}`);
  }

  async navigate(url) {
    await this.send("Page.navigate", { url });
    await this.waitFor("document.readyState === 'complete'", 20000, `readyState complete for ${url}`);
  }

  close() {
    try {
      this.ws?.close();
    } catch {
      // Ignore close errors during shutdown.
    }
  }
}

function launchChrome() {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage32a-contract-"));
  const chrome = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      "--disable-gpu",
      "--mute-audio",
      "--autoplay-policy=no-user-gesture-required",
      `--remote-debugging-port=${REMOTE_DEBUG_PORT}`,
      `--user-data-dir=${userDataDir}`,
      "about:blank",
    ],
    { stdio: "ignore", windowsHide: true },
  );
  return { chrome, userDataDir };
}

async function prepareClient() {
  await waitForDebugger();
  const targets = await listTargets();
  const pageTarget = targets.find(target => target.type === "page");
  if (!pageTarget?.webSocketDebuggerUrl) {
    throw new Error("No Chrome page target available for CDP connection");
  }

  const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await client.connect();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  return client;
}

async function setViewport(client, width, height, mobile = false) {
  await client.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile,
  });
}

async function assertNoHorizontalScroll(client, label) {
  const result = await client.evaluate(`
    (() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      ok: document.documentElement.scrollWidth <= window.innerWidth + 8,
      offenders: Array.from(document.querySelectorAll('body *'))
        .map(node => {
          const rect = node.getBoundingClientRect();
          return {
            tag: node.tagName,
            id: node.id || '',
            className: String(node.className || ''),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        })
        .filter(item => item.right > window.innerWidth + 8 || item.left < -8)
        .slice(0, 8)
    }))()
  `);
  assert(result?.ok, `${label} has horizontal scroll: ${JSON.stringify(result)}`);
}

async function assertSelectors(client, selectors, label) {
  for (const selector of selectors) {
    await client.waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`, 20000, `${label} selector ${selector}`);
  }
}

function assertSourceContains(filePaths, needles, label) {
  const haystack = filePaths.map(filePath => read(filePath)).join("\n");
  for (const needle of needles) {
    assert(haystack.includes(needle), `${label} source contract missing ${needle}`);
  }
}

async function assertUnifiedNav(client, activeHref) {
  await client.waitFor(
    `(() => {
      const links = Array.from(document.querySelectorAll('.page-nav-link'));
      return links.length >= 3
        && links.some(link => link.getAttribute('href') === '/')
        && links.some(link => link.getAttribute('href') === '/factory')
        && links.some(link => link.getAttribute('href') === '/studio')
        && document.querySelector('.page-nav-link.is-active')?.getAttribute('href') === ${JSON.stringify(activeHref)};
    })()`,
    20000,
    `unified nav ${activeHref}`,
  );
}

async function assertHidden(client, selector, label) {
  await client.waitFor(
    `(() => {
      const node = document.querySelector(${JSON.stringify(selector)});
      return Boolean(node) && node.hidden === true;
    })()`,
    20000,
    `${label} collapsed`,
  );
}

async function verifyDashboard(client, width, height, mobile = false) {
  await setViewport(client, width, height, mobile);
  await client.navigate(`${BASE_URL}/`);
  await assertUnifiedNav(client, "/");
  await assertSelectors(client, [
    "#taskCenter",
    "#entryCenter",
    "#modelPanel",
    "#diagnosticsPanel",
    "#coverModelSelect",
    "#jobsTableBody",
    "#jobSummaryCard",
    "#jobActionBar",
    "#jobStageLogsBody",
    "#jobTechnicalBody",
    "#modelsInventoryBody",
    "#modelsInventoryToggleBtn",
    "#modelDetailCard",
    "[data-mobile-tab-target]",
  ], `Dashboard ${width}px`);
  await assertSelectors(client, [
    "#coverCreateBtn",
    "#singleTrainCreateBtn",
    "#multiTrainCreateBtn",
  ], `Dashboard CTA ${width}px`);
  await assertHidden(client, "#jobTechnicalBody", "Dashboard job technical detail");
  await assertHidden(client, "#jobStageLogsBody", "Dashboard stage logs");
  await assertHidden(client, "#modelsInventoryBody", "Dashboard model inventory");
  await assertHidden(client, "#diagnostics-detail-panel", "Dashboard diagnostics details");
  await assertNoHorizontalScroll(client, `Dashboard ${width}px`);
}

async function verifyFactory(client, width, height, mobile = false) {
  await setViewport(client, width, height, mobile);
  await client.navigate(`${BASE_URL}/factory`);
  await assertUnifiedNav(client, "/factory");
  await assertSelectors(client, [
    "#factoryCreateBatchForm",
    "#factoryImportTracksForm",
    "#factoryRefreshBtn",
    "#factoryBatchesList",
    "#factoryTracksList",
    "#factoryCoverModelSelect",
    "#factoryCreateCoverJobBtn",
    "#factoryTrackJobsList",
    "#factoryTrackOutcomeCard",
    "#factoryCurrentMasterCard",
    "#factoryTrackTitle",
    "#factoryTrackSubtitle",
    "#factoryLyricText",
    "#factoryLyricsToggleBtn",
    "#factoryLyricsBody",
    "#factoryJobsBody",
  ], `Factory ${width}px`);
  await assertSelectors(client, [
    "#factoryCreateCoverJobBtn",
  ], `Factory CTA ${width}px`);
  await assertHidden(client, "#factoryLyricsBody", "Factory lyrics drawer");
  await assertHidden(client, "#factoryJobsBody", "Factory jobs drawer");
  await assertNoHorizontalScroll(client, `Factory ${width}px`);
}

async function verifyStudio(client, width, height, mobile = false) {
  await setViewport(client, width, height, mobile);
  await client.navigate(`${BASE_URL}/studio`);
  await assertUnifiedNav(client, "/studio");
  await assertSelectors(client, [
    "#studioSourceContextCard",
    "#studioSourceMetaGrid",
    "#studioFactoryBackBtn",
    "#studioArtifactSummaryCard",
    "#studioSummaryDownloadBtn",
    "#studioTrackHistoryPanel",
    "#studioTrackHistoryList",
    "#studioEffectRackList",
    "[data-effect-slot-toggle]",
    "#studioTechnicalToggleBtn",
    "#studioTechnicalBody",
    "#studioLibraryBody",
  ], `Studio ${width}px`);
  await assertSelectors(client, [
    "#studioSummaryDownloadBtn",
    "#studioEffectRackList",
  ], `Studio CTA ${width}px`);
  await assertHidden(client, "#studioTechnicalBody", "Studio technical detail");
  await assertHidden(client, "#studioTrackHistoryBody", "Studio track history");
  await assertHidden(client, "#studioLibraryBody", "Studio audition library");
  await assertNoHorizontalScroll(client, `Studio ${width}px`);
}

function verifySourceContracts() {
  assertSourceContains([FILES.dashboardHtml, FILES.dashboardJobs, FILES.dashboardModels], [
    "data-job-id",
    "data-open-studio",
    "data-model-id",
    "modelUseForCoverBtn",
    "modelSourceJobBtn",
    "modelTechnicalBody",
  ], "Dashboard");
  assertSourceContains([FILES.factoryHtml, FILES.factoryJs], [
    "data-batch-id",
    "data-track-id",
    "data-track-job-id",
    "data-studio-url",
    "data-download-url",
    "factoryLyricsBody",
    "factoryJobsBody",
  ], "Factory");
  assertSourceContains([FILES.studioHtml, FILES.studioJs], [
    "data-track-history-job-id",
    "data-set-track-master-job-id",
    "data-effect-slot-toggle",
    "studioTechnicalBody",
    "studioTrackHistoryBody",
    "studioLibraryBody",
  ], "Studio");
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    verifySourceContracts();

    chromeHandle = launchChrome();
    client = await prepareClient();

    await verifyDashboard(client, 1500, 1060, false);
    await verifyFactory(client, 1500, 1060, false);
    await verifyStudio(client, 1500, 1060, false);

    await verifyDashboard(client, 390, 920, true);
    await verifyFactory(client, 390, 920, true);
    await verifyStudio(client, 390, 920, true);

    console.log("STAGE32A_UI_CONTRACT_GUARD_SMOKE PASS");
    console.log(`contract_root=${path.join(ROOT, "docs", "ui-contract", "stage32-three-page-selector-contract.md")}`);
    console.log("desktop_viewport=1500x1060");
    console.log("mobile_viewport=390x920");
  } finally {
    client?.close();
    if (chromeHandle?.chrome && !chromeHandle.chrome.killed) {
      chromeHandle.chrome.kill("SIGKILL");
    }
    if (chromeHandle?.userDataDir) {
      try {
        fs.rmSync(chromeHandle.userDataDir, { recursive: true, force: true });
      } catch {
        // Ignore temp profile cleanup failures on Windows.
      }
    }
  }
}

main().catch(error => {
  console.error("STAGE32A_UI_CONTRACT_GUARD_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
