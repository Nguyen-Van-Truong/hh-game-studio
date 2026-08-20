import fs from "node:fs";

import { E, typedError } from "../registry/errors.js";
import type { ProcessSupervisor } from "./supervisor.js";

function currentAccount(): string {
  const user = process.env.USERNAME;
  if (!user) {
    throw typedError(E.E_PATH, "USERNAME is required for ACL", "USERNAME");
  }
  const domain = process.env.USERDOMAIN;
  return domain ? `${domain}\\${user}` : user;
}

/** Current-user ACL on Windows via icacls argv. chmod 0700 elsewhere. Fail closed. */
export function applyCurrentUserAcl(target: string, supervisor: ProcessSupervisor): void {
  if (!fs.existsSync(target)) {
    throw typedError(E.E_PATH, "ACL target missing", target);
  }
  if (process.platform !== "win32") {
    const mode = fs.statSync(target).isDirectory() ? 0o700 : 0o600;
    fs.chmodSync(target, mode);
    return;
  }
  const account = currentAccount();
  const grant = fs.statSync(target).isDirectory() ? `${account}:(OI)(CI)F` : `${account}:F`;
  const result = supervisor.runSync("icacls.exe", [target, "/inheritance:r", "/grant:r", grant]);
  if (result.status !== 0) {
    throw typedError(E.E_PATH, "failed to set current-user ACL", "acl");
  }
}
