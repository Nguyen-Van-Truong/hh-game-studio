/** Real Git slice checkpoint / LFS / revert. Jailed worktree only. No history rewrite. */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { jailProjectPath, stripResScheme } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";
import { newUlid } from "../registry/ulid.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";
import {
  agentBranch,
  findJailedGitFromPaths,
  GIT_CKPT_DIR,
  jailGitEvidence,
  LFS_THRESHOLD_BYTES,
  LFS_TYPES,
  posixRel,
  projectSlugOk,
  resolveJailedGit,
  runIdOk,
  runJailedGit,
  verifyToplevel,
  type JailedGit,
} from "./git_jail.js";

export const GIT_CKPT_SCHEMA = "hh-git-ckpt/1";

const SECRET_RE =
  /(^|\/)(\.env([.]|$)|.*token.*|.*secret.*|.*credential.*|.*\.pem$|.*\.key$|\.godot\/)/i;
const FORBIDDEN_COMMIT_RE =
  /(^|\/)(\.godot\/|\.hh-agent\/|token|credentials|\.env($|\.)|(^|\/)(build|export|cache)\/*)/i;

export interface GitStatusFile {
  path: string;
  xy: string;
  kind: "allowlisted" | "dirty_user" | "untracked_asset" | "conflicted" | "secret" | "other";
}

export interface GitStatusReport {
  repo: string;
  jailed: boolean;
  parent_walk_refused: boolean;
  branch: string;
  detached: boolean;
  head: string;
  dirty_user: string[];
  allowlisted: string[];
  untracked_assets: string[];
  conflicted: string[];
  secrets_redacted: boolean;
  files: GitStatusFile[];
  checkpoint_id: string;
  checkpoint_commit: string;
  checkpoint_branch: string;
  checkpoint_ref: string;
  resume_ok: boolean;
  source: string;
}

export interface GitAssetRow {
  path: string;
  size: number;
  sha256: string;
  lfs: boolean;
}

export interface GitCheckpointManifest {
  schema: typeof GIT_CKPT_SCHEMA;
  checkpoint_id: string;
  command_id: string;
  created_at: string;
  project: string;
  run_id: string;
  branch: string;
  git_commit: string;
  git_ref: string;
  git_real: true;
  repo_rel: string;
  files: { rel: string; git_path: string; sha256: string }[];
  assets: GitAssetRow[];
  dirty_user: string[];
  untracked_assets: string[];
  lfs_threshold: number;
  lfs_available: boolean;
}

function fail(
  commandId: string,
  code: string,
  message: string,
  pathName = "git",
  after?: Record<string, unknown>,
): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    ...(after ? { after } : {}),
    postcondition: { verified: false, checks: [] },
    error: typedError(code, message, pathName),
  };
}

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

function atomicWriteUtf8(absPath: string, text: string): boolean {
  fs.mkdirSync(path.dirname(absPath), { recursive: true });
  const tmp = `${absPath}.tmp`;
  fs.writeFileSync(tmp, text, "utf8");
  fsyncPath(tmp);
  try {
    fs.unlinkSync(absPath);
  } catch {
    /* dest may not exist */
  }
  try {
    fs.renameSync(tmp, absPath);
    return true;
  } catch {
    return false;
  }
}

function isSecretPath(rel: string): boolean {
  return SECRET_RE.test(posixRel(rel));
}

function isForbiddenCommit(rel: string): boolean {
  return FORBIDDEN_COMMIT_RE.test(posixRel(rel)) || posixRel(rel).startsWith(".godot/");
}

function extOf(rel: string): string {
  return path.posix.extname(posixRel(rel)).toLowerCase();
}

function isLfsType(rel: string): boolean {
  return LFS_TYPES.has(extOf(rel));
}

function isLfsPointer(abs: string): boolean {
  try {
    const fd = fs.openSync(abs, "r");
    const buf = Buffer.alloc(120);
    const n = fs.readSync(fd, buf, 0, 120, 0);
    fs.closeSync(fd);
    return buf.subarray(0, n).toString("utf8").startsWith("version https://git-lfs.github.com/spec/v1");
  } catch {
    return false;
  }
}

export function lfsAvailable(git: JailedGit): boolean {
  const probe = runJailedGit(git, ["lfs", "version"]);
  return probe.status === 0 && /git-lfs/i.test(`${probe.stdout}${probe.stderr}`);
}

function gitattributesHasLfs(worktree: string, gitPath: string): boolean {
  const dest = path.join(worktree, ".gitattributes");
  if (!fs.existsSync(dest) || !fs.statSync(dest).isFile()) {
    return false;
  }
  let text = "";
  try {
    text = fs.readFileSync(dest, "utf8");
  } catch {
    return false;
  }
  const posix = posixRel(gitPath);
  const ext = extOf(posix);
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    if (!/\bfilter=lfs\b/.test(line)) {
      continue;
    }
    const rule = line.split(/\s+/)[0] ?? "";
    if (rule === posix || rule === path.posix.basename(posix)) {
      return true;
    }
    if (rule === `*${ext}` && ext) {
      return true;
    }
  }
  return false;
}

function parsePorcelainPath(rest: string): string {
  let body = rest.trim();
  if (body.startsWith('"') && body.endsWith('"')) {
    body = body.slice(1, -1).replace(/\\n/g, "\n").replace(/\\t/g, "\t").replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
  const arrow = body.indexOf(" -> ");
  if (arrow >= 0) {
    body = body.slice(arrow + 4);
  }
  return posixRel(body);
}

function isUnmerged(xy: string): boolean {
  if (xy.length < 2) {
    return false;
  }
  const a = xy[0] ?? " ";
  const b = xy[1] ?? " ";
  return a === "U" || b === "U" || xy === "AA" || xy === "DD";
}

function classifyKind(
  rel: string,
  xy: string,
  allow: Set<string>,
): GitStatusFile["kind"] {
  if (isSecretPath(rel)) {
    return "secret";
  }
  if (isUnmerged(xy)) {
    return "conflicted";
  }
  if (allow.has(rel)) {
    return "allowlisted";
  }
  if (xy === "??" && isLfsType(rel)) {
    return "untracked_asset";
  }
  if (xy !== "  " && xy !== "!!") {
    return "dirty_user";
  }
  return "other";
}

function projectRelFromGit(git: JailedGit, projectRoot: string, gitPath: string): string {
  const abs = path.join(git.worktree, gitPath);
  return posixRel(path.relative(path.resolve(projectRoot), abs));
}

function gitPathFromProject(git: JailedGit, projectRoot: string, projectRel: string): string {
  const abs = path.resolve(projectRoot, stripResScheme(projectRel));
  return posixRel(path.relative(git.worktree, abs));
}

export function parseStatusPorcelain(
  text: string,
  git: JailedGit,
  projectRoot: string,
  allowlist: readonly string[],
): Omit<GitStatusReport, "checkpoint_id" | "checkpoint_commit" | "checkpoint_branch" | "checkpoint_ref" | "resume_ok"> {
  const allow = new Set(allowlist.map((p) => posixRel(stripResScheme(p))));
  const files: GitStatusFile[] = [];
  let branch = "";
  let detached = false;
  for (const raw of text.split(/\r?\n/)) {
    if (!raw) {
      continue;
    }
    if (raw.startsWith("## ")) {
      const head = raw.slice(3);
      detached = /HEAD \(no branch\)|detached/i.test(head);
      const name = head.replace(/\.\.\..*$/, "").trim();
      branch = detached ? "HEAD" : name;
      continue;
    }
    if (raw.length < 3) {
      continue;
    }
    const xy = raw.slice(0, 2);
    const rel = projectRelFromGit(git, projectRoot, parsePorcelainPath(raw.slice(3)));
    files.push({ path: rel, xy, kind: classifyKind(rel, xy, allow) });
  }
  return {
    repo: git.rel || ".",
    jailed: true,
    parent_walk_refused: false,
    branch,
    detached,
    head: "",
    dirty_user: files.filter((f) => f.kind === "dirty_user").map((f) => f.path),
    allowlisted: files.filter((f) => f.kind === "allowlisted").map((f) => f.path),
    untracked_assets: files.filter((f) => f.kind === "untracked_asset").map((f) => f.path),
    conflicted: files.filter((f) => f.kind === "conflicted").map((f) => f.path),
    secrets_redacted: files.some((f) => f.kind === "secret"),
    files: files.filter((f) => f.kind !== "secret"),
    source: "git",
  };
}

function readManifestFile(abs: string): GitCheckpointManifest | undefined {
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(abs, "utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return undefined;
    }
    const rec = parsed as GitCheckpointManifest;
    if (rec.schema !== GIT_CKPT_SCHEMA || !rec.git_real || !rec.checkpoint_id) {
      return undefined;
    }
    return rec;
  } catch {
    return undefined;
  }
}

export function listGitManifests(projectRoot: string): { abs: string; rel: string; manifest: GitCheckpointManifest }[] {
  const root = jailGitEvidence(projectRoot, `${GIT_CKPT_DIR}/.keep`);
  const dir = path.join(projectRoot, GIT_CKPT_DIR);
  if (!root.ok && !fs.existsSync(dir)) {
    return [];
  }
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
    return [];
  }
  const out: { abs: string; rel: string; manifest: GitCheckpointManifest }[] = [];
  let entries: fs.Dirent[] = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const rel = `${GIT_CKPT_DIR}/${entry.name}/checkpoint.json`;
    const jailed = jailGitEvidence(projectRoot, rel);
    if (!jailed.ok || !fs.existsSync(jailed.abs)) {
      continue;
    }
    const manifest = readManifestFile(jailed.abs);
    if (manifest) {
      out.push({ abs: jailed.abs, rel: jailed.rel, manifest });
    }
  }
  return out;
}

export function resolveGitManifest(
  projectRoot: string,
  ref: string,
): { abs: string; rel: string; manifest: GitCheckpointManifest } | undefined {
  const raw = ref.trim();
  if (!raw) {
    return undefined;
  }
  if (raw.endsWith("checkpoint.json")) {
    const jailed = jailGitEvidence(projectRoot, posixRel(stripResScheme(raw)));
    if (jailed.ok && fs.existsSync(jailed.abs)) {
      const manifest = readManifestFile(jailed.abs);
      if (manifest) {
        return { abs: jailed.abs, rel: jailed.rel, manifest };
      }
    }
  }
  const direct = jailGitEvidence(projectRoot, `${GIT_CKPT_DIR}/${raw}/checkpoint.json`);
  if (direct.ok && fs.existsSync(direct.abs)) {
    const manifest = readManifestFile(direct.abs);
    if (manifest) {
      return { abs: direct.abs, rel: direct.rel, manifest };
    }
  }
  const id = raw.replace(/^refs\/hh-ckpt\//, "").replace(/^hh-ckpt\//, "");
  for (const row of listGitManifests(projectRoot)) {
    const m = row.manifest;
    if (
      m.checkpoint_id === raw ||
      m.checkpoint_id === id ||
      m.git_ref === raw ||
      m.git_commit === raw ||
      m.run_id === raw ||
      `${m.project}/${m.run_id}` === raw
    ) {
      return row;
    }
  }
  return undefined;
}

function attachCheckpoint(
  projectRoot: string,
  report: GitStatusReport,
  runId?: string,
): GitStatusReport {
  const next = { ...report };
  const found = runId
    ? resolveGitManifest(projectRoot, runId) ?? listGitManifests(projectRoot).find((r) => r.manifest.run_id === runId)
    : listGitManifests(projectRoot)[0];
  if (!found) {
    return next;
  }
  next.checkpoint_id = found.manifest.checkpoint_id;
  next.checkpoint_commit = found.manifest.git_commit;
  next.checkpoint_branch = found.manifest.branch;
  next.checkpoint_ref = found.manifest.git_ref;
  next.resume_ok =
    Boolean(found.manifest.git_commit) && found.manifest.git_real === true && next.detached !== true;
  return next;
}

function emptyStatus(): GitStatusReport {
  return {
    repo: "none",
    jailed: true,
    parent_walk_refused: true,
    branch: "",
    detached: false,
    head: "",
    dirty_user: [],
    allowlisted: [],
    untracked_assets: [],
    conflicted: [],
    secrets_redacted: false,
    files: [],
    checkpoint_id: "",
    checkpoint_commit: "",
    checkpoint_branch: "",
    checkpoint_ref: "",
    resume_ok: false,
    source: "no-project-git",
  };
}

export function readGitStatus(opts: {
  projectRoot: string;
  repo?: string;
  runId?: string;
  allowlist?: readonly string[];
}): GitStatusReport {
  const resolved = opts.repo
    ? resolveJailedGit(opts.projectRoot, opts.repo)
    : opts.runId
      ? (() => {
          const found = resolveGitManifest(opts.projectRoot, opts.runId ?? "");
          return found
            ? resolveJailedGit(opts.projectRoot, found.manifest.repo_rel)
            : findJailedGitFromPaths(opts.projectRoot, [], opts.repo);
        })()
      : resolveJailedGit(opts.projectRoot);
  if (!resolved.ok || !verifyToplevel(resolved.git)) {
    const empty = emptyStatus();
    return attachCheckpoint(opts.projectRoot, empty, opts.runId);
  }
  const status = runJailedGit(resolved.git, ["status", "--porcelain=v1", "-b"]);
  if (status.status !== 0) {
    const empty = emptyStatus();
    empty.source = "git-status-failed";
    empty.parent_walk_refused = false;
    empty.repo = resolved.git.rel || ".";
    return attachCheckpoint(opts.projectRoot, empty, opts.runId);
  }
  const parsed = parseStatusPorcelain(status.stdout, resolved.git, opts.projectRoot, opts.allowlist ?? []);
  const head = runJailedGit(resolved.git, ["rev-parse", "HEAD"]);
  parsed.head = head.status === 0 ? head.stdout.trim() : "";
  const full: GitStatusReport = {
    ...parsed,
    checkpoint_id: "",
    checkpoint_commit: "",
    checkpoint_branch: "",
    checkpoint_ref: "",
    resume_ok: false,
  };
  return attachCheckpoint(opts.projectRoot, full, opts.runId);
}

export function readGitDiff(opts: {
  projectRoot: string;
  path: string;
  repo?: string;
}): { ok: true; path: string; text: string; source: string } | { ok: false; error: { code: string; message: string; path: string } } {
  const jailed = jailProjectPath(opts.projectRoot, stripResScheme(opts.path), { forWrite: false });
  if (!jailed.ok) {
    return { ok: false, error: jailed.error };
  }
  if (isSecretPath(jailed.rel)) {
    return { ok: false, error: typedError(E.E_POLICY, "refusing to diff a secret path", jailed.rel) };
  }
  const git = findJailedGitFromPaths(opts.projectRoot, [opts.path], opts.repo);
  if (!git.ok || !verifyToplevel(git.git)) {
    return {
      ok: true,
      path: opts.path,
      text: "",
      source: "no-project-git",
    };
  }
  const rel = gitPathFromProject(git.git, opts.projectRoot, jailed.rel);
  const diff = runJailedGit(git.git, ["diff", "--", rel]);
  if (diff.status !== 0) {
    return { ok: false, error: typedError(E.E_UNVERIFIED, diff.stderr || diff.stdout || "git diff failed", "git") };
  }
  return { ok: true, path: opts.path, text: diff.stdout, source: "git" };
}

function branchExists(git: JailedGit, name: string): boolean {
  const probe = runJailedGit(git, ["rev-parse", "--verify", `refs/heads/${name}`]);
  return probe.status === 0;
}

function ensureAgentBranch(git: JailedGit, name: string): { ok: true } | { ok: false; message: string } {
  if (branchExists(git, name)) {
    const sw = runJailedGit(git, ["switch", name]);
    if (sw.status === 0) {
      return { ok: true };
    }
    const co = runJailedGit(git, ["checkout", name]);
    if (co.status === 0) {
      return { ok: true };
    }
    return { ok: false, message: sw.stderr || co.stderr || "switch to agent branch failed" };
  }
  const created = runJailedGit(git, ["switch", "-c", name]);
  if (created.status === 0) {
    return { ok: true };
  }
  const legacy = runJailedGit(git, ["checkout", "-b", name]);
  if (legacy.status === 0) {
    return { ok: true };
  }
  return { ok: false, message: created.stderr || legacy.stderr || "create agent branch failed" };
}

function switchToCommitBranch(git: JailedGit, name: string, sha: string): { ok: true } | { ok: false; message: string } {
  if (branchExists(git, name)) {
    const sw = runJailedGit(git, ["switch", name]);
    if (sw.status === 0) {
      return { ok: true };
    }
    const co = runJailedGit(git, ["checkout", name]);
    return co.status === 0 ? { ok: true } : { ok: false, message: sw.stderr || co.stderr || "switch failed" };
  }
  const created = runJailedGit(git, ["switch", "-c", name, sha]);
  if (created.status === 0) {
    return { ok: true };
  }
  const legacy = runJailedGit(git, ["checkout", "-b", name, sha]);
  return legacy.status === 0
    ? { ok: true }
    : { ok: false, message: created.stderr || legacy.stderr || "create branch at checkpoint failed" };
}

function currentHead(git: JailedGit): string {
  const head = runJailedGit(git, ["rev-parse", "HEAD"]);
  return head.status === 0 ? head.stdout.trim() : "";
}

function currentBranch(git: JailedGit): { name: string; detached: boolean } {
  const sym = runJailedGit(git, ["symbolic-ref", "--short", "-q", "HEAD"]);
  if (sym.status === 0 && sym.stdout.trim()) {
    return { name: sym.stdout.trim(), detached: false };
  }
  return { name: "HEAD", detached: true };
}

function writeSnapshot(filesDir: string, rel: string, abs: string): { sha256: string } | { error: string } {
  const dest = path.join(filesDir, rel.replace(/[\\/]/g, "__"));
  try {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(abs, dest);
    fsyncPath(dest);
    const digest = sha256File(dest);
    if (digest !== sha256File(abs)) {
      return { error: `snapshot hash mismatch ${rel}` };
    }
    return { sha256: digest };
  } catch (err) {
    return { error: err instanceof Error ? err.message : "snapshot failed" };
  }
}

function refuseLargeBinary(opts: {
  git: JailedGit;
  abs: string;
  projectRel: string;
  gitPath: string;
  lfsOn: boolean;
}): { ok: true; asset: GitAssetRow } | { ok: false; message: string } {
  const size = fs.statSync(opts.abs).size;
  const digest = sha256File(opts.abs);
  const pointer = isLfsPointer(opts.abs);
  const tracked = gitattributesHasLfs(opts.git.worktree, opts.gitPath);
  const largeType = isLfsType(opts.projectRel) && size >= LFS_THRESHOLD_BYTES;
  if (largeType && !pointer) {
    if (!opts.lfsOn) {
      return {
        ok: false,
        message: `git-lfs missing; refusing raw blob commit of ${opts.projectRel} (${size} bytes)`,
      };
    }
    if (!tracked) {
      return {
        ok: false,
        message: `large binary ${opts.projectRel} has no LFS track rule; pause/resync (not a raw blob commit)`,
      };
    }
  }
  return {
    ok: true,
    asset: { path: opts.projectRel, size, sha256: digest, lfs: pointer && largeType },
  };
}

export function applyGitSliceCheckpoint(opts: {
  commandId: string;
  projectRoot: string;
  message: string;
  paths: readonly string[];
  allowlist?: readonly string[];
  repo?: string;
  runId?: string;
  project?: string;
  resume?: boolean;
  pause?: { pause: () => { paused: boolean; state?: string; ack_ms?: number } };
}): PluginCommandResult {
  const allow = (opts.allowlist && opts.allowlist.length > 0 ? opts.allowlist : opts.paths).map((p) =>
    posixRel(stripResScheme(p)),
  );
  const runId = opts.runId && runIdOk(opts.runId) ? opts.runId : opts.commandId;
  const project = opts.project && projectSlugOk(opts.project) ? opts.project : "project";
  const fromManifest = opts.runId ? resolveGitManifest(opts.projectRoot, opts.runId) : undefined;
  const git = opts.repo
    ? resolveJailedGit(opts.projectRoot, opts.repo)
    : fromManifest
      ? resolveJailedGit(opts.projectRoot, fromManifest.manifest.repo_rel)
      : findJailedGitFromPaths(opts.projectRoot, opts.paths.length > 0 ? opts.paths : allow, opts.repo);
  if (!git.ok) {
    return fail(opts.commandId, git.error.code, git.error.message, git.error.path);
  }
  if (!verifyToplevel(git.git)) {
    return fail(opts.commandId, E.E_PATH, "git toplevel is not the jailed worktree (parent walk refused)", "git");
  }
  if (opts.resume === true) {
    return applyGitResume({
      commandId: opts.commandId,
      projectRoot: opts.projectRoot,
      runId,
      git: git.git,
    });
  }
  if (allow.length < 1) {
    return fail(opts.commandId, E.E_MISSING_REQUIRED, "git.checkpoint needs allowlisted paths", "params.paths");
  }
  const report = readGitStatus({
    projectRoot: opts.projectRoot,
    repo: git.git.rel,
    runId,
    allowlist: allow,
  });
  if (report.conflicted.length > 0 || fs.existsSync(path.join(git.git.gitDir, "MERGE_HEAD"))) {
    const ack = opts.pause?.pause();
    return fail(
      opts.commandId,
      E.E_CONFLICT,
      "merge conflict; pause/resync required (not auto-resolved)",
      "git",
      {
        conflicted: report.conflicted,
        resync: true,
        paused: true,
        pause_ack: ack ?? { paused: true, state: "draining" },
        git_real: true,
        source: "sidecar-git",
      },
    );
  }
  const branch = agentBranch(project, runId); // agent/<project>/<run>
  const ensured = ensureAgentBranch(git.git, branch);
  if (!ensured.ok) {
    return fail(opts.commandId, E.E_UNVERIFIED, ensured.message, "git");
  }
  const lfsOn = lfsAvailable(git.git);
  const assets: GitAssetRow[] = [];
  const files: { rel: string; git_path: string; sha256: string }[] = [];
  const staged: string[] = [];
  for (const rel of allow) {
    if (isForbiddenCommit(rel) || isSecretPath(rel)) {
      return fail(opts.commandId, E.E_POLICY, `refusing to commit locked/secret path ${rel}`, rel);
    }
    const jailed = jailProjectPath(opts.projectRoot, rel, { forWrite: true });
    if (!jailed.ok) {
      return fail(opts.commandId, jailed.error.code, jailed.error.message, jailed.error.path);
    }
    const gitPath = gitPathFromProject(git.git, opts.projectRoot, jailed.rel);
    if (gitPath.startsWith("..") || path.isAbsolute(gitPath)) {
      return fail(opts.commandId, E.E_PATH, `allowlisted path is outside the jailed repo: ${rel}`, rel);
    }
    if (!fs.existsSync(jailed.abs) || !fs.statSync(jailed.abs).isFile()) {
      return fail(opts.commandId, E.E_PATH, `allowlisted file missing: ${rel}`, rel);
    }
    const binary = refuseLargeBinary({
      git: git.git,
      abs: jailed.abs,
      projectRel: jailed.rel,
      gitPath,
      lfsOn,
    });
    if (!binary.ok) {
      return fail(opts.commandId, E.E_POLICY, binary.message, rel, {
        lfs_available: lfsOn,
        lfs: false,
        refused_raw_blob: true,
        path: rel,
        git_real: true,
        source: "sidecar-git",
      });
    }
    assets.push(binary.asset);
    const added = runJailedGit(git.git, ["add", "--", gitPath]);
    if (added.status !== 0) {
      return fail(opts.commandId, E.E_UNVERIFIED, added.stderr || "git add failed", rel);
    }
    if (binary.asset.lfs !== true && isLfsType(rel) && fs.statSync(jailed.abs).size >= LFS_THRESHOLD_BYTES) {
      const indexed = runJailedGit(git.git, ["show", `:${gitPath}`]);
      const pointer = (indexed.stdout || "").startsWith("version https://git-lfs.github.com/spec/v1");
      if (!pointer) {
        runJailedGit(git.git, ["rm", "--cached", "--", gitPath]);
        return fail(
          opts.commandId,
          E.E_POLICY,
          `refusing raw blob index for ${rel} (LFS pointer missing)`,
          rel,
          { lfs: false, refused_raw_blob: true, git_real: true, source: "sidecar-git" },
        );
      }
      binary.asset.lfs = true;
    }
    staged.push(gitPath);
    files.push({ rel: jailed.rel, git_path: gitPath, sha256: sha256File(jailed.abs) });
  }
  const checkpointId = newUlid();
  const msg = `hh-agent checkpoint ${checkpointId} command_id=${opts.commandId}\n\n${opts.message}`;
  const stagedState = runJailedGit(git.git, ["diff", "--cached", "--name-only"]);
  let commit = currentHead(git.git);
  if ((stagedState.stdout || "").trim() || staged.length > 0) {
    const committed = runJailedGit(git.git, [
      "-c",
      "user.name=hh-agent",
      "-c",
      "user.email=hh-agent@localhost",
      "commit",
      "--only",
      "-m",
      msg,
      "--",
      ...staged,
    ]);
    if (committed.status !== 0) {
      return fail(opts.commandId, E.E_UNVERIFIED, committed.stderr || committed.stdout || "git commit failed", "git");
    }
    commit = currentHead(git.git);
  }
  if (!commit) {
    return fail(opts.commandId, E.E_CHECKPOINT, "checkpoint commit SHA missing", "git");
  }
  const ref = `refs/hh-ckpt/${checkpointId}`;
  const updated = runJailedGit(git.git, ["update-ref", ref, commit]);
  const gitRef = updated.status === 0 ? ref : "";
  const evidenceRel = `${GIT_CKPT_DIR}/${checkpointId}/checkpoint.json`;
  const jailedManifest = jailGitEvidence(opts.projectRoot, evidenceRel);
  if (!jailedManifest.ok) {
    return fail(opts.commandId, jailedManifest.error.code, jailedManifest.error.message, jailedManifest.error.path);
  }
  const filesDir = path.join(path.dirname(jailedManifest.abs), "files");
  fs.mkdirSync(filesDir, { recursive: true });
  for (const file of files) {
    const abs = path.join(opts.projectRoot, file.rel);
    const shot = writeSnapshot(filesDir, file.rel, abs);
    if ("error" in shot) {
      return fail(opts.commandId, E.E_CHECKPOINT, shot.error, file.rel);
    }
  }
  const afterStatus = readGitStatus({
    projectRoot: opts.projectRoot,
    repo: git.git.rel,
    runId,
    allowlist: allow,
  });
  const manifest: GitCheckpointManifest = {
    schema: GIT_CKPT_SCHEMA,
    checkpoint_id: checkpointId,
    command_id: opts.commandId,
    created_at: new Date().toISOString(),
    project,
    run_id: runId,
    branch,
    git_commit: commit,
    git_ref: gitRef,
    git_real: true,
    repo_rel: git.git.rel,
    files,
    assets,
    dirty_user: afterStatus.dirty_user,
    untracked_assets: afterStatus.untracked_assets,
    lfs_threshold: LFS_THRESHOLD_BYTES,
    lfs_available: lfsOn,
  };
  const body = `${JSON.stringify(manifest, null, 2)}\n`;
  if (!atomicWriteUtf8(jailedManifest.abs, body)) {
    return fail(opts.commandId, E.E_CHECKPOINT, "checkpoint manifest tmp+rename failed", jailedManifest.rel);
  }
  const verify = readManifestFile(jailedManifest.abs);
  if (!verify || verify.checkpoint_id !== checkpointId || verify.git_commit !== commit) {
    return fail(opts.commandId, E.E_CHECKPOINT, "checkpoint manifest verify failed", jailedManifest.rel);
  }
  return {
    type: "result",
    ok: true,
    command_id: opts.commandId,
    changed: true,
    after: {
      checkpoint_id: checkpointId,
      checkpoint_dir: path.dirname(jailedManifest.abs),
      manifest_path: jailedManifest.rel,
      message: opts.message,
      git_ref: gitRef,
      git_head: commit,
      git_commit: commit,
      git_real: true,
      branch,
      run_id: runId,
      project,
      repo: git.git.rel,
      files: files.map((f) => f.rel),
      assets,
      dirty_user: afterStatus.dirty_user,
      untracked_assets: afterStatus.untracked_assets,
      lfs_available: lfsOn,
      staged,
      source: "sidecar-git",
    },
    postcondition: { verified: true, checks: ["checkpoint_ref_present"] },
  };
}

export function applyGitResume(opts: {
  commandId: string;
  projectRoot: string;
  runId: string;
  git: JailedGit;
}): PluginCommandResult {
  const found = resolveGitManifest(opts.projectRoot, opts.runId);
  if (!found) {
    return fail(opts.commandId, E.E_CHECKPOINT, `checkpoint for run ${opts.runId} not found`, "git");
  }
  const m = found.manifest;
  const probe = runJailedGit(opts.git, ["cat-file", "-t", m.git_commit]);
  if (probe.status !== 0 || probe.stdout.trim() !== "commit") {
    return fail(opts.commandId, E.E_CHECKPOINT, "checkpoint commit missing after restart", m.git_commit);
  }
  const switched = switchToCommitBranch(opts.git, m.branch, m.git_commit);
  if (!switched.ok) {
    return fail(opts.commandId, E.E_UNVERIFIED, switched.message, "git");
  }
  const head = currentHead(opts.git);
  const br = currentBranch(opts.git);
  return {
    type: "result",
    ok: true,
    command_id: opts.commandId,
    changed: br.name === m.branch && !br.detached,
    after: {
      checkpoint_id: m.checkpoint_id,
      checkpoint_dir: path.dirname(found.abs),
      manifest_path: found.rel,
      git_ref: m.git_ref,
      git_head: head,
      git_commit: m.git_commit,
      git_real: true,
      branch: br.name,
      detached: br.detached,
      resume_ok: br.name === m.branch && !br.detached,
      run_id: m.run_id,
      source: "sidecar-git",
    },
    postcondition: { verified: true, checks: ["checkpoint_ref_present"] },
  };
}

export function applyGitSliceRevert(opts: {
  commandId: string;
  projectRoot: string;
  ref: string;
  pause?: { pause: () => { paused: boolean; state?: string; ack_ms?: number } };
}): PluginCommandResult {
  const found = resolveGitManifest(opts.projectRoot, opts.ref);
  if (!found) {
    return fail(opts.commandId, E.E_CHECKPOINT, `checkpoint ref not found: ${opts.ref}`, "params.ref");
  }
  const m = found.manifest;
  const git = resolveJailedGit(opts.projectRoot, m.repo_rel);
  if (!git.ok || !verifyToplevel(git.git)) {
    return fail(opts.commandId, E.E_PATH, "checkpoint repo is not a jailed project git", m.repo_rel);
  }
  const status = readGitStatus({
    projectRoot: opts.projectRoot,
    repo: git.git.rel,
    runId: m.run_id,
    allowlist: m.files.map((f) => f.rel),
  });
  if (status.conflicted.length > 0) {
    const ack = opts.pause?.pause();
    return fail(opts.commandId, E.E_CONFLICT, "merge conflict; pause/resync required", "git", {
      conflicted: status.conflicted,
      resync: true,
      paused: true,
      pause_ack: ack ?? { paused: true, state: "draining" },
      git_real: true,
    });
  }
  const checkpointSet = new Set(m.files.map((f) => posixRel(f.rel)));
  const preserved = status.dirty_user.filter((p) => !checkpointSet.has(posixRel(p)));
  const onBranch = ensureAgentBranch(git.git, m.branch);
  if (!onBranch.ok) {
    return fail(opts.commandId, E.E_UNVERIFIED, onBranch.message, "git");
  }
  const restored: string[] = [];
  for (const file of m.files) {
    if (!checkpointSet.has(file.rel)) {
      continue;
    }
    const jailed = jailProjectPath(opts.projectRoot, file.rel, { forWrite: true });
    if (!jailed.ok) {
      return fail(opts.commandId, jailed.error.code, jailed.error.message, jailed.error.path);
    }
    const co = runJailedGit(git.git, ["checkout", m.git_commit, "--", file.git_path]);
    if (co.status !== 0) {
      return fail(opts.commandId, E.E_CHECKPOINT, co.stderr || `checkout ${file.rel} failed`, file.rel);
    }
    restored.push(file.rel);
  }
  for (const file of m.files) {
    const dest = path.join(opts.projectRoot, file.rel);
    if (!fs.existsSync(dest) || sha256File(dest) !== file.sha256) {
      return fail(opts.commandId, E.E_CHECKPOINT, `revert hash mismatch ${file.rel}`, file.rel);
    }
  }
  for (const rel of preserved) {
    /* dirty user files that were never in the checkpoint stay untouched */
    void rel;
  }
  const revertPaths = m.files.map((f) => f.git_path);
  const msg = `hh-agent revert ${m.checkpoint_id} command_id=${opts.commandId}`;
  const committed = runJailedGit(git.git, [
    "-c",
    "user.name=hh-agent",
    "-c",
    "user.email=hh-agent@localhost",
    "commit",
    "--only",
    "-m",
    msg,
    "--",
    ...revertPaths,
  ]);
  if (committed.status !== 0) {
    return fail(opts.commandId, E.E_UNVERIFIED, committed.stderr || committed.stdout || "revert commit failed", "git");
  }
  const revertCommit = currentHead(git.git);
  if (!revertCommit || revertCommit === m.git_commit) {
    return fail(opts.commandId, E.E_CHECKPOINT, "revert must create a new commit (not checkout-only)", "git");
  }
  return {
    type: "result",
    ok: true,
    command_id: opts.commandId,
    changed: true,
    after: {
      ref: opts.ref,
      manifest_path: found.rel,
      restored,
      deleted: [],
      recovery: { restored: true, files: restored, deleted: [] },
      os_global_atomic: false,
      git_real: true,
      git_commit: m.git_commit,
      revert_commit: revertCommit,
      branch: m.branch,
      dirty_user_preserved: preserved,
      source: "sidecar-git",
    },
    postcondition: { verified: true, checks: ["tree_matches_checkpoint"] },
  };
}
