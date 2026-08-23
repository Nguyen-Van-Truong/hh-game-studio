/** R7-WP2 orchestrator record. Persistable under r7w2/. */

export const ORCH_SCHEMA = "hh-orch/1" as const;
export const ORCH_DIR = "r7w2";
export const ORCH_HEARTBEAT_STALE_MS = 5_000;
export const ORCH_MAX_SAME_REPAIR = 3;
export const DEFAULT_BUDGETS = {
  commands: 64,
  wall_ms: 600_000,
  retries: 8,
  context_tokens: 250_000,
} as const;

export const ORCH_STATES = [
  "inspect",
  "plan",
  "checkpoint",
  "execute",
  "verify",
  "repair",
  "review-ready",
  "done",
  "blocked",
  "cancelled",
] as const;

export type OrchState = (typeof ORCH_STATES)[number];

export const TERMINAL_STATES: ReadonlySet<OrchState> = new Set(["done", "blocked", "cancelled"]);

export const MUTATING_STATES: ReadonlySet<OrchState> = new Set(["checkpoint", "execute", "repair"]);

export type OrchFixture = "ok_slice" | "infinite_repair" | "dep_fail";

export type TaskRunStatus = "pending" | "running" | "ok" | "failed" | "cancelled" | "skipped";

export interface OrchTask {
  id: string;
  kind: string;
  deps: string[];
  commands: string[];
  verify: string;
}

export interface TaskCommand {
  action: string;
  command_id: string;
  committed: boolean;
}

export interface OrchBudgets {
  commands: number;
  wall_ms: number;
  retries: number;
  context_tokens: number;
}

export interface OrchUsed {
  commands: number;
  wall_ms: number;
  retries: number;
  context_tokens: number;
}

export interface OrchRepair {
  error_key: string;
  same_error_count: number;
  loops: number;
  root_cause: string;
}

export interface OrchRecord {
  schema: typeof ORCH_SCHEMA;
  job_id: string;
  state: OrchState;
  current_task_id: string;
  current_command_id: string;
  committed_command_ids: string[];
  tasks: OrchTask[];
  task_status: Record<string, TaskRunStatus>;
  task_commands: Record<string, TaskCommand[]>;
  started_at_ms: number;
  heartbeat_at_ms: number;
  budgets: OrchBudgets;
  used: OrchUsed;
  repair: OrchRepair;
  checkpoint_ref: string;
  fixture: string;
  hold_after: string;
  blocked_reason: string;
  cancel_requested: boolean;
  cancelled: boolean;
  brief_hash: string;
  applied_state: string;
}

export interface OrchView {
  job_id: string;
  state: OrchState;
  current_task_id: string;
  current_command_id: string;
  committed_command_ids: string[];
  heartbeat_at_ms: number;
  heartbeat_age_ms: number;
  stale: boolean;
  budgets: OrchBudgets;
  used: OrchUsed;
  blocked_reason: string;
  cancelled: boolean;
  fixture: string;
  checkpoint_ref: string;
  repair: OrchRepair;
  task_status: Record<string, TaskRunStatus>;
  tasks_executed: string[];
}

export interface RunInput {
  job_id: string;
  brief?: string;
  path?: string;
  fixture?: OrchFixture;
  hold_after?: OrchState;
  max_steps?: number;
  resume?: boolean;
  fail_task?: string;
  budgets?: Partial<OrchBudgets>;
}

export function isOrchState(value: string): value is OrchState {
  return (ORCH_STATES as readonly string[]).includes(value);
}

export function isOrchFixture(value: string): value is OrchFixture {
  return value === "ok_slice" || value === "infinite_repair" || value === "dep_fail";
}

export function canTransition(from: OrchState, to: OrchState): boolean {
  if (from === to) {
    return true;
  }
  if (TERMINAL_STATES.has(from)) {
    return false;
  }
  if (to === "cancelled" || to === "blocked") {
    return true;
  }
  if (from === "inspect" && to === "plan") {
    return true;
  }
  if (from === "plan" && to === "checkpoint") {
    return true;
  }
  if (from === "checkpoint" && to === "execute") {
    return true;
  }
  if (from === "execute" && to === "verify") {
    return true;
  }
  if (from === "verify" && (to === "repair" || to === "execute" || to === "review-ready" || to === "done")) {
    return true;
  }
  if (from === "repair" && to === "verify") {
    return true;
  }
  if (from === "review-ready" && to === "done") {
    return true;
  }
  return false;
}
