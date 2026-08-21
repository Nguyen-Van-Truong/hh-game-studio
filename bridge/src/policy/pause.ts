/** Pause mutation gate (A14). ACK is the closed/draining flag, measured with hrtime. */

import { performance } from "node:perf_hooks";

export const PAUSE_ACK_BUDGET_MS = 250;

export interface PauseJob {
  id: string;
  cancellable: boolean;
  atomic: boolean;
  cancelled: boolean;
  finished: boolean;
}

export interface PauseAck {
  paused: boolean;
  state: "open" | "draining";
  ack_ms: number;
  cancelled_jobs: string[];
}

export class PauseGate {
  private paused = false;
  private readonly jobs = new Map<string, PauseJob>();
  lastAck: PauseAck = { paused: false, state: "open", ack_ms: 0, cancelled_jobs: [] };

  isPaused(): boolean {
    return this.paused;
  }

  registerJob(id: string, opts: { cancellable?: boolean; atomic?: boolean } = {}): PauseJob {
    const job: PauseJob = {
      id,
      cancellable: opts.cancellable === true,
      atomic: opts.atomic === true,
      cancelled: false,
      finished: false,
    };
    this.jobs.set(id, job);
    return job;
  }

  finishJob(id: string): void {
    const job = this.jobs.get(id);
    if (job) {
      job.finished = true;
    }
  }

  job(id: string): PauseJob | undefined {
    return this.jobs.get(id);
  }

  allowsSideEffect(side: string): boolean {
    if (!this.paused) {
      return true;
    }
    return side === "read" || side === "view" || side === "";
  }

  pause(): PauseAck {
    const t0 = performance.now();
    this.paused = true;
    const cancelled: string[] = [];
    for (const job of this.jobs.values()) {
      if (job.cancellable && !job.finished) {
        job.cancelled = true;
        cancelled.push(job.id);
      }
    }
    const ackMs = performance.now() - t0;
    this.lastAck = { paused: true, state: "draining", ack_ms: ackMs, cancelled_jobs: cancelled };
    return this.lastAck;
  }

  resume(): PauseAck {
    const t0 = performance.now();
    this.paused = false;
    const ackMs = performance.now() - t0;
    this.lastAck = { paused: false, state: "open", ack_ms: ackMs, cancelled_jobs: [] };
    return this.lastAck;
  }

  measureSamples(count: number): { samples: number[]; p95: number } {
    const samples: number[] = [];
    for (let i = 0; i < count; i++) {
      this.resume();
      const ack = this.pause();
      samples.push(ack.ack_ms);
    }
    this.resume();
    const sorted = [...samples].sort((a, b) => a - b);
    const idx = Math.max(0, Math.ceil(0.95 * sorted.length) - 1);
    return { samples, p95: sorted[idx] ?? 0 };
  }
}
