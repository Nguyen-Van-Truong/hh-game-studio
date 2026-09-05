/**
 * Inner parcel lanes: dark asphalt strip + lighter walk edge.
 * Walk Harbor then east into Steps; lum delta on that inner shot;
 * door/glass still visible; lantern E still shop-lantern-fish;
 * leftover B E not stolen; data-at-bound still works.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
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
const OUT = join(import.meta.dirname, "J5-INNER-LANE-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-inner-lane.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9551), b: 9552 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-07";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const AOI = {
  west: 106.6961711,
  south: 10.7707034,
  east: 106.6998289,
  north: 10.7742966,
};
const M_PER_DEG_LAT = 111320;
const DOOR = { r: 26, g: 18, b: 14 };
const GLASS = { r: 27, g: 39, b: 51 };
const HARBOR_ONLY_FACES = 38;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
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

async function keyDown(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  });
}

async function keyUp(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  });
}

async function keyHold(ws, id, key, code, vk, ms) {
  await keyDown(ws, id, key, code, vk);
  await sleep(ms);
  await keyUp(ws, id + 1, key, code, vk);
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

function bandStats(pixels, width, height, xa, ya, xb, yb) {
  let n = 0;
  let door = 0;
  let glass = 0;
  let dark = 0;
  let beige = 0;
  let blueish = 0;
  let light = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  const step = 2;
  const x0 = Math.max(0, Math.floor(xa));
  const y0 = Math.max(0, Math.floor(ya));
  const x1 = Math.min(width, Math.ceil(xb));
  const y1 = Math.min(height, Math.ceil(yb));
  for (let y = y0; y < y1; y += step) {
    for (let x = x0; x < x1; x += step) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      sumR += r;
      sumG += g;
      sumB += b;
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (Math.hypot(r - DOOR.r, g - DOOR.g, b - DOOR.b) < 28) door += 1;
      if (Math.hypot(r - GLASS.r, g - GLASS.g, b - GLASS.b) < 32) glass += 1;
      if (r < 55 && g < 55 && b < 70 && Math.max(r, g, b) - Math.min(r, g, b) < 36) dark += 1;
      if (r > 170 && g > 140 && b < 180 && r - b > 20) beige += 1;
      if (b > r + 8 && b > 90) blueish += 1;
      if (lum > 110) light += 1;
    }
  }
  const meanR = sumR / Math.max(1, n);
  const meanG = sumG / Math.max(1, n);
  const meanB = sumB / Math.max(1, n);
  return {
    samples: n,
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    lum: Number((0.2126 * meanR + 0.7152 * meanG + 0.0722 * meanB).toFixed(1)),
    doorRatio: Number((door / Math.max(1, n)).toFixed(3)),
    glassRatio: Number((glass / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    lightRatio: Number((light / Math.max(1, n)).toFixed(3)),
  };
}

/** Darker center vs lighter walk on the same inner floor strip. */
function laneLums(pixels, width, height) {
  const bins = 12;
  const y0 = Math.floor(height * 0.81);
  const y1 = Math.floor(height * 0.86);
  const x0 = Math.floor(width * 0.42);
  const x1 = Math.floor(width * 0.6);
  const acc = Array.from({ length: bins }, () => ({ n: 0, s: 0 }));
  for (let y = y0; y < y1; y += 2) {
    for (let x = x0; x < x1; x += 2) {
      const b = Math.min(bins - 1, Math.floor(((x - x0) / Math.max(1, x1 - x0)) * bins));
      const i = (y * width + x) * 4;
      const lum = 0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2];
      acc[b].n += 1;
      acc[b].s += lum;
    }
  }
  const means = acc.map((row) => (row.n ? row.s / row.n : 0));
  let roadI = 0;
  let roadLum = Infinity;
  for (let i = 3; i < 9; i += 1) {
    if (means[i] < roadLum) {
      roadLum = means[i];
      roadI = i;
    }
  }
  let walkI = roadI;
  let walkLum = -1;
  for (let i = Math.max(0, roadI - 5); i <= Math.min(bins - 1, roadI + 5); i += 1) {
    if (i === roadI) {
      continue;
    }
    if (means[i] > walkLum) {
      walkLum = means[i];
      walkI = i;
    }
  }
  return {
    roadI,
    walkI,
    roadLum: Number(roadLum.toFixed(1)),
    walkLum: Number(walkLum.toFixed(1)),
    means: means.map((v) => Number(v.toFixed(1))),
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const floors = document.querySelector('[data-testid="play-ground-floors"]');
  const sides = document.querySelector('[data-testid="play-side-streets"]');
  const floorRows = [...document.querySelectorAll('[data-testid="play-ground-floors"] li')].map((el) => ({
    id: el.getAttribute("data-building-id") ?? "",
    street: el.getAttribute("data-street") ?? "",
    lane: el.getAttribute("data-lane") ?? "",
    storefronts: Number(el.getAttribute("data-storefronts") ?? "0"),
    displays: Number(el.getAttribute("data-displays") ?? "0"),
  }));
  const innerFloor = floorRows.filter((row) => row.lane === "inner" || /street-inner-/.test(row.street));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    alt: Number(avatar?.getAttribute("data-alt") ?? proof?.getAttribute("data-alt") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    atBound: avatar?.getAttribute("data-at-bound") ?? proof?.getAttribute("data-at-bound") ?? "",
    blocked: avatar?.getAttribute("data-blocked") ?? proof?.getAttribute("data-blocked") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    fog: proof?.getAttribute("data-fog") ?? "",
    blockEdge: proof?.getAttribute("data-block-edge") ?? "",
    ground: proof?.getAttribute("data-ground") ?? "",
    groundFloor: proof?.getAttribute("data-ground-floor") ?? "",
    gfFaces: Number(proof?.getAttribute("data-ground-floor-faces") ?? floors?.getAttribute("data-count") ?? "0"),
    gfMain: Number(proof?.getAttribute("data-ground-floor-main-faces") ?? floors?.getAttribute("data-main-faces") ?? "0"),
    gfInner: Number(proof?.getAttribute("data-ground-floor-inner-faces") ?? floors?.getAttribute("data-inner-faces") ?? "0"),
    sideStreet: proof?.getAttribute("data-side-street") ?? play?.getAttribute("data-side-street") ?? "",
    sideStreets: Number(proof?.getAttribute("data-side-street-streets") ?? sides?.getAttribute("data-count") ?? "0"),
    innerLane: proof?.getAttribute("data-inner-lane") ?? play?.getAttribute("data-inner-lane") ?? sides?.getAttribute("data-lane-kind") ?? "",
    innerRoads: Number(proof?.getAttribute("data-inner-lane-roads") ?? sides?.getAttribute("data-roads") ?? "0"),
    innerWalks: Number(proof?.getAttribute("data-inner-lane-walks") ?? sides?.getAttribute("data-walks") ?? "0"),
    innerEdges: Number(proof?.getAttribute("data-inner-lane-edges") ?? "0"),
    sideLamps: Number(proof?.getAttribute("data-side-street-lamps") ?? proof?.getAttribute("data-inner-lamps") ?? "0"),
    sideScooters: Number(proof?.getAttribute("data-side-street-scooters") ?? proof?.getAttribute("data-inner-scooters") ?? "0"),
    lamps: Number(proof?.getAttribute("data-lamps") ?? "0"),
    scooters: Number(proof?.getAttribute("data-scooters") ?? "0"),
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    footsteps: play?.getAttribute("data-footsteps") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    innerFloor: innerFloor.length,
    gtaClaim:
      /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-lane-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--autoplay-policy=no-user-gesture-required",
      "--window-size=1280,720",
      url,
    ],
    { stdio: "ignore" },
  );
}

async function waitSnap(ws, startId, pred, tries = 28, delay = 250) {
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

const chromes = [];
let report;
try {
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

  const readyA = await waitSnap(
    a.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );
  const readyB = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );
  const spawn = readyA.snap;

  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(120);
  await keyHold(a.ws, 90, "w", "KeyW", 87, 13000);
  await sleep(150);
  await keyHold(a.ws, 100, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHold(a.ws, 110, "w", "KeyW", 87, 8000);
  await sleep(200);
  const onInner = await evalExpr(a.ws, 130, SNAP);
  const innerShot = await cdp(a.ws, 131, "Page.captureScreenshot", { format: "png" });
  const innerBuf = Buffer.from(innerShot.data, "base64");
  writeFileSync(SHOT, innerBuf);

  await keyHold(a.ws, 140, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 150, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 160, "w", "KeyW", 87, 8000);
  await sleep(80);
  await keyHold(a.ws, 170, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHold(a.ws, 180, "w", "KeyW", 87, 5000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 190, SNAP);
  await keyHold(a.ws, 191, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 200, SNAP);
  await evalExpr(a.ws, 201, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  const shopClosed = await evalExpr(a.ws, 202, SNAP);

  let faceId = 400;
  let face = shopClosed;
  for (let i = 0; i < 10; i += 1) {
    const h = ((face.heading % 360) + 360) % 360;
    if (h >= 165 && h <= 195) {
      break;
    }
    await keyHold(a.ws, faceId, "a", "KeyA", 65, 280);
    faceId += 2;
    face = await evalExpr(a.ws, faceId, SNAP);
    faceId += 1;
    await sleep(40);
  }
  await sleep(80);
  await keyDown(a.ws, faceId, "Shift", "ShiftLeft", 16, 8);
  await keyDown(a.ws, faceId + 1, "w", "KeyW", 87, 8);
  const toward = await waitSnap(a.ws, faceId + 2, (s) => s.atBound === "1", 110, 550);
  const atEdge = toward.snap;
  await sleep(1800);
  const extra = await evalExpr(a.ws, faceId + 140, SNAP);
  await keyUp(a.ws, faceId + 141, "w", "KeyW", 87, 8);
  await keyUp(a.ws, faceId + 142, "Shift", "ShiftLeft", 16);

  const leftoverB =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";
  await keyHold(b.ws, 80, "e", "KeyE", 69, 180);
  await sleep(250);
  const bAfterE = await evalExpr(b.ws, 90, SNAP);
  const leftoverEStolen = Boolean(bAfterE.shopPanel) && LEFTOVER.test(bAfterE.shopPanelId || "");

  const png = decodePngRgba(innerBuf);
  const w = png.width;
  const h = png.height;
  const mid = bandStats(png.pixels, w, h, 180, 220, 1100, 680);
  const lane = laneLums(png.pixels, w, h);
  const roadBand = bandStats(
    png.pixels,
    w,
    h,
    w * (0.42 + (lane.roadI / 12) * 0.18),
    h * 0.81,
    w * (0.42 + ((lane.roadI + 1) / 12) * 0.18),
    h * 0.86,
  );
  const walkBand = bandStats(
    png.pixels,
    w,
    h,
    w * (0.42 + (lane.walkI / 12) * 0.18),
    h * 0.81,
    w * (0.42 + ((lane.walkI + 1) / 12) * 0.18),
    h * 0.86,
  );
  const walkMinusRoad = Number((lane.walkLum - lane.roadLum).toFixed(1));
  const extraFaces = Math.max(0, spawn.gfFaces - HARBOR_ONLY_FACES);
  const eastM = (onInner.lon - spawn.lon) * metersPerDegLon((onInner.lat + spawn.lat) / 2);
  const northM = (onInner.lat - spawn.lat) * M_PER_DEG_LAT;
  const southLimit = AOI.south + 2 / M_PER_DEG_LAT;
  const insideAoi =
    extra.lon >= AOI.west &&
    extra.lon <= AOI.east &&
    extra.lat >= southLimit - 0.00002 &&
    extra.lat <= AOI.north;

  const countsOk =
    spawn.innerLane === "asphalt-walk-edge" &&
    spawn.innerRoads >= 8 &&
    spawn.innerWalks >= 8 &&
    spawn.gfInner >= 8 &&
    spawn.gfFaces > spawn.gfMain &&
    extraFaces >= 8 &&
    spawn.sideStreets >= 8 &&
    spawn.sideStreet === "door-glass-lamp" &&
    spawn.innerFloor >= 8;
  const walkedOff =
    eastM > 6 &&
    northM > 10 &&
    onInner.insideRing === "0" &&
    onInner.insideAabb === "0";
  const doorGlassOk = mid.doorRatio + mid.glassRatio > 0.012 || mid.darkRatio > 0.04;
  const lumOk = walkMinusRoad >= 18 && roadBand.lum < 90 && walkBand.lum > 55;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const shopClosedOk = shopClosed.shopPanel === false && extra.shopPanel === false;
  const leftoverOk = leftoverB && !leftoverEStolen && !bAfterE.shopPanel;
  const atBoundOk = extra.atBound === "1" || extra.blocked === "1";
  const noTrap = extra.alt === 0 && insideAoi && onInner.alt === 0;
  const honestyOk =
    /Authored approximation/.test(spawn.honesty) &&
    /not a digital twin/i.test(spawn.honesty) &&
    /inner parcel lanes/.test(spawn.honesty) &&
    /NOT_PLAN_PASS/.test(spawn.honesty) &&
    spawn.gtaClaim === false;
  const keptOk =
    spawn.sky === "gradient-hemisphere" &&
    spawn.collision === "footprint-radius" &&
    spawn.blockEdge === "curb-wall-lot" &&
    spawn.fog === "distance-haze" &&
    spawn.walkCycle === "opposite-stride" &&
    spawn.groundFloor === "door-glass-awning" &&
    spawn.ground === "road-walk-curb";

  const ok =
    countsOk &&
    walkedOff &&
    doorGlassOk &&
    lumOk &&
    lanternOk &&
    shopClosedOk &&
    leftoverOk &&
    atBoundOk &&
    noTrap &&
    honestyOk &&
    keptOk;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_INNER_LANE_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    countsOk,
    walkedOff,
    doorGlassOk,
    lumOk,
    lanternOk,
    shopClosedOk,
    leftoverOk,
    atBoundOk,
    noTrap,
    honestyOk,
    keptOk,
    extraFaces,
    eastM: Number(eastM.toFixed(2)),
    northM: Number(northM.toFixed(2)),
    walkMinusRoad,
    spawn,
    onInner,
    atLantern,
    extra,
    atEdge,
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    mid,
    roadBand,
    walkBand,
    lane,
    honesty: spawn.honesty?.slice(0, 280),
    shot: SHOT,
    hash: createHash("sha256").update(innerBuf).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_INNER_LANE_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `roads=${report.spawn?.innerRoads}`,
  `walks=${report.spawn?.innerWalks}`,
  `lumDelta=${report.walkMinusRoad}`,
  `door=${report.mid?.doorRatio}`,
  `east=${report.eastM}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
