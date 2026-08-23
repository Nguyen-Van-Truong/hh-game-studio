/** CLI: run / resume / cancel / status / illegal-transition for official kill tests. */

import fs from "node:fs";

import { illegalTransition, handleOrchAction } from "./machine.js";
import { loadRecord } from "./store.js";
import type { OrchState } from "./types.js";
import { isOrchState } from "./types.js";

function write(value: unknown): void {
  fs.writeSync(1, `${JSON.stringify(value)}\n`);
}

function arg(args: string[], name: string, fallback = ""): string {
  const idx = args.indexOf(name);
  return idx >= 0 ? (args[idx + 1] ?? fallback) : fallback;
}

function projectFromArgs(args: string[]): string {
  const given = arg(args, "--project");
  if (given) {
    return given;
  }
  return process.cwd();
}

function linger(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.includes("--illegal")) {
    const from = arg(args, "--from", "inspect");
    const to = arg(args, "--to", "done");
    write(illegalTransition(from, to));
    return;
  }
  const projectRoot = projectFromArgs(args);
  const jobId = arg(args, "--job-id", "r7w2-harness");
  const commandId = arg(args, "--command-id", "01R7WP2HARNESS000000000001");
  const ctx = { projectRoot, commandId, now: Date.now(), paused: args.includes("--paused") };
  const params: Record<string, unknown> = { job_id: jobId };
  const fixture = arg(args, "--fixture");
  if (fixture) {
    params.fixture = fixture;
  }
  const hold = arg(args, "--hold-after");
  if (hold && isOrchState(hold)) {
    params.hold_after = hold as OrchState;
  }
  if (args.includes("--resume")) {
    params.resume = true;
  }
  const maxSteps = arg(args, "--max-steps");
  if (maxSteps) {
    params.max_steps = Number(maxSteps);
  }

  let action = "job.run";
  if (args.includes("--status")) {
    action = "job.status";
  } else if (args.includes("--cancel")) {
    action = "job.cancel";
  } else if (args.includes("--wait")) {
    action = "job.wait";
    const timeout = arg(args, "--timeout", "5");
    params.timeout_sec = Number(timeout) || 5;
  } else if (args.includes("--list")) {
    action = "job.list";
  }

  const result = handleOrchAction(action, ctx, params);
  const rec = loadRecord(projectRoot, jobId);
  write({
    ...result,
    disk: rec
      ? {
          state: rec.state,
          current_task_id: rec.current_task_id,
          committed_command_ids: rec.committed_command_ids,
          blocked_reason: rec.blocked_reason,
          cancelled: rec.cancelled,
          applied_state: rec.applied_state,
          repair: rec.repair,
          task_status: rec.task_status,
        }
      : null,
  });
  if (args.includes("--linger")) {
    fs.writeSync(1, "READY\n");
    const ms = Number(arg(args, "--linger", "60000"));
    await linger(Number.isFinite(ms) ? ms : 60_000);
  }
}

void main();
