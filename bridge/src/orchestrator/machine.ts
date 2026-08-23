/** Orchestrator state machine. Sidecar driver when the plugin is down. */

import { createHash } from "node:crypto";

import { compileBrief } from "../planner/brief_compiler.js";
import { E } from "../registry/errors.js";
import { newUlid } from "../registry/ulid.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import {
  jailOrchRel,
  loadRecord,
  listRecords,
  newRecord,
  readEvidence,
  saveRecord,
  typedFail,
  viewOf,
  writeEvidence,
} from "./store.js";
import {
  MUTATING_STATES,
  ORCH_MAX_SAME_REPAIR,
  TERMINAL_STATES,
  canTransition,
  isOrchFixture,
  isOrchState,
  type OrchFixture,
  type OrchRecord,
  type OrchState,
  type OrchTask,
  type RunInput,
  type TaskCommand,
} from "./types.js";

export interface MachineCtx {
  projectRoot: string;
  commandId: string;
  now: number;
  paused: boolean;
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

function hashBrief(brief: string): string {
  return createHash("sha256").update(brief).digest("hex").slice(0, 16);
}

function enter(rec: OrchRecord, next: OrchState): { ok: true } | { ok: false; message: string } {
  if (!canTransition(rec.state, next)) {
    return { ok: false, message: `illegal transition ${rec.state} → ${next}` };
  }
  if (rec.state !== next) {
    rec.state = next;
    rec.applied_state = "";
  }
  return { ok: true };
}

function alreadyApplied(rec: OrchRecord): boolean {
  return rec.applied_state === rec.state;
}

function markApplied(rec: OrchRecord): void {
  rec.applied_state = rec.state;
}

function persist(ctx: MachineCtx, rec: OrchRecord): PluginCommandResult | undefined {
  rec.used.wall_ms = Math.max(0, ctx.now - rec.started_at_ms);
  rec.used.context_tokens = JSON.stringify(rec).length;
  const saved = saveRecord(ctx.projectRoot, rec);
  if (!saved.ok) {
    return typedFail(ctx.commandId, saved.code, saved.message, saved.path, viewOf(rec, ctx.now) as unknown as Record<string, unknown>);
  }
  return undefined;
}

function block(rec: OrchRecord, reason: string): void {
  rec.blocked_reason = reason;
  rec.state = "blocked";
}

function budgetBlock(rec: OrchRecord): string {
  if (rec.used.commands > rec.budgets.commands) {
    return "budget_commands";
  }
  if (rec.used.wall_ms > rec.budgets.wall_ms) {
    return "budget_wall";
  }
  if (rec.used.retries > rec.budgets.retries) {
    return "budget_retry";
  }
  if (rec.used.context_tokens > rec.budgets.context_tokens) {
    return "budget_context";
  }
  return "";
}

function seedFor(fixture: string, tasks: OrchTask[]): Record<string, unknown> {
  if (fixture === "infinite_repair") {
    return { always_fail: true, fail_tasks: tasks.map((t) => t.id) };
  }
  if (fixture === "dep_fail") {
    return { always_fail: false, fail_tasks: tasks.filter((t) => t.verify === "fail").map((t) => t.id) };
  }
  return { always_fail: false, fail_tasks: [] };
}

function fixtureTasks(fixture: OrchFixture): OrchTask[] {
  if (fixture === "infinite_repair") {
    return [{ id: "task_a", kind: "verify", deps: [], commands: ["orch.mark"], verify: "always_fail" }];
  }
  if (fixture === "dep_fail") {
    return [
      { id: "task_a", kind: "produce", deps: [], commands: ["orch.mark"], verify: "fail" },
      { id: "task_b", kind: "produce", deps: ["task_a"], commands: ["orch.mark"], verify: "ok" },
    ];
  }
  return [
    { id: "task_a", kind: "produce", deps: [], commands: ["orch.mark"], verify: "ok" },
    { id: "task_b", kind: "produce", deps: ["task_a"], commands: ["orch.mark"], verify: "ok" },
  ];
}

function installTasks(rec: OrchRecord, tasks: OrchTask[]): void {
  rec.tasks = tasks;
  rec.task_status = {};
  rec.task_commands = {};
  for (const task of tasks) {
    rec.task_status[task.id] = "pending";
    rec.task_commands[task.id] = task.commands.map((action) => ({
      action,
      command_id: newUlid(),
      committed: false,
    }));
  }
  rec.current_task_id = nextReady(rec) ?? tasks[0]?.id ?? "inspect_root";
}

function nextReady(rec: OrchRecord): string | undefined {
  for (const task of rec.tasks) {
    const st = rec.task_status[task.id] ?? "pending";
    if (st !== "pending") {
      continue;
    }
    const depFail = dependencyProblem(rec, task);
    if (depFail) {
      continue;
    }
    return task.id;
  }
  return undefined;
}

function dependencyProblem(rec: OrchRecord, task: OrchTask): string {
  for (const dep of task.deps) {
    const st = rec.task_status[dep] ?? "pending";
    if (st === "failed") {
      return "dependency_failed";
    }
    if (st === "cancelled") {
      return "dependency_cancelled";
    }
    if (st === "skipped") {
      return "dependency_failed";
    }
    if (st !== "ok") {
      return "dependency_unready";
    }
  }
  return "";
}

function skipDependents(rec: OrchRecord, reason: string): void {
  for (const task of rec.tasks) {
    const st = rec.task_status[task.id] ?? "pending";
    if (st !== "pending") {
      continue;
    }
    const problem = dependencyProblem(rec, task);
    if (problem === "dependency_failed" || problem === "dependency_cancelled") {
      rec.task_status[task.id] = "skipped";
      rec.blocked_reason = reason || problem;
    }
  }
}

function commitCommand(rec: OrchRecord, commandId: string): boolean {
  if (rec.committed_command_ids.includes(commandId)) {
    return false;
  }
  rec.committed_command_ids.push(commandId);
  rec.used.commands += 1;
  rec.current_command_id = commandId;
  return true;
}

function applyInspect(rec: OrchRecord, input: RunInput): void {
  rec.current_task_id = rec.current_task_id || "inspect_root";
  if (input.fixture && isOrchFixture(input.fixture)) {
    rec.fixture = input.fixture;
  }
  if (input.brief) {
    rec.brief_hash = hashBrief(input.brief);
  }
  if (input.hold_after) {
    rec.hold_after = input.hold_after;
  }
}

function applyPlan(ctx: MachineCtx, rec: OrchRecord, input: RunInput): string {
  if (rec.fixture && isOrchFixture(rec.fixture)) {
    installTasks(rec, fixtureTasks(rec.fixture));
    writeEvidence(ctx.projectRoot, rec.job_id, "plan.json", { fixture: rec.fixture, tasks: rec.tasks });
    writeEvidence(ctx.projectRoot, rec.job_id, "seed.json", seedFor(rec.fixture, rec.tasks));
    return "";
  }
  if (input.brief) {
    const plan = compileBrief({ brief: input.brief });
    if (!plan.ok || plan.tasks.length === 0) {
      return plan.error?.message ?? "plan compile failed";
    }
    const tasks: OrchTask[] = plan.tasks.map((t) => ({
      id: t.id,
      kind: t.kind,
      deps: [...t.deps],
      commands: [...t.commands],
      verify: t.verify,
    }));
    installTasks(rec, tasks);
    writeEvidence(ctx.projectRoot, rec.job_id, "plan.json", { run_id: plan.run_id, tasks: rec.tasks });
    writeEvidence(ctx.projectRoot, rec.job_id, "seed.json", seedFor("", rec.tasks));
    rec.brief_hash = hashBrief(input.brief);
    return "";
  }
  if (rec.tasks.length > 0) {
    return "";
  }
  rec.fixture = "ok_slice";
  installTasks(rec, fixtureTasks("ok_slice"));
  writeEvidence(ctx.projectRoot, rec.job_id, "plan.json", { fixture: rec.fixture, tasks: rec.tasks });
  writeEvidence(ctx.projectRoot, rec.job_id, "seed.json", seedFor(rec.fixture, rec.tasks));
  return "";
}

function applyCheckpoint(ctx: MachineCtx, rec: OrchRecord): string {
  if (alreadyApplied(rec) && rec.checkpoint_ref) {
    return "";
  }
  const cid = newUlid();
  if (commitCommand(rec, cid)) {
    rec.checkpoint_ref = writeEvidence(ctx.projectRoot, rec.job_id, "checkpoint.json", {
      command_id: cid,
      current_task_id: rec.current_task_id,
      tasks: rec.tasks.map((t) => t.id),
    });
  }
  if (!rec.checkpoint_ref) {
    rec.checkpoint_ref = `${rec.job_id}/checkpoint`;
  }
  return "";
}

function applyExecute(ctx: MachineCtx, rec: OrchRecord, input: RunInput): string {
  const tid = rec.current_task_id;
  const task = rec.tasks.find((t) => t.id === tid);
  if (!task) {
    return "current task missing";
  }
  const problem = dependencyProblem(rec, task);
  if (problem === "dependency_failed" || problem === "dependency_cancelled") {
    rec.task_status[tid] = "skipped";
    skipDependents(rec, problem);
    return problem;
  }
  rec.task_status[tid] = "running";
  const rows: TaskCommand[] = rec.task_commands[tid] ?? [];
  for (const row of rows) {
    if (rec.committed_command_ids.includes(row.command_id)) {
      row.committed = true;
      continue;
    }
    const digest = createHash("sha256")
      .update(`${row.command_id}:${task.id}:${row.action}`)
      .digest("hex");
    const rel = writeEvidence(ctx.projectRoot, rec.job_id, `tasks/${task.id}-${row.command_id}.json`, {
      task_id: task.id,
      action: row.action,
      command_id: row.command_id,
      digest,
    });
    if (!rel) {
      return "execute evidence write failed";
    }
    commitCommand(rec, row.command_id);
    row.committed = true;
  }
  rec.task_commands[tid] = rows;
  if (input.fail_task === tid) {
    rec.task_status[tid] = "failed";
  }
  return "";
}

function lastCommittedFile(rec: OrchRecord, tid: string): string {
  const rows = rec.task_commands[tid] ?? [];
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (row?.committed) {
      return `tasks/${tid}-${row.command_id}.json`;
    }
  }
  return "";
}

function applyVerify(ctx: MachineCtx, rec: OrchRecord, input: RunInput): "pass" | "fail" {
  const tid = rec.current_task_id;
  const task = rec.tasks.find((t) => t.id === tid);
  if (!task) {
    return "fail";
  }
  if ((rec.task_status[tid] ?? "") === "failed") {
    return "fail";
  }
  if (input.fail_task === tid) {
    rec.task_status[tid] = "failed";
    return "fail";
  }
  const rel = lastCommittedFile(rec, tid);
  const body = rel ? readEvidence(ctx.projectRoot, rec.job_id, rel) : undefined;
  if (!body) {
    rec.task_status[tid] = "failed";
    rec.repair.root_cause = "missing execute evidence";
    return "fail";
  }
  const expect = createHash("sha256")
    .update(`${String(body.command_id ?? "")}:${String(body.task_id ?? "")}:${String(body.action ?? "")}`)
    .digest("hex");
  if (String(body.digest ?? "") !== expect || !rec.committed_command_ids.includes(String(body.command_id ?? ""))) {
    rec.task_status[tid] = "failed";
    rec.repair.root_cause = "execute digest mismatch";
    return "fail";
  }
  const seed = readEvidence(ctx.projectRoot, rec.job_id, "seed.json") ?? {};
  const failTasks = Array.isArray(seed.fail_tasks) ? seed.fail_tasks.map((x) => String(x)) : [];
  if (seed.always_fail === true || failTasks.includes(tid)) {
    rec.task_status[tid] = "failed";
    rec.repair.root_cause = `${tid}:seed fail`;
    return "fail";
  }
  rec.task_status[tid] = "ok";
  return "pass";
}

function applyRepair(ctx: MachineCtx, rec: OrchRecord): string {
  if (alreadyApplied(rec)) {
    return "";
  }
  const key = rec.repair.error_key || "same";
  rec.repair.error_key = key;
  rec.repair.loops += 1;
  rec.used.retries += 1;
  const rel = lastCommittedFile(rec, rec.current_task_id);
  const failed = rel ? readEvidence(ctx.projectRoot, rec.job_id, rel) : undefined;
  rec.repair.root_cause = String(failed?.verify ?? rec.repair.root_cause ?? key);
  writeEvidence(ctx.projectRoot, rec.job_id, `repair/${rec.repair.loops}.json`, {
    loop: rec.repair.loops,
    error_key: key,
    root_cause: rec.repair.root_cause,
    same_error_count: rec.repair.same_error_count,
    from_task: rel,
  });
  return "";
}

function noteVerifyFail(rec: OrchRecord): void {
  const key = rec.fixture === "infinite_repair" ? "infinite_repair:same" : `verify:${rec.current_task_id}`;
  if (rec.repair.error_key === key || rec.repair.error_key === "") {
    rec.repair.error_key = key;
    rec.repair.same_error_count += 1;
  } else {
    rec.repair.error_key = key;
    rec.repair.same_error_count = 1;
  }
  rec.repair.root_cause = key;
}

function afterVerify(rec: OrchRecord, input: RunInput, verdict: "pass" | "fail"): string {
  if (verdict === "fail") {
    noteVerifyFail(rec);
    skipDependents(rec, "dependency_failed");
    const skipped = Object.values(rec.task_status).some((st) => st === "skipped");
    if (skipped || (input.fail_task && input.fail_task === rec.current_task_id)) {
      block(rec, rec.blocked_reason || "dependency_failed");
      return "blocked";
    }
    if (rec.repair.same_error_count > ORCH_MAX_SAME_REPAIR) {
      block(rec, "repair_cap");
      return "blocked";
    }
    const jumped = enter(rec, "repair");
    return jumped.ok ? "repair" : jumped.message;
  }
  const nxt = nextReady(rec);
  if (nxt) {
    rec.current_task_id = nxt;
    const jumped = enter(rec, "execute");
    return jumped.ok ? "execute" : jumped.message;
  }
  const anySkipped = Object.values(rec.task_status).some((st) => st === "skipped" || st === "failed");
  if (anySkipped) {
    block(rec, rec.blocked_reason || "dependency_failed");
    return "blocked";
  }
  const jumped = enter(rec, "review-ready");
  return jumped.ok ? "review-ready" : jumped.message;
}

function advanceOnce(ctx: MachineCtx, rec: OrchRecord, input: RunInput): string {
  if (rec.cancel_requested && !TERMINAL_STATES.has(rec.state)) {
    rec.cancelled = true;
    rec.state = "cancelled";
    rec.blocked_reason = "cancelled";
    return "cancelled";
  }
  const billed = budgetBlock(rec);
  if (billed && !TERMINAL_STATES.has(rec.state)) {
    block(rec, billed);
    return "blocked";
  }
  if (TERMINAL_STATES.has(rec.state)) {
    return rec.state;
  }
  const hold = input.hold_after || rec.hold_after || "";
  if (ctx.paused && (MUTATING_STATES.has(rec.state) || rec.state === "review-ready")) {
    return "paused";
  }

  if (rec.state === "inspect") {
    if (!alreadyApplied(rec)) {
      applyInspect(rec, input);
      markApplied(rec);
    }
    if (hold === "inspect") {
      return "hold";
    }
    const jumped = enter(rec, "plan");
    return jumped.ok ? "plan" : jumped.message;
  }
  if (rec.state === "plan") {
    if (!alreadyApplied(rec)) {
      const err = applyPlan(ctx, rec, input);
      if (err) {
        block(rec, err);
        return "blocked";
      }
      markApplied(rec);
    }
    if (hold === "plan") {
      return "hold";
    }
    if (ctx.paused) {
      return "paused";
    }
    const jumped = enter(rec, "checkpoint");
    return jumped.ok ? "checkpoint" : jumped.message;
  }
  if (rec.state === "checkpoint") {
    if (ctx.paused) {
      return "paused";
    }
    if (!alreadyApplied(rec)) {
      const err = applyCheckpoint(ctx, rec);
      if (err) {
        block(rec, err);
        return "blocked";
      }
      markApplied(rec);
    }
    if (hold === "checkpoint") {
      return "hold";
    }
    const jumped = enter(rec, "execute");
    return jumped.ok ? "execute" : jumped.message;
  }
  if (rec.state === "execute") {
    if (ctx.paused) {
      return "paused";
    }
    if (!alreadyApplied(rec)) {
      const err = applyExecute(ctx, rec, input);
      if (err === "dependency_failed" || err === "dependency_cancelled") {
        block(rec, err);
        return "blocked";
      }
      if (err) {
        block(rec, err);
        return "blocked";
      }
      markApplied(rec);
    }
    if (hold === "execute") {
      return "hold";
    }
    const jumped = enter(rec, "verify");
    return jumped.ok ? "verify" : jumped.message;
  }
  if (rec.state === "verify") {
    let verdict: "pass" | "fail";
    if (!alreadyApplied(rec)) {
      verdict = applyVerify(ctx, rec, input);
      markApplied(rec);
    } else {
      const tid = rec.current_task_id;
      verdict = rec.task_status[tid] === "ok" ? "pass" : "fail";
    }
    if (hold === "verify") {
      return "hold";
    }
    return afterVerify(rec, input, verdict);
  }
  if (rec.state === "repair") {
    if (ctx.paused) {
      return "paused";
    }
    if (rec.repair.same_error_count > ORCH_MAX_SAME_REPAIR) {
      block(rec, "repair_cap");
      return "blocked";
    }
    if (!alreadyApplied(rec)) {
      applyRepair(ctx, rec);
      markApplied(rec);
    }
    if (hold === "repair") {
      return "hold";
    }
    const jumped = enter(rec, "verify");
    return jumped.ok ? "verify" : jumped.message;
  }
  if (rec.state === "review-ready") {
    if (hold === "review-ready") {
      return "hold";
    }
    const jumped = enter(rec, "done");
    return jumped.ok ? "done" : jumped.message;
  }
  return rec.state;
}

function parseInput(params: Record<string, unknown>): RunInput | { error: string; path: string } {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(jobId)) {
    return { error: "job_id required", path: "job_id" };
  }
  const input: RunInput = { job_id: jobId };
  if (typeof params.brief === "string") {
    input.brief = params.brief;
  }
  if (typeof params.path === "string") {
    input.path = params.path;
  }
  if (typeof params.fixture === "string" && isOrchFixture(params.fixture)) {
    input.fixture = params.fixture;
  }
  if (typeof params.hold_after === "string" && isOrchState(params.hold_after)) {
    input.hold_after = params.hold_after;
  }
  if (typeof params.max_steps === "number" && Number.isInteger(params.max_steps)) {
    input.max_steps = Math.min(64, Math.max(1, params.max_steps));
  }
  if (params.resume === true) {
    input.resume = true;
  }
  if (typeof params.fail_task === "string") {
    input.fail_task = params.fail_task;
  }
  if (params.budgets && typeof params.budgets === "object" && !Array.isArray(params.budgets)) {
    const raw = params.budgets as Record<string, unknown>;
    input.budgets = {
      ...(typeof raw.commands === "number" ? { commands: raw.commands } : {}),
      ...(typeof raw.wall_ms === "number" ? { wall_ms: raw.wall_ms } : {}),
      ...(typeof raw.retries === "number" ? { retries: raw.retries } : {}),
      ...(typeof raw.context_tokens === "number" ? { context_tokens: raw.context_tokens } : {}),
    };
  }
  return input;
}

export function runJob(ctx: MachineCtx, params: Record<string, unknown>): PluginCommandResult {
  const parsed = parseInput(params);
  if ("error" in parsed) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, parsed.error, parsed.path);
  }
  const input = parsed;
  let rec = loadRecord(ctx.projectRoot, input.job_id);
  if (!rec) {
    rec = newRecord(input.job_id, ctx.now, input.budgets);
    if (input.fixture) {
      rec.fixture = input.fixture;
    }
    if (input.hold_after) {
      rec.hold_after = input.hold_after;
    }
    const entered = enter(rec, "inspect");
    if (!entered.ok) {
      return typedFail(ctx.commandId, E.E_CONFLICT, entered.message, "state");
    }
  } else if (input.budgets) {
    rec.budgets = { ...rec.budgets, ...input.budgets };
  }
  if (input.resume === true && !input.hold_after) {
    rec.hold_after = "";
  }
  if (input.hold_after) {
    rec.hold_after = input.hold_after;
  }
  if (input.fixture && !rec.fixture) {
    rec.fixture = input.fixture;
  }
  rec.heartbeat_at_ms = ctx.now;
  rec.used.wall_ms = Math.max(0, ctx.now - rec.started_at_ms);

  if (params.inject_illegal === true) {
    const jumped = enter(rec, "execute");
    if (!jumped.ok) {
      return typedFail(ctx.commandId, E.E_CONFLICT, jumped.message, "state", viewOf(rec, ctx.now) as unknown as Record<string, unknown>);
    }
  }

  if (rec.cancelled || rec.state === "cancelled") {
    rec.cancelled = true;
    rec.state = "cancelled";
    const saved = persist(ctx, rec);
    if (saved) {
      return saved;
    }
    return typedFail(
      ctx.commandId,
      E.E_POLICY,
      "job is cancelled; resume will not execute",
      "job_id",
      viewOf(rec, ctx.now) as unknown as Record<string, unknown>,
    );
  }

  if (rec.state === "done") {
    const saved = persist(ctx, rec);
    if (saved) {
      return saved;
    }
    return ok(ctx.commandId, "orchestrator_state_persisted", viewOf(rec, ctx.now) as unknown as Record<string, unknown>, false);
  }
  if (rec.state === "blocked") {
    const saved = persist(ctx, rec);
    if (saved) {
      return saved;
    }
    return typedFail(
      ctx.commandId,
      rec.blocked_reason === "repair_cap" ? E.E_POLICY : E.E_UNVERIFIED,
      rec.blocked_reason || "blocked",
      "state",
      viewOf(rec, ctx.now) as unknown as Record<string, unknown>,
    );
  }

  const maxSteps = input.max_steps ?? 32;
  let steps = 0;
  let last = rec.state;
  while (steps < maxSteps && !TERMINAL_STATES.has(rec.state)) {
    ctx.now = Date.now();
    last = rec.state;
    const outcome = advanceOnce(ctx, rec, input);
    steps += 1;
    rec.used.wall_ms = Math.max(0, ctx.now - rec.started_at_ms);
    const billed = budgetBlock(rec);
    if (billed && !TERMINAL_STATES.has(rec.state)) {
      block(rec, billed);
    }
    if (outcome === "paused") {
      const saved = persist(ctx, rec);
      if (saved) {
        return saved;
      }
      return typedFail(
        ctx.commandId,
        E.E_PAUSED,
        `pause blocks ${last}`,
        "pause",
        viewOf(rec, ctx.now) as unknown as Record<string, unknown>,
      );
    }
    if (outcome.startsWith("illegal")) {
      return typedFail(ctx.commandId, E.E_CONFLICT, outcome, "state", viewOf(rec, ctx.now) as unknown as Record<string, unknown>);
    }
    if (outcome === "hold") {
      break;
    }
    if (TERMINAL_STATES.has(rec.state)) {
      break;
    }
    if (input.hold_after && rec.state === input.hold_after) {
      break;
    }
  }

  const saved = persist(ctx, rec);
  if (saved) {
    return saved;
  }
  const after = viewOf(rec, ctx.now) as unknown as Record<string, unknown>;
  after.steps = steps;
  const endState: string = rec.state;
  if (endState === "blocked") {
    return typedFail(
      ctx.commandId,
      rec.blocked_reason === "repair_cap" ? E.E_POLICY : E.E_UNVERIFIED,
      rec.blocked_reason || "blocked",
      "state",
      after,
    );
  }
  if (endState === "cancelled") {
    return typedFail(ctx.commandId, E.E_POLICY, "job is cancelled; resume will not execute", "job_id", after);
  }
  const jailed = jailOrchRel(ctx.projectRoot, `r7w2/${rec.job_id}/state.json`);
  if (!jailed.ok) {
    return typedFail(ctx.commandId, jailed.code, jailed.message, jailed.path);
  }
  return ok(ctx.commandId, "orchestrator_state_persisted", after, true);
}

export function statusJob(ctx: MachineCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const rec = loadRecord(ctx.projectRoot, jobId);
  if (!rec) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, `job ${jobId} not found`, "job_id");
  }
  return ok(ctx.commandId, "job_status_known", viewOf(rec, ctx.now) as unknown as Record<string, unknown>, false);
}

export function listJobs(ctx: MachineCtx, params: Record<string, unknown>): PluginCommandResult {
  const limit = typeof params.limit === "number" ? Math.min(100, Math.max(1, params.limit)) : 20;
  const jobs = listRecords(ctx.projectRoot)
    .map((rec) => viewOf(rec, ctx.now))
    .slice(0, limit);
  return ok(ctx.commandId, "job_list_returned", { jobs, total: jobs.length }, false);
}

export function cancelJob(ctx: MachineCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const rec = loadRecord(ctx.projectRoot, jobId);
  if (!rec) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, `job ${jobId} not found`, "job_id");
  }
  rec.cancel_requested = true;
  rec.cancelled = true;
  rec.state = "cancelled";
  rec.blocked_reason = "cancelled";
  rec.heartbeat_at_ms = ctx.now;
  const tid = rec.current_task_id;
  if (tid && (rec.task_status[tid] === "pending" || rec.task_status[tid] === "running")) {
    rec.task_status[tid] = "cancelled";
  }
  skipDependents(rec, "dependency_cancelled");
  const saved = persist(ctx, rec);
  if (saved) {
    return saved;
  }
  return ok(ctx.commandId, "job_cancelled", viewOf(rec, ctx.now) as unknown as Record<string, unknown>, true);
}

function waitSlice(ms: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

export function waitJob(ctx: MachineCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  let rec = loadRecord(ctx.projectRoot, jobId);
  if (!rec) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, `job ${jobId} not found`, "job_id");
  }
  const timeoutSec = typeof params.timeout_sec === "number" && Number.isFinite(params.timeout_sec)
    ? Math.max(0, params.timeout_sec)
    : 0;
  const deadline = Date.now() + timeoutSec * 1000;
  let last: PluginCommandResult | undefined;
  while (!TERMINAL_STATES.has(rec.state) && !rec.cancelled) {
    ctx.now = Date.now();
    last = runJob(ctx, { job_id: jobId, resume: true, max_steps: 16 });
    rec = loadRecord(ctx.projectRoot, jobId);
    if (!rec) {
      return last;
    }
    if (TERMINAL_STATES.has(rec.state) || rec.cancelled) {
      break;
    }
    if (Date.now() >= deadline) {
      break;
    }
    waitSlice(25);
  }
  if (TERMINAL_STATES.has(rec.state)) {
    return ok(ctx.commandId, "job_terminal_state", viewOf(rec, Date.now()) as unknown as Record<string, unknown>, true);
  }
  return typedFail(
    ctx.commandId,
    E.E_TIMEOUT,
    "job has not reached a terminal state",
    "job_id",
    viewOf(rec, Date.now()) as unknown as Record<string, unknown>,
  );
}

export function illegalTransition(from: string, to: string): { ok: false; error: { code: string; message: string; path: string } } | { ok: true } {
  if (!isOrchState(from) || !isOrchState(to) || !canTransition(from, to)) {
    return {
      ok: false,
      error: { code: E.E_CONFLICT, message: `illegal transition ${from} → ${to}`, path: "state" },
    };
  }
  return { ok: true };
}

export function handleOrchAction(
  actionId: string,
  ctx: MachineCtx,
  params: Record<string, unknown>,
): PluginCommandResult {
  if (actionId === "job.run") {
    return runJob(ctx, params);
  }
  if (actionId === "job.status") {
    return statusJob(ctx, params);
  }
  if (actionId === "job.list") {
    return listJobs(ctx, params);
  }
  if (actionId === "job.cancel") {
    return cancelJob(ctx, params);
  }
  if (actionId === "job.wait") {
    return waitJob(ctx, params);
  }
  return typedFail(ctx.commandId, E.E_UNKNOWN_ACTION, `unknown orchestrator action ${actionId}`, "action");
}

