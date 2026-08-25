import { E, typedError, type TypedError } from "./errors.js";
import { newUlid } from "./ulid.js";

export interface ToolRequest {
  tool: string;
  action: string;
  params: Record<string, unknown>;
}

export interface ToolSuccess {
  ok: true;
  after: Record<string, unknown>;
  postcondition: { verified: boolean; checks: string[] };
}

export interface ToolFailure {
  ok: false;
  error: TypedError;
  after?: Record<string, unknown>;
}

export type ToolResult = ToolSuccess | ToolFailure;

export interface ToolExecutor {
  execute(req: ToolRequest): ToolResult | Promise<ToolResult>;
}

/** Same stdio MCP tools/call shape as tests/bootstrap/test_session.py. */
export function mcpToolsCall(
  name: string,
  action: string,
  params: Record<string, unknown>,
  id: number,
  commandId?: string,
): Record<string, unknown> {
  return {
    jsonrpc: "2.0",
    id,
    method: "tools/call",
    params: {
      name,
      arguments: {
        action,
        params,
        ...(commandId ? { command_id: commandId } : {}),
      },
    },
  };
}

export function parseMcpToolResult(msg: unknown): ToolResult {
  if (msg === null || typeof msg !== "object") {
    return { ok: false, error: typedError(E.E_UNVERIFIED, "MCP result is not an object", "mcp") };
  }
  const rec = msg as { result?: { structuredContent?: unknown; isError?: unknown } };
  const body = rec.result?.structuredContent;
  if (body !== null && typeof body === "object") {
    const content = body as { ok?: unknown; error?: unknown; after?: unknown; postcondition?: unknown };
    const err = content.error;
    if (err !== null && typeof err === "object") {
      const e = err as { code?: unknown; message?: unknown; path?: unknown };
      const after =
        content.after !== null && typeof content.after === "object" && !Array.isArray(content.after)
          ? (content.after as Record<string, unknown>)
          : undefined;
      return {
        ok: false,
        error: typedError(
          typeof e.code === "string" ? e.code : E.E_UNVERIFIED,
          typeof e.message === "string" ? e.message : "MCP tool error",
          typeof e.path === "string" ? e.path : "",
        ),
        ...(after ? { after } : {}),
      };
    }
    if (content.ok === true) {
      const after =
        content.after !== null && typeof content.after === "object" && !Array.isArray(content.after)
          ? (content.after as Record<string, unknown>)
          : {};
      return {
        ok: true,
        after,
        postcondition: { verified: false, checks: ["mcp"] },
      };
    }
  }
  return { ok: false, error: typedError(E.E_UNVERIFIED, "MCP tool did not ACK", "mcp") };
}

/**
 * In-process deterministic executor. Does not talk to Godot.
 * Mutate verbs stay E_UNVERIFIED — the host does not apply scene writes.
 */
export class FakeExecutor implements ToolExecutor {
  execute(req: ToolRequest): ToolResult {
    if (req.tool === "godot.node" && req.action === "add") {
      return {
        ok: false,
        error: typedError(
          E.E_UNVERIFIED,
          "mutate is not applied by the host fake executor",
          "mutate",
        ),
      };
    }
    if (req.tool === "godot.project" && req.action === "inspect") {
      return {
        ok: true,
        after: {
          source: "fake-executor",
          action: "inspect",
          detail: req.params.detail ?? "short",
        },
        postcondition: { verified: false, checks: ["fake-inspect"] },
      };
    }
    if (req.tool === "godot.editor" && req.action === "state") {
      return {
        ok: true,
        after: { source: "fake-executor", action: "state" },
        postcondition: { verified: false, checks: ["fake-state"] },
      };
    }
    return {
      ok: true,
      after: { source: "fake-executor", tool: req.tool, action: req.action },
      postcondition: { verified: false, checks: ["fake-tool"] },
    };
  }
}

export interface LineStdio {
  writeLine(line: string): void;
  readLine(timeoutMs?: number): string | Promise<string>;
}

const HH_TOOLS = new Set([
  "hh.pause",
  "hh.resume",
  "hh.plugin_noop",
  "hh.session_status",
  "hh.doctor",
  "hh.ledger_inspect",
]);

function timeoutFor(req: ToolRequest): number {
  if (req.tool === "godot.play" || req.tool === "godot.test" || req.action === "repair") {
    return 180_000;
  }
  if (req.action === "screenshot" || req.action === "checkpoint") {
    return 60_000;
  }
  return 30_000;
}

/** Sidecar MCP over newline JSON-RPC. Sidecar stays deterministic execution. */
export class McpStdioExecutor implements ToolExecutor {
  private nextId = 1;
  private initialized = false;

  constructor(private readonly io: LineStdio) {}

  async execute(req: ToolRequest): Promise<ToolResult> {
    if (!this.initialized) {
      const maybeInit = this.io as LineStdio & { initialize?: () => Promise<void> };
      if (typeof maybeInit.initialize === "function") {
        await maybeInit.initialize();
      }
      this.initialized = true;
    }
    const id = this.nextId;
    this.nextId += 1;
    const payload = HH_TOOLS.has(req.tool)
      ? {
          jsonrpc: "2.0",
          id,
          method: "tools/call",
          params: { name: req.tool, arguments: { ...req.params } },
        }
      : mcpToolsCall(req.tool, req.action, req.params, id, newUlid());
    this.io.writeLine(JSON.stringify(payload));
    let parsed: unknown;
    try {
      const line = await Promise.resolve(this.io.readLine(timeoutFor(req)));
      parsed = JSON.parse(line);
    } catch (err) {
      const message = err instanceof Error ? err.message : "MCP line is not JSON";
      return { ok: false, error: typedError(E.E_UNVERIFIED, message, "mcp") };
    }
    return parseMcpToolResult(parsed);
  }
}
