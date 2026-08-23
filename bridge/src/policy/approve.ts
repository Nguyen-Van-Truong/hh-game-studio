/** One-shot EDIT destructive confirmation bound to actor + request hash + revision. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { resolveJailedGit, runJailedGit, verifyToplevel } from "../ledger/git_jail.js";

export function approvalToken(actorId: string, requestHash: string, revision: string): string {
  return createHash("sha256").update(`${actorId}\0${requestHash}\0${revision}`, "utf8").digest("hex");
}

export function projectRevision(projectRoot: string): string {
  if (!projectRoot) {
    return "none";
  }
  const scoped = resolveJailedGit(projectRoot);
  if (!scoped.ok || !verifyToplevel(scoped.git)) {
    return "none";
  }
  const head = runJailedGit(scoped.git, ["rev-parse", "HEAD"]);
  const rev = head.stdout.trim();
  return head.status === 0 && rev ? rev : "none";
}

export class ApprovalBinder {
  private unused = new Set<string>();
  private readonly storePath: string;

  constructor(projectRoot?: string) {
    this.storePath = projectRoot
      ? path.join(projectRoot, ".hh-agent", "approvals.json")
      : "";
    this.reload();
  }

  issue(actorId: string, requestHash: string, revision: string): string {
    this.reload();
    const token = approvalToken(actorId, requestHash, revision);
    this.unused.add(this.key(token, actorId, requestHash, revision));
    this.persist();
    return token;
  }

  consume(actorId: string, requestHash: string, revision: string, token: string): boolean {
    this.reload();
    const expected = approvalToken(actorId, requestHash, revision);
    if (!token || token !== expected) {
      return false;
    }
    const key = this.key(expected, actorId, requestHash, revision);
    if (!this.unused.has(key)) {
      return false;
    }
    this.unused.delete(key);
    this.persist();
    return true;
  }

  private key(token: string, actorId: string, requestHash: string, revision: string): string {
    return `${token}:${actorId}:${requestHash}:${revision}`;
  }

  private reload(): void {
    if (!this.storePath || !fs.existsSync(this.storePath)) {
      return;
    }
    try {
      const raw: unknown = JSON.parse(fs.readFileSync(this.storePath, "utf8"));
      if (Array.isArray(raw)) {
        this.unused = new Set(raw.filter((item): item is string => typeof item === "string"));
      }
    } catch {
      /* keep current */
    }
  }

  private persist(): void {
    if (!this.storePath) {
      return;
    }
    fs.mkdirSync(path.dirname(this.storePath), { recursive: true });
    const tmp = `${this.storePath}.tmp`;
    fs.writeFileSync(tmp, `${JSON.stringify([...this.unused])}\n`, { encoding: "utf8" });
    fs.renameSync(tmp, this.storePath);
  }
}
