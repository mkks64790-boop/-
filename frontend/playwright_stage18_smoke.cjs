const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${BASE_URL}/`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9234;
const DASHBOARD_SHOT = path.join(__dirname, "..", "stage18_dashboard.png");
const STUDIO_SHOT = path.join(__dirname, "..", "stage18_studio.png");

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
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
        // Ignore transient navigation errors.
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage18-"));
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
    width: 1600,
    height: 1100,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function fetchVisibleCoverJobs() {
  const response = await fetchJson(`${BASE_URL}/api/jobs?job_type=cover&status=%E5%AE%8C%E6%88%90&limit=100`);
  return (response.items || []).filter(item => item && item.job_id);
}

async function ensureDashboard(client) {
  await client.navigate(DASHBOARD_URL);
  await client.waitFor("Boolean(document.querySelector('#modelPanel'))", 20000, "modelPanel");
  await client.waitFor("Boolean(document.getElementById('modelsInventoryToggleBtn'))", 20000, "models inventory toggle");
  await client.waitFor("Boolean(document.getElementById('modelsInventoryBody'))", 20000, "models inventory body");
}

async function verifyDashboardDrawer(client) {
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === true", 20000, "models drawer collapsed");
  await client.evaluate(`(() => { document.getElementById('modelsInventoryToggleBtn')?.click(); return true; })()`);
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === false", 20000, "models drawer expanded");

  await client.evaluate(`(() => { document.getElementById('modelsRefreshBtn')?.click(); return true; })()`);
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === false", 20000, "models drawer stays expanded after refresh");

  await client.send("Page.reload", { ignoreCache: true });
  await client.waitFor("document.readyState === 'complete'", 20000, "dashboard reload");
  await client.waitFor("Boolean(document.getElementById('modelsInventoryBody'))", 20000, "models body after reload");
  await client.waitFor("document.getElementById('modelsInventoryBody')?.hidden === false", 20000, "models drawer persisted expanded");
}

async function openStudio(client, jobId) {
  await client.navigate(`${BASE_URL}/studio?job_id=${encodeURIComponent(jobId)}`);
  await client.waitFor("Boolean(document.getElementById('studioLibraryToggleBtn'))", 20000, "studio library toggle");
  await client.waitFor("Boolean(document.getElementById('studioLibraryBody'))", 20000, "studio library body");
}

async function verifyStudioDrawer(client, jobs) {
  const [firstJob, secondJob] = jobs;
  if (!firstJob || !secondJob) {
    throw new Error("Need at least two completed cover jobs for Studio drawer verification");
  }

  await client.waitFor("document.getElementById('studioLibraryBody')?.hidden === true", 20000, "studio drawer collapsed");
  await client.evaluate(`(() => { document.getElementById('studioLibraryToggleBtn')?.click(); return true; })()`);
  await client.waitFor("document.getElementById('studioLibraryBody')?.hidden === false", 20000, "studio drawer expanded");

  await client.evaluate(`
    (() => {
      const target = Array.from(document.querySelectorAll('#studioResourceList [data-job-id]'))
        .find(node => node.dataset.jobId === ${JSON.stringify(secondJob.job_id)});
      target?.click();
      return target?.dataset?.jobId || "";
    })()
  `);

  await client.waitFor(
    `document.getElementById("studioCurrentJobId")?.textContent?.includes(${JSON.stringify(secondJob.job_id)})`,
    20000,
    "studio switched job",
  );

  await client.send("Page.reload", { ignoreCache: true });
  await client.waitFor("document.readyState === 'complete'", 20000, "studio reload");
  await client.waitFor("document.getElementById('studioLibraryBody')?.hidden === false", 20000, "studio drawer persisted expanded");
  await client.waitFor(
    `document.getElementById("studioCurrentJobId")?.textContent?.includes(${JSON.stringify(secondJob.job_id)})`,
    20000,
    "studio preserved selection",
  );

  await client.waitFor("Boolean(document.getElementById('studioAudio')?.src)", 20000, "studio audio src");
  const playResult = await client.evaluate(`
    (() => {
      const audio = document.getElementById("studioAudio");
      if (!audio) return "audio element missing";
      return audio.play().then(() => true).catch(error => error?.message || String(error));
    })()
  `);
  if (playResult !== true) {
    throw new Error(`studio audio play failed: ${playResult}`);
  }

  await client.waitFor(
    "document.getElementById('studioAudio') && !document.getElementById('studioAudio').paused",
    10000,
    "audio playback start",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureDashboard(client);
    await verifyDashboardDrawer(client);
    await client.screenshot(DASHBOARD_SHOT);

    const jobs = await fetchVisibleCoverJobs();
    if (jobs.length < 2) {
      throw new Error(`Need at least two completed cover jobs, got ${jobs.length}`);
    }

    await openStudio(client, jobs[0].job_id);
    await verifyStudioDrawer(client, jobs);

    await client.screenshot(STUDIO_SHOT);

    console.log("STAGE18_PLAYWRIGHT_SMOKE PASS");
    console.log(`Dashboard screenshot: ${DASHBOARD_SHOT}`);
    console.log(`Studio screenshot: ${STUDIO_SHOT}`);
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
  console.error("STAGE18_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
