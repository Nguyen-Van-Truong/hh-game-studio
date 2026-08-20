/** In-memory ActionDef map. Dispatch is lookup only — no editor handlers. */

import { loadActionDefs } from "./actions.js";
import { requiredActionIds } from "./catalog.js";
import type { ActionDef } from "./types.js";

const DEFS = loadActionDefs();
const BY_ID = new Map<string, ActionDef>(DEFS.map((def) => [def.id, def]));

export function allActionDefs(): readonly ActionDef[] {
  return DEFS;
}

export function getAction(id: string): ActionDef | undefined {
  return BY_ID.get(id);
}

export function getRegistry(): ReadonlyMap<string, ActionDef> {
  return BY_ID;
}

export function actionCount(): number {
  return DEFS.length;
}

export function missingRequiredVerbs(): string[] {
  return requiredActionIds().filter((id) => !BY_ID.has(id));
}

export function actionIdFromMethod(method: string, action: string): string | null {
  if (!method.startsWith("godot.")) {
    return null;
  }
  const group = method.slice("godot.".length);
  if (!group || group.includes(".")) {
    return null;
  }
  return `${group}.${action}`;
}
