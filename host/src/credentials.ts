import fs from "node:fs";

import { E, HostError } from "./errors.js";
import { credentialPath } from "./paths.js";
import { sha256Hex } from "./redact.js";

export interface Credential {
  provider: string;
  source: "env" | "user-store";
  model: string;
  token: string;
  token_sha256: string;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

/**
 * Credential comes from the OS/user store or HH_HOST_CREDENTIAL.
 * Never from the Godot project tree.
 */
export function resolveCredential(providerId: string): Credential {
  const env = process.env.HH_HOST_CREDENTIAL;
  if (env !== undefined && env !== "") {
    const model = process.env.HH_HOST_MODEL ?? "user-configured";
    return {
      provider: providerId,
      source: "env",
      model,
      token: env,
      token_sha256: sha256Hex(env),
    };
  }

  const file = credentialPath(providerId);
  if (!fs.existsSync(file)) {
    throw new HostError(
      E.E_EXTERNAL,
      "credential missing from user store",
      "credential",
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(fs.readFileSync(file, { encoding: "utf8" }));
  } catch {
    throw new HostError(E.E_EXTERNAL, "credential file is not JSON", "credential");
  }
  const rec = asRecord(parsed);
  const token = rec.token;
  if (typeof token !== "string" || token === "") {
    throw new HostError(E.E_EXTERNAL, "credential file has no token", "credential");
  }
  const model = typeof rec.model === "string" && rec.model !== "" ? rec.model : "user-configured";
  return {
    provider: providerId,
    source: "user-store",
    model,
    token,
    token_sha256: sha256Hex(token),
  };
}
