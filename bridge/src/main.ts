import { runSessionDoctor } from "./doctor/doctor.js";
import { readDescriptor } from "./session/descriptor.js";
import { agentHome } from "./session/paths.js";
import { discoverProject } from "./session/project.js";
import { startSidecar } from "./session/session.js";
import { startMcpStdio } from "./transport/mcp_stdio.js";

function flag(name: string): boolean {
  return process.argv.includes(name);
}

function argValue(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  if (i < 0) {
    return undefined;
  }
  return process.argv[i + 1];
}

async function main(): Promise<void> {
  const project = argValue("--project");
  if (!project) {
    process.stderr.write("usage: node dist/main.js --project <godot-project>\n");
    process.exitCode = 2;
    return;
  }

  if (flag("--doctor")) {
    const found = discoverProject(project);
    let report;
    try {
      report = runSessionDoctor(readDescriptor(found.projectId, agentHome()), agentHome());
    } catch {
      report = runSessionDoctor(undefined, agentHome());
    }
    process.stdout.write(`${JSON.stringify(report)}\n`);
    process.exitCode = report.ok ? 0 : 1;
    return;
  }

  const sidecar = await startSidecar(project);
  const shutdown = async (): Promise<void> => {
    await sidecar.close();
  };
  process.on("SIGINT", () => {
    void shutdown().finally(() => process.exit(0));
  });
  process.on("SIGTERM", () => {
    void shutdown().finally(() => process.exit(0));
  });

  sidecar.log.info("sidecar listening (stdio MCP + plugin socket)");
  startMcpStdio({
    descriptor: () => sidecar.descriptor,
    doctor: () => runSessionDoctor(sidecar.descriptor),
    log: sidecar.log,
  });
}

void main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : "sidecar failed";
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
