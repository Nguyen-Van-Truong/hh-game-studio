/** R7-WP5 soak record. Persistable under r7w5/. */

export const SOAK_DIR = "r7w5";
export const SOAK_SCHEMA = "hh-soak/1";
export const SOAK_CURRENT = "r7w5/current.json";

export const SOAK_EVENT_MAX_LINES = 256;
export const SOAK_EVENT_ROTATE_KEEP = 4;
export const SOAK_CACHE_MAX = 512;
export const SOAK_EVIDENCE_MAX_FILES = 32;
/** Stated LEAK budgets — official test enforces the same numbers. */
export const SOAK_EVENT_BUDGET_BYTES = 2 * 1024 * 1024;
export const SOAK_EVIDENCE_BUDGET_BYTES = 4 * 1024 * 1024;
export const SOAK_CACHE_BUDGET_BYTES = 2 * 1024 * 1024;

export type SoakPhase = "running" | "idle" | "done" | "blocked";
export type SoakOp = "compact" | "note" | "wake" | "rotate";

export interface SoakProgress {
  applied: number;
  play_runs: number;
  next_step: number;
  restarts: { sidecar: number; editor: number; host: number };
}

export interface SoakRecord {
  schema: typeof SOAK_SCHEMA;
  job_id: string;
  session_id: string;
  task_id: string;
  command_id: string;
  brief: string;
  context_summary: string;
  progress: SoakProgress;
  committed_command_ids: string[];
  checkpoint_refs: string[];
  compacted: boolean;
  transcript: unknown[];
  phase: SoakPhase;
  blocked_reason: string;
  heartbeat_at_ms: number;
  started_at_ms: number;
  version_pin: string;
  project_hash: string;
  scene_hash: string;
}

export interface SoakView {
  job_id: string;
  kind: "soak";
  session_id: string;
  task_id: string;
  command_id: string;
  brief: string;
  context_summary: string;
  progress: SoakProgress;
  committed_count: number;
  checkpoint_refs: string[];
  compacted: boolean;
  transcript: unknown[];
  phase: SoakPhase;
  blocked_reason: string;
  heartbeat_at_ms: number;
  state: SoakPhase;
  resource_uri: "session://state";
  resource_path: string;
}

export interface SoakCacheEntry {
  command_id: string;
  ok: boolean;
  cached: true;
  after: Record<string, unknown>;
  postcondition: { verified: boolean; checks: string[] };
  changed: boolean;
}
