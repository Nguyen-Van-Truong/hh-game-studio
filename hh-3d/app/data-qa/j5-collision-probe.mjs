/**
 * Solid collision remint: walk into a wall on recycled 4175.
 * Position must not enter a building AABB. Feet stay on the slab.
 * NOT_PLAN_PASS. Not GATE-U1. Not a 1:1 / GTA claim.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9362);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-COLLISION-2026-09-03.txt");
const SHOT = join(import.meta.dirname, "j5-3d-wall.png");
const M_PER_DEG_LAT = 111320;

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const playCanvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const boxes = [...document.querySelectorAll('[data-testid="play-building-list"] [data-mesh="extrude"]')].map(
    (el) => ({
      id: el.getAttribute("data-building-id"),
      west: Number(el.getAttribute("data-west") ?? "NaN"),
      south: Number(el.getAttribute("data-south") ?? "NaN"),
      east: Number(el.getAttribute("data-east") ?? "NaN"),
      north: Number(el.getAttribute("data-north") ?? "NaN"),
    }),
  );
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
          insideAabb: avatar.getAttribute("data-inside-aabb"),
          blocked: avatar.getAttribute("data-blocked"),
          collision: avatar.getAttribute("data-collision"),
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
          blocked: proof.getAttribute("data-blocked") ?? "",
          hitBuilding: proof.getAttribute("data-hit-building") ?? "",
        }
      : null,
    boxes,
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-col-"));
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
  await cdp(ws, 4, "Page.navigate", { url: PLAYER });

  let home = null;
  const readyDeadline = Date.now() + 12000;
  while (Date.now() < readyDeadline) {
    home = await evalExpr(ws, 10, SNAP);
    if (home.playReady === "yes" && home.avatar && home.proof?.buildings >= 20) {
      break;
    }
    await sleep(150);
  }

  const geoRes = await fetch(new URL("/data/ben-thanh-400m.authored.geojson", PLAYER));
  const geo = await geoRes.json();
  const liveBoxes = geo.features
    .filter((feature) => feature.properties?.kind === "building")
    .map((feature) => ({
      id: String(feature.id ?? feature.properties.id),
      ...ringAabb(feature.geometry.coordinates[0]),
    }));

  await keyHold(ws, 21, "w", "KeyW", 87, 8000);
  await sleep(200);
  const upStreet = await evalExpr(ws, 30, SNAP);

  await keyHold(ws, 32, "d", "KeyD", 68, 820);
  await sleep(200);
  const turned = await evalExpr(ws, 40, SNAP);

  await keyHold(ws, 42, "w", "KeyW", 87, 10000);
  await sleep(200);
  const atWall = await evalExpr(ws, 50, SNAP);

  await keyHold(ws, 52, "w", "KeyW", 87, 3000);
  await sleep(200);
  const still = await evalExpr(ws, 60, SNAP);
  const shot = await cdp(ws, 51, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  const pos = (snap) => ({ lon: snap.avatar.lon, lat: snap.avatar.lat });
  const street = deltaM(pos(home), pos(upStreet));
  const toward = deltaM(pos(turned), pos(atWall));
  const extra = deltaM(pos(atWall), pos(still));

  const insideAfter = (snap) => {
    const lon = snap.avatar.lon;
    const lat = snap.avatar.lat;
    const live = liveBoxes.filter((box) => pointInAabb(lon, lat, box)).map((box) => box.id);
    const dom = (snap.boxes ?? []).filter((box) => pointInAabb(lon, lat, box)).map((box) => box.id);
    return { live, dom };
  };
  const hitAfter = insideAfter(atWall);
  const hitStill = insideAfter(still);
  const nearest = liveBoxes
    .map((box) => ({ id: box.id, dist: distToAabb(still.avatar.lon, still.avatar.lat, box) }))
    .sort((a, b) => a.dist - b.dist)[0];

  const playOk =
    home.playReady === "yes" &&
    home.playEngine === "r3f" &&
    home.playCanvas &&
    home.proof?.camera === "behind" &&
    home.proof?.follow === "heading" &&
    home.proof?.buildings >= 20 &&
    home.proof?.collision === "aabb-radius" &&
    home.proof?.groundY === "0" &&
    home.avatar?.groundY === "0" &&
    home.avatar?.insideAabb === "0";
  const streetOk = street.north > 8 && street.east < 1.5;
  const walkTowardOk = toward.east > 6 && toward.moved > 6;
  const blockedOk =
    toward.east < 14 &&
    extra.east < 0.6 &&
    hitAfter.live.length === 0 &&
    hitAfter.dom.length === 0 &&
    hitStill.live.length === 0 &&
    hitStill.dom.length === 0 &&
    atWall.proof?.insideAabb === "0" &&
    still.proof?.insideAabb === "0" &&
    still.avatar?.insideAabb === "0" &&
    nearest &&
    nearest.dist < 1.25;
  const stayOnSlabOk = still.avatar?.groundY === "0" && still.proof?.groundY === "0";
  const turnOk = Number(turned.proof?.heading) > 70 && Number(turned.proof?.heading) < 120;
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);
  const shopOk = Boolean(home.shopMarker || turned.shopMarker || atWall.shopMarker);

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-07",
    player: PLAYER,
    verdict:
      playOk &&
      streetOk &&
      walkTowardOk &&
      blockedOk &&
      stayOnSlabOk &&
      turnOk &&
      honestyOk &&
      shopOk
        ? "J5_COLLISION_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    playOk,
    streetOk,
    walkTowardOk,
    blockedOk,
    stayOnSlabOk,
    turnOk,
    honestyOk,
    shopOk,
    street,
    toward,
    extra,
    nearest,
    hitAfter,
    hitStill,
    liveBuildingCount: liveBoxes.length,
    home,
    upStreet,
    turned,
    atWall,
    still,
    shot: SHOT,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-07",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_COLLISION_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `east=${report.toward.east.toFixed(2)}`,
  `extraEast=${report.extra.east.toFixed(3)}`,
  `near=${report.nearest.id}@${report.nearest.dist.toFixed(2)}m`,
  `inside=0`,
);
