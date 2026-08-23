/** Job-scoped file/scene/resource leases under r7w4/<job>/locks (not .hh-agent). */

import path from "node:path";

import { LeaseTable } from "../policy/leases.js";
import { SCHED_DIR } from "./types.js";

export function jobLeaseTable(projectRoot: string, jobId: string): LeaseTable {
  return new LeaseTable(projectRoot, { dir: path.posix.join(SCHED_DIR, jobId, "locks") });
}
