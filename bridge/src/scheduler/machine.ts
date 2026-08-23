/** Multi-agent scheduler. Coordinator owns registry/generated/progress; workers propose. */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { contentHash } from "../policy/leases.js";
import { E } from "../registry/errors.js";
import { newUlid } from "../registry/ulid.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import { pidAlive } from "../session/supervisor.js";
import { holdMutationLane, mutationLaneBusy, releaseMutationLane } from "./lane.js";
import { jobLeaseTable } from "./leases.js";
import { mergeStaged } from "./merge.js";
import {
  generatedRel,
  jailSchedRel,
  loadRecord,
  listRecords,
  newRecord,
  registryRel,
  saveRecord,
  typedFail,
  writeOwned,
  coordinatorOwnedRel,
  fileDigest,
} from "./store.js";
import {
  COORDINATOR_ID,
  DEFAULT_WORK_UNITS,
  SCHED_DIR,
  THROUGHPUT_SCENES,
  WORKER_ROLES,
  isSchedFixture,
  isSchedOp,
  isWorkerRole,
  rolesOverlap,
  type ChangeProposal,
  type SchedRecord,
  type WorkerRole,
} from "./types.js";
import { runDagWorkers, runOverlapWorkers, runThroughputParallel, runThroughputSerial } from "./workers.js";

export interface SchedCtx {
  projectRoot: string;
  commandId: string;
  now: number;
  paused: boolean;
}

const HOLD_WORKER = fileURLToPath(new URL("./role_worker.js", import.meta.url));

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

function persist(ctx: SchedCtx, rec: SchedRecord): PluginCommandResult | undefined {
  rec.heartbeat_at_ms = ctx.now;
  const saved = saveRecord(ctx.projectRoot, rec);
  if (!saved.ok) {
    return typedFail(ctx.commandId, saved.code, saved.message, saved.path);
  }
  return undefined;
}

function ensureRecord(ctx: SchedCtx, jobId: string, fixture = ""): SchedRecord {
  return loadRecord(ctx.projectRoot, jobId) ?? newRecord(jobId, ctx.now, fixture);
}

function viewOf(rec: SchedRecord): Record<string, unknown> {
  return {
    job_id: rec.job_id,
    kind: "scheduler",
    state: rec.state,
    fixture: rec.fixture,
    workers: rec.workers,
    roles: rec.workers.map((row) => row.role),
    overlap: rec.overlap,
    serial_ms: rec.serial_ms,
    parallel_ms: rec.parallel_ms,
    proposals: rec.proposals,
    progress: rec.progress,
    generated: rec.generated,
    registry: rec.registry,
    lane: rec.lane,
    blocked_reason: rec.blocked_reason,
    owner: COORDINATOR_ID,
  };
}

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function resolveRel(jobId: string, raw: string): string {
  const stripped = raw.replace(/^res:\/\//, "").replace(/\\/g, "/").replace(/^\/+/, "");
  if (stripped.startsWith(`${SCHED_DIR}/`)) {
    return stripped;
  }
  return `${SCHED_DIR}/${jobId}/${stripped}`;
}

async function runFixture(ctx: SchedCtx, rec: SchedRecord, fixture: string, units: number): Promise<void> {
  rec.fixture = fixture;
  rec.state = "running";
  if (fixture === "throughput") {
    const serial = runThroughputSerial(THROUGHPUT_SCENES, units);
    const parallel = await runThroughputParallel(THROUGHPUT_SCENES, units);
    rec.serial_ms = serial.ms;
    rec.parallel_ms = parallel.ms;
    rec.workers = [];
    rec.progress = {
      owner: COORDINATOR_ID,
      scenes: THROUGHPUT_SCENES,
      serial_ms: serial.ms,
      parallel_ms: parallel.ms,
      faster: parallel.ms < serial.ms,
      serial_digests: serial.digests,
      parallel_digests: parallel.digests,
    };
    rec.generated = { owner: COORDINATOR_ID, corpus: "independent_scenes" };
    rec.state = parallel.ms < serial.ms ? "done" : "blocked";
    rec.blocked_reason = parallel.ms < serial.ms ? "" : "parallel_not_faster";
    return;
  }
  if (fixture === "crash") {
    await crashAndReacquire(ctx, rec);
    return;
  }
  const stamps = fixture === "dag" ? await runDagWorkers(units) : await runOverlapWorkers(units);
  rec.workers = stamps;
  rec.overlap = rolesOverlap(stamps);
  rec.progress = {
    owner: COORDINATOR_ID,
    roles: stamps.map((row) => row.role),
    overlap: rec.overlap,
  };
  rec.generated = { owner: COORDINATOR_ID, worker_count: stamps.length };
  rec.registry = { owner: COORDINATOR_ID, verbs: [...WORKER_ROLES] };
  rec.state = rec.overlap || fixture === "dag" ? "done" : "blocked";
  rec.blocked_reason = rec.state === "done" ? "" : "workers_did_not_overlap";
}

async function crashAndReacquire(ctx: SchedCtx, rec: SchedRecord): Promise<void> {
  const rel = `${SCHED_DIR}/${rec.job_id}/crash_target.txt`;
  const jailed = jailSchedRel(ctx.projectRoot, rel);
  if (!jailed.ok) {
    rec.state = "blocked";
    rec.blocked_reason = jailed.message;
    return;
  }
  fs.mkdirSync(path.dirname(jailed.abs), { recursive: true });
  fs.writeFileSync(jailed.abs, "before-crash\n", "utf8");
  const ready = path.join(ctx.projectRoot, SCHED_DIR, rec.job_id, "hold.ready");
  try {
    fs.unlinkSync(ready);
  } catch {
    /* ok */
  }
  const child = spawn(
    process.execPath,
    [HOLD_WORKER, "--hold-lease", "--project", ctx.projectRoot, "--job", rec.job_id, "--rel", rel, "--writer", "dead_worker"],
    { stdio: "ignore", windowsHide: true },
  );
  const childPid = child.pid ?? 0;
  const deadline = Date.now() + 8_000;
  while (!fs.existsSync(ready) && Date.now() < deadline) {
    await sleepMs(25);
  }
  if (!fs.existsSync(ready)) {
    child.kill();
    rec.state = "blocked";
    rec.blocked_reason = "crash holder never acquired";
    return;
  }
  child.kill();
  const killDeadline = Date.now() + 8_000;
  while (childPid > 0 && pidAlive(childPid) && Date.now() < killDeadline) {
    await sleepMs(25);
  }
  if (childPid > 0 && pidAlive(childPid)) {
    child.kill("SIGKILL");
    await sleepMs(50);
  }
  const table = jobLeaseTable(ctx.projectRoot, rec.job_id);
  const held = table.peekFile(jailed.rel);
  const next = table.acquireFile("alive_worker", jailed.rel, jailed.abs, 30_000, { skipWriter: true });
  rec.progress = {
    owner: COORDINATOR_ID,
    crashed_pid: childPid,
    crashed_alive: childPid > 0 ? pidAlive(childPid) : false,
    prior_writer: held?.writer_id ?? "",
    next_writer: next.writer_id,
    released: next.writer_id === "alive_worker",
  };
  rec.generated = { owner: COORDINATOR_ID, crash: true };
  rec.state = next.writer_id === "alive_worker" ? "done" : "blocked";
  rec.blocked_reason = rec.state === "done" ? "" : "crash did not release lease";
}

async function opRun(ctx: SchedCtx, params: Record<string, unknown>): Promise<PluginCommandResult> {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const fixture = typeof params.fixture === "string" && isSchedFixture(params.fixture) ? params.fixture : "overlap";
  const units = typeof params.work_units === "number" ? params.work_units : DEFAULT_WORK_UNITS;
  const rec = ensureRecord(ctx, jobId, fixture);
  try {
    await runFixture(ctx, rec, fixture, units);
  } catch (err) {
    rec.state = "blocked";
    rec.blocked_reason = err instanceof Error ? err.message : "worker pool failed";
    persist(ctx, rec);
    return typedFail(ctx.commandId, E.E_UNVERIFIED, rec.blocked_reason, "workers", viewOf(rec));
  }
  const fail = persist(ctx, rec);
  if (fail) {
    return fail;
  }
  if (rec.state === "blocked") {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, rec.blocked_reason || "scheduler blocked", "fixture", viewOf(rec));
  }
  return ok(ctx.commandId, "scheduler_job_persisted", viewOf(rec), true);
}

function opPropose(ctx: SchedCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const writerId = typeof params.writer_id === "string" ? params.writer_id : "";
  const role = typeof params.role === "string" && isWorkerRole(params.role) ? params.role : "code_staging";
  const rawPath = typeof params.path === "string" ? params.path : "";
  const baseHash = typeof params.base_hash === "string" ? params.base_hash : "";
  const contents = typeof params.contents === "string" ? params.contents : "";
  if (!writerId || !rawPath || !baseHash || !contents) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, "propose needs writer_id/path/base_hash/contents", "params");
  }
  if (writerId === COORDINATOR_ID) {
    return typedFail(ctx.commandId, E.E_POLICY, "coordinator applies merges; workers send proposals", "writer_id");
  }
  const rel = resolveRel(jobId, rawPath);
  const rec = ensureRecord(ctx, jobId);
  const proposal: ChangeProposal = {
    proposal_id: newUlid(),
    writer_id: writerId,
    role,
    path: rel,
    base_hash: baseHash,
    contents,
    created_at_ms: ctx.now,
    status: "proposed",
  };
  rec.proposals.push(proposal);
  rec.state = "running";
  const fail = persist(ctx, rec);
  if (fail) {
    return fail;
  }
  return ok(ctx.commandId, "scheduler_job_persisted", { ...viewOf(rec), proposal }, true);
}

function opLease(ctx: SchedCtx, params: Record<string, unknown>, kind: "lease" | "heartbeat" | "release"): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const writerId = typeof params.writer_id === "string" ? params.writer_id : "";
  const rawPath = typeof params.path === "string" ? params.path : "";
  const ttlMs = typeof params.ttl_ms === "number" ? params.ttl_ms : 30_000;
  if (!writerId || !rawPath) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, "lease needs writer_id and path", "params");
  }
  const rel = resolveRel(jobId, rawPath);
  const jailed = jailSchedRel(ctx.projectRoot, rel);
  if (!jailed.ok) {
    return typedFail(ctx.commandId, jailed.code, jailed.message, jailed.path);
  }
  fs.mkdirSync(path.dirname(jailed.abs), { recursive: true });
  if (!fs.existsSync(jailed.abs)) {
    fs.writeFileSync(jailed.abs, "", "utf8");
  }
  const table = jobLeaseTable(ctx.projectRoot, jobId);
  try {
    if (kind === "release") {
      table.releaseFile(writerId, jailed.rel);
      return ok(ctx.commandId, "scheduler_job_persisted", { path: jailed.rel, writer_id: writerId, released: true }, true);
    }
    if (kind === "heartbeat") {
      const lease = table.heartbeat(writerId, jailed.rel, ttlMs);
      return ok(ctx.commandId, "scheduler_job_persisted", { lease, heartbeat: true }, true);
    }
    const lease = table.acquireFile(writerId, jailed.rel, jailed.abs, ttlMs, { skipWriter: true });
    return ok(ctx.commandId, "scheduler_job_persisted", { lease, hash: contentHash(jailed.abs) }, true);
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string }) : {};
    return typedFail(ctx.commandId, rec.code ?? E.E_LEASE, rec.message ?? "lease", jailed.rel);
  }
}

function opMerge(ctx: SchedCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const writerId = typeof params.writer_id === "string" ? params.writer_id : COORDINATOR_ID;
  const rawPath = typeof params.path === "string" ? params.path : "";
  const baseHash = typeof params.base_hash === "string" ? params.base_hash : "";
  const contents = typeof params.contents === "string" ? params.contents : "";
  const proposalId = typeof params.proposal_id === "string" ? params.proposal_id : "";
  const rec = ensureRecord(ctx, jobId);
  let rel = rawPath ? resolveRel(jobId, rawPath) : "";
  let hash = baseHash;
  let body = contents;
  if (proposalId) {
    const found = rec.proposals.find((row) => row.proposal_id === proposalId);
    if (!found) {
      return typedFail(ctx.commandId, E.E_UNVERIFIED, "proposal not found", "proposal_id");
    }
    rel = found.path;
    hash = found.base_hash;
    body = found.contents;
  }
  if (!rel || !hash || !body) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, "merge needs path/base_hash/contents or proposal_id", "params");
  }
  if (coordinatorOwnedRel(rel) && writerId !== COORDINATOR_ID) {
    return typedFail(
      ctx.commandId,
      E.E_POLICY,
      "registry/generated/progress is coordinator-owned; send a change proposal",
      rel,
    );
  }
  const merged = mergeStaged({
    projectRoot: ctx.projectRoot,
    jobId,
    writerId,
    rel,
    baseHash: hash,
    contents: body,
  });
  if (!merged.ok) {
    if (proposalId) {
      const found = rec.proposals.find((row) => row.proposal_id === proposalId);
      if (found) {
        found.status = "conflict";
      }
      rec.state = "conflict";
      rec.blocked_reason = merged.message;
      persist(ctx, rec);
    }
    return typedFail(ctx.commandId, merged.code, merged.message, merged.path, {
      merged: false,
      conflict: merged.code === E.E_CONFLICT,
    });
  }
  if (proposalId) {
    const found = rec.proposals.find((row) => row.proposal_id === proposalId);
    if (found) {
      found.status = "merged";
    }
  }
  if (rel.includes("/generated/") || writerId === COORDINATOR_ID) {
    rec.generated = { owner: COORDINATOR_ID, last: rel, hash: merged.hash };
    writeOwned(ctx.projectRoot, generatedRel(jobId, "last.json"), rec.generated);
  }
  rec.progress = { ...rec.progress, owner: COORDINATOR_ID, last_merge: rel, last_hash: merged.hash };
  rec.registry = { ...rec.registry, owner: COORDINATOR_ID };
  writeOwned(ctx.projectRoot, registryRel(jobId, "owned.json"), rec.registry);
  rec.state = "done";
  rec.lane.push({ at_ms: Date.now(), writer_id: writerId, path: rel, op: "merge" });
  const fail = persist(ctx, rec);
  if (fail) {
    return fail;
  }
  return ok(ctx.commandId, "scheduler_job_persisted", { ...viewOf(rec), merged: true, path: rel, hash: merged.hash }, true);
}

function opApply(ctx: SchedCtx, params: Record<string, unknown>): PluginCommandResult {
  return opMerge(ctx, { ...params, writer_id: typeof params.writer_id === "string" ? params.writer_id : COORDINATOR_ID });
}

function opLane(ctx: SchedCtx, params: Record<string, unknown>, op: "hold_lane" | "release_lane"): PluginCommandResult {
  const writerId = typeof params.writer_id === "string" && params.writer_id ? params.writer_id : COORDINATOR_ID;
  try {
    if (op === "hold_lane") {
      holdMutationLane(writerId);
    } else {
      releaseMutationLane();
    }
  } catch (err) {
    const rec = err && typeof err === "object" && "code" in err ? (err as { code: string; message: string; path?: string }) : undefined;
    return typedFail(ctx.commandId, rec?.code ?? E.E_BUSY, rec?.message ?? "lane", rec?.path ?? "lane");
  }
  return ok(ctx.commandId, "scheduler_job_persisted", { lane_busy: mutationLaneBusy(), op, writer_id: writerId }, true);
}

function opStatus(ctx: SchedCtx, params: Record<string, unknown>, check: string): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  const rec = loadRecord(ctx.projectRoot, jobId);
  if (!rec) {
    return typedFail(ctx.commandId, E.E_UNVERIFIED, `scheduler job ${jobId} not found`, "job_id");
  }
  return ok(ctx.commandId, check, viewOf(rec), false);
}

export function statusSchedJob(ctx: SchedCtx, params: Record<string, unknown>): PluginCommandResult {
  return opStatus(ctx, params, "job_status_known");
}

export function listSchedJobs(ctx: SchedCtx, limit: number): Record<string, unknown>[] {
  return listRecords(ctx.projectRoot)
    .slice(0, limit)
    .map((rec) => ({
      id: rec.job_id,
      kind: "scheduler",
      state: rec.state,
      fixture: rec.fixture,
      overlap: rec.overlap,
    }));
}

export async function handleScheduleAction(ctx: SchedCtx, params: Record<string, unknown>): Promise<PluginCommandResult> {
  if (ctx.paused) {
    return typedFail(ctx.commandId, E.E_PAUSED, "mutation gate is paused", "pause");
  }
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  if (!jobId) {
    return typedFail(ctx.commandId, E.E_MISSING_REQUIRED, "job_id required", "params.job_id");
  }
  const op = typeof params.op === "string" ? params.op : "";
  if (!isSchedOp(op)) {
    return typedFail(ctx.commandId, E.E_INVALID_TYPE, "unknown scheduler op", "params.op");
  }
  if (op === "run") {
    return opRun(ctx, params);
  }
  if (op === "propose") {
    return opPropose(ctx, params);
  }
  if (op === "lease" || op === "heartbeat" || op === "release") {
    return opLease(ctx, params, op);
  }
  if (op === "merge") {
    return opMerge(ctx, params);
  }
  if (op === "apply") {
    return opApply(ctx, params);
  }
  if (op === "hold_lane" || op === "release_lane") {
    return opLane(ctx, params, op);
  }
  return opStatus(ctx, params, "scheduler_job_persisted");
}

export function peekFileHash(projectRoot: string, rawPath: string): string {
  const stripped = rawPath.replace(/^res:\/\//, "").replace(/\\/g, "/");
  const jailed = jailSchedRel(projectRoot, stripped);
  if (!jailed.ok) {
    return "";
  }
  return fileDigest(jailed.abs);
}

export function isSchedRole(value: string): value is WorkerRole {
  return isWorkerRole(value);
}
