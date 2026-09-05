/**
 * Slim authored street HUD chip: Harbor Walk → Steps East.
 * Chip text must change; plaques stay 4; lantern E still
 * shop-lantern-fish; leftover B E not stolen. NOT_PLAN_PASS.
 * Not GATE-U1. Not OSM / WAN. Not GPS.
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
const OUT = join(import.meta.dirname, "J5-STREET-HUD-2026-09-04.txt");
const SHOT_HARBOR = join(import.meta.dirname, "j5-3d-street-hud-harbor.png");
const SHOT_STEPS = join(import.meta.dirname, "j5-3d-street-hud-steps.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9571), b: 9572 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-09";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const M_PER_DEG_LAT = 111320;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
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

async function keyDown(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  });
}

async function keyUp(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
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
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const list = document.querySelector('[data-testid="play-street-plaques"]');
  const plaques = [...document.querySelectorAll('[data-testid="play-street-plaques"] li')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
    role: el.getAttribute("data-role") ?? "",
  }));
  const chipBox = chip ? chip.getBoundingClientRect() : null;
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    alt: Number(avatar?.getAttribute("data-alt") ?? proof?.getAttribute("data-alt") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    atBound: avatar?.getAttribute("data-at-bound") ?? proof?.getAttribute("data-at-bound") ?? "",
    blocked: avatar?.getAttribute("data-blocked") ?? proof?.getAttribute("data-blocked") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    fog: proof?.getAttribute("data-fog") ?? "",
    blockEdge: proof?.getAttribute("data-block-edge") ?? "",
    ground: proof?.getAttribute("data-ground") ?? "",
    groundFloor: proof?.getAttribute("data-ground-floor") ?? "",
    innerLane: proof?.getAttribute("data-inner-lane") ?? play?.getAttribute("data-inner-lane") ?? "",
    streetPlaques: Number(
      proof?.getAttribute("data-street-plaques") ?? play?.getAttribute("data-street-plaques") ?? "0",
    ),
    plaqueKind: proof?.getAttribute("data-street-plaque-kind") ?? play?.getAttribute("data-street-plaque-kind") ?? "",
    plaqueOfficial: Number(proof?.getAttribute("data-street-plaque-official") ?? "0"),
    plaqueInner: Number(proof?.getAttribute("data-street-plaque-inner") ?? "0"),
    streetHud: play?.getAttribute("data-street-hud") ?? proof?.getAttribute("data-street-hud") ?? "",
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      proof?.getAttribute("data-street-name") ??
      "",
    streetRole:
      chip?.getAttribute("data-street-role") ??
      play?.getAttribute("data-street-role") ??
      proof?.getAttribute("data-street-role") ??
      "",
    chipText: (chip?.textContent ?? "").trim(),
    chipOnScreen: Boolean(
      chipBox && chipBox.width > 8 && chipBox.height > 8 && chipBox.x > -8 && chipBox.x < 1288 && chipBox.y > -8 && chipBox.y < 728,
    ),
    chipBox: chipBox
      ? {
          x: Number(chipBox.x.toFixed(1)),
          y: Number(chipBox.y.toFixed(1)),
          w: Number(chipBox.width.toFixed(1)),
          h: Number(chipBox.height.toFixed(1)),
        }
      : null,
    menuHidden: Boolean(menu?.hidden) || menu?.getAttribute("data-open") === "no",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    plaques,
    plaqueNames: plaques.map((row) => row.name),
    gtaClaim:
      /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
    gpsClaim: /\\bgps\\b/i.test(chip?.textContent ?? "") || /\\bgps\\b/i.test(chip?.getAttribute("data-street-name") ?? ""),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-hud-${port}-`));
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

const chromes = [];
let report;
try {
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

  const readyA = await waitSnap(
    a.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.chipText,
    36,
    250,
  );
  const readyB = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );
  const spawn = readyA.snap;

  const geo = await fetch(`${PLAYER}data/ben-thanh-400m.authored.geojson`).then((res) => res.json());
  const geoStreets = (geo.features ?? []).filter((row) => row.properties?.kind === "street");

  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(120);
  await keyHold(a.ws, 90, "w", "KeyW", 87, 2400);
  await sleep(180);
  const onHarbor = await evalExpr(a.ws, 100, SNAP);
  const harborShot = await cdp(a.ws, 101, "Page.captureScreenshot", { format: "png" });
  const harborBuf = Buffer.from(harborShot.data, "base64");
  writeFileSync(SHOT_HARBOR, harborBuf);

  await keyHold(a.ws, 110, "w", "KeyW", 87, 10600);
  await sleep(120);
  await keyHold(a.ws, 120, "d", "KeyD", 68, 850);
  await sleep(80);
  await keyHold(a.ws, 130, "w", "KeyW", 87, 4500);
  await sleep(200);
  const onSteps = await evalExpr(a.ws, 140, SNAP);
  const stepsShot = await cdp(a.ws, 141, "Page.captureScreenshot", { format: "png" });
  const stepsBuf = Buffer.from(stepsShot.data, "base64");
  writeFileSync(SHOT_STEPS, stepsBuf);

  await keyHold(a.ws, 150, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 160, "a", "KeyA", 65, 850);
  await sleep(60);
  await keyHold(a.ws, 170, "w", "KeyW", 87, 5000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 180, SNAP);
  await keyHold(a.ws, 181, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 190, SNAP);
  await evalExpr(a.ws, 191, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  const shopClosed = await evalExpr(a.ws, 192, SNAP);

  const leftoverB =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";
  await keyHold(b.ws, 80, "e", "KeyE", 69, 180);
  await sleep(250);
  const bAfterE = await evalExpr(b.ws, 90, SNAP);
  const leftoverEStolen = Boolean(bAfterE.shopPanel) && LEFTOVER.test(bAfterE.shopPanelId || "");

  const eastM = (onSteps.lon - spawn.lon) * metersPerDegLon((onSteps.lat + spawn.lat) / 2);
  const northM = (onSteps.lat - spawn.lat) * M_PER_DEG_LAT;
  const names = spawn.plaqueNames ?? [];
  const plaquesOk =
    spawn.streetPlaques >= 4 &&
    spawn.plaqueKind === "pole-board" &&
    names.includes("Harbor Walk") &&
    names.includes("Tram Approach") &&
    names.includes("Steps East") &&
    names.includes("Steps West");
  const harborChip =
    (onHarbor.chipText === "Harbor Walk" || onHarbor.streetName === "Harbor Walk") &&
    onHarbor.chipOnScreen &&
    onHarbor.streetHud === "named-chip";
  const stepsChip =
    (onSteps.chipText === "Steps East" || onSteps.streetName === "Steps East") &&
    onSteps.chipOnScreen &&
    onSteps.chipText !== onHarbor.chipText;
  const walkedOff =
    eastM > 6 &&
    northM > 10 &&
    onSteps.insideRing === "0" &&
    onSteps.insideAabb === "0";
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const leftoverOk = leftoverB && !leftoverEStolen && !bAfterE.shopPanel;
  const honestyOk =
    /Authored approximation/.test(spawn.honesty) &&
    /not a digital twin/i.test(spawn.honesty) &&
    /inner parcel lanes/.test(spawn.honesty) &&
    /two official named streets/.test(spawn.honesty) &&
    /NOT_PLAN_PASS/.test(spawn.honesty) &&
    spawn.gtaClaim === false &&
    onHarbor.gpsClaim === false &&
    onSteps.gpsClaim === false;
  const geoOk = geoStreets.length === 2;
  const slimOk =
    onHarbor.menuHidden &&
    onSteps.menuHidden &&
    (onHarbor.chipBox?.h ?? 99) < 40 &&
    (onHarbor.chipBox?.w ?? 999) < 220;
  const keptOk =
    spawn.sky === "gradient-hemisphere" &&
    spawn.blockEdge === "curb-wall-lot" &&
    spawn.fog === "distance-haze" &&
    spawn.groundFloor === "door-glass-awning" &&
    spawn.innerLane === "asphalt-walk-edge";

  const ok =
    plaquesOk &&
    harborChip &&
    stepsChip &&
    walkedOff &&
    lanternOk &&
    leftoverOk &&
    shopClosed.shopPanel === false &&
    honestyOk &&
    geoOk &&
    slimOk &&
    keptOk &&
    onHarbor.alt === 0 &&
    onSteps.alt === 0;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_STREET_HUD_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    not_gps: true,
    plaquesOk,
    harborChip,
    stepsChip,
    walkedOff,
    lanternOk,
    leftoverOk,
    honestyOk,
    geoOk,
    slimOk,
    keptOk,
    chipHarbor: onHarbor.chipText,
    chipSteps: onSteps.chipText,
    geoStreets: geoStreets.map((row) => row.properties?.display_name ?? row.properties?.name),
    eastM: Number(eastM.toFixed(2)),
    northM: Number(northM.toFixed(2)),
    plaqueNames: names,
    spawn,
    onHarbor,
    onSteps,
    atLantern,
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    honesty: spawn.honesty?.slice(0, 280),
    shots: { harbor: SHOT_HARBOR, steps: SHOT_STEPS },
    hashHarbor: createHash("sha256").update(harborBuf).digest("hex").slice(0, 16),
    hashSteps: createHash("sha256").update(stepsBuf).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_STREET_HUD_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `chipHarbor=${report.chipHarbor}`,
  `chipSteps=${report.chipSteps}`,
  `plaques=${report.spawn?.streetPlaques}`,
  `east=${report.eastM}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
