/** Scene lifecycle verbs proven in R3-WP1. Node CRUD stays refused. */

export const SCENE_LIFECYCLE_APPLY = [
  "scene.create",
  "scene.open",
  "scene.save",
  "scene.save_as",
  "scene.reload",
  "scene.activate",
  "scene.close",
] as const;

export const SCENE_DURABLE_DISK = ["scene.create", "scene.save", "scene.save_as"] as const;

export function isSceneLifecycleApply(actionId: string): boolean {
  return (SCENE_LIFECYCLE_APPLY as readonly string[]).includes(actionId);
}

export function sceneNeedsDiskHash(actionId: string): boolean {
  return (SCENE_DURABLE_DISK as readonly string[]).includes(actionId);
}
