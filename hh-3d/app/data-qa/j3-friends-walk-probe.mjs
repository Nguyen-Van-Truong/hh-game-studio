/**
 * J3 two-context friends walk on existing 4175.
 * Chrome A (?seat=a) and Chrome B (?seat=b) are isolated profiles.
 * Walking in A must move the friend body in B. Offline/unfriend hide it.
 * Stranger C (third context) is never drawn.
 * NOT_PLAN_PASS. GATE-U1 still open. Does not start a second preview.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J3-FRIENDS-WALK-2026-09-03.txt");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9248), b: 9249, c: 9250 };

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

async function keyEvent(ws, id, type, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j3-${port}-`));
  const chrome = spawn(
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
  return chrome;
}

const SNAP = `(() => {
  const remotes = [...document.querySelectorAll('[data-testid^="remote-avatar-"]')].map((el) => ({
    id: el.getAttribute("data-testid"),
    seat: el.getAttribute("data-seat"),
    pose: el.getAttribute("data-pose"),
    heading: el.getAttribute("data-heading"),
    lon: el.getAttribute("data-lon"),
    lat: el.getAttribute("data-lat"),
  }));
  const people = [...document.querySelectorAll('[data-testid^="people-row-"]')].map((el) => ({
    id: el.getAttribute("data-testid"),
    seat: el.getAttribute("data-seat"),
    pose: el.getAttribute("data-pose"),
    lon: el.getAttribute("data-lon"),
    lat: el.getAttribute("data-lat"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const self = document.querySelector('[data-testid="self-avatar"]');
  const friendB = document.querySelector('[data-testid="friend-row-b"]');
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const friendC = document.querySelector('[data-testid="friend-row-c"]');
  return {
    title: document.title,
    href: location.href,
    seat: document.querySelector('[data-testid="seat-switcher"]')?.getAttribute("data-seat") ?? "",
    currentSeat: document.querySelector('[data-testid="current-seat"]')?.textContent ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    peopleLayer: document.querySelector('[data-testid="people-layer"]')?.textContent ?? "",
    remoteCount: Number(document.querySelector('[data-testid="people-layer"]')?.getAttribute("data-remote-count") ?? "-1"),
    peopleRowsCount: Number(document.querySelector('[data-testid="people-rows"]')?.getAttribute("data-count") ?? "-1"),
    onlineDisabled: document.querySelector('[data-testid="online-btn"]')?.disabled ?? null,
    optIn: document.querySelector('[data-testid="presence-opt-in"]')?.checked ?? null,
    honesty: document.querySelector('[data-testid="presence-honesty"]')?.textContent ?? "",
    friendsHonesty: document.querySelector('[data-testid="friends-honesty"]')?.textContent ?? "",
    relationB: friendB?.getAttribute("data-relation") ?? null,
    relationA: friendA?.getAttribute("data-relation") ?? null,
    relationC: friendC?.getAttribute("data-relation") ?? null,
    addB: Boolean(document.querySelector('[data-testid="add-friend-b"]')),
    addA: Boolean(document.querySelector('[data-testid="add-friend-a"]')),
    addC: Boolean(document.querySelector('[data-testid="add-friend-c"]')),
    acceptB: Boolean(document.querySelector('[data-testid="accept-friend-b"]')),
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
    unfriendB: Boolean(document.querySelector('[data-testid="unfriend-b"]')),
    remotes,
    people,
    hasRemoteC: Boolean(document.querySelector('[data-testid="remote-avatar-c"]')),
    hasPeopleC: Boolean(document.querySelector('[data-testid="people-row-c"]')),
    self: self
      ? {
          seat: self.getAttribute("data-seat"),
          lon: self.getAttribute("data-lon"),
          lat: self.getAttribute("data-lat"),
          pose: self.getAttribute("data-pose"),
        }
      : null,
    bodyHasCityServer: /city presence server/i.test(document.body.innerText) && /not a city presence server/i.test(document.body.innerText),
    gpsClaim: /your gps|device gps|geolocation on/i.test(document.body.innerText),
    googleOidc: /sign in with google|oidc login/i.test(document.body.innerText),
  };
})()`;

async function waitSnap(ws, startId, pred, tries = 20, delay = 250) {
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
  for (const seat of ["a", "b", "c"]) {
    await fetch(`${origin}/demo-bus`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        v: 1,
        kind: "local-demo-bus",
        not_presence_server: true,
        not_plan_pass: true,
        leave: seat,
        graph: {
          v: 1,
          kind: "local-demo-friends",
          pairs: [],
          updated_at: Date.now(),
          not_presence_server: true,
          not_plan_pass: true,
        },
      }),
    });
  }
}

const chromes = [];
let report;
try {
  await resetBus();
  const chromeA = launchChrome(PORTS.a, `${PLAYER}?seat=a`);
  const chromeB = launchChrome(PORTS.b, `${PLAYER}?seat=b`);
  const chromeC = launchChrome(PORTS.c, `${PLAYER}?seat=c`);
  chromes.push(chromeA, chromeB, chromeC);

  const { ws: wsA } = await connectPage(PORTS.a);
  const { ws: wsB } = await connectPage(PORTS.b);
  const { ws: wsC } = await connectPage(PORTS.c);
  for (const [ws, base] of [
    [wsA, 1],
    [wsB, 1],
    [wsC, 1],
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
  await sleep(800);
  const origin = PLAYER.replace(/\/$/, "");
  for (const [ws, seat, base] of [
    [wsA, "a", 10],
    [wsB, "b", 10],
    [wsC, "c", 10],
  ]) {
    await cdp(ws, base, "Storage.clearDataForOrigin", {
      origin,
      storageTypes: "local_storage",
    });
    await cdp(ws, base + 1, "Page.navigate", { url: `${PLAYER}?seat=${seat}` });
  }
  await sleep(2400);

  const homeA = await evalExpr(wsA, 20, SNAP);
  const homeB = await evalExpr(wsB, 20, SNAP);
  const homeC = await evalExpr(wsC, 20, SNAP);

  await evalExpr(wsA, 19, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(wsB, 19, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(wsC, 19, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(wsA, 21, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  const pendingReady = await waitSnap(wsB, 22, (s) => s.acceptA === true, 16, 300);
  await evalExpr(wsA, 40, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(wsB, 40, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(wsC, 40, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  const pending = (
    await waitSnap(
      wsB,
      41,
      (s) => s.mode.includes("Online") && s.acceptA === true && s.remoteCount === 0,
      12,
      250,
    )
  ).snap ?? pendingReady.snap;

  await evalExpr(wsB, 50, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  const friendsA = await waitSnap(wsA, 30, (s) => s.remoteCount === 1 && s.people.some((p) => p.seat === "b"));
  const friendsB = await waitSnap(wsB, 30, (s) => s.remoteCount === 1 && s.people.some((p) => p.seat === "a"));
  const friendsC = await waitSnap(wsC, 30, (s) => s.remoteCount === 0 && !s.hasRemoteC, 8, 200);

  const beforeB = friendsB.snap?.people.find((p) => p.seat === "a");
  await cdp(wsA, 80, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  await sleep(2400);
  await cdp(wsA, 81, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  const movedB = await waitSnap(
    wsB,
    90,
    (s) => {
      const row = s.people.find((p) => p.seat === "a");
      return Boolean(row && beforeB && Number(row.lat) !== Number(beforeB.lat));
    },
    16,
    250,
  );

  const beforeA = friendsA.snap?.people.find((p) => p.seat === "b");
  await keyEvent(wsB, 110, "keyDown", "w", "KeyW", 87);
  await sleep(2400);
  await keyEvent(wsB, 111, "keyUp", "w", "KeyW", 87);
  const movedA = await waitSnap(
    wsA,
    120,
    (s) => {
      const row = s.people.find((p) => p.seat === "b");
      return Boolean(row && beforeA && Number(row.lon) !== Number(beforeA.lon));
    },
    16,
    250,
  );

  await evalExpr(wsA, 140, `document.querySelector('[data-testid="offline-btn"]')?.click(); true`);
  const offlineB = await waitSnap(wsB, 150, (s) => s.remoteCount === 0 && s.people.length === 0);
  const offlineA = await evalExpr(wsA, 160, SNAP);

  await evalExpr(wsA, 161, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  const backB = await waitSnap(wsB, 170, (s) => s.remoteCount === 1 && s.people.some((p) => p.seat === "a"));

  await evalExpr(wsB, 190, `document.querySelector('[data-testid="unfriend-a"]')?.click(); true`);
  const unfriendA = await waitSnap(wsA, 200, (s) => s.remoteCount === 0);
  const unfriendB = await waitSnap(wsB, 210, (s) => s.remoteCount === 0);
  const finalC = await evalExpr(wsC, 220, SNAP);

  const afterLat = movedB.snap?.people.find((p) => p.seat === "a")?.lat;
  const afterLon = movedA.snap?.people.find((p) => p.seat === "b")?.lon;
  const walkOk =
    Boolean(beforeB?.lat) &&
    Boolean(afterLat) &&
    Number(afterLat) !== Number(beforeB.lat) &&
    Boolean(beforeA?.lon) &&
    Boolean(afterLon) &&
    Number(afterLon) !== Number(beforeA.lon);
  const friendOk =
    friendsA.snap?.remoteCount === 1 &&
    friendsB.snap?.remoteCount === 1 &&
    friendsA.snap.people.some((p) => p.seat === "b") &&
    friendsB.snap.people.some((p) => p.seat === "a") &&
    friendsA.snap.hasRemoteC === false &&
    friendsB.snap.hasRemoteC === false &&
    friendsC.snap?.remoteCount === 0 &&
    pending.remoteCount === 0;
  const hideOk =
    offlineB.snap?.remoteCount === 0 &&
    offlineA.mode.includes("Offline") &&
    backB.snap?.remoteCount === 1 &&
    unfriendA.snap?.remoteCount === 0 &&
    unfriendB.snap?.remoteCount === 0;
  const strangerOk =
    homeC.seat === "c" &&
    homeC.addA === false &&
    homeC.addB === false &&
    finalC.hasRemoteC === false &&
    finalC.hasPeopleC === false &&
    finalC.remoteCount === 0 &&
    !friendsA.snap?.hasPeopleC &&
    !friendsB.snap?.hasPeopleC;
  const honestyOk =
    /NOT_PLAN_PASS/.test(homeA.honesty) &&
    /not a city presence server/i.test(homeA.honesty) &&
    /not GPS/i.test(homeA.honesty) &&
    /this-machine|this machine/i.test(homeA.honesty + homeA.friendsHonesty) &&
    homeA.onlineDisabled === false &&
    homeA.googleOidc === false &&
    homeA.gpsClaim === false &&
    homeA.mode.includes("Offline") &&
    homeA.remoteCount === 0 &&
    homeB.remoteCount === 0;

  report = {
    run_id: "HH3D-J3-20260903-ASIA-SAIGON-01",
    player: PLAYER,
    verdict:
      walkOk && friendOk && hideOk && strangerOk && honestyOk ? "J3_OBSERVED" : "J3_REWORK",
    not_plan_pass: true,
    not_m2_wp1: true,
    walkOk,
    friendOk,
    hideOk,
    strangerOk,
    honestyOk,
    twoContexts: true,
    isolatedProfiles: true,
    beforeALat: beforeB?.lat ?? null,
    afterALat: afterLat ?? null,
    beforeBLon: beforeA?.lon ?? null,
    afterBLon: afterLon ?? null,
    homeA: {
      seat: homeA.seat,
      mode: homeA.mode,
      remoteCount: homeA.remoteCount,
      onlineDisabled: homeA.onlineDisabled,
    },
    homeB: { seat: homeB.seat, mode: homeB.mode, remoteCount: homeB.remoteCount },
    pending: { remoteCount: pending.remoteCount, relationA: pending.relationA },
    friendsA: {
      remoteCount: friendsA.snap?.remoteCount,
      people: friendsA.snap?.people,
      remotes: friendsA.snap?.remotes,
    },
    friendsB: {
      remoteCount: friendsB.snap?.remoteCount,
      people: friendsB.snap?.people,
      remotes: friendsB.snap?.remotes,
    },
    friendsC: { remoteCount: friendsC.snap?.remoteCount, remotes: friendsC.snap?.remotes },
    offlineB: { remoteCount: offlineB.snap?.remoteCount },
    backB: { remoteCount: backB.snap?.remoteCount },
    unfriend: {
      a: unfriendA.snap?.remoteCount,
      b: unfriendB.snap?.remoteCount,
    },
    honesty: homeA.honesty,
  };
  wsA.close();
  wsB.close();
  wsC.close();
} finally {
  for (const chrome of chromes) {
    chrome.kill();
  }
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J3_OBSERVED") {
  process.exitCode = 1;
}
