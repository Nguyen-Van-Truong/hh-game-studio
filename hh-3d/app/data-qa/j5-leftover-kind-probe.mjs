/**
 * Isolated guest B on recycled 4175. Leftover kind chip must not
 * paint street-gold #ead8a8 / uppercase (leftover-panel CSS nit:
 * .approx won over .shop-panel-leftover-copy). Menu · gap and
 * leftover desc honesty still hold. Does not catalog_clear.
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
const OUT = join(import.meta.dirname, "J5-LEFTOVER-KIND-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-leftover-kind.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9795);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-45";
const SHARED = "shop-local-sharedpc";
const J6 = "shop-local-mtl8ulddihjpre";
const LEFTOVER_IDS = new Set([SHARED, J6]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const JAM = /Shared PC(?! · )không|PCkhông trên phố/i;
const GAP = / · không trên phố| · leftover máy này/;
const STREET_DESC = /Player-opened shop on this machine/i;

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const banner = document.querySelector('[data-testid="shop-leftover-banner"]');
  const desc = document.querySelector('[data-testid="shop-panel-desc"]');
  const kind = document.querySelector('[data-testid="shop-panel-kind"]');
  const kindStyle = kind ? window.getComputedStyle(kind) : null;
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const wrap = document.querySelector('[data-testid="hh-world-minimap-wrap"], .minimap-wrap');
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    leftover: el.getAttribute("data-leftover") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
  }));
  return {
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    bannerPresent: Boolean(banner),
    desc: (desc?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    kindBg: kindStyle?.backgroundColor ?? "",
    kindColor: kindStyle?.color ?? "",
    kindTransform: kindStyle?.textTransform ?? "",
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-leftover-kind-${port}-`));
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

const chrome = launchChrome(PORT, `${PLAYER}?seat=b`);
let report;
try {
  const b = await connectPage(PORT);
  await cdp(b.ws, 1, "Runtime.enable");
  await cdp(b.ws, 2, "Page.enable");
  await cdp(b.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const ready = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200,
    36,
    250,
  );
  let nextId = ready.nextId;
  await keyHold(b.ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(220);
  const spawnE = await evalExpr(b.ws, nextId, SNAP);
  nextId += 1;
  if (spawnE.shopPanel) {
    await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
    nextId += 1;
  }
  await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  nextId += 1;
  const menuOpen = await waitSnap(b.ws, nextId, (s) => s.menuOpen === true, 20, 180);
  nextId = menuOpen.nextId;
  const menuSnap = menuOpen.snap;
  const leftoverRows = (menuSnap.rows || []).filter(
    (row) => row.leftover === "1" || LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop),
  );
  const jammed = leftoverRows.filter((row) => JAM.test(row.text) || !GAP.test(row.text));
  const leftoverRow = leftoverRows.find((row) => row.shop === SHARED) || leftoverRows[0];
  let leftoverPanel = null;
  if (leftoverRow?.shop) {
    await evalExpr(
      b.ws,
      nextId,
      `document.querySelector('[data-testid="open-shop-${leftoverRow.shop}"]')?.click(); true`,
    );
    nextId += 1;
    const opened = await waitSnap(
      b.ws,
      nextId,
      (s) => s.shopPanel === true && s.shopPanelId === leftoverRow.shop,
      20,
      160,
    );
    nextId = opened.nextId;
    leftoverPanel = opened.snap;
  }
  const shot = await cdp(b.ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));
  const js = await liveJsInfo();
  const gapOk = leftoverRows.length >= 1 && jammed.length === 0;
  const descOk =
    leftoverPanel &&
    leftoverPanel.shopLeftover === "1" &&
    leftoverPanel.bannerPresent === true &&
    !STREET_DESC.test(leftoverPanel.desc || "") &&
    /không trên phố|leftover máy này/i.test(leftoverPanel.desc || "");
  const gold = /ead8a8|234,\s*216,\s*168/i;
  const kindMuted =
    leftoverPanel &&
    leftoverPanel.kindBg &&
    !gold.test(leftoverPanel.kindBg) &&
    leftoverPanel.kindTransform !== "uppercase";
  const spawnEStolen =
    Boolean(spawnE.shopPanel) && (LEFTOVER.test(spawnE.shopPanelId || "") || LEFTOVER_IDS.has(spawnE.shopPanelId));
  const ok = gapOk && descOk && kindMuted && !spawnEStolen;
  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_LEFTOVER_KIND_OK" : "J5_REWORK",
    not_plan_pass: true,
    reminted: true,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    gapOk,
    descOk,
    spawnEStolen,
    leftoverRows,
    jammed: jammed.map((row) => row.text),
    leftoverDesc: leftoverPanel?.desc ?? "",
    leftoverBanner: leftoverPanel?.bannerPresent ?? false,
    kindMuted: Boolean(kindMuted),
    leftoverKindBg: leftoverPanel?.kindBg ?? "",
    leftoverKindColor: leftoverPanel?.kindColor ?? "",
    leftoverKindTransform: leftoverPanel?.kindTransform ?? "",
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
        `kindBg=${leftoverPanel?.kindBg ?? ""}`,
        `kindTf=${leftoverPanel?.kindTransform ?? ""}`,
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
