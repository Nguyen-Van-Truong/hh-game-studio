import fs from "node:fs";

import { E, HostError } from "../errors.js";
import type { ModelContext, ModelTurn, Provider } from "./types.js";

export const FAKE_MODEL_ID = "fake-deterministic";

/** Inspect then editor state then done. Kill/resume sits between the two tools. */
export const DEFAULT_FAKE_SCRIPT: readonly ModelTurn[] = [
  {
    kind: "tool",
    tool: "godot.project",
    action: "inspect",
    params: { detail: "short" },
  },
  {
    kind: "tool",
    tool: "godot.editor",
    action: "state",
    params: { detail: "short" },
  },
  {
    kind: "done",
    summary: "inspected project and editor state",
  },
];

function asTurn(value: unknown, index: number): ModelTurn {
  if (value === null || typeof value !== "object") {
    throw new HostError(E.E_POLICY, `fake script[${index}] is not an object`, "script");
  }
  const rec = value as { kind?: unknown; tool?: unknown; action?: unknown; params?: unknown; summary?: unknown };
  if (rec.kind === "done") {
    const summary = typeof rec.summary === "string" ? rec.summary : "done";
    return { kind: "done", summary };
  }
  if (rec.kind === "tool" && typeof rec.tool === "string" && typeof rec.action === "string") {
    const params =
      rec.params !== null && typeof rec.params === "object" && !Array.isArray(rec.params)
        ? (rec.params as Record<string, unknown>)
        : {};
    return { kind: "tool", tool: rec.tool, action: rec.action, params };
  }
  throw new HostError(E.E_POLICY, `fake script[${index}] is not a tool/done turn`, "script");
}

export function loadFakeScript(file: string): ModelTurn[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(fs.readFileSync(file, { encoding: "utf8" }));
  } catch {
    throw new HostError(E.E_POLICY, "fake script is not JSON", "script");
  }
  if (!Array.isArray(parsed)) {
    throw new HostError(E.E_POLICY, "fake script must be an array", "script");
  }
  return parsed.map((item, i) => asTurn(item, i));
}

export class FakeProvider implements Provider {
  readonly name = "fake";
  readonly model = FAKE_MODEL_ID;
  private readonly script: readonly ModelTurn[];

  constructor(script: readonly ModelTurn[] = DEFAULT_FAKE_SCRIPT) {
    this.script = script;
  }

  generate(ctx: ModelContext): ModelTurn {
    const turn = this.script[ctx.step];
    if (!turn) {
      return { kind: "done", summary: "script complete" };
    }
    return turn;
  }
}
