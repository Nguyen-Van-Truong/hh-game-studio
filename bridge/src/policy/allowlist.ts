/** Process and network allowlist. No arbitrary shell; argv arrays only. */

import { E, typedError } from "../registry/errors.js";

export const PROCESS_ALLOWLIST = ["godot", "gut", "exporter", "git", "icacls"] as const;

const PROCESS_ALIASES: Record<string, (typeof PROCESS_ALLOWLIST)[number]> = {
  godot: "godot",
  godot_console: "godot",
  godot_headless: "godot",
  gut: "gut",
  gut_cli: "gut",
  exporter: "exporter",
  godot_export: "exporter",
  git: "git",
  icacls: "icacls",
};

const LOOPBACK = new Set(["127.0.0.1", "::1", "localhost"]);

function baseName(file: string): string {
  const norm = file.replace(/\\/g, "/");
  const cut = norm.lastIndexOf("/");
  const name = (cut >= 0 ? norm.slice(cut + 1) : norm).toLowerCase();
  return name.replace(/\.exe$/i, "");
}

export function canonicalizeProcessName(file: string): string {
  const base = baseName(file);
  return PROCESS_ALIASES[base] ?? base;
}

export function assertAgentProcess(
  file: string,
  _argv: readonly string[],
  opts?: { shell?: boolean },
): void {
  if (opts?.shell) {
    throw typedError(E.E_PATH, "arbitrary shell is forbidden", "shell");
  }
  const canon = canonicalizeProcessName(file);
  if (!(PROCESS_ALLOWLIST as readonly string[]).includes(canon)) {
    throw typedError(E.E_POLICY, `process ${canon} is not on the allowlist`, "process");
  }
}

export function assertLoopbackHost(host: string): void {
  const trimmed = host.trim().toLowerCase().replace(/^\[|\]$/g, "");
  if (!LOOPBACK.has(trimmed)) {
    throw typedError(E.E_BIND, "network allowlist is loopback only", "host");
  }
}

export function isShellSpawnForbidden(opts: { shell?: unknown } | undefined): boolean {
  return opts?.shell === true || opts?.shell === "cmd.exe" || opts?.shell === "powershell.exe";
}
