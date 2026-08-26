/** Capability-lock / protocol / schema mismatch → Observe/Doctor only (S7). */

import fs from "node:fs";
import path from "node:path";

import { PINNED_VERSION_ID, versionIsRefused } from "../doctor/pin.js";
import { PROTOCOL, REGISTRY_VERSION } from "../registry/types.js";

export interface CompatLockAssessment {
  mismatch: boolean;
  reason: string;
  protocol: string;
  schema: string;
  lockVersionId: string;
}

function readTextIfFile(abs: string): string {
  try {
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      return fs.readFileSync(abs, "utf8").trim();
    }
  } catch {
    /* ignore */
  }
  return "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function assessCompatLock(projectRoot: string): CompatLockAssessment {
  const reasons: string[] = [];
  const protocol = readTextIfFile(path.join(projectRoot, ".hh-agent", "protocol"));
  const schema = readTextIfFile(path.join(projectRoot, ".hh-agent", "schema-version"));
  let lockVersionId = "";
  const lockPath = path.join(projectRoot, ".hh-agent", "capability-lock.json");
  const raw = readTextIfFile(lockPath);
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isRecord(parsed) && isRecord(parsed.godot) && typeof parsed.godot.version_id === "string") {
        lockVersionId = parsed.godot.version_id;
      }
    } catch {
      reasons.push("capability-lock is not valid JSON");
    }
  }
  if (protocol && protocol !== PROTOCOL) {
    reasons.push(`protocol ${protocol} != ${PROTOCOL}`);
  }
  if (schema && schema !== REGISTRY_VERSION) {
    reasons.push(`schema ${schema} != ${REGISTRY_VERSION}`);
  }
  if (lockVersionId && (versionIsRefused(lockVersionId) || lockVersionId !== PINNED_VERSION_ID)) {
    reasons.push(`capability-lock ${lockVersionId} != pin ${PINNED_VERSION_ID}`);
  }
  return {
    mismatch: reasons.length > 0,
    reason:
      reasons.length > 0
        ? `${reasons.join("; ")}; Observe/Doctor only`
        : "lock matches pin",
    protocol: protocol || PROTOCOL,
    schema: schema || REGISTRY_VERSION,
    lockVersionId,
  };
}

export function observeOnlyReason(projectRoot: string | undefined): string {
  if (!projectRoot) {
    return "";
  }
  const assessed = assessCompatLock(projectRoot);
  return assessed.mismatch ? assessed.reason : "";
}
