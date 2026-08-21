/** Test harness for bind/token. Hosts under test are passed on argv (not hardcoded here). */

import net from "node:net";

import { listenExplicit, listenLoopback, LOOPBACK_HOST } from "../transport/loopback.js";
import { E } from "../registry/errors.js";
import { generateSessionToken, isSessionToken } from "./token.js";

function write(obj: unknown): void {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function fail(err: unknown): never {
  const code =
    err && typeof err === "object" && "code" in err && typeof err.code === "string" ? err.code : "E_FAIL";
  const message = err instanceof Error ? err.message : "harness failed";
  write({ ok: false, error: { code, message } });
  process.exitCode = 1;
  throw err;
}

async function bindReject(host: string): Promise<void> {
  const server = net.createServer();
  try {
    await listenExplicit(server, host, 0);
    server.close();
    write({ ok: false, error: { code: "E_FAIL", message: "non-loopback listen was accepted" } });
    process.exitCode = 1;
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string }) : {};
    if (rec.code !== E.E_BIND) {
      write({ ok: false, error: { code: rec.code ?? "E_FAIL", message: "expected E_BIND" } });
      process.exitCode = 1;
      return;
    }
    write({ ok: true, code: E.E_BIND, rejected_host_len: host.length });
  }
}

async function bindOk(): Promise<void> {
  const server = net.createServer();
  const addr = await listenLoopback(server);
  if (addr.host !== LOOPBACK_HOST || addr.port <= 0) {
    server.close();
    fail(new Error("loopback listen produced a bad address"));
  }
  await new Promise<void>((resolve, reject) => {
    server.close((e) => (e ? reject(e) : resolve()));
  });
  write({ ok: true, host: addr.host, port: addr.port });
}

async function collision(): Promise<void> {
  const server = net.createServer();
  let attempts = 0;
  const addr = await listenLoopback(server, {
    listen(opts, cb) {
      attempts += 1;
      if (opts.host !== LOOPBACK_HOST || opts.port !== 0) {
        throw new Error("listen options must stay loopback + OS-assigned");
      }
      if (attempts === 1) {
        const err = Object.assign(new Error("in use"), { code: "EADDRINUSE" });
        queueMicrotask(() => server.emit("error", err));
        return server;
      }
      return net.Server.prototype.listen.call(server, opts, cb);
    },
  });
  if (attempts < 2) {
    server.close();
    fail(new Error("EADDRINUSE path did not retry listen"));
  }
  await new Promise<void>((resolve, reject) => {
    server.close((e) => (e ? reject(e) : resolve()));
  });
  write({ ok: true, attempts, host: addr.host, port: addr.port });
}

function tokenShape(): void {
  const secret = generateSessionToken();
  if (!isSessionToken(secret) || secret.length !== 64) {
    fail(new Error("token must be 32 bytes hex"));
  }
  write({ ok: true, bytes: 32, hex_len: 64 });
}

const cmd = process.argv[2] ?? "";
const extra = process.argv[3] ?? "";

void (async () => {
  try {
    if (cmd === "bind-ok") {
      await bindOk();
      return;
    }
    if (cmd === "bind-reject") {
      if (!extra) {
        fail(new Error("bind-reject requires a host argument"));
      }
      await bindReject(extra);
      return;
    }
    if (cmd === "collision") {
      await collision();
      return;
    }
    if (cmd === "token") {
      tokenShape();
      return;
    }
    if (cmd === "discover") {
      if (!extra) {
        fail(new Error("discover requires a project path"));
      }
      const { discoverProject } = await import("./project.js");
      const found = discoverProject(extra);
      write({ ok: true, root: found.root, project_id: found.projectId });
      return;
    }
    fail(new Error("unknown harness command"));
  } catch (err) {
    if (process.exitCode) {
      return;
    }
    fail(err);
  }
})();
