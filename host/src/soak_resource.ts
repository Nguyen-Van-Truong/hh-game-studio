/** Jailed soak state resource under r7w5/. Host --compact writes this; sidecar/MCP reads it. */

import fs from "node:fs";
import path from "node:path";

import { writeJsonAtomic } from "./persist.js";
import type { HostState } from "./session.js";

export const SOAK_DIR = "r7w5";
export const SOAK_SCHEMA = "hh-soak/1";
export const SOAK_RESOURCE_URI = "session://state";

function posixRel(value: string): string {
  return value.replace(/\\/g, "/").replace(/^\/+/, "");
}

function jailSoak(projectRoot: string, rel: string): { ok: true; abs: string; rel: string } | { ok: false; message: string } {
  const p = posixRel(rel);
  if (p.includes("..") || p.includes("addons/") || p.startsWith(".hh-agent") || p.includes("/.hh-agent")) {
    return { ok: false, message: "soak path escapes jail" };
  }
  if (!p.startsWith(`${SOAK_DIR}/`)) {
    return { ok: false, message: "soak writes only under r7w5/" };
  }
  const root = path.resolve(projectRoot);
  const abs = path.resolve(root, p);
  const relToRoot = path.relative(root, abs);
  if (relToRoot.startsWith("..") || path.isAbsolute(relToRoot)) {
    return { ok: false, message: "soak path leaves project" };
  }
  return { ok: true, abs, rel: p };
}

export function writeHostSoakResource(input: {
  projectRoot: string;
  jobId: string;
  state: HostState;
}): { ok: true; resource_path: string; resource_uri: string } | { ok: false; message: string } {
  const jobId = input.jobId;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(jobId)) {
    return { ok: false, message: "invalid job_id" };
  }
  const stateRel = `${SOAK_DIR}/${jobId}/state.json`;
  const jailed = jailSoak(input.projectRoot, stateRel);
  if (!jailed.ok) {
    return jailed;
  }
  const now = Date.now();
  let prev: Record<string, unknown> = {};
  if (fs.existsSync(jailed.abs)) {
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(jailed.abs, "utf8"));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        prev = parsed as Record<string, unknown>;
      }
    } catch {
      prev = {};
    }
  }
  const prevProgress =
    prev.progress !== null && typeof prev.progress === "object" && !Array.isArray(prev.progress)
      ? (prev.progress as Record<string, unknown>)
      : {};
  const prevRestarts =
    prevProgress.restarts !== null && typeof prevProgress.restarts === "object" && !Array.isArray(prevProgress.restarts)
      ? (prevProgress.restarts as Record<string, unknown>)
      : {};
  const prevIds = Array.isArray(prev.committed_command_ids)
    ? prev.committed_command_ids.filter((item): item is string => typeof item === "string")
    : [];
  const hostIds = input.state.tools.map((row) => row.command_id).filter((id) => id);
  const mergedIds = [...prevIds];
  for (const id of hostIds) {
    if (!mergedIds.includes(id)) {
      mergedIds.push(id);
    }
  }
  const body = {
    schema: SOAK_SCHEMA,
    job_id: jobId,
    session_id: input.state.session_id,
    task_id: input.state.task_id,
    command_id: input.state.command_id,
    brief: typeof prev.brief === "string" && prev.brief ? prev.brief : input.state.plan.summary,
    context_summary: input.state.context_summary,
    progress: {
      applied: typeof prevProgress.applied === "number" ? prevProgress.applied : mergedIds.length,
      play_runs: typeof prevProgress.play_runs === "number" ? prevProgress.play_runs : 0,
      next_step: typeof prevProgress.next_step === "number" ? prevProgress.next_step : mergedIds.length,
      restarts: {
        sidecar: typeof prevRestarts.sidecar === "number" ? prevRestarts.sidecar : 0,
        editor: typeof prevRestarts.editor === "number" ? prevRestarts.editor : 0,
        host: Math.max(1, typeof prevRestarts.host === "number" ? prevRestarts.host + 1 : 1),
      },
    },
    committed_command_ids: mergedIds,
    checkpoint_refs: Array.isArray(prev.checkpoint_refs) ? prev.checkpoint_refs : [],
    compacted: true,
    transcript: [],
    phase: input.state.phase === "done" ? "done" : "idle",
    blocked_reason: "",
    heartbeat_at_ms: now,
    started_at_ms: typeof prev.started_at_ms === "number" ? prev.started_at_ms : input.state.started_at,
    version_pin: "4.7.1.stable.official.a13da4feb",
    project_hash: typeof prev.project_hash === "string" ? prev.project_hash : "",
    scene_hash: typeof prev.scene_hash === "string" ? prev.scene_hash : "",
  };
  writeJsonAtomic(jailed.abs, body);
  const current = jailSoak(input.projectRoot, `${SOAK_DIR}/current.json`);
  if (current.ok) {
    writeJsonAtomic(current.abs, { job_id: jobId, schema: SOAK_SCHEMA });
  }
  return { ok: true, resource_path: jailed.rel, resource_uri: SOAK_RESOURCE_URI };
}

export function projectLooksLikeGodot(projectRoot: string): boolean {
  return fs.existsSync(path.join(projectRoot, "project.godot"));
}
