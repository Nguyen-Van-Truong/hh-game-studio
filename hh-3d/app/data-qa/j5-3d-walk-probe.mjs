/**
 * J5 remint: extruded authored block on recycled 4175.
 * Building meshes >> 5; walk / heading-follow / slim HUD / shop E still work.
 * NOT_PLAN_PASS. Not GATE-U1. Not a 1:1 / GTA claim.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9296);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-3D-WALK-2026-09-03.txt");
const SHOT = join(import.meta.dirname, "j5-3d-walk-behind.png");
const SHOT_TURN = join(import.meta.dirname, "j5-3d-walk-turn.png");
const SHOT_BLOCK = join(import.meta.dirname, "j5-3d-block.png");
const M_PER_DEG_LAT = 111320;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const map = document.querySelector('[data-testid="hh-world-map"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
  };
  const vis = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden") return null;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    return { sel, w: r.width, h: r.height, area: r.width * r.height, top: r.top, left: r.left };
  };
  const chrome = [
    vis(".topbar"),
    vis(".honesty-slim") || vis(".honesty"),
    vis('[data-testid="play-menu"]'),
    vis(".street-help"),
    vis(".walk-pad"),
    vis(".minimap-wrap"),
    vis(".mode-bar"),
    vis(".shop-sheet"),
  ].filter(Boolean);
  const overlayArea = chrome.reduce((n, row) => n + row.area, 0);
  return {
    title: document.title,
    href: location.href,
    play: Boolean(play),
    playEngine: play?.getAttribute("data-engine") ?? "",
    playCanvas: Boolean(playCanvas),
    playBox: box(play) ?? box(playCanvas),
    mini: Boolean(mini),
    miniBox: box(mini),
    worldMap: Boolean(map),
    maplibreMain: Boolean(document.querySelector(".map-pane:not(.map-pane-play) .maplibregl-canvas")),
    maplibreAny: Boolean(document.querySelector(".maplibregl-canvas")),
    three: typeof window.THREE !== "undefined",
    webglCanvas: playCanvas ? Boolean(playCanvas.getContext && (playCanvas.getContext("webgl2") || playCanvas.getContext("webgl"))) : false,
    avatar: avatar
      ? {
          engine: avatar.getAttribute("data-engine"),
          pose: avatar.dataset.pose,
          heading: avatar.dataset.heading,
          lon: avatar.dataset.lon,
          lat: avatar.dataset.lat,
          doll: /avatar-head|avatar-torso/.test(avatar.innerHTML),
          box: box(avatar),
        }
      : null,
    proof: proof
      ? {
          engine: proof.getAttribute("data-engine"),
          camera: proof.getAttribute("data-camera"),
          follow: proof.getAttribute("data-follow"),
          heading: Number(proof.getAttribute("data-heading") ?? "NaN"),
          camYaw: Number(proof.getAttribute("data-cam-yaw") ?? "NaN"),
          camX: Number(proof.getAttribute("data-cam-x") ?? "NaN"),
          camZ: Number(proof.getAttribute("data-cam-z") ?? "NaN"),
          buildings: Number(proof.getAttribute("data-buildings") ?? "0"),
          extruded: proof.getAttribute("data-extruded") ?? "",
        }
      : null,
    buildingList: [...document.querySelectorAll('[data-testid="play-building-list"] [data-mesh="extrude"]')].map(
      (el) => el.getAttribute("data-building-id"),
    ),
    menuOpen: menu?.getAttribute("data-open") === "yes",
    menuHidden: Boolean(menu?.hidden),
    menuBox: box(menu),
    chrome,
    overlayArea,
    overlayRatio: overlayArea / (1280 * 720),
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    menuToggle: Boolean(document.querySelector('[data-testid="play-menu-toggle"]')),
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-"));
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
  await cdp(ws, 4, "Page.navigate", { url: PLAYER });
  await sleep(2800);
  const home = await evalExpr(ws, 10, SNAP);
  const shotHome = await cdp(ws, 9, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_BLOCK, Buffer.from(shotHome.data, "base64"));

  await keyHold(ws, 11, "w", "KeyW", 87, 9000);
  await sleep(200);
  const walked = await evalExpr(ws, 20, SNAP);

  await keyHold(ws, 21, "a", "KeyA", 65, 1200);
  await sleep(200);
  const turnedLeft = await evalExpr(ws, 30, SNAP);
  const shotLeft = await cdp(ws, 31, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT_TURN, Buffer.from(shotLeft.data, "base64"));

  await keyHold(ws, 32, "d", "KeyD", 68, 1200);
  await sleep(200);
  const turnedRight = await evalExpr(ws, 40, SNAP);
  const shot = await cdp(ws, 41, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  const movedM = (() => {
    if (!home.avatar || !walked.avatar) return 0;
    const mid = (Number(home.avatar.lat) + Number(walked.avatar.lat)) / 2;
    const east =
      (Number(walked.avatar.lon) - Number(home.avatar.lon)) *
      (M_PER_DEG_LAT * Math.cos((mid * Math.PI) / 180));
    const north = (Number(walked.avatar.lat) - Number(home.avatar.lat)) * M_PER_DEG_LAT;
    return Math.hypot(east, north);
  })();

  const yawDelta = (a, b) => {
    const d = Math.abs(a - b) % 360;
    return d > 180 ? 360 - d : d;
  };
  const homeYaw = home.proof?.camYaw;
  const leftYaw = turnedLeft.proof?.camYaw;
  const rightYaw = turnedRight.proof?.camYaw;
  const leftHead = turnedLeft.proof?.heading;
  const rightHead = turnedRight.proof?.heading;
  const turnLeftOk =
    Number.isFinite(homeYaw) &&
    Number.isFinite(leftYaw) &&
    yawDelta(homeYaw, leftYaw) > 40 &&
    Math.abs(leftYaw - leftHead) < 1.5;
  const turnRightOk =
    Number.isFinite(rightYaw) &&
    yawDelta(leftYaw, rightYaw) > 40 &&
    Math.abs(rightYaw - rightHead) < 1.5;
  const hudOk =
    home.menuOpen === false &&
    home.menuHidden === true &&
    home.overlayRatio < 0.5 &&
    home.menuToggle === true &&
    (home.menuBox ? home.menuBox.w * home.menuBox.h === 0 || home.menuHidden : true);

  const playOk =
    home.play &&
    home.playEngine === "r3f" &&
    home.playCanvas &&
    home.playBox &&
    home.playBox.w >= 900 &&
    home.playBox.h >= 500 &&
    home.worldMap === false &&
    (home.miniBox ? home.miniBox.w * home.miniBox.h < home.playBox.w * home.playBox.h * 0.12 : true);
  const bodyOk =
    Boolean(home.avatar) &&
    home.avatar.engine === "r3f" &&
    home.avatar.doll === false &&
    home.proof?.camera === "behind" &&
    home.proof?.follow === "heading" &&
    home.proof?.buildings >= 20 &&
    home.proof?.extruded === "footprint" &&
    Array.isArray(home.buildingList) &&
    home.buildingList.length >= 20 &&
    home.buildingList.length === home.proof.buildings;
  const walkOk = movedM > 3 && Number(walked.avatar?.lat) > Number(home.avatar?.lat);
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false &&
    /Offline/.test(home.mode);
  const shopOk = home.shopMarker === true;

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-05",
    player: PLAYER,
    verdict:
      playOk && bodyOk && walkOk && honestyOk && shopOk && turnLeftOk && turnRightOk && hudOk
        ? "J5_OBSERVED"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    playOk,
    bodyOk,
    walkOk,
    honestyOk,
    shopOk,
    turnLeftOk,
    turnRightOk,
    hudOk,
    movedM,
    homeYaw,
    leftYaw,
    rightYaw,
    overlayRatio: home.overlayRatio,
    buildingCount: home.proof?.buildings ?? 0,
    buildingListCount: home.buildingList?.length ?? 0,
    shotBlock: SHOT_BLOCK,
    home,
    walked,
    turnedLeft,
    turnedRight,
    shot: SHOT,
    shotTurn: SHOT_TURN,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-05",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_OBSERVED") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `buildings=${report.buildingCount}`,
  `movedM=${report.movedM}`,
  `yaw ${report.homeYaw}->${report.leftYaw}->${report.rightYaw}`,
  `hud=${report.overlayRatio}`,
);
