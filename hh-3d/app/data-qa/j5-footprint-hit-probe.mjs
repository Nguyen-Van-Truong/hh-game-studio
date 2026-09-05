/**
 * Footprint-ring walk collision on recycled 4175.
 * Street-facing wall + chamfer inset: extra into the ring ≈ 0.
 * Slide still works. E at lantern still works. Spawn not trapped.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9411);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FOOTPRINT-HIT-2026-09-03.txt");
const SHOT_WALL = join(import.meta.dirname, "j5-3d-footprint-wall.png");
const SHOT_INSET = join(import.meta.dirname, "j5-3d-footprint-inset.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260903-ASIA-SAIGON-28";

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

function pointInAabb(lon, lat, box) {
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const playCanvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    playEngine: play?.getAttribute("data-engine") ?? "",
    playCanvas: Boolean(playCanvas),
    avatar: avatar
      ? {
          lon: Number(avatar.dataset.lon),
          lat: Number(avatar.dataset.lat),
          heading: Number(avatar.dataset.heading),
          pose: avatar.dataset.pose,
          groundY: avatar.getAttribute("data-ground-y"),
          alt: avatar.getAttribute("data-alt"),
          insideAabb: avatar.getAttribute("data-inside-aabb"),
          insideRing: avatar.getAttribute("data-inside-ring"),
          blocked: avatar.getAttribute("data-blocked"),
          collision: avatar.getAttribute("data-collision"),
          slide: avatar.getAttribute("data-slide"),
        }
      : null,
    proof: proof
      ? {
          camera: proof.getAttribute("data-camera"),
          follow: proof.getAttribute("data-follow"),
          heading: Number(proof.getAttribute("data-heading") ?? "NaN"),
          camYaw: Number(proof.getAttribute("data-cam-yaw") ?? "NaN"),
          buildings: Number(proof.getAttribute("data-buildings") ?? "0"),
          extruded: proof.getAttribute("data-extruded") ?? "",
          collision: proof.getAttribute("data-collision") ?? "",
          groundY: proof.getAttribute("data-ground-y") ?? "",
          insideAabb: proof.getAttribute("data-inside-aabb") ?? "",
          insideRing: proof.getAttribute("data-inside-ring") ?? "",
          blocked: proof.getAttribute("data-blocked") ?? "",
          hitBuilding: proof.getAttribute("data-hit-building") ?? "",
          slide: proof.getAttribute("data-slide") ?? "",
          lamps: proof.getAttribute("data-lamps") ?? "",
          crosswalks: proof.getAttribute("data-crosswalks") ?? "",
          planters: proof.getAttribute("data-planters") ?? "",
        }
      : null,
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

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
  throw new Error(`no CDP page: ${JSON.stringify(last)}`);
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

function headingError(from, to) {
  return ((to - from + 540) % 360) - 180;
}

async function turnTo(ws, id, target, tol = 3) {
  let snap = await evalExpr(ws, id, SNAP);
  for (let i = 0; i < 16; i += 1) {
    const err = headingError(Number(snap.avatar?.heading ?? 0), target);
    if (Math.abs(err) <= tol) {
      return { snap, id };
    }
    const ms = Math.min(380, Math.max(45, (Math.abs(err) / 110) * 1000 * 0.72));
    if (err > 0) {
      await keyHold(ws, id + 1, "d", "KeyD", 68, ms);
    } else {
      await keyHold(ws, id + 1, "a", "KeyA", 65, ms);
    }
    id += 3;
    await sleep(90);
    snap = await evalExpr(ws, id, SNAP);
  }
  return { snap, id };
}

async function goHome(ws, id) {
  await cdp(ws, id, "Page.navigate", { url: `${PLAYER}?seat=a` });
  await sleep(400);
  return waitReady(ws, id + 1);
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-fp-"));
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
  const steps = liveBuildings.find((row) => row.id === "bldg-steps-e-00");

  const classify = (snap) => {
    const lon = snap.avatar.lon;
    const lat = snap.avatar.lat;
    const liveAabb = liveBuildings.filter((box) => pointInAabb(lon, lat, box)).map((box) => box.id);
    const liveRing = liveBuildings.filter((row) => pointInRing(lon, lat, row.ring)).map((row) => row.id);
    return { liveAabb, liveRing };
  };

  const home = await goHome(ws, 4);
  await keyHold(ws, 20, "w", "KeyW", 87, 1200);
  await sleep(150);
  const afterSpawnW = await evalExpr(ws, 30, SNAP);
  const spawnStep = deltaM(
    { lon: home.avatar.lon, lat: home.avatar.lat },
    { lon: afterSpawnW.avatar.lon, lat: afterSpawnW.avatar.lat },
  );

  const insetHome = await goHome(ws, 40);
  const insetFace = await turnTo(ws, 50, 90, 3);
  const insetTurned = insetFace.snap;
  let atInset = insetTurned;
  let idCursor = insetFace.id + 5;
  for (let i = 0; i < 16; i += 1) {
    await keyHold(ws, idCursor, "w", "KeyW", 87, 500);
    idCursor += 3;
    await sleep(80);
    atInset = await evalExpr(ws, idCursor, SNAP);
    idCursor += 2;
    const hit = classify(atInset);
    if (hit.liveAabb.includes("bldg-steps-e-00") && hit.liveRing.length === 0) {
      break;
    }
  }
  await keyHold(ws, idCursor, "w", "KeyW", 87, 1500);
  await sleep(200);
  const insetStill = await evalExpr(ws, idCursor + 5, SNAP);
  const insetShot = await cdp(ws, 101, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_INSET, Buffer.from(insetShot.data, "base64"));

  const wallHome = await goHome(ws, 110);
  await keyHold(ws, 120, "w", "KeyW", 87, 3500);
  await sleep(150);
  const upStreet = await evalExpr(ws, 130, SNAP);
  await keyHold(ws, 140, "d", "KeyD", 68, 820);
  await sleep(150);
  const wallTurned = await evalExpr(ws, 150, SNAP);
  await keyHold(ws, 160, "w", "KeyW", 87, 10000);
  await sleep(200);
  const atWall = await evalExpr(ws, 170, SNAP);
  await keyHold(ws, 180, "w", "KeyW", 87, 3000);
  await sleep(200);
  const wallStill = await evalExpr(ws, 190, SNAP);
  const wallShot = await cdp(ws, 191, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_WALL, Buffer.from(wallShot.data, "base64"));

  await keyHold(ws, 200, "d", "KeyD", 68, 50);
  await sleep(80);
  const slideStart = await evalExpr(ws, 210, SNAP);
  await keyHold(ws, 220, "w", "KeyW", 87, 6000);
  await sleep(200);
  const slideEnd = await evalExpr(ws, 230, SNAP);

  const shopHome = await goHome(ws, 240);
  await keyHold(ws, 250, "w", "KeyW", 87, 16000);
  await sleep(250);
  const atLantern = await evalExpr(ws, 260, SNAP);
  await keyHold(ws, 270, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopOpen = await evalExpr(ws, 280, SNAP);

  const pos = (snap) => ({ lon: snap.avatar.lon, lat: snap.avatar.lat });
  const insetToward = deltaM(pos(insetTurned), pos(atInset));
  const insetExtra = deltaM(pos(atInset), pos(insetStill));
  const street = deltaM(pos(wallHome), pos(upStreet));
  const wallToward = deltaM(pos(wallTurned), pos(atWall));
  const wallExtra = deltaM(pos(atWall), pos(wallStill));
  const slide = deltaM(pos(slideStart), pos(slideEnd));
  const insetHit = classify(insetStill);
  const wallHit = classify(wallStill);
  const slideHit = classify(slideEnd);
  const nearestWall = liveBuildings
    .map((box) => ({ id: box.id, dist: distToAabb(wallStill.avatar.lon, wallStill.avatar.lat, box) }))
    .sort((a, b) => a.dist - b.dist)[0];
  const aabbWestM = steps
    ? (atInset.avatar.lon - steps.west) * metersPerDegLon(atInset.avatar.lat)
    : null;
  const insetInto = insetExtra.east + insetExtra.north;

  const playOk =
    home.playReady === "yes" &&
    home.playEngine === "r3f" &&
    home.playCanvas &&
    home.proof?.camera === "behind" &&
    home.proof?.buildings >= 20 &&
    home.proof?.collision === "footprint-radius" &&
    home.proof?.groundY === "0" &&
    home.avatar?.groundY === "0" &&
    home.avatar?.insideAabb === "0" &&
    home.avatar?.insideRing === "0";
  const spawnOk = spawnStep.north > 1.2 && spawnStep.east < 0.4 && classify(afterSpawnW).liveRing.length === 0;
  const streetOk = street.north > 4 && street.east < 1.5;
  const atInsetHit = classify(atInset);
  const aabbStopM = 11.07;
  const insetPastAabb = insetToward.east > aabbStopM + 0.55;
  const insetOk =
    insetPastAabb &&
    insetToward.east > 11.7 &&
    atInset.avatar?.insideRing === "0" &&
    atInsetHit.liveRing.length === 0 &&
    insetStill.avatar?.insideRing === "0" &&
    insetHit.liveRing.length === 0 &&
    atInset.proof?.collision === "footprint-radius";
  const wallOk =
    wallToward.east > 6 &&
    wallToward.east < 14 &&
    Math.abs(wallExtra.east) < 0.35 &&
    wallHit.liveRing.length === 0 &&
    wallStill.avatar?.insideRing === "0" &&
    wallStill.avatar?.groundY === "0" &&
    nearestWall &&
    nearestWall.id === "bldg-steps-e-00" &&
    nearestWall.dist < 1.25;
  const slideOk = Math.abs(slide.east) < 0.45 && slide.north < -0.3 && slideHit.liveRing.length === 0;
  const shopOk =
    Boolean(atLantern.shopMarker) &&
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      playOk && spawnOk && streetOk && insetOk && wallOk && slideOk && shopOk && honestyOk
        ? "J5_FOOTPRINT_HIT_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    playOk,
    spawnOk,
    streetOk,
    insetOk,
    wallOk,
    slideOk,
    shopOk,
    honestyOk,
    spawnStep,
    street,
    insetToward,
    insetExtra,
    insetInto,
    insetPastAabb,
    atInsetHit,
    wallToward,
    wallExtra,
    slide,
    insetHit,
    wallHit,
    slideHit,
    nearestWall,
    aabbWestM,
    liveBuildingCount: liveBuildings.length,
    home,
    afterSpawnW,
    insetTurned,
    atInset,
    insetStill,
    upStreet,
    wallTurned,
    atWall,
    wallStill,
    slideStart,
    slideEnd,
    atLantern,
    shopOpen,
    shotWall: SHOT_WALL,
    shotInset: SHOT_INSET,
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
if (report.verdict !== "J5_FOOTPRINT_HIT_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `insetEast=${report.insetToward.east.toFixed(2)}`,
  `insetExtra=${report.insetExtra.east.toFixed(3)}`,
  `wallExtra=${report.wallExtra.east.toFixed(3)}`,
  `slideN=${report.slide.north.toFixed(2)}`,
  `insideRing=0`,
  `shop=${report.shopOpen.shopPanelId}`,
);
