const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${BASE_URL}/`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9235;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage27_model_registry_linkage.png");
const PREFERRED_SOURCE_JOB_ID = "train_d8cd4ed377ca";

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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage27-"));
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

async function fetchLinkedModel() {
  const models = await fetchJson(`${BASE_URL}/api/models?include_unavailable=true`);
  const preferred = models.find(item => item.source_job_id === PREFERRED_SOURCE_JOB_ID)
    || models.find(item => item.origin_kind === "trained_local" && item.source_job_id);
  if (!preferred) {
    throw new Error("No trained_local model with source_job_id was found");
  }
  expect(Boolean(preferred.model_id), "Linked model is missing model_id");
  expect(Boolean(preferred.source_job_id), "Linked model is missing source_job_id");
  return preferred;
}

async function ensureDashboard(client) {
  await client.navigate(DASHBOARD_URL);
  await client.waitFor("Boolean(document.querySelector('#modelPanel'))", 20000, "#modelPanel");
  await client.waitFor("Boolean(document.querySelector('#taskCenter'))", 20000, "#taskCenter");
  await client.waitFor("Boolean(document.getElementById('coverModelSelect'))", 20000, "#coverModelSelect");
}

async function openLinkedModel(client, linkedModel) {
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === true", 20000, "models inventory collapsed");
  await client.evaluate(`
    (() => {
      document.getElementById("modelsInventoryToggleBtn")?.click();
      return true;
    })()
  `);
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === false", 20000, "models inventory expanded");
  const selectedModelId = await client.evaluate(`
    (() => {
      const row = document.querySelector('#modelsList [data-model-id="${linkedModel.model_id}"]');
      row?.click();
      return row?.dataset?.modelId || "";
    })()
  `);
  expect(selectedModelId === linkedModel.model_id, `Failed to select linked model ${linkedModel.model_id}`);
  await client.waitFor(
    `document.getElementById("modelDetailCard")?.textContent?.includes(${JSON.stringify(linkedModel.source_job_id)})`,
    20000,
    "model detail lineage summary",
  );
  await client.waitFor(
    "Boolean(document.getElementById('modelUseForCoverBtn'))",
    20000,
    "use model for cover button",
  );
}

async function verifyUseForCover(client, linkedModel) {
  await client.evaluate(`(() => { document.getElementById("modelUseForCoverBtn")?.click(); return true; })()`);
  await client.waitFor(
    `document.getElementById("coverModelSelect")?.value === ${JSON.stringify(linkedModel.model_id)}`,
    20000,
    "cover model select synced",
  );
}

async function verifySourceJobJump(client, linkedModel) {
  await client.evaluate(`(() => { document.getElementById("modelSourceJobBtn")?.click(); return true; })()`);
  await client.waitFor(
    `document.getElementById("jobSummaryCard")?.textContent?.includes(${JSON.stringify(linkedModel.source_job_id)})`,
    20000,
    "source job detail loaded",
  );
  await client.waitFor(
    `document.getElementById("jobMetaGrid")?.textContent?.includes(${JSON.stringify(linkedModel.model_id)})`,
    20000,
    "job detail generated model card",
  );
  await client.waitFor(
    "Boolean(document.querySelector('#jobActionBar [data-open-model]'))",
    20000,
    "open model action in job detail",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    const linkedModel = await fetchLinkedModel();
    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureDashboard(client);
    await openLinkedModel(client, linkedModel);
    await verifyUseForCover(client, linkedModel);
    await verifySourceJobJump(client, linkedModel);
    await client.screenshot(SCREENSHOT_PATH);

    console.log(`STAGE27_MODEL_REGISTRY_SMOKE PASS model=${linkedModel.model_id} source_job=${linkedModel.source_job_id}`);
  } finally {
    client?.close();
    if (chromeHandle?.chrome && chromeHandle.chrome.exitCode === null) {
      chromeHandle.chrome.kill();
    }
    if (chromeHandle?.userDataDir) {
      try {
        fs.rmSync(chromeHandle.userDataDir, { recursive: true, force: true });
      } catch {
        // Chrome may still be releasing the temp profile; cleanup is best effort.
      }
    }
  }
}

main().catch(error => {
  console.error(`STAGE27_MODEL_REGISTRY_SMOKE FAIL ${error?.stack || error}`);
  process.exitCode = 1;
});
