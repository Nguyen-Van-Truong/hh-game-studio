/** Soak compact / wake / rotate. Idle must not auto-flip blocked when state is unchanged. */

import { PINNED_VERSION_ID } from "../doctor/pin.js";
import { E } from "../registry/errors.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import {
  currentJobId,
  jailSoakRel,
  listRecords,
  loadRecord,
  newRecord,
  rotateEventsIfNeeded,
  saveRecord,
  typedFail,
  viewOf,
  writeEvidence,
} from "./store.js";
import type { SoakOp, SoakPhase, SoakRecord } from "./types.js";

export interface SoakCtx {
  projectRoot: string;
  commandId: string;
  now: number;
}

const STALE_NOT_BLOCKED = new Set(["", "unchanged", "stale", "no_change", "idle", "heartbeat"]);

function asPhase(value: unknown): SoakPhase | undefined {
  if (value === "running" || value === "idle" || value === "done" || value === "blocked") {
    return value;
  }
  return undefined;
}

function asOp(value: unknown): SoakOp {
  if (value === "note" || value === "wake" || value === "rotate" || value === "compact") {
    return value;
  }
  return "compact";
}

function mergeIds(into: string[], extra: unknown): void {
  if (!Array.isArray(extra)) {
    return;
  }
  for (const item of extra) {
    if (typeof item === "string" && item && !into.includes(item)) {
      into.push(item);
    }
  }
}

function applyParams(rec: SoakRecord, params: Record<string, unknown>, now: number): void {
  if (typeof params.session_id === "string" && params.session_id) {
    rec.session_id = params.session_id;
  }
  if (typeof params.task_id === "string" && params.task_id) {
    rec.task_id = params.task_id;
  }
  if (typeof params.command_id === "string" && params.command_id) {
    rec.command_id = params.command_id;
  }
  if (typeof params.brief === "string" && params.brief) {
    rec.brief = params.brief;
  }
  if (typeof params.context_summary === "string") {
    rec.context_summary = params.context_summary;
  }
  if (typeof params.project_hash === "string") {
    rec.project_hash = params.project_hash;
  }
  if (typeof params.scene_hash === "string") {
    rec.scene_hash = params.scene_hash;
  }
  if (typeof params.version_pin === "string" && params.version_pin) {
    rec.version_pin = params.version_pin;
  }
  mergeIds(rec.committed_command_ids, params.committed_command_ids);
  mergeIds(rec.checkpoint_refs, params.checkpoint_refs);
  if (params.progress !== null && typeof params.progress === "object" && !Array.isArray(params.progress)) {
    const p = params.progress as Record<string, unknown>;
    if (typeof p.applied === "number") {
      rec.progress.applied = p.applied;
    }
    if (typeof p.play_runs === "number") {
      rec.progress.play_runs = p.play_runs;
    }
    if (typeof p.next_step === "number") {
      rec.progress.next_step = p.next_step;
    }
    if (p.restarts !== null && typeof p.restarts === "object" && !Array.isArray(p.restarts)) {
      const r = p.restarts as Record<string, unknown>;
      if (typeof r.sidecar === "number") {
        rec.progress.restarts.sidecar = r.sidecar;
      }
      if (typeof r.editor === "number") {
        rec.progress.restarts.editor = r.editor;
      }
      if (typeof r.host === "number") {
        rec.progress.restarts.host = r.host;
      }
    }
  }
  rec.progress.applied = Math.max(rec.progress.applied, rec.committed_command_ids.length);
  rec.heartbeat_at_ms = now;
  rec.context_summary =
    rec.context_summary ||
    `task=${rec.task_id} command=${rec.command_id} brief=${rec.brief} applied=${rec.progress.applied}`;
}

function settlePhase(rec: SoakRecord, requested: SoakPhase | undefined, op: SoakOp): void {
  if (op === "wake") {
    if (rec.phase === "blocked" && STALE_NOT_BLOCKED.has(rec.blocked_reason)) {
      rec.phase = "idle";
      rec.blocked_reason = "";
    } else if (rec.phase === "blocked") {
      return;
    } else if (rec.phase !== "done") {
      rec.phase = rec.phase === "running" ? "running" : "idle";
    }
    return;
  }
  if (requested === "blocked") {
    const reason = rec.blocked_reason;
    if (STALE_NOT_BLOCKED.has(reason)) {
      rec.phase = rec.compacted ? "idle" : "running";
      rec.blocked_reason = "";
      return;
    }
    rec.phase = "blocked";
    return;
  }
  if (requested) {
    rec.phase = requested;
    rec.blocked_reason = "";
    return;
  }
  if (rec.phase === "blocked" && STALE_NOT_BLOCKED.has(rec.blocked_reason)) {
    rec.phase = rec.compacted ? "idle" : "running";
    rec.blocked_reason = "";
  }
}

function ok(commandId: string, check: string, after: Record<string, unknown>, changed: boolean): PluginCommandResult {
  return {
    type: "result",
    ok: true,
    command_id: commandId,
    changed,
    after,
    postcondition: { verified: true, checks: [check] },
  };
}

export function handleSoakAction(ctx: SoakCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  if (!jobId) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, "missing required param job_id", "params.job_id");
  }
  const jailed = jailSoakRel(ctx.projectRoot, `r7w5/${jobId}/state.json`);
  if (!jailed.ok) {
    return typedFail(ctx.commandId, jailed.code, jailed.message, jailed.path);
  }
  let rec = loadRecord(ctx.projectRoot, jobId) ?? newRecord(jobId, ctx.now);
  if (!rec.version_pin) {
    rec.version_pin = PINNED_VERSION_ID;
  }
  const op = asOp(params.op);
  if (typeof params.blocked_reason === "string") {
    rec.blocked_reason = params.blocked_reason;
  }
  applyParams(rec, params, ctx.now);
  settlePhase(rec, asPhase(params.phase), op);
  if (op === "compact") {
    rec.compacted = true;
    rec.transcript = [];
    rec.context_summary = `task=${rec.task_id} command=${rec.command_id} brief=${rec.brief} applied=${rec.progress.applied}`;
    if (rec.phase === "blocked" && STALE_NOT_BLOCKED.has(rec.blocked_reason)) {
      rec.phase = "idle";
      rec.blocked_reason = "";
    } else if (rec.phase === "running") {
      rec.phase = "idle";
    }
  }
  if (op === "rotate" || op === "compact" || op === "note") {
    rotateEventsIfNeeded(ctx.projectRoot, jobId);
  }
  const saved = saveRecord(ctx.projectRoot, rec);
  if (!saved.ok) {
    return typedFail(ctx.commandId, saved.code, saved.message, saved.path);
  }
  if (op === "compact") {
    writeEvidence(ctx.projectRoot, jobId, "compact.json", {
      job_id: rec.job_id,
      session_id: rec.session_id,
      task_id: rec.task_id,
      command_id: rec.command_id,
      compacted: true,
      checkpoint_refs: rec.checkpoint_refs,
    });
  }
  const extra =
    op === "wake" ? "soak_wake_idle" : op === "rotate" ? "soak_logs_rotated" : op === "note" ? "soak_state_persisted" : "soak_state_compacted";
  return {
    type: "result",
    ok: true,
    command_id: ctx.commandId,
    changed: true,
    after: { ...viewOf(rec) },
    postcondition: { verified: true, checks: ["soak_state_compacted", extra] },
  };
}

export function statusSoakJob(ctx: SoakCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : currentJobId(ctx.projectRoot);
  if (!jobId) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, "job not found", "job_id");
  }
  const rec = loadRecord(ctx.projectRoot, jobId);
  if (!rec) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, `job ${jobId} not found`, "job_id");
  }
  if (rec.phase === "blocked" && STALE_NOT_BLOCKED.has(rec.blocked_reason)) {
    rec.phase = rec.compacted ? "idle" : "running";
    rec.blocked_reason = "";
    rec.heartbeat_at_ms = ctx.now;
    saveRecord(ctx.projectRoot, rec);
  } else {
    rec.heartbeat_at_ms = ctx.now;
    saveRecord(ctx.projectRoot, rec);
  }
  return ok(ctx.commandId, "job_status_known", { ...viewOf(rec) }, false);
}

export function listSoakJobs(projectRoot: string): Array<Record<string, unknown>> {
  return listRecords(projectRoot).map((rec) => ({ ...viewOf(rec) }));
}
