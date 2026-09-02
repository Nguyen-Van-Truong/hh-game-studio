import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const CHROME =
  process.env.CHROME_PATH ??
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const DEBUG_PORT = 9333;
const BASE = process.env.HON_GIO_URL ?? "http://127.0.0.1:4173";
const OUT_DIR = join(import.meta.dirname);

mkdirSync(OUT_DIR, { recursive: true });

function makeSender(ws) {
  let nextId = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data));
    if (message.id != null && pending.has(message.id)) {
      const settle = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        settle.reject(new Error(JSON.stringify(message.error)));
      } else {
        settle.resolve(message.result);
      }
    }
  });
  return (method, params, sessionId) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      const payload = { id, method, params };
      if (sessionId) {
        payload.sessionId = sessionId;
      }
      ws.send(JSON.stringify(payload));
    });
}

async function waitForOpen(ws) {
  if (ws.readyState === WebSocket.OPEN) {
    return;
  }
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
}

const userData = mkdtempSync(join(tmpdir(), "hongio-chrome-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    "--remote-allow-origins=*",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--enable-webgl2",
    "--use-angle=d3d11",
    "--disable-extensions",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${userData}`,
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let version;
for (let attempt = 0; attempt < 40; attempt += 1) {
  try {
    version = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`).then(
      (response) => response.json(),
    );
    break;
  } catch {
    await delay(150);
  }
}

if (!version?.webSocketDebuggerUrl) {
  chrome.kill();
  throw new Error("Chrome DevTools endpoint did not start.");
}

const ws = new WebSocket(version.webSocketDebuggerUrl);
await waitForOpen(ws);
const send = makeSender(ws);

const { targetId } = await send("Target.createTarget", {
  url: "about:blank",
});
const { sessionId } = await send("Target.attachToTarget", {
  targetId,
  flatten: true,
});

const page = (method, params = {}) => send(method, params, sessionId);

await page("Page.enable");
await page("Runtime.enable");
await page("Emulation.setDeviceMetricsOverride", {
  width: 1280,
  height: 720,
  deviceScaleFactor: 1,
  mobile: false,
});

async function openAndWait(url, extraWaitMs = 3500) {
  await page("Page.navigate", { url });
  await delay(extraWaitMs);
  const probe = await page("Runtime.evaluate", {
    expression: `(() => ({
      title: document.title,
      text: document.body ? document.body.innerText.slice(0, 1200) : "",
      canvas: Boolean(document.querySelector("canvas")),
      canvasSize: (() => {
        const canvas = document.querySelector("canvas");
        if (!canvas) return null;
        return { w: canvas.width, h: canvas.height, cw: canvas.clientWidth, ch: canvas.clientHeight };
      })(),
      header: Boolean(document.querySelector(".site-mark")),
      headerText: document.querySelector(".site-mark")?.textContent ?? "",
      status: document.querySelector(".site-status")?.textContent ?? "",
      hints: document.querySelector(".control-hint")?.textContent ?? "",
      buttons: Array.from(document.querySelectorAll("button")).map((b) => b.textContent.trim()),
    }))()`,
    returnByValue: true,
  });
  return probe.result?.value ?? probe;
}

async function shot(name, width, height, extraWaitMs = 700) {
  await page("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 500,
  });
  await delay(extraWaitMs);
  const result = await page("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  const file = join(OUT_DIR, name);
  writeFileSync(file, Buffer.from(result.data, "base64"));
  return file;
}

const shots = [];
const playProbe = await openAndWait(`${BASE}/?walk=1`, 1980);
shots.push(await shot("play-walk.png", 1280, 720, 80));

const boatProbe = await openAndWait(`${BASE}/?boat=1&walk=1`, 1500);
shots.push(await shot("play-boat.png", 1280, 720, 200));

const overviewProbe = await openAndWait(`${BASE}/?preset=overview`);
shots.push(await shot("overview-1280x720.png", 1280, 720));

await openAndWait(`${BASE}/?select=lighthouse&preset=overview`);
shots.push(await shot("select-lighthouse.png", 1280, 720));

await page("Emulation.setDeviceMetricsOverride", {
  width: 1024,
  height: 768,
  deviceScaleFactor: 1,
  mobile: false,
});
await openAndWait(`${BASE}/`);
shots.push(await shot("overview-1024x768.png", 1024, 768));

await page("Emulation.setDeviceMetricsOverride", {
  width: 390,
  height: 844,
  deviceScaleFactor: 1,
  mobile: true,
});
await openAndWait(`${BASE}/`);
shots.push(await shot("overview-390x844.png", 390, 844));

const fallbackProbe = await openAndWait(`${BASE}/?fallback=1`, 1200);
shots.push(await shot("fallback.png", 1280, 720));

const report = {
  url: `${BASE}/`,
  playProbe,
  boatProbe,
  overviewProbe,
  fallbackProbe,
  shots,
};

writeFileSync(join(OUT_DIR, "capture-probe.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));

await send("Browser.close").catch(() => undefined);
ws.close();
chrome.kill();
process.exit(0);
