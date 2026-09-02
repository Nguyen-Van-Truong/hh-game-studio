import { layout } from "../scene/sceneConfig";

export type WalkPad = {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
  y: number;
};

export type CircleBlocker = {
  x: number;
  z: number;
  radius: number;
};

export type Vec2 = { x: number; z: number };

export const PLAYER_RADIUS = 0.22;

/** Feet height on the pier deck. */
export const PIER_SURFACE_Y = 0.33;

/**
 * Walkable pads. The visual terrace box overlaps the pier in XZ;
 * the terrace pad is notched so the pier keeps its own height.
 */
export const WALK_PADS: readonly WalkPad[] = [
  // Pier
  { x0: -7.55, x1: -1.15, z0: 4.82, z1: 6.28, y: PIER_SURFACE_Y },
  // Stairs from pier up to the lower terrace (do not overlap the pier deck)
  { x0: -4.45, x1: -2.45, z0: 4.50, z1: 4.80, y: 0.56 },
  { x0: -4.45, x1: -2.45, z0: 4.22, z1: 4.52, y: 0.84 },
  { x0: -4.45, x1: -2.45, z0: 3.94, z1: 4.24, y: 1.12 },
  { x0: -4.45, x1: -2.45, z0: 3.66, z1: 4.00, y: 1.36 },
  // Lower terrace (notched at +Z so pier/stairs own the join)
  { x0: -6.55, x1: 6.75, z0: -4.6, z1: 4.12, y: 1.44 },
  // Mid terrace
  { x0: -4.2, x1: 4.9, z0: -3.45, z1: 2.75, y: 2.445 },
  // Upper terrace
  { x0: -1.15, x1: 4.05, z0: -2.85, z1: 0.55, y: 3.17 },
  // Existing sand landing
  { x0: -5.5, x1: -2.1, z0: 1.3, z1: 3.5, y: 1.32 },
  // Thin beach ring
  { x0: -6.7, x1: 6.9, z0: 4.12, z1: 5.55, y: 0.28 },
  { x0: -6.7, x1: 6.9, z0: -6.15, z1: -4.55, y: 0.28 },
  { x0: 6.55, x1: 8.25, z0: -4.85, z1: 5.15, y: 0.28 },
  { x0: -8.15, x1: -6.45, z0: -4.85, z1: 5.15, y: 0.28 },
];

export const STEP_MESHES = [
  { position: [-3.45, 0.42, 4.65] as const, size: [1.95, 0.14, 0.36] as const },
  { position: [-3.45, 0.7, 4.37] as const, size: [1.95, 0.14, 0.36] as const },
  { position: [-3.45, 0.98, 4.09] as const, size: [1.95, 0.14, 0.36] as const },
  { position: [-3.45, 1.26, 3.82] as const, size: [1.95, 0.14, 0.36] as const },
] as const;

export const BEACH_MESHES = [
  { position: [0.1, 0.12, 4.42] as const, size: [13.4, 0.24, 0.72] as const },
  { position: [0.1, 0.12, -5.45] as const, size: [13.4, 0.24, 1.45] as const },
  { position: [7.45, 0.12, -0.2] as const, size: [1.55, 0.24, 8.6] as const },
  { position: [-7.35, 0.12, -0.2] as const, size: [1.55, 0.24, 8.6] as const },
] as const;

function houseBlockers(): CircleBlocker[] {
  return layout.houses.map((position) => ({
    x: position[0],
    z: position[2],
    radius: 0.64,
  }));
}

function treeBlockers(): CircleBlocker[] {
  return layout.trees.map((position) => ({
    x: position[0],
    z: position[2],
    radius: 0.3,
  }));
}

function rockBlockers(): CircleBlocker[] {
  return layout.rocks.map((position) => ({
    x: position[0],
    z: position[2],
    radius: 0.28,
  }));
}

export const BLOCKERS: readonly CircleBlocker[] = [
  {
    x: layout.lighthouse[0],
    z: layout.lighthouse[2],
    radius: 0.74,
  },
  ...houseBlockers(),
  ...treeBlockers(),
  ...rockBlockers(),
];

export const BOAT_BAY = {
  centerX: 0,
  centerZ: 1.2,
  radius: 20,
} as const;

/** Solid island mass the toy boat cannot cross. */
export const BOAT_LAND = {
  x0: -6.9,
  x1: 7.1,
  z0: -5.0,
  z1: 4.35,
} as const;

export const BOARD_DISTANCE = 1.85;

function containsPad(pad: WalkPad, x: number, z: number): boolean {
  return x >= pad.x0 && x <= pad.x1 && z >= pad.z0 && z <= pad.z1;
}

export function surfaceAt(x: number, z: number): number | null {
  let best: number | null = null;
  for (const pad of WALK_PADS) {
    if (!containsPad(pad, x, z)) {
      continue;
    }
    if (best === null || pad.y > best) {
      best = pad.y;
    }
  }
  return best;
}

export function isBlocked(x: number, z: number, radius: number): boolean {
  for (const blocker of BLOCKERS) {
    const dx = x - blocker.x;
    const dz = z - blocker.z;
    const limit = blocker.radius + radius;
    if (dx * dx + dz * dz < limit * limit) {
      return true;
    }
  }
  return false;
}

export function canStand(x: number, z: number, radius: number): boolean {
  return surfaceAt(x, z) !== null && !isBlocked(x, z, radius);
}

export function resolveWalk(
  fromX: number,
  fromZ: number,
  dx: number,
  dz: number,
  radius: number,
): { x: number; z: number; y: number } {
  const currentY = surfaceAt(fromX, fromZ) ?? PIER_SURFACE_Y;
  const tryPoint = (x: number, z: number) => {
    const y = surfaceAt(x, z);
    if (y === null || isBlocked(x, z, radius)) {
      return null;
    }
    return { x, z, y };
  };

  const next = tryPoint(fromX + dx, fromZ + dz);
  if (next) {
    return next;
  }
  const slideX = tryPoint(fromX + dx, fromZ);
  if (slideX) {
    return slideX;
  }
  const slideZ = tryPoint(fromX, fromZ + dz);
  if (slideZ) {
    return slideZ;
  }
  return { x: fromX, z: fromZ, y: currentY };
}

export function nearestWalkable(
  x: number,
  z: number,
  radius: number,
): { x: number; z: number; y: number } {
  if (canStand(x, z, radius)) {
    return { x, z, y: surfaceAt(x, z) ?? PIER_SURFACE_Y };
  }

  for (let ring = 1; ring <= 22; ring += 1) {
    const dist = ring * 0.45;
    const steps = 10 + ring * 2;
    for (let i = 0; i < steps; i += 1) {
      const angle = (i / steps) * Math.PI * 2;
      const nx = x + Math.cos(angle) * dist;
      const nz = z + Math.sin(angle) * dist;
      const y = surfaceAt(nx, nz);
      if (y !== null && !isBlocked(nx, nz, radius)) {
        return { x: nx, z: nz, y };
      }
    }
  }

  const spawnX = layout.dummy[0];
  const spawnZ = layout.dummy[2];
  return {
    x: spawnX,
    z: spawnZ,
    y: surfaceAt(spawnX, spawnZ) ?? PIER_SURFACE_Y,
  };
}

export function boatAllowed(x: number, z: number): boolean {
  const dx = x - BOAT_BAY.centerX;
  const dz = z - BOAT_BAY.centerZ;
  if (dx * dx + dz * dz > BOAT_BAY.radius * BOAT_BAY.radius) {
    return false;
  }
  if (
    x >= BOAT_LAND.x0 &&
    x <= BOAT_LAND.x1 &&
    z >= BOAT_LAND.z0 &&
    z <= BOAT_LAND.z1
  ) {
    return false;
  }
  return true;
}

export function clampBoat(fromX: number, fromZ: number, x: number, z: number): Vec2 {
  if (boatAllowed(x, z)) {
    return { x, z };
  }
  if (boatAllowed(x, fromZ)) {
    return { x, z: fromZ };
  }
  if (boatAllowed(fromX, z)) {
    return { x: fromX, z };
  }
  return { x: fromX, z: fromZ };
}
