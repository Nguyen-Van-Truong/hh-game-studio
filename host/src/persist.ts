import fs from "node:fs";
import path from "node:path";

import { E, HostError } from "./errors.js";
import { stripSecrets } from "./redact.js";

/** tmp+rename. Windows cannot rename over an existing file. */
export function writeJsonAtomic(file: string, value: unknown): void {
  const dir = path.dirname(file);
  fs.mkdirSync(dir, { recursive: true });
  const safe = stripSecrets(value);
  const body = `${JSON.stringify(safe, null, 2)}\n`;
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, body, { encoding: "utf8" });
  try {
    fs.renameSync(tmp, file);
  } catch {
    try {
      fs.unlinkSync(file);
    } catch {
      // dest may not exist
    }
    fs.renameSync(tmp, file);
  }
}

export function readJsonFile(file: string): unknown {
  if (!fs.existsSync(file)) {
    throw new HostError(E.E_PATH, "host state file missing", "session");
  }
  const raw = fs.readFileSync(file, { encoding: "utf8" });
  try {
    return JSON.parse(raw);
  } catch {
    throw new HostError(E.E_POLICY, "host state file is not JSON", "session");
  }
}
