import { randomBytes, timingSafeEqual } from "node:crypto";

const TOKEN_BYTES = 32;

/** 256-bit session secret from CSPRNG. Hex, 64 chars. */
export function generateSessionToken(): string {
  return randomBytes(TOKEN_BYTES).toString("hex");
}

export function isSessionToken(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}

export function tokensEqual(left: string, right: string): boolean {
  if (!isSessionToken(left) || !isSessionToken(right)) {
    return false;
  }
  const a = Buffer.from(left, "hex");
  const b = Buffer.from(right, "hex");
  if (a.length !== TOKEN_BYTES || b.length !== TOKEN_BYTES) {
    return false;
  }
  return timingSafeEqual(a, b);
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
