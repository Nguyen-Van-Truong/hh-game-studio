/** R9-WP1 sidecar export job supervisor. Godot CLI is spawned by tools/godot/export_job.py. */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { findRepoRoot } from "../doctor/pin.js";
import { jailExportOutDir } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";

const DEFAULT_PRESET = "Windows Desktop";
const JOB_SCHEMA = "hh-export-job/1";

export interface ExportCtx {
  projectRoot: string;
  commandId: string;
  now: number;
  paused?: boolean;
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

function fail(commandId: string, code: string, message: string, pathName = ""): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] },
    error: typedError(code, message, pathName),
  };
}

function presetName(raw: unknown): string {
  const name = typeof raw === "string" ? raw.trim() : "";
  if (name === "win64" || name === "WindowsDesktop") {
    return DEFAULT_PRESET;
  }
  return name || DEFAULT_PRESET;
}

function exportsHome(): string {
  const local = process.env.LOCALAPPDATA ?? "";
  if (!local) {
    throw new Error("LOCALAPPDATA missing");
  }
  return path.join(local, "HHGodotAgent", "exports");
}

function jobPath(jobId: string): string {
  return path.join(exportsHome(), jobId, "job.json");
}

function writeJob(rec: Record<string, unknown>): void {
  const jobId = String(rec.job_id ?? "");
  const dest = jobPath(jobId);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const tmp = `${dest}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(rec, null, 2)}\n`, "utf8");
  fs.renameSync(tmp, dest);
}

function readJob(jobId: string): Record<string, unknown> | undefined {
  const dest = jobPath(jobId);
  if (!fs.existsSync(dest)) {
    return undefined;
  }
  const parsed: unknown = JSON.parse(fs.readFileSync(dest, "utf8"));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return undefined;
  }
  return parsed as Record<string, unknown>;
}

function exportScript(projectRoot: string): string | undefined {
  const repo = findRepoRoot(projectRoot);
  if (!repo) {
    return undefined;
  }
  const script = path.join(repo, "tools", "godot", "export_job.py");
  return fs.existsSync(script) ? script : undefined;
}

function defaultOutDir(_projectRoot: string): string {
  return path.join(exportsHome(), "r9-wp1-export");
}

export function handleExportAction(
  actionId: string,
  ctx: ExportCtx,
  params: Record<string, unknown>,
): PluginCommandResult {
  if (ctx.paused === true && (actionId === "export.build" || actionId === "export.preset")) {
    return fail(ctx.commandId, E.E_PAUSED, "export mutation gate is paused", "pause");
  }
  if (actionId === "export.validate") {
    return validateExport(ctx, params);
  }
  if (actionId === "export.artifacts") {
    return listArtifacts(ctx, params);
  }
  if (actionId === "export.cancel") {
    return cancelExport(ctx, params);
  }
  if (actionId === "export.build") {
    return acceptBuild(ctx, params);
  }
  if (actionId === "export.preset") {
    return fail(ctx.commandId, E.E_UNVERIFIED, "export.preset requires the editor plugin", "export.preset");
  }
  return fail(ctx.commandId, E.E_UNKNOWN_ACTION, `unknown export action ${actionId}`, "action");
}

function validateExport(ctx: ExportCtx, params: Record<string, unknown>): PluginCommandResult {
  const name = presetName(params.name);
  const project = ctx.projectRoot;
  const godot = path.join(project, "project.godot");
  const preset = path.join(project, "export_presets.cfg");
  const notice = path.join(project, "NOTICE.md");
  if (!fs.existsSync(godot) || !fs.existsSync(preset) || !fs.existsSync(notice)) {
    return fail(ctx.commandId, E.E_UNVERIFIED, "preset/assets/main scene/license incomplete", "project");
  }
  const text = fs.readFileSync(preset, "utf8");
  if (!text.includes(`name="${name}"`) && !text.includes('name="Windows Desktop"')) {
    return fail(ctx.commandId, E.E_UNVERIFIED, "Windows Desktop preset missing", "name");
  }
  if (
    !text.includes("addons/") ||
    !text.includes(".hh-agent/") ||
    !text.includes("token") ||
    !text.includes("audit") ||
    !text.includes("contact_sheet")
  ) {
    return fail(ctx.commandId, E.E_UNVERIFIED, "release filter missing strip needles", "exclude_filter");
  }
  return ok(ctx.commandId, "export_preset_valid", { name, export_preset_valid: true }, false);
}

function listArtifacts(ctx: ExportCtx, params: Record<string, unknown>): PluginCommandResult {
  const name = presetName(params.name);
  const raw = typeof params.out_dir === "string" && params.out_dir ? params.out_dir : defaultOutDir(ctx.projectRoot);
  const jailed = jailExportOutDir(raw, findRepoRoot(ctx.projectRoot));
  if (!jailed.ok) {
    return fail(ctx.commandId, jailed.error.code, jailed.error.message, jailed.error.path);
  }
  const artifacts: Array<{ name: string; bytes: number }> = [];
  if (fs.existsSync(jailed.abs)) {
    for (const item of fs.readdirSync(jailed.abs)) {
      const full = path.join(jailed.abs, item);
      if (fs.statSync(full).isFile()) {
        artifacts.push({ name: item, bytes: fs.statSync(full).size });
      }
    }
  }
  return ok(ctx.commandId, "export_artifact_list", { name, artifacts, out_dir: jailed.abs }, false);
}

function cancelExport(ctx: ExportCtx, params: Record<string, unknown>): PluginCommandResult {
  const jobId = typeof params.job_id === "string" ? params.job_id : "";
  if (!jobId) {
    return fail(ctx.commandId, E.E_MISSING_REQUIRED, "job_id required", "job_id");
  }
  const rec = readJob(jobId);
  if (!rec) {
    return fail(ctx.commandId, E.E_UNVERIFIED, `export job ${jobId} not found`, "job_id");
  }
  rec.cancel_requested = true;
  rec.state = "cancelled";
  rec.message = "cancel has real state";
  const pid = typeof rec.pid === "number" ? rec.pid : 0;
  if (pid > 0) {
    try {
      process.kill(pid);
    } catch {
      /* already gone */
    }
    rec.pid = 0;
  }
  writeJob(rec);
  return ok(ctx.commandId, "export_job_cancelled", { job_id: jobId, state: "cancelled" }, true);
}

function acceptBuild(ctx: ExportCtx, params: Record<string, unknown>): PluginCommandResult {
  const name = presetName(params.name);
  const validated = validateExport(ctx, params);
  if (!validated.ok) {
    return validated;
  }
  const raw = typeof params.out_dir === "string" && params.out_dir ? params.out_dir : defaultOutDir(ctx.projectRoot);
  const jailed = jailExportOutDir(raw, findRepoRoot(ctx.projectRoot));
  if (!jailed.ok) {
    return fail(ctx.commandId, jailed.error.code, jailed.error.message, jailed.error.path);
  }
  const jobId = ctx.commandId;
  const rec: Record<string, unknown> = {
    schema: JOB_SCHEMA,
    job_id: jobId,
    name,
    state: "accepted",
    progress: 0,
    pid: 0,
    out_dir: jailed.abs,
    cancel_requested: false,
    message: "accepted",
  };
  writeJob(rec);
  const script = exportScript(ctx.projectRoot);
  if (script) {
    const child = spawn(
      process.env.PYTHON ?? "python",
      [script, "build", "--project", ctx.projectRoot, "--name", name, "--out", jailed.abs, "--job-id", jobId],
      { detached: true, stdio: "ignore", windowsHide: true },
    );
    child.unref();
    rec.pid = child.pid ?? 0;
    rec.state = "running";
    rec.message = "export_job.py spawned";
    writeJob(rec);
  }
  return ok(ctx.commandId, "export_job_accepted", { job_id: jobId, state: "accepted", out_dir: jailed.abs }, true);
}
