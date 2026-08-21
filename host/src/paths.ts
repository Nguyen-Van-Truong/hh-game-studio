import path from "node:path";

import { E, HostError } from "./errors.js";

export const AGENT_DIR_NAME = "HHGodotAgent" as const;
export const HOSTS_DIR_NAME = "hosts" as const;
export const CREDENTIALS_DIR_NAME = "credentials" as const;
export const STATE_FILE = "state.json" as const;
export const SESSION_MS = 90 * 60 * 1000;

/** %LOCALAPPDATA%/HHGodotAgent — never cwd, never the Godot project tree. */
export function agentHome(): string {
  const local = process.env.LOCALAPPDATA;
  if (!local) {
    throw new HostError(E.E_PATH, "LOCALAPPDATA is required for the host store", "LOCALAPPDATA");
  }
  return path.join(local, AGENT_DIR_NAME);
}

export function hostsRoot(home = agentHome()): string {
  return path.join(home, HOSTS_DIR_NAME);
}

export function hostDir(sessionId: string, home = agentHome()): string {
  return path.join(hostsRoot(home), sessionId);
}

export function statePath(sessionId: string, home = agentHome()): string {
  return path.join(hostDir(sessionId, home), STATE_FILE);
}

export function credentialsDir(home = agentHome()): string {
  return path.join(home, CREDENTIALS_DIR_NAME);
}

export function credentialPath(providerId: string, home = agentHome()): string {
  return path.join(credentialsDir(home), `${providerId}.json`);
}

export function isUnderAgentHome(target: string, home = agentHome()): boolean {
  const rel = path.relative(path.resolve(home), path.resolve(target));
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel);
}
