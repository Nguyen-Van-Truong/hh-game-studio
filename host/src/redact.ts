import { createHash } from "node:crypto";

const SECRET_KEYS = new Set([
  "token",
  "secret",
  "credential",
  "api_key",
  "apikey",
  "authorization",
  "password",
  "hh_host_credential",
]);

export function sha256Hex(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function redactSecrets(text: string, secrets: readonly string[]): string {
  let out = text;
  for (const secret of secrets) {
    if (secret.length >= 8 && out.includes(secret)) {
      out = out.split(secret).join("[redacted]");
    }
  }
  return out;
}

export function stripSecrets(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stripSecrets(item));
  }
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (SECRET_KEYS.has(key.toLowerCase())) {
        continue;
      }
      out[key] = stripSecrets(item);
    }
    return out;
  }
  return value;
}
