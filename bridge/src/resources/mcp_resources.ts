import { PINNED_VERSION_ID } from "../doctor/pin.js";
import {
  isAnimationApply,
  isAssetRefApply,
  isCameraApply,
  isCanvasApply,
  isNodeCrudApply,
  isTilemapApply,
  isProjectSettingsApply,
  isPropertyApply,
  isResourceApply,
  isSceneLifecycleApply,
  isScriptApply,
  isSignalApply,
} from "../ledger/scene_lifecycle.js";
import { allActionDefs } from "../registry/registry.js";
import { PROTOCOL, REGISTRY_VERSION } from "../registry/types.js";
import { publicDescriptorView, type SessionDescriptor } from "../session/descriptor.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";

export const RESOURCE_URIS = [
  "project://summary",
  "editor://state",
  "capability://matrix",
] as const;

export type ResourceUri = (typeof RESOURCE_URIS)[number];

export interface McpResource {
  uri: ResourceUri;
  name: string;
  description: string;
  mimeType: "application/json";
}

export function listResources(): McpResource[] {
  return [
    {
      uri: "project://summary",
      name: "Project summary",
      description: "Name, main scene, features. Never includes the session token.",
      mimeType: "application/json",
    },
    {
      uri: "editor://state",
      name: "Editor state",
      description: "Open scene, selection, play flag from a connected plugin.",
      mimeType: "application/json",
    },
    {
      uri: "capability://matrix",
      name: "Capability matrix",
      description: "Pinned Godot + action wiring. Scene lifecycle and node CRUD may apply.",
      mimeType: "application/json",
    },
  ];
}

function stripSecrets(value: unknown, secret?: string): unknown {
  if (typeof value === "string") {
    if (secret && value.includes(secret)) {
      return value.split(secret).join("[redacted]");
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => stripSecrets(item, secret));
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (key === "token" || key === "secret" || key === "authorization") {
        out[key] = "[redacted]";
        continue;
      }
      out[key] = stripSecrets(item, secret);
    }
    return out;
  }
  return value;
}

export function capabilityMatrix(): Record<string, unknown> {
  return {
    protocol: PROTOCOL,
    registry_version: REGISTRY_VERSION,
    godot_pin: PINNED_VERSION_ID,
    mutate_dispatched:
      "scene-lifecycle+node-crud+property+resource+signal+script+project-settings+tilemap+animation",
    node_crud_dispatched: true,
    property_dispatched: true,
    resource_dispatched: true,
    script_dispatched: true,
    tilemap_dispatched: true,
    animation_dispatched: true,
    note: "Scene/node/property/resource/signal/script/project.settings/tilemap/animation ACK after EditorUndoRedo or ProjectSettings.save + ConfigFile disk parse. play.input inject stays E_UNVERIFIED.",
    actions: allActionDefs().map((def) => ({
      id: def.id,
      method: def.method,
      side_effect: def.side_effect,
      policy: def.required_policy,
      postcondition: def.postcondition,
      adapter:
        def.id === "editor.select"
          ? "view-state-mutate-not-wp6"
          : isProjectSettingsApply(def.id)
            ? "project-settings"
          : isPropertyApply(def.id) || isCanvasApply(def.id)
            ? "property-codec"
            : isCameraApply(def.id)
              ? "camera-current"
            : isTilemapApply(def.id)
              ? "tilemap"
            : isAnimationApply(def.id)
              ? "animation"
            : isResourceApply(def.id) || isAssetRefApply(def.id)
              ? "resource-ops"
              : isSignalApply(def.id)
                ? "signal-ops"
                : isScriptApply(def.id)
                  ? "script-ops"
                  : isNodeCrudApply(def.id)
                  ? "node-crud"
                  : isSceneLifecycleApply(def.id)
                    ? "scene-lifecycle"
                    : def.side_effect === "read" || def.side_effect === "view"
                      ? "read-or-view"
                      : "not-dispatched",
    })),
  };
}

export function projectSummary(args: {
  descriptor: SessionDescriptor;
  inspect?: Record<string, unknown>;
}): Record<string, unknown> {
  const session = publicDescriptorView(args.descriptor);
  return {
    session: {
      protocol: session.protocol,
      project_id: session.project_id,
      host: session.host,
      port: session.port,
      pid: session.pid,
    },
    project_root_name: args.descriptor.project_root.split(/[/\\]/).filter(Boolean).at(-1) ?? "",
    inspect: args.inspect ?? { connected: false },
  };
}

export function editorStateFromResult(result: PluginCommandResult | undefined): Record<string, unknown> {
  if (!result) {
    return { connected: false, reason: "plugin not connected" };
  }
  if (!result.ok) {
    return {
      connected: true,
      ok: false,
      error: result.error ?? { code: "E_UNVERIFIED", message: "editor.state failed", path: "" },
    };
  }
  return { connected: true, ok: true, ...(result.after ?? {}) };
}

export function resourceBody(
  uri: string,
  body: unknown,
  secret?: string,
): { uri: string; mimeType: "application/json"; text: string } {
  const cleaned = stripSecrets(body, secret);
  return {
    uri,
    mimeType: "application/json",
    text: JSON.stringify(cleaned),
  };
}

export function isResourceUri(uri: string): uri is ResourceUri {
  return (RESOURCE_URIS as readonly string[]).includes(uri);
}
