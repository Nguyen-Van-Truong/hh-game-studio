/** R7-WP4 multi-agent scheduler record. Persistable under r7w4/. */

export const SCHED_SCHEMA = "hh-sched/1" as const;
export const SCHED_DIR = "r7w4";
export const COORDINATOR_ID = "coordinator";
export const EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
export const DEFAULT_WORK_UNITS = 8_000;
export const THROUGHPUT_SCENES = 8;

export const WORKER_ROLES = [
  "research",
  "code_staging",
  "asset_generation",
  "test_analysis",
] as const;

export type WorkerRole = (typeof WORKER_ROLES)[number];

export const SCHED_OPS = [
  "run",
  "propose",
  "lease",
  "heartbeat",
  "release",
  "merge",
  "status",
  "apply",
  "hold_lane",
  "release_lane",
] as const;

export type SchedOp = (typeof SCHED_OPS)[number];

export const SCHED_FIXTURES = ["overlap", "throughput", "crash", "dag"] as const;

export type SchedFixture = (typeof SCHED_FIXTURES)[number];

export type ProposalStatus = "proposed" | "merged" | "conflict";

export interface WorkerStamp {
  role: WorkerRole;
  started_at_ms: number;
  ended_at_ms: number;
  digest: string;
  thread_id: number;
}

export interface ChangeProposal {
  proposal_id: string;
  writer_id: string;
  role: string;
  path: string;
  base_hash: string;
  contents: string;
  created_at_ms: number;
  status: ProposalStatus;
}

export interface LaneEvent {
  at_ms: number;
  writer_id: string;
  path: string;
  op: string;
}

export interface SchedRecord {
  schema: typeof SCHED_SCHEMA;
  job_id: string;
  state: "idle" | "running" | "done" | "conflict" | "blocked";
  started_at_ms: number;
  heartbeat_at_ms: number;
  fixture: string;
  workers: WorkerStamp[];
  proposals: ChangeProposal[];
  progress: Record<string, unknown>;
  generated: Record<string, unknown>;
  registry: Record<string, unknown>;
  lane: LaneEvent[];
  overlap: boolean;
  serial_ms: number;
  parallel_ms: number;
  blocked_reason: string;
}

export function isWorkerRole(value: string): value is WorkerRole {
  return (WORKER_ROLES as readonly string[]).includes(value);
}

export function isSchedOp(value: string): value is SchedOp {
  return (SCHED_OPS as readonly string[]).includes(value);
}

export function isSchedFixture(value: string): value is SchedFixture {
  return (SCHED_FIXTURES as readonly string[]).includes(value);
}

export function rolesOverlap(stamps: WorkerStamp[]): boolean {
  if (stamps.length < 4) {
    return false;
  }
  const starts = stamps.map((row) => row.started_at_ms);
  const ends = stamps.map((row) => row.ended_at_ms);
  return Math.max(...starts) < Math.min(...ends);
}
