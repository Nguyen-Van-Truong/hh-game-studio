/**
 * First Harbor W after deferred corner MapLibre. Also checks chip+minimap
 * Harbor → Steps East. Do not start a preview. Not 60 / R2-WP1. NOT_PLAN_PASS.
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
const OUT = process.env.HH_OUT || join(import.meta.dirname, "J5-HITCH2-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9661);
const RUN_ID = process.env.HH_RUN_ID || "HH3D-J5-20260904-ASIA-SAIGON-16";
const SAMPLE_MS = 3000;
const SETTLE_MS = Number(process.env.HH_SETTLE_MS || 400);
const WARMUP_SKIP = 2;
const M_PER_DEG_LAT = 111320;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

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
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const friend = document.querySelector('[data-testid="friend-footstep-proof"]');
  const worldMap = document.querySelector('[data-testid="hh-world-map"]');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const wrap = document.querySelector(".minimap-wrap");
  const miniItems = [...document.querySelectorAll('[data-testid="hh-world-minimap-lanes"] li')].map((el) => ({
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
    role: el.getAttribute("data-role") ?? "",
    active: el.getAttribute("data-active") ?? "",
  }));
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    hitchWarmup: play?.getAttribute("data-hitch-warmup") ?? proof?.getAttribute("data-hitch-warmup") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      "",
    chipText: (chip?.textContent ?? "").trim(),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    worldMapPresent: Boolean(worldMap),
    farLod: play?.getAttribute("data-far-lod") ?? proof?.getAttribute("data-far-lod") ?? "",
    farLodM: Number(play?.getAttribute("data-far-lod-m") ?? proof?.getAttribute("data-far-lod-m") ?? "0"),
    plaques: Number(proof?.getAttribute("data-street-plaques") ?? play?.getAttribute("data-street-plaques") ?? "0"),
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    friendLive: friend?.getAttribute("data-friend-footsteps") ?? "0",
    friendTicks: Number(friend?.getAttribute("data-friend-footstep-ticks") ?? "0"),
    remotes: Number(document.querySelector('[data-testid="play-remote-bodies"]')?.getAttribute("data-count") ?? "0"),
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
    minimapDeferKind: wrap?.getAttribute("data-minimap-defer-kind") ?? "",
    minimap: {
      present: Boolean(mini),
      kind: mini?.getAttribute("data-minimap-lanes") ?? "",
      official: Number(mini?.getAttribute("data-minimap-official") ?? "0"),
      inner: Number(mini?.getAttribute("data-minimap-inner") ?? "0"),
      extra: Number(mini?.getAttribute("data-minimap-extra") ?? "0"),
      names: mini?.getAttribute("data-minimap-names") ?? "",
      active: mini?.getAttribute("data-minimap-active") ?? "",
      highlight: mini?.getAttribute("data-minimap-highlight") ?? "",
      activeRole: mini?.getAttribute("data-minimap-active-role") ?? "",
    },
    miniActiveItem: miniItems.find((row) => row.active === "1") ?? null,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-hitch2-${port}-`));
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

async function liveJsInfo() {
  const html = await fetch(PLAYER).then((res) => res.text());
  const path = /\/assets\/index-[^"']+\.js/.exec(html)?.[0] ?? "";
  if (!path) {
    return { path: "", len: 0, sha256: "" };
  }
  const buf = Buffer.from(await fetch(new URL(path, PLAYER)).then((res) => res.arrayBuffer()));
  return {
    path,
    len: buf.length,
    sha256: createHash("sha256").update(buf).digest("hex"),
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
      const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
      if (canvas instanceof HTMLElement) {
        canvas.focus();
        canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));
      }
      document.body.click();
      return true;
    })()`,
  );
  await sleep(SETTLE_MS);

  const beforeWalk = await evalExpr(a.ws, 90, SNAP);
  await keyDown(a.ws, 100, "w", "KeyW", 87);
  const walkRaw = await evalExpr(a.ws, 101, SAMPLE_FN, true);
  const midWalk = await evalExpr(a.ws, 102, SNAP);
  await keyUp(a.ws, 103, "w", "KeyW", 87);
  await sleep(180);
  const afterWalk = await evalExpr(a.ws, 104, SNAP);
  const walk = packSample(walkRaw);

  const miniReady = await waitSnap(
    a.ws,
    200,
    (s) => s.minimap?.present === true && (s.minimapDefer === "" || s.minimapDefer === "live"),
    32,
    200,
  );
  const onHarborMini = miniReady.snap;

  await keyHoldish(a.ws, 240, "w", "KeyW", 87, 11000);
  await sleep(120);
  await keyHoldish(a.ws, 250, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHoldish(a.ws, 260, "w", "KeyW", 87, 4500);
  await sleep(200);
  const onSteps = await evalExpr(a.ws, 280, SNAP);

  await keyHoldish(a.ws, 290, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHoldish(a.ws, 300, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHoldish(a.ws, 310, "w", "KeyW", 87, 5000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 330, SNAP);
  await keyDown(a.ws, 331, "e", "KeyE", 69);
  await sleep(180);
  await keyUp(a.ws, 332, "e", "KeyE", 69);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 340, SNAP);
  await evalExpr(a.ws, 341, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(160);

  const js = await liveJsInfo();
  const walkMean = walk.fps.mean;
  const walkMin = walk.fps.min;
  const harborOk =
    beforeWalk.chipText === "Harbor Walk" ||
    beforeWalk.streetName === "Harbor Walk" ||
    spawn.chipText === "Harbor Walk" ||
    spawn.streetName === "Harbor Walk";
  const walked =
    midWalk.pose === "walk" || afterWalk.pose === "walk" || afterWalk.lat !== beforeWalk.lat;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const friendOfflineClosed =
    Number(afterWalk.remotes ?? 0) === 0 &&
    String(afterWalk.friendLive ?? "0") === "0" &&
    Number(afterWalk.friendTicks ?? 0) === 0;
  const eastM = (onSteps.lon - spawn.lon) * metersPerDegLon((onSteps.lat + spawn.lat) / 2);
  const northM = (onSteps.lat - spawn.lat) * M_PER_DEG_LAT;
  const miniHarbor =
    onHarborMini.minimap?.present === true &&
    onHarborMini.minimap?.active === "Harbor Walk" &&
    (onHarborMini.chipText === "Harbor Walk" || onHarborMini.streetName === "Harbor Walk") &&
    onHarborMini.worldMapPresent === false;
  const miniSteps =
    onSteps.minimap?.present === true &&
    onSteps.minimap?.active === "Steps East" &&
    (onSteps.chipText === "Steps East" || onSteps.streetName === "Steps East") &&
    onSteps.minimap?.highlight === "1" &&
    onSteps.chipText === onSteps.minimap?.active;
  const keepOk = harborOk && walked && walk.n > 40 && lanternOk && friendOfflineClosed && miniHarbor && miniSteps;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    viewport: "1280x720",
    method: `headless-new CDP first-W rAF wall-clock ${SAMPLE_MS}ms settle=${SETTLE_MS}ms skip=${WARMUP_SKIP}`,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    verdict: keepOk ? "J5_HITCH2_OBSERVED" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_r2_wp1: true,
    not_60_fps: true,
    not_osm: true,
    not_wan: true,
    harborOk,
    walked,
    lanternOk,
    friendOfflineClosed,
    miniHarbor,
    miniSteps,
    walk,
    spawn,
    beforeWalk: {
      pose: beforeWalk.pose,
      chip: beforeWalk.chipText,
      street: beforeWalk.streetName,
      lon: beforeWalk.lon,
      lat: beforeWalk.lat,
      hitchWarmup: beforeWalk.hitchWarmup,
      minimapPresent: beforeWalk.minimap?.present ?? false,
      minimapDefer: beforeWalk.minimapDefer,
    },
    midWalk: {
      pose: midWalk.pose,
      chip: midWalk.chipText,
      lon: midWalk.lon,
      lat: midWalk.lat,
      minimapPresent: midWalk.minimap?.present ?? false,
      minimapDefer: midWalk.minimapDefer,
    },
    afterWalk: {
      pose: afterWalk.pose,
      chip: afterWalk.chipText,
      lon: afterWalk.lon,
      lat: afterWalk.lat,
      friendLive: afterWalk.friendLive,
      friendTicks: afterWalk.friendTicks,
      remotes: afterWalk.remotes,
      minimapPresent: afterWalk.minimap?.present ?? false,
      minimapDefer: afterWalk.minimapDefer,
    },
    harborMini: {
      chip: onHarborMini.chipText,
      active: onHarborMini.minimap?.active,
      defer: onHarborMini.minimapDefer,
      present: onHarborMini.minimap?.present,
    },
    steps: {
      chip: onSteps.chipText,
      active: onSteps.minimap?.active,
      highlight: onSteps.minimap?.highlight,
      role: onSteps.minimap?.activeRole,
      eastM: Number(eastM.toFixed(2)),
      northM: Number(northM.toFixed(2)),
    },
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    walkMin,
    walkMean,
    hitchWarmup: spawn.hitchWarmup || beforeWalk.hitchWarmup || "",
    minimapDeferKind: onHarborMini.minimapDeferKind || afterWalk.minimapDeferKind || "",
  };
  a.ws.close();
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
if (report.verdict !== "J5_HITCH2_OBSERVED") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walkMin=${report.walkMin}`,
  `walkMean=${report.walkMean}`,
  `walkN=${report.walk?.n}`,
  `chip=${report.beforeWalk?.chip}`,
  `miniSteps=${report.steps?.active}`,
  `lantern=${report.lantern?.panel}`,
  `friendOffline=${report.friendOfflineClosed}`,
  `defer=${report.minimapDeferKind || "none"}`,
  `js=${report.liveJs}`,
);
