import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { runDoctor } from "../doctor/doctor.js";
import { PINNED_VERSION_ID, pinnedConsolePath, versionIsRefused } from "../doctor/pin.js";
import { readGitDiff, readGitStatus } from "../ledger/git_adapter.js";
import { jailProjectPath, stripResScheme } from "../policy/jail.js";
import type { PauseGate } from "../policy/pause.js";
import { E, typedError } from "../registry/errors.js";
import { getAction } from "../registry/registry.js";
import { PROTOCOL, REGISTRY_VERSION } from "../registry/types.js";
import type { SessionDescriptor } from "../session/descriptor.js";
import { agentHome } from "../session/paths.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import { unverifiedResult } from "../transport/plugin_rpc.js";
import { compileBrief, writePlanEvidence } from "../planner/brief_compiler.js";
import { playJob, playJobs } from "../ledger/play_session.js";
import { listJobs, statusJob } from "../orchestrator/machine.js";
import { listSchedJobs, statusSchedJob } from "../scheduler/machine.js";

export interface SidecarReadInput {
  actionId: string;
  commandId: string;
  params: Record<string, unknown>;
  projectRoot: string;
  pause?: PauseGate;
  desc?: SessionDescriptor;
}

const SIDECAR_ONLY = new Set([
  "project.doctor",
  "git.status",
  "git.diff",
  "job.list",
]);

function ok(
  commandId: string,
  check: string,
  after: Record<string, unknown>,
): PluginCommandResult {
  return {
    type: "result",
    ok: true,
    command_id: commandId,
    changed: false,
    after,
    postcondition: { verified: true, checks: [check] },
  };
}

function fail(
  commandId: string,
  code: string,
  message: string,
  pathName = "",
): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] },
    error: typedError(code, message, pathName),
  };
}

function parseProjectGodot(projectRoot: string): Record<string, unknown> {
  const dest = path.join(projectRoot, "project.godot");
  const text = fs.existsSync(dest) ? fs.readFileSync(dest, "utf8") : "";
  const name = text.match(/config\/name="([^"]*)"/)?.[1] ?? "";
  const main = text.match(/run\/main_scene="([^"]*)"/)?.[1] ?? "";
  const features = text.match(/config\/features=PackedStringArray\(([^)]*)\)/)?.[1] ?? "";
  const plugin = text.includes("res://addons/hh_agent/plugin.cfg");
  return {
    name,
    main_scene: main,
    features,
    hh_agent_enabled: plugin,
    project_godot: "res://project.godot",
    source: "disk",
  };
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function describeAction(actionId: string): Record<string, unknown> | undefined {
  const def = getAction(actionId);
  if (!def) {
    return undefined;
  }
  return {
    id: def.id,
    method: def.method,
    verb: def.verb,
    side_effect: def.side_effect,
    required_policy: def.required_policy,
    postcondition: def.postcondition,
    timeout_ms: def.timeout_ms,
    undo: def.undo,
    checkpoint_required: def.checkpoint_required,
  };
}

function describeVersion(home: string): { after: Record<string, unknown> } {
  const exe = pinnedConsolePath(home);
  if (!fs.existsSync(exe)) {
    return { after: { pin: PINNED_VERSION_ID, binary: "", observed: "", source: "pin-file" } };
  }
  const proc = spawnSync(exe, ["--version"], {
    encoding: "utf8",
    timeout: 15_000,
    windowsHide: true,
  });
  const observed = `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim().split(/\r?\n/)[0] ?? "";
  return {
    after: {
      pin: PINNED_VERSION_ID,
      binary: exe,
      observed,
      protocol: PROTOCOL,
      registry_version: REGISTRY_VERSION,
      source: "godot-cli",
    },
  };
}

export function isSidecarOnlyAction(actionId: string, params: Record<string, unknown>): boolean {
  if (SIDECAR_ONLY.has(actionId)) {
    return true;
  }
  if (actionId === "capabilities.describe" && params.kind === "action") {
    return true;
  }
  return false;
}

export function trySidecarRead(input: SidecarReadInput): PluginCommandResult | undefined {
  const { actionId, commandId, params, projectRoot } = input;
  if (actionId === "project.doctor") {
    const report = runDoctor({
      ...(input.desc ? { desc: input.desc } : {}),
      projectRoot,
      home: agentHome(),
    });
    if (!report.ok && report.error) {
      return {
        type: "result",
        ok: false,
        command_id: commandId,
        changed: false,
        after: report as unknown as Record<string, unknown>,
        postcondition: { verified: false, checks: ["doctor_report_complete"] },
        error: report.error,
      };
    }
    return ok(commandId, "doctor_report_complete", report as unknown as Record<string, unknown>);
  }
  if (actionId === "project.inspect") {
    const after = parseProjectGodot(projectRoot);
    const again = parseProjectGodot(projectRoot);
    if (after.name !== again.name || after.main_scene !== again.main_scene) {
      return unverifiedResult(commandId, "project.godot changed during readback");
    }
    return ok(commandId, "project_inspect_matches_project_godot", after);
  }
  if (actionId === "git.status") {
    const status = readGitStatus({
      projectRoot,
      ...(typeof params.repo === "string" ? { repo: params.repo } : {}),
      ...(typeof params.run_id === "string" ? { runId: params.run_id } : {}),
      ...(stringList(params.allowlist).length > 0 ? { allowlist: stringList(params.allowlist) } : {}),
    });
    return ok(commandId, "git_status_parsed", {
      ...status,
      detail: typeof params.detail === "string" ? params.detail : "short",
      text: status.parent_walk_refused ? "" : `${status.branch} ${status.head}`.trim(),
    });
  }
  if (actionId === "git.diff") {
    const raw = typeof params.path === "string" ? params.path : "";
    const jailed = jailProjectPath(projectRoot, stripResScheme(raw), { forWrite: false });
    if (!jailed.ok) {
      return fail(commandId, jailed.error.code, jailed.error.message, jailed.error.path);
    }
    const diff = readGitDiff({
      projectRoot,
      path: raw,
      ...(typeof params.repo === "string" ? { repo: params.repo } : {}),
    });
    if (!diff.ok) {
      return fail(commandId, diff.error.code, diff.error.message, diff.error.path);
    }
    return ok(commandId, "git_diff_text", { path: raw, text: diff.text, source: diff.source });
  }
  if (actionId === "job.list") {
    const limit = typeof params.limit === "number" ? params.limit : 20;
    const jobs: Array<Record<string, unknown>> = input.pause
      ? [{ id: "mutate-lane", paused: input.pause.isPaused() }]
      : [];
    for (const play of playJobs()) {
      jobs.push({
        id: play.id,
        kind: play.kind,
        playing: play.playing,
        scene: play.scene,
        run_id: play.id,
      });
    }
    if (projectRoot) {
      const orch = listJobs(
        { projectRoot, commandId, now: Date.now(), paused: input.pause?.isPaused() === true },
        { limit },
      );
      const after = orch.after && typeof orch.after === "object" ? orch.after : {};
      const extra = Array.isArray((after as { jobs?: unknown }).jobs) ? (after as { jobs: Record<string, unknown>[] }).jobs : [];
      for (const row of extra) {
        jobs.push({ ...row, kind: "orchestrator" });
      }
      for (const row of listSchedJobs(
        { projectRoot, commandId, now: Date.now(), paused: input.pause?.isPaused() === true },
        limit,
      )) {
        jobs.push(row);
      }
    }
    return ok(commandId, "job_list_returned", { jobs: jobs.slice(0, limit), total: jobs.length });
  }
  if (actionId === "job.plan") {
    const brief = typeof params.brief === "string" ? params.brief : "";
    const runId = typeof params.run_id === "string" ? params.run_id : undefined;
    const fields =
      params.fields !== null && typeof params.fields === "object" && !Array.isArray(params.fields)
        ? (params.fields as Record<string, unknown>)
        : undefined;
    const plan = compileBrief({
      brief,
      ...(runId ? { run_id: runId } : {}),
      ...(fields ? { fields } : {}),
      ...(params.inject_cycle === true ? { inject_cycle: true } : {}),
    });
    if (!plan.ok || plan.tasks.length === 0) {
      return fail(
        commandId,
        plan.error?.code ?? E.E_UNVERIFIED,
        plan.error?.message ?? "empty DAG",
        plan.error?.path ?? "dag",
      );
    }
    const evidence = projectRoot ? writePlanEvidence(projectRoot, plan) : { assumptions: "", plan: "" };
    return ok(commandId, "plan_dag_compiled", {
      plan,
      cards: plan.cards,
      evidence,
      dock: { plan_cards: plan.cards.length, task_count: plan.tasks.length },
    });
  }
  if (actionId === "job.status") {
    const jobId = typeof params.job_id === "string" ? params.job_id : "";
    if (projectRoot) {
      const sched = statusSchedJob(
        { projectRoot, commandId, now: Date.now(), paused: input.pause?.isPaused() === true },
        { job_id: jobId },
      );
      if (sched.ok) {
        return sched;
      }
      const orch = statusJob(
        { projectRoot, commandId, now: Date.now(), paused: input.pause?.isPaused() === true },
        { job_id: jobId },
      );
      if (orch.ok) {
        return orch;
      }
    }
    const play = playJob(jobId);
    if (play) {
      return ok(commandId, "job_status_known", {
        job_id: play.id,
        kind: "play",
        playing: play.playing,
        scene: play.scene,
        run_id: play.id,
        finished: play.playing !== true,
        cancelled: false,
        paused: input.pause?.isPaused() === true,
      });
    }
    const job = input.pause?.job(jobId);
    if (!job) {
      return fail(commandId, E.E_UNVERIFIED, `job ${jobId} not found`, "job_id");
    }
    return ok(commandId, "job_status_known", {
      job_id: job.id,
      cancelled: job.cancelled,
      finished: job.finished,
      paused: input.pause?.isPaused() === true,
    });
  }
  if (actionId === "capabilities.describe") {
    const kind = params.kind;
    if (kind === "action") {
      const action = typeof params.action_id === "string" ? params.action_id : "";
      const payload = describeAction(action);
      if (!payload) {
        return fail(commandId, E.E_UNKNOWN_ACTION, `unknown action ${action}`, "action_id");
      }
      return ok(commandId, "describe_kind_payload_present", { kind: "action", action: payload });
    }
    if (kind === "version") {
      const described = describeVersion(agentHome());
      const after = described.after ?? {};
      const observed = typeof after.observed === "string" ? after.observed : "";
      if (observed && (versionIsRefused(observed) || observed !== PINNED_VERSION_ID)) {
        return fail(
          commandId,
          E.E_VERSION_SKEW,
          `Godot ${observed} != pin ${PINNED_VERSION_ID}`,
          "godot.version",
        );
      }
      if (!observed) {
        return unverifiedResult(commandId, "pinned Godot --version unavailable");
      }
      return ok(commandId, "describe_kind_payload_present", { kind: "version", ...after });
    }
  }
  return undefined;
}
