/**
 * Authored market spill (crates / baskets / stacks) on recycled 4175.
 * Visible at lantern; E still opens shop-lantern-fish; scooters stay 15;
 * sky stays blue. Authored props, not a real inventory.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9433);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-MARKET-SPILL-2026-09-03.txt");
const SHOT = join(import.meta.dirname, "j5-3d-market-spill.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260903-ASIA-SAIGON-35";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function distanceM(a, b) {
  const mid = (a.lat + b.lat) / 2;
  const east = (b.lon - a.lon) * metersPerDegLon(mid);
  const north = (b.lat - a.lat) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

function deltaM(a, b) {
  const mid = (a.lat + b.lat) / 2;
  return {
    east: (b.lon - a.lon) * metersPerDegLon(mid),
    north: (b.lat - a.lat) * M_PER_DEG_LAT,
    moved: distanceM(a, b),
  };
}

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

function isCrateWood(r, g, b) {
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  if (lum < 28 || lum > 170) return false;
  if (r > g + 12 && r > b + 22 && r > 70 && r < 190 && g > 35 && g < 150 && b < 110) return true;
  return false;
}

function isCoolerTeal(r, g, b) {
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  if (lum < 28 || lum > 160) return false;
  if (g > r + 10 && b > r + 6 && g > 55 && g < 170 && b > 50 && b < 170 && r < 120) return true;
  return false;
}

function bandStats(pixels, width, height, x0, y0, x1, y1) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let blueish = 0;
  let wood = 0;
  let teal = 0;
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
      if (isCrateWood(r, g, b)) wood += 1;
      if (isCoolerTeal(r, g, b)) teal += 1;
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
    woodRatio: Number((wood / Math.max(1, n)).toFixed(3)),
    tealRatio: Number((teal / Math.max(1, n)).toFixed(3)),
    spillRatio: Number(((wood + teal) / Math.max(1, n)).toFixed(3)),
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const playCanvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const spill = [...document.querySelectorAll('[data-testid="play-market-spill"] li')].map((el) => ({
    id: el.textContent?.trim() ?? "",
    kind: el.getAttribute("data-kind"),
    source: el.getAttribute("data-source"),
    shop: el.getAttribute("data-shop"),
    color: el.getAttribute("data-color"),
    collide: el.getAttribute("data-collide"),
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
  }));
  const scooters = [...document.querySelectorAll('[data-testid="play-scooters"] li')].map((el) => ({
    id: el.textContent?.trim() ?? "",
    street: el.getAttribute("data-street"),
  }));
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    playEngine: play?.getAttribute("data-engine") ?? "",
    playCanvas: Boolean(playCanvas),
    canvasBox: playCanvas
      ? (() => {
          const r = playCanvas.getBoundingClientRect();
          return { x: r.left, y: r.top, w: r.width, h: r.height };
        })()
      : null,
    avatar: avatar
      ? {
          lon: Number(avatar.dataset.lon),
          lat: Number(avatar.dataset.lat),
          heading: Number(avatar.dataset.heading),
          insideAabb: avatar.getAttribute("data-inside-aabb"),
          insideRing: avatar.getAttribute("data-inside-ring"),
        }
      : null,
    proof: proof
      ? {
          camera: proof.getAttribute("data-camera"),
          collision: proof.getAttribute("data-collision") ?? "",
          sky: proof.getAttribute("data-sky") ?? "",
          sun: proof.getAttribute("data-sun") ?? "",
          lamps: proof.getAttribute("data-lamps") ?? "",
          planters: proof.getAttribute("data-planters") ?? "",
          scooters: proof.getAttribute("data-scooters") ?? "",
          scooterKind: proof.getAttribute("data-scooter-kind") ?? "",
          marketSpill: proof.getAttribute("data-market-spill") ?? "",
          marketSpillCount: proof.getAttribute("data-market-spill-count") ?? "",
          marketSpillShop: proof.getAttribute("data-market-spill-shop") ?? "",
          marketSpillStreet: proof.getAttribute("data-market-spill-street") ?? "",
          marketSpillCoolers: proof.getAttribute("data-market-spill-coolers") ?? "",
          marketSpillBaskets: proof.getAttribute("data-market-spill-baskets") ?? "",
          groundFloor: proof.getAttribute("data-ground-floor") ?? "",
          roof: proof.getAttribute("data-roof") ?? "",
          shopStallKind: proof.getAttribute("data-shop-stall-kind") ?? "",
          camYaw: Number(proof.getAttribute("data-cam-yaw") ?? "NaN"),
          camPitch: Number(proof.getAttribute("data-cam-pitch") ?? "NaN"),
          insideAabb: proof.getAttribute("data-inside-aabb") ?? "",
          insideRing: proof.getAttribute("data-inside-ring") ?? "",
          buildings: Number(proof.getAttribute("data-buildings") ?? "0"),
        }
      : null,
    spill,
    scooters,
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

const DRAG = `(dx, dy) => {
  const c = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  if (!c) return { ok: false };
  const r = c.getBoundingClientRect();
  const x = r.left + r.width * 0.5;
  const y = r.top + r.height * 0.42;
  const base = { bubbles: true, cancelable: true, pointerId: 11, pointerType: "mouse", isPrimary: true };
  c.dispatchEvent(new PointerEvent("pointerdown", { ...base, button: 2, buttons: 2, clientX: x, clientY: y }));
  c.dispatchEvent(new PointerEvent("pointermove", {
    ...base, button: 2, buttons: 2, clientX: x + dx, clientY: y + dy, movementX: dx, movementY: dy,
  }));
  return { ok: true, x, y, w: r.width, h: r.height };
}`;

const DRAG_END = `() => {
  const c = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  if (!c) return false;
  const r = c.getBoundingClientRect();
  c.dispatchEvent(new PointerEvent("pointerup", {
    bubbles: true, cancelable: true, pointerId: 11, pointerType: "mouse", button: 2, buttons: 0,
    clientX: r.left + r.width * 0.5 + 80, clientY: r.top + r.height * 0.42,
  }));
  return true;
}`;

async function connectPage() {
  const deadline = Date.now() + 20000;
  let last = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
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
  throw new Error(`no CDP page on ${DEBUG_PORT}: ${JSON.stringify(last)}`);
}

async function waitReady(ws, id) {
  let snap = null;
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    snap = await evalExpr(ws, id, SNAP);
    if (snap.playReady === "yes" && snap.avatar && snap.proof?.buildings >= 20) {
      return snap;
    }
    await sleep(150);
  }
  return snap;
}

async function goHome(ws, id) {
  await cdp(ws, id, "Page.navigate", { url: `${PLAYER}?seat=a` });
  await sleep(400);
  return waitReady(ws, id + 1);
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-spill-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let report;
try {
  const { ws } = await connectPage();
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });

  const home = await goHome(ws, 4);
  await keyHold(ws, 20, "w", "KeyW", 87, 4500);
  await sleep(250);
  const midWalk = await evalExpr(ws, 24, SNAP);
  const skyShot = await cdp(ws, 25, "Page.captureScreenshot", { format: "png" });
  const skyBuf = Buffer.from(skyShot.data, "base64");
  await keyHold(ws, 26, "w", "KeyW", 87, 11500);
  await sleep(300);
  const atLantern = await evalExpr(ws, 30, SNAP);
  const box = atLantern.canvasBox ?? { x: 0, y: 48, w: 1280, h: 672 };
  const cx = Math.round(box.x + box.w * 0.5);
  const cy = Math.round(box.y + box.h * 0.42);
  const lookDx = -70;
  await cdp(ws, 40, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: cx,
    y: cy,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await cdp(ws, 41, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: cx + lookDx,
    y: cy + 8,
    button: "right",
    buttons: 2,
  });
  await sleep(80);
  let looked = await evalExpr(ws, 42, SNAP);
  let lookPath = "cdp-mouse";
  if (!(looked.proof && Math.abs(looked.proof.camYaw) > 4)) {
    await evalExpr(ws, 43, `(${DRAG})(${lookDx}, 8)`);
    await sleep(80);
    looked = await evalExpr(ws, 44, SNAP);
    lookPath = "canvas-pointer";
  }
  const shot = await cdp(ws, 45, "Page.captureScreenshot", { format: "png" });
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(SHOT, buf);
  await cdp(ws, 46, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: cx + lookDx,
    y: cy + 8,
    button: "right",
    buttons: 0,
    clickCount: 1,
  });
  await evalExpr(ws, 47, `(${DRAG_END})()`);

  await keyHold(ws, 80, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopOpen = await evalExpr(ws, 90, SNAP);

  const png = decodePngRgba(buf);
  const midPng = decodePngRgba(skyBuf);
  const canvasBox = looked.canvasBox ?? { x: 0, y: 48, w: 1280, h: 672 };
  const skyBand = bandStats(
    midPng.pixels,
    midPng.width,
    midPng.height,
    canvasBox.x + canvasBox.w * 0.38,
    canvasBox.y + canvasBox.h * 0.04,
    canvasBox.x + canvasBox.w * 0.62,
    canvasBox.y + canvasBox.h * 0.16,
  );
  const stallBand = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.22,
    canvasBox.y + canvasBox.h * 0.28,
    canvasBox.x + canvasBox.w * 0.78,
    canvasBox.y + canvasBox.h * 0.78,
  );
  const leftGoods = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.12,
    canvasBox.y + canvasBox.h * 0.38,
    canvasBox.x + canvasBox.w * 0.38,
    canvasBox.y + canvasBox.h * 0.82,
  );
  const rightGoods = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.62,
    canvasBox.y + canvasBox.h * 0.38,
    canvasBox.x + canvasBox.w * 0.88,
    canvasBox.y + canvasBox.h * 0.82,
  );

  const pos = (snap) => ({ lon: snap.avatar.lon, lat: snap.avatar.lat });
  const lanternDelta = deltaM(pos(home), pos(atLantern));
  const spillN = Number(looked.proof?.marketSpillCount ?? looked.spill?.length ?? 0);
  const streetN = Number(looked.proof?.marketSpillStreet ?? 0);
  const shopN = Number(looked.proof?.marketSpillShop ?? 0);
  const scooterN = Number(looked.proof?.scooters ?? looked.scooters?.length ?? 0);
  const lanternSpill = (looked.spill || []).filter((row) => row.shop === "shop-lantern-fish");
  const streetSpill = (looked.spill || []).filter((row) => row.source === "street");

  const spillDomOk =
    looked.proof?.marketSpill === "crate-basket-stack" &&
    spillN >= 6 &&
    looked.spill.length === spillN &&
    lanternSpill.length >= 3 &&
    lanternSpill.some((row) => row.kind === "cooler" && row.color === "#2a7a78") &&
    lanternSpill.some((row) => row.kind === "crate" && row.color === "#8a5a32") &&
    lanternSpill.some((row) => row.kind === "basket") &&
    streetN >= 2 &&
    streetN <= 4 &&
    streetSpill.length === streetN &&
    shopN >= 3;
  const pixOk =
    stallBand.spillRatio >= 0.012 ||
    leftGoods.spillRatio >= 0.012 ||
    rightGoods.spillRatio >= 0.012;
  const scooterOk =
    looked.proof?.scooterKind === "parked-box-scooter" && scooterN === 15;
  const walkOk =
    lanternDelta.north > 8 &&
    home.avatar?.insideAabb === "0" &&
    atLantern.avatar?.insideAabb === "0" &&
    atLantern.avatar?.insideRing === "0" &&
    looked.proof?.collision === "footprint-radius";
  const skyOk =
    looked.proof?.sky === "gradient-hemisphere" &&
    looked.proof?.sun === "disc" &&
    skyBand.beigeRatio < 0.22 &&
    (skyBand.bluerThanRed || skyBand.blueRatio > 0.22) &&
    skyBand.meanB > skyBand.meanR;
  const shopOk =
    Boolean(atLantern.shopMarker) &&
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const keptOk =
    Number(looked.proof?.lamps) >= 12 &&
    Number(looked.proof?.planters) >= 1 &&
    looked.proof?.groundFloor === "door-glass-awning" &&
    looked.proof?.roof === "parapet-ac-tank" &&
    looked.proof?.shopStallKind === "awning-kiosk";
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      spillDomOk && pixOk && scooterOk && walkOk && skyOk && shopOk && keptOk && honestyOk
        ? "J5_MARKET_SPILL_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    lookPath,
    lookDx,
    spillDomOk,
    pixOk,
    scooterOk,
    walkOk,
    skyOk,
    shopOk,
    keptOk,
    honestyOk,
    spillN,
    shopN,
    streetN,
    scooterN,
    lanternSpill,
    streetSpill,
    lanternDelta,
    skyBand,
    stallBand,
    leftGoods,
    rightGoods,
    shopPanelId: shopOpen.shopPanelId,
    hash: createHash("sha256").update(buf).digest("hex").slice(0, 16),
    bytes: buf.length,
    shot: SHOT,
    home,
    midWalk,
    atLantern,
    looked,
    shopOpen,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_MARKET_SPILL_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `spill=${report.spillN}`,
  `shop=${report.shopN}`,
  `street=${report.streetN}`,
  `scooters=${report.scooterN}`,
  `blue=${report.skyBand?.blueRatio}`,
  `pix=${Math.max(report.stallBand?.spillRatio ?? 0, report.leftGoods?.spillRatio ?? 0, report.rightGoods?.spillRatio ?? 0)}`,
  `shopE=${report.shopPanelId}`,
);
