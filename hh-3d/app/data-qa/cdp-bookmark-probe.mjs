const PORT = 9223;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(ws, id, method, params) {
  const result = await new Promise((resolve, reject) => {
    const onMsg = (event) => {
      const raw = typeof event.data === "string" ? event.data : String(event.data);
      const msg = JSON.parse(raw);
      if (msg.id === id) {
        ws.removeEventListener("message", onMsg);
        if (msg.error) {
          reject(new Error(JSON.stringify(msg.error)));
        } else {
          resolve(msg.result);
        }
      }
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
  return result;
}

const targets = await fetch(`http://127.0.0.1:${PORT}/json`).then((r) => r.json());
const page = targets.find((t) => t.type === "page" && String(t.url).includes("127.0.0.1:4175"));
if (!page) {
  throw new Error(`no page: ${JSON.stringify(targets)}`);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve);
  ws.addEventListener("error", reject);
});
await cdp(ws, 1, "Runtime.enable");
await sleep(1500);
const before = await cdp(ws, 2, "Runtime.evaluate", {
  expression: `({
    card: !!document.querySelector('[data-testid="place-card"]'),
    bookmarks: document.querySelector('[data-testid="bookmark-panel"]')?.innerText ?? "",
    btn: document.querySelector('[data-testid="bookmark-btn"]')?.textContent ?? ""
  })`,
  returnByValue: true,
});
const click = await cdp(ws, 3, "Runtime.evaluate", {
  expression: `document.querySelector('[data-testid="bookmark-btn"]')?.click(); true`,
  returnByValue: true,
});
await sleep(400);
const after = await cdp(ws, 4, "Runtime.evaluate", {
  expression: `({
    btn: document.querySelector('[data-testid="bookmark-btn"]')?.textContent ?? "",
    panel: document.querySelector('[data-testid="bookmark-panel"]')?.innerText ?? "",
    stored: localStorage.getItem("hh-world.bookmarks.v1")
  })`,
  returnByValue: true,
});
ws.close();
const report = { before: before.result.value, click: click.result.value, after: after.result.value };
console.log(JSON.stringify(report, null, 2));
const stored = report.after.stored ?? "";
if (!stored.includes("place-market-hall")) {
  throw new Error("bookmark not stored");
}
if (!String(report.after.panel).includes("Market Hall")) {
  throw new Error("bookmark panel missing Market Hall");
}
if (!String(report.after.btn).toLowerCase().includes("remove")) {
  throw new Error("button did not flip to remove");
}
console.log("BOOKMARK_PASS");
