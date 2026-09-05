/**
 * Authored street plaques: Harbor Walk / Tram Approach / Steps East / Steps West.
 * Harbor shot + walk into Steps East; DOM count + names; lantern E still
 * shop-lantern-fish; leftover B E not stolen; inner lum darker-center
 * if the Steps floor is in frame. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
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
const OUT = join(import.meta.dirname, "J5-STREET-NAME-2026-09-04.txt");
const SHOT_HARBOR = join(import.meta.dirname, "j5-3d-street-name-harbor.png");
const SHOT_STEPS = join(import.meta.dirname, "j5-3d-street-name-steps.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9561), b: 9562 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-08";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAQUE = { r: 31, g: 74, b: 60 };
const CREAM = { r: 243, g: 230, b: 196 };
const M_PER_DEG_LAT = 111320;

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

function plaqueStats(pixels, width, height, xa, ya, xb, yb) {
  let n = 0;
  let plaque = 0;
  let cream = 0;
  let dark = 0;
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
      if (Math.hypot(r - PLAQUE.r, g - PLAQUE.g, b - PLAQUE.b) < 38) plaque += 1;
      if (Math.hypot(r - CREAM.r, g - CREAM.g, b - CREAM.b) < 42) cream += 1;
      if (r < 55 && g < 55 && b < 70 && Math.max(r, g, b) - Math.min(r, g, b) < 36) dark += 1;
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
    plaqueRatio: Number((plaque / Math.max(1, n)).toFixed(3)),
    creamRatio: Number((cream / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    lightRatio: Number((light / Math.max(1, n)).toFixed(3)),
  };
}

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
    if (i === roadI) continue;
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
  const list = document.querySelector('[data-testid="play-street-plaques"]');
  const plaques = [...document.querySelectorAll('[data-testid="play-street-plaques"] li')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
    role: el.getAttribute("data-role") ?? "",
    street: el.getAttribute("data-street") ?? "",
    line2: el.getAttribute("data-line2") ?? "",
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
  }));
  const labels = [...document.querySelectorAll(".play-plaque-label")].map((el) => {
    const box = el.getBoundingClientRect();
    return {
      name: el.getAttribute("data-name") ?? el.textContent ?? "",
      role: el.getAttribute("data-role") ?? "",
      x: Number(box.x.toFixed(1)),
      y: Number(box.y.toFixed(1)),
      w: Number(box.width.toFixed(1)),
      h: Number(box.height.toFixed(1)),
      onScreen: box.width > 2 && box.height > 2 && box.x > -8 && box.x < 1288 && box.y > -8 && box.y < 728,
    };
  });
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
    innerLane: proof?.getAttribute("data-inner-lane") ?? play?.getAttribute("data-inner-lane") ?? "",
    innerRoads: Number(proof?.getAttribute("data-inner-lane-roads") ?? "0"),
    sideStreet: proof?.getAttribute("data-side-street") ?? play?.getAttribute("data-side-street") ?? "",
    streetPlaques: Number(
      proof?.getAttribute("data-street-plaques") ??
        play?.getAttribute("data-street-plaques") ??
        list?.getAttribute("data-count") ??
        "0",
    ),
    plaqueKind: proof?.getAttribute("data-street-plaque-kind") ?? play?.getAttribute("data-street-plaque-kind") ?? "",
    plaqueOfficial: Number(proof?.getAttribute("data-street-plaque-official") ?? list?.getAttribute("data-official") ?? "0"),
    plaqueInner: Number(proof?.getAttribute("data-street-plaque-inner") ?? list?.getAttribute("data-inner") ?? "0"),
    lamps: Number(proof?.getAttribute("data-lamps") ?? "0"),
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    plaques,
    labels,
    plaqueNames: plaques.map((row) => row.name),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-name-${port}-`));
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

function labelOnScreen(snap, name) {
  return (snap?.labels ?? []).some((row) => row.name === name && row.onScreen);
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

  const geo = await fetch(`${PLAYER}data/ben-thanh-400m.authored.geojson`).then((res) => res.json());
  const geoStreets = (geo.features ?? []).filter((row) => row.properties?.kind === "street");

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
  await keyHold(a.ws, 90, "w", "KeyW", 87, 2400);
  await sleep(180);
  const onHarbor = await evalExpr(a.ws, 100, SNAP);
  const harborShot = await cdp(a.ws, 101, "Page.captureScreenshot", { format: "png" });
  const harborBuf = Buffer.from(harborShot.data, "base64");
  writeFileSync(SHOT_HARBOR, harborBuf);

  await keyHold(a.ws, 110, "w", "KeyW", 87, 10600);
  await sleep(120);
  await keyHold(a.ws, 120, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHold(a.ws, 130, "w", "KeyW", 87, 4500);
  await sleep(200);
  const onSteps = await evalExpr(a.ws, 140, SNAP);
  const stepsShot = await cdp(a.ws, 141, "Page.captureScreenshot", { format: "png" });
  const stepsBuf = Buffer.from(stepsShot.data, "base64");
  writeFileSync(SHOT_STEPS, stepsBuf);

  await keyHold(a.ws, 150, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 160, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 170, "w", "KeyW", 87, 5000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 180, SNAP);
  await keyHold(a.ws, 181, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 190, SNAP);
  await evalExpr(a.ws, 191, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  const shopClosed = await evalExpr(a.ws, 192, SNAP);

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

  const harborPng = decodePngRgba(harborBuf);
  const stepsPng = decodePngRgba(stepsBuf);
  const harborPix = plaqueStats(harborPng.pixels, harborPng.width, harborPng.height, 80, 180, 620, 560);
  const stepsPix = plaqueStats(stepsPng.pixels, stepsPng.width, stepsPng.height, 420, 160, 1100, 580);
  const lane = laneLums(stepsPng.pixels, stepsPng.width, stepsPng.height);
  const walkMinusRoad = Number((lane.walkLum - lane.roadLum).toFixed(1));
  const eastM = (onSteps.lon - spawn.lon) * metersPerDegLon((onSteps.lat + spawn.lat) / 2);
  const northM = (onSteps.lat - spawn.lat) * M_PER_DEG_LAT;
  const names = spawn.plaqueNames ?? [];
  const countsOk =
    spawn.streetPlaques >= 4 &&
    spawn.plaqueKind === "pole-board" &&
    spawn.plaqueOfficial >= 2 &&
    spawn.plaqueInner >= 2 &&
    names.includes("Harbor Walk") &&
    names.includes("Tram Approach") &&
    names.includes("Steps East") &&
    names.includes("Steps West");
  const harborVisible =
    labelOnScreen(onHarbor, "Harbor Walk") || harborPix.plaqueRatio >= 0.004 || harborPix.creamRatio >= 0.003;
  const stepsVisible =
    labelOnScreen(onSteps, "Steps East") || stepsPix.plaqueRatio >= 0.004 || stepsPix.creamRatio >= 0.003;
  const walkedOff =
    eastM > 6 &&
    northM > 10 &&
    onSteps.insideRing === "0" &&
    onSteps.insideAabb === "0";
  const lumOk = walkMinusRoad >= 12 && lane.roadLum < 110;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const leftoverOk = leftoverB && !leftoverEStolen && !bAfterE.shopPanel;
  const honestyOk =
    /Authored approximation/.test(spawn.honesty) &&
    /not a digital twin/i.test(spawn.honesty) &&
    /inner parcel lanes/.test(spawn.honesty) &&
    /two official named streets/.test(spawn.honesty) &&
    /NOT_PLAN_PASS/.test(spawn.honesty) &&
    spawn.gtaClaim === false;
  const geoOk = geoStreets.length === 2;
  const keptOk =
    spawn.sky === "gradient-hemisphere" &&
    spawn.collision === "footprint-radius" &&
    spawn.blockEdge === "curb-wall-lot" &&
    spawn.fog === "distance-haze" &&
    spawn.walkCycle === "opposite-stride" &&
    spawn.groundFloor === "door-glass-awning" &&
    spawn.innerLane === "asphalt-walk-edge" &&
    spawn.ground === "road-walk-curb";

  const ok =
    countsOk &&
    harborVisible &&
    stepsVisible &&
    walkedOff &&
    lumOk &&
    lanternOk &&
    leftoverOk &&
    shopClosed.shopPanel === false &&
    honestyOk &&
    geoOk &&
    keptOk &&
    onHarbor.alt === 0 &&
    onSteps.alt === 0;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_STREET_NAME_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    countsOk,
    harborVisible,
    stepsVisible,
    walkedOff,
    lumOk,
    lanternOk,
    leftoverOk,
    honestyOk,
    geoOk,
    keptOk,
    geoStreets: geoStreets.map((row) => row.properties?.display_name ?? row.properties?.name),
    eastM: Number(eastM.toFixed(2)),
    northM: Number(northM.toFixed(2)),
    walkMinusRoad,
    plaqueNames: names,
    spawn,
    onHarbor,
    onSteps,
    atLantern,
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    harborPix,
    stepsPix,
    lane,
    honesty: spawn.honesty?.slice(0, 280),
    shots: { harbor: SHOT_HARBOR, steps: SHOT_STEPS },
    hashHarbor: createHash("sha256").update(harborBuf).digest("hex").slice(0, 16),
    hashSteps: createHash("sha256").update(stepsBuf).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_STREET_NAME_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `plaques=${report.spawn?.streetPlaques}`,
  `names=${(report.plaqueNames ?? []).join(",")}`,
  `harborVis=${report.harborVisible}`,
  `stepsVis=${report.stepsVisible}`,
  `east=${report.eastM}`,
  `lumDelta=${report.walkMinusRoad}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
