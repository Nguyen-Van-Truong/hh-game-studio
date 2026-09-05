/**
 * Follow-up: compositor screenshots + cache-disabled first-map.
 * Same 4175 preview. NOT_PLAN_PASS.
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9235);
const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const OUT = dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(ws, id, method, params) {
  return new Promise((resolve, reject) => {
    const onMsg = (event) => {
      const raw = typeof event.data === "string" ? event.data : String(event.data);
      const msg = JSON.parse(raw);
      if (msg.id === id) {
        ws.removeEventListener("message", onMsg);
        if (msg.error) reject(new Error(`${method}: ${JSON.stringify(msg.error)}`));
        else resolve(msg.result);
      }
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evalExpr(ws, id, expression, awaitPromise = false) {
  const result = await cdp(ws, id, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise,
  });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

async function connectPage() {
  const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
  const targets = await res.json();
  const page = targets.find((t) => t.type === "page");
  if (!page?.webSocketDebuggerUrl) throw new Error(`no page ${JSON.stringify(targets)}`);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });
  return ws;
}

function sha16(buf) {
  let h = 2166136261;
  for (let i = 0; i < buf.length; i += 3) {
    h ^= buf[i];
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16);
}

async function shot(ws, id, name) {
  const result = await cdp(ws, id, "Page.captureScreenshot", { format: "png" });
  const buf = Buffer.from(result.data, "base64");
  const path = join(OUT, name);
  writeFileSync(path, buf);
  return { name, bytes: buf.length, sha16: sha16(buf) };
}

const ws = await connectPage();
await cdp(ws, 1, "Runtime.enable");
await cdp(ws, 2, "Page.enable");
await cdp(ws, 3, "Network.enable");
await cdp(ws, 4, "Emulation.setDeviceMetricsOverride", {
  width: 1280,
  height: 720,
  deviceScaleFactor: 1,
  mobile: false,
});
await cdp(ws, 5, "Emulation.setEmulatedMedia", {
  features: [{ name: "prefers-reduced-motion", value: "no-preference" }],
});
await cdp(ws, 6, "Network.setCacheDisabled", { cacheDisabled: true });
await cdp(ws, 7, "Page.navigate", { url: "about:blank" });
await sleep(250);
const t0 = Date.now();
await cdp(ws, 8, "Page.navigate", { url: PLAYER });
const firstMap = await evalExpr(
  ws,
  9,
  `(() => new Promise((resolve) => {
    const t = performance.now();
    const check = () => {
      const canvas = document.querySelector(".maplibregl-canvas");
      const markers = document.querySelectorAll(".map-marker");
      if (canvas && canvas.width > 0 && markers.length >= 4) {
        resolve({ ok: true, firstMapMsFromNav: performance.now(), pollMs: performance.now() - t, markers: markers.length, canvas: { w: canvas.width, h: canvas.height } });
        return;
      }
      if (performance.now() - t > 20000) {
        resolve({ ok: false, pollMs: performance.now() - t, markers: document.querySelectorAll(".map-marker").length });
        return;
      }
      requestAnimationFrame(check);
    };
    check();
  }))()`,
  true,
);
const hostFirstMapMs = Date.now() - t0;
await sleep(1200);
const media = await evalExpr(ws, 10, `window.matchMedia("(prefers-reduced-motion: reduce)").matches`);
const shotOn = await shot(ws, 11, "r2-wp1-map-extrusion-on.png");
await evalExpr(
  ws,
  12,
  `(() => { const el = document.querySelector(".layer-toggle input"); if (el && el.checked) el.click(); return el ? el.checked : null; })()`,
);
await sleep(800);
const shotOff = await shot(ws, 13, "r2-wp1-map-extrusion-off.png");
const toggleState = await evalExpr(ws, 14, `document.querySelector(".layer-toggle input")?.checked ?? null`);

await evalExpr(
  ws,
  15,
  `(() => { const el = document.querySelector(".layer-toggle input"); if (el && !el.checked) el.click(); return true; })()`,
);
await sleep(400);
await evalExpr(
  ws,
  16,
  `(() => { const close = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Close"); close?.click(); return true; })()`,
);
await sleep(200);
const tClick = Date.now();
await evalExpr(
  ws,
  17,
  `(() => { const btn = [...document.querySelectorAll('[data-testid="place-list"] button')].find((el) => el.textContent.includes("Clock Garden")); btn?.click(); return Boolean(btn); })()`,
);
const shotA = await shot(ws, 18, "r2-wp1-motion-nopref-t0.png");
await sleep(180);
const shotB = await shot(ws, 19, "r2-wp1-motion-nopref-t180.png");
await sleep(280);
const shotC = await shot(ws, 20, "r2-wp1-motion-nopref-t460.png");

await cdp(ws, 21, "Emulation.setEmulatedMedia", {
  features: [{ name: "prefers-reduced-motion", value: "reduce" }],
});
const mediaReduce = await evalExpr(ws, 22, `window.matchMedia("(prefers-reduced-motion: reduce)").matches`);
await evalExpr(
  ws,
  23,
  `(() => { const close = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Close"); close?.click(); return true; })()`,
);
await sleep(250);
await evalExpr(
  ws,
  24,
  `(() => { const btn = [...document.querySelectorAll('[data-testid="place-list"] button')].find((el) => el.textContent.includes("Market Steps")); btn?.click(); return Boolean(btn); })()`,
);
const shotR0 = await shot(ws, 25, "r2-wp1-motion-reduce-t0.png");
await sleep(180);
const shotR1 = await shot(ws, 26, "r2-wp1-motion-reduce-t180.png");
await sleep(280);
const shotR2 = await shot(ws, 27, "r2-wp1-motion-reduce-t460.png");

ws.close();
const report = {
  hostFirstMapMs_cacheDisabled: hostFirstMapMs,
  firstMap,
  prefersReducedMotion_noPreferenceEmulated: media,
  prefersReducedMotion_reduceEmulated: mediaReduce,
  extrusionToggleAfterClick: toggleState,
  shots: { shotOn, shotOff, shotA, shotB, shotC, shotR0, shotR1, shotR2 },
  extrusionPngChanged: shotOn.sha16 !== shotOff.sha16,
  noprefFramesDiffer: new Set([shotA.sha16, shotB.sha16, shotC.sha16]).size > 1,
  reduceFramesDiffer: new Set([shotR0.sha16, shotR1.sha16, shotR2.sha16]).size > 1,
  clickToFirstShotMs: Date.now() - tClick,
};
console.log(JSON.stringify(report, null, 2));
