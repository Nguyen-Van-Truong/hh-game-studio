import {
  CAMERA_PRESET_IDS,
  type CameraPresetId,
} from "./sceneConfig";

export const VIEW_MODE_IDS = ["play", ...CAMERA_PRESET_IDS] as const;

export type ViewMode = (typeof VIEW_MODE_IDS)[number];

export function isCameraPreset(mode: ViewMode): mode is CameraPresetId {
  return mode !== "play";
}

export function viewModeFromQuery(value: string | null): ViewMode {
  if (value === "play") {
    return "play";
  }
  if (
    value === "overview" ||
    value === "harbor" ||
    value === "lighthouse" ||
    value === "island"
  ) {
    return value;
  }
  // The authored diorama is the safest first impression. Walking remains an
  // explicit mode (`?mode=play` or the Chơi button), so a fresh visitor first
  // sees the island instead of a close camera aimed at the pier edge.
  return "overview";
}
