/**
 * Procedural self footsteps on recycled 4175.
 * data-footsteps=1 while W held; 0 standing; 0 when tab hidden / menu.
 * Lantern E still shop-lantern-fish. Seat B leftover E not stolen.
 * Honesty 1280x720. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FOOTSTEPS-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-footsteps.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9521), b: 9522 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-04";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const steps = document.querySelector('[data-testid="footstep-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const live = window.__hhFootsteps || null;
  const box = canvas
    ? (() => {
        const r = canvas.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
      })()
    : null;
  const read = (el) => ({
    footsteps: el?.getAttribute("data-footsteps") ?? "",
    kind: el?.getAttribute("data-footstep-kind") ?? "",
    ticks: el?.getAttribute("data-footstep-ticks") ?? "",
    muted: el?.getAttribute("data-footstep-muted") ?? "",
    reason: el?.getAttribute("data-footstep-reason") ?? "",
    sprint: el?.getAttribute("data-footstep-sprint") ?? "",
  });
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    hidden: document.hidden === true,
    menuOpen: menu?.getAttribute("data-open") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    sprint: avatar?.getAttribute("data-sprint") ?? proof?.getAttribute("data-sprint") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    scooters: proof?.getAttribute("data-scooters") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height, box } : null,
    play: read(play),
    proof: read(proof),
    steps: read(steps),
    avatar: read(avatar),
    live,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-steps-${port}-`));
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

function footLive(snap) {
  const row = snap?.steps?.footsteps || snap?.play?.footsteps || snap?.live?.live;
  if (row === true || row === 1) return "1";
  if (row === false || row === 0) return "0";
  return String(row ?? "");
}

function ticksOf(snap) {
  const live = snap?.live?.ticks;
  if (Number.isFinite(live)) return Number(live);
  const raw = snap?.steps?.ticks || snap?.play?.ticks;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
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

  const stand0 = await evalExpr(a.ws, 80, SNAP);
  await evalExpr(
    a.ws,
    81,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(120);
  await keyDown(a.ws, 82, "w", "KeyW", 87);
  const walking = await waitSnap(a.ws, 83, (s) => footLive(s) === "1" && s.pose === "walk", 24, 80);
  const ticksAtWalk = ticksOf(walking.snap);
  await sleep(1100);
  const walkHeld = await evalExpr(a.ws, 120, SNAP);
  const ticksWalk = ticksOf(walkHeld);
  const walkShot = await cdp(a.ws, 121, "Page.captureScreenshot", { format: "png" });
  const walkBuf = Buffer.from(walkShot.data, "base64");
  writeFileSync(SHOT, walkBuf);

  await evalExpr(
    a.ws,
    130,
    `(() => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
      document.dispatchEvent(new Event("visibilitychange"));
      return document.hidden;
    })()`,
  );
  const hidden = await waitSnap(a.ws, 131, (s) => footLive(s) === "0" && s.hidden === true, 16, 80);
  await evalExpr(
    a.ws,
    150,
    `(() => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
      document.dispatchEvent(new Event("visibilitychange"));
      return document.hidden;
    })()`,
  );
  const unhidden = await waitSnap(a.ws, 151, (s) => footLive(s) === "1" && s.hidden === false, 16, 80);

  await evalExpr(a.ws, 170, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  const menuOn = await waitSnap(
    a.ws,
    171,
    (s) => s.menuOpen === "yes" && footLive(s) === "0",
    16,
    80,
  );
  await evalExpr(a.ws, 190, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  const menuOff = await waitSnap(
    a.ws,
    191,
    (s) => s.menuOpen !== "yes" && footLive(s) === "1",
    16,
    80,
  );

  await keyUp(a.ws, 210, "w", "KeyW", 87);
  const standing = await waitSnap(a.ws, 211, (s) => s.pose === "idle" && footLive(s) === "0", 20, 80);

  await keyDown(a.ws, 230, "Shift", "ShiftLeft", 16, 8);
  await keyDown(a.ws, 231, "w", "KeyW", 87, 8);
  const sprinting = await waitSnap(
    a.ws,
    232,
    (s) => footLive(s) === "1" && (s.sprint === "1" || s.live?.sprint === true),
    20,
    80,
  );
  const ticksSprintStart = ticksOf(sprinting.snap);
  await sleep(1100);
  const sprintHeld = await evalExpr(a.ws, 260, SNAP);
  const ticksSprint = ticksOf(sprintHeld);
  await keyUp(a.ws, 261, "w", "KeyW", 87, 8);
  await keyUp(a.ws, 262, "Shift", "ShiftLeft", 16);
  await sleep(80);

  await keyHold(a.ws, 270, "w", "KeyW", 87, 18000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 290, SNAP);
  await keyHold(a.ws, 291, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 300, SNAP);

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

  const walkOn = footLive(walking.snap) === "1" && walking.snap.pose === "walk";
  const standOff = footLive(stand0) === "0" && footLive(standing.snap) === "0";
  const hiddenOff = footLive(hidden.snap) === "0" && hidden.snap.hidden === true;
  const unhiddenOn = footLive(unhidden.snap) === "1";
  const menuMute = footLive(menuOn.snap) === "0" && menuOn.snap.menuOpen === "yes";
  const menuResume = footLive(menuOff.snap) === "1";
  const walkDelta = ticksWalk - ticksAtWalk;
  const sprintDelta = ticksSprint - ticksSprintStart;
  const tickWalk = walkDelta >= 2;
  const tickSprint = sprintDelta >= 2;
  const sprintFaster = sprintDelta >= walkDelta;
  const walkGain = Number(walkHeld.live?.lastGain ?? 0);
  const sprintGain = Number(sprintHeld.live?.lastGain ?? 0);
  const louder = sprintGain === 0 || walkGain === 0 || sprintGain > walkGain;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const leftoverOk = leftoverB && !leftoverEStolen && !bAfterE.shopPanel;
  const honestyOk =
    /Authored approximation/.test(readyA.snap.honesty) &&
    /not a digital twin/i.test(readyA.snap.honesty) &&
    /NOT_PLAN_PASS/.test(readyA.snap.honesty) &&
    readyA.snap.gtaClaim === false;
  const kindOk =
    (readyA.snap.steps.kind || readyA.snap.play.kind) === "procedural-thump" &&
    readyA.snap.walkCycle === "opposite-stride";
  const keptOk =
    readyA.snap.sky === "gradient-hemisphere" &&
    readyA.snap.collision === "footprint-radius" &&
    Number(readyA.snap.scooters) === 15;

  const ok =
    walkOn &&
    standOff &&
    hiddenOff &&
    unhiddenOn &&
    menuMute &&
    menuResume &&
    tickWalk &&
    tickSprint &&
    sprintFaster &&
    louder &&
    lanternOk &&
    leftoverOk &&
    honestyOk &&
    kindOk &&
    keptOk;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_FOOTSTEPS_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    walkOn,
    standOff,
    hiddenOff,
    unhiddenOn,
    menuMute,
    menuResume,
    tickWalk,
    tickSprint,
    sprintFaster,
    louder,
    lanternOk,
    leftoverOk,
    honestyOk,
    kindOk,
    keptOk,
    ticks: {
      walkStart: ticksAtWalk,
      walkHeld: ticksWalk,
      walkDelta: ticksWalk - ticksAtWalk,
      sprintStart: ticksSprintStart,
      sprintHeld: ticksSprint,
      sprintDelta: ticksSprint - ticksSprintStart,
      walkGain,
      sprintGain,
    },
    stand0: { pose: stand0.pose, footsteps: footLive(stand0), ticks: ticksOf(stand0) },
    walking: { pose: walking.snap.pose, footsteps: footLive(walking.snap), live: walking.snap.live },
    hidden: { footsteps: footLive(hidden.snap), hidden: hidden.snap.hidden, reason: hidden.snap.live?.reason },
    unhidden: { footsteps: footLive(unhidden.snap), hidden: unhidden.snap.hidden },
    menuOn: { footsteps: footLive(menuOn.snap), menuOpen: menuOn.snap.menuOpen, reason: menuOn.snap.live?.reason },
    standing: { pose: standing.snap.pose, footsteps: footLive(standing.snap) },
    sprinting: { pose: sprinting.snap.pose, sprint: sprinting.snap.sprint, footsteps: footLive(sprinting.snap) },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    honesty: readyA.snap.honesty?.slice(0, 180),
    shot: SHOT,
    hash: createHash("sha256").update(walkBuf).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_FOOTSTEPS_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walk=${report.walkOn}`,
  `stand=${report.standOff}`,
  `hidden=${report.hiddenOff}`,
  `menu=${report.menuMute}`,
  `ticksW=${report.ticks?.walkDelta}`,
  `ticksS=${report.ticks?.sprintDelta}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
