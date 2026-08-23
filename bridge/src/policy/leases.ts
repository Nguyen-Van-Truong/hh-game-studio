/** One project writer + per-file/scene leases with TTL and hash drift detection. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { E, typedError } from "../registry/errors.js";
import { pidAlive } from "../session/supervisor.js";

export const DEFAULT_LEASE_TTL_MS = 30_000;

export interface WriterLock {
  writer_id: string;
  expires_at: number;
  pid: number;
}

export interface FileLease {
  writer_id: string;
  hash: string;
  expires_at: number;
  rel: string;
  pid: number;
  heartbeat_at: number;
}

export interface LeaseTableOptions {
  /** Relative dir under project root. Default `.hh-agent` (R2-WP5). */
  dir?: string;
}

function nowMs(): number {
  return Date.now();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function contentHash(absPath: string): string {
  try {
    if (!fs.existsSync(absPath) || !fs.statSync(absPath).isFile()) {
      return "missing";
    }
    return createHash("sha256").update(fs.readFileSync(absPath)).digest("hex");
  } catch {
    return "missing";
  }
}

function readJson(file: string): unknown {
  if (!fs.existsSync(file)) {
    return undefined;
  }
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return undefined;
  }
}

function atomicWrite(file: string, body: string): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, body, { encoding: "utf8" });
  fs.renameSync(tmp, file);
}

function sleepMs(ms: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function fileStale(held: FileLease, now: number, currentHash?: string): boolean {
  if (held.expires_at <= now) {
    return true;
  }
  // Dead pid is a crash only when the bytes still match. Hash drift is human-edit / E_CONFLICT.
  if (held.pid > 0 && !pidAlive(held.pid) && (currentHash === undefined || currentHash === held.hash)) {
    return true;
  }
  return false;
}

export class LeaseTable {
  readonly projectRoot: string;
  readonly writerPath: string;
  readonly filesPath: string;

  constructor(projectRoot: string, opts?: LeaseTableOptions) {
    this.projectRoot = projectRoot;
    const dir = path.join(projectRoot, opts?.dir ?? ".hh-agent");
    this.writerPath = path.join(dir, "writer.lock");
    this.filesPath = path.join(dir, "file-leases.json");
  }

  private withFilesLock<T>(fn: () => T): T {
    const lock = `${this.filesPath}.lock`;
    fs.mkdirSync(path.dirname(lock), { recursive: true });
    const deadline = nowMs() + 2_000;
    for (;;) {
      try {
        fs.writeFileSync(lock, `${process.pid}\n`, { encoding: "utf8", flag: "wx" });
        break;
      } catch {
        let holder = 0;
        try {
          holder = Number.parseInt(fs.readFileSync(lock, "utf8").trim(), 10);
        } catch {
          holder = 0;
        }
        if (holder > 0 && !pidAlive(holder)) {
          try {
            fs.unlinkSync(lock);
          } catch {
            /* retry */
          }
        } else if (nowMs() >= deadline) {
          throw typedError(E.E_BUSY, "file lease table busy", "lease");
        } else {
          sleepMs(5);
        }
      }
    }
    try {
      return fn();
    } finally {
      try {
        fs.unlinkSync(lock);
      } catch {
        /* ignore */
      }
    }
  }

  private readWriter(): WriterLock | undefined {
    const raw = readJson(this.writerPath);
    if (!isRecord(raw) || typeof raw.writer_id !== "string") {
      return undefined;
    }
    const expires = typeof raw.expires_at === "number" ? raw.expires_at : 0;
    const pid = typeof raw.pid === "number" ? raw.pid : 0;
    return { writer_id: raw.writer_id, expires_at: expires, pid };
  }

  private readFiles(): Record<string, FileLease> {
    const raw = readJson(this.filesPath);
    if (!isRecord(raw)) {
      return {};
    }
    const out: Record<string, FileLease> = {};
    for (const [rel, value] of Object.entries(raw)) {
      if (!isRecord(value) || typeof value.writer_id !== "string" || typeof value.hash !== "string") {
        continue;
      }
      out[rel] = {
        writer_id: value.writer_id,
        hash: value.hash,
        expires_at: typeof value.expires_at === "number" ? value.expires_at : 0,
        rel,
        pid: typeof value.pid === "number" ? value.pid : 0,
        heartbeat_at: typeof value.heartbeat_at === "number" ? value.heartbeat_at : 0,
      };
    }
    return out;
  }

  acquireWriter(writerId: string, ttlMs = DEFAULT_LEASE_TTL_MS): WriterLock {
    fs.mkdirSync(path.dirname(this.writerPath), { recursive: true });
    const existing = this.readWriter();
    const now = nowMs();
    if (existing && existing.expires_at > now && existing.writer_id !== writerId) {
      if (existing.pid > 0 && !pidAlive(existing.pid)) {
        try {
          fs.unlinkSync(this.writerPath);
        } catch {
          /* stale lock */
        }
      } else {
        throw typedError(E.E_BUSY, "project writer lease held by another actor", "lease");
      }
    }
    const lock: WriterLock = { writer_id: writerId, expires_at: now + ttlMs, pid: process.pid };
    if (!existing || existing.expires_at <= now) {
      try {
        fs.writeFileSync(this.writerPath, `${JSON.stringify(lock)}\n`, { encoding: "utf8", flag: "wx" });
        return lock;
      } catch {
        const raced = this.readWriter();
        if (raced && raced.expires_at > now && raced.writer_id !== writerId) {
          throw typedError(E.E_BUSY, "project writer lease held by another actor", "lease");
        }
        if (raced && raced.writer_id !== writerId) {
          try {
            fs.unlinkSync(this.writerPath);
          } catch {
            /* continue */
          }
          try {
            fs.writeFileSync(this.writerPath, `${JSON.stringify(lock)}\n`, { encoding: "utf8", flag: "wx" });
            return lock;
          } catch {
            throw typedError(E.E_BUSY, "project writer lease held by another actor", "lease");
          }
        }
      }
    }
    atomicWrite(this.writerPath, `${JSON.stringify(lock)}\n`);
    return lock;
  }

  acquireFile(
    writerId: string,
    rel: string,
    abs: string,
    ttlMs = DEFAULT_LEASE_TTL_MS,
    opts: { allowHashRefresh?: boolean; skipWriter?: boolean } = {},
  ): FileLease {
    if (opts.skipWriter !== true) {
      this.acquireWriter(writerId, ttlMs);
    }
    return this.withFilesLock(() => {
      const files = this.readFiles();
      const now = nowMs();
      const current = contentHash(abs);
      const held = files[rel];
      if (held && held.writer_id !== writerId && !fileStale(held, now, current)) {
        throw typedError(E.E_LEASE, "file/scene lease held by another writer", rel);
      }
      if (held && !fileStale(held, now, current) && held.hash !== current && opts.allowHashRefresh !== true) {
        throw typedError(E.E_CONFLICT, "human-edit drift on leased file", rel);
      }
      const lease: FileLease = {
        writer_id: writerId,
        hash: current,
        expires_at: now + ttlMs,
        rel,
        pid: process.pid,
        heartbeat_at: now,
      };
      files[rel] = lease;
      atomicWrite(this.filesPath, `${JSON.stringify(files)}\n`);
      return lease;
    });
  }

  heartbeat(writerId: string, rel: string, ttlMs = DEFAULT_LEASE_TTL_MS): FileLease {
    return this.withFilesLock(() => {
      const files = this.readFiles();
      const now = nowMs();
      const held = files[rel];
      if (!held || held.writer_id !== writerId || fileStale(held, now)) {
        throw typedError(E.E_LEASE, "cannot heartbeat a file lease this writer does not hold", rel);
      }
      const lease: FileLease = {
        ...held,
        expires_at: now + ttlMs,
        pid: process.pid,
        heartbeat_at: now,
      };
      files[rel] = lease;
      atomicWrite(this.filesPath, `${JSON.stringify(files)}\n`);
      return lease;
    });
  }

  releaseFile(writerId: string, rel: string): void {
    this.withFilesLock(() => {
      const files = this.readFiles();
      const held = files[rel];
      if (!held) {
        return;
      }
      const now = nowMs();
      if (held.writer_id !== writerId && !fileStale(held, now)) {
        throw typedError(E.E_LEASE, "cannot release a file lease held by another writer", rel);
      }
      delete files[rel];
      atomicWrite(this.filesPath, `${JSON.stringify(files)}\n`);
    });
  }

  releaseWriter(writerId: string): void {
    const existing = this.readWriter();
    if (!existing) {
      return;
    }
    const now = nowMs();
    if (
      existing.writer_id !== writerId &&
      existing.expires_at > now &&
      !(existing.pid > 0 && !pidAlive(existing.pid))
    ) {
      throw typedError(E.E_BUSY, "project writer lease held by another actor", "lease");
    }
    try {
      fs.unlinkSync(this.writerPath);
    } catch {
      /* gone */
    }
  }

  assertUnchanged(rel: string, abs: string): void {
    const files = this.readFiles();
    const held = files[rel];
    if (!held) {
      return;
    }
    const current = contentHash(abs);
    if (held.hash !== current) {
      throw typedError(E.E_CONFLICT, "human-edit drift on leased file", rel);
    }
  }

  peekWriter(): WriterLock | undefined {
    return this.readWriter();
  }

  peekFile(rel: string): FileLease | undefined {
    return this.readFiles()[rel];
  }

  noteWritten(writerId: string, rel: string, abs: string, ttlMs = DEFAULT_LEASE_TTL_MS): FileLease {
    return this.withFilesLock(() => {
      const files = this.readFiles();
      const now = nowMs();
      const lease: FileLease = {
        writer_id: writerId,
        hash: contentHash(abs),
        expires_at: now + ttlMs,
        rel,
        pid: process.pid,
        heartbeat_at: now,
      };
      files[rel] = lease;
      atomicWrite(this.filesPath, `${JSON.stringify(files)}\n`);
      return lease;
    });
  }
}
