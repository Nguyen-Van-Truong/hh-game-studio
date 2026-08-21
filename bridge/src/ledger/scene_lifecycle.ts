/** Proven editor apply verbs. Scene, node, property, resource, signal, asset-ref. */

export const SCENE_LIFECYCLE_APPLY = [
  "scene.create",
  "scene.open",
  "scene.save",
  "scene.save_as",
  "scene.reload",
  "scene.activate",
  "scene.close",
] as const;

export const NODE_CRUD_APPLY = [
  "node.add",
  "node.remove",
  "node.rename",
  "node.reparent",
  "node.reorder",
  "node.duplicate",
  "node.group",
  "node.make_local",
  "node.undo",
  "node.redo",
  "scene.instantiate",
] as const;

export const PROPERTY_APPLY = ["property.set", "property.batch", "property.reset"] as const;

export const RESOURCE_APPLY = [
  "resource.create",
  "resource.assign",
  "resource.duplicate",
  "resource.edit",
  "resource.save",
] as const;

export const SIGNAL_APPLY = ["signal.connect", "signal.disconnect"] as const;

export const ASSET_REF_APPLY = ["asset.move", "asset.rename", "asset.delete"] as const;

export const NODE_UID_AFTER = [
  "node.add",
  "node.rename",
  "node.reparent",
  "node.reorder",
  "node.duplicate",
  "node.group",
  "scene.instantiate",
] as const;

export const SCENE_DURABLE_DISK = ["scene.create", "scene.save", "scene.save_as"] as const;

export function isSceneLifecycleApply(actionId: string): boolean {
  return (SCENE_LIFECYCLE_APPLY as readonly string[]).includes(actionId);
}

export function isNodeCrudApply(actionId: string): boolean {
  return (NODE_CRUD_APPLY as readonly string[]).includes(actionId);
}

export function isPropertyApply(actionId: string): boolean {
  return (PROPERTY_APPLY as readonly string[]).includes(actionId);
}

export function isResourceApply(actionId: string): boolean {
  return (RESOURCE_APPLY as readonly string[]).includes(actionId);
}

export function isSignalApply(actionId: string): boolean {
  return (SIGNAL_APPLY as readonly string[]).includes(actionId);
}

export function isAssetRefApply(actionId: string): boolean {
  return (ASSET_REF_APPLY as readonly string[]).includes(actionId);
}

export function isProvenEditorApply(actionId: string): boolean {
  return (
    isSceneLifecycleApply(actionId) ||
    isNodeCrudApply(actionId) ||
    isPropertyApply(actionId) ||
    isResourceApply(actionId) ||
    isSignalApply(actionId) ||
    isAssetRefApply(actionId)
  );
}

export function sceneNeedsDiskHash(actionId: string): boolean {
  return (SCENE_DURABLE_DISK as readonly string[]).includes(actionId);
}

function isExternalResPath(path: string): boolean {
  return (path.endsWith(".tres") || path.endsWith(".res")) && !path.includes("::");
}

export function mutationNeedsDiskHash(actionId: string, params: Record<string, unknown>): boolean {
  if (sceneNeedsDiskHash(actionId)) {
    return true;
  }
  if (actionId === "resource.create" || actionId === "resource.save") {
    return typeof params.path === "string" && isExternalResPath(params.path);
  }
  // unique=true is dest file-copy + RAM edit; the field is durable only after resource.save.
  if (actionId === "resource.duplicate") {
    return typeof params.dest === "string" && isExternalResPath(params.dest);
  }
  return actionId === "asset.move" || actionId === "asset.rename";
}

export function durableResPath(
  actionId: string,
  params: Record<string, unknown>,
  after?: Record<string, unknown>,
): string {
  const source = typeof params.path === "string" ? params.path : "";
  if (
    after &&
    typeof after.path === "string" &&
    after.path.startsWith("res://") &&
    isExternalResPath(after.path)
  ) {
    if (actionId === "asset.move" || actionId === "asset.rename" || actionId === "resource.duplicate") {
      return after.path;
    }
    if (actionId === "resource.edit" && after.path !== source) {
      return after.path;
    }
  }
  if (actionId === "resource.duplicate" && typeof params.dest === "string") {
    return params.dest;
  }
  if (actionId === "resource.edit" && params.unique === true && typeof params.dest === "string") {
    return params.dest;
  }
  if (actionId === "asset.move" && typeof params.to === "string") {
    return params.to;
  }
  return source;
}

export function nodeNeedsUidAfter(actionId: string): boolean {
  return (NODE_UID_AFTER as readonly string[]).includes(actionId);
}
