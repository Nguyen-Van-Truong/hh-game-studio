/** §5.4 command ledger states. Terminal: committed_durable | failed | uncertain. */

export const LEDGER_STATES = [
  "received",
  "validated",
  "applying",
  "applied_volatile",
  "verified",
  "committed_durable",
  "failed",
  "uncertain",
] as const;

export type LedgerState = (typeof LEDGER_STATES)[number];

export const FAULT_HOOKS = ["received", "validated", "applying", "verified"] as const;
export type FaultHook = (typeof FAULT_HOOKS)[number];

export const TERMINAL_STATES: ReadonlySet<LedgerState> = new Set([
  "committed_durable",
  "failed",
  "uncertain",
]);

export function isLedgerState(value: string): value is LedgerState {
  return (LEDGER_STATES as readonly string[]).includes(value);
}

export function isFaultHook(value: string): value is FaultHook {
  return (FAULT_HOOKS as readonly string[]).includes(value);
}
