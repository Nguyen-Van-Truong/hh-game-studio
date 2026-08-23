/** Project-scoped git jail. Never walk up to a parent (studio) repo. */

import fs from "node:fs";
import path from "node:path";

import { jailProjectPath } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";
import { ProcessSupervisor } from "../session/supervisor.js";

export const GIT_EVIDENCE_DIR = "r7w3";
export const GIT_CKPT_DIR = "r7w3/ckpts";
export const LFS_THRESHOLD_BYTES = 65_536;
export const LFS_TYPES = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".wav",
  ".ogg",
  ".mp3",
  ".exr",
  ".hdr",
  ".ttf",
  ".otf",
  ".bin",
]);

const FORBIDDEN_SUB = new Set(["reset", "push", "rebase", "filter-branch", "am", "cherry-pick"]);
const FORBIDDEN_FLAGS = new Set(["--hard", "--force", "--amend"]);
const STRIP_ENV = [
  "GIT_DIR",
  "GIT_WORK_TREE",
  "GIT_COMMON_DIR",
  "GIT_INDEX_FILE",
  "GIT_OBJECT_DIRECTORY",
  "GIT_ALTERNATE_OBJECT_DIRECTORIES",
];

export interface JailedGit {
  worktree: string;
  gitDir: string;
  rel: string;
}

export interface JailGitErr {
  ok: false;
  error: { code: string; message: string; path: string };
}

export interface GitRun {
  status: number;
  stdout: string;
  stderr: string;
}

export function posixRel(rel: string): string {
  return rel.replace(/\\/g, "/").replace(/^\/+/, "");
}

function foldPath(p: string): string {
  const n = p.replace(/\\/g, "/").replace(/\/+$/, "");
  return process.platform === "win32" ? n.toLowerCase() : n;
}

export function underRoot(root: string, candidate: string): boolean {
  const rel = path.relative(root, candidate);
  if (rel === "") {
    return true;
  }
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    return false;
  }
  return foldPath(path.resolve(root, rel)) === foldPath(path.resolve(candidate));
}

function realExisting(p: string): string {
  try {
    return fs.realpathSync.native(p);
  } catch {
    return path.resolve(p);
  }
}

function gitEnv(worktree: string, gitDir: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env };
  for (const key of STRIP_ENV) {
    delete env[key];
  }
  env.GIT_DIR = gitDir;
  env.GIT_WORK_TREE = worktree;
  return env;
}

export function assertSafeGitArgv(argv: readonly string[]): void {
  const sub = argv[0] ?? "";
  if (FORBIDDEN_SUB.has(sub)) {
    throw typedError(E.E_POLICY, `git ${sub} is forbidden (no rewrite/force-push)`, "git");
  }
  for (const arg of argv) {
    if (FORBIDDEN_FLAGS.has(arg) || arg === "-f") {
      throw typedError(E.E_POLICY, `git flag ${arg} is forbidden`, "git");
    }
  }
}

function parseGitDirFile(worktree: string, text: string): string | undefined {
  const match = text.match(/^gitdir:\s*(.+)\s*$/m);
  if (!match || !match[1]) {
    return undefined;
  }
  return path.resolve(worktree, match[1].trim());
}

export function resolveJailedGit(
  projectRoot: string,
  repoRel?: string,
): { ok: true; git: JailedGit } | JailGitErr {
  let workRel = "";
  let workAbs = path.resolve(projectRoot);
  if (repoRel && repoRel.trim()) {
    const jailed = jailProjectPath(projectRoot, posixRel(repoRel), { forWrite: true });
    if (!jailed.ok) {
      return { ok: false, error: jailed.error };
    }
    workRel = jailed.rel;
    workAbs = jailed.abs;
  }
  const rootAbs = realExisting(projectRoot);
  if (!underRoot(rootAbs, workAbs)) {
    return {
      ok: false,
      error: typedError(E.E_PATH, "git worktree escapes project root", repoRel ?? "."),
    };
  }
  const dotGit = path.join(workAbs, ".git");
  if (!fs.existsSync(dotGit)) {
    return {
      ok: false,
      error: typedError(E.E_PATH, "no project-scoped .git (parent walk refused)", workRel || "."),
    };
  }
  let gitDir = dotGit;
  try {
    const st = fs.statSync(dotGit);
    if (st.isFile()) {
      const parsed = parseGitDirFile(workAbs, fs.readFileSync(dotGit, "utf8"));
      if (!parsed) {
        return { ok: false, error: typedError(E.E_PATH, "unreadable gitdir file", workRel || ".") };
      }
      gitDir = parsed;
    } else if (!st.isDirectory()) {
      return { ok: false, error: typedError(E.E_PATH, "invalid .git", workRel || ".") };
    }
  } catch {
    return { ok: false, error: typedError(E.E_PATH, "stat .git failed", workRel || ".") };
  }
  const realGit = realExisting(gitDir);
  if (!underRoot(rootAbs, realGit)) {
    return {
      ok: false,
      error: typedError(E.E_PATH, "git dir is outside the project jail", workRel || "."),
    };
  }
  const rel = workRel || posixRel(path.relative(rootAbs, workAbs));
  return { ok: true, git: { worktree: workAbs, gitDir: realGit, rel } };
}

export function findJailedGitFromPaths(
  projectRoot: string,
  paths: readonly string[],
  repoRel?: string,
): { ok: true; git: JailedGit } | JailGitErr {
  if (repoRel && repoRel.trim()) {
    return resolveJailedGit(projectRoot, repoRel);
  }
  const rootAbs = realExisting(projectRoot);
  for (const raw of paths) {
    const jailed = jailProjectPath(projectRoot, raw, { forWrite: false });
    if (!jailed.ok) {
      continue;
    }
    let cur = fs.existsSync(jailed.abs) && fs.statSync(jailed.abs).isDirectory() ? jailed.abs : path.dirname(jailed.abs);
    while (underRoot(rootAbs, cur)) {
      const probe = resolveJailedGit(projectRoot, posixRel(path.relative(rootAbs, cur)));
      if (probe.ok) {
        return probe;
      }
      if (path.resolve(cur) === rootAbs) {
        break;
      }
      const parent = path.dirname(cur);
      if (parent === cur) {
        break;
      }
      cur = parent;
    }
  }
  return resolveJailedGit(projectRoot);
}

export function runJailedGit(git: JailedGit, argv: readonly string[], timeoutMs = 20_000): GitRun {
  assertSafeGitArgv(argv);
  const supervisor = new ProcessSupervisor();
  const result = supervisor.runSync(
    "git",
    ["-c", `safe.directory=${git.worktree}`, "-c", "core.autocrlf=false", ...argv],
    {
    cwd: git.worktree,
    env: gitEnv(git.worktree, git.gitDir),
    timeout: timeoutMs,
  });
  return {
    status: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

export function verifyToplevel(git: JailedGit): boolean {
  const shown = runJailedGit(git, ["rev-parse", "--show-toplevel"]);
  if (shown.status !== 0) {
    return false;
  }
  const top = foldPath(realExisting(shown.stdout.trim()));
  const work = foldPath(realExisting(git.worktree));
  return top === work;
}

export function jailGitEvidence(
  projectRoot: string,
  rel: string,
): { ok: true; abs: string; rel: string } | JailGitErr {
  const p = posixRel(rel);
  if (p.includes("..") || p.includes("addons/") || p.startsWith(".hh-agent") || p.includes("/.hh-agent")) {
    return { ok: false, error: typedError(E.E_PATH, "git evidence path escapes jail", rel) };
  }
  if (!p.startsWith(`${GIT_EVIDENCE_DIR}/`)) {
    return { ok: false, error: typedError(E.E_PATH, "git evidence writes only under r7w3/", rel) };
  }
  const jailed = jailProjectPath(projectRoot, p, { forWrite: true });
  if (!jailed.ok) {
    return { ok: false, error: jailed.error };
  }
  return { ok: true, abs: jailed.abs, rel: jailed.rel };
}

export function runIdOk(runId: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(runId);
}

export function projectSlugOk(slug: string): boolean {
  return /^[A-Za-z0-9_]{1,64}$/.test(slug);
}

export function agentBranch(project: string, runId: string): string {
  return `agent/${project}/${runId}`;
}
