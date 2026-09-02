import type { LandmarkId, SelectedObject } from "../lib/types";

export const CAMERA_PRESET_IDS = [
  "overview",
  "harbor",
  "lighthouse",
  "island",
] as const;

export type CameraPresetId = (typeof CAMERA_PRESET_IDS)[number];

export type Vec3 = readonly [number, number, number];

export type CameraPreset = {
  id: CameraPresetId;
  label: "Overview" | "Harbor" | "Lighthouse" | "Island";
  position: Vec3;
  target: Vec3;
};

/**
 * Art bar for later visual critic (Overview 1280x720):
 * - Sea: pastel turquoise/teal (#58b3b0 / #a3d8d0)
 * - Land: warm cream, muted green, soft red roofs
 * - Lighthouse (WP3): white + soft red stripes
 * - Overview must show sea + island + lighthouse + pier + boat in one frame
 * These camera numbers are the authored look-at for that silhouette.
 */
export const sceneConfig = {
  sky: {
    color: "#b7e0db",
  },
  fog: {
    color: "#9fd4cf",
    density: 0.0065,
  },
  lights: {
    ambientIntensity: 0.52,
    hemisphereSky: "#d7f0ea",
    hemisphereGround: "#c9b48a",
    hemisphereIntensity: 0.64,
    directionalIntensity: 1.55,
    directionalPosition: [16, 22, 8] as Vec3,
  },
  ocean: {
    y: 0,
    size: 96,
    color: "#4aa3a1",
    bandColor: "#82cbc5",
    rimColor: "#a3d8d0",
  },
  camera: {
    fov: 44,
    minDistance: 8,
    maxDistance: 42,
    playMinDistance: 4.2,
    playMaxDistance: 11,
    minPolar: 0.62,
    maxPolar: 1.42,
    playMinPolar: 0.4,
    playMaxPolar: 1.18,
    lookYawScale: 0.0025,
    lookPitchScale: 0.0019,
    // Mouse only. A/D uses a separate screen-right vector — do not
    // flip strafe when changing this. Play-tested: +1 inverted the camera.
    lookYawSign: -1,
    damping: 0.14,
    defaultPreset: "overview" as CameraPresetId,
  },
  presets: {
    overview: {
      id: "overview",
      label: "Overview",
      position: [13.4, 10.6, 19.5],
      target: [-0.9, 1.55, 1.2],
    },
    harbor: {
      id: "harbor",
      label: "Harbor",
      position: [-0.9, 5.0, 15.8],
      target: [-4.5, 0.9, 5.35],
    },
    lighthouse: {
      id: "lighthouse",
      label: "Lighthouse",
      position: [12.6, 7.4, 10.5],
      target: [5.4, 2.7, -2.0],
    },
    island: {
      id: "island",
      label: "Island",
      position: [4.8, 8.6, 15.8],
      target: [0.4, 1.8, -0.4],
    },
  } satisfies Record<CameraPresetId, CameraPreset>,
} as const;

export function getCameraPreset(id: CameraPresetId): CameraPreset {
  return sceneConfig.presets[id];
}

/** Fixed seed so reload does not reshuffle foliage/rocks. */
export const SCENE_SEED = 20260831;

export const palette = {
  sea: "#58b3b0",
  landCream: "#e6d5b8",
  landSand: "#d9c092",
  landGreen: "#879f75",
  landMoss: "#b6c993",
  roof: "#bd5a4c",
  wall: "#f4ede1",
  lighthouseWhite: "#f4f0ea",
  lighthouseStripe: "#d46a6a",
  wood: "#8b5a3c",
  woodLight: "#a56d48",
  boat: "#c47a48",
  foliage: "#6f8f4e",
  rock: "#b7a48a",
  dummy: "#d7c4a4",
} as const;

/** Soft coastal clothes — not Pelago, not GTA tactical. */
export const personPalette = {
  skin: "#e8c09a",
  skinShadow: "#d4a882",
  hair: "#1f1916",
  shirt: "#2a7d78",
  collar: "#1a5552",
  yoke: "#1a5552",
  pants: "#2a3331",
  sash: "#2a7d78",
  shoe: "#5c4030",
} as const;

/**
 * Chơi is third-person look-aim, not a crane: camera stays behind the
 * person and mouse Y pitches the look (down = ground, up = sky).
 */
export const playFollow = {
  standLookY: 1.12,
  boardLookY: 0.82,
  defaultPitch: -0.14,
  minPitch: -0.7,
  maxPitch: 0.48,
  standDistance: 6.2,
  boardDistance: 6.6,
  standSide: 0.4,
  boardSide: 0.46,
  sitLift: 0.14,
  camLift: 1.05,
  aimAhead: 2.1,
  minHeight: 0.55,
} as const;

export const playSpawn = {
  boardX: -9.4,
  boardZ: 9.1,
  boardYaw: -0.7,
} as const;

export type PlayLookOrigin = {
  x: number;
  y: number;
  z: number;
};

/** Behind-the-person camera from look yaw/pitch. Pitch+ looks up. */
export function playLookCamera(
  boarded: boolean,
  origin: PlayLookOrigin,
  yaw: number,
  pitch?: number,
  distance?: number,
): { position: [number, number, number]; target: [number, number, number] } {
  const aimPitch = pitch ?? playFollow.defaultPitch;
  const range =
    distance ?? (boarded ? playFollow.boardDistance : playFollow.standDistance);
  const lookY = boarded ? playFollow.boardLookY : playFollow.standLookY;
  const side = boarded ? playFollow.boardSide : playFollow.standSide;
  const cosP = Math.cos(aimPitch);
  const sinP = Math.sin(aimPitch);
  const fx = Math.sin(yaw) * cosP;
  const fy = sinP;
  const fz = Math.cos(yaw) * cosP;
  const rx = Math.cos(yaw);
  const rz = -Math.sin(yaw);
  const chestY = origin.y + lookY;
  const ahead = playFollow.aimAhead;
  const target: [number, number, number] = [
    origin.x + fx * ahead,
    chestY + fy * ahead,
    origin.z + fz * ahead,
  ];
  const position: [number, number, number] = [
    origin.x - fx * range + rx * side,
    Math.max(origin.y + playFollow.minHeight, chestY + playFollow.camLift - fy * range),
    origin.z - fz * range + rz * side,
  ];
  return { position, target };
}

export const layout = {
  lighthouse: [5.55, 1.48, -2.2] as Vec3,
  harbor: [-4.35, 0.24, 5.55] as Vec3,
  pierSize: [6.4, 0.18, 1.45] as Vec3,
  boat: [-7.15, 0.2, 7.15] as Vec3,
  /** Decorative second thúng in the bay — not boardable, no traffic. */
  idleBoat: [6.8, 0.18, 8.65] as Vec3,
  houses: [
    [-1.55, 2.58, -0.55],
    [0.85, 2.58, 0.35],
    [2.15, 2.58, -1.35],
  ] as const satisfies readonly Vec3[],
  dummy: [-3.55, 0.42, 5.45] as Vec3,
  trees: [
    [-3.6, 2.05, -2.1],
    [-2.2, 2.05, 1.55],
    [3.55, 2.05, 1.35],
    [3.9, 2.05, -2.35],
    [-4.35, 1.55, -3.1],
    [4.4, 1.55, 2.05],
    [-0.35, 2.85, -2.45],
    [2.85, 2.85, 0.15],
  ] as const satisfies readonly Vec3[],
  rocks: [
    [-5.4, 1.42, 1.15],
    [5.1, 1.42, 1.85],
    [-2.85, 1.42, -3.55],
    [1.15, 1.42, 3.05],
    [4.7, 1.42, -3.2],
    [-4.9, 1.42, -1.4],
  ] as const satisfies readonly Vec3[],
} as const;

export const landmarks = [
  {
    id: "lighthouse",
    title: "Hải đăng sọc",
    description:
      "Ngọn tháp trắng sọc đỏ đứng trên mỏm cao, soi đường cho vịnh Hòn Gió.",
  },
  {
    id: "harbor",
    title: "Bến gỗ",
    description:
      "Bến gỗ nhỏ nối bậc đảo với mặt nước — điểm xuất phát để đi bộ và lên thúng.",
  },
  {
    id: "boat",
    title: "Thúng neo",
    description:
      "Chiếc thúng neo cạnh bến. Đến gần rồi nhấn E để xuống nước và chèo thử.",
  },
  {
    id: "houses",
    title: "Nhà mái ngói",
    description:
      "Ba căn nhà mái ngói nằm trên bậc cỏ, tạo thành góc ở yên tĩnh nhìn ra vịnh.",
  },
] as const;

export function getLandmark(id: LandmarkId): SelectedObject {
  const found = landmarks.find((item) => item.id === id);
  if (!found) {
    throw new Error(`Unknown landmark: ${id}`);
  }
  return found;
}

function unit(seed: number, index: number): number {
  const value = Math.sin(seed * 12.9898 + index * 78.233) * 43758.5453;
  return value - Math.floor(value);
}

export function seededRange(
  seed: number,
  index: number,
  min: number,
  max: number,
): number {
  return min + unit(seed, index) * (max - min);
}
