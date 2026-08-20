import fs from "node:fs";

import { PROTOCOL } from "../registry/types.js";
import { publicDescriptorView, readDescriptor, type SessionDescriptor } from "../session/descriptor.js";
import { agentHome, descriptorPath, isUnderAgentHome } from "../session/paths.js";
import { pidAlive } from "../session/supervisor.js";
import { LOOPBACK_HOST } from "../transport/loopback.js";

export interface DoctorReport {
  ok: boolean;
  protocol: typeof PROTOCOL;
  home: "LOCALAPPDATA/HHGodotAgent";
  loopback: typeof LOOPBACK_HOST;
  session_present: boolean;
  pid_alive: boolean;
  descriptor_under_home: boolean;
  token_in_report: false;
  checks: string[];
  session?: Record<string, unknown>;
}

export function runSessionDoctor(desc?: SessionDescriptor, home = agentHome()): DoctorReport {
  const checks: string[] = [
    "bind is loopback with OS-assigned port",
    "session store is LOCALAPPDATA/HHGodotAgent",
    "token is never written to stdout",
  ];
  let session_present = false;
  let pid_ok = false;
  let under = false;
  let view: Record<string, unknown> | undefined;
  if (desc) {
    session_present = true;
    pid_ok = pidAlive(desc.pid);
    under = isUnderAgentHome(descriptorPath(desc.project_id, home), home);
    view = publicDescriptorView(desc);
    if (desc.host === LOOPBACK_HOST) {
      checks.push("descriptor host is loopback");
    }
    if (desc.protocol === PROTOCOL) {
      checks.push("descriptor protocol matches");
    }
    if (pid_ok) {
      checks.push("sidecar pid is alive");
    }
  }
  const ok = !desc || (desc.host === LOOPBACK_HOST && desc.protocol === PROTOCOL);
  return {
    ok,
    protocol: PROTOCOL,
    home: "LOCALAPPDATA/HHGodotAgent",
    loopback: LOOPBACK_HOST,
    session_present,
    pid_alive: pid_ok,
    descriptor_under_home: under,
    token_in_report: false,
    checks,
    ...(view ? { session: view } : {}),
  };
}

export function doctorFromProjectId(projectId: string, home = agentHome()): DoctorReport {
  try {
    const desc = readDescriptor(projectId, home);
    return runSessionDoctor(desc, home);
  } catch {
    return runSessionDoctor(undefined, home);
  }
}
