/**
 * Claim 4 remint: B default view sees A's tunic; look-down stays street;
 * same-body remote gait pixel-diff. Recycle 4175 only. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-FRIEND-GAIT-2026-09-04.txt");
const SHOT_B = join(import.meta.dirname, "j5-3d-friend-gait-b.png");
const SHOT_STAND = join(import.meta.dirname, "j5-3d-friend-gait-stand.png");
const SHOT_WALK1 = join(import.meta.dirname, "j5-3d-friend-gait-walk1.png");
const SHOT_WALK2 = join(import.meta.dirname, "j5-3d-friend-gait-walk2.png");
const SHOT_DOWN = join(import.meta.dirname, "j5-3d-friend-gait-lookdown.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9524), b: Number(process.env.HH_CDP_PORT_B || 9525) };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-03";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const DRAG = `(dx, dy) => {
  const c = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  if (!c) return { ok: false };
  const r = c.getBoundingClientRect();
  const x = r.left + r.width * 0.5;
  const y = r.top + r.height * 0.42;
  const base = { bubbles: true, cancelable: true, pointerId: 7, pointerType: "mouse", isPrimary: true };
  c.dispatchEvent(new PointerEvent("pointerdown", { ...base, button: 2, buttons: 2, clientX: x, clientY: y }));
  c.dispatchEvent(new PointerEvent("pointermove", {
    ...base, button: 2, buttons: 2, clientX: x + dx, clientY: y + dy, movementX: dx, movementY: dy,
  }));
  return { ok: true, x, y };
}`;

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

async function keyDown(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function keyUp(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function keyHold(ws, id, key, code, vk, ms) {
  await keyDown(ws, id, key, code, vk);
  await sleep(ms);
  await keyUp(ws, id + 1, key, code, vk);
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-gait-${port}-`));
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

function isTeal(r, g, b) {
  return g > r + 8 && b > r && g > 50 && g < 170 && r < 120 && b < 170;
}

function cropBox(png, cx, cy, hw = 55, hh = 85) {
  return {
    x0: Math.max(0, Math.floor(cx - hw)),
    y0: Math.max(0, Math.floor(cy - hh)),
    x1: Math.min(png.width, Math.ceil(cx + hw)),
    y1: Math.min(png.height, Math.ceil(cy + hh)),
  };
}

function cropStats(png, box) {
  let n = 0;
  let teal = 0;
  let black = 0;
  let sum = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  for (let y = box.y0; y < box.y1; y += 2) {
    for (let x = box.x0; x < box.x1; x += 2) {
      const i = (y * png.width + x) * 4;
      const r = png.pixels[i];
      const g = png.pixels[i + 1];
      const b = png.pixels[i + 2];
      n += 1;
      sum += 0.2126 * r + 0.7152 * g + 0.0722 * b;
      sumR += r;
      sumG += g;
      sumB += b;
      if (isTeal(r, g, b)) teal += 1;
      if (r + g + b < 24) black += 1;
    }
  }
  return {
    samples: n,
    tealRatio: Number((teal / Math.max(1, n)).toFixed(4)),
    blackRatio: Number((black / Math.max(1, n)).toFixed(4)),
    lum: Number((sum / Math.max(1, n)).toFixed(1)),
    meanR: Number((sumR / Math.max(1, n)).toFixed(1)),
    meanG: Number((sumG / Math.max(1, n)).toFixed(1)),
    meanB: Number((sumB / Math.max(1, n)).toFixed(1)),
  };
}

function pixelDiff(a, b, boxA, boxB) {
  const w = Math.min(boxA.x1 - boxA.x0, boxB.x1 - boxB.x0);
  const h = Math.min(boxA.y1 - boxA.y0, boxB.y1 - boxB.y0);
  let n = 0;
  let diff = 0;
  for (let y = 0; y < h; y += 2) {
    for (let x = 0; x < w; x += 2) {
      const ia = ((boxA.y0 + y) * a.width + (boxA.x0 + x)) * 4;
      const ib = ((boxB.y0 + y) * b.width + (boxB.x0 + x)) * 4;
      n += 1;
      const dr = Math.abs(a.pixels[ia] - b.pixels[ib]);
      const dg = Math.abs(a.pixels[ia + 1] - b.pixels[ib + 1]);
      const db = Math.abs(a.pixels[ia + 2] - b.pixels[ib + 2]);
      if (dr + dg + db > 36) diff += 1;
    }
  }
  return Number((diff / Math.max(1, n)).toFixed(4));
}

function cropHash(png, box) {
  const h = createHash("sha256");
  for (let y = box.y0; y < box.y1; y += 1) {
    const start = (y * png.width + box.x0) * 4;
    h.update(png.pixels.subarray(start, start + (box.x1 - box.x0) * 4));
  }
  return h.digest("hex").slice(0, 16);
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
          screenX: el.getAttribute("data-screen-x"),
          screenY: el.getAttribute("data-screen-y"),
          onCanvas: el.getAttribute("data-on-canvas"),
        }
      : null;
  const remotes = [...document.querySelectorAll('[data-testid^="remote-avatar-"]')].map(pick).filter(Boolean);
  const remoteWalk = [...document.querySelectorAll('[data-testid^="remote-walk-cycle-"]')].map((el) => ({
    seat: el.getAttribute("data-seat"),
    spread: el.getAttribute("data-limb-spread"),
    opposite: el.getAttribute("data-limb-opposite"),
    moving: el.getAttribute("data-limb-moving"),
    screenX: el.getAttribute("data-screen-x"),
    screenY: el.getAttribute("data-screen-y"),
    onCanvas: el.getAttribute("data-on-canvas"),
  }));
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
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
    cam: proof
      ? {
          hit: proof.getAttribute("data-cam-hit"),
          hitId: proof.getAttribute("data-cam-hit-id"),
          dist: proof.getAttribute("data-cam-dist"),
          side: proof.getAttribute("data-cam-side"),
          inside: proof.getAttribute("data-cam-inside"),
          insideId: proof.getAttribute("data-cam-inside-id"),
          pitch: proof.getAttribute("data-cam-pitch"),
          yaw: proof.getAttribute("data-cam-yaw"),
          y: proof.getAttribute("data-cam-y"),
        }
      : null,
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

function remoteA(snap) {
  return snap?.remotes?.find((row) => row.seat === "a") ?? null;
}

function remoteProof(snap) {
  return snap?.remoteWalk?.find((row) => row.seat === "a") ?? remoteA(snap);
}

function bodyBox(snap, png) {
  const row = remoteProof(snap) ?? remoteA(snap);
  const canvasBox = snap.canvas?.box ?? { left: 0, top: 48, w: 1280, h: 672 };
  const sx = Number(row?.screenX);
  const sy = Number(row?.screenY);
  const cx = Number.isFinite(sx) ? sx : canvasBox.left + canvasBox.w * 0.38;
  const cy = Number.isFinite(sy) ? sy : canvasBox.top + canvasBox.h * 0.55;
  return cropBox(png, cx, cy, 90, 130);
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

  const friendsB = await waitSnap(
    b.ws,
    60,
    (s) => Boolean(remoteA(s) || s.remoteWalk.some((row) => row.seat === "a")),
    32,
    300,
  );

  const seenB = await waitSnap(
    b.ws,
    friendsB.nextId,
    (s) => {
      const row = remoteA(s) ?? remoteProof(s);
      return row && (row.onCanvas === "1" || Number(row.screenY) > 40);
    },
    24,
    200,
  );

  const defaultShot = await cdp(b.ws, 200, "Page.captureScreenshot", { format: "png" });
  const defaultBuf = Buffer.from(defaultShot.data, "base64");
  writeFileSync(SHOT_B, defaultBuf);
  writeFileSync(SHOT_STAND, defaultBuf);
  const defaultPng = decodePngRgba(defaultBuf);
  const defaultSnap = seenB.snap;
  const defaultBox = bodyBox(defaultSnap, defaultPng);
  const defaultStats = cropStats(defaultPng, defaultBox);
  const standPng = defaultPng;
  const standSnap = defaultSnap;
  const standBox = defaultBox;
  const standHash = cropHash(standPng, standBox);
  const standStats = defaultStats;

  await evalExpr(
    a.ws,
    210,
    `(() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); document.body.click(); return true; })()`,
  );
  await sleep(120);
  await keyDown(a.ws, 211, "w", "KeyW", 87);

  const walking = await waitSnap(
    b.ws,
    220,
    (s) => {
      const row = remoteA(s);
      const proof = remoteProof(s);
      const spread = Number(proof?.spread ?? row?.limbSpread ?? 0);
      const opposite = (proof?.opposite ?? row?.limbOpposite) === "1";
      const moving = (proof?.moving ?? row?.limbMoving) === "1" || row?.pose === "walk";
      return Boolean(row && spread > 0.55 && opposite && moving && (proof?.onCanvas === "1" || row.onCanvas === "1"));
    },
    36,
    160,
  );

  const walk1Shot = await cdp(b.ws, 260, "Page.captureScreenshot", { format: "png" });
  const walk1Buf = Buffer.from(walk1Shot.data, "base64");
  writeFileSync(SHOT_WALK1, walk1Buf);
  const walk1Png = decodePngRgba(walk1Buf);
  const walk1Snap = await evalExpr(b.ws, 261, SNAP);
  const walk1Box = bodyBox(walk1Snap, walk1Png);
  const walk1Hash = cropHash(walk1Png, walk1Box);
  const walk1Stats = cropStats(walk1Png, walk1Box);
  const walk1Proof = remoteProof(walk1Snap) ?? remoteA(walking.snap);

  await sleep(340);
  const walk2Ready = await waitSnap(
    b.ws,
    262,
    (s) => {
      const row = remoteA(s) ?? remoteProof(s);
      return row && (row.onCanvas === "1" || Number(row.screenX) > 8) && Number(row.spread ?? row.limbSpread ?? 0) > 0.4;
    },
    12,
    80,
  );
  const walk2Shot = await cdp(b.ws, 280, "Page.captureScreenshot", { format: "png" });
  const walk2Buf = Buffer.from(walk2Shot.data, "base64");
  writeFileSync(SHOT_WALK2, walk2Buf);
  const walk2Png = decodePngRgba(walk2Buf);
  const walk2Snap = walk2Ready.snap;
  const walk2Box = bodyBox(walk2Snap, walk2Png);
  const walk2Hash = cropHash(walk2Png, walk2Box);
  const walk2Stats = cropStats(walk2Png, walk2Box);
  const walk2Proof = remoteProof(walk2Snap);

  await keyUp(a.ws, 270, "w", "KeyW", 87);

  const standVsWalk = pixelDiff(standPng, walk1Png, standBox, walk1Box);
  const walkPhaseDiff = pixelDiff(walk1Png, walk2Png, walk1Box, walk2Box);

  await evalExpr(b.ws, 290, `(${DRAG})(0, 220)`);
  await sleep(200);
  const downSnap = await evalExpr(b.ws, 291, SNAP);
  const downShot = await cdp(b.ws, 292, "Page.captureScreenshot", { format: "png" });
  const downBuf = Buffer.from(downShot.data, "base64");
  writeFileSync(SHOT_DOWN, downBuf);
  const downPng = decodePngRgba(downBuf);
  const canvasBox = downSnap.canvas?.box ?? { left: 0, top: 48, w: 1280, h: 672 };
  const downStats = cropStats(downPng, {
    x0: canvasBox.left + 80,
    y0: canvasBox.top + 40,
    x1: canvasBox.left + canvasBox.w - 80,
    y1: canvasBox.top + canvasBox.h - 40,
  });

  await keyHold(a.ws, 300, "w", "KeyW", 87, 14000);
  await sleep(300);
  await keyHold(a.ws, 310, "e", "KeyE", 69, 180);
  await sleep(400);
  const lanternA = await evalExpr(a.ws, 320, SNAP);

  const walkSpread = Number(walk1Proof?.spread ?? walk1Proof?.limbSpread ?? 0);
  const walkOpposite = (walk1Proof?.opposite ?? walk1Proof?.limbOpposite) === "1";
  const seenRow = remoteA(defaultSnap) ?? remoteProof(defaultSnap);
  const seeA =
    defaultSnap.cam?.inside !== "1" &&
    defaultStats.tealRatio > 0.02 &&
    (seenRow?.onCanvas === "1" || Number(seenRow?.screenY) > 40 || defaultStats.tealRatio > 0.03);
  const gaitOk =
    standVsWalk > 0.02 &&
    walk1Hash !== standHash &&
    walk2Hash !== standHash &&
    walk2Hash !== walk1Hash &&
    walkPhaseDiff > 0.015 &&
    standStats.tealRatio > 0.02 &&
    walk1Stats.tealRatio > 0.02 &&
    walk2Stats.tealRatio > 0.015 &&
    walkSpread > 0.55 &&
    walkOpposite;
  const lookDownOk =
    downStats.blackRatio < 0.55 &&
    downStats.lum > 28 &&
    downSnap.cam?.inside !== "1";
  const camOk = defaultSnap.cam?.inside !== "1" && Number(defaultSnap.cam?.pitch ?? 0) < 0;
  const lanternOk = /lantern|shop-lantern-fish/i.test(lanternA.shopPanelId || "");
  const honestyOk = Boolean(readyA.snap.honesty);

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      eOk && seeA && gaitOk && lookDownOk && camOk && lanternOk && honestyOk ? "J5_FRIEND_GAIT_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    eOk,
    seeA,
    gaitOk,
    lookDownOk,
    camOk,
    lanternOk,
    honestyOk,
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      cam: defaultSnap.cam,
    },
    remoteA: remoteA(walking.snap),
    walk1Proof,
    walk2Proof,
    defaultStats,
    standStats,
    walk1Stats,
    walk2Stats,
    downStats,
    standVsWalk,
    walkPhaseDiff,
    standHash,
    walk1Hash,
    walk2Hash,
    lookDownBlack: downStats.blackRatio >= 0.55 || downStats.lum <= 28,
    lanternPanel: lanternA.shopPanelId,
    shotB: SHOT_B,
    shotStand: SHOT_STAND,
    shotWalk1: SHOT_WALK1,
    shotWalk2: SHOT_WALK2,
    shotDown: SHOT_DOWN,
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
if (report.verdict !== "J5_FRIEND_GAIT_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `pixelDiff=${report.standVsWalk}`,
  `phaseDiff=${report.walkPhaseDiff}`,
  `lookDownBlack=${report.lookDownBlack}`,
  `teal=${report.defaultStats?.tealRatio}`,
  `lantern=${report.lanternPanel}`,
);
