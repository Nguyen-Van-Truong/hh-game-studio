import { E, HostError } from "./errors.js";
import type { ToolResult } from "./executor.js";
import { SESSION_MS, statePath } from "./paths.js";
import { readJsonFile, writeJsonAtomic } from "./persist.js";
import { stripSecrets } from "./redact.js";

export type HostMode = "persistent" | "interactive";
export type HostPhase =
  | "running"
  | "held_after_decision"
  | "awaiting_model"
  | "done"
  | "failed"
  | "cancelled";

export interface InFlight {
  tool: string;
  action: string;
  params: Record<string, unknown>;
  command_id: string;
  task_id: string;
}

export interface ToolRecord {
  task_id: string;
  command_id: string;
  tool: string;
  action: string;
  result: ToolResult;
}

export interface HostState {
  session_id: string;
  task_id: string;
  command_id: string;
  started_at: number;
  deadline_at: number;
  heartbeat_at: number;
  session_ms: number;
  phase: HostPhase;
  mode: HostMode;
  provider: string;
  model: string;
  budget: { max_steps: number; used_steps: number };
  cancelled: boolean;
  compacted: boolean;
  plan: { summary: string };
  context_summary: string;
  tools: ToolRecord[];
  transcript: unknown[];
  writer_pid: number;
  persist_path: string;
  inflight?: InFlight;
  wakeup_at?: number;
  handoff?: { from_pid: number; to_pid: number; at: number };
}

export function newHostState(input: {
  session_id: string;
  task_id: string;
  command_id: string;
  mode: HostMode;
  provider: string;
  model: string;
  max_steps: number;
  persist_path: string;
  now?: number;
}): HostState {
  const now = input.now ?? Date.now();
  return {
    session_id: input.session_id,
    task_id: input.task_id,
    command_id: input.command_id,
    started_at: now,
    deadline_at: now + SESSION_MS,
    heartbeat_at: now,
    session_ms: SESSION_MS,
    phase: "running",
    mode: input.mode,
    provider: input.provider,
    model: input.model,
    budget: { max_steps: input.max_steps, used_steps: 0 },
    cancelled: false,
    compacted: false,
    plan: { summary: "host task" },
    context_summary: `task=${input.task_id} command=${input.command_id} plan=host task`,
    tools: [],
    transcript: [],
    writer_pid: process.pid,
    persist_path: input.persist_path,
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  throw new HostError(E.E_POLICY, "host state is not an object", "session");
}

function requireString(rec: Record<string, unknown>, key: string): string {
  const v = rec[key];
  if (typeof v !== "string" || v === "") {
    throw new HostError(E.E_POLICY, `host state missing ${key}`, key);
  }
  return v;
}

function requireNumber(rec: Record<string, unknown>, key: string): number {
  const v = rec[key];
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new HostError(E.E_POLICY, `host state missing ${key}`, key);
  }
  return v;
}

export function parseHostState(value: unknown): HostState {
  const rec = asRecord(stripSecrets(value));
  const budgetRec = asRecord(rec.budget ?? {});
  const planRec = asRecord(rec.plan ?? { summary: "host task" });
  const toolsRaw = Array.isArray(rec.tools) ? rec.tools : [];
  const tools: ToolRecord[] = [];
  for (const row of toolsRaw) {
    const item = asRecord(row);
    const result = item.result;
    if (result === null || typeof result !== "object") {
      throw new HostError(E.E_POLICY, "tool record missing result", "tools");
    }
    tools.push({
      task_id: requireString(item, "task_id"),
      command_id: requireString(item, "command_id"),
      tool: requireString(item, "tool"),
      action: requireString(item, "action"),
      result: result as ToolResult,
    });
  }
  const state: HostState = {
    session_id: requireString(rec, "session_id"),
    task_id: requireString(rec, "task_id"),
    command_id: requireString(rec, "command_id"),
    started_at: requireNumber(rec, "started_at"),
    deadline_at: requireNumber(rec, "deadline_at"),
    heartbeat_at: requireNumber(rec, "heartbeat_at"),
    session_ms: requireNumber(rec, "session_ms"),
    phase: requireString(rec, "phase") as HostPhase,
    mode: requireString(rec, "mode") as HostMode,
    provider: requireString(rec, "provider"),
    model: requireString(rec, "model"),
    budget: {
      max_steps: requireNumber(budgetRec, "max_steps"),
      used_steps: requireNumber(budgetRec, "used_steps"),
    },
    cancelled: rec.cancelled === true,
    compacted: rec.compacted === true,
    plan: { summary: typeof planRec.summary === "string" ? planRec.summary : "host task" },
    context_summary: typeof rec.context_summary === "string" ? rec.context_summary : "",
    tools,
    transcript: Array.isArray(rec.transcript) ? rec.transcript : [],
    writer_pid: typeof rec.writer_pid === "number" ? rec.writer_pid : 0,
    persist_path: requireString(rec, "persist_path"),
  };
  if (rec.inflight !== null && typeof rec.inflight === "object") {
    const inf = asRecord(rec.inflight);
    state.inflight = {
      tool: requireString(inf, "tool"),
      action: requireString(inf, "action"),
      params:
        inf.params !== null && typeof inf.params === "object" && !Array.isArray(inf.params)
          ? (inf.params as Record<string, unknown>)
          : {},
      command_id: requireString(inf, "command_id"),
      task_id: requireString(inf, "task_id"),
    };
  }
  if (typeof rec.wakeup_at === "number") {
    state.wakeup_at = rec.wakeup_at;
  }
  if (rec.handoff !== null && typeof rec.handoff === "object") {
    const h = asRecord(rec.handoff);
    state.handoff = {
      from_pid: requireNumber(h, "from_pid"),
      to_pid: requireNumber(h, "to_pid"),
      at: requireNumber(h, "at"),
    };
  }
  return state;
}

export function saveHostState(state: HostState): void {
  writeJsonAtomic(state.persist_path, state);
}

export function loadHostState(sessionId: string): HostState {
  const file = statePath(sessionId);
  const state = parseHostState(readJsonFile(file));
  if (state.session_id !== sessionId) {
    throw new HostError(E.E_POLICY, "session_id mismatch on disk", "session_id");
  }
  return state;
}

export function compactState(state: HostState): HostState {
  const next: HostState = {
    ...state,
    compacted: true,
    transcript: [],
    context_summary: `task=${state.task_id} command=${state.command_id} plan=${state.plan.summary}`,
    heartbeat_at: Date.now(),
  };
  return next;
}

export function assertRunnable(state: HostState, now = Date.now()): void {
  if (state.cancelled) {
    throw new HostError(E.E_CANCELLED, "host session cancelled", "cancel");
  }
  if (now > state.deadline_at) {
    throw new HostError(E.E_TIMEOUT, "90-minute host session expired", "deadline");
  }
  if (state.budget.used_steps >= state.budget.max_steps) {
    throw new HostError(E.E_POLICY, "host budget exhausted", "budget");
  }
}

export function pidAlive(pid: number): boolean {
  if (pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}
