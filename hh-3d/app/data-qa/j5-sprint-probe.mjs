/**
 * Sprint (Shift / pad ≫) is faster than walk on recycled 4175.
 * Body stays the tunic humanoid. Look / WASD / collision not the proof.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN / city.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9376);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-SPRINT-2026-09-03.txt");
const SHOT_STAND = join(import.meta.dirname, "j5-3d-body-stand.png");
const SHOT_WALK = join(import.meta.dirname, "j5-3d-body-walk.png");
const SHOT_SPRINT = join(import.meta.dirname, "j5-3d-body-sprint.png");
const M_PER_DEG_LAT = 111320;
const HOLD_MS = 3000;

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
    canvas: Boolean(playCanvas),
    canvasBox: r ? { w: Math.round(r.width), h: Math.round(r.height) } : null,
    pose: avatar?.getAttribute("data-pose") ?? "",
    sprint: avatar?.getAttribute("data-sprint") ?? proof?.getAttribute("data-sprint") ?? "",
    turning: avatar?.getAttribute("data-turning") ?? "",
    body: avatar?.getAttribute("data-body") ?? proof?.getAttribute("data-body") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    look: proof?.getAttribute("data-look") ?? "",
    camYaw: Number(proof?.getAttribute("data-cam-yaw") ?? "NaN"),
    camera: proof?.getAttribute("data-camera") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    status: document.querySelector('[data-testid="avatar-status"]')?.textContent ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    padSprint: Boolean(document.querySelector('[data-testid="walk-sprint"]')),
    padJump: Boolean(document.querySelector('[data-testid="walk-jump"]')),
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-sprint-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    PLAYER,
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

  let home = null;
  const readyDeadline = Date.now() + 14000;
  while (Date.now() < readyDeadline) {
    home = await evalExpr(ws, 10, SNAP);
    if (home.playReady === "yes" && Number.isFinite(home.lon) && home.buildings >= 20) {
      break;
    }
    await sleep(150);
  }

  const standShot = await cdp(ws, 11, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_STAND, Buffer.from(standShot.data, "base64"));

  await keyDown(ws, 20, "w", "KeyW", 87);
  await sleep(900);
  const midWalk = await evalExpr(ws, 21, SNAP);
  const walkShot = await cdp(ws, 22, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_WALK, Buffer.from(walkShot.data, "base64"));
  await sleep(HOLD_MS - 900);
  await keyUp(ws, 23, "w", "KeyW", 87);
  await sleep(120);
  const afterWalk = await evalExpr(ws, 24, SNAP);
  const walk = deltaM(
    { lon: home.lon, lat: home.lat },
    { lon: afterWalk.lon, lat: afterWalk.lat },
  );

  await cdp(ws, 30, "Page.reload", { ignoreCache: true });
  let reset = null;
  const resetDeadline = Date.now() + 12000;
  while (Date.now() < resetDeadline) {
    reset = await evalExpr(ws, 31, SNAP);
    if (reset.playReady === "yes" && Number.isFinite(reset.lon)) {
      break;
    }
    await sleep(150);
  }

  await keyDown(ws, 40, "Shift", "ShiftLeft", 16, 8);
  await keyDown(ws, 41, "w", "KeyW", 87, 8);
  await sleep(900);
  const midSprint = await evalExpr(ws, 42, SNAP);
  const sprintShot = await cdp(ws, 43, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_SPRINT, Buffer.from(sprintShot.data, "base64"));
  await sleep(HOLD_MS - 900);
  await keyUp(ws, 44, "w", "KeyW", 87, 8);
  await keyUp(ws, 45, "Shift", "ShiftLeft", 16);
  await sleep(120);
  const afterSprint = await evalExpr(ws, 46, SNAP);
  const sprint = deltaM(
    { lon: reset.lon, lat: reset.lat },
    { lon: afterSprint.lon, lat: afterSprint.lat },
  );

  const walkMps = walk.moved / (HOLD_MS / 1000);
  const sprintMps = sprint.moved / (HOLD_MS / 1000);
  const faster = sprint.moved > walk.moved * 1.2 && sprintMps > walkMps;
  const walkOk = walk.north > 4.2 && walk.east < 0.4 && walkMps > 1.2 && walkMps < 2.0;
  const sprintOk =
    faster &&
    sprint.north > walk.north + 1.5 &&
    sprint.east < 0.5 &&
    sprintMps > 2.2 &&
    sprintMps < 3.4 &&
    (midSprint.sprint === "1" || /sprint/i.test(midSprint.status));
  const released = afterSprint.sprint === "0";
  const bodyOk = home.body === "tunic-humanoid" && home.camera === "behind";
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false;
  const padOk = home.padSprint && home.padJump;
  const streetOk = home.buildings >= 60 && afterWalk.insideAabb === "0" && afterSprint.insideAabb === "0";

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-10",
    player: PLAYER,
    verdict: sprintOk && walkOk && bodyOk && honestyOk && padOk && streetOk && released ? "J5_SPRINT_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    holdMs: HOLD_MS,
    walk,
    sprint,
    walkMps,
    sprintMps,
    faster,
    walkOk,
    sprintOk,
    released,
    bodyOk,
    honestyOk,
    padOk,
    streetOk,
    midWalk: { pose: midWalk.pose, sprint: midWalk.sprint, status: midWalk.status },
    midSprint: { pose: midSprint.pose, sprint: midSprint.sprint, status: midSprint.status },
    afterWalk: { lon: afterWalk.lon, lat: afterWalk.lat, sprint: afterWalk.sprint },
    afterSprint: { lon: afterSprint.lon, lat: afterSprint.lat, sprint: afterSprint.sprint },
    home: {
      buildings: home.buildings,
      body: home.body,
      camera: home.camera,
      canvas: home.canvasBox,
    },
    shots: { stand: SHOT_STAND, walk: SHOT_WALK, sprint: SHOT_SPRINT },
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-10",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_SPRINT_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walk=${report.walkMps.toFixed(2)}`,
  `sprint=${report.sprintMps.toFixed(2)}`,
  `faster=${report.faster}`,
);
