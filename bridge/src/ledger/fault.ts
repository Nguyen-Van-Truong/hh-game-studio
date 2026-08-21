import { E, typedError } from "../registry/errors.js";
import { isFaultHook, type FaultHook } from "./states.js";

export const LEDGER_FAULT_EXIT = 99 as const;
export const LEDGER_ATTEMPT_CRASH_EXIT = 98 as const;

export class LedgerPluginDeath extends Error {
  readonly hook: FaultHook;
  constructor(hook: FaultHook) {
    super(`ledger plugin death at ${hook}`);
    this.name = "LedgerPluginDeath";
    this.hook = hook;
  }
}

function env(name: string): string {
  return (process.env[name] ?? "").trim();
}

/** Kill sidecar, or throw so the caller can drop the plugin, after a flushed state. */
export function maybeFault(hook: FaultHook, commandId: string): void {
  const at = env("HH_LEDGER_FAULT_AT");
  if (!isFaultHook(at) || at !== hook) {
    return;
  }
  const only = env("HH_LEDGER_FAULT_COMMAND_ID");
  if (only && only !== commandId) {
    return;
  }
  const mode = env("HH_LEDGER_FAULT_MODE") || "sidecar";
  if (mode === "plugin") {
    throw new LedgerPluginDeath(hook);
  }
  process.stderr.write(`hh-ledger-fault=${hook}\n`);
  process.exit(LEDGER_FAULT_EXIT);
}

export function maybeCrashAfterDispatchAttempt(commandId: string): void {
  if (env("HH_LEDGER_CRASH_AFTER_DISPATCH_ATTEMPT") !== "1") {
    return;
  }
  const only = env("HH_LEDGER_FAULT_COMMAND_ID");
  if (only && only !== commandId) {
    return;
  }
  process.stderr.write("hh-ledger-fault=dispatch_attempted\n");
  process.exit(LEDGER_ATTEMPT_CRASH_EXIT);
}

export function faultEnvError(hook: string): { code: string; message: string; path: string } {
  return typedError(E.E_UNCERTAIN, `interrupted at ${hook}`, "");
}
