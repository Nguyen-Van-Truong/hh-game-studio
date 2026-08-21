import { createInterface } from "node:readline";

import { ApprovalBinder, projectRevision } from "../policy/approve.js";
import { canonicalRequestHash } from "../ledger/hash.js";
import { executeCommand, inspectRow, type LedgerBound, type LedgerRuntime } from "../ledger/execute.js";
import type { CommandLedger } from "../ledger/store.js";
import type { PauseGate } from "../policy/pause.js";
import type { PolicyServices } from "../policy/engine.js";
import { acceptCommand } from "../registry/dispatch.js";
import { E } from "../registry/errors.js";
import { allActionDefs } from "../registry/registry.js";
import { isUlid, newUlid } from "../registry/ulid.js";
import type { SessionLog } from "../session/log.js";
import { publicDescriptorView, type SessionDescriptor } from "../session/descriptor.js";
import type { DoctorReport } from "../doctor/doctor.js";
import {
  emptyReadback,
  PLUGIN_NOOP_ACTION,
  PLUGIN_NOOP_METHOD,
  unverifiedResult,
  type PluginCommandResult,
  type PluginReadbackResult,
} from "./plugin_rpc.js";

interface JsonRpcReq {
  jsonrpc?: string;
  id?: string | number | null;
  method?: string;
  params?: unknown;
}

export interface McpStdioContext {
  descriptor: () => SessionDescriptor;
  doctor: () => DoctorReport;
  log: SessionLog;
  plugin?: {
    connected: () => boolean;
    dispatch: (
      envelope: Record<string, unknown>,
      timeoutMs: number,
    ) => Promise<PluginCommandResult>;
    readPostcondition: (commandId: string, timeoutMs: number) => Promise<PluginReadbackResult>;
    dropPlugin: () => void;
    sendControl?: (msg: Record<string, unknown>) => boolean;
  };
  ledger?: CommandLedger;
  bound?: LedgerBound;
  pause?: PauseGate;
  policy?: PolicyServices;
}

function writeRpc(obj: unknown): void {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function domainTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  const byMethod = new Map<string, string[]>();
  for (const def of allActionDefs()) {
    const list = byMethod.get(def.method) ?? [];
    list.push(def.verb);
    byMethod.set(def.method, list);
  }
  const tools: Array<{
    name: string;
    description: string;
    inputSchema: Record<string, unknown>;
  }> = [
    {
      name: "hh.session_status",
      description: "Sidecar session status. Never returns the session secret.",
      inputSchema: { type: "object", additionalProperties: false, properties: {} },
    },
    {
      name: "hh.doctor",
      description: "Session/transport doctor. Secrets are redacted.",
      inputSchema: { type: "object", additionalProperties: false, properties: {} },
    },
    {
      name: "hh.plugin_noop",
      description: "Test noop ACK through a connected plugin. Does not mutate the scene.",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        properties: {
          command_id: { type: "string", minLength: 26, maxLength: 26 },
        },
      },
    },
    {
      name: "hh.command",
      description: "Submit an envelope through the durable ledger. Bindings are session-assigned.",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["command_id", "method", "action", "params"],
        properties: {
          command_id: { type: "string", minLength: 26, maxLength: 26 },
          method: { type: "string" },
          action: { type: "string" },
          params: { type: "object" },
          approval: { type: "string", minLength: 64, maxLength: 64 },
        },
      },
    },
    {
      name: "hh.ledger_inspect",
      description: "Read a ledger row. Never returns session secrets.",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["command_id"],
        properties: {
          command_id: { type: "string", minLength: 26, maxLength: 26 },
        },
      },
    },
    {
      name: "hh.pause",
      description: "Close the mutation gate. ACK is draining, not a kill.",
      inputSchema: { type: "object", additionalProperties: false, properties: {} },
    },
    {
      name: "hh.resume",
      description: "Re-open the mutation gate. Does not apply uncertain commands.",
      inputSchema: { type: "object", additionalProperties: false, properties: {} },
    },
    {
      name: "hh.approve",
      description: "Issue a one-shot EDIT destructive bind (actor + request hash + revision).",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["command_id", "method", "action", "params"],
        properties: {
          command_id: { type: "string", minLength: 26, maxLength: 26 },
          method: { type: "string" },
          action: { type: "string" },
          params: { type: "object" },
        },
      },
    },
  ];
  for (const [name, verbs] of byMethod) {
    tools.push({
      name,
      description: `Domain tool ${name}. Discriminator is action. Editor dispatch is not live.`,
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["action", "params"],
        properties: {
          action: { type: "string", enum: verbs },
          params: { type: "object" },
        },
      },
    });
  }
  return tools;
}

function toolResult(id: string | number | null | undefined, body: unknown, isError: boolean): void {
  writeRpc({
    jsonrpc: "2.0",
    id: id ?? null,
    result: {
      content: [{ type: "text", text: JSON.stringify(body) }],
      structuredContent: body,
      isError,
    },
  });
}

function issueApproval(
  ctx: McpStdioContext,
  args: Record<string, unknown>,
): { body: unknown; isError: boolean } {
  const commandId = typeof args.command_id === "string" ? args.command_id : "";
  const method = typeof args.method === "string" ? args.method : "";
  const action = typeof args.action === "string" ? args.action : "";
  const params = args.params;
  if (!isUlid(commandId) || !method || !action || !params || typeof params !== "object" || Array.isArray(params)) {
    return {
      body: {
        error: { code: E.E_INVALID_ENVELOPE, message: "command_id, method, action, params required", path: "params" },
      },
      isError: true,
    };
  }
  if (!ctx.bound || !ctx.policy) {
    return {
      body: { error: { code: E.E_POLICY, message: "approval binder unavailable", path: "approval" } },
      isError: true,
    };
  }
  const requestHash = canonicalRequestHash({
    command_id: commandId,
    method,
    action,
    params,
  });
  const revision = ctx.policy.revision ?? projectRevision(ctx.policy.projectRoot);
  const approvals = ctx.policy.approvals ?? new ApprovalBinder();
  ctx.policy.approvals = approvals;
  const token = approvals.issue(ctx.bound.actorId, requestHash, revision);
  return {
    body: {
      ok: true,
      approval: token,
      request_hash: requestHash,
      revision,
      actor: ctx.bound.actorId,
      command_id: commandId,
    },
    isError: false,
  };
}

function runtimeOf(ctx: McpStdioContext): LedgerRuntime {
  return {
    pluginConnected: () => ctx.plugin?.connected() ?? false,
    killPlugin: () => ctx.plugin?.dropPlugin(),
    dispatch: (envelope, timeoutMs) => {
      const commandId = typeof envelope.command_id === "string" ? envelope.command_id : "";
      if (!ctx.plugin) {
        return Promise.resolve(unverifiedResult(commandId, "no plugin"));
      }
      return ctx.plugin.dispatch(envelope, timeoutMs);
    },
    readPostcondition: async (commandId) => {
      if (!ctx.plugin) {
        return emptyReadback(commandId);
      }
      const raw = await ctx.plugin.readPostcondition(commandId, 2_000);
      return {
        command_id: raw.command_id,
        found: raw.found,
        ok: raw.ok,
        postcondition: raw.postcondition,
      };
    },
    ...(ctx.policy ? { policy: ctx.policy } : {}),
  };
}

async function runThroughLedger(
  ctx: McpStdioContext,
  envelope: Record<string, unknown>,
): Promise<{ body: unknown; isError: boolean }> {
  if (!ctx.ledger || !ctx.bound) {
    const commandId = typeof envelope.command_id === "string" ? envelope.command_id : "";
    return { body: unverifiedResult(commandId, "ledger unavailable"), isError: true };
  }
  const result = await executeCommand(ctx.ledger, envelope, ctx.bound, runtimeOf(ctx));
  return { body: result, isError: !result.ok };
}

async function handleTool(
  ctx: McpStdioContext,
  name: string,
  args: Record<string, unknown>,
): Promise<{ body: unknown; isError: boolean }> {
  if (name === "hh.pause") {
    const ack = ctx.pause?.pause() ?? { paused: true, state: "draining", ack_ms: 0, cancelled_jobs: [] };
    ctx.plugin?.sendControl?.({ type: "pause", paused: true, ack_ms: ack.ack_ms, state: ack.state });
    return { body: { ok: true, ...ack }, isError: false };
  }
  if (name === "hh.resume") {
    const ack = ctx.pause?.resume() ?? { paused: false, state: "open", ack_ms: 0, cancelled_jobs: [] };
    ctx.plugin?.sendControl?.({ type: "pause", paused: false, ack_ms: ack.ack_ms, state: ack.state });
    return { body: { ok: true, ...ack, uncertain_not_applied: true }, isError: false };
  }
  if (name === "hh.session_status") {
    return { body: { ok: true, session: publicDescriptorView(ctx.descriptor()) }, isError: false };
  }
  if (name === "hh.doctor") {
    return { body: ctx.doctor(), isError: false };
  }
  if (name === "hh.ledger_inspect") {
    const commandId = typeof args.command_id === "string" ? args.command_id : "";
    if (!isUlid(commandId)) {
      return {
        body: { error: { code: E.E_INVALID_COMMAND_ID, message: "command_id must be a ULID", path: "command_id" } },
        isError: true,
      };
    }
    const row = ctx.ledger?.get(commandId);
    return {
      body: {
        ok: true,
        path: ctx.ledger?.filePath ?? "",
        row: row ? inspectRow(row) : null,
      },
      isError: false,
    };
  }
  if (name === "hh.plugin_noop") {
    const commandId = typeof args.command_id === "string" ? args.command_id : newUlid();
    if (!isUlid(commandId)) {
      return {
        body: { error: { code: E.E_INVALID_COMMAND_ID, message: "command_id must be a ULID", path: "command_id" } },
        isError: true,
      };
    }
    return runThroughLedger(ctx, {
      protocol: ctx.descriptor().protocol,
      command_id: commandId,
      method: PLUGIN_NOOP_METHOD,
      action: PLUGIN_NOOP_ACTION,
      params: {},
    });
  }
  if (name === "hh.approve") {
    return issueApproval(ctx, args);
  }
  if (name === "hh.command") {
    const commandId = typeof args.command_id === "string" ? args.command_id : "";
    const method = typeof args.method === "string" ? args.method : "";
    const action = typeof args.action === "string" ? args.action : "";
    const params = args.params;
    if (!isUlid(commandId) || !method || !action || !params || typeof params !== "object" || Array.isArray(params)) {
      return {
        body: {
          error: { code: E.E_INVALID_ENVELOPE, message: "command_id, method, action, params required", path: "params" },
        },
        isError: true,
      };
    }
    if (ctx.policy && typeof args.approval === "string") {
      ctx.policy.approvalToken = args.approval;
    }
    try {
      return await runThroughLedger(ctx, {
        protocol: ctx.descriptor().protocol,
        command_id: commandId,
        method,
        action,
        params,
      });
    } finally {
      if (ctx.policy) {
        delete ctx.policy.approvalToken;
      }
    }
  }
  const action = args.action;
  const params = args.params;
  if (typeof action !== "string" || !params || typeof params !== "object" || Array.isArray(params)) {
    return {
      body: {
        error: { code: E.E_INVALID_ENVELOPE, message: "action and params required", path: "params" },
      },
      isError: true,
    };
  }
  const command_id = typeof args.command_id === "string" ? args.command_id : newUlid();
  const accepted = acceptCommand({
    protocol: ctx.descriptor().protocol,
    command_id,
    method: name,
    action,
    params,
  });
  if (!accepted.accepted) {
    return { body: { error: accepted.error, registry: accepted }, isError: true };
  }
  return runThroughLedger(ctx, {
    protocol: ctx.descriptor().protocol,
    command_id,
    method: name,
    action,
    params,
  });
}

export function startMcpStdio(ctx: McpStdioContext): void {
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (line) => {
    if (!line.trim()) {
      return;
    }
    let msg: JsonRpcReq;
    try {
      msg = JSON.parse(line) as JsonRpcReq;
    } catch {
      writeRpc({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } });
      return;
    }
    const id = msg.id ?? null;
    const method = msg.method ?? "";
    if (method === "initialize") {
      const params = msg.params && typeof msg.params === "object" ? (msg.params as Record<string, unknown>) : {};
      const requested = typeof params.protocolVersion === "string" ? params.protocolVersion : "2024-11-05";
      writeRpc({
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: requested,
          capabilities: { tools: {} },
          serverInfo: { name: "hh-godot-bridge", version: "0.0.0" },
        },
      });
      return;
    }
    if (method === "notifications/initialized" || method.startsWith("notifications/")) {
      return;
    }
    if (method === "ping") {
      writeRpc({ jsonrpc: "2.0", id, result: {} });
      return;
    }
    if (method === "tools/list") {
      writeRpc({ jsonrpc: "2.0", id, result: { tools: domainTools() } });
      return;
    }
    if (method === "tools/call") {
      const params = msg.params && typeof msg.params === "object" ? (msg.params as Record<string, unknown>) : {};
      const name = typeof params.name === "string" ? params.name : "";
      const args =
        params.arguments && typeof params.arguments === "object" && !Array.isArray(params.arguments)
          ? (params.arguments as Record<string, unknown>)
          : {};
      void (async () => {
        try {
          const out = await handleTool(ctx, name, args);
          toolResult(id, out.body, out.isError);
        } catch (err) {
          ctx.log.error(`tools/call failed: ${err instanceof Error ? err.message : "error"}`);
          toolResult(
            id,
            { error: { code: E.E_UNVERIFIED, message: "not dispatched", path: "" } },
            true,
          );
        }
      })();
      return;
    }
    writeRpc({
      jsonrpc: "2.0",
      id,
      error: { code: -32601, message: `unknown method ${method}` },
    });
  });
}
