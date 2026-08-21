import { createHash } from "node:crypto";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Deterministic JSON for request hashing. Sorted object keys; arrays keep order. */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value === "number" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "bigint") {
    return JSON.stringify(value.toString());
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (isRecord(value)) {
    const keys = Object.keys(value).sort();
    const body = keys
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",");
    return `{${body}}`;
  }
  return JSON.stringify(null);
}

export interface RequestHashInput {
  command_id: string;
  method: string;
  action: string;
  params: unknown;
  precondition?: unknown;
  presentation?: unknown;
  action_version?: unknown;
}

/** Canonical request hash. Bound actor/project/policy are compared separately. */
export function canonicalRequestHash(input: RequestHashInput): string {
  const payload = {
    command_id: input.command_id,
    method: input.method,
    action: input.action,
    params: input.params ?? {},
    precondition: input.precondition ?? null,
    presentation: input.presentation ?? null,
    action_version: input.action_version ?? null,
  };
  return createHash("sha256").update(stableStringify(payload), "utf8").digest("hex");
}
