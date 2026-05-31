const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9254;
const DASHBOARD_SHOT = path.join(__dirname, "..", "stage33a_dashboard_guard.png");
const FACTORY_SHOT = path.join(__dirname, "..", "stage33a_factory_guard.png");

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage33a-hotfix-"));
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

async function assertSelectors(client, selectors, label) {
  for (const selector of selectors) {
    await client.waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`, 20000, `${label} selector ${selector}`);
  }
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
        .sort((a, b) => b.right - a.right)
        .slice(0, 8)
    }))()
  `);
  assert(result?.ok, `${label} has horizontal scroll: ${JSON.stringify(result)}`);
}

async function verifyEngineUsage(client) {
  await assertSelectors(client, ["#engineUsageToggleBtn", "#engineUsagePanel"], "Engine usage");

  const collapsed = await client.evaluate(`
    (() => {
      const panel = document.getElementById("engineUsagePanel");
      const button = document.getElementById("engineUsageToggleBtn");
      return {
        hidden: panel?.hidden,
        display: panel ? getComputedStyle(panel).display : "",
        height: panel ? panel.getBoundingClientRect().height : -1,
        expanded: button?.getAttribute("aria-expanded"),
        text: button?.textContent || "",
      };
    })()
  `);
  assert(collapsed.hidden === true, `engine usage should default collapsed: ${JSON.stringify(collapsed)}`);
  assert(collapsed.display === "none" || collapsed.height === 0, `engine usage collapsed must be visually zero: ${JSON.stringify(collapsed)}`);

  await client.evaluate("document.getElementById('engineUsageToggleBtn').click()");
  const expanded = await client.waitFor(`
    (() => {
      const panel = document.getElementById("engineUsagePanel");
      const button = document.getElementById("engineUsageToggleBtn");
      if (!panel || panel.hidden || button?.getAttribute("aria-expanded") !== "true") return false;
      return { height: panel.getBoundingClientRect().height, text: button.textContent || "" };
    })()
  `, 20000, "engine usage expanded");
  assert(expanded.height > 0, `engine usage expanded height should be positive: ${JSON.stringify(expanded)}`);

  await client.evaluate("document.getElementById('engineUsageToggleBtn').click()");
  const recollapsed = await client.waitFor(`
    (() => {
      const panel = document.getElementById("engineUsagePanel");
      const button = document.getElementById("engineUsageToggleBtn");
      if (!panel || !button) return false;
      return {
        hidden: panel.hidden,
        display: getComputedStyle(panel).display,
        height: panel.getBoundingClientRect().height,
        expanded: button.getAttribute("aria-expanded"),
        text: button.textContent || "",
      };
    })()
  `, 20000, "engine usage recollapsed");
  assert(recollapsed.hidden === true, `engine usage should recollapse hidden: ${JSON.stringify(recollapsed)}`);
  assert(recollapsed.display === "none" || recollapsed.height === 0, `engine usage recollapsed must be visually zero: ${JSON.stringify(recollapsed)}`);
  assert(recollapsed.expanded === "false", `engine usage aria-expanded should be false: ${JSON.stringify(recollapsed)}`);
}

async function selectAnyJob(client) {
  await client.waitFor("Boolean(document.querySelector('#jobsTableBody'))", 20000, "jobs table");
  await client.evaluate(`
    (() => {
      const row = document.querySelector('#jobsTableBody .job-row[data-job-id]');
      row?.click();
      return Boolean(row);
    })()
  `);
  await delay(750);
}

async function verifyJobDetailOverflow(client) {
  await assertSelectors(client, [
    "#jobDetailPanel",
    "#jobDetailTitle",
    "#jobSummaryCard",
    "#jobStageLogsBody",
    "#jobTechnicalBody",
  ], "Job detail");
  await selectAnyJob(client);

  const overflow = await client.evaluate(`
    (() => {
      const panel = document.getElementById("jobDetailPanel");
      if (!panel) return { ok: false, reason: "missing panel" };
      const rect = panel.getBoundingClientRect();
      const computed = getComputedStyle(panel);
      return {
        ok: panel.scrollWidth <= Math.ceil(rect.width) + 2 && computed.overflowX === "hidden",
        scrollWidth: panel.scrollWidth,
        width: Math.ceil(rect.width),
        overflowX: computed.overflowX,
        overflowY: computed.overflowY,
        maxHeight: computed.maxHeight,
      };
    })()
  `);
  assert(overflow.ok, `job detail panel overflow not controlled: ${JSON.stringify(overflow)}`);
  await assertNoHorizontalScroll(client, "Dashboard after job detail selection");
}

async function verifyArtifactsDrawer(client) {
  await assertSelectors(client, [
    "#jobArtifactsToggleBtn",
    "#jobArtifactsBody",
    "#jobArtifactsList",
  ], "Job artifacts");

  const before = await client.evaluate(`
    (() => {
      const body = document.getElementById("jobArtifactsBody");
      const buttons = Array.from(document.querySelectorAll('#jobArtifactsList button[data-artifact-download]'));
      return {
        hidden: body?.hidden,
        buttonCount: buttons.length,
        enabledDownloadCount: buttons.filter(button => !button.disabled && button.getAttribute("aria-disabled") !== "true").length,
      };
    })()
  `);
  assert(typeof before.hidden === "boolean", `artifact body hidden state missing: ${JSON.stringify(before)}`);

  await client.evaluate("document.getElementById('jobArtifactsToggleBtn').click()");
  const toggled = await client.waitFor(`
    (() => {
      const body = document.getElementById("jobArtifactsBody");
      return body ? body.hidden === ${JSON.stringify(!before.hidden)} : false;
    })()
  `, 20000, "artifact drawer first toggle");
  assert(toggled === true, "artifact drawer first toggle did not change hidden state");

  await client.evaluate("document.getElementById('jobArtifactsToggleBtn').click()");
  const restored = await client.waitFor(`
    (() => {
      const body = document.getElementById("jobArtifactsBody");
      return body ? body.hidden === ${JSON.stringify(before.hidden)} : false;
    })()
  `, 20000, "artifact drawer second toggle");
  assert(restored === true, "artifact drawer second toggle did not restore hidden state");

  const after = await client.evaluate(`
    (() => {
      const buttons = Array.from(document.querySelectorAll('#jobArtifactsList button[data-artifact-download]'));
      return {
        buttonCount: buttons.length,
        enabledDownloadCount: buttons.filter(button => !button.disabled && button.getAttribute("aria-disabled") !== "true").length,
      };
    })()
  `);
  if (after.buttonCount > 0) {
    assert(after.enabledDownloadCount > 0, `artifact download buttons exist but none are usable: ${JSON.stringify(after)}`);
  }
}

async function verifyFactoryBatchesDrawer(client) {
  await client.navigate(`${BASE_URL}/factory`);
  await assertSelectors(client, [
    "#factoryBatchesToggleBtn",
    "#factoryBatchesBody",
    "#factoryBatchesList",
    "#factoryBatchHint",
  ], "Factory batches");

  const before = await client.evaluate(`
    (() => {
      const body = document.getElementById("factoryBatchesBody");
      return { hidden: body?.hidden, batchCount: document.querySelectorAll('#factoryBatchesList [data-batch-id]').length };
    })()
  `);
  assert(typeof before.hidden === "boolean", `factory batches hidden state missing: ${JSON.stringify(before)}`);

  await client.evaluate("document.getElementById('factoryBatchesToggleBtn').click()");
  await client.waitFor(`
    (() => {
      const body = document.getElementById("factoryBatchesBody");
      return body ? body.hidden === ${JSON.stringify(!before.hidden)} : false;
    })()
  `, 20000, "factory batches first toggle");

  await client.evaluate("document.getElementById('factoryBatchesToggleBtn').click()");
  await client.waitFor(`
    (() => {
      const body = document.getElementById("factoryBatchesBody");
      return body ? body.hidden === ${JSON.stringify(before.hidden)} : false;
    })()
  `, 20000, "factory batches second toggle");

  const clickResult = await client.evaluate(`
    (() => {
      const body = document.getElementById("factoryBatchesBody");
      if (body?.hidden) document.getElementById("factoryBatchesToggleBtn")?.click();
      const batch = document.querySelector('#factoryBatchesList [data-batch-id]');
      if (!batch) return { clicked: false, reason: "no batch rows" };
      const batchId = batch.dataset.batchId || "";
      batch.click();
      return { clicked: true, batchId };
    })()
  `);
  if (clickResult.clicked) {
    await client.waitFor(
      `document.querySelector('#factoryBatchesList [data-batch-id="${clickResult.batchId}"]')?.classList.contains('is-active')`,
      20000,
      "factory batch row click keeps selection logic",
    );
  }
  await assertNoHorizontalScroll(client, "Factory batches");
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    chromeHandle = launchChrome();
    client = await prepareClient();

    await client.navigate(`${BASE_URL}/`);
    await verifyEngineUsage(client);
    await verifyJobDetailOverflow(client);
    await verifyArtifactsDrawer(client);
    await client.screenshot(DASHBOARD_SHOT);

    await verifyFactoryBatchesDrawer(client);
    await client.screenshot(FACTORY_SHOT);

    console.log("STAGE33A_UI_HOTFIX_GUARD_SMOKE PASS");
    console.log(`dashboard_screenshot=${DASHBOARD_SHOT}`);
    console.log(`factory_screenshot=${FACTORY_SHOT}`);
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
  console.error("STAGE33A_UI_HOTFIX_GUARD_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
