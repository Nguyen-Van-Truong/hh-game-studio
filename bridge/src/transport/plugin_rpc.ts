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
}

export function isNoopEnvelope(env: { method?: unknown; action?: unknown }): boolean {
  return env.method === PLUGIN_NOOP_METHOD && env.action === PLUGIN_NOOP_ACTION;
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
