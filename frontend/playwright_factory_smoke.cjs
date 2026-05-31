const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const FACTORY_URL = `${BASE_URL}/factory`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9236;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage20_factory.png");

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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage20-factory-"));
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

async function ensureFactoryPage(client) {
  await client.navigate(FACTORY_URL);
  await client.waitFor("Boolean(document.querySelector('#factoryCreateBatchForm'))", 20000, "factoryCreateBatchForm");
  await client.waitFor("Boolean(document.querySelector('#factoryImportTracksForm'))", 20000, "factoryImportTracksForm");
  await client.waitFor("Boolean(document.querySelector('#factoryLyricText'))", 20000, "factoryLyricText");
}

async function createBatchFromPage(client, batchName) {
  return client.evaluate(`
    (async () => {
      const response = await fetch("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_name: ${JSON.stringify(batchName)},
          target_platforms: ["douyin", "bilibili"],
          metadata: { smoke: true, source: "playwright_factory_smoke" }
        })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    })()
  `);
}

async function importTracksFromPage(client, batchId) {
  return client.evaluate(`
    (async () => {
      const formData = new FormData();
      const fileA = new File([new Uint8Array([1, 2, 3, 4])], "factory-smoke-a.wav", { type: "audio/wav" });
      const fileB = new File([new Uint8Array([5, 6, 7, 8])], "factory-smoke-b.wav", { type: "audio/wav" });
      formData.append("files", fileA);
      formData.append("files", fileB);
      formData.append("titles_json", JSON.stringify(["stage20_smoke_track_a", "stage20_smoke_track_b"]));
      formData.append("artist", "stage20_smoke_artist");
      formData.append("notes", "playwright smoke");
      formData.append("metadata_json", JSON.stringify({ smoke: true, source: "playwright_factory_smoke" }));
      const response = await fetch("/api/batches/${batchId}/tracks/import", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    })()
  `);
}

async function getTrackLyricState(client, trackId) {
  return client.evaluate(`
    (async () => {
      const response = await fetch("/api/tracks/${trackId}/lyrics/versions");
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    })()
  `);
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureFactoryPage(client);
    const batchName = `stage20_smoke_factory_${Date.now()}`;
    const batch = await createBatchFromPage(client, batchName);
    const batchId = batch.batch_id;
    if (!batchId) throw new Error("batch creation did not return batch_id");

    await client.evaluate(`document.getElementById("factoryRefreshBtn")?.click();`);
    await client.waitFor(
      `Boolean(document.querySelector('#factoryBatchesList [data-batch-id="${batchId}"]'))`,
      20000,
      `batch ${batchId} visible in list`,
    );
    await client.evaluate(`
      (() => {
        const batch = document.querySelector('#factoryBatchesList [data-batch-id="${batchId}"]');
        batch?.click();
        return Boolean(batch);
      })()
    `);
    await client.waitFor(
      `document.getElementById("factoryBatchTitle")?.textContent?.includes(${JSON.stringify(batchName)})`,
      20000,
      "selected batch title",
    );

    const importPayload = await importTracksFromPage(client, batchId);
    const importedTracks = importPayload.imported_tracks || [];
    if (importedTracks.length < 2) throw new Error("expected at least two imported tracks");

    await client.evaluate(`document.getElementById("factoryReloadTracksBtn")?.click();`);
    await client.waitFor(
      `Boolean(document.querySelector('#factoryTracksList [data-track-id="${importedTracks[1].track_id}"]'))`,
      20000,
      `track ${importedTracks[1].track_id} visible in list`,
    );
    await client.evaluate(`
      (() => {
        const track = document.querySelector('#factoryTracksList [data-track-id="${importedTracks[1].track_id}"]');
        track?.click();
        return Boolean(track);
      })()
    `);
    await client.waitFor(
      `document.getElementById("factoryTrackTitle")?.textContent?.includes(${JSON.stringify(importedTracks[1].title)})`,
      20000,
      "selected track title",
    );

    await client.evaluate(`document.getElementById("factoryExtractLyricsBtn")?.click();`);
    await client.waitFor("document.getElementById('factoryLyricText')?.value?.length > 0", 20000, "lyric draft text");

    await client.evaluate(`document.getElementById("factoryAlignLyricsBtn")?.click();`);
    await client.waitFor(
      "document.querySelectorAll('#factoryLyricVersions [data-promote-timeline]').length >= 1",
      20000,
      "first timeline version",
    );
    const firstVersion = await getTrackLyricState(client, importedTracks[1].track_id);
    const firstTimelineId = firstVersion.current_timeline_version_id || "";
    if (!firstTimelineId) throw new Error("first timeline version was not created");

    await client.evaluate(`
      (() => {
        const textarea = document.getElementById("factoryLyricText");
        textarea.value = ${JSON.stringify(`${importedTracks[1].title}\nSecond version for promotion`)};
        document.getElementById("factoryAlignLyricsBtn")?.click();
        return true;
      })()
    `);
    await client.waitFor(
      "document.querySelectorAll('#factoryLyricVersions [data-promote-timeline]').length >= 2",
      20000,
      "second timeline version",
    );

    const secondVersion = await getTrackLyricState(client, importedTracks[1].track_id);
    const oldTimelineId = (secondVersion.versions || []).find(item => item.timeline_id !== secondVersion.current_timeline_version_id)?.timeline_id || "";
    if (!oldTimelineId) throw new Error("did not find an older timeline version to promote");

    await client.evaluate(`
      (() => {
        const button = document.querySelector('#factoryLyricVersions [data-promote-timeline="${oldTimelineId}"]');
        button?.click();
        return Boolean(button);
      })()
    `);

    await client.waitFor(
      `document.getElementById("factoryTrackLyricState")?.textContent?.includes(${JSON.stringify(oldTimelineId)})`,
      20000,
      "promoted timeline reflected in UI",
    );

    const promotedVersion = await getTrackLyricState(client, importedTracks[1].track_id);
    if (promotedVersion.current_timeline_version_id !== oldTimelineId) {
      throw new Error(`timeline promotion failed: expected ${oldTimelineId}, got ${promotedVersion.current_timeline_version_id || ""}`);
    }

    await client.screenshot(SCREENSHOT_PATH);
    console.log("FACTORY_PLAYWRIGHT_SMOKE PASS");
    console.log(`Screenshot: ${SCREENSHOT_PATH}`);
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
  console.error("FACTORY_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
