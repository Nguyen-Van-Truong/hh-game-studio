import path from "node:path";

import { E, typedError } from "../registry/errors.js";

export const AGENT_DIR_NAME = "HHGodotAgent" as const;
export const SESSIONS_DIR_NAME = "sessions" as const;
export const DESCRIPTOR_FILE = "session.json" as const;
export const LOCK_FILE = "sidecar.lock" as const;

/** %LOCALAPPDATA%/HHGodotAgent — never cwd, never the git project. */
export function agentHome(): string {
  const local = process.env.LOCALAPPDATA;
  if (!local) {
    throw typedError(E.E_PATH, "LOCALAPPDATA is required for the session store", "LOCALAPPDATA");
  }
  return path.join(local, AGENT_DIR_NAME);
}

export function sessionsRoot(home = agentHome()): string {
  return path.join(home, SESSIONS_DIR_NAME);
}

export function sessionDir(projectId: string, home = agentHome()): string {
  if (!/^[0-9a-f]{32}$/.test(projectId)) {
    throw typedError(E.E_PROJECT_MISMATCH, "invalid project id", "project_id");
  }
  return path.join(sessionsRoot(home), projectId);
}

export function descriptorPath(projectId: string, home = agentHome()): string {
  return path.join(sessionDir(projectId, home), DESCRIPTOR_FILE);
}

export function lockPath(projectId: string, home = agentHome()): string {
  return path.join(sessionDir(projectId, home), LOCK_FILE);
}

export function isUnderAgentHome(target: string, home = agentHome()): boolean {
  const rel = path.relative(path.resolve(home), path.resolve(target));
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel);
}
