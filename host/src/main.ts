import { Host, showSession, type HostOptions } from "./host.js";
import { E, HostError } from "./errors.js";
import { SESSION_MS } from "./paths.js";

function flag(name: string): boolean {
  return process.argv.includes(name);
}

function argValue(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  if (i < 0) {
    return undefined;
  }
  const v = process.argv[i + 1];
  return v;
}

function writeReport(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function fail(err: HostError): never {
  writeReport({ ok: false, error: err.typed() });
  process.exit(1);
}

function parseMode(): "persistent" | "interactive" {
  const raw = argValue("--mode") ?? "persistent";
  if (raw === "interactive" || raw === "persistent") {
    return raw;
  }
  throw new HostError(E.E_POLICY, "mode must be persistent or interactive", "mode");
}

function parseProvider(): "fake" | "configured" {
  const raw = argValue("--provider") ?? "fake";
  if (raw === "fake" || raw === "configured") {
    return raw;
  }
  throw new HostError(E.E_POLICY, "provider must be fake or configured", "provider");
}

function parseBudget(): number | undefined {
  const raw = argValue("--budget");
  if (raw === undefined) {
    return undefined;
  }
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 0) {
    throw new HostError(E.E_POLICY, "budget must be a non-negative integer", "budget");
  }
  return n;
}

function commonOpts(mode: "persistent" | "interactive"): HostOptions {
  const opts: HostOptions = {
    mode,
    providerName: parseProvider(),
  };
  const sessionId = argValue("--session-id");
  if (sessionId) {
    opts.sessionId = sessionId;
  }
  const taskId = argValue("--task-id");
  if (taskId) {
    opts.taskId = taskId;
  }
  const commandId = argValue("--command-id");
  if (commandId) {
    opts.commandId = commandId;
  }
  const script = argValue("--script");
  if (script) {
    opts.scriptPath = script;
  }
  const budget = parseBudget();
  if (budget !== undefined) {
    opts.maxSteps = budget;
  }
  if (flag("--hold-after-decision")) {
    opts.holdAfterDecision = true;
  }
  return opts;
}

function main(): void {
  try {
    if (flag("--help")) {
      process.stderr.write(
        "hh-godot-host: persistent Agent Host. Interactive IDE clients are the host.\n" +
          "  --provider fake|configured  --mode persistent|interactive\n" +
          "  --resume <session_id>  --hold-after-decision\n" +
          "  --show|--compact|--cancel <session_id>\n" +
          "  --compact <session_id> [--project <godot-project> --job-id <id>]\n" +
          `  session length ${SESSION_MS} ms (90 minutes)\n`,
      );
      process.exitCode = 0;
      return;
    }

    const showId = argValue("--show");
    if (showId) {
      writeReport(showSession(showId));
      return;
    }
    const compactId = argValue("--compact");
    if (compactId) {
      const projectRoot = argValue("--project");
      const jobId = argValue("--job-id");
      const state = Host.compact(compactId, {
        ...(projectRoot ? { projectRoot } : {}),
        ...(jobId ? { jobId } : {}),
      });
      const shown = showSession(state.session_id);
      if (projectRoot && jobId) {
        shown.resource_uri = "session://state";
        shown.resource_path = `r7w5/${jobId}/state.json`;
        shown.job_id = jobId;
        shown.transcript = [];
      }
      writeReport(shown);
      return;
    }
    const cancelId = argValue("--cancel");
    if (cancelId) {
      const state = Host.cancel(cancelId);
      writeReport({
        ok: false,
        error: { code: E.E_CANCELLED, message: "host session cancelled", path: "cancel" },
        session_id: state.session_id,
        task_id: state.task_id,
        command_id: state.command_id,
      });
      process.exitCode = 1;
      return;
    }

    const resumeId = argValue("--resume");
    const mode = parseMode();
    if (resumeId) {
      const host = Host.resume({ ...commonOpts(mode), sessionId: resumeId });
      const report = host.run();
      writeReport(report);
      if (!report.ok) {
        process.exitCode = 1;
      }
      return;
    }

    const host = Host.create(commonOpts(mode));
    const report = host.run();
    writeReport(report);
    if (report.phase === "held_after_decision") {
      return;
    }
    if (!report.ok) {
      process.exitCode = 1;
    }
  } catch (err) {
    if (err instanceof HostError) {
      fail(err);
    }
    const message = err instanceof Error ? err.message : "host failed";
    fail(new HostError(E.E_POLICY, message, "host"));
  }
}

void main();
