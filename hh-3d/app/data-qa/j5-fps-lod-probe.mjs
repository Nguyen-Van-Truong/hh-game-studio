/**
 * Harbor idle + walk FPS on existing 4175. Do not start a preview.
 * rAF wall-clock ~3 s idle, then hold W ~3 s walk. Do not invent 60.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FPS-LOD-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9611);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-11";
const SAMPLE_MS = 3000;
const WARMUP_SKIP = 8;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function stats(values) {
  const s = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) {
    return { n: 0, min: null, median: null, p1: null, max: null, mean: null };
  }
  const q = (p) => {
    const idx = (n - 1) * p;
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return s[lo];
    return s[lo] + (s[hi] - s[lo]) * (idx - lo);
  };
  const mean = s.reduce((a, b) => a + b, 0) / n;
  return {
    n,
    min: Number(s[0].toFixed(2)),
    median: Number(q(0.5).toFixed(2)),
    p1: Number(q(0.01).toFixed(2)),
    max: Number(s[n - 1].toFixed(2)),
    mean: Number(mean.toFixed(2)),
  };
}

function fpsFromDts(dts) {
  return dts.map((dt) => (dt > 0 ? 1000 / dt : 0));
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

async function keyHoldish(ws, id, key, code, vk, ms) {
  await keyDown(ws, id, key, code, vk);
  await sleep(ms);
  await keyUp(ws, id + 1, key, code, vk);
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    engine: play?.getAttribute("data-engine") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    fog: proof?.getAttribute("data-fog") ?? "",
    groundFloor: proof?.getAttribute("data-ground-floor") ?? "",
    streetHud: play?.getAttribute("data-street-hud") ?? proof?.getAttribute("data-street-hud") ?? "",
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      "",
    chipText: (chip?.textContent ?? "").trim(),
    menuHidden: Boolean(menu?.hidden) || menu?.getAttribute("data-open") === "no",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    honesty: honesty?.innerText ?? "",
    farLod: play?.getAttribute("data-far-lod") ?? proof?.getAttribute("data-far-lod") ?? "",
    farLodM: Number(play?.getAttribute("data-far-lod-m") ?? proof?.getAttribute("data-far-lod-m") ?? "0"),
    farDrawnInner: Number(play?.getAttribute("data-far-lod-drawn-inner") ?? "0"),
    farDrawnScooters: Number(play?.getAttribute("data-far-lod-drawn-scooters") ?? "0"),
    plaques: Number(proof?.getAttribute("data-street-plaques") ?? play?.getAttribute("data-street-plaques") ?? "0"),
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    minimapActive: mini?.getAttribute("data-minimap-active") ?? "",
  };
})()`;

const SAMPLE_FN = `(() => {
  const sampleMs = ${SAMPLE_MS};
  const warmup = ${WARMUP_SKIP};
  return new Promise((resolve) => {
    const dts = [];
    let last = null;
    let started = null;
    let skipped = 0;
    const tick = (now) => {
      if (last == null) {
        last = now;
        requestAnimationFrame(tick);
        return;
      }
      const dt = now - last;
      last = now;
      if (skipped < warmup) {
        skipped += 1;
        requestAnimationFrame(tick);
        return;
      }
      if (started == null) started = now;
      dts.push(dt);
      if (now - started >= sampleMs) {
        resolve({
          dts,
          wallMs: now - started,
          n: dts.length,
        });
      } else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-fps-${port}-`));
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

async function waitSnap(ws, startId, pred, tries = 40, delay = 250) {
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

function packSample(raw) {
  const dts = Array.isArray(raw?.dts) ? raw.dts : [];
  const fps = fpsFromDts(dts);
  return {
    wallMs: Number((raw?.wallMs ?? 0).toFixed(1)),
    n: dts.length,
    frameMs: stats(dts),
    fps: stats(fps),
  };
}

const chrome = launchChrome(PORT, `${PLAYER}?seat=a`);
let report;
try {
  const a = await connectPage(PORT);
  await cdp(a.ws, 1, "Runtime.enable");
  await cdp(a.ws, 2, "Page.enable");
  await cdp(a.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });

  const ready = await waitSnap(
    a.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    40,
    250,
  );
  const spawn = ready.snap;

  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(1200);

  const beforeIdle = await evalExpr(a.ws, 90, SNAP);
  const idleRaw = await evalExpr(a.ws, 91, SAMPLE_FN, true);
  const afterIdle = await evalExpr(a.ws, 92, SNAP);
  const idle = packSample(idleRaw);

  await keyDown(a.ws, 100, "w", "KeyW", 87);
  const walkRaw = await evalExpr(a.ws, 101, SAMPLE_FN, true);
  const midWalk = await evalExpr(a.ws, 102, SNAP);
  await keyUp(a.ws, 103, "w", "KeyW", 87);
  await sleep(200);
  const afterWalk = await evalExpr(a.ws, 104, SNAP);
  const walk = packSample(walkRaw);
  const idleAfterWalkRaw = await evalExpr(a.ws, 105, SAMPLE_FN, true);
  const idleAfterWalkSnap = await evalExpr(a.ws, 106, SNAP);
  const idleAfterWalk = packSample(idleAfterWalkRaw);

  await keyHoldish(a.ws, 110, "w", "KeyW", 87, 10600);
  await sleep(120);
  await keyHoldish(a.ws, 120, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHoldish(a.ws, 130, "w", "KeyW", 87, 4500);
  await sleep(200);
  const onSteps = await evalExpr(a.ws, 140, SNAP);
  await keyHoldish(a.ws, 150, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHoldish(a.ws, 160, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHoldish(a.ws, 170, "w", "KeyW", 87, 5000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 180, SNAP);
  await keyDown(a.ws, 181, "e", "KeyE", 69);
  await sleep(180);
  await keyUp(a.ws, 182, "e", "KeyE", 69);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 190, SNAP);
  await evalExpr(a.ws, 191, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(200);

  const liveJs = await fetch(PLAYER).then(async (res) => {
    const html = await res.text();
    return /\/assets\/index-[^"']+\.js/.exec(html)?.[0] ?? "";
  });

  const idleMean = idle.fps.mean;
  const walkMean = walk.fps.mean;
  const reminted = process.env.HH_REMINTED === "1";
  const remintNeeded = walkMean != null && walkMean < 45;
  const idleOk = idleMean != null && idleMean >= 50;
  const walkOk = walkMean != null && walkMean >= 45;
  const harborOk =
    beforeIdle.chipText === "Harbor Walk" ||
    beforeIdle.streetName === "Harbor Walk" ||
    afterIdle.chipText === "Harbor Walk";
  const walked =
    midWalk.pose === "walk" || afterWalk.pose === "walk" || afterWalk.lat !== beforeIdle.lat;
  const stepsChip =
    onSteps.chipText === "Steps East" || onSteps.streetName === "Steps East";
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const lodOk = spawn.farLod === "inner-door-glass" && spawn.farLodM === 90;
  const plaquesOk = spawn.plaques >= 4;
  const keepOk = harborOk && walked && idle.n > 40 && walk.n > 40 && (reminted ? stepsChip && lanternOk : true);

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    viewport: "1280x720",
    method: "headless-new CDP rAF wall-clock 3000ms",
    liveJs,
    verdict: keepOk ? "J5_FPS_LOD_OBSERVED" : "J5_REWORK",
    remintNeeded,
    reminted,
    idleOk,
    walkOk,
    harborOk,
    walked,
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    idle,
    walk,
    idleAfterWalk,
    spawn,
    beforeIdle: {
      pose: beforeIdle.pose,
      chip: beforeIdle.chipText,
      street: beforeIdle.streetName,
      lon: beforeIdle.lon,
      lat: beforeIdle.lat,
    },
    afterIdle: {
      pose: afterIdle.pose,
      chip: afterIdle.chipText,
      lon: afterIdle.lon,
      lat: afterIdle.lat,
    },
    midWalk: {
      pose: midWalk.pose,
      chip: midWalk.chipText,
      lon: midWalk.lon,
      lat: midWalk.lat,
    },
    afterWalk: {
      pose: afterWalk.pose,
      chip: afterWalk.chipText,
      lon: afterWalk.lon,
      lat: afterWalk.lat,
    },
    afterSecondIdle: {
      pose: idleAfterWalkSnap.pose,
      chip: idleAfterWalkSnap.chipText,
      lon: idleAfterWalkSnap.lon,
      lat: idleAfterWalkSnap.lat,
    },
    onSteps: {
      pose: onSteps.pose,
      chip: onSteps.chipText,
      mini: onSteps.minimapActive,
      lon: onSteps.lon,
      lat: onSteps.lat,
    },
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    stepsChip,
    lanternOk,
    lodOk,
    plaquesOk,
    farLod: spawn.farLod,
    farLodM: spawn.farLodM,
    farDrawnInner: spawn.farDrawnInner,
    farDrawnScooters: spawn.farDrawnScooters,
    honesty: spawn.honesty?.slice(0, 240),
  };
  a.ws.close();
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_REWORK",
    remintNeeded: null,
    reminted: false,
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_FPS_LOD_OBSERVED") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `idleMean=${report.idle?.fps?.mean}`,
  `walkMean=${report.walk?.fps?.mean}`,
  `idle2Mean=${report.idleAfterWalk?.fps?.mean}`,
  `idleMed=${report.idle?.fps?.median}`,
  `walkMed=${report.walk?.fps?.median}`,
  `idle2Med=${report.idleAfterWalk?.fps?.median}`,
  `remintNeeded=${report.remintNeeded}`,
  `chip=${report.beforeIdle?.chip}`,
  `steps=${report.onSteps?.chip}`,
  `lantern=${report.lantern?.panel}`,
  `lod=${report.farLod}`,
  `poseWalk=${report.midWalk?.pose}`,
  `js=${report.liveJs}`,
);
