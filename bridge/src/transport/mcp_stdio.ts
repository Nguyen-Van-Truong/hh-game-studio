import { createInterface } from "node:readline";

import { acceptCommand } from "../registry/dispatch.js";
import { E } from "../registry/errors.js";
import { allActionDefs } from "../registry/registry.js";
import type { SessionLog } from "../session/log.js";
import { publicDescriptorView, type SessionDescriptor } from "../session/descriptor.js";
import type { DoctorReport } from "../doctor/doctor.js";

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

function handleTool(ctx: McpStdioContext, name: string, args: Record<string, unknown>): { body: unknown; isError: boolean } {
  if (name === "hh.session_status") {
    return { body: { ok: true, session: publicDescriptorView(ctx.descriptor()) }, isError: false };
  }
  if (name === "hh.doctor") {
    return { body: ctx.doctor(), isError: false };
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
  const accepted = acceptCommand({
    protocol: ctx.descriptor().protocol,
    command_id: "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    method: name,
    action,
    params,
  });
  return {
    body: {
      error: {
        code: E.E_UNVERIFIED,
        message: "not dispatched; transport only",
        path: "",
      },
      registry: accepted,
    },
    isError: true,
  };
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
      try {
        const out = handleTool(ctx, name, args);
        toolResult(id, out.body, out.isError);
      } catch (err) {
        ctx.log.error(`tools/call failed: ${err instanceof Error ? err.message : "error"}`);
        toolResult(
          id,
          { error: { code: E.E_UNVERIFIED, message: "not dispatched; transport only", path: "" } },
          true,
        );
      }
      return;
    }
    writeRpc({
      jsonrpc: "2.0",
      id,
      error: { code: -32601, message: `unknown method ${method}` },
    });
  });
}
