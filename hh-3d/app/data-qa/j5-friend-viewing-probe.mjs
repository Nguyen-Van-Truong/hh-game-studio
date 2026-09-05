/**
 * Isolated seats A+B on recycled 4175. After they are accepted Online,
 * B sees A's street body. A opens lantern shelf; B must lose that body
 * and see “Đang xem cửa hàng” + shop-lantern-fish. Close shelf: body
 * returns. Does not catalog_clear. Local demo-bus only. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-FRIEND-VIEWING-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-friend-viewing.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9781), b: Number(process.env.HH_CDP_PORT_B || 9783) };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-43";
const LANTERN = "shop-lantern-fish";
const VIEWING = /Đang xem cửa hàng/;

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
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const people = document.querySelector('[data-testid="people-layer"]');
  const rowA = document.querySelector('[data-testid="people-row-a"]');
  const bodies = document.querySelector('[data-testid="play-remote-bodies"]');
  const viewing = document.querySelector('[data-testid="play-remote-viewing"]');
  const viewingA = document.querySelector('[data-testid="remote-viewing-a"]');
  const bodyA = document.querySelector('[data-testid="remote-body-a"]');
  const labelA = document.querySelector('[data-testid="remote-avatar-a"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  return {
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    remoteCount: Number(people?.getAttribute("data-remote-count") ?? "-1"),
    streetCount: Number(people?.getAttribute("data-street-count") ?? "-1"),
    viewingCount: Number(people?.getAttribute("data-viewing-count") ?? "-1"),
    peopleText: (people?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    rowA: rowA
      ? {
          street: rowA.getAttribute("data-street") ?? "",
          shop: rowA.getAttribute("data-viewing-shop") ?? "",
          text: (rowA.textContent ?? "").replace(/\\s+/g, " ").trim(),
        }
      : null,
    bodyCount: Number(bodies?.getAttribute("data-count") ?? "-1"),
    viewingListCount: Number(viewing?.getAttribute("data-count") ?? "-1"),
    bodyA: Boolean(bodyA),
    labelA: Boolean(labelA),
    viewingA: viewingA
      ? {
          shop: viewingA.getAttribute("data-shop") ?? "",
          street: viewingA.getAttribute("data-street") ?? "",
          text: (viewingA.textContent ?? "").trim(),
        }
      : null,
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
    addB: Boolean(document.querySelector('[data-testid="add-friend-b"]')),
    honesty: honesty?.innerText ?? "",
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-friend-viewing-${port}-`));
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

async function waitSnap(ws, startId, pred, tries = 28, delay = 280) {
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

async function resetFriendsOnly() {
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
  await resetFriendsOnly();
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
  const readyA = await waitSnap(a.ws, 20, (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200, 32, 250);
  const readyB = await waitSnap(b.ws, 20, (s) => s.playReady === "yes" && s.canvas && s.canvas.w >= 200, 32, 250);
  let nextA = readyA.nextId;
  let nextB = readyB.nextId;

  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  nextA += 1;
  await evalExpr(b.ws, nextB, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  nextB += 1;
  await sleep(200);
  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  nextA += 1;
  const acceptReady = await waitSnap(b.ws, nextB, (s) => s.acceptA === true, 16, 250);
  nextB = acceptReady.nextId;
  await evalExpr(b.ws, nextB, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  nextB += 1;
  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  nextA += 1;
  await evalExpr(b.ws, nextB, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  nextB += 1;

  const streetB = await waitSnap(b.ws, nextB, (s) => s.bodyA === true && s.streetCount >= 1, 36, 280);
  nextB = streetB.nextId;
  const before = streetB.snap;

  await evalExpr(
    a.ws,
    nextA,
    `(() => {
      const btn = document.querySelector('[data-testid="open-shop-${LANTERN}"]');
      if (btn) { btn.click(); return { ok: true }; }
      return { ok: false };
    })()`,
  );
  nextA += 1;
  const aOpen = await waitSnap(a.ws, nextA, (s) => s.shopPanelId === LANTERN, 20, 180);
  nextA = aOpen.nextId;

  const viewingB = await waitSnap(
    b.ws,
    nextB,
    (s) =>
      s.bodyA === false &&
      s.viewingA?.shop === LANTERN &&
      s.rowA?.street === "0" &&
      VIEWING.test(s.rowA?.text ?? "") &&
      VIEWING.test(s.peopleText ?? ""),
    36,
    280,
  );
  nextB = viewingB.nextId;
  const during = viewingB.snap;

  const shot = await cdp(b.ws, nextB, "Page.captureScreenshot", { format: "png" });
  nextB += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  nextA += 1;
  const afterB = await waitSnap(b.ws, nextB, (s) => s.bodyA === true && !s.viewingA, 36, 280);
  nextB = afterB.nextId;
  const after = afterB.snap;

  const js = await liveJsInfo();
  const streetBefore = before.bodyA === true && before.streetCount >= 1 && before.viewingCount <= 0;
  const viewingOk =
    during.bodyA === false &&
    during.labelA === false &&
    during.viewingA?.shop === LANTERN &&
    during.viewingA?.street === "0" &&
    during.rowA?.street === "0" &&
    during.rowA?.shop === LANTERN &&
    VIEWING.test(during.rowA?.text ?? "") &&
    VIEWING.test(during.peopleText ?? "") &&
    during.streetCount === 0 &&
    during.viewingCount >= 1 &&
    aOpen.snap.shopPanelId === LANTERN &&
    aOpen.snap.shopLeftover !== "1";
  const backOk = after.bodyA === true && !after.viewingA && after.streetCount >= 1;
  const honestyOk = /not a digital twin|not osm|not a live/i.test(during.honesty || before.honesty || "");
  const ok = streetBefore && viewingOk && backOk && honestyOk;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_FRIEND_VIEWING_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m2: true,
    reminted: true,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    streetBefore,
    viewingOk,
    backOk,
    honestyOk,
    before: {
      bodyA: before.bodyA,
      streetCount: before.streetCount,
      viewingCount: before.viewingCount,
    },
    during: {
      bodyA: during.bodyA,
      labelA: during.labelA,
      streetCount: during.streetCount,
      viewingCount: during.viewingCount,
      viewingA: during.viewingA,
      rowA: during.rowA,
      peopleText: during.peopleText,
      aPanel: aOpen.snap.shopPanelId,
    },
    after: {
      bodyA: after.bodyA,
      viewingA: after.viewingA,
      streetCount: after.streetCount,
    },
    shot: SHOT,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    console.error(JSON.stringify(report, null, 2));
    process.exitCode = 1;
  } else {
    console.log(
      [report.verdict, js.path, `viewing=${during.viewingA?.shop}`, `street ${before.streetCount}->${during.streetCount}->${after.streetCount}`].join(" "),
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
  for (const chrome of chromes) {
    chrome.kill();
  }
}
