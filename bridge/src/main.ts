import { runDoctor, type DoctorOptions } from "./doctor/doctor.js";
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
    let desc;
    try {
      desc = readDescriptor(found.projectId, agentHome());
    } catch {
      desc = undefined;
    }
    const opts: DoctorOptions = {
      home: agentHome(),
      projectRoot: found.root,
    };
    if (desc) {
      opts.desc = desc;
    }
    const godotExe = argValue("--godot-exe");
    if (godotExe) {
      opts.godotExe = godotExe;
    }
    const forcedGodot = argValue("--force-godot-version");
    if (forcedGodot) {
      opts.forceGodotVersion = forcedGodot;
    }
    const forcedProtocol = argValue("--force-protocol");
    if (forcedProtocol) {
      opts.forceProtocol = forcedProtocol;
    }
    const forcedSchema = argValue("--force-schema");
    if (forcedSchema) {
      opts.forceSchema = forcedSchema;
    }
    const report = runDoctor(opts);
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
    doctor: () =>
      runDoctor({
        desc: sidecar.descriptor,
        home: agentHome(),
        projectRoot: sidecar.project.root,
      }),
    log: sidecar.log,
    ledger: sidecar.ledger,
    bound: {
      actorId: sidecar.actorId,
      projectId: sidecar.project.projectId,
      policy: sidecar.policy,
    },
    pause: sidecar.pause,
    policy: sidecar.policyServices,
    plugin: {
      connected: () => sidecar.transport.pluginConnected(),
      dispatch: (envelope, timeoutMs) => sidecar.transport.dispatchToPlugin(envelope, timeoutMs),
      readPostcondition: (commandId, timeoutMs) =>
        sidecar.transport.readPostcondition(commandId, timeoutMs),
      dropPlugin: () => sidecar.transport.dropPlugin(),
      sendControl: (msg) => sidecar.transport.sendControl(msg),
    },
  });
}

void main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : "sidecar failed";
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
