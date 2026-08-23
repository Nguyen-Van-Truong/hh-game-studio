/** Worker-thread / CLI role. CPU work is real sha256, not a sleep pad. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { isMainThread, parentPort, threadId, workerData } from "node:worker_threads";

import { contentHash, LeaseTable } from "../policy/leases.js";
import { SCHED_DIR, type WorkerRole, type WorkerStamp } from "./types.js";

export function cpuWork(units: number, seed: string): string {
  const buf = Buffer.alloc(2048, seed);
  let digest = seed;
  for (let i = 0; i < units; i += 1) {
    buf.writeUInt32LE(i >>> 0, 0);
    digest = createHash("sha256").update(buf).update(digest).digest("hex");
  }
  return digest;
}

function arg(name: string, fallback = ""): string {
  const idx = process.argv.indexOf(name);
  if (idx < 0) {
    return fallback;
  }
  return process.argv[idx + 1] ?? fallback;
}

function holdLease(): void {
  const projectRoot = arg("--project");
  const jobId = arg("--job");
  const rel = arg("--rel");
  const writerId = arg("--writer", "dead_worker");
  const ttlMs = Number.parseInt(arg("--ttl", "60000"), 10);
  if (!projectRoot || !jobId || !rel) {
    process.exit(2);
  }
  const table = new LeaseTable(projectRoot, { dir: path.posix.join(SCHED_DIR, jobId, "locks") });
  const abs = path.join(projectRoot, rel.replace(/\//g, path.sep));
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  if (!fs.existsSync(abs)) {
    fs.writeFileSync(abs, "hold\n", "utf8");
  }
  table.acquireFile(writerId, rel.replace(/\\/g, "/"), abs, Number.isFinite(ttlMs) ? ttlMs : 60_000, {
    skipWriter: true,
  });
  const ready = path.join(projectRoot, SCHED_DIR, jobId, "hold.ready");
  fs.mkdirSync(path.dirname(ready), { recursive: true });
  fs.writeFileSync(ready, `${process.pid}\n${contentHash(abs)}\n`, "utf8");
  setInterval(() => {
    try {
      table.heartbeat(writerId, rel.replace(/\\/g, "/"), Number.isFinite(ttlMs) ? ttlMs : 60_000);
    } catch {
      /* released */
    }
  }, 250);
}

function runRole(): WorkerStamp {
  const role = String((workerData as { role?: string }).role ?? "research") as WorkerRole;
  const units = Number((workerData as { units?: number }).units ?? 8000);
  const seed = String((workerData as { seed?: string }).seed ?? role);
  const started_at_ms = Date.now();
  const digest = cpuWork(units, seed);
  return {
    role,
    started_at_ms,
    ended_at_ms: Date.now(),
    digest,
    thread_id: threadId,
  };
}

if (!isMainThread) {
  parentPort?.postMessage(runRole());
} else if (process.argv.includes("--hold-lease")) {
  holdLease();
}
