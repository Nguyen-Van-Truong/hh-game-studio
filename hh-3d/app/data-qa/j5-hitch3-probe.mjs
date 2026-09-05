/**
 * First Harbor W: corner MapLibre stays pending during W and just after
 * keyup. Idle after the walk mounts it. Reports first-W rAF honestly.
 * Does not claim 60 / R2-WP1. Does not catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-HITCH3-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-hitch3.png");
const PORT = Number(process.env.HH_CDP_PORT || 9663);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-46";
const SAMPLE_MS = 3000;
const SETTLE_MS = 80;
const WARMUP_SKIP = 2;
const KEYUP_MS = 180;
const IDLE_WAIT_MS = 950;

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const wrap = document.querySelector('[data-testid="hh-world-minimap-wrap"], .minimap-wrap');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const worldMap = document.querySelector('[data-testid="hh-world-map"]');
  return {
    playReady: play?.getAttribute("data-play-ready") ?? "",
    hitchWarmup: play?.getAttribute("data-hitch-warmup") ?? proof?.getAttribute("data-hitch-warmup") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    chipText: (chip?.textContent ?? "").trim(),
    streetName: chip?.getAttribute("data-street-name") ?? play?.getAttribute("data-street-name") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    worldMapPresent: Boolean(worldMap),
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
    minimapDeferKind: wrap?.getAttribute("data-minimap-defer-kind") ?? "",
    minimapPresent: Boolean(mini),
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
        resolve({ dts, wallMs: now - started, n: dts.length });
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-hitch3-${port}-`));
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

function pending(snap) {
  return snap?.minimapPresent !== true && snap?.minimapDefer !== "live";
}

function liveMini(snap) {
  return snap?.minimapPresent === true && (snap?.minimapDefer === "live" || snap?.minimapDefer === "");
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
    (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200,
    40,
    200,
  );
  let nextId = ready.nextId;
  const spawn = ready.snap;
  await evalExpr(
    a.ws,
    nextId,
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
  nextId += 1;
  await sleep(SETTLE_MS);
  const beforeWalk = await evalExpr(a.ws, nextId, SNAP);
  nextId += 1;
  await keyDown(a.ws, nextId, "w", "KeyW", 87);
  nextId += 1;
  const walkRaw = await evalExpr(a.ws, nextId, SAMPLE_FN, true);
  nextId += 1;
  const midWalk = await evalExpr(a.ws, nextId, SNAP);
  nextId += 1;
  await keyUp(a.ws, nextId, "w", "KeyW", 87);
  nextId += 1;
  await sleep(KEYUP_MS);
  const afterKeyup = await evalExpr(a.ws, nextId, SNAP);
  nextId += 1;
  const walk = packSample(walkRaw);
  await sleep(IDLE_WAIT_MS);
  const afterIdle = await evalExpr(a.ws, nextId, SNAP);
  nextId += 1;
  const shot = await cdp(a.ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));
  const js = await liveJsInfo();
  const harborOk =
    beforeWalk.chipText === "Harbor Walk" ||
    beforeWalk.streetName === "Harbor Walk" ||
    spawn.chipText === "Harbor Walk" ||
    spawn.streetName === "Harbor Walk";
  const walked = midWalk.pose === "walk" || afterKeyup.lat !== beforeWalk.lat;
  const pendingThroughWalk = pending(beforeWalk) && pending(midWalk);
  const keyupStillPending = pending(afterKeyup);
  const idleMounted = liveMini(afterIdle);
  const kindOk = afterIdle.minimapDeferKind === "play-idle" || midWalk.minimapDeferKind === "play-idle";
  const noWorldMap = afterIdle.worldMapPresent !== true;
  const spawnEStolen = Boolean(spawn.shopPanel);
  const ok =
    harborOk &&
    walked &&
    walk.n > 40 &&
    pendingThroughWalk &&
    keyupStillPending &&
    idleMounted &&
    kindOk &&
    noWorldMap &&
    !spawnEStolen;
  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_HITCH3_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_r2_wp1: true,
    not_60_fps: true,
    reminted: true,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    harborOk,
    walked,
    pendingThroughWalk,
    keyupStillPending,
    idleMounted,
    kindOk,
    spawnEStolen,
    walk,
    walkMin: walk.fps.min,
    walkMean: walk.fps.mean,
    beforeWalk,
    midWalk,
    afterKeyup,
    afterIdle,
    hitchWarmup: spawn.hitchWarmup || beforeWalk.hitchWarmup || "",
    minimapDeferKind: afterIdle.minimapDeferKind || midWalk.minimapDeferKind || "",
    shot: SHOT,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    console.error(JSON.stringify(report, null, 2));
    process.exitCode = 1;
  } else {
    console.log(
      [
        report.verdict,
        js.path,
        `walkMin=${walk.fps.min}`,
        `walkMean=${walk.fps.mean}`,
        `keyupPending=${keyupStillPending}`,
        `idleLive=${idleMounted}`,
        `kind=${report.minimapDeferKind}`,
      ].join(" "),
    );
  }
} catch (err) {
  writeFileSync(
    OUT,
    `${JSON.stringify({ run_id: RUN_ID, verdict: "J5_REWORK", error: String(err) }, null, 2)}\n`,
  );
  console.error(err);
  process.exitCode = 1;
} finally {
  chrome.kill();
}
