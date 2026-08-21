/** Proven editor apply verbs. Scene lifecycle from R3-WP1; node CRUD from R3-WP2. */

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

export function isProvenEditorApply(actionId: string): boolean {
  return isSceneLifecycleApply(actionId) || isNodeCrudApply(actionId);
}

export function sceneNeedsDiskHash(actionId: string): boolean {
  return (SCENE_DURABLE_DISK as readonly string[]).includes(actionId);
}

export function nodeNeedsUidAfter(actionId: string): boolean {
  return (NODE_UID_AFTER as readonly string[]).includes(actionId);
}
