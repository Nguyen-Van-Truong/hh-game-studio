/**
 * Isolated seat on 4175. Slim connectivity pill only.
 * onLine=false → Mất kết nối; onLine=true → Đang kết nối lại then Đang kết nối.
 * Social Offline must not flip. Does not click Online or Simulate no-network.
 * Does not catalog_clear. Not a presence reconnect server. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-NET-RECONNECT-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9670);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-27";

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const hudPresence = document.querySelector('[data-testid="hud-presence"]');
  const hudConn = document.querySelector('[data-testid="hud-connection"]');
  const modeStatus = document.querySelector('[data-testid="mode-status"]');
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const mode = document.querySelector('[data-testid="presence-mode"]');
  const menuConn = document.querySelector('[data-testid="menu-connection"]');
  const online = document.querySelector('[data-testid="online-btn"]');
  const offline = document.querySelector('[data-testid="offline-btn"]');
  const cutBar = document.querySelector('[data-testid="network-cut-sim"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const hudBox = modeStatus ? modeStatus.getBoundingClientRect() : null;
  const hudConnBox = hudConn ? hudConn.getBoundingClientRect() : null;
  const chipBox = chip ? chip.getBoundingClientRect() : null;
  const onScreen = (box) =>
    Boolean(box && box.width > 8 && box.height > 8 && box.x > -8 && box.x < 1288 && box.y > -8 && box.y < 728);
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    streetName: chip?.getAttribute("data-street-name") ?? "",
    chipOnScreen: onScreen(chipBox),
    hudPresence: (hudPresence?.textContent ?? "").trim(),
    hudPresenceAttr: hudPresence?.getAttribute("data-presence") ?? "",
    hudConnection: (hudConn?.textContent ?? "").trim(),
    hudConnectionAttr: hudConn?.getAttribute("data-connection") ?? "",
    hudOnScreen: onScreen(hudBox),
    hudConnOnScreen: onScreen(hudConnBox),
    hudBox: hudBox
      ? { x: Number(hudBox.x.toFixed(1)), y: Number(hudBox.y.toFixed(1)), w: Number(hudBox.width.toFixed(1)), h: Number(hudBox.height.toFixed(1)) }
      : null,
    presenceMode: (mode?.textContent ?? "").trim(),
    menuConnection: (menuConn?.textContent ?? "").trim(),
    onlineActive: online?.getAttribute("data-active") ?? "",
    offlineActive: offline?.getAttribute("data-active") ?? "",
    networkCutBar: Boolean(cutBar?.checked),
    navOnline: navigator.onLine,
    menuOpen: document.querySelector('[data-testid="play-menu"]')?.getAttribute("data-open") ?? "",
    honesty: (honesty?.textContent ?? "").replace(/\\s+/g, " ").slice(0, 220),
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

async function liveJsInfo() {
  const liveHtml = await fetch(PLAYER).then((res) => res.text());
  const jsMatch = liveHtml.match(/\/assets\/index-[^"]+\.js/);
  const liveJs = jsMatch ? jsMatch[0] : "";
  let liveLen = 0;
  let liveSha = "";
  if (liveJs) {
    const jsRes = await fetch(new URL(liveJs, PLAYER));
    const buf = Buffer.from(await jsRes.arrayBuffer());
    liveLen = buf.length;
    liveSha = createHash("sha256").update(buf).digest("hex");
  }
  return { liveJs, liveLen, liveSha };
}

function socialUnchanged(snap) {
  return (
    snap.hudPresence === "Offline" &&
    snap.hudPresenceAttr === "offline" &&
    /Offline — Stroll alone/.test(snap.presenceMode || "") &&
    snap.offlineActive === "yes" &&
    snap.onlineActive === "no" &&
    snap.networkCutBar === false
  );
}

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${mkdtempSync(join(tmpdir(), "hh-world-j5-net-reconnect-"))}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let report;
try {
  const { ws } = await connectPage(PORT);
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Network.enable");
  await cdp(ws, 4, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(ws, 5, "Page.navigate", { url: `${PLAYER}?seat=a` });

  const ready = await waitSnap(
    ws,
    20,
    (s) =>
      s.playReady === "yes" &&
      s.buildings >= 20 &&
      s.hudPresence === "Offline" &&
      s.hudConnection === "Đang kết nối",
    48,
    250,
  );
  let nextId = ready.nextId;
  const onlineSnap = ready.snap;

  if (onlineSnap.menuOpen === "yes") {
    throw new Error("menu should start hidden so HUD labels are the walk chrome");
  }
  if (!onlineSnap.hudOnScreen || !onlineSnap.hudConnOnScreen) {
    throw new Error(`HUD labels not on screen ${JSON.stringify(onlineSnap.hudBox)}`);
  }
  if (!socialUnchanged(onlineSnap) || onlineSnap.navOnline !== true) {
    throw new Error(`spawn labels wrong ${JSON.stringify(onlineSnap)}`);
  }
  if (onlineSnap.hudConnection === "Đang kết nối lại") {
    throw new Error("first paint must not flash Đang kết nối lại");
  }
  if ((onlineSnap.hudBox?.h || 99) > 28) {
    throw new Error(`HUD line too fat ${JSON.stringify(onlineSnap.hudBox)}`);
  }

  await cdp(ws, nextId, "Network.emulateNetworkConditions", {
    offline: true,
    latency: 0,
    downloadThroughput: 0,
    uploadThroughput: 0,
    connectionType: "none",
  });
  nextId += 1;
  await evalExpr(
    ws,
    nextId,
    `(() => {
      if (navigator.onLine) {
        return { nav: navigator.onLine, dispatched: false };
      }
      window.dispatchEvent(new Event("offline"));
      return { nav: navigator.onLine, dispatched: true };
    })()`,
  );
  nextId += 1;
  const lost = await waitSnap(
    ws,
    nextId,
    (s) => s.navOnline === false && s.hudConnection === "Mất kết nối",
    24,
    200,
  );
  nextId = lost.nextId;

  if (!socialUnchanged(lost.snap)) {
    throw new Error(`lost-network flipped social ${JSON.stringify(lost.snap)}`);
  }
  if (lost.snap.hudConnection !== "Mất kết nối" || lost.snap.hudConnectionAttr !== "off") {
    throw new Error(`HUD connectivity did not become Mất kết nối ${JSON.stringify(lost.snap)}`);
  }
  if (lost.snap.networkCutBar) {
    throw new Error("checkbox sim was on; this slice must use navigator.onLine=false only");
  }
  if (lost.snap.menuOpen === "yes") {
    throw new Error("opening the menu is not required to show Mất kết nối");
  }

  await cdp(ws, nextId, "Network.emulateNetworkConditions", {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });
  nextId += 1;
  await evalExpr(ws, nextId, `window.dispatchEvent(new Event("online")); navigator.onLine`);
  nextId += 1;

  const restoreStarted = Date.now();
  let retrySnap = null;
  let settledSnap = null;
  let retryFirstMs = null;
  let retryLastMs = null;
  const samples = [];
  for (let i = 0; i < 40; i += 1) {
    const snap = await evalExpr(ws, nextId, SNAP);
    nextId += 1;
    const elapsed = Date.now() - restoreStarted;
    samples.push({
      ms: elapsed,
      hudConnection: snap.hudConnection,
      hudConnectionAttr: snap.hudConnectionAttr,
      hudPresence: snap.hudPresence,
      navOnline: snap.navOnline,
    });
    if (!socialUnchanged(snap)) {
      throw new Error(`restore flipped social ${JSON.stringify(snap)}`);
    }
    if (snap.hudConnection === "Đang kết nối lại") {
      if (retryFirstMs === null) {
        retryFirstMs = elapsed;
        retrySnap = snap;
      }
      retryLastMs = elapsed;
    }
    if (snap.hudConnection === "Đang kết nối" && retrySnap) {
      settledSnap = snap;
      break;
    }
    await sleep(40);
  }

  if (!retrySnap) {
    throw new Error(`did not catch Đang kết nối lại ${JSON.stringify(samples)}`);
  }
  if (!settledSnap) {
    const late = await waitSnap(
      ws,
      nextId,
      (s) => s.hudConnection === "Đang kết nối",
      20,
      100,
    );
    nextId = late.nextId;
    settledSnap = late.snap;
  }
  if (!settledSnap || settledSnap.hudConnection !== "Đang kết nối") {
    throw new Error(`did not settle on Đang kết nối ${JSON.stringify(samples)}`);
  }
  if (!socialUnchanged(settledSnap)) {
    throw new Error(`settle flipped social ${JSON.stringify(settledSnap)}`);
  }
  if (retrySnap.hudConnectionAttr !== "retry") {
    throw new Error(`retry attr missing ${JSON.stringify(retrySnap)}`);
  }
  const retryVisibleMs =
    retryLastMs !== null && retryFirstMs !== null ? retryLastMs - retryFirstMs + 40 : 0;

  const live = await liveJsInfo();
  const ok =
    socialUnchanged(onlineSnap) &&
    socialUnchanged(lost.snap) &&
    socialUnchanged(retrySnap) &&
    socialUnchanged(settledSnap) &&
    onlineSnap.hudConnection === "Đang kết nối" &&
    lost.snap.hudConnection === "Mất kết nối" &&
    retrySnap.hudConnection === "Đang kết nối lại" &&
    settledSnap.hudConnection === "Đang kết nối" &&
    lost.snap.navOnline === false &&
    settledSnap.navOnline === true;

  report = {
    runId: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_NET_RECONNECT_OK" : "J5_NET_RECONNECT_FAIL",
    live,
    online: {
      hudPresence: onlineSnap.hudPresence,
      hudConnection: onlineSnap.hudConnection,
      presenceMode: onlineSnap.presenceMode,
      menuOpen: onlineSnap.menuOpen,
      streetName: onlineSnap.streetName,
      hudBox: onlineSnap.hudBox,
      navOnline: onlineSnap.navOnline,
    },
    lost: {
      hudPresence: lost.snap.hudPresence,
      hudConnection: lost.snap.hudConnection,
      presenceMode: lost.snap.presenceMode,
      menuOpen: lost.snap.menuOpen,
      navOnline: lost.snap.navOnline,
      networkCutBar: lost.snap.networkCutBar,
    },
    retry: {
      hudPresence: retrySnap.hudPresence,
      hudConnection: retrySnap.hudConnection,
      hudConnectionAttr: retrySnap.hudConnectionAttr,
      presenceMode: retrySnap.presenceMode,
      menuOpen: retrySnap.menuOpen,
      firstMs: retryFirstMs,
      lastMs: retryLastMs,
      visibleMs: retryVisibleMs,
    },
    settled: {
      hudPresence: settledSnap.hudPresence,
      hudConnection: settledSnap.hudConnection,
      hudConnectionAttr: settledSnap.hudConnectionAttr,
      presenceMode: settledSnap.presenceMode,
      navOnline: settledSnap.navOnline,
    },
    samples,
    honesty: onlineSnap.honesty,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_NET_RECONNECT_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_NET_RECONNECT_OK",
      `hud=${onlineSnap.hudPresence}+${onlineSnap.hudConnection}`,
      `lost=${lost.snap.hudPresence}+${lost.snap.hudConnection}`,
      `retry=${retrySnap.hudPresence}+${retrySnap.hudConnection}`,
      `settled=${settledSnap.hudPresence}+${settledSnap.hudConnection}`,
      `retryMs=${retryVisibleMs}`,
      `js=${live.liveJs}`,
    ].join(" "),
  );
} finally {
  chrome.kill();
}
