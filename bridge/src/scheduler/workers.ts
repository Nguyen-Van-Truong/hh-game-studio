/** Four worker roles via worker_threads. Serial path calls the same cpuWork — no extra sleep. */

import { Worker } from "node:worker_threads";
import { fileURLToPath } from "node:url";

import { cpuWork } from "./role_worker.js";
import {
  DEFAULT_WORK_UNITS,
  THROUGHPUT_SCENES,
  WORKER_ROLES,
  type WorkerRole,
  type WorkerStamp,
} from "./types.js";

const WORKER_FILE = fileURLToPath(new URL("./role_worker.js", import.meta.url));

function oneWorker(role: WorkerRole, units: number, seed: string): Promise<WorkerStamp> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(WORKER_FILE, { workerData: { role, units, seed } });
    worker.once("message", (msg: WorkerStamp) => {
      void worker.terminate();
      resolve(msg);
    });
    worker.once("error", (err) => {
      void worker.terminate();
      reject(err);
    });
    worker.once("exit", (code) => {
      if (code !== 0) {
        reject(new Error(`worker ${role} exited ${code}`));
      }
    });
  });
}

export async function runOverlapWorkers(units = DEFAULT_WORK_UNITS): Promise<WorkerStamp[]> {
  return Promise.all(WORKER_ROLES.map((role) => oneWorker(role, units, role)));
}

export async function runDagWorkers(units = DEFAULT_WORK_UNITS): Promise<WorkerStamp[]> {
  const research = await oneWorker("research", units, "research");
  const [code, assets] = await Promise.all([
    oneWorker("code_staging", units, "code_staging"),
    oneWorker("asset_generation", units, "asset_generation"),
  ]);
  const test = await oneWorker("test_analysis", units, "test_analysis");
  return [research, code, assets, test];
}

export function sceneSeeds(count: number): string[] {
  return Array.from({ length: count }, (_, i) => `scene_${i + 1}`);
}

export async function runThroughputParallel(
  scenes = THROUGHPUT_SCENES,
  units = DEFAULT_WORK_UNITS,
): Promise<{ ms: number; digests: string[] }> {
  const seeds = sceneSeeds(scenes);
  const started = Date.now();
  const stamps = await Promise.all(seeds.map((seed) => oneWorker("research", units, seed)));
  return { ms: Date.now() - started, digests: stamps.map((row) => row.digest) };
}

export function runThroughputSerial(scenes = THROUGHPUT_SCENES, units = DEFAULT_WORK_UNITS): {
  ms: number;
  digests: string[];
} {
  const seeds = sceneSeeds(scenes);
  const started = Date.now();
  const digests = seeds.map((seed) => cpuWork(units, seed));
  return { ms: Date.now() - started, digests };
}
