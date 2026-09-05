/**
 * Quieter remote friend footsteps on recycled 4175.
 * Isolated A/B: add/accept/Online; A holds W; B plant count rises.
 * B stand / hidden = 0 friend plants. Offline A: B live=0, ticks/osc flat.
 * Leftover E not stolen. Chip / minimap / LOD kept. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-FRIEND-STEPS-2026-09-04.txt");
const PORTS = {
  a: Number(process.env.HH_CDP_PORT_A || 9541),
  b: Number(process.env.HH_CDP_PORT_B || 9542),
};
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-13";
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

async function keyDown(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function keyUp(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
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
  const friend = document.querySelector('[data-testid="friend-footstep-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const live = window.__hhFootsteps || null;
  const friendLive = window.__hhFriendFootsteps || null;
  const remotes = [...document.querySelectorAll("[data-remote-avatar]")].map((el) => ({
    seat: el.getAttribute("data-seat") ?? "",
    pose: el.getAttribute("data-pose") ?? "",
    friendSteps: el.getAttribute("data-friend-footsteps") ?? "",
    friendTicks: el.getAttribute("data-friend-footstep-ticks") ?? "",
  }));
  const remoteWalk = [...document.querySelectorAll("[data-testid^='remote-walk-cycle-']")].map((el) => ({
    seat: el.getAttribute("data-seat") ?? "",
    friendSteps: el.getAttribute("data-friend-footsteps") ?? "",
    friendTicks: el.getAttribute("data-friend-footstep-ticks") ?? "",
    reason: el.getAttribute("data-friend-footstep-reason") ?? "",
  }));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    hidden: document.hidden === true,
    menuOpen: menu?.getAttribute("data-open") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    scooters: proof?.getAttribute("data-scooters") ?? "",
    farLod: proof?.getAttribute("data-far-lod") ?? play?.getAttribute("data-far-lod") ?? "",
    farLodM: proof?.getAttribute("data-far-lod-m") ?? play?.getAttribute("data-far-lod-m") ?? "",
    plaques: proof?.getAttribute("data-street-plaques") ?? "",
    streetHud: proof?.getAttribute("data-street-hud") ?? "",
    streetName: chip?.getAttribute("data-street-name") ?? proof?.getAttribute("data-street-name") ?? "",
    chip: Boolean(chip),
    minimap: Boolean(mini),
    minimapLanes: mini?.getAttribute("data-minimap-lanes") ?? "",
    selfSteps: play?.getAttribute("data-footsteps") ?? steps?.getAttribute("data-footsteps") ?? "",
    selfTicks: live?.ticks ?? Number(steps?.getAttribute("data-footstep-ticks") ?? "0"),
    friendSteps:
      friend?.getAttribute("data-friend-footsteps") ??
      play?.getAttribute("data-friend-footsteps") ??
      "",
    friendTicks: Number(
      friendLive?.ticks ??
        friend?.getAttribute("data-friend-footstep-ticks") ??
        play?.getAttribute("data-friend-footstep-ticks") ??
        "0",
    ),
    friendMuted: friend?.getAttribute("data-friend-footstep-muted") ?? "",
    friendReason: friendLive?.reason ?? friend?.getAttribute("data-friend-footstep-reason") ?? "",
    friendGain: friendLive?.lastGain ?? Number(friend?.getAttribute("data-friend-footstep-gain") ?? "0"),
    friendDist: friendLive?.lastDistM ?? Number(friend?.getAttribute("data-friend-footstep-dist") ?? "0"),
    friendSeat: friendLive?.seat ?? friend?.getAttribute("data-friend-footstep-seat") ?? "",
    friendLive,
    osc: Number(window.__hhOscHook?.osc ?? 0),
    src: Number(window.__hhOscHook?.src ?? 0),
    remotes,
    remoteWalk,
    remoteCount: Number(document.querySelector('[data-testid="people-layer"]')?.getAttribute("data-remote-count") ?? "-1"),
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
    addB: Boolean(document.querySelector('[data-testid="add-friend-b"]')),
    offlineActive:
      document.querySelector('[data-testid="offline-btn"]')?.getAttribute("data-active") ?? "",
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    gtaClaim:
      /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
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

const HOOK_OSC = `(() => {
  if (window.__hhOscHook) return window.__hhOscHook;
  const hook = { osc: 0, src: 0 };
  const wrap = (Ctor, key) => {
    const proto = Ctor && Ctor.prototype;
    if (!proto || typeof proto.start !== "function") return;
    const orig = proto.start;
    proto.start = function (...args) {
      hook[key] += 1;
      return orig.apply(this, args);
    };
  };
  wrap(window.OscillatorNode, "osc");
  wrap(window.AudioBufferSourceNode, "src");
  window.__hhOscHook = hook;
  return hook;
})()`;

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-fsteps-${port}-`));
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

function friendTicksOf(snap) {
  const n = Number(snap?.friendTicks);
  return Number.isFinite(n) ? n : 0;
}

function friendLiveOf(snap) {
  return String(snap?.friendSteps ?? "") === "1";
}

function remoteA(snap) {
  return (
    snap?.remotes?.find((row) => row.seat === "a") ??
    snap?.remoteWalk?.find((row) => row.seat === "a") ??
    null
  );
}

function notRising(vals) {
  if (!vals.length) {
    return false;
  }
  for (let i = 1; i < vals.length; i += 1) {
    if (vals[i] > vals[i - 1]) {
      return false;
    }
  }
  return true;
}

function allEqual(vals) {
  return vals.length > 0 && Math.max(...vals) === Math.min(...vals);
}

async function resetBus() {
  const origin = PLAYER.replace(/\/$/, "");
  await fetch(`${origin}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      graph_clear: true,
      leave: "a",
    }),
  });
  await fetch(`${origin}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      leave: "b",
    }),
  });
}

const chromes = [];
let report;
try {
  await resetBus();
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
  await sleep(500);
  const origin = PLAYER.replace(/\/$/, "");
  for (const [ws, seat, base] of [
    [a.ws, "a", 10],
    [b.ws, "b", 10],
  ]) {
    await cdp(ws, base, "Storage.clearDataForOrigin", {
      origin,
      storageTypes: "local_storage",
    });
    await cdp(ws, base + 1, "Page.navigate", { url: `${PLAYER}?seat=${seat}` });
  }

  const readyA = await waitSnap(
    a.ws,
    20,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );
  const readyB = await waitSnap(
    b.ws,
    20,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );

  const leftoverSpawn =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";

  await evalExpr(b.ws, 39, HOOK_OSC);
  const standB0 = await evalExpr(b.ws, 40, SNAP);

  await evalExpr(a.ws, 41, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 41, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, 42, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  await waitSnap(b.ws, 42, (s) => s.acceptA === true, 16, 250);
  await evalExpr(b.ws, 50, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  await evalExpr(a.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(b.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(a.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);

  const friendsB = await waitSnap(
    b.ws,
    60,
    (s) => Boolean(remoteA(s)) && s.remoteCount >= 1,
    36,
    250,
  );

  const standFriends = await evalExpr(b.ws, 100, SNAP);

  await evalExpr(
    a.ws,
    101,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await evalExpr(b.ws, 101, `document.body.click(); true`);
  await sleep(80);
  await keyDown(a.ws, 102, "w", "KeyW", 87);
  const walkingB = await waitSnap(
    b.ws,
    110,
    (s) => friendLiveOf(s) && friendTicksOf(s) >= 1 && remoteA(s)?.pose === "walk",
    36,
    80,
  );
  const ticksAtWalk = friendTicksOf(walkingB.snap);
  await sleep(1100);
  const walkHeld = await evalExpr(b.ws, 160, SNAP);
  const ticksWalk = friendTicksOf(walkHeld);
  const selfWhileFriend = walkHeld.selfSteps;
  await keyUp(a.ws, 161, "w", "KeyW", 87);
  await sleep(2300);
  const afterStop = await waitSnap(
    b.ws,
    170,
    (s) => !friendLiveOf(s),
    20,
    120,
  );

  await keyDown(a.ws, 200, "w", "KeyW", 87);
  const walkingAgain = await waitSnap(b.ws, 201, (s) => friendLiveOf(s), 24, 80);
  await evalExpr(
    b.ws,
    230,
    `(() => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
      document.dispatchEvent(new Event("visibilitychange"));
      return document.hidden;
    })()`,
  );
  const hidden = await waitSnap(
    b.ws,
    231,
    (s) => !friendLiveOf(s) && s.hidden === true,
    20,
    80,
  );
  const hiddenTicks0 = friendTicksOf(hidden.snap);
  await sleep(900);
  const hiddenHeld = await evalExpr(b.ws, 260, SNAP);
  const hiddenTicks1 = friendTicksOf(hiddenHeld);
  await evalExpr(
    b.ws,
    270,
    `(() => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
      document.dispatchEvent(new Event("visibilitychange"));
      return document.hidden;
    })()`,
  );
  const unhidden = await waitSnap(
    b.ws,
    271,
    (s) => friendLiveOf(s) && s.hidden === false,
    20,
    80,
  );
  const unhiddenTicks0 = friendTicksOf(unhidden.snap);
  await sleep(900);
  const unhiddenHeld = await evalExpr(b.ws, 300, SNAP);
  const unhiddenTicks1 = friendTicksOf(unhiddenHeld);
  await keyUp(a.ws, 301, "w", "KeyW", 87);
  await sleep(400);

  await evalExpr(a.ws, 310, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(120);
  await evalExpr(a.ws, 311, `document.querySelector('[data-testid="offline-btn"]')?.click(); true`);
  await sleep(80);
  await evalExpr(a.ws, 312, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(
    a.ws,
    313,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );

  const offlineTeardown = [];
  let offlineId = 320;
  for (let i = 0; i < 14; i += 1) {
    offlineTeardown.push(await evalExpr(b.ws, offlineId, SNAP));
    offlineId += 1;
    await sleep(70);
  }
  const firstZeroRemote = offlineTeardown.findIndex((s) => Number(s.remoteCount) === 0);
  const afterZero = firstZeroRemote >= 0 ? offlineTeardown.slice(firstZeroRemote) : offlineTeardown;
  const teardownLiveOff = afterZero.every((s) => !friendLiveOf(s));
  const teardownTicks = afterZero.map((s) => friendTicksOf(s));
  const teardownOsc = afterZero.map((s) => Number(s.osc || 0));
  const teardownTicksFlat = notRising(teardownTicks);
  const teardownOscFlat = allEqual(teardownOsc);
  const teardownLayerZero = afterZero.every((s) => Number(s.remoteCount) === 0);

  await keyDown(a.ws, 400, "w", "KeyW", 87);
  const offlineWalk = [];
  let walkId = 410;
  for (let i = 0; i < 10; i += 1) {
    offlineWalk.push(await evalExpr(b.ws, walkId, SNAP));
    walkId += 1;
    await sleep(120);
  }
  await keyUp(a.ws, 430, "w", "KeyW", 87);
  const offlineWalkLiveOff = offlineWalk.every((s) => !friendLiveOf(s));
  const offlineWalkTicks = offlineWalk.map((s) => friendTicksOf(s));
  const offlineWalkOsc = offlineWalk.map((s) => Number(s.osc || 0));
  const offlineWalkTicksFlat = allEqual(offlineWalkTicks) && notRising(offlineWalkTicks);
  const offlineWalkOscFlat = allEqual(offlineWalkOsc);
  const offlineWalkLayerZero = offlineWalk.every((s) => Number(s.remoteCount) === 0);
  const offlineCut =
    firstZeroRemote >= 0 &&
    teardownLiveOff &&
    teardownTicksFlat &&
    teardownOscFlat &&
    teardownLayerZero &&
    offlineWalkLiveOff &&
    offlineWalkTicksFlat &&
    offlineWalkOscFlat &&
    offlineWalkLayerZero;

  await evalExpr(a.ws, 440, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(80);
  await evalExpr(a.ws, 441, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await sleep(80);
  await evalExpr(a.ws, 442, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(200);

  await keyHold(a.ws, 450, "w", "KeyW", 87, 18000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 500, SNAP);
  await keyHold(a.ws, 501, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 510, SNAP);

  const leftoverBLive = await evalExpr(b.ws, 520, SNAP);
  await keyHold(b.ws, 521, "e", "KeyE", 69, 180);
  await sleep(250);
  const bAfterE = await evalExpr(b.ws, 530, SNAP);
  const leftoverEStolen = Boolean(bAfterE.shopPanel) && LEFTOVER.test(bAfterE.shopPanelId || "");

  const keptOk =
    readyA.snap.chip === true &&
    readyA.snap.minimap === true &&
    readyA.snap.farLod === "inner-door-glass" &&
    String(readyA.snap.farLodM) === "90" &&
    Number(readyA.snap.plaques) === 4 &&
    readyA.snap.streetHud === "named-chip" &&
    readyA.snap.sky === "gradient-hemisphere" &&
    readyA.snap.walkCycle === "opposite-stride";

  const standZero =
    !friendLiveOf(standB0) &&
    friendTicksOf(standB0) === 0 &&
    !friendLiveOf(standFriends) &&
    friendTicksOf(standFriends) === 0;
  const walkRise = friendLiveOf(walkingB.snap) && ticksWalk - ticksAtWalk >= 2;
  const quieter =
    Number(walkHeld.friendGain) > 0 && Number(walkHeld.friendGain) < 0.14;
  const nearby =
    Number(walkHeld.friendDist) > 0 && Number(walkHeld.friendDist) <= 25;
  const bSelfQuiet = selfWhileFriend !== "1";
  const stopOff = !friendLiveOf(afterStop.snap);
  const hiddenOff = !friendLiveOf(hidden.snap) && hidden.snap.hidden === true;
  const hiddenFrozen = hiddenTicks1 - hiddenTicks0 === 0;
  const unhiddenOn = friendLiveOf(unhidden.snap);
  const unhiddenRise = unhiddenTicks1 - unhiddenTicks0 >= 1;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const leftoverOk = leftoverSpawn && leftoverBLive && !leftoverEStolen && !bAfterE.shopPanel;
  const leftoverStill =
    leftoverBLive &&
    !LEFTOVER.test(leftoverBLive.nearbyShop || "") &&
    leftoverBLive.nearbyShop !== "shop-local-sharedpc";
  const honestyOk =
    /Authored approximation/.test(readyA.snap.honesty) &&
    /not a digital twin/i.test(readyA.snap.honesty) &&
    /NOT_PLAN_PASS/.test(readyA.snap.honesty) &&
    readyA.snap.gtaClaim === false;
  const friendsOn = Boolean(remoteA(friendsB.snap)) && friendsB.snap.remoteCount >= 1;

  const ok =
    walkRise &&
    standZero &&
    quieter &&
    nearby &&
    bSelfQuiet &&
    stopOff &&
    hiddenOff &&
    hiddenFrozen &&
    unhiddenOn &&
    unhiddenRise &&
    lanternOk &&
    leftoverOk &&
    leftoverStill &&
    honestyOk &&
    keptOk &&
    friendsOn &&
    offlineCut;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_FRIEND_STEPS_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    walkRise,
    standZero,
    quieter,
    nearby,
    bSelfQuiet,
    stopOff,
    hiddenOff,
    hiddenFrozen,
    unhiddenOn,
    unhiddenRise,
    lanternOk,
    leftoverOk,
    leftoverStill,
    honestyOk,
    keptOk,
    friendsOn,
    offlineCut,
    ticks: {
      stand0: friendTicksOf(standB0),
      standFriends: friendTicksOf(standFriends),
      walkStart: ticksAtWalk,
      walkHeld: ticksWalk,
      walkDelta: ticksWalk - ticksAtWalk,
      hidden0: hiddenTicks0,
      hidden1: hiddenTicks1,
      hiddenDelta: hiddenTicks1 - hiddenTicks0,
      unhidden0: unhiddenTicks0,
      unhidden1: unhiddenTicks1,
      unhiddenDelta: unhiddenTicks1 - unhiddenTicks0,
      walkGain: walkHeld.friendGain,
      walkDist: walkHeld.friendDist,
      walkSeat: walkHeld.friendSeat,
    },
    standB0: {
      pose: standB0.pose,
      friendSteps: standB0.friendSteps,
      friendTicks: friendTicksOf(standB0),
    },
    walking: {
      friendSteps: walkHeld.friendSteps,
      friendTicks: ticksWalk,
      remotePose: remoteA(walkHeld)?.pose,
      selfSteps: walkHeld.selfSteps,
      gain: walkHeld.friendGain,
      dist: walkHeld.friendDist,
    },
    hidden: {
      friendSteps: hiddenHeld.friendSteps,
      hidden: hiddenHeld.hidden,
      reason: hiddenHeld.friendReason,
      ticks: hiddenTicks1,
    },
    offline: {
      firstZeroRemote,
      teardown: afterZero.slice(0, 6).map((s) => ({
        remotes: s.remoteCount,
        live: s.friendSteps,
        ticks: friendTicksOf(s),
        osc: s.osc,
        src: s.src,
        reason: s.friendReason,
        remoteA: Boolean(remoteA(s)),
      })),
      walk: offlineWalk.slice(0, 6).map((s) => ({
        remotes: s.remoteCount,
        live: s.friendSteps,
        ticks: friendTicksOf(s),
        osc: s.osc,
        src: s.src,
        reason: s.friendReason,
        remoteA: Boolean(remoteA(s)),
      })),
      teardownLiveOff,
      teardownTicksFlat,
      teardownOscFlat,
      walkLiveOff: offlineWalkLiveOff,
      walkTicksFlat: offlineWalkTicksFlat,
      walkOscFlat: offlineWalkOscFlat,
    },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterWalkNearby: leftoverBLive.nearbyShop,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    kept: {
      chip: readyA.snap.chip,
      minimap: readyA.snap.minimap,
      farLod: readyA.snap.farLod,
      farLodM: readyA.snap.farLodM,
      plaques: readyA.snap.plaques,
      streetHud: readyA.snap.streetHud,
      streetName: readyA.snap.streetName,
    },
    honesty: readyA.snap.honesty?.slice(0, 180),
    hash: createHash("sha256").update(JSON.stringify(walkHeld)).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_FRIEND_STEPS_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walk=+${report.ticks?.walkDelta}`,
  `stand=${report.standZero}`,
  `hidden=${report.hiddenFrozen}`,
  `gain=${report.ticks?.walkGain}`,
  `offline=${report.offlineCut}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
