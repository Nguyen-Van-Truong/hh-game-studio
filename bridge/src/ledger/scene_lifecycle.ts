/** Proven editor apply verbs. Scene lifecycle, node CRUD, and property codec. */

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

export function isProvenEditorApply(actionId: string): boolean {
  return isSceneLifecycleApply(actionId) || isNodeCrudApply(actionId) || isPropertyApply(actionId);
}

export function sceneNeedsDiskHash(actionId: string): boolean {
  return (SCENE_DURABLE_DISK as readonly string[]).includes(actionId);
}

export function nodeNeedsUidAfter(actionId: string): boolean {
  return (NODE_UID_AFTER as readonly string[]).includes(actionId);
}
