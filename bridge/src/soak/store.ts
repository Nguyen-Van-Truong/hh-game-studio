/** Atomic persist for soak state. Jail: r7w5/ only, no .. / addons / .hh-agent. */

import fs from "node:fs";
import path from "node:path";

import { PINNED_VERSION_ID } from "../doctor/pin.js";
import { jailProjectPath } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import {
  SOAK_CACHE_BUDGET_BYTES,
  SOAK_CACHE_MAX,
  SOAK_CURRENT,
  SOAK_DIR,
  SOAK_EVENT_MAX_LINES,
  SOAK_EVENT_ROTATE_KEEP,
  SOAK_EVIDENCE_MAX_FILES,
  SOAK_SCHEMA,
  type SoakCacheEntry,
  type SoakPhase,
  type SoakProgress,
  type SoakRecord,
  type SoakView,
} from "./types.js";

export function jobIdOk(jobId: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(jobId);
}

export function jailSoakRel(
  projectRoot: string,
  rel: string,
): { ok: true; abs: string; rel: string } | { ok: false; code: string; message: string; path: string } {
  const p = rel.replace(/\\/g, "/").replace(/^\/+/, "");
  if (p.includes("..") || p.includes("addons/") || p.startsWith(".hh-agent") || p.includes("/.hh-agent")) {
    return { ok: false, code: E.E_PATH, message: "soak path escapes jail", path: rel };
  }
  if (!p.startsWith(`${SOAK_DIR}/`)) {
    return { ok: false, code: E.E_PATH, message: "soak writes only under r7w5/", path: rel };
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
  return `${SOAK_DIR}/${jobId}/state.json`;
}

function emptyProgress(): SoakProgress {
  return { applied: 0, play_runs: 0, next_step: 0, restarts: { sidecar: 0, editor: 0, host: 0 } };
}

export function newRecord(jobId: string, now: number): SoakRecord {
  return {
    schema: SOAK_SCHEMA,
    job_id: jobId,
    session_id: "",
    task_id: "",
    command_id: "",
    brief: "",
    context_summary: "",
    progress: emptyProgress(),
    committed_command_ids: [],
    checkpoint_refs: [],
    compacted: false,
    transcript: [],
    phase: "running",
    blocked_reason: "",
    heartbeat_at_ms: now,
    started_at_ms: now,
    version_pin: PINNED_VERSION_ID,
    project_hash: "",
    scene_hash: "",
  };
}

function asProgress(value: unknown): SoakProgress {
  const rec = value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
  const restarts =
    rec.restarts !== null && typeof rec.restarts === "object" && !Array.isArray(rec.restarts)
      ? (rec.restarts as Record<string, unknown>)
      : {};
  return {
    applied: typeof rec.applied === "number" ? rec.applied : 0,
    play_runs: typeof rec.play_runs === "number" ? rec.play_runs : 0,
    next_step: typeof rec.next_step === "number" ? rec.next_step : 0,
    restarts: {
      sidecar: typeof restarts.sidecar === "number" ? restarts.sidecar : 0,
      editor: typeof restarts.editor === "number" ? restarts.editor : 0,
      host: typeof restarts.host === "number" ? restarts.host : 0,
    },
  };
}

function parseRecord(value: unknown, jobId: string): SoakRecord | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const rec = value as Record<string, unknown>;
  if (rec.schema !== SOAK_SCHEMA || rec.job_id !== jobId) {
    return undefined;
  }
  const phase: SoakPhase =
    rec.phase === "idle" || rec.phase === "done" || rec.phase === "blocked" || rec.phase === "running"
      ? rec.phase
      : "running";
  return {
    schema: SOAK_SCHEMA,
    job_id: jobId,
    session_id: typeof rec.session_id === "string" ? rec.session_id : "",
    task_id: typeof rec.task_id === "string" ? rec.task_id : "",
    command_id: typeof rec.command_id === "string" ? rec.command_id : "",
    brief: typeof rec.brief === "string" ? rec.brief : "",
    context_summary: typeof rec.context_summary === "string" ? rec.context_summary : "",
    progress: asProgress(rec.progress),
    committed_command_ids: Array.isArray(rec.committed_command_ids)
      ? rec.committed_command_ids.filter((item): item is string => typeof item === "string" && item.length > 0)
      : [],
    checkpoint_refs: Array.isArray(rec.checkpoint_refs)
      ? rec.checkpoint_refs.filter((item): item is string => typeof item === "string" && item.length > 0)
      : [],
    compacted: rec.compacted === true,
    transcript: [],
    phase,
    blocked_reason: typeof rec.blocked_reason === "string" ? rec.blocked_reason : "",
    heartbeat_at_ms: typeof rec.heartbeat_at_ms === "number" ? rec.heartbeat_at_ms : 0,
    started_at_ms: typeof rec.started_at_ms === "number" ? rec.started_at_ms : 0,
    version_pin: typeof rec.version_pin === "string" ? rec.version_pin : PINNED_VERSION_ID,
    project_hash: typeof rec.project_hash === "string" ? rec.project_hash : "",
    scene_hash: typeof rec.scene_hash === "string" ? rec.scene_hash : "",
  };
}

export function loadRecord(projectRoot: string, jobId: string): SoakRecord | undefined {
  if (!jobIdOk(jobId)) {
    return undefined;
  }
  const jailed = jailSoakRel(projectRoot, stateRel(jobId));
  if (!jailed.ok || !fs.existsSync(jailed.abs)) {
    return undefined;
  }
  try {
    return parseRecord(JSON.parse(fs.readFileSync(jailed.abs, "utf8")), jobId);
  } catch {
    return undefined;
  }
}

export function saveRecord(
  projectRoot: string,
  rec: SoakRecord,
): { ok: true; rel: string } | { ok: false; code: string; message: string; path: string } {
  if (!jobIdOk(rec.job_id)) {
    return { ok: false, code: E.E_PATH, message: "invalid job_id", path: "job_id" };
  }
  rec.transcript = [];
  const jailed = jailSoakRel(projectRoot, stateRel(rec.job_id));
  if (!jailed.ok) {
    return { ok: false, code: jailed.code, message: jailed.message, path: jailed.path };
  }
  if (!atomicWriteUtf8(jailed.abs, `${JSON.stringify(rec, null, 2)}\n`)) {
    return { ok: false, code: E.E_UNVERIFIED, message: "soak persist failed", path: jailed.rel };
  }
  const cur = jailSoakRel(projectRoot, SOAK_CURRENT);
  if (cur.ok) {
    atomicWriteUtf8(cur.abs, `${JSON.stringify({ job_id: rec.job_id, schema: SOAK_SCHEMA }, null, 2)}\n`);
  }
  return { ok: true, rel: jailed.rel };
}

export function currentJobId(projectRoot: string): string {
  const jailed = jailSoakRel(projectRoot, SOAK_CURRENT);
  if (!jailed.ok || !fs.existsSync(jailed.abs)) {
    return "";
  }
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(jailed.abs, "utf8"));
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const id = (parsed as { job_id?: unknown }).job_id;
      return typeof id === "string" && jobIdOk(id) ? id : "";
    }
  } catch {
    return "";
  }
  return "";
}

export function listRecords(projectRoot: string): SoakRecord[] {
  const root = path.join(projectRoot, SOAK_DIR);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    return [];
  }
  const out: SoakRecord[] = [];
  for (const name of fs.readdirSync(root)) {
    const rec = loadRecord(projectRoot, name);
    if (rec) {
      out.push(rec);
    }
  }
  return out;
}

export function viewOf(rec: SoakRecord): SoakView {
  return {
    job_id: rec.job_id,
    kind: "soak",
    session_id: rec.session_id,
    task_id: rec.task_id,
    command_id: rec.command_id,
    brief: rec.brief,
    context_summary: rec.context_summary,
    progress: { ...rec.progress, restarts: { ...rec.progress.restarts } },
    committed_count: rec.committed_command_ids.length,
    checkpoint_refs: [...rec.checkpoint_refs],
    compacted: rec.compacted,
    transcript: [],
    phase: rec.phase,
    blocked_reason: rec.blocked_reason,
    heartbeat_at_ms: rec.heartbeat_at_ms,
    state: rec.phase,
    resource_uri: "session://state",
    resource_path: stateRel(rec.job_id),
  };
}

export function publicStateResource(projectRoot: string): Record<string, unknown> {
  const jobId = currentJobId(projectRoot);
  if (!jobId) {
    return { compacted: false, reason: "no soak state", resource_uri: "session://state", transcript: [] };
  }
  const rec = loadRecord(projectRoot, jobId);
  if (!rec) {
    return { compacted: false, reason: "soak state missing", job_id: jobId, resource_uri: "session://state", transcript: [] };
  }
  return { ...viewOf(rec), ok: true };
}

function eventsRel(jobId: string): string {
  return `${SOAK_DIR}/${jobId}/logs/events.jsonl`;
}

function rotateIndexRel(jobId: string): string {
  return `${SOAK_DIR}/${jobId}/logs/rotate.json`;
}

export function appendEvent(projectRoot: string, jobId: string, event: Record<string, unknown>): void {
  const jailed = jailSoakRel(projectRoot, eventsRel(jobId));
  if (!jailed.ok) {
    return;
  }
  fs.mkdirSync(path.dirname(jailed.abs), { recursive: true });
  fs.appendFileSync(jailed.abs, `${JSON.stringify(event)}\n`, "utf8");
  rotateEventsIfNeeded(projectRoot, jobId);
}

export function rotateEventsIfNeeded(projectRoot: string, jobId: string): { rotated: boolean; refs: string[] } {
  const jailed = jailSoakRel(projectRoot, eventsRel(jobId));
  if (!jailed.ok || !fs.existsSync(jailed.abs)) {
    return { rotated: false, refs: checkpointRefsFromDisk(projectRoot, jobId) };
  }
  const text = fs.readFileSync(jailed.abs, "utf8");
  const lines = text.split(/\r?\n/).filter((line) => line.length > 0);
  if (lines.length < SOAK_EVENT_MAX_LINES) {
    return { rotated: false, refs: checkpointRefsFromDisk(projectRoot, jobId) };
  }
  const rec = loadRecord(projectRoot, jobId);
  const refs = rec ? [...rec.checkpoint_refs] : [];
  const stamp = Date.now();
  const destRel = `${SOAK_DIR}/${jobId}/logs/events.${stamp}.jsonl`;
  const dest = jailSoakRel(projectRoot, destRel);
  if (!dest.ok) {
    return { rotated: false, refs };
  }
  atomicWriteUtf8(dest.abs, `${lines.join("\n")}\n`);
  atomicWriteUtf8(jailed.abs, "");
  const index = jailSoakRel(projectRoot, rotateIndexRel(jobId));
  if (index.ok) {
    let prev: { files?: string[]; checkpoint_refs?: string[] } = {};
    if (fs.existsSync(index.abs)) {
      try {
        prev = JSON.parse(fs.readFileSync(index.abs, "utf8")) as { files?: string[]; checkpoint_refs?: string[] };
      } catch {
        prev = {};
      }
    }
    const files = [destRel, ...(Array.isArray(prev.files) ? prev.files : [])].slice(0, SOAK_EVENT_ROTATE_KEEP);
    const keptRefs = [...refs, ...(Array.isArray(prev.checkpoint_refs) ? prev.checkpoint_refs : [])].filter(
      (item, i, all) => all.indexOf(item) === i,
    );
    atomicWriteUtf8(
      index.abs,
      `${JSON.stringify({ files, checkpoint_refs: keptRefs, rotated_at_ms: stamp }, null, 2)}\n`,
    );
    pruneRotated(projectRoot, jobId, files);
  }
  return { rotated: true, refs };
}

function pruneRotated(projectRoot: string, jobId: string, keep: string[]): void {
  const dir = jailSoakRel(projectRoot, `${SOAK_DIR}/${jobId}/logs`);
  if (!dir.ok || !fs.existsSync(dir.abs)) {
    return;
  }
  const keepSet = new Set(keep.map((item) => item.replace(/\\/g, "/")));
  for (const name of fs.readdirSync(dir.abs)) {
    if (!name.startsWith("events.") || !name.endsWith(".jsonl") || name === "events.jsonl") {
      continue;
    }
    const rel = `${SOAK_DIR}/${jobId}/logs/${name}`;
    if (!keepSet.has(rel)) {
      try {
        fs.unlinkSync(path.join(dir.abs, name));
      } catch {
        /* ignore */
      }
    }
  }
}

function checkpointRefsFromDisk(projectRoot: string, jobId: string): string[] {
  const rec = loadRecord(projectRoot, jobId);
  const fromState = rec ? rec.checkpoint_refs : [];
  const index = jailSoakRel(projectRoot, rotateIndexRel(jobId));
  if (!index.ok || !fs.existsSync(index.abs)) {
    return fromState;
  }
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(index.abs, "utf8"));
    const extra =
      parsed && typeof parsed === "object" && !Array.isArray(parsed) && Array.isArray((parsed as { checkpoint_refs?: unknown }).checkpoint_refs)
        ? ((parsed as { checkpoint_refs: unknown[] }).checkpoint_refs.filter((item): item is string => typeof item === "string"))
        : [];
    return [...fromState, ...extra].filter((item, i, all) => all.indexOf(item) === i);
  } catch {
    return fromState;
  }
}

function cacheRel(jobId: string, commandId: string): string {
  return `${SOAK_DIR}/${jobId}/cache/${commandId}.json`;
}

function slimCachedAfter(after: Record<string, unknown>): Record<string, unknown> {
  const slim: Record<string, unknown> = {};
  for (const key of [
    "job_id",
    "kind",
    "session_id",
    "task_id",
    "command_id",
    "brief",
    "compacted",
    "phase",
    "state",
    "resource_uri",
    "soak_cached",
  ]) {
    if (key in after) {
      slim[key] = after[key];
    }
  }
  if (typeof after.committed_count === "number") {
    slim.committed_count = after.committed_count;
  }
  return Object.keys(slim).length > 0 ? slim : { soak_cached: true };
}

function slimGenericAfter(after: Record<string, unknown>): Record<string, unknown> {
  const slim: Record<string, unknown> = { soak_cached: true };
  for (const key of ["name", "path", "class_name", "scene", "parent"]) {
    if (key in after) {
      slim[key] = after[key];
    }
  }
  return slim;
}

export function rememberSoakResult(projectRoot: string, commandId: string, result: PluginCommandResult): void {
  const jobId = currentJobId(projectRoot);
  if (!jobId || !commandId) {
    return;
  }
  const after =
    result.after && typeof result.after === "object" && !Array.isArray(result.after)
      ? (result.after as Record<string, unknown>)
      : {};
  const checks = result.postcondition?.checks ?? [];
  const soakWake = after.kind === "soak" && checks.includes("soak_wake_idle");
  if (soakWake) {
    pruneCache(projectRoot, jobId);
    return;
  }
  const jailed = jailSoakRel(projectRoot, cacheRel(jobId, commandId));
  if (!jailed.ok) {
    return;
  }
  const entry: SoakCacheEntry = {
    command_id: commandId,
    ok: result.ok === true,
    cached: true,
    after: after.kind === "soak" ? slimCachedAfter(after) : slimGenericAfter(after),
    postcondition: result.postcondition ?? { verified: false, checks: [] },
    changed: result.changed === true,
  };
  atomicWriteUtf8(jailed.abs, `${JSON.stringify(entry)}\n`);
  const rec = loadRecord(projectRoot, jobId);
  if (rec && !rec.committed_command_ids.includes(commandId)) {
    rec.committed_command_ids.push(commandId);
    rec.progress.applied = rec.committed_command_ids.length;
    rec.heartbeat_at_ms = Date.now();
    saveRecord(projectRoot, rec);
  }
  pruneCache(projectRoot, jobId);
  appendEvent(projectRoot, jobId, { kind: "apply", command_id: commandId, at: Date.now() });
}

export function lookupSoakCached(projectRoot: string, commandId: string): PluginCommandResult | undefined {
  if (!projectRoot || !commandId) {
    return undefined;
  }
  const jobIds = [currentJobId(projectRoot), ...listRecords(projectRoot).map((row) => row.job_id)].filter(
    (id, i, all) => id && all.indexOf(id) === i,
  );
  for (const jobId of jobIds) {
    const jailed = jailSoakRel(projectRoot, cacheRel(jobId, commandId));
    if (!jailed.ok || !fs.existsSync(jailed.abs)) {
      continue;
    }
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(jailed.abs, "utf8"));
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        continue;
      }
      const entry = parsed as SoakCacheEntry;
      if (entry.command_id !== commandId) {
        continue;
      }
      return {
        type: "result",
        ok: entry.ok,
        command_id: commandId,
        changed: false,
        after: { ...entry.after, soak_cached: true },
        postcondition: entry.postcondition ?? { verified: entry.ok, checks: ["soak_cached"] },
      };
    } catch {
      continue;
    }
  }
  for (const rec of listRecords(projectRoot)) {
    if (rec.committed_command_ids.includes(commandId)) {
      return {
        type: "result",
        ok: true,
        command_id: commandId,
        changed: false,
        after: { soak_cached: true, job_id: rec.job_id },
        postcondition: { verified: true, checks: ["soak_cached"] },
      };
    }
  }
  return undefined;
}

function pruneCache(projectRoot: string, jobId: string): void {
  const dir = jailSoakRel(projectRoot, `${SOAK_DIR}/${jobId}/cache`);
  if (!dir.ok || !fs.existsSync(dir.abs)) {
    return;
  }
  const files = fs
    .readdirSync(dir.abs)
    .filter((name) => name.endsWith(".json"))
    .map((name) => {
      const abs = path.join(dir.abs, name);
      let mtime = 0;
      try {
        mtime = fs.statSync(abs).mtimeMs;
      } catch {
        mtime = 0;
      }
      return { name, abs, mtime };
    })
    .sort((a, b) => a.mtime - b.mtime);
  const dropOldest = (): void => {
    const drop = files.shift();
    if (drop) {
      try {
        fs.unlinkSync(drop.abs);
      } catch {
        /* ignore */
      }
    }
  };
  while (files.length > SOAK_CACHE_MAX) {
    dropOldest();
  }
  let bytes = 0;
  for (const file of files) {
    try {
      bytes += fs.statSync(file.abs).size;
    } catch {
      /* ignore */
    }
  }
  while (files.length > 0 && bytes > SOAK_CACHE_BUDGET_BYTES) {
    const next = files[0];
    if (!next) {
      break;
    }
    try {
      bytes -= fs.statSync(next.abs).size;
    } catch {
      bytes = Math.max(0, bytes);
    }
    dropOldest();
  }
}

export function capEvidence(projectRoot: string, jobId: string): void {
  const dir = jailSoakRel(projectRoot, `${SOAK_DIR}/${jobId}/evidence`);
  if (!dir.ok || !fs.existsSync(dir.abs)) {
    return;
  }
  const files = fs
    .readdirSync(dir.abs)
    .map((name) => {
      const abs = path.join(dir.abs, name);
      let mtime = 0;
      try {
        mtime = fs.statSync(abs).mtimeMs;
      } catch {
        mtime = 0;
      }
      return { abs, mtime };
    })
    .sort((a, b) => a.mtime - b.mtime);
  while (files.length > SOAK_EVIDENCE_MAX_FILES) {
    const drop = files.shift();
    if (drop) {
      try {
        fs.unlinkSync(drop.abs);
      } catch {
        /* ignore */
      }
    }
  }
}

export function writeEvidence(projectRoot: string, jobId: string, name: string, body: unknown): string {
  const rel = `${SOAK_DIR}/${jobId}/evidence/${name}`;
  const jailed = jailSoakRel(projectRoot, rel);
  if (!jailed.ok) {
    return "";
  }
  if (!atomicWriteUtf8(jailed.abs, `${JSON.stringify(body, null, 2)}\n`)) {
    return "";
  }
  capEvidence(projectRoot, jobId);
  return jailed.rel;
}

export function leakBytes(projectRoot: string, jobId: string): { events: number; evidence: number; cache: number } {
  const sumDir = (rel: string): number => {
    const jailed = jailSoakRel(projectRoot, rel);
    if (!jailed.ok || !fs.existsSync(jailed.abs)) {
      return 0;
    }
    let total = 0;
    const walk = (abs: string): void => {
      let st: fs.Stats;
      try {
        st = fs.statSync(abs);
      } catch {
        return;
      }
      if (st.isFile()) {
        total += st.size;
        return;
      }
      if (st.isDirectory()) {
        for (const name of fs.readdirSync(abs)) {
          walk(path.join(abs, name));
        }
      }
    };
    walk(jailed.abs);
    return total;
  };
  return {
    events: sumDir(`${SOAK_DIR}/${jobId}/logs`),
    evidence: sumDir(`${SOAK_DIR}/${jobId}/evidence`),
    cache: sumDir(`${SOAK_DIR}/${jobId}/cache`),
  };
}

export function typedFail(commandId: string, code: string, message: string, pathName: string) {
  return {
    type: "result" as const,
    ok: false as const,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] as string[] },
    error: typedError(code, message, pathName),
  };
}
