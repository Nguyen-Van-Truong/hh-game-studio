/** Recovery checkpoint primitive (A10). Manifest + COW/quarantine; Git ref if the tree is clean. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { E, typedError } from "../registry/errors.js";
import { newUlid } from "../registry/ulid.js";
import { ProcessSupervisor } from "../session/supervisor.js";
import { jailProjectPath } from "./jail.js";

export interface CheckpointFile {
  rel: string;
  sha256: string;
  missing: boolean;
}

export interface CheckpointManifest {
  checkpoint_id: string;
  command_id: string;
  created_at: string;
  project_root: string;
  git_ref: string;
  git_head: string;
  files: CheckpointFile[];
  referenced_by: string[];
  hard_delete_blocked: boolean;
}

export interface CheckpointOk {
  ok: true;
  checkpoint_id: string;
  dir: string;
  manifest_path: string;
  manifest: CheckpointManifest;
}

export interface CheckpointErr {
  ok: false;
  error: { code: string; message: string; path: string };
}

export type CheckpointResult = CheckpointOk | CheckpointErr;

function sha256File(abs: string): string {
  return createHash("sha256").update(fs.readFileSync(abs)).digest("hex");
}

function fsyncPath(abs: string): void {
  const fd = fs.openSync(abs, "r+");
  try {
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

function gitCleanHead(projectRoot: string): { head: string; clean: boolean } {
  const supervisor = new ProcessSupervisor();
  const status = supervisor.runSync("git", ["-C", projectRoot, "status", "--porcelain"]);
  if (status.status !== 0) {
    return { head: "", clean: false };
  }
  const dirty = status.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.includes(".hh-agent"));
  const clean = dirty.length === 0;
  const head = supervisor.runSync("git", ["-C", projectRoot, "rev-parse", "HEAD"]);
  if (head.status !== 0) {
    return { head: "", clean: false };
  }
  return { head: head.stdout.trim(), clean };
}

function tryGitRef(projectRoot: string, checkpointId: string, head: string): string {
  if (!head) {
    return "";
  }
  const ref = `refs/hh-ckpt/${checkpointId}`;
  const supervisor = new ProcessSupervisor();
  const updated = supervisor.runSync("git", ["-C", projectRoot, "update-ref", ref, head]);
  return updated.status === 0 ? ref : "";
}

export function findReferences(projectRoot: string, rel: string): string[] {
  const needle = rel.replace(/\\/g, "/");
  const name = path.posix.basename(needle);
  const hits: string[] = [];
  const walk = (dir: string): void => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name === ".git" || entry.name === ".godot" || entry.name === "node_modules" || entry.name === ".hh-agent") {
        continue;
      }
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(abs);
        continue;
      }
      if (!entry.isFile()) {
        continue;
      }
      const ext = path.extname(entry.name).toLowerCase();
      if (![".tscn", ".tres", ".gd", ".cfg", ".import", ".md", ".txt", ".json", ".toml"].includes(ext)) {
        continue;
      }
      let text = "";
      try {
        text = fs.readFileSync(abs, "utf8");
      } catch {
        continue;
      }
      if (text.includes(needle) || (name && text.includes(name))) {
        const relHit = path.relative(projectRoot, abs).replace(/\\/g, "/");
        if (relHit !== needle) {
          hits.push(relHit);
        }
      }
    }
  };
  walk(projectRoot);
  return hits;
}

export function createRecoveryCheckpoint(opts: {
  projectRoot: string;
  commandId: string;
  targets: readonly string[];
  fail?: boolean;
}): CheckpointResult {
  if (opts.fail || (process.env.HH_CHECKPOINT_FAIL ?? "").trim() === "1") {
    return {
      ok: false,
      error: typedError(E.E_CHECKPOINT, "checkpoint flush/verify failed", "checkpoint"),
    };
  }
  const jailed: { abs: string; rel: string }[] = [];
  for (const target of opts.targets) {
    const result = jailProjectPath(opts.projectRoot, target, { forWrite: true });
    if (!result.ok) {
      return { ok: false, error: result.error };
    }
    jailed.push({ abs: result.abs, rel: result.rel });
  }
  const checkpointId = newUlid();
  const dir = path.join(opts.projectRoot, ".hh-agent", "checkpoints", checkpointId);
  const filesDir = path.join(dir, "files");
  try {
    fs.mkdirSync(filesDir, { recursive: true });
  } catch {
    return {
      ok: false,
      error: typedError(E.E_CHECKPOINT, "checkpoint directory could not be created", dir),
    };
  }

  const files: CheckpointFile[] = [];
  const referenced: string[] = [];
  try {
    for (const item of jailed) {
      const dest = path.join(filesDir, item.rel.replace(/[\\/]/g, "__"));
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      let missing = true;
      let digest = "missing";
      if (fs.existsSync(item.abs) && fs.statSync(item.abs).isFile()) {
        fs.copyFileSync(item.abs, dest);
        fsyncPath(dest);
        digest = sha256File(dest);
        const original = sha256File(item.abs);
        if (digest !== original) {
          throw typedError(E.E_CHECKPOINT, "checkpoint copy hash mismatch", item.rel);
        }
        missing = false;
      }
      files.push({ rel: item.rel, sha256: digest, missing });
      referenced.push(...findReferences(opts.projectRoot, item.rel));
    }
  } catch (err) {
    const message = err && typeof err === "object" && "message" in err ? String(err.message) : "copy failed";
    return { ok: false, error: typedError(E.E_CHECKPOINT, message, "checkpoint") };
  }

  const git = gitCleanHead(opts.projectRoot);
  const gitRef = git.clean ? tryGitRef(opts.projectRoot, checkpointId, git.head) : "";
  const manifest: CheckpointManifest = {
    checkpoint_id: checkpointId,
    command_id: opts.commandId,
    created_at: new Date().toISOString(),
    project_root: opts.projectRoot,
    git_ref: gitRef,
    git_head: git.clean ? git.head : "",
    files,
    referenced_by: [...new Set(referenced)],
    hard_delete_blocked: referenced.length > 0,
  };
  const manifestPath = path.join(dir, "manifest.json");
  const body = `${JSON.stringify(manifest, null, 2)}\n`;
  try {
    fs.writeFileSync(manifestPath, body, { encoding: "utf8" });
    fsyncPath(manifestPath);
    const verify: unknown = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    if (!verify || typeof verify !== "object" || !("checkpoint_id" in verify)) {
      throw new Error("manifest verify failed");
    }
    for (const file of files) {
      if (file.missing) {
        continue;
      }
      const dest = path.join(filesDir, file.rel.replace(/[\\/]/g, "__"));
      if (sha256File(dest) !== file.sha256) {
        throw new Error(`verify hash mismatch ${file.rel}`);
      }
    }
  } catch {
    return {
      ok: false,
      error: typedError(E.E_CHECKPOINT, "checkpoint flush/verify failed", manifestPath),
    };
  }
  return { ok: true, checkpoint_id: checkpointId, dir, manifest_path: manifestPath, manifest };
}

export function resolveCheckpointRef(projectRoot: string, ref: string): string | undefined {
  const raw = ref.trim();
  if (!raw) {
    return undefined;
  }
  if (raw.endsWith("manifest.json") && fs.existsSync(raw) && fs.statSync(raw).isFile()) {
    return raw;
  }
  const id = raw.replace(/^refs\/hh-ckpt\//, "").replace(/^hh-ckpt\//, "");
  const direct = path.join(projectRoot, ".hh-agent", "checkpoints", id, "manifest.json");
  if (fs.existsSync(direct) && fs.statSync(direct).isFile()) {
    return direct;
  }
  const root = path.join(projectRoot, ".hh-agent", "checkpoints");
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    return undefined;
  }
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return undefined;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const manifestPath = path.join(root, entry.name, "manifest.json");
    if (!fs.existsSync(manifestPath)) {
      continue;
    }
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      if (!parsed || typeof parsed !== "object") {
        continue;
      }
      const rec = parsed as Record<string, unknown>;
      if (rec.checkpoint_id === raw || rec.checkpoint_id === id || rec.git_ref === raw) {
        return manifestPath;
      }
    } catch {
      continue;
    }
  }
  return undefined;
}

function destAllowed(rel: string): boolean {
  const posix = rel.replace(/\\/g, "/");
  if (posix.includes("..") || posix.startsWith("addons/hh_agent") || posix.startsWith(".hh-agent/")) {
    return false;
  }
  return true;
}

export function restoreCheckpoint(
  manifestPath: string,
): { ok: true; restored: string[]; deleted: string[] } | CheckpointErr {
  let manifest: CheckpointManifest;
  try {
    const raw: unknown = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    if (!raw || typeof raw !== "object" || !("files" in raw) || !("checkpoint_id" in raw)) {
      throw new Error("bad manifest");
    }
    manifest = raw as CheckpointManifest;
  } catch {
    return { ok: false, error: typedError(E.E_CHECKPOINT, "checkpoint manifest unreadable", manifestPath) };
  }
  const dir = path.dirname(manifestPath);
  const filesDir = path.join(dir, "files");
  const restored: string[] = [];
  const deleted: string[] = [];
  try {
    for (const file of manifest.files) {
      if (!destAllowed(file.rel)) {
        throw new Error(`refusing restore outside product files ${file.rel}`);
      }
      const dest = path.join(manifest.project_root, file.rel);
      if (file.missing) {
        if (fs.existsSync(dest) && fs.statSync(dest).isFile()) {
          fs.unlinkSync(dest);
          deleted.push(file.rel);
        }
        continue;
      }
      const src = path.join(filesDir, file.rel.replace(/[\\/]/g, "__"));
      if (!fs.existsSync(src)) {
        throw new Error(`quarantine missing ${file.rel}`);
      }
      if (sha256File(src) !== file.sha256) {
        throw new Error(`quarantine hash mismatch ${file.rel}`);
      }
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      const tmp = `${dest}.hh-restore.tmp`;
      fs.copyFileSync(src, tmp);
      fsyncPath(tmp);
      fs.renameSync(tmp, dest);
      restored.push(file.rel);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "restore failed";
    return { ok: false, error: typedError(E.E_CHECKPOINT, message, manifestPath) };
  }
  return { ok: true, restored, deleted };
}
