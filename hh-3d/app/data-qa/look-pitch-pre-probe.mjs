/**
 * Implementer pre-edit CDP. Does not recycle 4175. Not a critic TICK.
 * Port 10048 (unused; not 10014–10036).
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";

const PLAYER = "http://127.0.0.1:4175/?seat=a";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "look-pitch-pre-shots");
const PORT = 10048;
const EXPECT_JS = "/assets/index-CoTKbFff.js";
const EXPECT_SHA = "2971c5c4577664cd319c9dbdd2f451f141ea6cf201fd52ba8db496dd15bf273c";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(ws, id, method, params) {
  return new Promise((resolve, reject) => {
    const onMsg = (event) => {
      const msg = JSON.parse(typeof event.data === "string" ? event.data : String(event.data));
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

async function evalExpr(ws, id, expression) {
  const result = await cdp(ws, id, "Runtime.evaluate", { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const self = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const help = document.querySelector('[data-testid="avatar-status"]');
  const fps = document.querySelector('[data-testid="play-fps"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  if (menu && menu.getAttribute("data-open") === "yes") {
    document.querySelector('[data-testid="menu-close"]')?.click();
  }
  const lon = Number(self?.dataset.lon ?? proof?.dataset.lon ?? NaN);
  const lat = Number(self?.dataset.lat ?? NaN);
  const heading = Number(self?.dataset.heading ?? proof?.dataset.heading ?? NaN);
  const camX = Number(proof?.dataset.camX ?? NaN);
  const camY = Number(proof?.dataset.camY ?? NaN);
  const camZ = Number(proof?.dataset.camZ ?? NaN);
  const camPitch = Number(proof?.dataset.camPitch ?? NaN);
  const originLon = 106.698;
  const originLat = 10.7725;
  const mLon = 111320 * Math.cos((originLat * Math.PI) / 180);
  const bodyX = (lon - originLon) * mLon;
  const bodyZ = (lat - originLat) * 111320;
  const bodyY = 1.15;
  const lookX = Number(proof?.dataset.camLookX ?? NaN);
  const lookY = Number(proof?.dataset.camLookY ?? NaN);
  const lookZ = Number(proof?.dataset.camLookZ ?? NaN);
  // Three.js lookAt: zAxis = normalize(eye-target); xAxis = normalize(cross(up,z))
  const tx = Number.isFinite(lookX) ? lookX : bodyX;
  const ty = Number.isFinite(lookY) ? lookY : bodyY;
  const tz = Number.isFinite(lookZ) ? lookZ : bodyZ + 1.4;
  let zx = camX - tx;
  let zy = camY - ty;
  let zz = camZ - tz;
  const zlen = Math.hypot(zx, zy, zz) || 1;
  zx /= zlen; zy /= zlen; zz /= zlen;
  let xx = 1 * zz - 0 * zy;
  let xy = 0 * zx - 0 * zz;
  let xz = 0 * zy - 1 * zx;
  const xlen = Math.hypot(xx, xy, xz) || 1;
  xx /= xlen; xy /= xlen; xz /= xlen;
  const yx = zy * xz - zz * xy;
  const yy = zz * xx - zx * xz;
  const yz = zx * xy - zy * xx;
  const fx = bodyX - camX;
  const fy = bodyY - camY;
  const fz = bodyZ - camZ;
  const vx = fx * xx + fy * xy + fz * xz;
  const vy = fx * yx + fy * yy + fz * yz;
  const vz = fx * zx + fy * zy + fz * zz;
  const fov = 50 * Math.PI / 180;
  const aspect = 1280 / 720;
  const ndcX = (vx / -vz) / (Math.tan(fov / 2) * aspect);
  const ndcY = (vy / -vz) / Math.tan(fov / 2);
  const screenX = (ndcX * 0.5 + 0.5) * 1280;
  const screenY = (-ndcY * 0.5 + 0.5) * 720;
  const inFrame = ndcX > -0.92 && ndcX < 0.92 && ndcY > -0.92 && ndcY < 0.92 && -vz > 0.2;
  return {
    ready: play?.getAttribute("data-play-ready") ?? "",
    look: play?.getAttribute("data-look") ?? proof?.getAttribute("data-look") ?? "",
    heading,
    lon,
    lat,
    camX, camY, camZ, camPitch,
    bodyX, bodyZ,
    ndcX, ndcY, screenX, screenY, inFrame,
    camRightX: xx, camRightZ: xz,
    help: (help?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    fps: fps?.textContent ?? "",
    js: [...document.scripts].map((s) => s.src).find((s) => s.includes("/assets/index-")) ?? "",
  };
})()`;

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-look-pre-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
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

async function connectPage(port) {
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await res.json();
      const page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
          ws.addEventListener("open", resolve);
          ws.addEventListener("error", reject);
        });
        return ws;
      }
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error(`no CDP page on ${port}`);
}

async function shot(ws, id, path) {
  const raw = await cdp(ws, id, "Page.captureScreenshot", { format: "png" });
  writeFileSync(path, Buffer.from(raw.data, "base64"));
}

async function holdA(ws, id, ms) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
  await sleep(ms);
  await cdp(ws, id + 2, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
}

async function pitchUp(ws, id, pixels) {
  const canvas = await evalExpr(
    ws,
    id,
    `(() => {
      const c = document.querySelector("canvas.play-canvas");
      if (!c) return null;
      const r = c.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`,
  );
  if (!canvas) throw new Error("no canvas");
  await cdp(ws, id + 1, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: canvas.x,
    y: canvas.y,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await cdp(ws, id + 2, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: canvas.x,
    y: canvas.y - pixels,
    button: "right",
    buttons: 2,
    movementX: 0,
    movementY: -pixels,
  });
  await sleep(80);
  await cdp(ws, id + 3, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: canvas.x,
    y: canvas.y - pixels,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const html = await fetch(PLAYER).then((r) => r.text());
  const jsName = (html.match(/\/assets\/index-[^"]+\.js/) ?? [""])[0];
  const jsBuf = Buffer.from(await fetch(`http://127.0.0.1:4175${jsName}`).then((r) => r.arrayBuffer()));
  const sha = createHash("sha256").update(jsBuf).digest("hex");
  const hashOk = jsName === EXPECT_JS && sha === EXPECT_SHA && jsBuf.length === 2174312;
  const chrome = launchChrome(PORT, PLAYER);
  let ws;
  try {
    ws = await connectPage(PORT);
    await cdp(ws, 1, "Page.enable");
    await cdp(ws, 2, "Runtime.enable");
    let snap = null;
    for (let i = 0; i < 40; i += 1) {
      snap = await evalExpr(ws, 10 + i, SNAP);
      if (snap?.ready === "yes") break;
      await sleep(250);
    }
    await shot(ws, 60, join(OUT, "a-before.png"));
    const before = snap;
    await holdA(ws, 70, 900);
    await sleep(120);
    const afterA = await evalExpr(ws, 80, SNAP);
    await shot(ws, 81, join(OUT, "a-after.png"));
    await pitchUp(ws, 90, 220);
    await sleep(200);
    const afterPitch = await evalExpr(ws, 100, SNAP);
    await shot(ws, 101, join(OUT, "pitch-up.png"));
    const dLon = afterA.lon - before.lon;
    const dScreen = afterA.screenX - before.screenX;
    const out = {
      hashOk,
      jsName,
      sha,
      len: jsBuf.length,
      before,
      afterA,
      afterPitch,
      dLon,
      dScreen,
      lonWest: dLon < -1e-7,
      screenRight: dScreen > 8,
      screenLeft: dScreen < -8,
      pitchLostBody: afterPitch.inFrame === false,
      pitchCamY: afterPitch.camY,
      pitchLook: afterPitch.camPitch,
    };
    writeFileSync(join(OUT, "result.json"), JSON.stringify(out, null, 2));
    console.log(JSON.stringify(out, null, 2));
  } finally {
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
    chrome.kill();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
