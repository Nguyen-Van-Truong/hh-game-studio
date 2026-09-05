/**
 * Player-feel remint: right-drag look changes camera; W walks along look;
 * angled wall hold slides along the face (stable, no clip). Recycled 4175.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN / city.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9374);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FEEL-2026-09-03.txt");
const SHOT_LOOK = join(import.meta.dirname, "j5-3d-look.png");
const SHOT_SLIDE = join(import.meta.dirname, "j5-3d-slide.png");
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
  const r = playCanvas ? playCanvas.getBoundingClientRect() : null;
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    playEngine: play?.getAttribute("data-engine") ?? "",
    playCanvas: Boolean(playCanvas),
    canvasBox: r
      ? { x: r.left, y: r.top, w: r.width, h: r.height }
      : null,
    avatar: avatar
      ? {
          lon: Number(avatar.dataset.lon),
          lat: Number(avatar.dataset.lat),
          heading: Number(avatar.dataset.heading),
          pose: avatar.dataset.pose,
          look: avatar.getAttribute("data-look") ?? "",
          slide: avatar.getAttribute("data-slide") ?? "",
          insideAabb: avatar.getAttribute("data-inside-aabb"),
        }
      : null,
    proof: proof
      ? {
          camera: proof.getAttribute("data-camera"),
          follow: proof.getAttribute("data-follow"),
          look: proof.getAttribute("data-look") ?? "",
          heading: Number(proof.getAttribute("data-heading") ?? "NaN"),
          camYaw: Number(proof.getAttribute("data-cam-yaw") ?? "NaN"),
          camPitch: Number(proof.getAttribute("data-cam-pitch") ?? "NaN"),
          camX: Number(proof.getAttribute("data-cam-x") ?? "NaN"),
          camY: Number(proof.getAttribute("data-cam-y") ?? "NaN"),
          camZ: Number(proof.getAttribute("data-cam-z") ?? "NaN"),
          buildings: Number(proof.getAttribute("data-buildings") ?? "0"),
          slide: proof.getAttribute("data-slide") ?? "",
          insideAabb: proof.getAttribute("data-inside-aabb") ?? "",
          hitBuilding: proof.getAttribute("data-hit-building") ?? "",
        }
      : null,
    status: document.querySelector('[data-testid="avatar-status"]')?.textContent ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    pad: Boolean(document.querySelector('[data-testid="walk-pad"]')),
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
  const base = { bubbles: true, cancelable: true, pointerId: 7, pointerType: "mouse", isPrimary: true };
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
    bubbles: true, cancelable: true, pointerId: 7, pointerType: "mouse", button: 2, buttons: 0,
    clientX: r.left + r.width * 0.5 + 180, clientY: r.top + r.height * 0.42 - 36,
  }));
  return true;
}`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-feel-"));
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
  const readyDeadline = Date.now() + 14000;
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

  const box = home.canvasBox ?? { x: 640, y: 300, w: 1280, h: 720 };
  const cx = Math.round(box.x + box.w * 0.5);
  const cy = Math.round(box.y + box.h * 0.42);
  await cdp(ws, 20, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: cx,
    y: cy,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await cdp(ws, 21, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: cx + 180,
    y: cy - 36,
    button: "right",
    buttons: 2,
  });
  await sleep(80);
  let during = await evalExpr(ws, 22, SNAP);
  let lookPath = "cdp-mouse";
  if (
    !(
      during.proof &&
      (during.proof.look === "drag" || Math.abs(during.proof.camYaw - (home.proof?.camYaw ?? 0)) > 4)
    )
  ) {
    await evalExpr(ws, 23, `(${DRAG})(180, -36)`);
    await sleep(80);
    during = await evalExpr(ws, 24, SNAP);
    lookPath = "canvas-pointer";
  }
  const lookShot = await cdp(ws, 25, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_LOOK, Buffer.from(lookShot.data, "base64"));
  await cdp(ws, 26, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: cx + 180,
    y: cy - 36,
    button: "right",
    buttons: 0,
    clickCount: 1,
  });
  await evalExpr(ws, 27, `(${DRAG_END})()`);
  await sleep(120);
  const afterLook = await evalExpr(ws, 28, SNAP);

  await keyHold(ws, 30, "w", "KeyW", 87, 2200);
  await sleep(150);
  const walked = await evalExpr(ws, 40, SNAP);

  await keyHold(ws, 41, "a", "KeyA", 65, 400);
  await sleep(80);
  const afterA = await evalExpr(ws, 42, SNAP);

  await cdp(ws, 50, "Page.reload", { ignoreCache: true });
  let reset = null;
  const resetDeadline = Date.now() + 12000;
  while (Date.now() < resetDeadline) {
    reset = await evalExpr(ws, 51, SNAP);
    if (reset.playReady === "yes" && reset.avatar) {
      break;
    }
    await sleep(150);
  }

  await keyHold(ws, 60, "w", "KeyW", 87, 8000);
  await sleep(150);
  const upStreet = await evalExpr(ws, 61, SNAP);
  await keyHold(ws, 62, "d", "KeyD", 68, 860);
  await sleep(120);
  const turned = await evalExpr(ws, 63, SNAP);
  await keyHold(ws, 64, "w", "KeyW", 87, 10000);
  await sleep(150);
  const atWall = await evalExpr(ws, 65, SNAP);

  const slideSamples = [];
  await cdp(ws, 70, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  for (let i = 0; i < 12; i += 1) {
    await sleep(500);
    const row = await evalExpr(ws, 71 + i, SNAP);
    slideSamples.push({
      lon: row.avatar?.lon,
      lat: row.avatar?.lat,
      pose: row.avatar?.pose,
      slide: row.proof?.slide ?? row.avatar?.slide,
      inside: row.proof?.insideAabb,
      heading: row.proof?.heading,
    });
  }
  await cdp(ws, 90, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  await sleep(120);
  const still = await evalExpr(ws, 91, SNAP);
  const slideShot = await cdp(ws, 92, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_SLIDE, Buffer.from(slideShot.data, "base64"));

  const pos = (snap) => ({ lon: snap.avatar.lon, lat: snap.avatar.lat });
  const lookWalk = deltaM(pos(afterLook), pos(walked));
  const street = deltaM(pos(reset), pos(upStreet));
  const toward = deltaM(pos(turned), pos(atWall));
  const extra = deltaM(pos(atWall), pos(still));
  const lons = slideSamples.map((row) => row.lon).filter((n) => Number.isFinite(n));
  const lats = slideSamples.map((row) => row.lat).filter((n) => Number.isFinite(n));
  const lonSpanM =
    lons.length >= 2 ? (Math.max(...lons) - Math.min(...lons)) * metersPerDegLon(lats[0] ?? 10.77) : 99;
  const latMono =
    lats.length >= 3 &&
    lats.every((lat, i) => i === 0 || lat <= lats[i - 1] + 1e-8);
  const insideSlide = slideSamples.some((row) => row.inside === "1");
  const hitStill = liveBoxes.filter((boxRow) => pointInAabb(still.avatar.lon, still.avatar.lat, boxRow));
  const yawDelta = Math.abs((during.proof?.camYaw ?? 0) - (home.proof?.camYaw ?? 0));
  const yawKept = Math.abs((afterLook.proof?.camYaw ?? 0) - (home.proof?.camYaw ?? 0));
  const pitchDelta = Math.abs((during.proof?.camPitch ?? 0) - (home.proof?.camPitch ?? 0));
  const camMoved =
    Math.abs((during.proof?.camX ?? 0) - (home.proof?.camX ?? 0)) > 0.25 ||
    Math.abs((during.proof?.camZ ?? 0) - (home.proof?.camZ ?? 0)) > 0.25;

  const lookOk =
    home.playReady === "yes" &&
    (during.proof?.look === "drag" || yawDelta > 8) &&
    yawKept > 8 &&
    camMoved &&
    afterLook.proof?.camYaw > 8;
  const walkAlongLookOk = lookWalk.moved > 2 && lookWalk.east > 0.4;
  const padStillTurns = Number(afterA.proof?.heading) !== Number(afterLook.proof?.heading);
  const streetOk = street.north > 8 && street.east < 1.5;
  const slideOk =
    toward.east > 6 &&
    extra.east < 0.08 &&
    lonSpanM < 0.06 &&
    latMono &&
    extra.north < -0.25 &&
    !insideSlide &&
    hitStill.length === 0 &&
    still.avatar?.insideAabb === "0";
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);
  const padOk = Boolean(home.pad);

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-09",
    player: PLAYER,
    verdict:
      lookOk && walkAlongLookOk && streetOk && slideOk && honestyOk && padOk
        ? "J5_FEEL_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    lookPath,
    lookOk,
    walkAlongLookOk,
    padStillTurns,
    streetOk,
    slideOk,
    honestyOk,
    padOk,
    yawDelta,
    yawKept,
    pitchDelta,
    camMoved,
    lookWalk,
    street,
    toward,
    extra,
    lonSpanM,
    latMono,
    slideSamples,
    duringLook: during.proof,
    afterLook: afterLook.proof,
    atWall: { lon: atWall.avatar?.lon, lat: atWall.avatar?.lat, heading: atWall.proof?.heading },
    still: { lon: still.avatar?.lon, lat: still.avatar?.lat, inside: still.avatar?.insideAabb },
    shots: { look: SHOT_LOOK, slide: SHOT_SLIDE },
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-09",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_FEEL_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `look=${report.lookPath}`,
  `yaw=${report.yawKept.toFixed(1)}`,
  `walkE=${report.lookWalk.east.toFixed(2)}`,
  `slideN=${report.extra.north.toFixed(2)}`,
  `lonSpan=${report.lonSpanM.toFixed(3)}`,
);
