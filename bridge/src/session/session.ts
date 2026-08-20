import { randomBytes } from "node:crypto";

import { PROTOCOL } from "../registry/types.js";
import { startPluginTransport, type PluginTransport } from "../transport/websocket.js";
import { applyCurrentUserAcl } from "./acl.js";
import {
  acquireProjectLock,
  cleanupStaleSessions,
  removeSessionFiles,
  writeDescriptor,
  type SessionDescriptor,
} from "./descriptor.js";
import { createSessionLog, type SessionLog } from "./log.js";
import { agentHome, sessionDir } from "./paths.js";
import { discoverProject, type DiscoveredProject } from "./project.js";
import { ProcessSupervisor } from "./supervisor.js";
import { generateSessionToken } from "./token.js";

export interface SidecarHandle {
  project: DiscoveredProject;
  descriptor: SessionDescriptor;
  transport: PluginTransport;
  supervisor: ProcessSupervisor;
  log: SessionLog;
  close: () => Promise<void>;
}

export async function startSidecar(projectInput: string): Promise<SidecarHandle> {
  const project = discoverProject(projectInput);
  const home = agentHome();
  const supervisor = new ProcessSupervisor();
  cleanupStaleSessions(home);
  acquireProjectLock(project.projectId, supervisor, home);

  const token = generateSessionToken();
  const log = createSessionLog(() => [token]);
  const sessionId = randomBytes(16).toString("hex");

  let transport: PluginTransport | undefined;
  try {
    transport = await startPluginTransport({
      protocol: PROTOCOL,
      projectId: project.projectId,
      token,
      sessionId,
      log,
      heartbeatMs: 1_000,
    });
    applyCurrentUserAcl(sessionDir(project.projectId, home), supervisor);
    const descriptor: SessionDescriptor = {
      protocol: PROTOCOL,
      project_id: project.projectId,
      project_root: project.root,
      host: transport.host,
      port: transport.port,
      pid: process.pid,
      started_at: new Date().toISOString(),
      token,
    };
    writeDescriptor(descriptor, supervisor, home);
    const live = transport;
    return {
      project,
      descriptor,
      transport: live,
      supervisor,
      log,
      close: async () => {
        await live.close();
        await supervisor.shutdown();
        removeSessionFiles(project.projectId, home);
      },
    };
  } catch (err) {
    if (transport) {
      await transport.close();
    }
    removeSessionFiles(project.projectId, home);
    throw err;
  }
}
