import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { jailProjectPath } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";

export interface DiscoveredProject {
  root: string;
  projectId: string;
}

function realPathOf(p: string): string {
  return fs.realpathSync.native(p);
}

/** Walk up to project.godot; id is sha256(canonical root) truncated to 32 hex chars. */
export function discoverProject(inputPath: string): DiscoveredProject {
  if (!inputPath) {
    throw typedError(E.E_PROJECT_MISMATCH, "project path required", "project");
  }
  let dir = path.resolve(inputPath);
  if (fs.existsSync(dir) && fs.statSync(dir).isFile()) {
    dir = path.dirname(dir);
  }
  for (;;) {
    const marker = path.join(dir, "project.godot");
    if (fs.existsSync(marker) && fs.statSync(marker).isFile()) {
      const root = realPathOf(dir);
      const projectId = createHash("sha256").update(root, "utf8").digest("hex").slice(0, 32);
      return { root, projectId };
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      break;
    }
    dir = parent;
  }
  throw typedError(E.E_PROJECT_MISMATCH, "project.godot not found", "project");
}

export function jailUnderProject(projectRoot: string, candidate: string): string {
  const jailed = jailProjectPath(projectRoot, candidate, { forWrite: true });
  if (!jailed.ok) {
    throw typedError(jailed.error.code, jailed.error.message, jailed.error.path);
  }
  return jailed.abs;
}
