/**
 * Space jump on the 60-building authored block. Recycled 4175 only.
 * Heading-follow, walls, slim HUD, shop E stay. Not a city. NOT_PLAN_PASS.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9366);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-JUMP-2026-09-03.txt");
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
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const menu = document.querySelector('[data-testid="play-menu"]');
  const status = document.querySelector('[data-testid="avatar-status"]')?.textContent ?? "";
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  };
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: box(canvas),
    menuOpen: menu?.getAttribute("data-open") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    alt: Number(avatar?.getAttribute("data-alt") ?? "NaN"),
    airborne: avatar?.getAttribute("data-airborne") ?? "",
    groundY: avatar?.getAttribute("data-ground-y") ?? "",
    camYaw: Number(proof?.getAttribute("data-cam-yaw") ?? "NaN"),
    follow: proof?.getAttribute("data-follow") ?? "",
    camera: proof?.getAttribute("data-camera") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    status,
    stallHint: document.querySelector('[data-testid="stall-hint"]')?.textContent ?? "",
    shopPanel: Boolean(document.querySelector('[data-testid="shop-panel"]')),
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.textContent ?? "",
    jumpPad: Boolean(document.querySelector('[data-testid="walk-jump"]')),
  };
})()`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-jump-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    "--disable-gpu",
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
  await sleep(2200);
  let home = await evalExpr(ws, 10, SNAP);
  for (let i = 0; i < 20 && home.playReady !== "yes"; i += 1) {
    await sleep(250);
    home = await evalExpr(ws, 11 + i, SNAP);
  }
  const homeLon = home.lon;
  const homeLat = home.lat;

  await cdp(ws, 40, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: " ",
    code: "Space",
    windowsVirtualKeyCode: 32,
    nativeVirtualKeyCode: 32,
  });
  await cdp(ws, 41, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: " ",
    code: "Space",
    windowsVirtualKeyCode: 32,
    nativeVirtualKeyCode: 32,
  });

  let peak = home;
  let seq = 50;
  for (let i = 0; i < 18; i += 1) {
    await sleep(40);
    const snap = await evalExpr(ws, seq, SNAP);
    seq += 1;
    if (snap.alt > (peak.alt || 0)) {
      peak = snap;
    }
  }
  await sleep(700);
  const landed = await evalExpr(ws, 80, SNAP);

  await keyHold(ws, 90, "a", "KeyA", 65, 1200);
  const turned = await evalExpr(ws, 100, SNAP);
  await keyHold(ws, 101, "w", "KeyW", 87, 2500);
  const walked = await evalExpr(ws, 110, SNAP);
  const northM = (walked.lat - homeLat) * M_PER_DEG_LAT;
  const eastM = (walked.lon - homeLon) * metersPerDegLon((walked.lat + homeLat) / 2);

  const jumpOk = peak.airborne === "1" && peak.alt >= 0.35 && peak.alt < 1.4;
  const landOk = landed.airborne === "0" && landed.alt <= 0.05 && landed.groundY === "0";
  const turnOk = turned.heading > 90 && turned.camYaw > 90;
  const walkOk = northM > 2 || Math.abs(eastM) > 2;
  const hudOk = home.menuOpen === "no" && home.canvas?.w >= 1200 && home.buildings === 60;
  const honestyOk = /NOT_PLAN_PASS/.test(home.honesty) && /authored/i.test(home.honesty);

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-08",
    player: PLAYER,
    verdict: jumpOk && landOk && turnOk && walkOk && hudOk && honestyOk ? "J5_JUMP_OK" : "J5_REWORK",
    not_plan_pass: true,
    jumpOk,
    landOk,
    turnOk,
    walkOk,
    hudOk,
    honestyOk,
    peakAlt: peak.alt,
    peakAirborne: peak.airborne,
    landedAlt: landed.alt,
    homeHeading: home.heading,
    turnedHeading: turned.heading,
    turnedCamYaw: turned.camYaw,
    northM,
    eastM,
    buildings: home.buildings,
    jumpPad: home.jumpPad,
    statusPeak: peak.status,
  };
  ws.close();
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J5_JUMP_OK") {
  process.exitCode = 1;
}
