/** Test harness for the durable command ledger. Hosts under test come from argv JSON. */

import fs from "node:fs";
import path from "node:path";

import { E } from "../registry/errors.js";
import { PROTOCOL } from "../registry/types.js";
import { ProcessSupervisor } from "../session/supervisor.js";
import {
  isNoopEnvelope,
  unverifiedResult,
  type PluginCommandResult,
} from "../transport/plugin_rpc.js";
import {
  executeCommand,
  inspectRow,
  normalizePolicy,
  type LedgerBound,
  type LedgerRuntime,
  type PluginReadback,
} from "./execute.js";
import { ledgerFilePath } from "./paths.js";
import { openLedger, type CommandLedger } from "./store.js";

function write(obj: unknown): void {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function fail(err: unknown): never {
  const code =
    err && typeof err === "object" && "code" in err && typeof err.code === "string"
      ? err.code
      : "E_FAIL";
  const message = err instanceof Error ? err.message : "harness failed";
  write({ ok: false, error: { code, message } });
  process.exitCode = 1;
  throw err;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readJsonArg(): Record<string, unknown> {
  const raw = process.argv[3] ?? "{}";
  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed)) {
    fail(new Error("payload must be a JSON object"));
  }
  return parsed;
}

function str(rec: Record<string, unknown>, key: string, fallback = ""): string {
  const value = rec[key];
  return typeof value === "string" ? value : fallback;
}

function applyLogPath(): string {
  return (process.env.HH_LEDGER_APPLY_LOG ?? "").trim();
}

function appendApply(commandId: string): void {
  const dest = applyLogPath();
  if (!dest) {
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.appendFileSync(dest, `${commandId}\n`, "utf8");
}

function memoryReadback(): {
  remember: (result: PluginCommandResult) => void;
  read: (commandId: string) => PluginReadback;
  clear: () => void;
} {
  let last: PluginCommandResult | undefined;
  return {
    remember(result) {
      last = result;
    },
    read(commandId) {
      if (!last || last.command_id !== commandId) {
        return {
          command_id: commandId,
          found: false,
          ok: false,
          postcondition: { verified: false, checks: [] },
        };
      }
      return {
        command_id: commandId,
        found: true,
        ok: last.ok,
        postcondition: last.postcondition,
      };
    },
    clear() {
      last = undefined;
    },
  };
}

function mockRuntime(): { runtime: LedgerRuntime; memory: ReturnType<typeof memoryReadback> } {
  const memory = memoryReadback();
  let pluginUp = true;
  const runtime: LedgerRuntime = {
    pluginConnected: () => pluginUp,
    killPlugin: () => {
      pluginUp = false;
      memory.clear();
    },
    readPostcondition: (commandId) => Promise.resolve(memory.read(commandId)),
    dispatch: async (envelope) => {
      const commandId = typeof envelope.command_id === "string" ? envelope.command_id : "";
      if (!pluginUp) {
        return unverifiedResult(commandId, "no plugin");
      }
      appendApply(commandId);
      if ((process.env.HH_LEDGER_DISPATCH_THROW ?? "").trim() === "1") {
        throw new Error("simulated plugin death during dispatch");
      }
      if (isNoopEnvelope(envelope)) {
        const result: PluginCommandResult = {
          type: "result",
          ok: true,
          command_id: commandId,
          changed: false,
          postcondition: { verified: true, checks: ["noop"] },
        };
        memory.remember(result);
        return result;
      }
      const result = unverifiedResult(commandId, "not dispatched");
      memory.remember(result);
      return result;
    },
  };
  return { runtime, memory };
}

function openFrom(payload: Record<string, unknown>): { ledger: CommandLedger; bound: LedgerBound } {
  const projectId = str(payload, "project_id");
  const home = str(payload, "home");
  if (!projectId || !home) {
    fail(new Error("home and project_id required"));
  }
  const supervisor = new ProcessSupervisor();
  const ledger = openLedger({ projectId, supervisor, home });
  return {
    ledger,
    bound: {
      actorId: str(payload, "actor", "actor-a"),
      projectId,
      policy: normalizePolicy(str(payload, "policy", "OBSERVE")),
    },
  };
}

async function submit(payload: Record<string, unknown>): Promise<void> {
  const { ledger, bound } = openFrom(payload);
  try {
    const envelopeRaw = payload.envelope;
    if (!isRecord(envelopeRaw)) {
      fail(new Error("envelope required"));
    }
    const envelope: Record<string, unknown> = {
      protocol: typeof envelopeRaw.protocol === "string" ? envelopeRaw.protocol : PROTOCOL,
      ...envelopeRaw,
    };
    const { runtime } = mockRuntime();
    const result = await executeCommand(ledger, envelope, bound, runtime);
    const row = ledger.get(typeof envelope.command_id === "string" ? envelope.command_id : "");
    write({
      ok: result.ok,
      result,
      ledger: row ? inspectRow(row) : null,
      path: ledger.filePath,
    });
    if (!result.ok) {
      process.exitCode = result.error?.code === E.E_UNCERTAIN || result.error?.code === E.E_IDEMPOTENCY_CONFLICT ? 0 : 0;
    }
  } finally {
    ledger.close();
  }
}

function inspect(payload: Record<string, unknown>): void {
  const { ledger } = openFrom(payload);
  try {
    const commandId = str(payload, "command_id");
    const row = ledger.get(commandId);
    write({
      ok: true,
      path: ledger.filePath,
      pragma: ledger.pragmaInfo(),
      row: row ? inspectRow(row) : null,
    });
  } finally {
    ledger.close();
  }
}

function pragma(payload: Record<string, unknown>): void {
  const { ledger } = openFrom(payload);
  try {
    write({ ok: true, path: ledger.filePath, pragma: ledger.pragmaInfo() });
  } finally {
    ledger.close();
  }
}

function pathCmd(payload: Record<string, unknown>): void {
  const projectId = str(payload, "project_id");
  const home = str(payload, "home");
  write({ ok: true, path: ledgerFilePath(projectId, home) });
}

function evidence(payload: Record<string, unknown>): void {
  const { ledger } = openFrom(payload);
  try {
    const refs = payload.evidence;
    const list = Array.isArray(refs) ? refs.filter((item): item is string => typeof item === "string") : [];
    const row = ledger.attachEvidence(str(payload, "command_id"), list);
    write({ ok: true, row: inspectRow(row) });
  } finally {
    ledger.close();
  }
}

function checkpoint(payload: Record<string, unknown>): void {
  const { ledger } = openFrom(payload);
  try {
    const refs = payload.evidence;
    const list = Array.isArray(refs) ? refs.filter((item): item is string => typeof item === "string") : [];
    ledger.addCheckpoint(str(payload, "checkpoint_id"), list, str(payload, "command_id"));
    write({ ok: true, checkpoints: ledger.listCheckpoints() });
  } finally {
    ledger.close();
  }
}

function compact(payload: Record<string, unknown>): void {
  const { ledger } = openFrom(payload);
  try {
    const maxAge =
      typeof payload.max_age_ms === "number" && Number.isFinite(payload.max_age_ms)
        ? payload.max_age_ms
        : 0;
    const now =
      typeof payload.now_ms === "number" && Number.isFinite(payload.now_ms)
        ? payload.now_ms
        : Date.now();
    const result = ledger.compact(now, maxAge);
    write({ ok: true, ...result, path: ledger.filePath });
  } finally {
    ledger.close();
  }
}

const cmd = process.argv[2] ?? "";

void (async () => {
  try {
    const payload = cmd === "" ? {} : readJsonArg();
    if (cmd === "submit") {
      await submit(payload);
      return;
    }
    if (cmd === "inspect") {
      inspect(payload);
      return;
    }
    if (cmd === "pragma") {
      pragma(payload);
      return;
    }
    if (cmd === "path") {
      pathCmd(payload);
      return;
    }
    if (cmd === "evidence") {
      evidence(payload);
      return;
    }
    if (cmd === "checkpoint") {
      checkpoint(payload);
      return;
    }
    if (cmd === "compact") {
      compact(payload);
      return;
    }
    fail(new Error("unknown harness command"));
  } catch (err) {
    if (process.exitCode) {
      return;
    }
    fail(err);
  }
})();
