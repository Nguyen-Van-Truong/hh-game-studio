import { E, typedError } from "../registry/errors.js";

export const PLUGIN_NOOP_METHOD = "hh.plugin" as const;
export const PLUGIN_NOOP_ACTION = "noop" as const;

export interface PluginCommandResult {
  type: "result";
  ok: boolean;
  command_id: string;
  changed: boolean;
  postcondition: { verified: boolean; checks: string[] };
  error?: { code: string; message: string; path: string };
  after?: Record<string, unknown>;
  before?: Record<string, unknown>;
  undo_action?: string;
  warnings?: string[];
  evidence?: string[];
}

export function isNoopEnvelope(env: { method?: unknown; action?: unknown }): boolean {
  return env.method === PLUGIN_NOOP_METHOD && env.action === PLUGIN_NOOP_ACTION;
}

export const PLUGIN_READBACK_TYPE = "readback" as const;
export const PLUGIN_READBACK_RESULT_TYPE = "readback_result" as const;

export interface PluginReadbackResult {
  type: typeof PLUGIN_READBACK_RESULT_TYPE;
  command_id: string;
  found: boolean;
  ok: boolean;
  postcondition: { verified: boolean; checks: string[] };
}

export function emptyReadback(commandId: string): PluginReadbackResult {
  return {
    type: PLUGIN_READBACK_RESULT_TYPE,
    command_id: commandId,
    found: false,
    ok: false,
    postcondition: { verified: false, checks: [] },
  };
}

export function parsePluginReadback(raw: unknown): PluginReadbackResult | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (raw.type !== PLUGIN_READBACK_RESULT_TYPE) {
    return null;
  }
  if (typeof raw.command_id !== "string" || raw.command_id.length < 1) {
    return null;
  }
  const postRaw = raw.postcondition;
  let postcondition = { verified: false, checks: [] as string[] };
  if (isRecord(postRaw)) {
    const checks = Array.isArray(postRaw.checks)
      ? postRaw.checks.filter((c): c is string => typeof c === "string")
      : [];
    postcondition = { verified: postRaw.verified === true, checks };
  }
  return {
    type: PLUGIN_READBACK_RESULT_TYPE,
    command_id: raw.command_id,
    found: raw.found === true,
    ok: raw.ok === true,
    postcondition,
  };
}

export function unverifiedResult(commandId: string, message: string): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] },
    error: typedError(E.E_UNVERIFIED, message, ""),
  };
}

export function busyResult(commandId: string, message: string): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] },
    error: typedError(E.E_BUSY, message, ""),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function parsePluginResult(raw: unknown): PluginCommandResult | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (raw.type !== "result") {
    return null;
  }
  if (typeof raw.command_id !== "string" || raw.command_id.length < 1) {
    return null;
  }
  const postRaw = raw.postcondition;
  let postcondition = { verified: false, checks: [] as string[] };
  if (isRecord(postRaw)) {
    const checks = Array.isArray(postRaw.checks)
      ? postRaw.checks.filter((c): c is string => typeof c === "string")
      : [];
    postcondition = { verified: postRaw.verified === true, checks };
  }
  const result: PluginCommandResult = {
    type: "result",
    ok: raw.ok === true,
    command_id: raw.command_id,
    changed: raw.changed === true,
    postcondition,
  };
  if (isRecord(raw.error) && typeof raw.error.code === "string") {
    result.error = {
      code: raw.error.code,
      message: typeof raw.error.message === "string" ? raw.error.message : "",
      path: typeof raw.error.path === "string" ? raw.error.path : "",
    };
  }
  if (isRecord(raw.after)) {
    result.after = raw.after;
  }
  if (isRecord(raw.before)) {
    result.before = raw.before;
  }
  if (typeof raw.undo_action === "string") {
    result.undo_action = raw.undo_action;
  }
  if (Array.isArray(raw.warnings)) {
    result.warnings = raw.warnings.filter((item): item is string => typeof item === "string");
  }
  if (Array.isArray(raw.evidence)) {
    result.evidence = raw.evidence.filter((item): item is string => typeof item === "string");
  }
  return result;
}

export function guardPaperSuccess(
  result: PluginCommandResult,
  envelope: { method?: unknown; action?: unknown },
): PluginCommandResult {
  if (
    result.ok &&
    result.postcondition.verified &&
    result.postcondition.checks.length === 0 &&
    !isNoopEnvelope(envelope)
  ) {
    return unverifiedResult(result.command_id, "verified:true with empty checks is a paper success");
  }
  return result;
}
