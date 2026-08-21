import { createInterface } from "node:readline";

import { acceptCommand } from "../registry/dispatch.js";
import { E } from "../registry/errors.js";
import { actionIdFromMethod, allActionDefs, getAction } from "../registry/registry.js";
import { newUlid } from "../registry/ulid.js";
import type { SessionLog } from "../session/log.js";
import { publicDescriptorView, type SessionDescriptor } from "../session/descriptor.js";
import type { DoctorReport } from "../doctor/doctor.js";
import {
  PLUGIN_NOOP_ACTION,
  PLUGIN_NOOP_METHOD,
  unverifiedResult,
  type PluginCommandResult,
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
  };
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
      inputSchema: { type: "object", additionalProperties: false, properties: {} },
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

async function handleTool(
  ctx: McpStdioContext,
  name: string,
  args: Record<string, unknown>,
): Promise<{ body: unknown; isError: boolean }> {
  if (name === "hh.session_status") {
    return { body: { ok: true, session: publicDescriptorView(ctx.descriptor()) }, isError: false };
  }
  if (name === "hh.doctor") {
    return { body: ctx.doctor(), isError: false };
  }
  if (name === "hh.plugin_noop") {
    const envelope = {
      protocol: ctx.descriptor().protocol,
      command_id: newUlid(),
      method: PLUGIN_NOOP_METHOD,
      action: PLUGIN_NOOP_ACTION,
      params: {},
    };
    if (!ctx.plugin?.connected()) {
      return { body: unverifiedResult(envelope.command_id, "no plugin"), isError: true };
    }
    const result = await ctx.plugin.dispatch(envelope, 5_000);
    return { body: result, isError: !result.ok };
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
  const command_id = newUlid();
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
  const resolvedId = accepted.action_id || actionIdFromMethod(name, action);
  const def = resolvedId ? getAction(resolvedId) : undefined;
  if (
    def &&
    (def.side_effect === "mutate" || def.side_effect === "destructive" || def.side_effect === "external")
  ) {
    return {
      body: {
        error: {
          code: E.E_UNVERIFIED,
          message: "not dispatched",
          path: "",
        },
      },
      isError: true,
    };
  }
  if (!def) {
    return {
      body: {
        error: { code: E.E_UNVERIFIED, message: "not dispatched", path: "" },
        registry: accepted,
      },
      isError: true,
    };
  }
  if (!ctx.plugin?.connected()) {
    return { body: unverifiedResult(command_id, "no plugin"), isError: true };
  }
  const result = await ctx.plugin.dispatch(
    {
      protocol: ctx.descriptor().protocol,
      command_id,
      method: name,
      action,
      params,
    },
    def.timeout_ms,
  );
  return { body: result, isError: !result.ok };
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
