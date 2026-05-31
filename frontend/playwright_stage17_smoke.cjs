const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = `${BASE_URL}/`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9233;
const DASHBOARD_SHOT = path.join(__dirname, "..", "stage17_dashboard.png");
const STUDIO_SHOT = path.join(__dirname, "..", "stage17_studio.png");

function expect(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

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
      if (version.webSocketDebuggerUrl) {
        return version;
      }
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
      const onError = (event) => reject(new Error(`CDP websocket error: ${event?.message || "unknown"}`));

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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage17-"));
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

async function ensureDashboard(client) {
  await client.navigate(DASHBOARD_URL);
  await client.waitFor("Boolean(document.querySelector('#taskCenter'))", 20000, "#taskCenter");
  await client.waitFor("Boolean(document.querySelector('#entryCenter'))", 20000, "#entryCenter");
  await client.waitFor("Boolean(document.querySelector('#modelPanel'))", 20000, "#modelPanel");
  await client.waitFor("Boolean(document.querySelector('#diagnosticsPanel'))", 20000, "#diagnosticsPanel");
  await client.waitFor("Boolean(document.querySelector('.page-nav-link[href=\"/studio\"]'))", 20000, "Studio nav link");
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

    if (!(rowCount > 0)) {
      return "";
    }
  }

  const jobId = await client.evaluate(`
    (() => {
      const row = ${preferredJobId ? `document.querySelector('#jobsTableBody .job-row[data-job-id="${preferredJobId}"]') || ` : ""}document.querySelector("#jobsTableBody .job-row");
      row?.click();
      return row?.dataset?.jobId || "";
    })()
  `);

  return jobId;
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
        // Keep searching for a usable completed cover job.
      }
    }

    const first = items.find(item => item && item.job_id);
    if (first?.job_id) return first.job_id;
  }

  return "";
}

async function openStudioFromDashboard(client, fallbackJobId) {
  const clicked = await client.evaluate(`
    (() => {
      const button = document.querySelector('#jobActionBar button[data-open-studio="true"]');
      if (!button) return false;
      button.click();
      return true;
    })()
  `);

  if (!clicked && fallbackJobId) {
    await client.navigate(`${BASE_URL}/studio?job_id=${encodeURIComponent(fallbackJobId)}`);
  }

  await client.waitFor('location.pathname === "/studio"', 20000, "Studio page navigation");
  await client.waitFor("Boolean(document.getElementById('studioResourceSelect'))", 20000, "studioResourceSelect");
  await client.waitFor("Boolean(document.getElementById('studioAudio')?.src)", 20000, "studio audio src");
  await client.waitFor(
    'document.getElementById("studioDownloadBtn")?.getAttribute("aria-disabled") === "false"',
    20000,
    "enabled Studio download button",
  );
}

async function verifyStudioPlayback(client, expectedJobId) {
  await client.waitFor(
    `document.getElementById("studioCurrentJobId")?.textContent?.includes(${JSON.stringify(expectedJobId)})`,
    20000,
    `Studio current job id ${expectedJobId}`,
  );

  const playResult = await client.evaluate(`
    (() => {
      const audio = document.getElementById("studioAudio");
      if (!audio) return "audio element missing";
      return audio.play().then(() => true).catch(error => error?.message || String(error));
    })()
  `);

  expect(playResult === true, `studio audio play failed: ${playResult}`);
  await client.waitFor("document.getElementById('studioAudio') && !document.getElementById('studioAudio').paused", 10000, "audio playback start");
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureDashboard(client);
    const visibleJobId = await selectCompletedCoverJob(client);
    const fallbackJobId = await fetchLatestCompletedCoverJobId();
    const jobId = visibleJobId || fallbackJobId;
    expect(Boolean(jobId), "no completed cover job available for Studio verification");
    await client.screenshot(DASHBOARD_SHOT);

    await openStudioFromDashboard(client, jobId);
    await verifyStudioPlayback(client, jobId);
    await client.screenshot(STUDIO_SHOT);

    console.log("STAGE17_PLAYWRIGHT_SMOKE PASS");
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
  console.error("STAGE17_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
