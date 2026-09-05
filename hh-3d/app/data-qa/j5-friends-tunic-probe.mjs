/**
 * Two seats on recycled 4175. B sees A's Hòn Gió tunic remote body move.
 * Offline hides the other body. Authored boxes have cheap facade insets.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN / other-PC / city.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FRIENDS-TUNIC-2026-09-03.txt");
const SHOT = join(import.meta.dirname, "j5-3d-friend-tunic.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9388), b: 9389 };
const TUNIC_A = "#2a7d78";
const TUNIC_B = "#c4a046";

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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-tunic-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
      "--disable-gpu",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--window-size=1280,720",
      url,
    ],
    { stdio: "ignore" },
  );
}

const SNAP = `(() => {
  const pick = (el) =>
    el
      ? {
          testid: el.getAttribute("data-testid"),
          seat: el.getAttribute("data-seat"),
          body: el.getAttribute("data-body"),
          tunic: el.getAttribute("data-tunic"),
          pose: el.getAttribute("data-pose"),
          heading: el.getAttribute("data-heading"),
          lon: el.getAttribute("data-lon"),
          lat: el.getAttribute("data-lat"),
        }
      : null;
  const remotes = [...document.querySelectorAll('[data-testid^="remote-avatar-"], [data-testid^="remote-body-"]')]
    .map(pick)
    .filter(Boolean);
  const people = [...document.querySelectorAll('[data-testid^="people-row-"]')].map(pick);
  const buildings = [...document.querySelectorAll('[data-testid="play-building-list"] [data-building-id]')].map((el) => ({
    id: el.getAttribute("data-building-id"),
    facade: el.getAttribute("data-facade"),
    insets: Number(el.getAttribute("data-insets") ?? "0"),
  }));
  const proof = document.querySelector('[data-testid="play-proof"]');
  const self = document.querySelector('[data-testid="self-avatar"]');
  const play = document.querySelector('[data-testid="play-view"]');
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    remoteCount: Number(document.querySelector('[data-testid="people-layer"]')?.getAttribute("data-remote-count") ?? "-1"),
    remotes,
    people,
    self: pick(self),
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
    addB: Boolean(document.querySelector('[data-testid="add-friend-b"]')),
    proof: {
      body: proof?.getAttribute("data-body") ?? "",
      tunic: proof?.getAttribute("data-tunic") ?? "",
      facade: proof?.getAttribute("data-facade") ?? "",
      windows: Number(proof?.getAttribute("data-facade-windows") ?? "0"),
      doors: Number(proof?.getAttribute("data-facade-doors") ?? "0"),
      bands: Number(proof?.getAttribute("data-facade-bands") ?? "0"),
      total: Number(proof?.getAttribute("data-facade-total") ?? "0"),
      buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    },
    buildings,
    insetBuildings: buildings.filter((row) => row.facade === "inset" && row.insets > 0).length,
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.textContent ?? "",
    friendsHonesty: document.querySelector('[data-testid="friends-honesty"]')?.textContent ?? "",
  };
})()`;

async function waitSnap(ws, startId, pred, tries = 24, delay = 300) {
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

function remoteA(snap) {
  return (
    snap?.remotes.find((row) => row.seat === "a") ??
    snap?.people.find((row) => row.seat === "a") ??
    null
  );
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
  await sleep(700);
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
  await sleep(2600);

  const readyA = await waitSnap(a.ws, 20, (s) => s.playReady === "yes" && s.proof.buildings >= 20);
  const readyB = await waitSnap(b.ws, 20, (s) => s.playReady === "yes" && s.proof.buildings >= 20);

  await evalExpr(a.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, 41, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  await waitSnap(b.ws, 41, (s) => s.acceptA === true, 16, 250);
  await evalExpr(b.ws, 50, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  await evalExpr(a.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(b.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(a.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 52, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);

  const friendsB = await waitSnap(
    b.ws,
    60,
    (s) => s.remoteCount === 1 && Boolean(remoteA(s)),
    20,
    300,
  );
  const friendsA = await waitSnap(a.ws, 60, (s) => s.remoteCount === 1, 16, 250);

  const before = remoteA(friendsB.snap);
  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(150);
  await keyHold(a.ws, 81, "w", "KeyW", 87, 3500);
  const walked = await waitSnap(
    b.ws,
    90,
    (s) => {
      const row = remoteA(s);
      return Boolean(row && before && Number(row.lat) > Number(before.lat) + 0.000008);
    },
    20,
    250,
  );

  const shot = await cdp(b.ws, 120, "Page.captureScreenshot", { format: "png" });
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  await evalExpr(b.ws, 121, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(a.ws, 130, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(a.ws, 131, `document.querySelector('[data-testid="offline-btn"]')?.click(); true`);
  const offlineB = await waitSnap(b.ws, 140, (s) => s.remoteCount === 0 && !remoteA(s), 16, 250);

  const after = remoteA(walked.snap);
  const tunicOk =
    after?.body === "tunic-humanoid" &&
    after?.tunic === TUNIC_A &&
    friendsB.snap.self?.tunic === TUNIC_B &&
    after.tunic !== friendsB.snap.self?.tunic &&
    friendsA.snap.proof.body === "tunic-humanoid";
  const moveOk =
    Boolean(before?.lat) &&
    Boolean(after?.lat) &&
    Number(after.lat) > Number(before.lat) + 0.000008;
  const hideOk = offlineB.snap.remoteCount === 0 && !remoteA(offlineB.snap);
  const facadeOk =
    readyB.snap.proof.facade === "inset" &&
    readyB.snap.proof.windows >= 60 &&
    readyB.snap.proof.doors >= 40 &&
    readyB.snap.proof.bands >= 60 &&
    readyB.snap.proof.buildings >= 60 &&
    readyB.snap.insetBuildings >= 50;
  const honestyOk =
    /Authored approximation|NOT_PLAN_PASS/i.test(readyA.snap.honesty + readyA.snap.friendsHonesty) &&
    /not wan|loopback|this PC|this machine/i.test(readyA.snap.honesty + readyA.snap.friendsHonesty);

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-11",
    player: PLAYER,
    verdict: tunicOk && moveOk && hideOk && facadeOk && honestyOk ? "J5_FRIENDS_TUNIC_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_wan: true,
    not_other_pc: true,
    tunicOk,
    moveOk,
    hideOk,
    facadeOk,
    honestyOk,
    tunics: { a: after?.tunic ?? null, b: friendsB.snap.self?.tunic ?? null },
    remoteOnB: after,
    startLat: before?.lat ?? null,
    walkedLat: after?.lat ?? null,
    facade: readyB.snap.proof,
    insetBuildings: readyB.snap.insetBuildings,
    offlineB: offlineB.snap.remoteCount,
    shot: SHOT,
  };
  a.ws.close();
  b.ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-11",
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

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J5_FRIENDS_TUNIC_OK") {
  process.exitCode = 1;
}
