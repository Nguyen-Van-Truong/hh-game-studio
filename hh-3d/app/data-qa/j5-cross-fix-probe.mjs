/**
 * Cross-audit remint: leftover shops must not own Nearby E;
 * spawn/north sky not beige; B observes A's opposite-stride.
 * Catalog persist stays. NOT_PLAN_PASS. Not GATE-U1 / OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-CROSS-FIX-2026-09-04.txt");
const SHOT_SPAWN = join(import.meta.dirname, "j5-3d-cross-fix-spawn.png");
const SHOT_B = join(import.meta.dirname, "j5-3d-cross-fix-seat-b.png");
const SHOT_WALK = join(import.meta.dirname, "j5-3d-cross-fix-friend-walk.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9491), b: 9492 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-02";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
  if (result.exceptionDetails) {
    throw new Error(JSON.stringify(result.exceptionDetails));
  }
  return result.result.value;
}

async function keyHold(ws, id, key, code, vk, ms) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
  await sleep(ms);
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function connectPage(port) {
  const deadline = Date.now() + 25000;
  let last = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await res.json();
      last = targets;
      const page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
          ws.addEventListener("open", resolve);
          ws.addEventListener("error", reject);
        });
        return { ws, page };
      }
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error(`no CDP page on ${port}: ${JSON.stringify(last)}`);
}

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-cross-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--window-size=1280,720",
      url,
    ],
    { stdio: "ignore" },
  );
}

function decodePngRgba(buf) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (buf.length < 24 || !buf.subarray(0, 8).equals(sig)) {
    throw new Error("not a PNG");
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idats = [];
  while (offset + 12 <= buf.length) {
    const len = buf.readUInt32BE(offset);
    const type = buf.toString("ascii", offset + 4, offset + 8);
    const data = buf.subarray(offset + 8, offset + 8 + len);
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") {
      idats.push(data);
    } else if (type === "IEND") {
      break;
    }
    offset += 12 + len;
  }
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(`unsupported PNG ${bitDepth}/${colorType}`);
  }
  const bpp = colorType === 6 ? 4 : 3;
  const raw = inflateSync(Buffer.concat(idats));
  const stride = width * bpp;
  const pixels = Buffer.alloc(width * height * 4);
  let src = 0;
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[src];
    src += 1;
    const row = raw.subarray(src, src + stride);
    src += stride;
    const out = Buffer.alloc(stride);
    for (let i = 0; i < stride; i += 1) {
      const left = i >= bpp ? out[i - bpp] : 0;
      const up = prev[i];
      const upLeft = i >= bpp ? prev[i - bpp] : 0;
      const x = row[i];
      if (filter === 0) out[i] = x;
      else if (filter === 1) out[i] = (x + left) & 255;
      else if (filter === 2) out[i] = (x + up) & 255;
      else if (filter === 3) out[i] = (x + Math.floor((left + up) / 2)) & 255;
      else if (filter === 4) {
        const p = left + up - upLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upLeft);
        const pr = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        out[i] = (x + pr) & 255;
      } else {
        throw new Error(`bad PNG filter ${filter}`);
      }
    }
    for (let x = 0; x < width; x += 1) {
      const di = (y * width + x) * 4;
      const si = x * bpp;
      pixels[di] = out[si];
      pixels[di + 1] = out[si + 1];
      pixels[di + 2] = out[si + 2];
      pixels[di + 3] = bpp === 4 ? out[si + 3] : 255;
    }
    prev = out;
  }
  return { width, height, pixels };
}

function bandStats(pixels, width, height, x0, y0, x1, y1) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let blueish = 0;
  const xa = Math.max(0, Math.floor(x0));
  const ya = Math.max(0, Math.floor(y0));
  const xb = Math.min(width, Math.ceil(x1));
  const yb = Math.min(height, Math.ceil(y1));
  for (let y = ya; y < yb; y += step) {
    for (let x = xa; x < xb; x += step) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      sumR += r;
      sumG += g;
      sumB += b;
      if (r > 170 && g > 140 && b < 180 && r - b > 20) beige += 1;
      if (b > r + 8 && b > 90) blueish += 1;
    }
  }
  const meanR = n ? sumR / n : 0;
  const meanG = n ? sumG / n : 0;
  const meanB = n ? sumB / n : 0;
  return {
    samples: n,
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const pick = (el) =>
    el
      ? {
          testid: el.getAttribute("data-testid"),
          seat: el.getAttribute("data-seat"),
          body: el.getAttribute("data-body"),
          tunic: el.getAttribute("data-tunic"),
          pose: el.getAttribute("data-pose"),
          heading: el.getAttribute("data-heading"),
          lon: el.getAttribute("data-lon"),
          lat: el.getAttribute("data-lat"),
          limbSpread: el.getAttribute("data-limb-spread"),
          limbOpposite: el.getAttribute("data-limb-opposite"),
          limbMoving: el.getAttribute("data-limb-moving"),
        }
      : null;
  const remotes = [...document.querySelectorAll('[data-testid^="remote-avatar-"]')].map(pick).filter(Boolean);
  const remoteWalk = [...document.querySelectorAll('[data-testid^="remote-walk-cycle-"]')].map((el) => ({
    seat: el.getAttribute("data-seat"),
    spread: el.getAttribute("data-limb-spread"),
    opposite: el.getAttribute("data-limb-opposite"),
    moving: el.getAttribute("data-limb-moving"),
  }));
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const box = canvas
    ? (() => {
        const r = canvas.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
      })()
    : null;
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  return {
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height, box } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    remoteCount: Number(document.querySelector('[data-testid="people-layer"]')?.getAttribute("data-remote-count") ?? "-1"),
    remotes,
    remoteWalk,
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
    addB: Boolean(document.querySelector('[data-testid="add-friend-b"]')),
    honesty: document.body.innerText?.includes("NOT_PLAN_PASS") ?? false,
  };
})()`;

async function waitSnap(ws, startId, pred, tries = 24, delay = 300) {
  let last = null;
  let id = startId;
  for (let i = 0; i < tries; i += 1) {
    last = await evalExpr(ws, id, SNAP);
    id += 1;
    if (pred(last)) {
      return { snap: last, nextId: id };
    }
    await sleep(delay);
  }
  return { snap: last, nextId: id };
}

async function resetBus() {
  const origin = PLAYER.replace(/\/$/, "");
  await fetch(`${origin}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      graph_clear: true,
      leave: "a",
    }),
  });
  await fetch(`${origin}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      leave: "b",
    }),
  });
}

const chromes = [];
let report;
try {
  await resetBus();
  chromes.push(launchChrome(PORTS.a, `${PLAYER}?seat=a`));
  chromes.push(launchChrome(PORTS.b, `${PLAYER}?seat=b`));
  const a = await connectPage(PORTS.a);
  const b = await connectPage(PORTS.b);
  for (const [ws, base] of [
    [a.ws, 1],
    [b.ws, 1],
  ]) {
    await cdp(ws, base, "Runtime.enable");
    await cdp(ws, base + 1, "Page.enable");
    await cdp(ws, base + 2, "Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 720,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }
  await sleep(600);
  const origin = PLAYER.replace(/\/$/, "");
  for (const [ws, seat, base] of [
    [a.ws, "a", 10],
    [b.ws, "b", 10],
  ]) {
    await cdp(ws, base, "Storage.clearDataForOrigin", {
      origin,
      storageTypes: "local_storage",
    });
    await cdp(ws, base + 1, "Page.navigate", { url: `${PLAYER}?seat=${seat}` });
  }
  const readyA = await waitSnap(a.ws, 20, (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200, 30, 250);
  const readyB = await waitSnap(b.ws, 20, (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200, 30, 250);

  const spawnShot = await cdp(a.ws, 30, "Page.captureScreenshot", { format: "png" });
  const spawnBuf = Buffer.from(spawnShot.data, "base64");
  writeFileSync(SHOT_SPAWN, spawnBuf);
  const spawnPng = decodePngRgba(spawnBuf);
  const canvasBox = readyA.snap.canvas?.box ?? { left: 0, top: 48, w: 1280, h: 672 };
  const skyBand = bandStats(
    spawnPng.pixels,
    spawnPng.width,
    spawnPng.height,
    canvasBox.left + canvasBox.w * 0.38,
    canvasBox.top + canvasBox.h * 0.05,
    canvasBox.left + canvasBox.w * 0.62,
    canvasBox.top + canvasBox.h * 0.16,
  );

  const seatBShot = await cdp(b.ws, 31, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_B, Buffer.from(seatBShot.data, "base64"));

  const eOk =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";

  await evalExpr(a.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, 41, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  await waitSnap(b.ws, 41, (s) => s.acceptA === true, 16, 250);
  await evalExpr(b.ws, 50, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  await evalExpr(a.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(b.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(a.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);

  await sleep(400);
  const friendsB = await waitSnap(
    b.ws,
    60,
    (s) => s.remoteCount === 1 && s.remotes.some((row) => row.seat === "a"),
    28,
    300,
  );

  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(200);
  await keyHold(a.ws, 81, "w", "KeyW", 87, 5000);
  const walked = await waitSnap(
    b.ws,
    90,
    (s) => {
      const row = s.remotes.find((item) => item.seat === "a");
      const proof = s.remoteWalk.find((item) => item.seat === "a");
      const spread = Number(proof?.spread ?? row?.limbSpread ?? 0);
      const opposite = (proof?.opposite ?? row?.limbOpposite) === "1";
      const moving = (proof?.moving ?? row?.limbMoving) === "1" || row?.pose === "walk";
      return Boolean(row && spread > 0.6 && opposite && moving);
    },
    30,
    200,
  );
  const walkShot = await cdp(b.ws, 120, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_WALK, Buffer.from(walkShot.data, "base64"));

  await keyHold(a.ws, 130, "w", "KeyW", 87, 14000);
  await sleep(400);
  await keyHold(a.ws, 140, "e", "KeyE", 69, 180);
  await sleep(400);
  const lanternA = await evalExpr(a.ws, 150, SNAP);

  const remoteA = walked.snap.remotes.find((row) => row.seat === "a");
  const remoteProof =
    walked.snap.remoteWalk.find((row) => row.seat === "a") ?? remoteA;
  const skyOk = skyBand.bluerThanRed && skyBand.blueRatio > 0.28 && skyBand.beigeRatio < 0.08;
  const walkOk =
    Number(remoteProof?.spread) > 0.8 &&
    remoteProof?.opposite === "1" &&
    (remoteProof?.moving === "1" || remoteA?.pose === "walk");
  const lanternOk = /lantern|shop-lantern-fish/i.test(lanternA.shopPanelId || "");
  const honestyOk = Boolean(readyA.snap.honesty);
  const hash = createHash("sha256").update(spawnBuf).digest("hex").slice(0, 16);
  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: eOk && skyOk && walkOk && lanternOk && honestyOk ? "J5_CROSS_FIX_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    eOk,
    skyOk,
    walkOk,
    lanternOk,
    honestyOk,
    skyBand,
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
    },
    remoteA,
    remoteProof,
    walkedRemotes: walked.snap.remotes,
    walkedRemoteWalk: walked.snap.remoteWalk,
    lanternPanel: lanternA.shopPanelId,
    hash,
    shotSpawn: SHOT_SPAWN,
    shotB: SHOT_B,
    shotWalk: SHOT_WALK,
    friendsB: friendsB.snap.remoteCount,
  };
  a.ws.close();
  b.ws.close();
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  for (const chrome of chromes) {
    chrome.kill();
  }
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_CROSS_FIX_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `eOk=${report.eOk}`,
  `nearbyB=${report.seatB?.nearbyShop || "none"}`,
  `skyBlue=${report.skyBand?.blueRatio}`,
  `remoteSpread=${report.remoteProof?.spread}`,
  `lantern=${report.lanternPanel}`,
);
