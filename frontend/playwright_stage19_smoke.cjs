const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${BASE_URL}/`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9234;
const DASHBOARD_SHOT = path.join(__dirname, "..", "stage19_dashboard.png");
const MODEL_SHOT = path.join(__dirname, "..", "stage19_model_detail.png");

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.json();
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
          const { resolve, reject } = this.pending.get(payload.id);
          this.pending.delete(payload.id);
          if (payload.error) {
            reject(new Error(payload.error.message || JSON.stringify(payload.error)));
          } else {
            resolve(payload.result || {});
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
        // Ignore transient navigation errors while waiting.
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage19-"));
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
    {
      stdio: "ignore",
      windowsHide: true,
    },
  );

  return { chrome, userDataDir };
}

async function prepareClient() {
  await waitForDebugger();
  const targets = await listTargets();
  const pageTarget = targets.find(target => target.type === "page");
  if (!pageTarget?.webSocketDebuggerUrl) throw new Error("No Chrome page target available for CDP connection");

  const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await client.connect();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 1100,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function ensureDashboard(client) {
  await client.navigate(DASHBOARD_URL);
  await client.waitFor("Boolean(document.querySelector('#taskCenter'))", 20000, "#taskCenter");
  await client.waitFor("Boolean(document.querySelector('#entryCenter'))", 20000, "#entryCenter");
  await client.waitFor("Boolean(document.querySelector('#modelPanel'))", 20000, "#modelPanel");
  await client.waitFor("Boolean(document.querySelector('#diagnosticsPanel'))", 20000, "#diagnosticsPanel");
}

async function fetchLatestCompletedCoverJobId() {
  const queries = [
    `${BASE_URL}/api/jobs?job_type=cover&status=%E5%AE%8C%E6%88%90&limit=50`,
    `${BASE_URL}/api/jobs?job_type=cover&status=%E5%AE%8C%E6%88%90&include_smoke=true&limit=50`,
  ];

  for (const query of queries) {
    const response = await fetchJson(query);
    const items = Array.isArray(response.items) ? response.items : [];
    for (const item of items) {
      if (!item?.job_id) continue;
      try {
        const artifacts = await fetchJson(`${BASE_URL}/api/jobs/${item.job_id}/artifacts`);
        const hasFinalCover = Array.isArray(artifacts.artifacts)
          && artifacts.artifacts.some(artifact => artifact?.artifact_type === "cover_master" && artifact?.is_final);
        if (hasFinalCover) return item.job_id;
      } catch {
        // Ignore transient artifact lookup errors and keep searching.
      }
    }

    const first = items.find(item => item && item.job_id);
    if (first?.job_id) return first.job_id;
  }

  return "";
}

async function selectCompletedCoverJob(client) {
  const preferredJobId = await fetchLatestCompletedCoverJobId();
  await client.evaluate(`
    (() => {
      const type = document.getElementById("jobsFilterType");
      const status = document.getElementById("jobsFilterStatus");
      const form = document.getElementById("jobsFilterForm");
      if (!type || !status || !form) return false;
      type.value = "cover";
      status.value = "完成";
      form.requestSubmit();
      return true;
    })()
  `);

  if (preferredJobId) {
    await client.waitFor(
      `Boolean(document.querySelector('#jobsTableBody .job-row[data-job-id="${preferredJobId}"]'))`,
      20000,
      `filtered row ${preferredJobId}`,
    );
  } else {
    const rowCount = await client.waitFor(
      `(() => {
        const rows = document.querySelectorAll("#jobsTableBody .job-row");
        const placeholder = document.querySelector("#jobsTableBody .table-placeholder");
        return rows.length || (placeholder ? -1 : 0);
      })()`,
      20000,
      "filtered completed cover jobs",
    );
    expect(rowCount > 0, "no completed cover jobs available");
  }

  const jobId = await client.evaluate(preferredJobId ? `
    (() => {
      const row = document.querySelector('#jobsTableBody .job-row[data-job-id="${preferredJobId}"]') || document.querySelector("#jobsTableBody .job-row");
      row?.click();
      return row?.dataset?.jobId || "";
    })()
  ` : `
    (() => {
      const row = document.querySelector("#jobsTableBody .job-row");
      row?.click();
      return row?.dataset?.jobId || "";
    })()
  `);
  return jobId;
}

async function openSelectedCoverJob(client) {
  await client.waitFor("document.querySelector('#jobSummaryCard')?.textContent?.includes('已完成的翻唱任务')", 20000, "completed cover summary");
  await client.waitFor("Boolean(document.querySelector('#jobActionBar button[data-open-studio=\"true\"]'))", 20000, "Studio action button");
  await client.waitFor("Boolean(document.querySelector('#jobStageLogsBody'))", 20000, "#jobStageLogsBody");
  await client.waitFor("Boolean(document.querySelector('#jobTechnicalBody'))", 20000, "#jobTechnicalBody");

  const state = await client.evaluate(`
    (() => ({
      logsHidden: document.querySelector('#jobStageLogsBody')?.hidden ?? null,
      techHidden: document.querySelector('#jobTechnicalBody')?.hidden ?? null,
      actionLabels: Array.from(document.querySelectorAll('#jobActionBar button')).map(btn => btn.textContent.trim()),
      actionText: document.querySelector('#jobActionBar')?.textContent?.replace(/\\s+/g, ' ').trim() || ''
    }))()
  `);

  expect(state.logsHidden === true, "job logs should be collapsed by default");
  expect(state.techHidden === true, "job technical drawer should be collapsed by default");
  expect(state.actionLabels.includes("进入 Studio"), "completed cover job should expose Studio action");
  expect(state.actionLabels.some(label => label.includes("下载成品")), "completed cover job should expose download action");
  expect(!/重试|取消|重新入队/.test(state.actionText), "completed cover job should not expose retry/requeue/cancel actions");
}

async function persistJobDrawers(client) {
  await client.evaluate(`document.getElementById("jobStageLogsToggleBtn")?.click();`);
  await client.waitFor("document.querySelector('#jobStageLogsBody') && !document.querySelector('#jobStageLogsBody').hidden", 10000, "expanded job stage logs");
  await client.evaluate(`document.getElementById("jobTechnicalToggleBtn")?.click();`);
  await client.waitFor("document.querySelector('#jobTechnicalBody') && !document.querySelector('#jobTechnicalBody').hidden", 10000, "expanded job technical");

  const collapsedFlags = await client.evaluate(`
    (() => ({
      logs: JSON.parse(window.localStorage.getItem("feishark_ui_task_logs_collapsed") || "null"),
      tech: JSON.parse(window.localStorage.getItem("feishark_ui_task_technical_collapsed") || "null"),
    }))()
  `);
  expect(collapsedFlags.logs === false, "task logs collapsed state should persist as open");
  expect(collapsedFlags.tech === false, "task technical collapsed state should persist as open");
}

async function verifyJobDrawerPersistence(client) {
  await client.navigate(DASHBOARD_URL);
  await selectCompletedCoverJob(client);
  await client.waitFor("Boolean(document.querySelector('#jobActionBar button[data-open-studio=\"true\"]'))", 20000, "Studio action after reload");
  const state = await client.evaluate(`
    (() => ({
      logsHidden: document.querySelector('#jobStageLogsBody')?.hidden ?? null,
      techHidden: document.querySelector('#jobTechnicalBody')?.hidden ?? null,
      actionLabels: Array.from(document.querySelectorAll('#jobActionBar button')).map(btn => btn.textContent.trim()),
    }))()
  `);
  expect(state.logsHidden === false, "job logs should stay expanded after reload");
  expect(state.techHidden === false, "job technical drawer should stay expanded after reload");
  expect(state.actionLabels.includes("进入 Studio"), "completed cover job should still expose Studio action after reload");
}

async function expandModelsInventory(client) {
  const collapsed = await client.evaluate(`document.getElementById("modelsInventoryBody")?.hidden ?? null`);
  expect(collapsed === true, "models inventory should default collapsed");
  await client.evaluate(`document.getElementById("modelsInventoryToggleBtn")?.click();`);
  await client.waitFor("document.querySelector('#modelsInventoryBody') && !document.querySelector('#modelsInventoryBody').hidden", 10000, "expanded models inventory");
}

async function selectFirstModel(client) {
  await client.waitFor("Boolean(document.querySelector('#modelsList [data-model-id]'))", 20000, "model list item");
  const modelId = await client.evaluate(`
    (() => {
      const card = document.querySelector('#modelsList [data-model-id]');
      card?.click();
      return card?.dataset?.modelId || "";
    })()
  `);
  expect(Boolean(modelId), "no model available for detail verification");
  return modelId;
}

async function openSelectedModelDetail(client) {
  await client.waitFor("Boolean(document.querySelector('#modelTechnicalBody'))", 20000, "#modelTechnicalBody");
  const state = await client.evaluate(`
    (() => ({
      hidden: document.querySelector('#modelTechnicalBody')?.hidden ?? null,
      buttons: Array.from(document.querySelectorAll('#modelDetailCard button')).map(btn => btn.textContent.trim()),
    }))()
  `);
  expect(state.hidden === true, "model technical drawer should be collapsed by default");
  expect(state.buttons.includes("查看诊断"), "model detail should expose diagnostics action");
}

async function persistModelDrawer(client) {
  await client.evaluate(`document.getElementById("modelTechnicalToggleBtn")?.click();`);
  await client.waitFor("document.querySelector('#modelTechnicalBody') && !document.querySelector('#modelTechnicalBody').hidden", 10000, "expanded model technical");
  const collapsedFlag = await client.evaluate(`JSON.parse(window.localStorage.getItem("feishark_ui_model_technical_collapsed") || "null")`);
  expect(collapsedFlag === false, "model technical collapsed state should persist as open");
}

async function verifyModelDrawerPersistence(client) {
  await client.navigate(DASHBOARD_URL);
  const inventoryHidden = await client.evaluate(`document.getElementById("modelsInventoryBody")?.hidden ?? null`);
  if (inventoryHidden) {
    await client.evaluate(`document.getElementById("modelsInventoryToggleBtn")?.click();`);
    await client.waitFor("document.querySelector('#modelsInventoryBody') && !document.querySelector('#modelsInventoryBody').hidden", 10000, "expanded models inventory after reload");
  }
  await selectFirstModel(client);
  await client.waitFor("document.querySelector('#modelTechnicalBody')", 20000, "#modelTechnicalBody after reload");
  const hidden = await client.evaluate(`document.querySelector('#modelTechnicalBody')?.hidden ?? null`);
  expect(hidden === false, "model technical drawer should stay expanded after reload");
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureDashboard(client);
    const jobId = (await selectCompletedCoverJob(client)) || (await fetchLatestCompletedCoverJobId());
    expect(Boolean(jobId), "no completed cover job available for Stage 19 verification");
    await openSelectedCoverJob(client);
    await client.screenshot(DASHBOARD_SHOT);
    await persistJobDrawers(client);
    await verifyJobDrawerPersistence(client);

    await expandModelsInventory(client);
    const modelId = await selectFirstModel(client);
    expect(Boolean(modelId), "no model available for Stage 19 verification");
    await openSelectedModelDetail(client);
    await client.screenshot(MODEL_SHOT);
    await persistModelDrawer(client);
    await verifyModelDrawerPersistence(client);

    console.log("STAGE19_PLAYWRIGHT_SMOKE PASS");
    console.log(`Dashboard screenshot: ${DASHBOARD_SHOT}`);
    console.log(`Model screenshot: ${MODEL_SHOT}`);
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
  console.error("STAGE19_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
