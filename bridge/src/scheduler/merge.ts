/** Merge staged code only when the on-disk base hash still matches. No blind auto-resolve. */

import fs from "node:fs";

import { E } from "../registry/errors.js";
import { withMutationLane } from "./lane.js";
import { jobLeaseTable } from "./leases.js";
import { atomicWriteUtf8, coordinatorOwnedRel, fileDigest, jailSchedRel } from "./store.js";
import { COORDINATOR_ID } from "./types.js";

export function mergeStaged(opts: {
  projectRoot: string;
  jobId: string;
  writerId: string;
  rel: string;
  baseHash: string;
  contents: string;
}):
  | { ok: true; rel: string; hash: string; merged: true }
  | { ok: false; code: string; message: string; path: string; merged: false } {
  if (coordinatorOwnedRel(opts.rel) && opts.writerId !== COORDINATOR_ID) {
    return {
      ok: false,
      code: E.E_POLICY,
      message: "registry/generated/progress is coordinator-owned; send a change proposal",
      path: opts.rel,
      merged: false,
    };
  }
  const jailed = jailSchedRel(opts.projectRoot, opts.rel);
  if (!jailed.ok) {
    return { ok: false, code: jailed.code, message: jailed.message, path: jailed.path, merged: false };
  }
  const current = fileDigest(jailed.abs);
  if (current !== opts.baseHash) {
    return {
      ok: false,
      code: E.E_CONFLICT,
      message: "base hash mismatch; pause/resync, not auto-resolve",
      path: jailed.rel,
      merged: false,
    };
  }
  const table = jobLeaseTable(opts.projectRoot, opts.jobId);
  try {
    table.acquireFile(opts.writerId, jailed.rel, jailed.abs, undefined, { skipWriter: true });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string }) : {};
    return {
      ok: false,
      code: rec.code ?? E.E_LEASE,
      message: rec.message ?? "lease",
      path: jailed.rel,
      merged: false,
    };
  }
  try {
    withMutationLane(opts.writerId, jailed.rel, "merge", () => {
      if (!atomicWriteUtf8(jailed.abs, opts.contents)) {
        throw new Error("atomic write failed");
      }
      table.noteWritten(opts.writerId, jailed.rel, jailed.abs);
    });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string }) : {};
    return {
      ok: false,
      code: rec.code ?? E.E_BUSY,
      message: rec.message ?? "mutation lane",
      path: jailed.rel,
      merged: false,
    };
  }
  if (!fs.existsSync(jailed.abs)) {
    return { ok: false, code: E.E_UNVERIFIED, message: "merge did not persist", path: jailed.rel, merged: false };
  }
  return { ok: true, rel: jailed.rel, hash: fileDigest(jailed.abs), merged: true };
}
