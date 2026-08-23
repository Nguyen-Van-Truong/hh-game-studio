/** Atomic persist for orchestrator records. Jail: r7w2/ only, no .. / addons / .hh-agent. */

import fs from "node:fs";
import path from "node:path";

import { jailProjectPath } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";
import {
  DEFAULT_BUDGETS,
  ORCH_DIR,
  ORCH_HEARTBEAT_STALE_MS,
  ORCH_SCHEMA,
  type OrchRecord,
  type OrchView,
  type TaskCommand,
  type TaskRunStatus,
} from "./types.js";

export function jobIdOk(jobId: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(jobId);
}

export function jailOrchRel(projectRoot: string, rel: string): { ok: true; abs: string; rel: string } | { ok: false; code: string; message: string; path: string } {
  const p = rel.replace(/\\/g, "/").replace(/^\/+/, "");
  if (p.includes("..") || p.includes("addons/") || p.startsWith(".hh-agent") || p.includes("/.hh-agent")) {
    return { ok: false, code: E.E_PATH, message: "orchestrator path escapes jail", path: rel };
  }
  if (!p.startsWith(`${ORCH_DIR}/`)) {
    return { ok: false, code: E.E_PATH, message: "orchestrator writes only under r7w2/", path: rel };
  }
  const jailed = jailProjectPath(projectRoot, p, { forWrite: true });
  if (!jailed.ok) {
    return { ok: false, code: jailed.error.code, message: jailed.error.message, path: jailed.error.path };
  }
  return { ok: true, abs: jailed.abs, rel: jailed.rel };
}

function atomicWriteUtf8(absPath: string, text: string): boolean {
  fs.mkdirSync(path.dirname(absPath), { recursive: true });
  const tmp = `${absPath}.tmp`;
  fs.writeFileSync(tmp, text, "utf8");
  try {
    fs.unlinkSync(absPath);
  } catch {
    /* dest may not exist */
  }
  try {
    fs.renameSync(tmp, absPath);
    return true;
  } catch {
    return false;
  }
}

export function stateRel(jobId: string): string {
  return `${ORCH_DIR}/${jobId}/state.json`;
}

export function loadRecord(projectRoot: string, jobId: string): OrchRecord | undefined {
  if (!jobIdOk(jobId)) {
    return undefined;
  }
  const jailed = jailOrchRel(projectRoot, stateRel(jobId));
  if (!jailed.ok || !fs.existsSync(jailed.abs)) {
    return undefined;
  }
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(jailed.abs, "utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return undefined;
    }
    const rec = parsed as OrchRecord;
    if (rec.schema !== ORCH_SCHEMA || rec.job_id !== jobId) {
      return undefined;
    }
    if (typeof rec.applied_state !== "string") {
      rec.applied_state = "";
    }
    return rec;
  } catch {
    return undefined;
  }
}

export function saveRecord(projectRoot: string, rec: OrchRecord): { ok: true } | { ok: false; code: string; message: string; path: string } {
  if (!jobIdOk(rec.job_id)) {
    return { ok: false, code: E.E_PATH, message: "invalid job_id", path: "job_id" };
  }
  rec.used.context_tokens = JSON.stringify(rec).length;
  const jailed = jailOrchRel(projectRoot, stateRel(rec.job_id));
  if (!jailed.ok) {
    return { ok: false, code: jailed.code, message: jailed.message, path: jailed.path };
  }
  if (!atomicWriteUtf8(jailed.abs, `${JSON.stringify(rec, null, 2)}\n`)) {
    return { ok: false, code: E.E_UNVERIFIED, message: "orchestrator persist failed", path: jailed.rel };
  }
  return { ok: true };
}

export function writeEvidence(projectRoot: string, jobId: string, relName: string, body: unknown): string {
  const rel = `${ORCH_DIR}/${jobId}/${relName}`;
  const jailed = jailOrchRel(projectRoot, rel);
  if (!jailed.ok) {
    return "";
  }
  if (!atomicWriteUtf8(jailed.abs, `${JSON.stringify(body, null, 2)}\n`)) {
    return "";
  }
  return jailed.rel;
}

export function readEvidence(projectRoot: string, jobId: string, relName: string): Record<string, unknown> | undefined {
  const rel = `${ORCH_DIR}/${jobId}/${relName}`;
  const jailed = jailOrchRel(projectRoot, rel);
  if (!jailed.ok || !fs.existsSync(jailed.abs)) {
    return undefined;
  }
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(jailed.abs, "utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return undefined;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

export function listRecords(projectRoot: string): OrchRecord[] {
  const root = path.join(projectRoot, ORCH_DIR);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    return [];
  }
  const out: OrchRecord[] = [];
  for (const name of fs.readdirSync(root)) {
    const rec = loadRecord(projectRoot, name);
    if (rec) {
      out.push(rec);
    }
  }
  return out;
}

export function emptyRepair(): OrchRecord["repair"] {
  return { error_key: "", same_error_count: 0, loops: 0, root_cause: "" };
}

export function newRecord(jobId: string, now: number, budgets?: Partial<OrchRecord["budgets"]>): OrchRecord {
  return {
    schema: ORCH_SCHEMA,
    job_id: jobId,
    state: "inspect",
    current_task_id: "inspect_root",
    current_command_id: "",
    committed_command_ids: [],
    tasks: [],
    task_status: {},
    task_commands: {},
    started_at_ms: now,
    heartbeat_at_ms: now,
    budgets: {
      commands: budgets?.commands ?? DEFAULT_BUDGETS.commands,
      wall_ms: budgets?.wall_ms ?? DEFAULT_BUDGETS.wall_ms,
      retries: budgets?.retries ?? DEFAULT_BUDGETS.retries,
      context_tokens: budgets?.context_tokens ?? DEFAULT_BUDGETS.context_tokens,
    },
    used: { commands: 0, wall_ms: 0, retries: 0, context_tokens: 0 },
    repair: emptyRepair(),
    checkpoint_ref: "",
    fixture: "",
    hold_after: "",
    blocked_reason: "",
    cancel_requested: false,
    cancelled: false,
    brief_hash: "",
    applied_state: "",
  };
}

export function viewOf(rec: OrchRecord, now: number): OrchView {
  const age = Math.max(0, now - rec.heartbeat_at_ms);
  const executed = Object.entries(rec.task_status)
    .filter(([, st]) => st === "ok" || st === "running")
    .map(([id]) => id);
  return {
    job_id: rec.job_id,
    state: rec.state,
    current_task_id: rec.current_task_id,
    current_command_id: rec.current_command_id,
    committed_command_ids: [...rec.committed_command_ids],
    heartbeat_at_ms: rec.heartbeat_at_ms,
    heartbeat_age_ms: age,
    stale: age > ORCH_HEARTBEAT_STALE_MS,
    budgets: { ...rec.budgets },
    used: { ...rec.used },
    blocked_reason: rec.blocked_reason,
    cancelled: rec.cancelled,
    fixture: rec.fixture,
    checkpoint_ref: rec.checkpoint_ref,
    repair: { ...rec.repair },
    task_status: { ...rec.task_status },
    tasks_executed: executed,
  };
}

export function typedFail(commandId: string, code: string, message: string, pathName: string, after?: Record<string, unknown>) {
  return {
    type: "result" as const,
    ok: false as const,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] as string[] },
    error: typedError(code, message, pathName),
    ...(after ? { after } : {}),
  };
}

export function cloneCommands(rows: TaskCommand[]): TaskCommand[] {
  return rows.map((row) => ({ action: row.action, command_id: row.command_id, committed: row.committed }));
}

export function statusName(value: unknown): TaskRunStatus {
  if (
    value === "pending" ||
    value === "running" ||
    value === "ok" ||
    value === "failed" ||
    value === "cancelled" ||
    value === "skipped"
  ) {
    return value;
  }
  return "pending";
}
