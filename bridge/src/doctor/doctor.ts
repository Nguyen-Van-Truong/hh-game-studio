import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { LOOPBACK_HOST } from "../transport/loopback.js";
import { E, typedError } from "../registry/errors.js";
import { PROTOCOL, REGISTRY_VERSION } from "../registry/types.js";
import { publicDescriptorView, readDescriptor, type SessionDescriptor } from "../session/descriptor.js";
import { agentHome, descriptorPath, isUnderAgentHome } from "../session/paths.js";
import { pidAlive } from "../session/supervisor.js";
import { assessCompatLock } from "../policy/compat_lock.js";
import {
  findRepoRoot,
  installedTemplatesDir,
  PINNED_REGISTRY,
  PINNED_VERSION_ID,
  pinnedConsolePath,
  pinnedTemplatesTpz,
  versionIsRefused,
} from "./pin.js";

export interface DoctorCheck {
  id: string;
  ok: boolean;
  detail: string;
}

export interface DoctorReport {
  ok: boolean;
  protocol: typeof PROTOCOL;
  registry_version: typeof REGISTRY_VERSION;
  pin_version_id: typeof PINNED_VERSION_ID;
  home: "LOCALAPPDATA/HHGodotAgent";
  loopback: typeof LOOPBACK_HOST;
  session_present: boolean;
  pid_alive: boolean;
  descriptor_under_home: boolean;
  token_in_report: boolean;
  checks: string[];
  check_details: DoctorCheck[];
  error?: { code: string; message: string; path: string };
  session?: Record<string, unknown>;
}

export interface DoctorOptions {
  desc?: SessionDescriptor;
  home?: string;
  projectRoot?: string;
  godotExe?: string;
  forceGodotVersion?: string;
  forceProtocol?: string;
  forceSchema?: string;
}

const VENDOR_POLICY_NEEDLES = ["satellite" + "oflove", "MCPGame" + "Bridge", "godot" + "_mcp"];

export function tokenAbsentFromBlob(blob: string, token: string): boolean {
  return !token || !blob.includes(token);
}

function readTextIfFile(abs: string): string {
  try {
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      return fs.readFileSync(abs, "utf8").trim();
    }
  } catch {
    /* ignore */
  }
  return "";
}

function schemaFromProject(projectRoot: string | undefined, repo: string | undefined): string {
  if (projectRoot) {
    const planted = readTextIfFile(path.join(projectRoot, ".hh-agent", "schema-version"));
    if (planted) {
      return planted;
    }
    const actions = path.join(projectRoot, "addons", "hh_agent", "core", "actions.json");
    const raw = readTextIfFile(actions);
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && "registry_version" in parsed) {
          const ver = (parsed as { registry_version?: unknown }).registry_version;
          if (typeof ver === "string" && ver) {
            return ver;
          }
        }
      } catch {
        /* fall through */
      }
    }
  }
  if (repo) {
    const generated = path.join(repo, "bridge", "generated", "plugin-validator.json");
    const raw = readTextIfFile(generated);
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && "registry_version" in parsed) {
          const ver = (parsed as { registry_version?: unknown }).registry_version;
          if (typeof ver === "string" && ver) {
            return ver;
          }
        }
      } catch {
        /* fall through */
      }
    }
  }
  return REGISTRY_VERSION;
}

function protocolFromProject(projectRoot: string | undefined, desc?: SessionDescriptor): string {
  if (projectRoot) {
    const planted = readTextIfFile(path.join(projectRoot, ".hh-agent", "protocol"));
    if (planted) {
      return planted;
    }
    const actions = path.join(projectRoot, "addons", "hh_agent", "core", "actions.json");
    const raw = readTextIfFile(actions);
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && "protocol" in parsed) {
          const proto = (parsed as { protocol?: unknown }).protocol;
          if (typeof proto === "string" && proto) {
            return proto;
          }
        }
      } catch {
        /* fall through */
      }
    }
  }
  return desc?.protocol ?? PROTOCOL;
}

function policyOk(projectRoot: string | undefined): { ok: boolean; detail: string } {
  if (!projectRoot) {
    return { ok: false, detail: "no project root; OWNER_AUTOPILOT cannot be proven" };
  }
  const godot = path.join(projectRoot, "project.godot");
  const text = readTextIfFile(godot);
  for (const needle of VENDOR_POLICY_NEEDLES) {
    if (text.includes(needle)) {
      return { ok: false, detail: `vendor MCP needle ${needle} in project.godot` };
    }
  }
  const addons = path.join(projectRoot, "addons");
  if (fs.existsSync(addons)) {
    const names = fs.readdirSync(addons);
    for (const name of names) {
      const lower = name.toLowerCase();
      if (VENDOR_POLICY_NEEDLES.some((needle) => lower.includes(needle.toLowerCase()))) {
        return { ok: false, detail: `vendor addon ${name}` };
      }
    }
  }
  return { ok: true, detail: "OWNER_AUTOPILOT is project-scoped; no vendor MCP in project" };
}

function add(
  details: DoctorCheck[],
  lines: string[],
  id: string,
  ok: boolean,
  detail: string,
): void {
  details.push({ id, ok, detail });
  lines.push(`${ok ? "ok" : "fail"}:${id} ${detail}`);
}

function godotVersionSpawn(exe: string): { command: string; args: string[] } {
  const lower = exe.toLowerCase();
  if (lower.endsWith(".js") || lower.endsWith(".mjs") || lower.endsWith(".cjs")) {
    return { command: process.execPath, args: [exe, "--version"] };
  }
  if (process.platform === "win32" && (lower.endsWith(".cmd") || lower.endsWith(".bat"))) {
    return { command: process.env.ComSpec ?? "cmd.exe", args: ["/d", "/s", "/c", exe, "--version"] };
  }
  return { command: exe, args: ["--version"] };
}

function runGodotVersion(exe: string): { ok: boolean; text: string } {
  if (!fs.existsSync(exe)) {
    return { ok: false, text: "" };
  }
  const spec = godotVersionSpawn(exe);
  const proc = spawnSync(spec.command, spec.args, {
    encoding: "utf8",
    timeout: 15_000,
    windowsHide: true,
  });
  const text = `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim().split(/\r?\n/)[0] ?? "";
  return { ok: proc.error === undefined && text.length > 0, text };
}

function runGit(projectRoot: string, args: string[]): { ok: boolean; text: string } {
  const proc = spawnSync("git", ["-C", projectRoot, ...args], {
    encoding: "utf8",
    timeout: 10_000,
    windowsHide: true,
  });
  const text = `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim();
  return { ok: proc.status === 0, text };
}

function pluginEnabled(projectRoot: string): boolean {
  const cfg = path.join(projectRoot, "addons", "hh_agent", "plugin.cfg");
  if (!fs.existsSync(cfg)) {
    return false;
  }
  const godot = path.join(projectRoot, "project.godot");
  if (!fs.existsSync(godot)) {
    return false;
  }
  const text = fs.readFileSync(godot, "utf8");
  return text.includes("res://addons/hh_agent/plugin.cfg");
}

function firstError(
  details: DoctorCheck[],
  extra?: { code: string; message: string; path: string },
): { code: string; message: string; path: string } | undefined {
  if (extra) {
    return extra;
  }
  const failed = details.find((item) => !item.ok);
  if (!failed) {
    return undefined;
  }
  if (failed.id === "godot_version") {
    return typedError(E.E_VERSION_SKEW, failed.detail, "godot.version");
  }
  if (failed.id === "capability_lock") {
    return typedError(E.E_VERSION_SKEW, failed.detail, "capability-lock");
  }
  if (failed.id === "binary") {
    return typedError(E.E_UNVERIFIED, failed.detail, "godot.binary");
  }
  if (failed.id === "protocol") {
    return typedError(E.E_PROTOCOL_VERSION, failed.detail, "protocol");
  }
  if (failed.id === "schema") {
    return typedError(E.E_ACTION_VERSION, failed.detail, "schema");
  }
  return typedError(E.E_UNVERIFIED, failed.detail, failed.id);
}

export function runDoctor(opts: DoctorOptions = {}): DoctorReport {
  const home = opts.home ?? agentHome();
  const details: DoctorCheck[] = [];
  const checks: string[] = [
    "bind is loopback with OS-assigned port",
    "session store is LOCALAPPDATA/HHGodotAgent",
    "token is never written to stdout",
  ];
  let session_present = false;
  let pid_ok = false;
  let under = false;
  let view: Record<string, unknown> | undefined;
  let skew: { code: string; message: string; path: string } | undefined;

  const repo = opts.projectRoot ? findRepoRoot(opts.projectRoot) : undefined;
  const protocolSeen = opts.forceProtocol ?? protocolFromProject(opts.projectRoot, opts.desc);
  const schemaSeen = opts.forceSchema ?? schemaFromProject(opts.projectRoot, repo);

  if (protocolSeen !== PROTOCOL) {
    skew = typedError(
      E.E_VERSION_SKEW,
      `protocol ${protocolSeen} != ${PROTOCOL}`,
      "protocol",
    );
    add(details, checks, "protocol", false, skew.message);
  } else {
    add(details, checks, "protocol", true, PROTOCOL);
  }

  if (schemaSeen !== REGISTRY_VERSION || schemaSeen !== PINNED_REGISTRY) {
    if (!skew) {
      skew = typedError(
        E.E_VERSION_SKEW,
        `schema ${schemaSeen} != ${REGISTRY_VERSION}`,
        "schema",
      );
    }
    add(details, checks, "schema", false, `schema ${schemaSeen} != ${REGISTRY_VERSION}`);
  } else {
    add(details, checks, "schema", true, REGISTRY_VERSION);
  }

  if (opts.desc) {
    session_present = true;
    pid_ok = pidAlive(opts.desc.pid);
    under = isUnderAgentHome(descriptorPath(opts.desc.project_id, home), home);
    view = publicDescriptorView(opts.desc);
    add(details, checks, "loopback", opts.desc.host === LOOPBACK_HOST, `host=${opts.desc.host}`);
    add(details, checks, "session_protocol", opts.desc.protocol === PROTOCOL, opts.desc.protocol);
    add(details, checks, "pid", pid_ok, pid_ok ? "sidecar pid is alive" : "sidecar pid is not alive");
    if (opts.desc.host !== LOOPBACK_HOST && !skew) {
      skew = typedError(E.E_BIND, "descriptor host is not loopback", "host");
    }
  } else {
    add(details, checks, "loopback", true, LOOPBACK_HOST);
  }

  const consoleExe = opts.godotExe ?? pinnedConsolePath(home);
  const binaryPresent = fs.existsSync(consoleExe);
  add(
    details,
    checks,
    "binary",
    binaryPresent,
    binaryPresent ? consoleExe : "pinned 4.7.1-stable console exe is not installed",
  );

  let observedVersion = opts.forceGodotVersion ?? "";
  if (!observedVersion && binaryPresent) {
    const ran = runGodotVersion(consoleExe);
    observedVersion = ran.text;
  }
  if (opts.forceGodotVersion || binaryPresent) {
    const refused = versionIsRefused(observedVersion);
    const match = observedVersion === PINNED_VERSION_ID;
    const versionOk = !refused && match;
    add(
      details,
      checks,
      "godot_version",
      versionOk,
      observedVersion
        ? `--version ${observedVersion}`
        : "godot --version produced no output",
    );
    if (!versionOk && !skew) {
      skew = typedError(
        E.E_VERSION_SKEW,
        refused
          ? `refused Godot ${observedVersion}`
          : `Godot ${observedVersion || "(empty)"} != pin ${PINNED_VERSION_ID}`,
        "godot.version",
      );
    }
  } else {
    add(details, checks, "godot_version", false, "cannot read --version without pin exe");
  }

  const tpz = pinnedTemplatesTpz(home);
  const installed = installedTemplatesDir();
  const templatesOk =
    (installed !== undefined && fs.existsSync(installed)) || fs.existsSync(tpz);
  add(
    details,
    checks,
    "templates",
    templatesOk,
    templatesOk
      ? installed && fs.existsSync(installed)
        ? installed
        : tpz
      : "export templates 4.7.1.stable not installed and tpz cache missing",
  );

  const projectRoot = opts.projectRoot ?? opts.desc?.project_root;
  if (projectRoot) {
    const lock = assessCompatLock(projectRoot);
    add(
      details,
      checks,
      "capability_lock",
      !lock.mismatch,
      lock.mismatch ? lock.reason : "lock matches pin; Observe/Doctor only on mismatch",
    );
    if (lock.mismatch && !skew) {
      skew = typedError(E.E_VERSION_SKEW, lock.reason, "capability-lock");
    }
    const pluginOk = pluginEnabled(projectRoot);
    add(
      details,
      checks,
      "plugin",
      pluginOk,
      pluginOk ? "hh_agent enabled in project.godot" : "hh_agent missing or not enabled",
    );
    const repo = findRepoRoot(projectRoot);
    add(
      details,
      checks,
      "bridge",
      repo !== undefined && fs.existsSync(path.join(repo, "bridge", "package.json")),
      repo ? path.join(repo, "bridge") : "bridge package not found from project",
    );
    const git = runGit(projectRoot, ["rev-parse", "--is-inside-work-tree"]);
    add(details, checks, "git", git.ok && git.text === "true", git.ok ? "git work tree" : git.text || "git missing");
    const policy = policyOk(projectRoot);
    add(details, checks, "policy", policy.ok, policy.detail);
  } else {
    add(details, checks, "plugin", false, "no project root");
    add(details, checks, "bridge", false, "no project root");
    add(details, checks, "git", false, "no project root");
    const policy = policyOk(undefined);
    add(details, checks, "policy", policy.ok, policy.detail);
  }

  const preview = JSON.stringify({
    checks,
    check_details: details,
    session: view,
  });
  const token = opts.desc?.token ?? "";
  const redacted = tokenAbsentFromBlob(preview, token);
  add(
    details,
    checks,
    "token_redacted",
    redacted,
    redacted ? "token absent from doctor body" : "session token leaked into doctor body",
  );

  const error = firstError(details, skew);
  const ok = error === undefined && details.every((item) => item.ok);
  const report: DoctorReport = {
    ok,
    protocol: PROTOCOL,
    registry_version: REGISTRY_VERSION,
    pin_version_id: PINNED_VERSION_ID,
    home: "LOCALAPPDATA/HHGodotAgent",
    loopback: LOOPBACK_HOST,
    session_present,
    pid_alive: pid_ok,
    descriptor_under_home: under,
    token_in_report: !redacted,
    checks,
    check_details: details,
  };
  if (error) {
    report.error = error;
  }
  if (view) {
    report.session = view;
  }
  return report;
}

/** Session-only subset kept for callers that still import the R2-WP2 name. */
export function runSessionDoctor(desc?: SessionDescriptor, home = agentHome()): DoctorReport {
  return runDoctor({ ...(desc ? { desc } : {}), home });
}

export function doctorFromProjectId(projectId: string, home = agentHome()): DoctorReport {
  try {
    const desc = readDescriptor(projectId, home);
    return runDoctor({ desc, home, projectRoot: desc.project_root });
  } catch {
    return runDoctor({ home });
  }
}
