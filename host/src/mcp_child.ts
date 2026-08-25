/** Spawn the sidecar and speak newline JSON-RPC MCP. Not a fake executor. */

import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

import { E, HostError } from "./errors.js";
import type { LineStdio } from "./executor.js";

const DEFAULT_READ_MS = 30_000;

export interface McpChild extends LineStdio {
  readonly pid: number;
  initialize(): Promise<void>;
  dispose(): void;
}

function bridgeMainJs(): string {
  const fromEnv = process.env.HH_BRIDGE_MAIN;
  if (fromEnv && fromEnv.trim()) {
    return path.resolve(fromEnv);
  }
  const here = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(here, "..", "..", "bridge", "dist", "main.js");
}

export function spawnMcpChild(opts: { projectRoot: string; logDir?: string }): McpChild {
  const main = bridgeMainJs();
  if (!fs.existsSync(main)) {
    throw new HostError(E.E_PATH, "bridge dist/main.js missing (build the sidecar)", "mcp");
  }
  const child: ChildProcessWithoutNullStreams = spawn(
    process.execPath,
    [main, "--project", path.resolve(opts.projectRoot)],
    {
      cwd: path.dirname(main),
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  if (opts.logDir) {
    fs.mkdirSync(opts.logDir, { recursive: true });
    fs.writeFileSync(path.join(opts.logDir, "mcp.pid"), `${child.pid}\n`, "utf8");
    const errLog = fs.createWriteStream(path.join(opts.logDir, "sidecar.stderr.log"), { flags: "a" });
    child.stderr.pipe(errLog);
  } else {
    child.stderr.resume();
  }

  const lines: string[] = [];
  const waiters: Array<(line: string) => void> = [];
  const rl = createInterface({ input: child.stdout, crlfDelay: Infinity });
  rl.on("line", (line) => {
    const next = waiters.shift();
    if (next) {
      next(line);
      return;
    }
    lines.push(line);
  });

  const io: McpChild = {
    pid: child.pid ?? 0,
    writeLine(line: string): void {
      if (!child.stdin.writable) {
        throw new HostError(E.E_UNVERIFIED, "MCP stdin is closed", "mcp");
      }
      child.stdin.write(`${line}\n`);
    },
    readLine(timeoutMs = DEFAULT_READ_MS): Promise<string> {
      if (lines.length > 0) {
        return Promise.resolve(lines.shift() ?? "");
      }
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          const idx = waiters.indexOf(onLine);
          if (idx >= 0) {
            waiters.splice(idx, 1);
          }
          reject(new HostError(E.E_TIMEOUT, "MCP read timed out", "mcp"));
        }, timeoutMs);
        const onLine = (line: string): void => {
          clearTimeout(timer);
          resolve(line);
        };
        waiters.push(onLine);
      });
    },
    async initialize(): Promise<void> {
      this.writeLine(
        JSON.stringify({
          jsonrpc: "2.0",
          id: 0,
          method: "initialize",
          params: {
            protocolVersion: "2024-11-05",
            capabilities: {},
            clientInfo: { name: "hh-godot-host", version: "0" },
          },
        }),
      );
      const line = await this.readLine(15_000);
      let parsed: unknown;
      try {
        parsed = JSON.parse(line);
      } catch {
        throw new HostError(E.E_UNVERIFIED, "MCP initialize is not JSON", "mcp");
      }
      const rec = parsed as { result?: unknown; error?: unknown };
      if (!rec.result || rec.error) {
        throw new HostError(E.E_UNVERIFIED, "MCP initialize failed", "mcp");
      }
      this.writeLine(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }));
    },
    dispose(): void {
      try {
        rl.close();
      } catch {
        /* ignore */
      }
      if (child.exitCode === null && child.signalCode === null) {
        child.kill();
      }
    },
  };
  return io;
}
