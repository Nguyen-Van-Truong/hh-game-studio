export type AvatarPose = "idle" | "walk";

export type AvatarState = {
  lon: number;
  lat: number;
  heading: number;
  pose: AvatarPose;
  /** Meters above the authored slab. Jump only; walls stay 2D. */
  alt: number;
  vy: number;
  airborne: boolean;
  /** Hold Shift / pad. Faster walk only; same collision. */
  sprint: boolean;
  /** In-place A/D or pad turn. Pose stays idle for presence. */
  turning: boolean;
};

export type BBox = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type BuildingPoly = {
  id: string;
  ring: [number, number][];
  height_m?: number;
  name?: string;
  aabb?: LonLatBox;
};

/** Match hh-3d/demo play.ts (2.55 / 4.35). 1.6 felt like a crawl. */
export const WALK_SPEED_MPS = 2.55;
/** Hold-to-sprint. Same demo run. Release returns walk. */
export const SPRINT_SPEED_MPS = 4.35;
/** Residual in-place turn (mouse is the look). Same sign as LOOK_YAW_SIGN. */
export const TURN_DEG_PER_SEC = 110;
/** Same as demo lookYawSign. Do not flip strafe when this changes. */
export const TURN_YAW_SIGN = -1;
/** At-the-kiosk radius. 10 m still covered Harbor asphalt (laneM ≲ 3). */
export const NEARBY_SHOP_M = 4;
/** Driving-lane band. Street E stays on the sidewalk kiosk, not the asphalt. */
export const STREET_SHOP_ASPHALT_LANE_M = 3;
export const AOI_INSET_M = 2;
/** 2D keep-in at the authored 400 m frame. Fixture edge, not a city. */
export const BLOCK_BOUND_KIND = "fixture-edge" as const;
export const AOI_BOUND_PAD_M = 1.25;
/** Body radius so the visual walker stops at the authored footprint wall. */
export const AVATAR_RADIUS_M = 0.55;
/** Circle vs extruded ring. AABB is only a broad-phase / proof box. */
export const COLLISION_KIND = "footprint-radius" as const;
/** Feet stay on the authored slab. Play never writes a negative Y. */
export const GROUND_Y = 0;
/** Same hop as hh-3d/demo. Vertical only — does not clear a building. */
export const JUMP_SPEED = 6.1;
export const GRAVITY = 17;
export const M_PER_DEG_LAT = 111320;

export type LonLatBox = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export const AVATAR_SPAWN: AvatarState = {
  lon: 106.69804,
  lat: 10.77162,
  heading: 0,
  pose: "idle",
  alt: GROUND_Y,
  vy: 0,
  airborne: false,
  sprint: false,
  turning: false,
};

/** Hide leftover kiosk mesh/collide in this radius. Catalog persist stays. */
export const SPAWN_KEEP_OUT_M = 14;

export function inSpawnKeepOut(lon: number, lat: number): boolean {
  return distanceM({ lon, lat }, AVATAR_SPAWN) <= SPAWN_KEEP_OUT_M;
}

/** Leftover this-PC shops in the spawn cone stay in the catalog but do not own street E. */
export function isStreetPlayShop(shop: { lon: number; lat: number }): boolean {
  return !inSpawnKeepOut(shop.lon, shop.lat);
}

export function streetPlayShops<T extends { lon: number; lat: number }>(shops: T[]): T[] {
  return shops.filter((shop) => isStreetPlayShop(shop));
}

/** Guest Menu/Tab list: persist keep-out rows are not "on the street". */
export const MENU_LEFTOVER_LABEL = "không trên phố / leftover máy này";

export function isMenuLeftoverShop(shop: { lon: number; lat: number }): boolean {
  return !isStreetPlayShop(shop);
}

/** Street shops first; spawn-keep-out leftovers last. Catalog persist stays. */
export function sortMenuShops<T extends { lon: number; lat: number }>(shops: T[]): T[] {
  const street: T[] = [];
  const leftover: T[] = [];
  for (const shop of shops) {
    if (isStreetPlayShop(shop)) {
      street.push(shop);
    } else {
      leftover.push(shop);
    }
  }
  return [...street, ...leftover];
}

export function moveSpeedMps(sprint: boolean): number {
  return sprint ? SPRINT_SPEED_MPS : WALK_SPEED_MPS;
}

export function onGround(
  state: Omit<AvatarState, "alt" | "vy" | "airborne" | "sprint" | "turning"> & Partial<AvatarState>,
): AvatarState {
  return {
    lon: state.lon,
    lat: state.lat,
    heading: state.heading,
    pose: state.pose,
    alt: GROUND_Y,
    vy: 0,
    airborne: false,
    sprint: state.sprint ?? false,
    turning: state.turning ?? false,
  };
}

export function applyJump(state: AvatarState): AvatarState {
  if (state.airborne) {
    return state;
  }
  return { ...state, vy: JUMP_SPEED, airborne: true };
}

export function integrateVertical(state: AvatarState, dtSec: number): AvatarState {
  const dt = Math.min(dtSec, 0.05);
  if (!state.airborne && state.alt <= GROUND_Y && state.vy <= 0) {
    if (state.alt === GROUND_Y && state.vy === 0) {
      return state;
    }
    return { ...state, alt: GROUND_Y, vy: 0, airborne: false };
  }
  const vy = state.vy - GRAVITY * dt;
  const alt = state.alt + vy * dt;
  if (alt <= GROUND_Y && vy <= 0) {
    return { ...state, alt: GROUND_Y, vy: 0, airborne: false };
  }
  return { ...state, alt, vy, airborne: true };
}

export function metersPerDegLon(lat: number): number {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

export function offsetLngLat(
  lon: number,
  lat: number,
  eastM: number,
  northM: number,
): { lon: number; lat: number } {
  return {
    lon: lon + eastM / metersPerDegLon(lat),
    lat: lat + northM / M_PER_DEG_LAT,
  };
}

export function distanceM(
  a: { lon: number; lat: number },
  b: { lon: number; lat: number },
): number {
  const midLat = (a.lat + b.lat) / 2;
  const east = (b.lon - a.lon) * metersPerDegLon(midLat);
  const north = (b.lat - a.lat) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

export function headingFromDelta(eastM: number, northM: number): number {
  if (eastM === 0 && northM === 0) {
    return 0;
  }
  return ((Math.atan2(eastM, northM) * 180) / Math.PI + 360) % 360;
}

export function pointInRing(lon: number, lat: number, ring: [number, number][]): boolean {
  let inside = false;
  const n = ring.length;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const pi = ring[i];
    const pj = ring[j];
    if (!pi || !pj) {
      continue;
    }
    const xi = pi[0];
    const yi = pi[1];
    const xj = pj[0];
    const yj = pj[1];
    if (yj === yi) {
      continue;
    }
    const intersect = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) {
      inside = !inside;
    }
  }
  return inside;
}

export function aoiWalkBox(bbox: BBox, lat: number): BBox {
  const dLon = AOI_INSET_M / metersPerDegLon(lat);
  const dLat = AOI_INSET_M / M_PER_DEG_LAT;
  return {
    west: bbox.west + dLon,
    east: bbox.east - dLon,
    south: bbox.south + dLat,
    north: bbox.north - dLat,
  };
}

export function isInsideAoi(lon: number, lat: number, bbox: BBox): boolean {
  const box = aoiWalkBox(bbox, lat);
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

/** Snap back onto the authored frame if a step leaked past the GeoJSON extent. */
export function clampInsideAoi(lon: number, lat: number, bbox: BBox): { lon: number; lat: number } {
  const box = aoiWalkBox(bbox, lat);
  return {
    lon: Math.min(box.east, Math.max(box.west, lon)),
    lat: Math.min(box.north, Math.max(box.south, lat)),
  };
}

/** True when the body is on the inner face of the fixture edge. */
export function isAtAoiBound(lon: number, lat: number, bbox: BBox, padM = AOI_BOUND_PAD_M): boolean {
  const box = aoiWalkBox(bbox, lat);
  const mLon = metersPerDegLon(lat);
  const dW = (lon - box.west) * mLon;
  const dE = (box.east - lon) * mLon;
  const dS = (lat - box.south) * M_PER_DEG_LAT;
  const dN = (box.north - lat) * M_PER_DEG_LAT;
  return Math.min(dW, dE, dS, dN) <= padM;
}

/** Zero the out-of-frame axis so a diagonal step slides along the fixture edge. */
export function projectBoundSlide(
  east: number,
  north: number,
  lon: number,
  lat: number,
  bbox: BBox,
): { east: number; north: number } {
  const next = offsetLngLat(lon, lat, east, north);
  if (isInsideAoi(next.lon, next.lat, bbox)) {
    return { east, north };
  }
  let e = east;
  let n = north;
  if (!isInsideAoi(next.lon, lat, bbox)) {
    e = 0;
  }
  if (!isInsideAoi(lon, next.lat, bbox)) {
    n = 0;
  }
  return { east: e, north: n };
}

export function ringAabb(ring: [number, number][]): LonLatBox | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  let n = 0;
  for (const pt of ring) {
    if (!pt) {
      continue;
    }
    west = Math.min(west, pt[0]);
    east = Math.max(east, pt[0]);
    south = Math.min(south, pt[1]);
    north = Math.max(north, pt[1]);
    n += 1;
  }
  if (n < 3 || !Number.isFinite(west)) {
    return null;
  }
  return { west, south, east, north };
}

export function buildingAabb(building: BuildingPoly): LonLatBox | null {
  return building.aabb ?? ringAabb(building.ring);
}

export function pointInAabb(lon: number, lat: number, box: LonLatBox): boolean {
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

/** Circle vs AABB. Broad-phase only — chamfered rings sit inside this box. */
export function circleHitsAabb(
  lon: number,
  lat: number,
  radiusM: number,
  box: LonLatBox,
): boolean {
  const closestLon = Math.min(box.east, Math.max(box.west, lon));
  const closestLat = Math.min(box.north, Math.max(box.south, lat));
  return distanceM({ lon, lat }, { lon: closestLon, lat: closestLat }) < radiusM;
}

export type RingContact = {
  distM: number;
  closestLon: number;
  closestLat: number;
  east: number;
  north: number;
  inside: boolean;
};

/** Nearest ring edge in meters, plus an outward unit normal. */
export function closestRingContact(
  lon: number,
  lat: number,
  ring: [number, number][],
): RingContact | null {
  const inside = pointInRing(lon, lat, ring);
  const mPerLon = metersPerDegLon(lat);
  let bestDist = Infinity;
  let bestE = 0;
  let bestN = 0;
  let bestVe = 0;
  let bestVn = 0;
  let found = false;
  const count = ring.length;
  for (let i = 0; i < count; i += 1) {
    const a = ring[i];
    const b = ring[(i + 1) % count];
    if (!a || !b) {
      continue;
    }
    const ae = (a[0] - lon) * mPerLon;
    const an = (a[1] - lat) * M_PER_DEG_LAT;
    const be = (b[0] - lon) * mPerLon;
    const bn = (b[1] - lat) * M_PER_DEG_LAT;
    const ve = be - ae;
    const vn = bn - an;
    const len2 = ve * ve + vn * vn;
    if (len2 < 1e-12) {
      continue;
    }
    const t = Math.max(0, Math.min(1, (-ae * ve - an * vn) / len2));
    const ce = ae + t * ve;
    const cn = an + t * vn;
    const dist = Math.hypot(ce, cn);
    if (dist < bestDist) {
      bestDist = dist;
      bestE = ce;
      bestN = cn;
      bestVe = ve;
      bestVn = vn;
      found = true;
    }
  }
  if (!found) {
    return null;
  }
  let nx: number;
  let ny: number;
  if (bestDist > 1e-7) {
    if (inside) {
      nx = bestE / bestDist;
      ny = bestN / bestDist;
    } else {
      nx = -bestE / bestDist;
      ny = -bestN / bestDist;
    }
  } else {
    const edgeLen = Math.hypot(bestVe, bestVn);
    const rightE = bestVn / edgeLen;
    const rightN = -bestVe / edgeLen;
    const test = offsetLngLat(lon, lat, rightE * 0.05, rightN * 0.05);
    if (pointInRing(test.lon, test.lat, ring)) {
      nx = -rightE;
      ny = -rightN;
    } else {
      nx = rightE;
      ny = rightN;
    }
  }
  return {
    distM: bestDist,
    closestLon: lon + bestE / mPerLon,
    closestLat: lat + bestN / M_PER_DEG_LAT,
    east: nx,
    north: ny,
    inside,
  };
}

export function circleHitsRing(
  lon: number,
  lat: number,
  radiusM: number,
  ring: [number, number][],
): boolean {
  const hit = closestRingContact(lon, lat, ring);
  if (!hit) {
    return false;
  }
  return hit.inside || hit.distM < radiusM;
}

export function circleHitsBuilding(
  lon: number,
  lat: number,
  radiusM: number,
  building: BuildingPoly,
): boolean {
  const box = buildingAabb(building);
  if (box && !circleHitsAabb(lon, lat, radiusM, box)) {
    return false;
  }
  if (building.ring.length >= 4) {
    return circleHitsRing(lon, lat, radiusM, building.ring);
  }
  return box ? circleHitsAabb(lon, lat, radiusM, box) : false;
}

export function ringOutwardNormal(
  lon: number,
  lat: number,
  ring: [number, number][],
): { east: number; north: number } {
  const hit = closestRingContact(lon, lat, ring);
  if (hit) {
    return { east: hit.east, north: hit.north };
  }
  return { east: 0, north: 1 };
}

export function isInsideBuildingAabb(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
): boolean {
  return buildings.some((building) => {
    const box = buildingAabb(building);
    return box ? pointInAabb(lon, lat, box) : false;
  });
}

export function isInsideBuildingRing(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
): boolean {
  return buildings.some((building) => pointInRing(lon, lat, building.ring));
}

export function hitsSolidBuilding(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
  radiusM = AVATAR_RADIUS_M,
): boolean {
  return buildings.some((building) => circleHitsBuilding(lon, lat, radiusM, building));
}

/** Outward normal from the nearest AABB point toward the body (east/north). */
export function aabbOutwardNormal(lon: number, lat: number, box: LonLatBox): { east: number; north: number } {
  const closestLon = Math.min(box.east, Math.max(box.west, lon));
  const closestLat = Math.min(box.north, Math.max(box.south, lat));
  const east = (lon - closestLon) * metersPerDegLon(lat);
  const north = (lat - closestLat) * M_PER_DEG_LAT;
  const len = Math.hypot(east, north);
  if (len > 1e-7) {
    return { east: east / len, north: north / len };
  }
  const mPerLon = metersPerDegLon(lat);
  const dWest = (lon - box.west) * mPerLon;
  const dEast = (box.east - lon) * mPerLon;
  const dSouth = (lat - box.south) * M_PER_DEG_LAT;
  const dNorth = (box.north - lat) * M_PER_DEG_LAT;
  const nearest = Math.min(dWest, dEast, dSouth, dNorth);
  if (nearest === dWest) {
    return { east: -1, north: 0 };
  }
  if (nearest === dEast) {
    return { east: 1, north: 0 };
  }
  if (nearest === dSouth) {
    return { east: 0, north: -1 };
  }
  return { east: 0, north: 1 };
}

function solidOutwardNormal(
  lon: number,
  lat: number,
  building: BuildingPoly,
): { east: number; north: number } {
  if (building.ring.length >= 4) {
    return ringOutwardNormal(lon, lat, building.ring);
  }
  const box = buildingAabb(building);
  return box ? aabbOutwardNormal(lon, lat, box) : { east: 0, north: 1 };
}

/** Remove the component walking into nearby footprint faces so the rest slides. */
export function projectSlide(
  east: number,
  north: number,
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
  radiusM = AVATAR_RADIUS_M,
): { east: number; north: number } {
  let e = east;
  let n = north;
  for (const building of buildings) {
    const box = buildingAabb(building);
    const probe = offsetLngLat(lon, lat, e, n);
    if (
      box &&
      !circleHitsAabb(lon, lat, radiusM + 0.22, box) &&
      !circleHitsAabb(probe.lon, probe.lat, radiusM, box)
    ) {
      continue;
    }
    const closeNow = circleHitsBuilding(lon, lat, radiusM + 0.22, building);
    const hitsNext = circleHitsBuilding(probe.lon, probe.lat, radiusM, building);
    if (!closeNow && !hitsNext) {
      continue;
    }
    const normal = solidOutwardNormal(closeNow ? lon : probe.lon, closeNow ? lat : probe.lat, building);
    const into = e * -normal.east + n * -normal.north;
    if (into > 0) {
      e += normal.east * into;
      n += normal.north * into;
    }
  }
  return { east: e, north: n };
}

export function separateFromBuildings(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
  radiusM = AVATAR_RADIUS_M,
): { lon: number; lat: number } {
  let outLon = lon;
  let outLat = lat;
  for (let iter = 0; iter < 3; iter += 1) {
    let moved = false;
    for (const building of buildings) {
      if (!circleHitsBuilding(outLon, outLat, radiusM, building)) {
        continue;
      }
      const contact =
        building.ring.length >= 4 ? closestRingContact(outLon, outLat, building.ring) : null;
      let push = 0;
      let normal = { east: 0, north: 1 };
      if (contact) {
        push = contact.inside
          ? contact.distM + radiusM + 0.002
          : radiusM - contact.distM + 0.002;
        normal = { east: contact.east, north: contact.north };
      } else {
        const box = buildingAabb(building);
        if (!box) {
          continue;
        }
        const closestLon = Math.min(box.east, Math.max(box.west, outLon));
        const closestLat = Math.min(box.north, Math.max(box.south, outLat));
        const dist = distanceM({ lon: outLon, lat: outLat }, { lon: closestLon, lat: closestLat });
        push = radiusM - dist + 0.002;
        normal = aabbOutwardNormal(outLon, outLat, box);
      }
      if (push <= 0) {
        continue;
      }
      const next = offsetLngLat(outLon, outLat, normal.east * push, normal.north * push);
      outLon = next.lon;
      outLat = next.lat;
      moved = true;
    }
    if (!moved) {
      break;
    }
  }
  return { lon: outLon, lat: outLat };
}

export function hitBuildingId(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
  radiusM = AVATAR_RADIUS_M,
): string | null {
  for (const building of buildings) {
    if (circleHitsBuilding(lon, lat, radiusM, building)) {
      return building.id;
    }
  }
  return null;
}

export function isInsideBuilding(lon: number, lat: number, buildings: BuildingPoly[]): boolean {
  return isInsideBuildingRing(lon, lat, buildings);
}

export function isWalkable(
  lon: number,
  lat: number,
  buildings: BuildingPoly[],
  bbox: BBox,
): boolean {
  if (!isInsideAoi(lon, lat, bbox)) {
    return false;
  }
  if (buildings.length === 0) {
    return false;
  }
  return !hitsSolidBuilding(lon, lat, buildings);
}

/**
 * WASD along look. Right vector is Hòn Gió's flipped screen-right
 * (`-cos`, `+sin`), not anatomic right.
 *
 * Three.js lookAt from behind heading 0 (camera south, looking +Z) has
 * camera-right = west. Geographic "A = west" is therefore screen-RIGHT.
 * Demo comment: from behind, A must use the flipped vector or it feels
 * inverted. Do not flip this again when changing LOOK_YAW_SIGN.
 */
export function cameraRelativeAxes(
  forward: number,
  right: number,
  bearingDeg: number,
): { east: number; north: number } {
  const rad = (bearingDeg * Math.PI) / 180;
  const sinB = Math.sin(rad);
  const cosB = Math.cos(rad);
  return {
    east: forward * sinB - right * cosB,
    north: forward * cosB + right * sinB,
  };
}

export function wrapHeadingDeg(headingDeg: number): number {
  return ((headingDeg % 360) + 360) % 360;
}

/** W/S walk along facing. A/D (turn) rotate in place. Heading is kept on reverse. */
export function applyFacingMove(
  state: AvatarState,
  forward: number,
  turn: number,
  dtSec: number,
  buildings: BuildingPoly[],
  bbox: BBox,
  sprint = false,
): AvatarState {
  const dt = Math.min(dtSec, 0.05);
  const heading = wrapHeadingDeg(state.heading + turn * TURN_YAW_SIGN * TURN_DEG_PER_SEC * dt);
  const faced = { ...state, heading, sprint: false, turning: false };
  if (forward === 0) {
    return { ...faced, pose: "idle", turning: turn !== 0 };
  }
  const rad = (heading * Math.PI) / 180;
  const stepped = tryStep(
    faced,
    Math.sin(rad) * forward,
    Math.cos(rad) * forward,
    dt,
    buildings,
    bbox,
    moveSpeedMps(sprint),
  );
  return { ...stepped, heading, sprint: sprint && stepped.pose === "walk", turning: false };
}

/** WASD along current heading: W/S forward, A/D strafe. Does not turn the body. */
export function applyLookMove(
  state: AvatarState,
  forward: number,
  strafe: number,
  dtSec: number,
  buildings: BuildingPoly[],
  bbox: BBox,
  sprint = false,
): AvatarState {
  if (forward === 0 && strafe === 0) {
    return { ...state, pose: "idle", sprint: false, turning: false };
  }
  const axes = cameraRelativeAxes(forward, strafe, state.heading);
  const stepped = tryStep(state, axes.east, axes.north, dtSec, buildings, bbox, moveSpeedMps(sprint));
  return {
    ...stepped,
    heading: state.heading,
    sprint: sprint && stepped.pose === "walk",
    turning: false,
  };
}

export function tryStep(
  state: AvatarState,
  eastM: number,
  northM: number,
  dtSec: number,
  buildings: BuildingPoly[],
  bbox: BBox,
  speedMps = WALK_SPEED_MPS,
): AvatarState {
  const moving = eastM !== 0 || northM !== 0;
  if (!moving) {
    return { ...state, pose: "idle", sprint: false };
  }
  const len = Math.hypot(eastM, northM);
  const scale = (speedMps * Math.min(dtSec, 0.05)) / len;
  const east = eastM * scale;
  const north = northM * scale;
  const heading = headingFromDelta(eastM, northM);
  const settle = (lon: number, lat: number, pose: AvatarPose): AvatarState => {
    const held = clampInsideAoi(lon, lat, bbox);
    const safe = separateFromBuildings(held.lon, held.lat, buildings);
    const pinned = clampInsideAoi(safe.lon, safe.lat, bbox);
    if (!isWalkable(pinned.lon, pinned.lat, buildings, bbox)) {
      const stay = clampInsideAoi(state.lon, state.lat, bbox);
      return { ...state, lon: stay.lon, lat: stay.lat, heading, pose: "idle", sprint: false, turning: false };
    }
    return { ...state, lon: pinned.lon, lat: pinned.lat, heading, pose };
  };
  const next = offsetLngLat(state.lon, state.lat, east, north);
  if (isWalkable(next.lon, next.lat, buildings, bbox)) {
    return settle(next.lon, next.lat, "walk");
  }
  const slideB = projectSlide(east, north, state.lon, state.lat, buildings);
  const slide = projectBoundSlide(slideB.east, slideB.north, state.lon, state.lat, bbox);
  if (Math.hypot(slide.east, slide.north) > 1e-6) {
    const along = offsetLngLat(state.lon, state.lat, slide.east, slide.north);
    const held = separateFromBuildings(along.lon, along.lat, buildings);
    if (isWalkable(held.lon, held.lat, buildings, bbox)) {
      return settle(held.lon, held.lat, "walk");
    }
    if (isWalkable(along.lon, along.lat, buildings, bbox)) {
      return settle(along.lon, along.lat, "walk");
    }
  }
  const onlyEast = offsetLngLat(state.lon, state.lat, east, 0);
  if (east !== 0 && isWalkable(onlyEast.lon, onlyEast.lat, buildings, bbox)) {
    return settle(onlyEast.lon, onlyEast.lat, "walk");
  }
  const onlyNorth = offsetLngLat(state.lon, state.lat, 0, north);
  if (north !== 0 && isWalkable(onlyNorth.lon, onlyNorth.lat, buildings, bbox)) {
    return settle(onlyNorth.lon, onlyNorth.lat, "walk");
  }
  const stay = clampInsideAoi(state.lon, state.lat, bbox);
  return { ...state, lon: stay.lon, lat: stay.lat, heading, pose: "idle", sprint: false, turning: false };
}

/**
 * Street E / Nearby. playPose is the drawn stall plant (mesh xz).
 * Persist lon/lat stay in the catalog. When persist and plant split
 * (kiosk on the sidewalk, marker in the lane), empty persist must
 * not own E — stand closer to the plant than to persist.
 * Driving-lane stands (laneM ≲ STREET_SHOP_ASPHALT_LANE_M) never own
 * a sidewalk kiosk even if the plant is still inside maxM.
 */
export function nearestPublishedShop<T extends { lon: number; lat: number }>(
  avatar: { lon: number; lat: number },
  shops: T[],
  maxM = NEARBY_SHOP_M,
  playPose?: (shop: T) => { lon: number; lat: number },
  laneM?: number,
): T | null {
  if (laneM != null && Number.isFinite(laneM) && laneM <= STREET_SHOP_ASPHALT_LANE_M) {
    return null;
  }
  let best: T | null = null;
  let bestD = maxM;
  for (const shop of shops) {
    if (!isStreetPlayShop(shop)) {
      continue;
    }
    const pose = playPose?.(shop) ?? shop;
    const d = distanceM(avatar, pose);
    if (d > bestD) {
      continue;
    }
    if (playPose) {
      const persistD = distanceM(avatar, shop);
      const splitM = distanceM(pose, shop);
      if (splitM > 3 && persistD + 0.4 < d) {
        continue;
      }
    }
    best = shop;
    bestD = d;
  }
  return best;
}
