/**
 * First Harbor W hitch on existing 4175. Do not start a preview.
 * After Play ready + short settle, hold W ~3 s and sample rAF min/mean.
 * Not a 60 / R2-WP1 claim. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-HITCH-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9641);
const RUN_ID = process.env.HH_RUN_ID || "HH3D-J5-20260904-ASIA-SAIGON-14";
const SAMPLE_MS = 3000;
const SETTLE_MS = Number(process.env.HH_SETTLE_MS || 400);
const WARMUP_SKIP = 2;

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
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const friend = document.querySelector('[data-testid="friend-footstep-proof"]');
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
    farLod: play?.getAttribute("data-far-lod") ?? proof?.getAttribute("data-far-lod") ?? "",
    farLodM: Number(play?.getAttribute("data-far-lod-m") ?? proof?.getAttribute("data-far-lod-m") ?? "0"),
    plaques: Number(proof?.getAttribute("data-street-plaques") ?? play?.getAttribute("data-street-plaques") ?? "0"),
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    friendLive: friend?.getAttribute("data-friend-footsteps") ?? "0",
    friendTicks: Number(friend?.getAttribute("data-friend-footstep-ticks") ?? "0"),
    remotes: Number(document.querySelector('[data-testid="play-remote-bodies"]')?.getAttribute("data-count") ?? "0"),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-hitch-${port}-`));
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

  await keyHoldish(a.ws, 110, "w", "KeyW", 87, 14500);
  await sleep(150);
  const atLantern = await evalExpr(a.ws, 180, SNAP);
  await keyDown(a.ws, 181, "e", "KeyE", 69);
  await sleep(180);
  await keyUp(a.ws, 182, "e", "KeyE", 69);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 190, SNAP);
  await evalExpr(a.ws, 191, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
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
  const keepOk = harborOk && walked && walk.n > 40 && lanternOk && friendOfflineClosed;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    viewport: "1280x720",
    method: `headless-new CDP first-W rAF wall-clock ${SAMPLE_MS}ms settle=${SETTLE_MS}ms skip=${WARMUP_SKIP}`,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    verdict: keepOk ? "J5_HITCH_OBSERVED" : "J5_REWORK",
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
    walk,
    spawn,
    beforeWalk: {
      pose: beforeWalk.pose,
      chip: beforeWalk.chipText,
      street: beforeWalk.streetName,
      lon: beforeWalk.lon,
      lat: beforeWalk.lat,
      hitchWarmup: beforeWalk.hitchWarmup,
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
      friendLive: afterWalk.friendLive,
      friendTicks: afterWalk.friendTicks,
      remotes: afterWalk.remotes,
    },
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    walkMin,
    walkMean,
    hitchWarmup: spawn.hitchWarmup || beforeWalk.hitchWarmup || "",
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
if (report.verdict !== "J5_HITCH_OBSERVED") {
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
  `pose=${report.midWalk?.pose}`,
  `lantern=${report.lantern?.panel}`,
  `friendOffline=${report.friendOfflineClosed}`,
  `warmup=${report.hitchWarmup || "none"}`,
  `js=${report.liveJs}`,
);
