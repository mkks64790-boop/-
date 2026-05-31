const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9252;
const DASHBOARD_SHOT = path.join(__dirname, "..", "stage32b_dashboard_layout.png");
const FACTORY_SHOT = path.join(__dirname, "..", "stage32b_factory_layout.png");
const STUDIO_SHOT = path.join(__dirname, "..", "stage32b_studio_layout.png");

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
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

  async screenshot(targetPath) {
    const data = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    fs.writeFileSync(targetPath, Buffer.from(data.data, "base64"));
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage32b-layout-"));
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
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1500,
    height: 1060,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function assertNoHorizontalScroll(client, label) {
  const result = await client.evaluate(`
    (() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      ok: document.documentElement.scrollWidth <= window.innerWidth + 8,
      shell: (() => {
        const node = document.querySelector('main');
        if (!node) return null;
        const rect = node.getBoundingClientRect();
        return { left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width), className: node.className };
      })(),
      topbar: (() => {
        const node = document.querySelector('.topbar');
        if (!node) return null;
        const rect = node.getBoundingClientRect();
        return { left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) };
      })(),
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
        .sort((a, b) => b.right - a.right)
        .slice(0, 8)
    }))()
  `);
  if (!result?.ok) {
    throw new Error(`${label} has horizontal scroll: ${JSON.stringify(result)}`);
  }
}

async function assertSelectors(client, selectors, label) {
  for (const selector of selectors) {
    await client.waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`, 20000, `${label} selector ${selector}`);
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

async function verifyDashboard(client) {
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
  ], "Dashboard");
  await client.waitFor("document.getElementById('jobTechnicalBody')?.hidden === true", 20000, "dashboard technical drawer collapsed");
  await client.waitFor("document.getElementById('jobStageLogsBody')?.hidden === true", 20000, "dashboard stage logs collapsed");
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === true", 20000, "dashboard model inventory collapsed");
  await client.waitFor("document.getElementById('diagnostics-detail-panel')?.hidden === true", 20000, "dashboard diagnostics details collapsed");
  await assertNoHorizontalScroll(client, "Dashboard");
  await client.screenshot(DASHBOARD_SHOT);
}

async function verifyFactory(client) {
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
  ], "Factory");
  await client.waitFor("document.getElementById('factoryLyricsBody')?.hidden === true", 20000, "factory lyrics drawer collapsed");
  await client.waitFor("document.getElementById('factoryJobsBody')?.hidden === true", 20000, "factory jobs drawer collapsed");
  await assertNoHorizontalScroll(client, "Factory");
  await client.screenshot(FACTORY_SHOT);
}

async function verifyStudio(client) {
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
  ], "Studio");
  await client.waitFor("document.getElementById('studioTechnicalBody')?.hidden === true", 20000, "studio technical drawer collapsed");
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === true", 20000, "studio history drawer collapsed");
  await client.waitFor("document.getElementById('studioLibraryBody')?.hidden === true", 20000, "studio library drawer collapsed");
  await assertNoHorizontalScroll(client, "Studio");
  await client.screenshot(STUDIO_SHOT);
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    chromeHandle = launchChrome();
    client = await prepareClient();

    await verifyDashboard(client);
    await verifyFactory(client);
    await verifyStudio(client);

    console.log("STAGE32B_THREE_PAGE_LAYOUT_SMOKE PASS");
    console.log(`dashboard_screenshot=${DASHBOARD_SHOT}`);
    console.log(`factory_screenshot=${FACTORY_SHOT}`);
    console.log(`studio_screenshot=${STUDIO_SHOT}`);
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
  console.error("STAGE32B_THREE_PAGE_LAYOUT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
