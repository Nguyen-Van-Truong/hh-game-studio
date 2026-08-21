import { randomBytes } from "node:crypto";

import { openLedger, type CommandLedger } from "../ledger/store.js";
import { DEFAULT_LEDGER_POLICY, normalizePolicy } from "../ledger/execute.js";
import { durableActorId } from "../ledger/paths.js";
import { ApprovalBinder, projectRevision } from "../policy/approve.js";
import { LeaseTable } from "../policy/leases.js";
import { PauseGate } from "../policy/pause.js";
import type { PolicyServices } from "../policy/engine.js";
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
  ledger: CommandLedger;
  actorId: string;
  policy: string;
  pause: PauseGate;
  policyServices: PolicyServices;
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

  const pause = new PauseGate();
  let transport: PluginTransport | undefined;
  let ledger: CommandLedger | undefined;
  try {
    transport = await startPluginTransport({
      protocol: PROTOCOL,
      projectId: project.projectId,
      token,
      sessionId,
      log,
      heartbeatMs: 1_000,
      onPluginPause: (paused) => (paused ? pause.pause() : pause.resume()),
    });
    applyCurrentUserAcl(sessionDir(project.projectId, home), supervisor);
    ledger = openLedger({ projectId: project.projectId, supervisor, home });
    const liveLedger = ledger;
    const actorId = (process.env.HH_LEDGER_ACTOR ?? "").trim() || durableActorId(project.projectId);
    const policy = normalizePolicy(process.env.HH_LEDGER_POLICY ?? DEFAULT_LEDGER_POLICY);
    const policyServices: PolicyServices = {
      projectRoot: project.root,
      writerId: actorId,
      pause,
      leases: new LeaseTable(project.root),
      approvals: new ApprovalBinder(project.root),
      revision: projectRevision(project.root),
    };
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
      ledger: liveLedger,
      actorId,
      policy,
      pause,
      policyServices,
      close: async () => {
        await live.close();
        liveLedger.close();
        await supervisor.shutdown();
        removeSessionFiles(project.projectId, home);
      },
    };
  } catch (err) {
    if (ledger) {
      ledger.close();
    }
    if (transport) {
      await transport.close();
    }
    removeSessionFiles(project.projectId, home);
    throw err;
  }
}
