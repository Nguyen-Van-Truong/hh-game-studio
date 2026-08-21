export interface ModelTurnTool {
  kind: "tool";
  tool: string;
  action: string;
  params: Record<string, unknown>;
}

export interface ModelTurnDone {
  kind: "done";
  summary: string;
}

export type ModelTurn = ModelTurnTool | ModelTurnDone;

/** Compact context — not an infinite chat transcript. */
export interface ModelContext {
  task_id: string;
  command_id: string;
  plan_summary: string;
  step: number;
  last_tools: Array<{ tool: string; action: string }>;
}

export interface Provider {
  readonly name: string;
  readonly model: string;
  generate(ctx: ModelContext): ModelTurn;
}
