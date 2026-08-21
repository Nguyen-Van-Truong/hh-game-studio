/** Test harness for policy, jail, leases, checkpoint, and Pause ACK. */

import { performance } from "node:perf_hooks";

import { E } from "../registry/errors.js";
import { PROTOCOL } from "../registry/types.js";
import { executeCommand, inspectRow, type LedgerBound, type LedgerRuntime } from "../ledger/execute.js";
import { openLedger } from "../ledger/store.js";
import { ProcessSupervisor } from "../session/supervisor.js";
import { isNoopEnvelope, unverifiedResult, type PluginCommandResult } from "../transport/plugin_rpc.js";
import { ApprovalBinder, projectRevision } from "./approve.js";
import { assertAgentProcess, assertLoopbackHost } from "./allowlist.js";
import { createRecoveryCheckpoint, restoreCheckpoint } from "./checkpoint.js";
import { canonicalRequestHash } from "../ledger/hash.js";
import { extractTargetPaths, jailProjectPath } from "./jail.js";
import { LeaseTable } from "./leases.js";
import { PauseGate } from "./pause.js";
import { DEFAULT_POLICY, normalizePolicy } from "./profiles.js";
import { runMutationGate, type PolicyServices } from "./engine.js";

function write(obj: unknown): void {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function fail(err: unknown): never {
  const code =
    err && typeof err === "object" && "code" in err && typeof err.code === "string" ? err.code : "E_FAIL";
  const message = err instanceof Error ? err.message : "harness failed";
  write({ ok: false, error: { code, message } });
  process.exitCode = 1;
  throw err;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readJsonArg(): Record<string, unknown> {
  const raw = process.argv[3] ?? "{}";
  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed)) {
    fail(new Error("payload must be a JSON object"));
  }
  return parsed;
}

function str(rec: Record<string, unknown>, key: string, fallback = ""): string {
  const value = rec[key];
  return typeof value === "string" ? value : fallback;
}

function num(rec: Record<string, unknown>, key: string, fallback: number): number {
  const value = rec[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

const pauseSingleton = new PauseGate();

function servicesOf(payload: Record<string, unknown>): PolicyServices {
  const projectRoot = str(payload, "project_root");
  if (!projectRoot) {
    fail(new Error("project_root required"));
  }
  return {
    projectRoot,
    writerId: str(payload, "writer_id", str(payload, "actor", "writer-a")),
    pause: pauseSingleton,
    leases: new LeaseTable(projectRoot),
    approvals: new ApprovalBinder(projectRoot),
    approvalToken: str(payload, "approval"),
    revision: str(payload, "revision") || projectRevision(projectRoot),
    checkpointFail: payload.checkpoint_fail === true,
  };
}

function mockRuntime(policy: PolicyServices | undefined): LedgerRuntime {
  return {
    pluginConnected: () => true,
    dispatch: async (envelope) => {
      const commandId = typeof envelope.command_id === "string" ? envelope.command_id : "";
      if (isNoopEnvelope(envelope)) {
        return {
          type: "result",
          ok: true,
          command_id: commandId,
          changed: false,
          postcondition: { verified: true, checks: ["noop"] },
        };
      }
      return unverifiedResult(commandId, "not dispatched");
    },
    readPostcondition: async (commandId) => ({
      command_id: commandId,
      found: false,
      ok: false,
      postcondition: { verified: false, checks: [] },
    }),
    ...(policy ? { policy } : {}),
  };
}

function jailCmd(payload: Record<string, unknown>): void {
  const result = jailProjectPath(str(payload, "project_root"), str(payload, "path"), {
    forWrite: payload.for_write !== false,
  });
  if (!result.ok) {
    write({ ok: false, error: result.error });
    return;
  }
  write({ ok: true, abs: result.abs, rel: result.rel });
}

function writerCmd(payload: Record<string, unknown>): void {
  const table = new LeaseTable(str(payload, "project_root"));
  try {
    const lock = table.acquireWriter(str(payload, "writer_id", "writer-a"), num(payload, "ttl_ms", 30_000));
    write({ ok: true, writer: lock });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string }) : {};
    write({
      ok: false,
      error: { code: rec.code ?? E.E_BUSY, message: rec.message ?? "writer", path: "lease" },
    });
  }
}

async function writerHold(payload: Record<string, unknown>): Promise<void> {
  const table = new LeaseTable(str(payload, "project_root"));
  const lock = table.acquireWriter(str(payload, "writer_id", "writer-a"), num(payload, "ttl_ms", 30_000));
  write({ ok: true, writer: lock, holding: true });
  const holdMs = num(payload, "hold_ms", 1_500);
  await new Promise<void>((resolve) => {
    setTimeout(resolve, holdMs);
  });
}

function leaseCmd(payload: Record<string, unknown>): void {
  const table = new LeaseTable(str(payload, "project_root"));
  const jailed = jailProjectPath(str(payload, "project_root"), str(payload, "path"));
  if (!jailed.ok) {
    write({ ok: false, error: jailed.error });
    return;
  }
  try {
    const lease = table.acquireFile(
      str(payload, "writer_id", "writer-a"),
      jailed.rel,
      jailed.abs,
      num(payload, "ttl_ms", 30_000),
    );
    write({ ok: true, lease });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string }) : {};
    write({
      ok: false,
      error: { code: rec.code ?? E.E_CONFLICT, message: rec.message ?? "lease", path: "lease" },
    });
  }
}

function checkpointCmd(payload: Record<string, unknown>): void {
  const targetsRaw = payload.targets;
  const targets = Array.isArray(targetsRaw)
    ? targetsRaw.filter((item): item is string => typeof item === "string")
    : [str(payload, "path")].filter(Boolean);
  const created = createRecoveryCheckpoint({
    projectRoot: str(payload, "project_root"),
    commandId: str(payload, "command_id", "01ARZ3NDEKTSV4RRFFQ69G5FAV"),
    targets,
    fail: payload.fail === true,
  });
  write(created.ok ? created : { ok: false, error: created.error });
}

function restoreCmd(payload: Record<string, unknown>): void {
  const restored = restoreCheckpoint(str(payload, "manifest_path"));
  write(restored);
}

function pauseCmd(payload: Record<string, unknown>): void {
  const samples = Math.max(1, Math.min(200, num(payload, "samples", 40)));
  if (payload.cancellable_job === true) {
    pauseSingleton.registerJob("job-cancel", { cancellable: true });
  }
  if (payload.atomic_job === true) {
    pauseSingleton.registerJob("job-atomic", { atomic: true });
  }
  const measured = pauseSingleton.measureSamples(samples);
  const extra = pauseSingleton.pause();
  const cancelJob = pauseSingleton.job("job-cancel");
  const atomicJob = pauseSingleton.job("job-atomic");
  write({
    ok: true,
    samples: measured.samples,
    p95: measured.p95,
    budget_ms: 250,
    last: extra,
    cancellable_cancelled: cancelJob?.cancelled === true,
    atomic_cancelled: atomicJob?.cancelled === true,
  });
}

function resumeCmd(): void {
  write({ ok: true, ...pauseSingleton.resume() });
}

function allowlistCmd(payload: Record<string, unknown>): void {
  try {
    if (payload.kind === "process") {
      const argvRaw = payload.argv;
      const argv = Array.isArray(argvRaw)
        ? argvRaw.filter((item): item is string => typeof item === "string")
        : [];
      const spawnOpts: { shell?: boolean } = {};
      if (payload.shell === true) {
        spawnOpts.shell = true;
      }
      assertAgentProcess(str(payload, "file"), argv, spawnOpts);
      write({ ok: true, allowed: true });
      return;
    }
    assertLoopbackHost(str(payload, "host"));
    write({ ok: true, allowed: true });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string; path?: string }) : {};
    write({
      ok: false,
      error: { code: rec.code ?? E.E_POLICY, message: rec.message ?? "denied", path: rec.path ?? "" },
    });
  }
}

function gateCmd(payload: Record<string, unknown>): void {
  const svc = servicesOf(payload);
  if (payload.paused === true) {
    svc.pause.pause();
  }
  const params = isRecord(payload.params) ? payload.params : {};
  const result = runMutationGate({
    commandId: str(payload, "command_id", "01ARZ3NDEKTSV4RRFFQ69G5FAV"),
    sideEffect: str(payload, "side_effect", "destructive"),
    actionId: str(payload, "action_id", "asset.delete"),
    checkpointRequired: payload.checkpoint_required !== false,
    policy: normalizePolicy(str(payload, "policy", DEFAULT_POLICY)),
    params,
    requestHash: str(payload, "request_hash")
      || canonicalRequestHash({
        command_id: str(payload, "command_id", "01ARZ3NDEKTSV4RRFFQ69G5FAV"),
        method: str(payload, "method", "godot.asset"),
        action: str(payload, "action", "delete"),
        params,
      }),
    services: svc,
  });
  write(
    result.ok
      ? {
          ok: true,
          jailed: result.jailed,
          checkpoint_id: result.checkpoint?.checkpoint_id ?? "",
          checkpoint_dir: result.checkpoint?.dir ?? "",
          manifest_path: result.checkpoint?.manifest_path ?? "",
          hard_delete_blocked: result.checkpoint?.manifest.hard_delete_blocked === true,
          referenced_by: result.checkpoint?.manifest.referenced_by ?? [],
        }
      : { ok: false, error: result.error },
  );
}

async function submitCmd(payload: Record<string, unknown>): Promise<void> {
  const projectId = str(payload, "project_id");
  const home = str(payload, "home");
  if (!projectId || !home) {
    fail(new Error("home and project_id required"));
  }
  const supervisor = new ProcessSupervisor();
  const ledger = openLedger({ projectId, supervisor, home });
  const policy = str(payload, "project_root") ? servicesOf(payload) : undefined;
  if (payload.paused === true && policy) {
    policy.pause.pause();
  }
  const bound: LedgerBound = {
    actorId: str(payload, "actor", "actor-a"),
    projectId,
    policy: normalizePolicy(str(payload, "policy", DEFAULT_POLICY)),
  };
  const envelopeRaw = payload.envelope;
  if (!isRecord(envelopeRaw)) {
    fail(new Error("envelope required"));
  }
  const envelope: Record<string, unknown> = {
    protocol: typeof envelopeRaw.protocol === "string" ? envelopeRaw.protocol : PROTOCOL,
    ...envelopeRaw,
  };
  try {
    const result: PluginCommandResult = await executeCommand(ledger, envelope, bound, mockRuntime(policy));
    const row = ledger.get(typeof envelope.command_id === "string" ? envelope.command_id : "");
    write({
      ok: result.ok,
      result,
      ledger: row ? inspectRow(row) : null,
      targets: extractTargetPaths(isRecord(envelope.params) ? envelope.params : {}),
    });
  } finally {
    ledger.close();
  }
}

function defaultPolicyCmd(): void {
  write({ ok: true, default_policy: DEFAULT_POLICY, normalized_empty: normalizePolicy(undefined) });
}

function approveCmd(payload: Record<string, unknown>): void {
  const envelopeRaw = isRecord(payload.envelope) ? payload.envelope : payload;
  const commandId = str(envelopeRaw, "command_id");
  const method = str(envelopeRaw, "method");
  const action = str(envelopeRaw, "action");
  const params = isRecord(envelopeRaw.params) ? envelopeRaw.params : {};
  const actor = str(payload, "actor", str(payload, "writer_id", "writer-a"));
  const requestHash = canonicalRequestHash({
    command_id: commandId,
    method,
    action,
    params,
  });
  const revision = str(payload, "revision") || projectRevision(str(payload, "project_root"));
  const token = new ApprovalBinder(str(payload, "project_root")).issue(actor, requestHash, revision);
  write({ ok: true, approval: token, request_hash: requestHash, revision, actor });
}

function supervisorCmd(payload: Record<string, unknown>): void {
  const supervisor = new ProcessSupervisor();
  const argvRaw = payload.argv;
  const argv = Array.isArray(argvRaw)
    ? argvRaw.filter((item): item is string => typeof item === "string")
    : [];
  try {
    const result = supervisor.runSync(str(payload, "file"), argv);
    write({ ok: true, status: result.status, stdout: result.stdout.slice(0, 200) });
  } catch (err) {
    const rec = err && typeof err === "object" ? (err as { code?: string; message?: string; path?: string }) : {};
    write({
      ok: false,
      error: { code: rec.code ?? E.E_POLICY, message: rec.message ?? "denied", path: rec.path ?? "" },
    });
  }
}

function pausePluginLocal(): void {
  const samples: number[] = [];
  for (let i = 0; i < 40; i++) {
    const t0 = performance.now();
    const paused = true;
    const ack = performance.now() - t0;
    samples.push(ack);
    if (paused !== true) {
      fail(new Error("plugin-local pause flag failed"));
    }
  }
  const sorted = [...samples].sort((a, b) => a - b);
  const idx = Math.max(0, Math.ceil(0.95 * sorted.length) - 1);
  write({ ok: true, kind: "plugin_local_flag", samples, p95: sorted[idx] ?? 0 });
}

const cmd = process.argv[2] ?? "";

void (async () => {
  try {
    const payload = cmd === "" ? {} : readJsonArg();
    if (cmd === "jail") {
      jailCmd(payload);
      return;
    }
    if (cmd === "writer") {
      writerCmd(payload);
      return;
    }
    if (cmd === "writer-hold") {
      await writerHold(payload);
      return;
    }
    if (cmd === "lease") {
      leaseCmd(payload);
      return;
    }
    if (cmd === "checkpoint") {
      checkpointCmd(payload);
      return;
    }
    if (cmd === "restore") {
      restoreCmd(payload);
      return;
    }
    if (cmd === "pause") {
      pauseCmd(payload);
      return;
    }
    if (cmd === "resume") {
      resumeCmd();
      return;
    }
    if (cmd === "allowlist") {
      allowlistCmd(payload);
      return;
    }
    if (cmd === "gate") {
      gateCmd(payload);
      return;
    }
    if (cmd === "submit") {
      await submitCmd(payload);
      return;
    }
    if (cmd === "default-policy") {
      defaultPolicyCmd();
      return;
    }
    if (cmd === "approve") {
      approveCmd(payload);
      return;
    }
    if (cmd === "supervisor") {
      supervisorCmd(payload);
      return;
    }
    if (cmd === "pause-plugin-local") {
      pausePluginLocal();
      return;
    }
    fail(new Error("unknown harness command"));
  } catch (err) {
    if (process.exitCode) {
      return;
    }
    fail(err);
  }
})();
