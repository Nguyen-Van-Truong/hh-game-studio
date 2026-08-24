import { resolveCredential } from "./credentials.js";
import { FakeExecutor, type ToolExecutor, type ToolResult } from "./executor.js";
import { E, HostError } from "./errors.js";
import { agentHome, isUnderAgentHome, statePath } from "./paths.js";
import { ConfiguredProvider } from "./providers/configured.js";
import { FakeProvider, loadFakeScript } from "./providers/fake.js";
import type { ModelContext, Provider } from "./providers/types.js";
import { redactSecrets } from "./redact.js";
import {
  assertRunnable,
  compactState,
  loadHostState,
  newHostState,
  pidAlive,
  saveHostState,
  type HostMode,
  type HostState,
  type ToolRecord,
} from "./session.js";
import { writeHostSoakResource } from "./soak_resource.js";
import { newUlid, parseUlid } from "./ulid.js";

export interface HostOptions {
  mode: HostMode;
  providerName: "fake" | "configured";
  sessionId?: string;
  taskId?: string;
  commandId?: string;
  scriptPath?: string;
  maxSteps?: number;
  holdAfterDecision?: boolean;
  secrets?: string[];
}

export interface HostReport {
  ok: boolean;
  mode: HostMode;
  provider: string;
  model: string;
  session_id: string;
  task_id: string;
  command_id: string;
  started_at: number;
  deadline_at: number;
  session_ms: number;
  phase: string;
  compacted: boolean;
  persist_path: string;
  tools: Array<{
    task_id: string;
    command_id: string;
    tool: string;
    action: string;
    result: ToolResult;
  }>;
  plan: { summary: string };
  context_summary: string;
  error?: { code: string; message: string; path: string };
}

/**
 * Host is the ONLY class that calls the model and decides the tool loop.
 * Sidecar/plugin stay deterministic execution. Interactive IDE clients are
 * this same class; unattended uses a persistent process of this class.
 */
export class Host {
  readonly provider: Provider;
  readonly executor: ToolExecutor;
  readonly secrets: string[];
  private state: HostState;
  private readonly holdAfterDecision: boolean;
  private held = false;

  private constructor(
    provider: Provider,
    executor: ToolExecutor,
    state: HostState,
    holdAfterDecision: boolean,
    secrets: string[],
  ) {
    this.provider = provider;
    this.executor = executor;
    this.state = state;
    this.holdAfterDecision = holdAfterDecision;
    this.secrets = secrets;
  }

  static create(opts: HostOptions): Host {
    const built = buildProvider(opts);
    const sessionId = opts.sessionId ? parseUlid(opts.sessionId, "session_id") : newUlid();
    const taskId = opts.taskId ? parseUlid(opts.taskId, "task_id") : newUlid();
    const commandId = opts.commandId ? parseUlid(opts.commandId, "command_id") : newUlid();
    const persist = statePath(sessionId);
    if (!isUnderAgentHome(persist)) {
      throw new HostError(E.E_PATH, "host state escaped HHGodotAgent", "persist");
    }
    const state = newHostState({
      session_id: sessionId,
      task_id: taskId,
      command_id: commandId,
      mode: opts.mode,
      provider: built.provider.name,
      model: built.provider.model,
      max_steps: opts.maxSteps ?? 16,
      persist_path: persist,
    });
    const host = new Host(
      built.provider,
      new FakeExecutor(),
      state,
      opts.holdAfterDecision === true,
      built.secrets,
    );
    host.persist();
    return host;
  }

  static resume(opts: HostOptions & { sessionId: string }): Host {
    const sessionId = parseUlid(opts.sessionId, "session_id");
    const state = loadHostState(sessionId);
    if (pidAlive(state.writer_pid) && state.writer_pid !== process.pid) {
      throw new HostError(E.E_BUSY, "session has a live host process", "writer_pid");
    }
    const resumeOpts: HostOptions = {
      mode: opts.mode,
      providerName: state.provider === "configured" ? "configured" : "fake",
    };
    if (opts.scriptPath) {
      resumeOpts.scriptPath = opts.scriptPath;
    }
    if (opts.secrets) {
      resumeOpts.secrets = opts.secrets;
    }
    const built = buildProvider(resumeOpts);
    const now = Date.now();
    state.wakeup_at = now;
    state.handoff = { from_pid: state.writer_pid, to_pid: process.pid, at: now };
    state.writer_pid = process.pid;
    state.heartbeat_at = now;
    if (state.phase === "held_after_decision") {
      state.phase = "running";
    }
    const host = new Host(built.provider, new FakeExecutor(), state, false, built.secrets);
    host.persist();
    return host;
  }

  static load(sessionId: string): HostState {
    return loadHostState(parseUlid(sessionId, "session_id"));
  }

  static compact(
    sessionId: string,
    opts?: { projectRoot?: string; jobId?: string },
  ): HostState {
    const state = compactState(loadHostState(parseUlid(sessionId, "session_id")));
    saveHostState(state);
    const projectRoot = opts?.projectRoot;
    const jobId = opts?.jobId;
    if (projectRoot && jobId) {
      writeHostSoakResource({ projectRoot, jobId, state });
    }
    return state;
  }

  static cancel(sessionId: string): HostState {
    const state = loadHostState(parseUlid(sessionId, "session_id"));
    state.cancelled = true;
    state.phase = "cancelled";
    state.heartbeat_at = Date.now();
    saveHostState(state);
    return state;
  }

  private modelContext(): ModelContext {
    return {
      task_id: this.state.task_id,
      command_id: this.state.command_id,
      plan_summary: this.state.plan.summary,
      step: this.state.tools.length,
      last_tools: this.state.tools.map((row) => ({ tool: row.tool, action: row.action })),
    };
  }

  private log(line: string): void {
    process.stderr.write(`${redactSecrets(line, this.secrets)}\n`);
  }

  private persist(): void {
    this.state.heartbeat_at = Date.now();
    this.state.persist_path = statePath(this.state.session_id);
    if (!isUnderAgentHome(this.state.persist_path, agentHome())) {
      throw new HostError(E.E_PATH, "host state escaped HHGodotAgent", "persist");
    }
    saveHostState(this.state);
  }

  private finishInflight(): void {
    const inflight = this.state.inflight;
    if (!inflight) {
      return;
    }
    const result = this.executor.execute({
      tool: inflight.tool,
      action: inflight.action,
      params: inflight.params,
    });
    const record: ToolRecord = {
      task_id: inflight.task_id,
      command_id: inflight.command_id,
      tool: inflight.tool,
      action: inflight.action,
      result,
    };
    this.state.tools.push(record);
    delete this.state.inflight;
    this.state.phase = "awaiting_model";
    this.state.context_summary =
      `task=${this.state.task_id} command=${this.state.command_id} last=${inflight.tool}.${inflight.action}`;
    this.persist();
    this.log(`host tool ${inflight.tool}.${inflight.action} session=${this.state.session_id}`);
  }

  private hangForKill(): void {
    this.log(`host holding after decision session=${this.state.session_id}`);
    const beat = (): void => {
      this.state.heartbeat_at = Date.now();
      saveHostState(this.state);
    };
    setInterval(beat, 1000);
  }

  /**
   * Decide the next tool via the provider, persist in-flight command_id,
   * optionally hold so a test can kill this process, then execute.
   */
  run(): HostReport {
    try {
      if (this.state.inflight) {
        this.finishInflight();
      }
      while (this.state.phase !== "done" && this.state.phase !== "cancelled") {
        assertRunnable(this.state);
        const turn = this.provider.generate(this.modelContext());
        this.state.budget.used_steps += 1;
        if (turn.kind === "done") {
          this.state.phase = "done";
          this.state.plan = { summary: turn.summary };
          this.state.context_summary =
            `task=${this.state.task_id} command=${this.state.command_id} plan=${turn.summary}`;
          this.persist();
          break;
        }
        this.state.inflight = {
          tool: turn.tool,
          action: turn.action,
          params: turn.params,
          command_id: this.state.command_id,
          task_id: this.state.task_id,
        };
        this.state.phase = "held_after_decision";
        this.persist();
        if (this.holdAfterDecision && !this.held) {
          this.held = true;
          this.hangForKill();
          return this.report(false);
        }
        this.finishInflight();
      }
      return this.report(true);
    } catch (err) {
      if (err instanceof HostError) {
        this.state.phase = err.code === E.E_CANCELLED ? "cancelled" : "failed";
        this.persist();
        const report = this.report(false);
        report.error = err.typed();
        return report;
      }
      throw err;
    }
  }

  report(ok = this.state.phase === "done"): HostReport {
    const out: HostReport = {
      ok,
      mode: this.state.mode,
      provider: this.state.provider,
      model: this.state.model,
      session_id: this.state.session_id,
      task_id: this.state.task_id,
      command_id: this.state.command_id,
      started_at: this.state.started_at,
      deadline_at: this.state.deadline_at,
      session_ms: this.state.session_ms,
      phase: this.state.phase,
      compacted: this.state.compacted,
      persist_path: this.state.persist_path,
      tools: this.state.tools.map((row) => ({
        task_id: row.task_id,
        command_id: row.command_id,
        tool: row.tool,
        action: row.action,
        result: row.result,
      })),
      plan: this.state.plan,
      context_summary: this.state.context_summary,
    };
    return out;
  }
}

function buildProvider(opts: HostOptions): { provider: Provider; secrets: string[] } {
  const secrets: string[] = [...(opts.secrets ?? [])];
  if (opts.providerName === "configured") {
    const cred = resolveCredential("configured");
    secrets.push(cred.token);
    return { provider: new ConfiguredProvider(cred), secrets };
  }
  const script = opts.scriptPath ? loadFakeScript(opts.scriptPath) : undefined;
  return { provider: new FakeProvider(script), secrets };
}

export function showSession(sessionId: string): Record<string, unknown> {
  const state = Host.load(sessionId);
  return {
    ok: true,
    session_id: state.session_id,
    task_id: state.task_id,
    command_id: state.command_id,
    phase: state.phase,
    compacted: state.compacted,
    plan: state.plan,
    context_summary: state.context_summary,
    persist_path: state.persist_path,
    started_at: state.started_at,
    deadline_at: state.deadline_at,
    session_ms: state.session_ms,
    tools: state.tools.map((row) => ({
      task_id: row.task_id,
      command_id: row.command_id,
      tool: row.tool,
      action: row.action,
    })),
  };
}
