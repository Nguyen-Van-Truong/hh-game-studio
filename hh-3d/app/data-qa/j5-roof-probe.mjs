/**
 * Authored roof language (parapet + hashed AC/tank) on recycled 4175.
 * Pitch up from Harbor Walk; sky stays blue; E still opens lantern;
 * footprint-radius collision still holds (slim SAIGON-28 checks).
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9418);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-ROOF-2026-09-03.txt");
const SHOT_ROOF = join(import.meta.dirname, "j5-3d-roof.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260903-ASIA-SAIGON-29";

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

function ringAabb(ring) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const pt of ring) {
    if (!Array.isArray(pt) || pt.length < 2) {
      continue;
    }
    west = Math.min(west, pt[0]);
    east = Math.max(east, pt[0]);
    south = Math.min(south, pt[1]);
    north = Math.max(north, pt[1]);
  }
  return { west, south, east, north };
}

function pointInRing(lon, lat, ring) {
  let inside = false;
  const n = ring.length;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const pi = ring[i];
    const pj = ring[j];
    if (!pi || !pj || pj[1] === pi[1]) {
      continue;
    }
    if (pi[1] > lat !== pj[1] > lat && lon < ((pj[0] - pi[0]) * (lat - pi[1])) / (pj[1] - pi[1]) + pi[0]) {
      inside = !inside;
    }
  }
  return inside;
}

function distToAabb(lon, lat, box) {
  const closestLon = Math.min(box.east, Math.max(box.west, lon));
  const closestLat = Math.min(box.north, Math.max(box.south, lat));
  return distanceM({ lon, lat }, { lon: closestLon, lat: closestLat });
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

function bandStats(pixels, width, height, x0, y0, x1, y1) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let grayish = 0;
  let blueish = 0;
  let dark = 0;
  let ac = 0;
  let lid = 0;
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
      const spread = Math.max(r, g, b) - Math.min(r, g, b);
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (spread < 14 && r > 140 && r < 230 && g > 140 && g < 230 && b > 140 && b < 230) {
        grayish += 1;
      }
      if (r > 170 && g > 140 && b < 180 && r - b > 20) {
        beige += 1;
      }
      if (b > r + 8 && b > 90) {
        blueish += 1;
      }
      if (lum < 70) {
        dark += 1;
      }
      if (lum > 95 && lum < 175 && spread < 36 && b >= r - 6 && g >= r - 8 && r > 110 && r < 190) {
        ac += 1;
      }
      if (lum < 88 && r > g + 4 && r > b + 8 && r < 140 && g < 110 && b < 100) {
        lid += 1;
      }
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
    grayRatio: Number((grayish / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    acRatio: Number((ac / Math.max(1, n)).toFixed(3)),
    lidRatio: Number((lid / Math.max(1, n)).toFixed(3)),
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const playCanvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const roofs = [...document.querySelectorAll('[data-testid="play-roofs"] li')].map((el) => ({
    building: el.getAttribute("data-building-id"),
    parapets: Number(el.getAttribute("data-parapets") ?? "0"),
    acs: Number(el.getAttribute("data-acs") ?? "0"),
    tanks: Number(el.getAttribute("data-tanks") ?? "0"),
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
          groundY: avatar.getAttribute("data-ground-y"),
          insideAabb: avatar.getAttribute("data-inside-aabb"),
          insideRing: avatar.getAttribute("data-inside-ring"),
          collision: avatar.getAttribute("data-collision"),
        }
      : null,
    proof: proof
      ? {
          camera: proof.getAttribute("data-camera"),
          follow: proof.getAttribute("data-follow"),
          heading: Number(proof.getAttribute("data-heading") ?? "NaN"),
          camYaw: Number(proof.getAttribute("data-cam-yaw") ?? "NaN"),
          camPitch: Number(proof.getAttribute("data-cam-pitch") ?? "NaN"),
          buildings: Number(proof.getAttribute("data-buildings") ?? "0"),
          extruded: proof.getAttribute("data-extruded") ?? "",
          collision: proof.getAttribute("data-collision") ?? "",
          groundY: proof.getAttribute("data-ground-y") ?? "",
          insideAabb: proof.getAttribute("data-inside-aabb") ?? "",
          insideRing: proof.getAttribute("data-inside-ring") ?? "",
          hitBuilding: proof.getAttribute("data-hit-building") ?? "",
          sky: proof.getAttribute("data-sky") ?? "",
          sun: proof.getAttribute("data-sun") ?? "",
          lamps: proof.getAttribute("data-lamps") ?? "",
          planters: proof.getAttribute("data-planters") ?? "",
          groundFloor: proof.getAttribute("data-ground-floor") ?? "",
          roof: proof.getAttribute("data-roof") ?? "",
          roofBuildings: Number(proof.getAttribute("data-roof-buildings") ?? "0"),
          roofParapets: Number(proof.getAttribute("data-roof-parapets") ?? "0"),
          roofAcs: Number(proof.getAttribute("data-roof-acs") ?? "0"),
          roofTanks: Number(proof.getAttribute("data-roof-tanks") ?? "0"),
        }
      : null,
    roofs,
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
  const base = { bubbles: true, cancelable: true, pointerId: 9, pointerType: "mouse", isPrimary: true };
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
    bubbles: true, cancelable: true, pointerId: 9, pointerType: "mouse", button: 2, buttons: 0,
    clientX: r.left + r.width * 0.5 + 170, clientY: r.top + r.height * 0.42 - 200,
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

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-roof-"));
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

  const geoRes = await fetch(new URL("/data/ben-thanh-400m.authored.geojson", PLAYER));
  const geo = await geoRes.json();
  const liveBuildings = geo.features
    .filter((feature) => feature.properties?.kind === "building")
    .map((feature) => ({
      id: String(feature.id ?? feature.properties.id),
      ring: feature.geometry.coordinates[0],
      ...ringAabb(feature.geometry.coordinates[0]),
    }));

  const home = await goHome(ws, 4);
  await keyHold(ws, 20, "w", "KeyW", 87, 4200);
  await sleep(200);
  const midWalk = await evalExpr(ws, 30, SNAP);

  const box = midWalk.canvasBox ?? { x: 0, y: 48, w: 1280, h: 672 };
  const cx = Math.round(box.x + box.w * 0.5);
  const cy = Math.round(box.y + box.h * 0.42);
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
    x: cx + 170,
    y: cy - 200,
    button: "right",
    buttons: 2,
  });
  await sleep(80);
  let pitched = await evalExpr(ws, 42, SNAP);
  let lookPath = "cdp-mouse";
  if (!(pitched.proof && pitched.proof.camPitch > 8 && pitched.proof.camYaw > 8)) {
    await evalExpr(ws, 43, `(${DRAG})(170, -200)`);
    await sleep(80);
    pitched = await evalExpr(ws, 44, SNAP);
    lookPath = "canvas-pointer";
  }
  const roofShot = await cdp(ws, 45, "Page.captureScreenshot", { format: "png" });
  const roofBuf = Buffer.from(roofShot.data, "base64");
  writeFileSync(SHOT_ROOF, roofBuf);
  await cdp(ws, 46, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: cx + 170,
    y: cy - 200,
    button: "right",
    buttons: 0,
    clickCount: 1,
  });
  await evalExpr(ws, 47, `(${DRAG_END})()`);

  const wallHome = await goHome(ws, 50);
  await keyHold(ws, 60, "w", "KeyW", 87, 3500);
  await sleep(120);
  await keyHold(ws, 70, "d", "KeyD", 68, 820);
  await sleep(120);
  const wallTurned = await evalExpr(ws, 80, SNAP);
  await keyHold(ws, 90, "w", "KeyW", 87, 10000);
  await sleep(150);
  const atWall = await evalExpr(ws, 100, SNAP);
  await keyHold(ws, 110, "w", "KeyW", 87, 3000);
  await sleep(150);
  const wallStill = await evalExpr(ws, 120, SNAP);

  const shopHome = await goHome(ws, 130);
  await keyHold(ws, 140, "w", "KeyW", 87, 16000);
  await sleep(250);
  const atLantern = await evalExpr(ws, 150, SNAP);
  await keyHold(ws, 160, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopOpen = await evalExpr(ws, 170, SNAP);

  const png = decodePngRgba(roofBuf);
  const canvasBox = pitched.canvasBox ?? { x: 0, y: 48, w: 1280, h: 672 };
  const skyBand = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.38,
    canvasBox.y + canvasBox.h * 0.04,
    canvasBox.x + canvasBox.w * 0.62,
    canvasBox.y + canvasBox.h * 0.16,
  );
  const roofBand = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.18,
    canvasBox.y + canvasBox.h * 0.18,
    canvasBox.x + canvasBox.w * 0.82,
    canvasBox.y + canvasBox.h * 0.48,
  );
  const sideLid = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.x + canvasBox.w * 0.04,
    canvasBox.y + canvasBox.h * 0.2,
    canvasBox.x + canvasBox.w * 0.28,
    canvasBox.y + canvasBox.h * 0.52,
  );

  const pos = (snap) => ({ lon: snap.avatar.lon, lat: snap.avatar.lat });
  const wallToward = deltaM(pos(wallTurned), pos(atWall));
  const wallExtra = deltaM(pos(atWall), pos(wallStill));
  const liveRing = liveBuildings.filter((row) =>
    pointInRing(wallStill.avatar.lon, wallStill.avatar.lat, row.ring),
  );
  const nearestWall = liveBuildings
    .map((row) => ({ id: row.id, dist: distToAabb(wallStill.avatar.lon, wallStill.avatar.lat, row) }))
    .sort((a, b) => a.dist - b.dist)[0];

  const harborRoofs = (pitched.roofs || []).filter((row) => /steps-|west-|east-|market-/.test(row.building || ""));
  const roofDomOk =
    pitched.proof?.roof === "parapet-ac-tank" &&
    pitched.proof.roofBuildings >= 50 &&
    pitched.proof.roofParapets >= 200 &&
    pitched.proof.roofAcs >= 12 &&
    pitched.proof.roofTanks >= 2 &&
    harborRoofs.some((row) => row.parapets >= 4 && row.acs + row.tanks >= 1);
  const lookOk =
    pitched.proof?.camPitch > 12 &&
    pitched.proof.camPitch <= 30 &&
    pitched.proof.camYaw > 10;
  const skyOk =
    pitched.proof?.sky === "gradient-hemisphere" &&
    pitched.proof?.sun === "disc" &&
    skyBand.beigeRatio < 0.22 &&
    (skyBand.bluerThanRed || skyBand.blueRatio > 0.22) &&
    skyBand.meanB > skyBand.meanR;
  const roofPixOk =
    (roofBand.lidRatio >= 0.02 || sideLid.lidRatio >= 0.02) &&
    (roofBand.acRatio >= 0.004 || roofBand.darkRatio >= 0.08) &&
    roofBand.beigeRatio < 0.55;
  const wallOk =
    wallToward.east > 6 &&
    Math.abs(wallExtra.east) < 0.35 &&
    liveRing.length === 0 &&
    wallStill.avatar?.insideRing === "0" &&
    wallStill.proof?.collision === "footprint-radius" &&
    nearestWall &&
    nearestWall.id === "bldg-steps-e-00" &&
    nearestWall.dist < 1.25;
  const shopOk =
    Boolean(atLantern.shopMarker) &&
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const keptOk =
    pitched.proof?.collision === "footprint-radius" &&
    pitched.proof?.groundFloor === "door-glass-awning" &&
    Number(pitched.proof?.lamps) >= 12 &&
    Number(pitched.proof?.planters) >= 1;
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      roofDomOk && lookOk && skyOk && roofPixOk && wallOk && shopOk && keptOk && honestyOk
        ? "J5_ROOF_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    lookPath,
    roofDomOk,
    lookOk,
    skyOk,
    roofPixOk,
    wallOk,
    shopOk,
    keptOk,
    honestyOk,
    camPitch: pitched.proof?.camPitch,
    roof: pitched.proof
      ? {
          kind: pitched.proof.roof,
          buildings: pitched.proof.roofBuildings,
          parapets: pitched.proof.roofParapets,
          acs: pitched.proof.roofAcs,
          tanks: pitched.proof.roofTanks,
        }
      : null,
    skyBand,
    roofBand,
    sideLid,
    wallToward,
    wallExtra,
    nearestWall,
    liveRing,
    shopPanelId: shopOpen.shopPanelId,
    hash: createHash("sha256").update(roofBuf).digest("hex").slice(0, 16),
    bytes: roofBuf.length,
    shotRoof: SHOT_ROOF,
    home,
    midWalk,
    pitched,
    wallStill,
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
if (report.verdict !== "J5_ROOF_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `roof=${report.roof?.kind}`,
  `parapets=${report.roof?.parapets}`,
  `acs=${report.roof?.acs}`,
  `tanks=${report.roof?.tanks}`,
  `pitch=${report.camPitch}`,
  `blue=${report.skyBand?.blueRatio}`,
  `lid=${report.roofBand?.lidRatio}`,
  `ac=${report.roofBand?.acRatio}`,
  `wallExtra=${report.wallExtra?.east?.toFixed?.(3)}`,
  `shop=${report.shopPanelId}`,
);
