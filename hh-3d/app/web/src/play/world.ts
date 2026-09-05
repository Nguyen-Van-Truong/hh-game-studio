import type { BuildingPoly } from "../avatar/walk";
import {
  AVATAR_SPAWN,
  M_PER_DEG_LAT,
  SPAWN_KEEP_OUT_M,
  inSpawnKeepOut,
  isStreetPlayShop,
  metersPerDegLon,
} from "../avatar/walk";
import type { FeatureCollection } from "../contracts/types";
import { AOI_CENTER, buildingsFromCollection } from "../map/aoi";

export const WORLD_ORIGIN = {
  lon: AOI_CENTER[0],
  lat: AOI_CENTER[1],
};

export const PLAY_BEARING_DEG = 0;
export const PLAY_CAM_DISTANCE = 5.6;
export const PLAY_CAM_HEIGHT = 3.55;
export const PLAY_LOOK_Y = 1.32;
export const PLAY_LOOK_AHEAD = 1.4;
export const PLAY_CAM_SIDE = 0.42;
/**
 * Seat B faces west toward A. A south-of-east side keeps the behind-rig
 * off Steps East so the first look is the street / A's tunic.
 */
export const PLAY_CAM_SIDE_B = -1.6;
/** Street look at A. Seat A still uses PLAY_DEFAULT_PITCH_DEG when look is off. */
export const PLAY_SEAT_B_PITCH_DEG = -8;
/** Default north look-up so spawn sky is zenith, not canyon beige. */
export const PLAY_DEFAULT_PITCH_DEG = 10;
/** Demo minHeight. Pitch-up may drop the lens; never through the slab. */
export const PLAY_CAM_MIN_HEIGHT = 0.55;
/** Pull-in along the look ray vs extruded footprint rings. Not mesh collision. */
export const CAM_HIT_KIND = "look-ray-ring" as const;
/** Keep the lens on the street side of a hit face. */
export const CAM_HIT_PAD_M = 0.32;
/** Extra street pad when looking down so the lens is not in a box. */
export const CAM_LOOKDOWN_PAD_M = 0.5;
/** Open-street floor so the lens is not inside the tunic. Wall hits may come closer. */
export const CAM_MIN_FROM_HEAD_M = 0.92;
/** Absolute floor — never through the head / look point. */
export const CAM_ABS_MIN_FROM_HEAD_M = 0.4;
/** When a wall forces a short rig, sit over the nape, not inside the tunic. */
export const CAM_COLLAPSE_Y = 2.38;
/** Shoulder / nape origin for the camera ray. */
export const CAM_HEAD_Y = 1.48;
/** Never drop the lens under the slab / into a box floor. */
export const CAM_STREET_FLOOR_Y = 0.82;
export const STREET_WIDTH_M = 8.6;
export const WALK_WIDTH_M = 16.4;
export const CURB_WIDTH_M = 0.72;
export const CURB_HEIGHT_M = 0.22;
export const EDGE_WIDTH_M = 0.2;
export const PERSON_SCALE = 1.36;
export const GROUND_Y = 0;
export const SLAB_SIZE_M = 400;
export const SURROUND_SIZE_M = 720;
/** Cheap distance haze so far boxes fade. Not a downloaded HDRI. */
export const FOG_KIND = "distance-haze" as const;
export const FOG_NEAR_M = 58;
export const FOG_FAR_M = 155;
/** Skip inner door/glass/awning (and distant scooters) past this range. Harbor stays. */
export const FAR_DETAIL_KIND = "inner-door-glass" as const;
export const FAR_DETAIL_M = 90;
export const FAR_DETAIL_CELL_M = 12;
/** Visible authored limit on the 400 m fixture. Not a city beyond the file. */
export const BLOCK_EDGE_KIND = "curb-wall-lot" as const;
export const BLOCK_HALF_M = SLAB_SIZE_M / 2;
export const BLOCK_WALL_H_M = 2.28;
export const BLOCK_WALL_T_M = 0.52;
export const BLOCK_CURB_W_M = 0.7;
export const BLOCK_CURB_H_M = 0.26;
export const BLOCK_LOT_W_M = 12;
export const BLOCK_WALL_COLOR = "#7a7268";
export const BLOCK_COPE_COLOR = "#c4b8a4";
export const BLOCK_LOT_COLOR = "#3d7a88";
export const BLOCK_LOT_DEEP = "#2f6a78";

/** Authored street language — not photogrammetry, not a beige sandbox. */
export const GROUND_KIND = "road-walk-curb" as const;
export const ROAD_COLOR = "#1a1c20";
export const WALK_COLOR = "#ddd6c8";
export const PLAZA_COLOR = "#b5b1a6";
export const SURROUND_COLOR = "#2a2c2e";
export const CURB_COLOR = "#8f8778";
export const EDGE_COLOR = "#e4cf6a";
export const ASPHALT_STREET_IDS = ["street-harbor-walk", "street-tram-approach"] as const;
/** Inner parcel lanes already carved in the 400 m fixture — not a new downtown. */
export const SIDE_STREET_KIND = "door-glass-lamp" as const;
export const INNER_STREET_PREFIX = "street-inner-";
export const INNER_LANE_GAP_MIN_M = 3.6;
export const INNER_LANE_GAP_MAX_M = 7.2;
export const INNER_LINK_GAP_MAX_M = 22;
export const INNER_MIN_OVERLAP_M = 10;
export const INNER_LANE_WIDTH_M = 2.35;
export const INNER_LINK_WIDTH_MAX_M = 6.2;
export const INNER_LAMP_MAX = 10;
export const INNER_SCOOTER_MAX = 8;
export const INNER_NEAR_MAIN_M = 22;
/** Same cheap Harbor language on derived inner centerlines — not a city grid. */
export const INNER_LANE_KIND = "asphalt-walk-edge" as const;
export const INNER_WALK_OVER_ROAD_M = 1.15;
export const INNER_WALK_RATIO = 1.85;
export const INNER_WALK_WALL_PAD_M = 0.28;

/** Slim HUD chip for the four authored names. Not GPS. Not OSM. Not a city. */
export const STREET_HUD_KIND = "named-chip" as const;
export const STREET_HUD_EMPTY = "—";
/** Corner minimap lines for the same four HUD names. In-memory, not OSM. */
export const MINIMAP_LANE_KIND = "authored-hud-lanes" as const;
/** Cheap 2D dots for street-play published stalls. Plant pose, not persist. */
export const MINIMAP_SHOP_KIND = "street-play-plant" as const;

/** Cheap authored street-name plaques — fixture names, not a downtown grid. */
export const STREET_PLAQUE_KIND = "pole-board" as const;
export const PLAQUE_COLLIDE_HALF_M = 0.36;
export const PLAQUE_SKIP_LANTERN_M = 10.2;
export const PLAQUE_BOARD_W = 2.62;
export const PLAQUE_BOARD_H = 0.94;
export const PLAQUE_POLE_H = 2.48;
export const PLAQUE_BOARD_Y = 2.12;
export const PLAQUE_COLOR = "#1f4a3c";
export const PLAQUE_CREAM = "#f3e6c4";
export const PLAQUE_POLE = "#4a3a28";

/** Cheap gradient sky — not photogrammetry, not a beige/gray void. */
export const SKY_KIND = "gradient-hemisphere" as const;
export const SKY_ZENITH = "#2f74c4";
export const SKY_MID = "#3d8ee0";
export const SKY_HORIZON = "#6eb4ea";
export const SKY_GROUND_HAZE = "#4a90cc";
export const SKY_SUN = "#fff3c4";
export const SKY_FOG = "#8ec4e8";
export const SKY_CLEAR = "#3d8ee0";
export const SKY_HEMI_UP = "#9ec8f2";
export const SKY_HEMI_DOWN = "#3c3a36";
export const SUN_LOCAL = [22, 68, 95] as const;
export const SUN_KEY = [38, 46, 16] as const;
export const SUN_COLOR = "#fff1c8";
export const SUN_INTENSITY = 2.2;
export const HEMI_INTENSITY = 0.78;
export const AMBIENT_INTENSITY = 0.22;
export const FILL_INTENSITY = 0.72;
export const SHADOW_EXTENT_M = 42;
export const LIGHT_KIND = "hemi-sun" as const;
export const SUN_DISC_R = 6.2;
export const SKY_DOME_R = 380;
export const WALL_FINISH_KIND = "plaster-paint" as const;

/** Cheap authored street furniture — not photogrammetry, not downloaded models. */
export const STREET_PROPS_KIND = "lamps-crosswalk-planters" as const;
export const LAMP_SPACING_M = 40;
export const LAMP_CURB_M = STREET_WIDTH_M / 2 + 0.52;
export const LAMP_SKIP_SPAWN_M = 16;
export const LAMP_SKIP_CROSSING_M = 12;
export const LAMP_COLLIDE_HALF_M = 0.28;
export const PLANTER_COLLIDE_HALF_M = 0.62;
export const LAMP_GLOW_MAX = 6;
export const LAMP_COLOR = "#2c3036";
export const LAMP_GLOW_COLOR = "#ffe7a0";
export const LAMP_LIGHT_COLOR = "#ffd89a";
export const CROSSWALK_COLOR = "#f4f1e4";
/** Authored Harbor Walk mouths at Steps East, Steps West, and Tram Approach. Not a fifth street, not OSM. */
export const CORNER_CROSSING_KIND = "zebra-stopline-curb" as const;
export const CORNER_CROSSWALK_ID = "crosswalk-harbor-steps-east";
export const CORNER_STOP_LINE_ID = "stopline-harbor-steps-east";
export const WEST_CROSSWALK_ID = "crosswalk-harbor-steps-west";
export const WEST_STOP_LINE_ID = "stopline-harbor-steps-west";
export const TRAM_CROSSWALK_ID = "crosswalk-harbor-tram";
export const TRAM_STOP_LINE_ID = "stopline-harbor-tram";
export const CORNER_ZEBRA_STRIPES = 7;
export const CORNER_ZEBRA_ALONG_M = 0.58;
export const CORNER_ZEBRA_GAP_M = 0.42;
export const CORNER_STOP_THICK_M = 0.4;
export const CORNER_CURB_ALONG_M = 2.2;
export const CORNER_CURB_ARM_M = 2.15;
export const CORNER_MOUTH_HALF_M = 2.8;
export const CORNER_SKIP_SPAWN_M = 16;
export const CORNER_SKIP_LANTERN_M = 5.2;
/** West ribbon sits farther from Harbor than the east gap. */
export const WEST_CORNER_DIST_MAX_M = 22;
/** Inner Steps West asphalt + walk edge. Harbor width would hit the west wall. */
export const WEST_ZEBRA_ACROSS_M = 4.2;
/** Sit the official-official zebra on Tram Approach just east of Harbor. */
export const TRAM_MOUTH_ALONG_M = 5.55;
export const TRAM_JOIN_MAX_M = 8;
/** Steps mouths sit near z=-76; the Tram mouth must stay north of this. */
export const TRAM_SKIP_STEPS_Z = -40;

export function isHarborStepsCrosswalk(id: string): boolean {
  return id === CORNER_CROSSWALK_ID || id === WEST_CROSSWALK_ID;
}
export function isHarborTramCrosswalk(id: string): boolean {
  return id === TRAM_CROSSWALK_ID;
}
export function isAuthoredMouthCrosswalk(id: string): boolean {
  return isHarborStepsCrosswalk(id) || isHarborTramCrosswalk(id);
}
export const PLANTER_BOX_COLOR = "#6b5340";
export const PLANTER_TRUNK_COLOR = "#5a4030";
export const PLANTER_CANOPY_COLOR = "#3f6b38";
/** Cheap parked box scooters — authored props, not traffic, not brands. */
export const SCOOTER_KIND = "parked-box-scooter" as const;
export const SCOOTER_CURB_M = STREET_WIDTH_M / 2 + 1.28;
export const SCOOTER_SPACING_M = 28;
export const SCOOTER_START_M = 22;
export const SCOOTER_END_PAD_M = 22;
export const SCOOTER_SKIP_SPAWN_M = 2.8;
export const SCOOTER_SKIP_LANTERN_M = 11;
export const SCOOTER_SKIP_ZEBRA_M = 5;
export const SCOOTER_SKIP_CROSSING_M = 9;
export const SCOOTER_COLLIDE_HALF_M = 0.78;
export const SCOOTER_MIN_LAMP_M = 1.9;
export const SCOOTER_MIN_PLANTER_M = 2.2;
export const SCOOTER_MIN_PEER_M = 8;
export const SCOOTER_PLASTIC = "#1c1d20";
export const SCOOTER_WHEEL = "#2a2b2e";
export const SCOOTER_BAR = "#4a4036";
export const SCOOTER_COLORS = [
  "#c45a2a",
  "#2a6b8a",
  "#3d3f44",
  "#c4b04a",
  "#6e3d5a",
  "#4a7a3a",
  "#8a3a32",
  "#2f4f6e",
  "#b8783a",
  "#5a5c62",
] as const;
/** Same stall the walker already uses for E. Not a new downtown. */
export const LANTERN_SHOP_LL = { lon: 106.6980366, lat: 10.7718712 } as const;

/** Cheap authored market spill — boxes/cylinders, not a real inventory. */
export const MARKET_SPILL_KIND = "crate-basket-stack" as const;
export const CRATE_WOOD = "#8a5a32";
export const CRATE_WOOD_DARK = "#6b4224";
export const COOLER_TEAL = "#2a7a78";
export const COOLER_LID = "#3d9a94";
export const BASKET_RIM = "#c4a06a";
export const BASKET_IN = "#a87840";
export const SPILL_COLLIDE_HALF_M = 0.48;
export const SPILL_SKIP_SPAWN_M = 3.4;
export const SPILL_SKIP_LANTERN_M = 10;
export const SPILL_SKIP_ZEBRA_M = 5;
export const SPILL_SKIP_SCOOTER_M = 2.2;
export const SPILL_SKIP_PLANTER_M = 2.1;
export const SPILL_SKIP_PEER_M = 7.5;
export const SPILL_STREET_ACROSS_M = STREET_WIDTH_M / 2 + 2.55;
export const SPILL_HASH_CRATES = [
  "#8a5a32",
  "#6e3d24",
  "#a06a3a",
  "#5a4030",
  "#9a6a42",
  "#7a4a28",
] as const;

/** Cheap authored storefront — awning + kiosk, not an interior, not photogrammetry. */
export const SHOP_STALL_KIND = "awning-kiosk" as const;
/** Painted chalkboard on the kiosk face. Authored fiction names, not a live market. */
export const STALL_BOARD_KIND = "chalkboard-menu" as const;
export const STALL_BOARD_SLATE = "#1a3328";
export const STALL_BOARD_CHALK = "#e8d9a8";
export const STALL_BOARD_FRAME = "#5a3a22";
export const STALL_BOARD_HONESTY = "mẫu · not a live market";
export const STALL_AWNING_W = 4.15;
export const STALL_AWNING_H = 0.28;
export const STALL_AWNING_D = 3.05;
export const STALL_AWNING_Y = 2.58;
export const STALL_BODY_BACK_M = 0.72;
/** Harbor/Tram sidewalk hug — same band as planters / plaques (~7 m across). */
export const STALL_SIDEWALK_ACROSS_M = 7.2;
/** Persist plant already off the driving lane (lantern) stays put. */
export const STALL_OFF_LANE_M = STREET_WIDTH_M / 2 + 1.5;
export const STALL_COLLIDE_HALF_X = 1.32;
export const STALL_COLLIDE_HALF_Z = 0.88;
export const STALL_COUNTER_COLOR = "#6a4a32";
export const STALL_POST_COLOR = "#4a3224";
export const AWNING_COLORS = [
  "#1e8a7c",
  "#2f5fbe",
  "#b82e4a",
  "#c48a12",
  "#4a8c2e",
  "#6e3d9a",
  "#c45a18",
  "#1f6f8a",
] as const;

/** Muted neighborhood tints from building ids — not a downtown palette. */
export const WALLS = [
  "#c9a06e",
  "#b89062",
  "#d4b07a",
  "#a67c58",
  "#c09a68",
  "#b89a7a",
  "#a8885c",
  "#d2ae78",
  "#9a7a62",
  "#c4a090",
  "#8e6d55",
  "#d8b48a",
  "#b07058",
  "#c8b090",
  "#8f8468",
  "#be8a6a",
  "#a89878",
  "#d2c0a4",
  "#7d6a58",
  "#c9b4a0",
] as const;
export const ROOFS = [
  "#8f4034",
  "#7a3830",
  "#a34a38",
  "#6e322c",
  "#91503a",
  "#6a4a40",
  "#9a3f32",
  "#7d4a38",
  "#6b4038",
  "#8a5344",
  "#7a4e3a",
  "#5e3a34",
  "#9b5a42",
  "#704840",
  "#865040",
  "#5a4038",
] as const;

export type WorldPoint = {
  x: number;
  z: number;
};

export type WallFinish = "plaster" | "paint";

export type WorldBuilding = {
  id: string;
  name: string;
  height_m: number;
  points: [number, number][];
  cx: number;
  cz: number;
  width: number;
  depth: number;
  wall: string;
  roof: string;
  finish: WallFinish;
};

export type StreetSurface = "asphalt" | "walk";
export type StreetLane = "main" | "inner";

export type WorldStreet = {
  id: string;
  name: string;
  points: [number, number][];
  surface: StreetSurface;
  lane: StreetLane;
  widthM: number;
  halfGapM: number;
};

export function isInnerStreetId(id: string): boolean {
  return id.startsWith(INNER_STREET_PREFIX);
}

export function isInnerStreet(street: WorldStreet): boolean {
  return street.lane === "inner" || isInnerStreetId(street.id);
}

export function streetRoadWidth(street: WorldStreet): number {
  return street.widthM > 0 ? street.widthM : STREET_WIDTH_M;
}

/** Lighter walk band around an inner asphalt ribbon. Stays inside the parcel gap. */
export function innerWalkWidth(street: WorldStreet): number {
  const road = streetRoadWidth(street);
  const gap = street.halfGapM > 0 ? street.halfGapM * 2 : road + INNER_WALK_OVER_ROAD_M * 2;
  const want = Math.max(road + INNER_WALK_OVER_ROAD_M, road * INNER_WALK_RATIO);
  const inside = Math.max(road + 0.7, gap - INNER_WALK_WALL_PAD_M);
  return Math.min(inside, want);
}

export type WorldPark = {
  id: string;
  name: string;
  points: [number, number][];
};

export type WorldPlaceMark = {
  id: string;
  name: string;
  x: number;
  z: number;
};

export type StreetSegment = {
  x: number;
  z: number;
  length: number;
  width: number;
  rotationY: number;
};

export type BlockEdgePiece = {
  id: string;
  kind: "wall" | "curb" | "lot" | "cope";
  x: number;
  y: number;
  z: number;
  sx: number;
  sy: number;
  sz: number;
  color: string;
};

/** Low wall + inner curb + outer water/lot on the 400 m GeoJSON bounds. */
export function blockEdgePieces(): BlockEdgePiece[] {
  const h = BLOCK_HALF_M;
  const wt = BLOCK_WALL_T_M;
  const wh = BLOCK_WALL_H_M;
  const cw = BLOCK_CURB_W_M;
  const ch = BLOCK_CURB_H_M;
  const lw = BLOCK_LOT_W_M;
  const span = SLAB_SIZE_M + wt;
  const lotSpan = SLAB_SIZE_M + lw;
  const curbInset = wt / 2 + cw / 2;
  const lotOut = wt / 2 + lw / 2;
  const walls: BlockEdgePiece[] = [
    { id: "block-wall-s", kind: "wall", x: 0, y: wh / 2, z: -h, sx: span, sy: wh, sz: wt, color: BLOCK_WALL_COLOR },
    { id: "block-wall-n", kind: "wall", x: 0, y: wh / 2, z: h, sx: span, sy: wh, sz: wt, color: BLOCK_WALL_COLOR },
    { id: "block-wall-w", kind: "wall", x: -h, y: wh / 2, z: 0, sx: wt, sy: wh, sz: span, color: BLOCK_WALL_COLOR },
    { id: "block-wall-e", kind: "wall", x: h, y: wh / 2, z: 0, sx: wt, sy: wh, sz: span, color: BLOCK_WALL_COLOR },
  ];
  const curbs: BlockEdgePiece[] = [
    { id: "block-curb-s", kind: "curb", x: 0, y: ch / 2, z: -(h - curbInset), sx: SLAB_SIZE_M - wt, sy: ch, sz: cw, color: CURB_COLOR },
    { id: "block-curb-n", kind: "curb", x: 0, y: ch / 2, z: h - curbInset, sx: SLAB_SIZE_M - wt, sy: ch, sz: cw, color: CURB_COLOR },
    { id: "block-curb-w", kind: "curb", x: -(h - curbInset), y: ch / 2, z: 0, sx: cw, sy: ch, sz: SLAB_SIZE_M - wt, color: CURB_COLOR },
    { id: "block-curb-e", kind: "curb", x: h - curbInset, y: ch / 2, z: 0, sx: cw, sy: ch, sz: SLAB_SIZE_M - wt, color: CURB_COLOR },
  ];
  const lots: BlockEdgePiece[] = [
    { id: "block-lot-s", kind: "lot", x: 0, y: -0.04, z: -(h + lotOut), sx: lotSpan, sy: 0.2, sz: lw, color: BLOCK_LOT_COLOR },
    { id: "block-lot-n", kind: "lot", x: 0, y: -0.04, z: h + lotOut, sx: lotSpan, sy: 0.2, sz: lw, color: BLOCK_LOT_DEEP },
    { id: "block-lot-w", kind: "lot", x: -(h + lotOut), y: -0.04, z: 0, sx: lw, sy: 0.2, sz: lotSpan, color: BLOCK_LOT_COLOR },
    { id: "block-lot-e", kind: "lot", x: h + lotOut, y: -0.04, z: 0, sx: lw, sy: 0.2, sz: lotSpan, color: BLOCK_LOT_DEEP },
  ];
  const copeH = 0.16;
  const copes: BlockEdgePiece[] = walls.map((wall) => ({
    id: wall.id.replace("wall", "cope"),
    kind: "cope",
    x: wall.x,
    y: wall.y + wall.sy / 2 + copeH / 2,
    z: wall.z,
    sx: wall.sx + 0.12,
    sy: copeH,
    sz: wall.sz + 0.12,
    color: BLOCK_COPE_COLOR,
  }));
  return [...walls, ...curbs, ...lots, ...copes];
}

export function countBlockEdge(pieces: BlockEdgePiece[]): {
  walls: number;
  curbs: number;
  lots: number;
  copes: number;
} {
  return {
    walls: pieces.filter((row) => row.kind === "wall").length,
    curbs: pieces.filter((row) => row.kind === "curb").length,
    lots: pieces.filter((row) => row.kind === "lot").length,
    copes: pieces.filter((row) => row.kind === "cope").length,
  };
}

export function lngLatToWorld(
  lon: number,
  lat: number,
  origin = WORLD_ORIGIN,
): WorldPoint {
  return {
    x: (lon - origin.lon) * metersPerDegLon(origin.lat),
    z: (lat - origin.lat) * M_PER_DEG_LAT,
  };
}

export function worldToLngLat(
  x: number,
  z: number,
  origin = WORLD_ORIGIN,
): { lon: number; lat: number } {
  return {
    lon: origin.lon + x / metersPerDegLon(origin.lat),
    lat: origin.lat + z / M_PER_DEG_LAT,
  };
}

export function headingToYaw(headingDeg: number): number {
  return (headingDeg * Math.PI) / 180;
}

/** Seat B uses a south street offset so the west look is not inside Steps East. */
export function seatFollowSide(seat: string): number {
  return seat === "b" ? PLAY_CAM_SIDE_B : PLAY_CAM_SIDE;
}

export type FollowCameraPose = {
  x: number;
  y: number;
  z: number;
  lookX: number;
  lookY: number;
  lookZ: number;
  yawDeg: number;
  pitchDeg: number;
};

export type FollowCameraResolved = FollowCameraPose & {
  hit: boolean;
  hitId: string | null;
  distM: number;
  desiredDistM: number;
  kind: typeof CAM_HIT_KIND;
};

/** Third-person rig: stay behind current heading/look yaw, optional pitch. */
export function followCameraPose(
  pos: WorldPoint,
  headingDeg: number,
  distance = PLAY_CAM_DISTANCE,
  height = PLAY_CAM_HEIGHT,
  side = PLAY_CAM_SIDE,
  lookAhead = PLAY_LOOK_AHEAD,
  alt = 0,
  pitchDeg = 0,
): FollowCameraPose {
  const yaw = headingToYaw(headingDeg);
  const pitch = (Math.max(-42, Math.min(28, pitchDeg)) * Math.PI) / 180;
  const sin = Math.sin(yaw);
  const cos = Math.cos(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const distH = distance * cp;
  const chestY = PLAY_LOOK_Y + alt;
  const camLift = height - PLAY_LOOK_Y;
  const minY = Math.max(CAM_STREET_FLOOR_Y, PLAY_CAM_MIN_HEIGHT) + alt;
  return {
    x: pos.x - sin * distH + cos * side,
    y: Math.max(minY, chestY + camLift - sp * distance),
    z: pos.z - cos * distH - sin * side,
    lookX: pos.x + sin * lookAhead * cp,
    lookY: chestY + lookAhead * sp,
    lookZ: pos.z + cos * lookAhead * cp,
    yawDeg: ((headingDeg % 360) + 360) % 360,
    pitchDeg,
  };
}

function raySegmentT(
  ox: number,
  oz: number,
  dx: number,
  dz: number,
  ax: number,
  az: number,
  bx: number,
  bz: number,
): number | null {
  const ex = bx - ax;
  const ez = bz - az;
  const det = dx * ez - dz * ex;
  if (Math.abs(det) < 1e-10) {
    return null;
  }
  const t = ((ax - ox) * ez - (az - oz) * ex) / det;
  const u = ((ax - ox) * dz - (az - oz) * dx) / det;
  if (t < 0 || t > 1 || u < 0 || u > 1) {
    return null;
  }
  return t;
}

function pointInWorldRing(x: number, z: number, points: [number, number][]): boolean {
  let inside = false;
  const n = points.length;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const pi = points[i];
    const pj = points[j];
    if (!pi || !pj || pj[1] === pi[1]) {
      continue;
    }
    if (pi[1] > z !== pj[1] > z && x < ((pj[0] - pi[0]) * (z - pi[1])) / (pj[1] - pi[1]) + pi[0]) {
      inside = !inside;
    }
  }
  return inside;
}

/** First wall on the head→desired-camera ray. Vertical ring faces only; lids stay visual. */
export function cameraRayHit(
  from: { x: number; y: number; z: number },
  to: { x: number; y: number; z: number },
  buildings: BuildingPoly[],
): { t: number; id: string } | null {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dz = to.z - from.z;
  const midX = (from.x + to.x) * 0.5;
  const midZ = (from.z + to.z) * 0.5;
  const span = Math.hypot(dx, dz) * 0.5 + 1.4;
  let bestT = 1;
  let bestId: string | null = null;
  for (const building of buildings) {
    if (building.ring.length < 4) {
      continue;
    }
    const points = ringToPoints(building.ring);
    const box = aabbOf(points);
    if (Math.abs(box.cx - midX) > box.width * 0.5 + span) {
      continue;
    }
    if (Math.abs(box.cz - midZ) > box.depth * 0.5 + span) {
      continue;
    }
    const height = building.height_m && building.height_m > 0 ? building.height_m : 8;
    const count = points.length;
    for (let i = 0; i < count; i += 1) {
      const a = points[i];
      const b = points[(i + 1) % count];
      if (!a || !b) {
        continue;
      }
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-8) {
        continue;
      }
      const t = raySegmentT(from.x, from.z, dx, dz, a[0], a[1], b[0], b[1]);
      if (t == null || t < 0.02 || t >= bestT) {
        continue;
      }
      const y = from.y + dy * t;
      if (y < -0.2 || y > height + 0.4) {
        continue;
      }
      bestT = t;
      bestId = building.id;
    }
  }
  return bestId ? { t: bestT, id: bestId } : null;
}

/** True when the lens is inside an extruded footprint (box interior / black). */
export function cameraPointInsideSolid(
  x: number,
  y: number,
  z: number,
  buildings: BuildingPoly[],
): { id: string; height: number } | null {
  for (const building of buildings) {
    if (building.ring.length < 4) {
      continue;
    }
    const height = building.height_m && building.height_m > 0 ? building.height_m : 8;
    if (y < -0.2 || y > height + 0.4) {
      continue;
    }
    const points = ringToPoints(building.ring);
    if (pointInWorldRing(x, z, points)) {
      return { id: building.id, height };
    }
  }
  return null;
}

/** Step the lens out of a footprint along the AABB outward, then pad. */
export function pushCameraOutOfSolid(
  x: number,
  y: number,
  z: number,
  buildings: BuildingPoly[],
  padM = CAM_HIT_PAD_M,
): { x: number; y: number; z: number; id: string | null } {
  const hit = cameraPointInsideSolid(x, y, z, buildings);
  if (!hit) {
    return { x, y: Math.max(y, CAM_STREET_FLOOR_Y), z, id: null };
  }
  const building = buildings.find((row) => row.id === hit.id);
  if (!building) {
    return { x, y: Math.max(y, CAM_STREET_FLOOR_Y), z, id: hit.id };
  }
  const points = ringToPoints(building.ring);
  const box = aabbOf(points);
  let vx = x - box.cx;
  let vz = z - box.cz;
  let len = Math.hypot(vx, vz);
  if (len < 1e-6) {
    vx = -1;
    vz = 0;
    len = 1;
  }
  const ux = vx / len;
  const uz = vz / len;
  let ox = x;
  let oz = z;
  for (let i = 0; i < 32; i += 1) {
    ox += ux * 0.28;
    oz += uz * 0.28;
    if (!pointInWorldRing(ox, oz, points)) {
      ox += ux * padM;
      oz += uz * padM;
      break;
    }
  }
  return { x: ox, y: Math.max(y, CAM_STREET_FLOOR_Y), z: oz, id: hit.id };
}

/** Behind-heading unless the player is actively looking. Residual pitch must not steal yaw. */
export function followRigYaw(
  headingDeg: number,
  lookMode: string,
  lookYaw: number,
  lookPitch: number,
): number {
  return lookMode !== "off" ? lookYaw : headingDeg;
}

/**
 * Desired behind-rig, then pull in along the look ray if a footprint/stall wall is in the way.
 * Does not turn the body. Does not make roofs walkable.
 */
export function resolveFollowCamera(
  pos: WorldPoint,
  headingDeg: number,
  buildings: BuildingPoly[],
  alt = 0,
  pitchDeg = 0,
  distance = PLAY_CAM_DISTANCE,
  height = PLAY_CAM_HEIGHT,
  side = PLAY_CAM_SIDE,
  lookAhead = PLAY_LOOK_AHEAD,
): FollowCameraResolved {
  const desired = followCameraPose(pos, headingDeg, distance, height, side, lookAhead, alt, pitchDeg);
  const head = { x: pos.x, y: CAM_HEAD_Y + alt, z: pos.z };
  const hit = cameraRayHit(head, desired, buildings);
  const dx = desired.x - head.x;
  const dy = desired.y - head.y;
  const dz = desired.z - head.z;
  const rayLen = Math.hypot(dx, dy, dz);
  const desiredDistM = Math.hypot(desired.x - pos.x, desired.z - pos.z);
  const padM = CAM_HIT_PAD_M + (pitchDeg < -18 ? CAM_LOOKDOWN_PAD_M : 0);
  let t = 1;
  if (hit && rayLen > 1e-6) {
    const padT = padM / rayLen;
    const minT = CAM_MIN_FROM_HEAD_M / rayLen;
    const absMinT = CAM_ABS_MIN_FROM_HEAD_M / rayLen;
    const streetT = hit.t - padT;
    t = streetT >= minT ? Math.min(1, streetT) : Math.max(absMinT, streetT);
  }
  let x = head.x + dx * t;
  let z = head.z + dz * t;
  let distM = Math.hypot(x - pos.x, z - pos.z);
  let y = Math.max(head.y + dy * t, CAM_STREET_FLOOR_Y + alt);
  if (hit && distM < CAM_MIN_FROM_HEAD_M) {
    y = Math.max(y, CAM_COLLAPSE_Y + alt);
  }
  const inside = cameraPointInsideSolid(x, y, z, buildings);
  let hitId = hit?.id ?? null;
  let pulled = Boolean(hit);
  if (inside) {
    const pushed = pushCameraOutOfSolid(x, y, z, buildings, padM);
    x = pushed.x;
    y = pushed.y;
    z = pushed.z;
    hitId = hitId ?? pushed.id;
    pulled = true;
    distM = Math.hypot(x - pos.x, z - pos.z);
  }
  return {
    ...desired,
    x,
    y,
    z,
    hit: pulled,
    hitId,
    distM,
    desiredDistM,
    kind: CAM_HIT_KIND,
  };
}

function ringToPoints(ring: [number, number][]): [number, number][] {
  return ring.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
}

function readRing(coords: unknown): [number, number][] {
  if (!Array.isArray(coords) || !Array.isArray(coords[0])) {
    return [];
  }
  const ring: [number, number][] = [];
  for (const pt of coords[0] as unknown[]) {
    if (!Array.isArray(pt) || pt.length < 2) {
      continue;
    }
    const lon = pt[0];
    const lat = pt[1];
    if (typeof lon === "number" && typeof lat === "number") {
      ring.push([lon, lat]);
    }
  }
  return ring;
}

function readLine(coords: unknown): [number, number][] {
  if (!Array.isArray(coords)) {
    return [];
  }
  const line: [number, number][] = [];
  for (const pt of coords) {
    if (!Array.isArray(pt) || pt.length < 2) {
      continue;
    }
    const lon = pt[0];
    const lat = pt[1];
    if (typeof lon === "number" && typeof lat === "number") {
      line.push([lon, lat]);
    }
  }
  return line;
}

export function colorIndex(id: string): number {
  let n = 0;
  for (let i = 0; i < id.length; i += 1) {
    n = (n + id.charCodeAt(i) * (i + 3)) % 97;
  }
  return n;
}

export function wallColorForId(id: string): string {
  return WALLS[colorIndex(id) % WALLS.length] ?? "#c9a06e";
}

export function roofColorForId(id: string): string {
  return ROOFS[colorIndex(id) % ROOFS.length] ?? "#8f4034";
}

/** Lid slightly darker than the painted/plaster wall so the cap reads. */
export function lidColorForId(id: string): string {
  const wall = wallDisplayColor(id);
  return mixHex(shadeHex(wall, 0.58), roofColorForId(id), 0.22);
}

export function wallFinishForId(id: string): WallFinish {
  return colorIndex(id) % 2 === 0 ? "plaster" : "paint";
}

export function wallRoughnessForFinish(finish: WallFinish): number {
  return finish === "plaster" ? 0.94 : 0.52;
}

export function mixHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = parseHex(a);
  const [br, bg, bb] = parseHex(b);
  const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)));
  const to = (x: number, y: number) => clamp(x + (y - x) * t).toString(16).padStart(2, "0");
  return `#${to(ar, br)}${to(ag, bg)}${to(ab, bb)}`;
}

/** Lift an ID tint toward painted plaster so walls do not read as asphalt. */
export function plasterLift(hex: string): string {
  return mixHex(hex, "#efe6d6", 0.38);
}

export function wallDisplayColor(id: string, finish = wallFinishForId(id)): string {
  const base = wallColorForId(id);
  return finish === "plaster" ? plasterLift(base) : base;
}

export function hexLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

export function isAsphaltStreet(id: string, name = ""): boolean {
  return (
    (ASPHALT_STREET_IDS as readonly string[]).includes(id) ||
    /harbor walk|tram approach/i.test(name)
  );
}

function aabbOf(points: [number, number][]): {
  cx: number;
  cz: number;
  width: number;
  depth: number;
} {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const pt of points) {
    if (!pt) {
      continue;
    }
    minX = Math.min(minX, pt[0]);
    maxX = Math.max(maxX, pt[0]);
    minZ = Math.min(minZ, pt[1]);
    maxZ = Math.max(maxZ, pt[1]);
  }
  return {
    cx: (minX + maxX) / 2,
    cz: (minZ + maxZ) / 2,
    width: Math.max(2, maxX - minX),
    depth: Math.max(2, maxZ - minZ),
  };
}

export function buildingsToWorld(buildings: BuildingPoly[]): WorldBuilding[] {
  return buildings.map((building) => {
    const points = ringToPoints(building.ring);
    const box = aabbOf(points);
    return {
      id: building.id,
      name: building.name ?? building.id,
      height_m: building.height_m && building.height_m > 0 ? building.height_m : 8,
      points,
      cx: box.cx,
      cz: box.cz,
      width: box.width,
      depth: box.depth,
      wall: wallColorForId(building.id),
      roof: lidColorForId(building.id),
      finish: wallFinishForId(building.id),
    };
  });
}

export type FacadeKind = "window" | "door" | "band" | "display" | "storefront" | "awning";

/** Street-facing ground floor on Harbor Walk / Tram Approach / inner lanes. Visual, not shops. */
export const GROUND_FLOOR_KIND = "door-glass-awning" as const;
export const STOREFRONT_DOOR_COLOR = "#1a120e";
export const DISPLAY_GLASS_COLOR = "#1b2733";
export const BUILDING_AWNING_MIX = "#4a2c22";
export const STREET_FACE_MIN_M = 5.4;
export const STREET_FACE_MAX_M = 24;
export const STREET_FACE_ALIGN = 0.45;
export const STREET_FACE_FRONT = 0.4;
export const STOREFRONT_OUT_M = 0.08;
export const AWNING_OUT_M = 0.58;
export const AWNING_THICK_M = 0.1;
export const AWNING_Y = 2.68;

export type FacadePiece = {
  kind: FacadeKind;
  x: number;
  y: number;
  z: number;
  sx: number;
  sy: number;
  sz: number;
  rotationY: number;
  color: string;
};

function parseHex(hex: string): [number, number, number] {
  const raw = hex.startsWith("#") ? hex.slice(1) : hex;
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((ch) => ch + ch)
          .join("")
      : raw;
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n)) {
    return [180, 150, 110];
  }
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Darken an authored wall tint for cheap window/door/band patches. */
export function shadeHex(hex: string, factor: number): string {
  const [r, g, b] = parseHex(hex);
  const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)));
  const to = (value: number) => clamp(value * factor).toString(16).padStart(2, "0");
  return `#${to(r)}${to(g)}${to(b)}`;
}

export type FaceSpec = {
  length: number;
  nx: number;
  nz: number;
  rot: number;
  px: number;
  pz: number;
};

function facesOf(building: WorldBuilding): FaceSpec[] {
  const halfW = building.width / 2;
  const halfD = building.depth / 2;
  return [
    { length: building.width, nx: 0, nz: 1, rot: 0, px: building.cx, pz: building.cz + halfD },
    { length: building.width, nx: 0, nz: -1, rot: 0, px: building.cx, pz: building.cz - halfD },
    { length: building.depth, nx: 1, nz: 0, rot: Math.PI / 2, px: building.cx + halfW, pz: building.cz },
    { length: building.depth, nx: -1, nz: 0, rot: Math.PI / 2, px: building.cx - halfW, pz: building.cz },
  ];
}

/**
 * Cheap window/door/band boxes on AABB faces. Still boxes — not interiors,
 * photogrammetry, or a city.
 */
export function facadePiecesForBuilding(building: WorldBuilding): FacadePiece[] {
  const pieces: FacadePiece[] = [];
  const idn = colorIndex(building.id);
  const wall = building.wall;
  const band = shadeHex(wall, 0.66);
  const glass = shadeHex(wall, 0.36);
  const doorColor = "#3a2a20";
  const height = building.height_m;
  const faces = facesOf(building);
  let doorIdx = 0;
  let best = -1;
  faces.forEach((face, index) => {
    const score = face.length + (face.nz < 0 ? 0.85 : 0);
    if (score > best) {
      best = score;
      doorIdx = index;
    }
  });
  const out = 0.055;
  faces.forEach((face, faceIndex) => {
    if (face.length < 2.4) {
      return;
    }
    pieces.push({
      kind: "band",
      x: face.px + face.nx * out,
      y: 0.38,
      z: face.pz + face.nz * out,
      sx: face.length * 0.96,
      sy: 0.76,
      sz: 0.08,
      rotationY: face.rot,
      color: shadeHex(wall, 0.74),
    });
    if (height >= 7) {
      pieces.push({
        kind: "band",
        x: face.px + face.nx * out,
        y: Math.min(height * 0.42, 4.15),
        z: face.pz + face.nz * out,
        sx: face.length * 0.94,
        sy: 0.4,
        sz: 0.07,
        rotationY: face.rot,
        color: band,
      });
    }
    const tangentX = face.nz !== 0 ? 1 : 0;
    const tangentZ = face.nx !== 0 ? 1 : 0;
    if (face.length < 4.2) {
      if (faceIndex === doorIdx) {
        pieces.push({
          kind: "door",
          x: face.px + face.nx * (out + 0.01),
          y: 1.12,
          z: face.pz + face.nz * (out + 0.01),
          sx: Math.min(1.18, face.length * 0.45),
          sy: 2.15,
          sz: 0.12,
          rotationY: face.rot,
          color: doorColor,
        });
      }
      return;
    }
    const floors = height >= 14 ? 3 : height >= 9 ? 2 : 1;
    const winW = 1.05;
    const winH = 1.22;
    const gap = 2.35;
    const usable = face.length - 2.8;
    let count = Math.max(1, Math.floor(usable / gap));
    count = Math.min(count, 5);
    if ((idn + faceIndex) % 5 === 0 && count > 1) {
      count -= 1;
    }
    const start = -((count - 1) * gap) / 2;
    for (let floor = 0; floor < floors; floor += 1) {
      const y = 1.55 + floor * 3.15;
      if (y + winH / 2 > height - 0.3) {
        continue;
      }
      for (let i = 0; i < count; i += 1) {
        const along = start + i * gap;
        if (floor === 0 && faceIndex === doorIdx && Math.abs(along) < 0.75) {
          continue;
        }
        pieces.push({
          kind: "window",
          x: face.px + face.nx * out + along * tangentX,
          y,
          z: face.pz + face.nz * out + along * tangentZ,
          sx: winW,
          sy: winH,
          sz: 0.1,
          rotationY: face.rot,
          color: glass,
        });
      }
    }
    if (faceIndex === doorIdx) {
      pieces.push({
        kind: "door",
        x: face.px + face.nx * (out + 0.01),
        y: 1.12,
        z: face.pz + face.nz * (out + 0.01),
        sx: 1.18,
        sy: 2.2,
        sz: 0.12,
        rotationY: face.rot,
        color: doorColor,
      });
    }
  });
  return pieces;
}

export function countFacadePieces(buildings: WorldBuilding[]): {
  windows: number;
  doors: number;
  bands: number;
  total: number;
} {
  let windows = 0;
  let doors = 0;
  let bands = 0;
  for (const building of buildings) {
    for (const piece of facadePiecesForBuilding(building)) {
      if (piece.kind === "window") {
        windows += 1;
      } else if (piece.kind === "door") {
        doors += 1;
      } else if (piece.kind === "band") {
        bands += 1;
      }
    }
  }
  return { windows, doors, bands, total: windows + doors + bands };
}

export type GroundFloorFace = {
  buildingId: string;
  streetId: string;
  nx: number;
  nz: number;
  x: number;
  z: number;
  length: number;
  pieces: FacadePiece[];
};

export type GroundFloorCount = {
  buildings: number;
  faces: number;
  displays: number;
  storefronts: number;
  awnings: number;
  mainFaces: number;
  innerFaces: number;
};

function streetFaceBand(street: WorldStreet): { min: number; max: number } {
  if (isInnerStreet(street)) {
    const half = street.halfGapM > 0 ? street.halfGapM : INNER_LANE_WIDTH_M;
    return {
      min: Math.max(1.35, half - 1.15),
      max: Math.min(12, half + 2.4),
    };
  }
  return { min: STREET_FACE_MIN_M, max: STREET_FACE_MAX_M };
}

function asphaltOf(streets: WorldStreet[]): WorldStreet[] {
  return streets.filter((street) => street.surface === "asphalt");
}

/**
 * True when this AABB face actually fronts an asphalt polyline already
 * in the map (Harbor Walk, Tram Approach, or a carved inner lane).
 * Sidewalk setback only — alley backs and far lots stay plain boxes.
 */
export function faceFrontsAsphaltStreet(face: FaceSpec, streets: WorldStreet[]): string | null {
  const tangentX = face.nz !== 0 ? 1 : 0;
  const tangentZ = face.nx !== 0 ? 1 : 0;
  const spans = face.length >= 5 ? [-0.28, 0, 0.28] : [0];
  let bestId: string | null = null;
  let bestHits = 0;
  let bestDist = Infinity;
  for (const street of asphaltOf(streets)) {
    const band = streetFaceBand(street);
    let hits = 0;
    let hitDist = Infinity;
    for (const span of spans) {
      const sx = face.px + span * face.length * tangentX;
      const sz = face.pz + span * face.length * tangentZ;
      const near = nearestOnPolyline(street.points, sx, sz);
      if (!near) {
        continue;
      }
      const front = (near.x - sx) * face.nx + (near.z - sz) * face.nz;
      const align = Math.abs(near.dx * face.nx + near.dz * face.nz);
      if (front > STREET_FACE_FRONT && align < STREET_FACE_ALIGN && near.dist >= band.min && near.dist <= band.max) {
        hits += 1;
        hitDist = Math.min(hitDist, near.dist);
      }
    }
    const enough = hits >= (spans.length > 1 ? 2 : 1);
    if (enough && (hits > bestHits || (hits === bestHits && hitDist < bestDist))) {
      bestHits = hits;
      bestDist = hitDist;
      bestId = street.id;
    }
  }
  return bestId;
}

function storefrontPiecesOnFace(
  building: WorldBuilding,
  face: FaceSpec,
): FacadePiece[] {
  const pieces: FacadePiece[] = [];
  if (face.length < 2.6) {
    return pieces;
  }
  const idn = colorIndex(building.id);
  const tangentX = face.nz !== 0 ? 1 : 0;
  const tangentZ = face.nx !== 0 ? 1 : 0;
  const out = STOREFRONT_OUT_M;
  const side = idn % 2 === 0 ? -1 : 1;
  const doorW = Math.min(1.36, Math.max(1.02, face.length * 0.2));
  const half = face.length / 2 - 0.5;
  const doorAlong = side * Math.min(Math.max(0.7, half - doorW / 2), face.length * 0.32);
  pieces.push({
    kind: "storefront",
    x: face.px + face.nx * (out + 0.02) + doorAlong * tangentX,
    y: 1.08,
    z: face.pz + face.nz * (out + 0.02) + doorAlong * tangentZ,
    sx: doorW,
    sy: 2.12,
    sz: 0.14,
    rotationY: face.rot,
    color: STOREFRONT_DOOR_COLOR,
  });
  const doorLo = doorAlong - doorW / 2;
  const doorHi = doorAlong + doorW / 2;
  const panes: Array<{ along: number; w: number }> = [];
  const leftW = doorLo - 0.22 - -half;
  const rightW = half - (doorHi + 0.22);
  if (leftW >= 1.55) {
    panes.push({ along: -half + leftW / 2, w: leftW });
  }
  if (rightW >= 1.55) {
    panes.push({ along: doorHi + 0.22 + rightW / 2, w: rightW });
  }
  if (panes.length === 0 && face.length >= 4) {
    panes.push({
      along: -doorAlong * 0.35,
      w: Math.max(1.8, face.length * 0.48),
    });
  }
  for (const pane of panes) {
    pieces.push({
      kind: "display",
      x: face.px + face.nx * out + pane.along * tangentX,
      y: 1.42,
      z: face.pz + face.nz * out + pane.along * tangentZ,
      sx: pane.w,
      sy: 1.88,
      sz: 0.1,
      rotationY: face.rot,
      color: DISPLAY_GLASS_COLOR,
    });
  }
  if (face.length >= 3.4) {
    pieces.push({
      kind: "awning",
      x: face.px + face.nx * (out + AWNING_OUT_M / 2),
      y: AWNING_Y,
      z: face.pz + face.nz * (out + AWNING_OUT_M / 2),
      sx: face.length * 0.9,
      sy: AWNING_THICK_M,
      sz: AWNING_OUT_M,
      rotationY: face.rot,
      color: mixHex(building.wall, BUILDING_AWNING_MIX, 0.52),
    });
  }
  return pieces;
}

/**
 * Darker door slab + wider display glass + thin building awning on street
 * faces only. Cheap boxes. Not interiors, not listings, not shop kiosks.
 */
export function groundFloorFacesForBuilding(
  building: WorldBuilding,
  streets: WorldStreet[],
): GroundFloorFace[] {
  const out: GroundFloorFace[] = [];
  for (const face of facesOf(building)) {
    const streetId = faceFrontsAsphaltStreet(face, streets);
    if (!streetId) {
      continue;
    }
    const pieces = storefrontPiecesOnFace(building, face);
    if (pieces.length === 0) {
      continue;
    }
    out.push({
      buildingId: building.id,
      streetId,
      nx: face.nx,
      nz: face.nz,
      x: face.px,
      z: face.pz,
      length: face.length,
      pieces,
    });
  }
  return out;
}

export function groundFloorPiecesForBuilding(
  building: WorldBuilding,
  streets: WorldStreet[],
): FacadePiece[] {
  return groundFloorFacesForBuilding(building, streets).flatMap((face) => face.pieces);
}

export function farDetailVisible(
  playerX: number,
  playerZ: number,
  x: number,
  z: number,
  maxM = FAR_DETAIL_M,
): boolean {
  const dx = x - playerX;
  const dz = z - playerZ;
  return dx * dx + dz * dz <= maxM * maxM;
}

export function lodSamplePoint(x: number, z: number, cellM = FAR_DETAIL_CELL_M): { x: number; z: number } {
  return {
    x: Math.round(x / cellM) * cellM,
    z: Math.round(z / cellM) * cellM,
  };
}

/** Harbor / Tram faces stay. Inner door+glass+awning only inside FAR_DETAIL_M. */
export function shouldDrawGroundFloorFace(
  face: Pick<GroundFloorFace, "streetId" | "x" | "z">,
  playerX: number,
  playerZ: number,
): boolean {
  if (!isInnerStreetId(face.streetId)) {
    return true;
  }
  return farDetailVisible(playerX, playerZ, face.x, face.z);
}

export function shouldDrawScooter(
  scooter: { x: number; z: number },
  playerX: number,
  playerZ: number,
): boolean {
  return farDetailVisible(playerX, playerZ, scooter.x, scooter.z);
}

/** Drei Html labels only inside FAR_DETAIL_M. Meshes stay. First-W leftover. */
export const PLAY_HTML_LOD_KIND = "far-html" as const;

export function shouldDrawPlayHtml(
  x: number,
  z: number,
  playerX: number,
  playerZ: number,
): boolean {
  return farDetailVisible(playerX, playerZ, x, z);
}

export function countGroundFloorPieces(
  buildings: WorldBuilding[],
  streets: WorldStreet[],
): GroundFloorCount {
  const seen = new Set<string>();
  let faces = 0;
  let displays = 0;
  let storefronts = 0;
  let awnings = 0;
  let mainFaces = 0;
  let innerFaces = 0;
  for (const building of buildings) {
    const rows = groundFloorFacesForBuilding(building, streets);
    if (rows.length > 0) {
      seen.add(building.id);
    }
    faces += rows.length;
    for (const row of rows) {
      if (isInnerStreetId(row.streetId)) {
        innerFaces += 1;
      } else {
        mainFaces += 1;
      }
      for (const piece of row.pieces) {
        if (piece.kind === "display") {
          displays += 1;
        } else if (piece.kind === "storefront") {
          storefronts += 1;
        } else if (piece.kind === "awning") {
          awnings += 1;
        }
      }
    }
  }
  return { buildings: seen.size, faces, displays, storefronts, awnings, mainFaces, innerFaces };
}

/** Cheap roof language — parapet + hashed AC/tank. Visual only, not walkable. */
export const ROOF_KIND = "parapet-ac-tank" as const;
export const ROOF_LID_H_M = 0.28;
export const PARAPET_H_M = 0.72;
export const PARAPET_T_M = 0.34;
export const AC_COLOR = "#9aa4ae";
export const TANK_COLOR = "#c4b89a";

export type RoofKind = "parapet" | "ac" | "tank";

export type RoofPiece = {
  kind: RoofKind;
  x: number;
  y: number;
  z: number;
  sx: number;
  sy: number;
  sz: number;
  rotationY: number;
  color: string;
};

export type RoofCount = {
  buildings: number;
  parapets: number;
  acs: number;
  tanks: number;
};

function closedWorldRing(points: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const pt of points) {
    if (!pt) {
      continue;
    }
    const prev = out[out.length - 1];
    if (prev && Math.abs(prev[0] - pt[0]) < 1e-6 && Math.abs(prev[1] - pt[1]) < 1e-6) {
      continue;
    }
    out.push(pt);
  }
  if (out.length >= 2) {
    const first = out[0];
    const last = out[out.length - 1];
    if (
      first &&
      last &&
      Math.abs(first[0] - last[0]) < 1e-6 &&
      Math.abs(first[1] - last[1]) < 1e-6
    ) {
      out.pop();
    }
  }
  return out;
}

/** 0 / 1 / 2 units from the building id. Stable across reloads. */
export function roofUnitsForId(id: string): { ac: number; tank: number } {
  const n = colorIndex(id);
  if (n % 3 === 0) {
    return { ac: 0, tank: 0 };
  }
  if (n % 5 === 0) {
    return { ac: 1, tank: 1 };
  }
  if (n % 2 === 0) {
    return { ac: 2, tank: 0 };
  }
  return { ac: 1, tank: 0 };
}

/**
 * Thin parapet around the extruded ring plus 1–2 AC/tank boxes on a hashed
 * subset. Still boxes. Not interiors, not a walkable roof, not photogrammetry.
 */
export function roofPiecesForBuilding(building: WorldBuilding): RoofPiece[] {
  const pieces: RoofPiece[] = [];
  const ring = closedWorldRing(building.points);
  const lid = building.roof;
  const parapet = mixHex(lid, "#d8cfc4", 0.38);
  const y0 = building.height_m + ROOF_LID_H_M;
  for (let i = 0; i < ring.length; i += 1) {
    const a = ring[i];
    const b = ring[(i + 1) % ring.length];
    if (!a || !b) {
      continue;
    }
    const dx = b[0] - a[0];
    const dz = b[1] - a[1];
    const length = Math.hypot(dx, dz);
    if (length < 0.35) {
      continue;
    }
    const mx = (a[0] + b[0]) / 2;
    const mz = (a[1] + b[1]) / 2;
    const nx = -dz / length;
    const nz = dx / length;
    const inward = (building.cx - mx) * nx + (building.cz - mz) * nz >= 0 ? 1 : -1;
    const inset = PARAPET_T_M * 0.45;
    pieces.push({
      kind: "parapet",
      x: mx + nx * inward * inset,
      y: y0 + PARAPET_H_M / 2,
      z: mz + nz * inward * inset,
      sx: PARAPET_T_M,
      sy: PARAPET_H_M,
      sz: length,
      rotationY: Math.atan2(dx, dz),
      color: parapet,
    });
  }
  const units = roofUnitsForId(building.id);
  const idn = colorIndex(building.id);
  const halfW = Math.max(0.8, building.width * 0.22);
  const halfD = Math.max(0.8, building.depth * 0.22);
  let slot = 0;
  const place = (kind: "ac" | "tank", sx: number, sy: number, sz: number, color: string) => {
    const ox = (((idn + slot * 13) % 7) - 3) * (halfW / 3);
    const oz = (((idn + slot * 17) % 7) - 3) * (halfD / 3);
    slot += 1;
    pieces.push({
      kind,
      x: building.cx + ox,
      y: y0 + sy / 2,
      z: building.cz + oz,
      sx,
      sy,
      sz,
      rotationY: ((idn + slot) % 2) * (Math.PI / 2) * 0.12,
      color,
    });
  };
  for (let i = 0; i < units.ac; i += 1) {
    place("ac", 1.72, 1.38, 1.22, AC_COLOR);
  }
  for (let i = 0; i < units.tank; i += 1) {
    place("tank", 1.12, 1.62, 1.12, TANK_COLOR);
  }
  return pieces;
}

export function countRoofPieces(buildings: WorldBuilding[]): RoofCount {
  let parapets = 0;
  let acs = 0;
  let tanks = 0;
  let withRoof = 0;
  for (const building of buildings) {
    const rows = roofPiecesForBuilding(building);
    if (rows.length > 0) {
      withRoof += 1;
    }
    for (const row of rows) {
      if (row.kind === "parapet") {
        parapets += 1;
      } else if (row.kind === "ac") {
        acs += 1;
      } else if (row.kind === "tank") {
        tanks += 1;
      }
    }
  }
  return { buildings: withRoof, parapets, acs, tanks };
}

export type ShopSignSpec = {
  shop_id: string;
  name: string;
  x: number;
  z: number;
  poleH: number;
  boardY: number;
  boardW: number;
  boardH: number;
  yaw: number;
  eHint: "E";
  kind: "pole-board";
  draw: boolean;
  laneM: number;
};

export function inSpawnKeepOutXZ(x: number, z: number): boolean {
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  return Math.hypot(spawn.x - x, spawn.z - z) <= SPAWN_KEEP_OUT_M;
}

/** Sign or stall inside the spawn cone. Persist can stay; do not draw. */
export function shopInSpawnKeepOut(shop: { lon: number; lat: number }): boolean {
  const sign = lngLatToWorld(shop.lon, shop.lat);
  return (
    inSpawnKeepOut(shop.lon, shop.lat) ||
    inSpawnKeepOutXZ(sign.x, sign.z) ||
    inSpawnKeepOutXZ(sign.x, sign.z + STALL_BODY_BACK_M)
  );
}

/** 3D pole + painted board at the drawn stall plant. Faces the street both ways. */
export function shopSignSpec(
  shop: {
    shop_id: string;
    name: string;
    lon: number;
    lat: number;
  },
  streets: readonly WorldStreet[] = [],
): ShopSignSpec {
  const stall = shopStallSpec(shop, streets);
  return {
    shop_id: shop.shop_id,
    name: shop.name,
    x: stall.x,
    z: stall.z,
    poleH: 4.05,
    boardY: 3.52,
    boardW: 3.55,
    boardH: 1.22,
    yaw: stall.yaw,
    eHint: "E",
    kind: "pole-board",
    draw: stall.draw,
    laneM: stall.laneM,
  };
}

export type ShopStallSpec = {
  shop_id: string;
  name: string;
  x: number;
  z: number;
  signX: number;
  signZ: number;
  yaw: number;
  awning: string;
  stripe: string;
  body: string;
  counter: string;
  post: string;
  awningW: number;
  awningH: number;
  awningD: number;
  awningY: number;
  collide: boolean;
  collideHalfX: number;
  collideHalfZ: number;
  draw: boolean;
  laneM: number;
  streetId: string | null;
  kind: typeof SHOP_STALL_KIND;
};

/** Saturated canopy from shop id + name. Not photogrammetry. */
export function stallColorForShop(shop: { shop_id: string; name: string }): string {
  const key = `${shop.shop_id}\0${shop.name}`;
  return AWNING_COLORS[colorIndex(key) % AWNING_COLORS.length] ?? "#1e8a7c";
}

/** Muted body tint from scooter id. Not a brand livery. */
export function scooterColorForId(id: string): string {
  return SCOOTER_COLORS[colorIndex(id) % SCOOTER_COLORS.length] ?? "#3d3f44";
}

function keepHashedScooter(id: string): boolean {
  return colorIndex(id) % 7 < 2;
}

/** Harbor Walk + Tram Approach only. Not inner lanes. Not a fifth street. */
export function officialStallWays(streets: readonly WorldStreet[]): WorldStreet[] {
  return streets.filter((street) => (ASPHALT_STREET_IDS as readonly string[]).includes(street.id));
}

/**
 * Persist lon/lat stay. Mesh + collide hug the nearest official sidewalk
 * when the persist plant sits on the driving lane. Already-off-lane plants
 * keep their persist pose (lantern). No street match keeps persist+back.
 */
export function stallSidewalkPlant(
  signX: number,
  signZ: number,
  streets: readonly WorldStreet[],
): { x: number; z: number; yaw: number; laneM: number; streetId: string | null } {
  const plantedX = signX;
  const plantedZ = signZ + STALL_BODY_BACK_M;
  const yaw = Math.PI;
  let best: {
    streetId: string;
    x: number;
    z: number;
    dx: number;
    dz: number;
    dist: number;
  } | null = null;
  for (const street of officialStallWays(streets)) {
    const hit = nearestOnPolyline(street.points, plantedX, plantedZ);
    if (!hit) {
      continue;
    }
    if (!best || hit.dist < best.dist) {
      best = { streetId: street.id, ...hit };
    }
  }
  if (!best || best.dist > WALK_WIDTH_M + 2) {
    return { x: plantedX, z: plantedZ, yaw, laneM: best?.dist ?? 0, streetId: best?.streetId ?? null };
  }
  if (best.dist >= STALL_OFF_LANE_M) {
    return { x: plantedX, z: plantedZ, yaw, laneM: best.dist, streetId: best.streetId };
  }
  const rot = Math.atan2(best.dx, best.dz);
  const signed = (plantedX - best.x) * Math.cos(rot) + (plantedZ - best.z) * -Math.sin(rot);
  const side: 1 | -1 = signed < 0 ? -1 : 1;
  const placed = offsetSide(best.x, best.z, best.dx, best.dz, side, STALL_SIDEWALK_ACROSS_M);
  return {
    x: placed.x,
    z: placed.z,
    yaw,
    laneM: STALL_SIDEWALK_ACROSS_M,
    streetId: best.streetId,
  };
}

/**
 * Awning + shallow kiosk. Pole-board, mesh, collide, and street E
 * share this sidewalk plant. Collision is the counter/kiosk
 * footprint only. Not an interior. Persist lon/lat stay; drawn pose
 * sits on the nearest Harbor/Tram sidewalk (~7 m across) so a local
 * stall is not on the asphalt centerline. Spawn keep-out hides
 * leftover mesh + collision. Catalog persist stays.
 */
export function shopStallSpec(
  shop: {
    shop_id: string;
    name: string;
    lon: number;
    lat: number;
  },
  streets: readonly WorldStreet[] = [],
): ShopStallSpec {
  const persist = lngLatToWorld(shop.lon, shop.lat);
  const plant = stallSidewalkPlant(persist.x, persist.z, streets);
  const awning = stallColorForShop(shop);
  const draw = !shopInSpawnKeepOut(shop);
  return {
    shop_id: shop.shop_id,
    name: shop.name,
    x: plant.x,
    z: plant.z,
    signX: plant.x,
    signZ: plant.z,
    yaw: plant.yaw,
    awning,
    stripe: mixHex(awning, "#fff3c4", 0.35),
    body: mixHex(awning, "#e6d2b0", 0.55),
    counter: STALL_COUNTER_COLOR,
    post: STALL_POST_COLOR,
    awningW: STALL_AWNING_W,
    awningH: STALL_AWNING_H,
    awningD: STALL_AWNING_D,
    awningY: STALL_AWNING_Y,
    collide: draw,
    collideHalfX: STALL_COLLIDE_HALF_X,
    collideHalfZ: STALL_COLLIDE_HALF_Z,
    draw,
    laneM: plant.laneM,
    streetId: plant.streetId,
    kind: SHOP_STALL_KIND,
  };
}

/** Drawn stall plant as lon/lat. Nearby/E use this. New create persist writes this plant. Existing catalog persist stays. */
export function shopPlayLngLat(
  shop: {
    shop_id: string;
    name: string;
    lon: number;
    lat: number;
  },
  streets: readonly WorldStreet[] = [],
): { lon: number; lat: number } {
  const stall = shopStallSpec(shop, streets);
  return worldToLngLat(stall.x, stall.z);
}

export type MinimapStreetShopMark = {
  shop_id: string;
  name: string;
  lon: number;
  lat: number;
  persistLon: number;
  persistLat: number;
  draw: true;
  keepOut: false;
};

/**
 * Corner-minimap dots. Street-play published stalls only (draw=1).
 * Lon/lat is the sidewalk plant, not on-lane persist. Spawn keep-out
 * leftovers (Shared PC / J6) stay off the 2D map.
 */
export function minimapStreetShopMarks(
  shops: readonly {
    shop_id: string;
    name: string;
    lon: number;
    lat: number;
    status?: string;
  }[],
  streets: readonly WorldStreet[] = [],
): MinimapStreetShopMark[] {
  const out: MinimapStreetShopMark[] = [];
  for (const shop of shops) {
    if (shop.status && shop.status !== "published") {
      continue;
    }
    if (!isStreetPlayShop(shop)) {
      continue;
    }
    const stall = shopStallSpec(shop, streets);
    if (!stall.draw) {
      continue;
    }
    const plant = shopPlayLngLat(shop, streets);
    out.push({
      shop_id: shop.shop_id,
      name: shop.name,
      lon: plant.lon,
      lat: plant.lat,
      persistLon: shop.lon,
      persistLat: shop.lat,
      draw: true,
      keepOut: false,
    });
  }
  return out;
}

/**
 * Persist lon/lat for a newly published player shop.
 * Same sidewalk plant as the drawn stall. Does not rewrite existing rows.
 */
export function persistSidewalkLngLat(
  lon: number,
  lat: number,
  streets: readonly WorldStreet[],
): { lon: number; lat: number } {
  if (!streets.length) {
    return { lon, lat };
  }
  return shopPlayLngLat(
    { shop_id: "shop-local-persist-plant", name: "persist-plant", lon, lat },
    streets,
  );
}

function solidFromWorldRect(
  id: string,
  x: number,
  z: number,
  halfX: number,
  halfZ: number,
): BuildingPoly {
  const { lon, lat } = worldToLngLat(x, z);
  const dLon = halfX / metersPerDegLon(lat);
  const dLat = halfZ / M_PER_DEG_LAT;
  const aabb = {
    west: lon - dLon,
    east: lon + dLon,
    south: lat - dLat,
    north: lat + dLat,
  };
  return {
    id,
    name: id,
    height_m: 2.2,
    ring: [
      [aabb.west, aabb.south],
      [aabb.east, aabb.south],
      [aabb.east, aabb.north],
      [aabb.west, aabb.north],
      [aabb.west, aabb.south],
    ],
    aabb,
  };
}

export function shopStallSolid(spec: ShopStallSpec): BuildingPoly | null {
  if (!spec.draw || !spec.collide) {
    return null;
  }
  return solidFromWorldRect(
    `stall-${spec.shop_id}`,
    spec.x,
    spec.z,
    spec.collideHalfX,
    spec.collideHalfZ,
  );
}

export function shopStallSolids(
  shops: Array<{ shop_id: string; name: string; lon: number; lat: number }>,
  streets: readonly WorldStreet[] = [],
): BuildingPoly[] {
  const out: BuildingPoly[] = [];
  for (const shop of shops) {
    const solid = shopStallSolid(shopStallSpec(shop, streets));
    if (solid) {
      out.push(solid);
    }
  }
  return out;
}

/** Footprint rings plus stall boxes. Skip lamps / planters / scooters / spill. */
export function cameraHitSolids(
  buildings: BuildingPoly[],
  shops: Array<{ shop_id: string; name: string; lon: number; lat: number }>,
  streets: readonly WorldStreet[] = [],
): BuildingPoly[] {
  const stalls = shopStallSolids(shops, streets);
  return stalls.length === 0 ? buildings : buildings.concat(stalls);
}

export type MarketSpillKind = "crate" | "basket" | "stack" | "cooler";

export type MarketSpillPiece = {
  id: string;
  x: number;
  z: number;
  yaw: number;
  kind: MarketSpillKind;
  color: string;
  accent: string;
  shop_id: string | null;
  source: "shop" | "street";
  collide: boolean;
};

/** Fish stall reads cooler/teal + crate wood. Others hash from id/name. */
export function isFishStallShop(shop: { shop_id: string; name: string }): boolean {
  const key = `${shop.shop_id} ${shop.name}`.toLowerCase();
  return /lantern|fish|cá|ca\s/.test(key);
}

export function spillPaletteForShop(shop: { shop_id: string; name: string }): {
  crate: string;
  cooler: string;
  basket: string;
  accent: string;
} {
  if (isFishStallShop(shop)) {
    return {
      crate: CRATE_WOOD,
      cooler: COOLER_TEAL,
      basket: BASKET_RIM,
      accent: COOLER_LID,
    };
  }
  const hashed =
    SPILL_HASH_CRATES[colorIndex(`${shop.shop_id}\0${shop.name}`) % SPILL_HASH_CRATES.length] ??
    CRATE_WOOD;
  const awning = stallColorForShop(shop);
  return {
    crate: hashed,
    cooler: mixHex(awning, "#3a5c58", 0.45),
    basket: mixHex(hashed, "#d2b48c", 0.35),
    accent: mixHex(hashed, "#fff3c4", 0.2),
  };
}

/**
 * Authored crates / bowls / stacks beside a kiosk. Not catalog listings.
 * Sits east/west of the counter so the south E approach stays open.
 */
export function shopMarketSpill(
  shop: { shop_id: string; name: string; lon: number; lat: number },
  streets: readonly WorldStreet[] = [],
): MarketSpillPiece[] {
  const stall = shopStallSpec(shop, streets);
  if (!stall.draw) {
    return [];
  }
  const palette = spillPaletteForShop(shop);
  const fish = isFishStallShop(shop);
  const westX = stall.x - 1.72;
  const eastX = stall.x + 1.72;
  const sideZ = stall.z + 0.55;
  const collide =
    stall.collide &&
    !inSpawnKeepOutXZ(westX, sideZ) &&
    !inSpawnKeepOutXZ(eastX, sideZ);
  const pieces: MarketSpillPiece[] = [];
  if (fish) {
    pieces.push({
      id: `spill-${shop.shop_id}-cooler`,
      x: westX,
      z: sideZ,
      yaw: 0.08,
      kind: "cooler",
      color: palette.cooler,
      accent: palette.accent,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
    pieces.push({
      id: `spill-${shop.shop_id}-crate-w`,
      x: westX - 0.62,
      z: sideZ + 0.18,
      yaw: -0.12,
      kind: "crate",
      color: palette.crate,
      accent: CRATE_WOOD_DARK,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
    pieces.push({
      id: `spill-${shop.shop_id}-basket`,
      x: eastX,
      z: sideZ - 0.08,
      yaw: 0.2,
      kind: "basket",
      color: palette.basket,
      accent: BASKET_IN,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
    pieces.push({
      id: `spill-${shop.shop_id}-stack-e`,
      x: eastX + 0.58,
      z: sideZ + 0.22,
      yaw: 0.15,
      kind: "stack",
      color: palette.crate,
      accent: CRATE_WOOD_DARK,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
  } else {
    pieces.push({
      id: `spill-${shop.shop_id}-crate-w`,
      x: westX,
      z: sideZ,
      yaw: -0.1,
      kind: "crate",
      color: palette.crate,
      accent: CRATE_WOOD_DARK,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
    pieces.push({
      id: `spill-${shop.shop_id}-basket`,
      x: westX + 0.55,
      z: sideZ + 0.28,
      yaw: 0.18,
      kind: "basket",
      color: palette.basket,
      accent: palette.accent,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
    pieces.push({
      id: `spill-${shop.shop_id}-stack-e`,
      x: eastX,
      z: sideZ + 0.1,
      yaw: 0.12,
      kind: "stack",
      color: palette.crate,
      accent: CRATE_WOOD_DARK,
      shop_id: shop.shop_id,
      source: "shop",
      collide,
    });
  }
  return pieces.filter((piece) => !inSpawnKeepOutXZ(piece.x, piece.z));
}

function streetSpillBlocked(
  x: number,
  z: number,
  props: StreetProps,
  peers: MarketSpillPiece[],
): boolean {
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  if (Math.hypot(x, z) > SLAB_SIZE_M / 2 - 8) {
    return true;
  }
  if (Math.hypot(x - spawn.x, z - spawn.z) < SPILL_SKIP_SPAWN_M) {
    return true;
  }
  if (Math.hypot(x - shop.x, z - shop.z) < SPILL_SKIP_LANTERN_M) {
    return true;
  }
  if (Math.hypot(x, z) < SCOOTER_SKIP_CROSSING_M) {
    return true;
  }
  if (nearAnyCrosswalk(x, z, props.crosswalks, SPILL_SKIP_ZEBRA_M)) {
    return true;
  }
  if (props.lamps.some((lamp) => Math.hypot(lamp.x - x, lamp.z - z) < 1.6)) {
    return true;
  }
  if (props.planters.some((row) => Math.hypot(row.x - x, row.z - z) < SPILL_SKIP_PLANTER_M)) {
    return true;
  }
  if (props.scooters.some((row) => Math.hypot(row.x - x, row.z - z) < SPILL_SKIP_SCOOTER_M)) {
    return true;
  }
  if (peers.some((row) => Math.hypot(row.x - x, row.z - z) < SPILL_SKIP_PEER_M)) {
    return true;
  }
  return false;
}

/**
 * 2–4 extra crate stacks on Harbor Walk sidewalk near lamps.
 * Off the driving lane / zebra / lantern 10 m E path / scooter slots.
 */
export function streetMarketSpill(streets: WorldStreet[], props: StreetProps): MarketSpillPiece[] {
  const harbor = streets.find((street) => street.id === "street-harbor-walk");
  if (!harbor) {
    return [];
  }
  const out: MarketSpillPiece[] = [];
  const tryPlace = (id: string, x: number, z: number, yaw: number): void => {
    if (out.length >= 4) {
      return;
    }
    if (streetSpillBlocked(x, z, props, out)) {
      return;
    }
    const tint = SPILL_HASH_CRATES[colorIndex(id) % SPILL_HASH_CRATES.length] ?? CRATE_WOOD;
    out.push({
      id,
      x,
      z,
      yaw,
      kind: "stack",
      color: tint,
      accent: CRATE_WOOD_DARK,
      shop_id: null,
      source: "street",
      collide: true,
    });
  };

  const authored: Array<{ id: string; along: number; side: 1 | -1 }> = [
    { id: "spill-harbor-walk-e", along: 0.268, side: 1 },
    { id: "spill-harbor-mid-w", along: 0.408, side: -1 },
    { id: "spill-harbor-north-e", along: 0.512, side: 1 },
    { id: "spill-harbor-far-w", along: 0.575, side: -1 },
  ];
  const total = polylineLength(harbor.points);
  for (const spec of authored) {
    const at = pointAtDistance(harbor.points, spec.along * total);
    if (!at) {
      continue;
    }
    const placed = offsetSide(at.x, at.z, at.dx, at.dz, spec.side, SPILL_STREET_ACROSS_M);
    tryPlace(spec.id, placed.x, placed.z, placed.yaw + 0.08);
  }

  if (out.length < 2) {
    for (const lamp of props.lamps.filter((row) => row.streetId === "street-harbor-walk")) {
      const at = nearestOnPolyline(harbor.points, lamp.x, lamp.z);
      if (!at) {
        continue;
      }
      const side: 1 | -1 = lamp.x >= at.x ? 1 : -1;
      const placed = offsetSide(at.x, at.z, at.dx, at.dz, side, SPILL_STREET_ACROSS_M);
      tryPlace(`spill-street-${lamp.id}`, placed.x, placed.z, placed.yaw);
    }
  }
  return out;
}

export function marketSpillForPlay(
  streets: WorldStreet[],
  shops: Array<{ shop_id: string; name: string; lon: number; lat: number }>,
  props: StreetProps,
): MarketSpillPiece[] {
  return [...shops.flatMap((shop) => shopMarketSpill(shop, streets)), ...streetMarketSpill(streets, props)];
}

export function marketSpillFromCollection(
  data: FeatureCollection,
  shops: Array<{ shop_id: string; name: string; lon: number; lat: number }>,
): MarketSpillPiece[] {
  const streets = worldFromCollection(data).streets;
  const buildings = buildingsToWorld(buildingsFromCollection(data));
  return marketSpillForPlay(streets, shops, streetPropsFromStreets(streets, buildings));
}

export function marketSpillSolids(pieces: MarketSpillPiece[]): BuildingPoly[] {
  return pieces
    .filter((piece) => piece.collide)
    .map((piece) => solidFromWorld(piece.id, piece.x, piece.z, SPILL_COLLIDE_HALF_M));
}

export function countMarketSpill(pieces: MarketSpillPiece[]): {
  total: number;
  shop: number;
  street: number;
  crates: number;
  baskets: number;
  stacks: number;
  coolers: number;
} {
  return {
    total: pieces.length,
    shop: pieces.filter((row) => row.source === "shop").length,
    street: pieces.filter((row) => row.source === "street").length,
    crates: pieces.filter((row) => row.kind === "crate").length,
    baskets: pieces.filter((row) => row.kind === "basket").length,
    stacks: pieces.filter((row) => row.kind === "stack").length,
    coolers: pieces.filter((row) => row.kind === "cooler").length,
  };
}

export function skyStops(): { t: number; hex: string }[] {
  return [
    { t: 0, hex: SKY_ZENITH },
    { t: 0.58, hex: SKY_MID },
    { t: 0.82, hex: SKY_HORIZON },
    { t: 1, hex: SKY_GROUND_HAZE },
  ];
}

export function followPitchDeg(lookMode: string, lookPitch: number): number {
  return lookMode !== "off" || Math.abs(lookPitch) > 0.4 ? lookPitch : PLAY_DEFAULT_PITCH_DEG;
}

/** True when a hex is the old beige/gray void, not a blue zenith. */
export function isBeigeOrGrayVoid(hex: string): boolean {
  const [r, g, b] = parseHex(hex);
  const spread = Math.max(r, g, b) - Math.min(r, g, b);
  const beige = r > 170 && g > 140 && b < 180 && r - b > 20;
  const gray = spread < 22 && r > 95 && r < 210 && g > 95 && g < 210 && b > 95 && b < 210;
  return beige || gray;
}

function buildingBox(building: WorldBuilding): {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
} {
  return {
    minX: building.cx - building.width / 2,
    maxX: building.cx + building.width / 2,
    minZ: building.cz - building.depth / 2,
    maxZ: building.cz + building.depth / 2,
  };
}

function innerGapOk(gap: number): boolean {
  return gap >= INNER_LANE_GAP_MIN_M && gap <= INNER_LINK_GAP_MAX_M;
}

function innerWidthForGap(gap: number): number {
  if (gap <= INNER_LANE_GAP_MAX_M) {
    return INNER_LANE_WIDTH_M;
  }
  return Math.min(INNER_LINK_WIDTH_MAX_M, Math.max(INNER_LANE_WIDTH_M, gap * 0.42));
}

type InnerDraft = {
  axis: "x" | "z";
  pos: number;
  a: number;
  b: number;
  gap: number;
};

function axisKey(value: number): string {
  return `${value < 0 ? "n" : "p"}${Math.abs(Math.round(value))}`;
}

function innerStreetId(axis: "x" | "z", pos: number, alongMid: number): string {
  const dir = axis === "x" ? "ns" : "ew";
  return `${INNER_STREET_PREFIX}${dir}-${axisKey(pos)}-${axisKey(alongMid)}`;
}

function mergeInnerDrafts(drafts: InnerDraft[]): WorldStreet[] {
  const groups = new Map<string, InnerDraft[]>();
  for (const draft of drafts) {
    const q = Math.round(draft.pos / 0.8) * 0.8;
    const key = `${draft.axis}:${q}`;
    const list = groups.get(key);
    if (list) {
      list.push(draft);
    } else {
      groups.set(key, [draft]);
    }
  }
  const out: WorldStreet[] = [];
  for (const group of groups.values()) {
    group.sort((a, b) => a.a - b.a);
    let cur = group[0];
    if (!cur) {
      continue;
    }
    const flush = (row: InnerDraft) => {
      const len = row.b - row.a;
      if (len < INNER_MIN_OVERLAP_M) {
        return;
      }
      const half = row.gap / 2;
      const points: [number, number][] =
        row.axis === "x"
          ? [
              [row.pos, row.a],
              [row.pos, row.b],
            ]
          : [
              [row.a, row.pos],
              [row.b, row.pos],
            ];
      out.push({
        id: innerStreetId(row.axis, row.pos, (row.a + row.b) / 2),
        name: "Inner Lane",
        points,
        surface: "asphalt",
        lane: "inner",
        widthM: innerWidthForGap(row.gap),
        halfGapM: half,
      });
    };
    for (let i = 1; i < group.length; i += 1) {
      const next = group[i];
      if (!next) {
        continue;
      }
      if (next.a <= cur.b + 8.2) {
        cur = {
          axis: cur.axis,
          pos: (cur.pos * (cur.b - cur.a) + next.pos * (next.b - next.a)) / Math.max(0.2, cur.b - cur.a + next.b - next.a),
          a: Math.min(cur.a, next.a),
          b: Math.max(cur.b, next.b),
          gap: (cur.gap + next.gap) / 2,
        };
      } else {
        flush(cur);
        cur = next;
      }
    }
    flush(cur);
  }
  return out;
}

/**
 * Centerlines down existing parcel gaps in the 400 m fixture.
 * Not new downtown. Not OSM. Alley backs without a facing partner stay plain.
 */
export function innerStreetsFromBuildings(buildings: WorldBuilding[]): WorldStreet[] {
  const drafts: InnerDraft[] = [];
  for (let i = 0; i < buildings.length; i += 1) {
    const A = buildings[i];
    if (!A) {
      continue;
    }
    const a = buildingBox(A);
    for (let j = i + 1; j < buildings.length; j += 1) {
      const B = buildings[j];
      if (!B) {
        continue;
      }
      const b = buildingBox(B);
      if (a.maxX < b.minX) {
        const gap = b.minX - a.maxX;
        const overlap = Math.min(a.maxZ, b.maxZ) - Math.max(a.minZ, b.minZ);
        if (innerGapOk(gap) && overlap >= INNER_MIN_OVERLAP_M) {
          drafts.push({
            axis: "x",
            pos: (a.maxX + b.minX) / 2,
            a: Math.max(a.minZ, b.minZ),
            b: Math.min(a.maxZ, b.maxZ),
            gap,
          });
        }
      } else if (b.maxX < a.minX) {
        const gap = a.minX - b.maxX;
        const overlap = Math.min(a.maxZ, b.maxZ) - Math.max(a.minZ, b.minZ);
        if (innerGapOk(gap) && overlap >= INNER_MIN_OVERLAP_M) {
          drafts.push({
            axis: "x",
            pos: (b.maxX + a.minX) / 2,
            a: Math.max(a.minZ, b.minZ),
            b: Math.min(a.maxZ, b.maxZ),
            gap,
          });
        }
      }
      if (a.maxZ < b.minZ) {
        const gap = b.minZ - a.maxZ;
        const overlap = Math.min(a.maxX, b.maxX) - Math.max(a.minX, b.minX);
        if (innerGapOk(gap) && overlap >= INNER_MIN_OVERLAP_M) {
          drafts.push({
            axis: "z",
            pos: (a.maxZ + b.minZ) / 2,
            a: Math.max(a.minX, b.minX),
            b: Math.min(a.maxX, b.maxX),
            gap,
          });
        }
      } else if (b.maxZ < a.minZ) {
        const gap = a.minZ - b.maxZ;
        const overlap = Math.min(a.maxX, b.maxX) - Math.max(a.minX, b.minX);
        if (innerGapOk(gap) && overlap >= INNER_MIN_OVERLAP_M) {
          drafts.push({
            axis: "z",
            pos: (b.maxZ + a.minZ) / 2,
            a: Math.max(a.minX, b.minX),
            b: Math.min(a.maxX, b.maxX),
            gap,
          });
        }
      }
    }
  }
  return mergeInnerDrafts(drafts);
}

export function worldFromCollection(data: FeatureCollection): {
  streets: WorldStreet[];
  parks: WorldPark[];
  places: WorldPlaceMark[];
} {
  const streets: WorldStreet[] = [];
  const parks: WorldPark[] = [];
  const places: WorldPlaceMark[] = [];
  for (const feature of data.features) {
    const kind = feature.properties?.kind;
    const id = String(feature.properties?.id ?? feature.id ?? kind ?? "feat");
    const name = feature.properties?.display_name ?? feature.properties?.name ?? id;
    if (kind === "street" && feature.geometry.type === "LineString") {
      const line = readLine(feature.geometry.coordinates);
      if (line.length >= 2) {
        streets.push({
          id,
          name,
          points: ringToPoints(line),
          surface: isAsphaltStreet(id, name) ? "asphalt" : "walk",
          lane: "main",
          widthM: STREET_WIDTH_M,
          halfGapM: STREET_WIDTH_M / 2 + 4,
        });
      }
    }
    if (kind === "park" && feature.geometry.type === "Polygon") {
      const ring = readRing(feature.geometry.coordinates);
      if (ring.length >= 4) {
        parks.push({ id, name, points: ringToPoints(ring) });
      }
    }
    if (kind === "place" && feature.geometry.type === "Point") {
      const coords = feature.geometry.coordinates;
      if (Array.isArray(coords) && typeof coords[0] === "number" && typeof coords[1] === "number") {
        const p = lngLatToWorld(coords[0], coords[1]);
        places.push({ id, name, x: p.x, z: p.z });
      }
    }
  }
  const inner = innerStreetsFromBuildings(buildingsToWorld(buildingsFromCollection(data)));
  const seen = new Set(streets.map((street) => street.id));
  for (const street of inner) {
    if (!seen.has(street.id)) {
      streets.push(street);
      seen.add(street.id);
    }
  }
  return { streets, parks, places };
}

export function walkSegments(points: [number, number][]): StreetSegment[] {
  return streetSegments(points, WALK_WIDTH_M);
}

/** Harbor-width sidewalks stay on named streets. Inner lanes use a gap-clamped band. */
export function innerWalkSegments(street: WorldStreet): StreetSegment[] {
  return streetSegments(street.points, innerWalkWidth(street));
}

function offsetAcross(seg: StreetSegment, across: number, width: number): StreetSegment[] {
  const cos = Math.cos(seg.rotationY);
  const sin = Math.sin(seg.rotationY);
  return [
    {
      x: seg.x + cos * across,
      z: seg.z - sin * across,
      length: seg.length,
      width,
      rotationY: seg.rotationY,
    },
    {
      x: seg.x - cos * across,
      z: seg.z + sin * across,
      length: seg.length,
      width,
      rotationY: seg.rotationY,
    },
  ];
}

/** Cheap raised lip at the asphalt edge. Still authored boxes. */
export function curbSegments(points: [number, number][]): StreetSegment[] {
  return streetSegments(points, STREET_WIDTH_M).flatMap((seg) =>
    offsetAcross(seg, STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2, CURB_WIDTH_M),
  );
}

/** Painted road-edge line on Harbor Walk / Tram Approach. */
export function edgeStripSegments(points: [number, number][]): StreetSegment[] {
  return streetSegments(points, STREET_WIDTH_M).flatMap((seg) =>
    offsetAcross(seg, STREET_WIDTH_M / 2 - EDGE_WIDTH_M / 2, EDGE_WIDTH_M),
  );
}

/** Thin painted edge on a derived inner ribbon. Same yellow, street-local width. */
export function innerEdgeStripSegments(street: WorldStreet): StreetSegment[] {
  const width = streetRoadWidth(street);
  return streetSegments(street.points, width).flatMap((seg) =>
    offsetAcross(seg, width / 2 - EDGE_WIDTH_M / 2, EDGE_WIDTH_M),
  );
}

export function countInnerLanes(streets: WorldStreet[]): {
  roads: number;
  walks: number;
  edges: number;
} {
  const inners = streets.filter((street) => isInnerStreet(street));
  return {
    roads: inners.length,
    walks: inners.reduce((n, street) => n + innerWalkSegments(street).length, 0),
    edges: inners.reduce((n, street) => n + innerEdgeStripSegments(street).length, 0),
  };
}

export function streetSegments(
  points: [number, number][],
  width = STREET_WIDTH_M,
): StreetSegment[] {
  const out: StreetSegment[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) {
      continue;
    }
    const dx = b[0] - a[0];
    const dz = b[1] - a[1];
    const length = Math.hypot(dx, dz);
    if (length < 0.2) {
      continue;
    }
    out.push({
      x: (a[0] + b[0]) / 2,
      z: (a[1] + b[1]) / 2,
      length,
      width,
      rotationY: Math.atan2(dx, dz),
    });
  }
  return out;
}

export type StreetLamp = {
  id: string;
  x: number;
  z: number;
  yaw: number;
  glow: boolean;
  streetId: string;
};

export type StreetCrosswalk = {
  id: string;
  x: number;
  z: number;
  rotationY: number;
  across: number;
  stripes: number;
  stripeAlong: number;
  stripeGap: number;
};

export type StreetStopLine = {
  id: string;
  x: number;
  z: number;
  rotationY: number;
  across: number;
  thick: number;
};

export type StreetCurbReturn = {
  id: string;
  x: number;
  z: number;
  rotationY: number;
  width: number;
  length: number;
};

export type CornerCrossing = {
  kind: typeof CORNER_CROSSING_KIND;
  crosswalk: StreetCrosswalk;
  stopLine: StreetStopLine;
  curbReturns: StreetCurbReturn[];
};

export type StreetPlanter = {
  id: string;
  x: number;
  z: number;
};

export type StreetScooter = {
  id: string;
  x: number;
  z: number;
  yaw: number;
  color: string;
  streetId: string;
};

export type StreetProps = {
  lamps: StreetLamp[];
  crosswalks: StreetCrosswalk[];
  planters: StreetPlanter[];
  scooters: StreetScooter[];
  stopLines: StreetStopLine[];
  curbReturns: StreetCurbReturn[];
};

type PlanterSpec = {
  id: string;
  streetId: string;
  along: number;
  side: 1 | -1;
  across: number;
};

/** Sidewalk masses only. Stay on Harbor Walk / Tram Approach, inside 400 m. */
const PLANTER_SPECS: PlanterSpec[] = [
  { id: "planter-harbor-shop-e", streetId: "street-harbor-walk", along: 0.325, side: 1, across: 7.55 },
  { id: "planter-harbor-shop-w", streetId: "street-harbor-walk", along: 0.348, side: -1, across: 7.55 },
  { id: "planter-harbor-north-e", streetId: "street-harbor-walk", along: 0.455, side: 1, across: 7.7 },
  { id: "planter-tram-east-s", streetId: "street-tram-approach", along: 0.64, side: -1, across: 7.4 },
];

function polylineLength(points: [number, number][]): number {
  let total = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) {
      continue;
    }
    total += Math.hypot(b[0] - a[0], b[1] - a[1]);
  }
  return total;
}

function pointAtDistance(
  points: [number, number][],
  dist: number,
): { x: number; z: number; dx: number; dz: number } | null {
  let left = dist;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) {
      continue;
    }
    const seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (seg < 0.2) {
      continue;
    }
    if (left <= seg) {
      const dx = (b[0] - a[0]) / seg;
      const dz = (b[1] - a[1]) / seg;
      return { x: a[0] + dx * left, z: a[1] + dz * left, dx, dz };
    }
    left -= seg;
  }
  return null;
}

function nearestOnPolyline(
  points: [number, number][],
  x: number,
  z: number,
): { x: number; z: number; dx: number; dz: number; dist: number } | null {
  let best: { x: number; z: number; dx: number; dz: number; dist: number } | null = null;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (!a || !b) {
      continue;
    }
    const vx = b[0] - a[0];
    const vz = b[1] - a[1];
    const seg = Math.hypot(vx, vz);
    if (seg < 0.2) {
      continue;
    }
    const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (seg * seg)));
    const px = a[0] + vx * t;
    const pz = a[1] + vz * t;
    const dist = Math.hypot(x - px, z - pz);
    if (!best || dist < best.dist) {
      best = { x: px, z: pz, dx: vx / seg, dz: vz / seg, dist };
    }
  }
  return best;
}

function offsetSide(
  x: number,
  z: number,
  dx: number,
  dz: number,
  side: 1 | -1,
  across: number,
): { x: number; z: number; yaw: number } {
  const rot = Math.atan2(dx, dz);
  const ox = Math.cos(rot) * side * across;
  const oz = -Math.sin(rot) * side * across;
  const inwardX = -Math.cos(rot) * side;
  const inwardZ = Math.sin(rot) * side;
  return { x: x + ox, z: z + oz, yaw: Math.atan2(inwardX, inwardZ) };
}

function lngLatBoxAround(lon: number, lat: number, halfM: number) {
  const dLon = halfM / metersPerDegLon(lat);
  const dLat = halfM / M_PER_DEG_LAT;
  return {
    west: lon - dLon,
    east: lon + dLon,
    south: lat - dLat,
    north: lat + dLat,
  };
}

function solidFromWorld(id: string, x: number, z: number, halfM: number): BuildingPoly {
  const { lon, lat } = worldToLngLat(x, z);
  const aabb = lngLatBoxAround(lon, lat, halfM);
  return {
    id,
    name: id,
    height_m: 4,
    ring: [
      [aabb.west, aabb.south],
      [aabb.east, aabb.south],
      [aabb.east, aabb.north],
      [aabb.west, aabb.north],
      [aabb.west, aabb.south],
    ],
    aabb,
  };
}

function innerPropAcross(street: WorldStreet, kind: "lamp" | "scooter"): number {
  const half = street.halfGapM > 0 ? street.halfGapM : INNER_LANE_WIDTH_M;
  if (half <= 3.6) {
    return Math.max(0.85, half - (kind === "lamp" ? 0.42 : 0.88));
  }
  return streetRoadWidth(street) / 2 + (kind === "lamp" ? 0.5 : 1.15);
}

function nearAnyCrosswalk(
  x: number,
  z: number,
  rows: StreetCrosswalk[],
  radius: number,
): boolean {
  return rows.some((row) => Math.hypot(x - row.x, z - row.z) < radius);
}

/**
 * Cheap zebra + stop-line + curb return at the Harbor Walk / Steps East
 * mouth only. Reuses Harbor stripe sizes. Not a fifth street. Not OSM.
 */
export function harborStepsEastCrossing(
  streets: WorldStreet[],
  buildings: WorldBuilding[],
): CornerCrossing | null {
  const harbor = streets.find((street) => street.id === "street-harbor-walk");
  if (!harbor) {
    return null;
  }
  const box = unionBuildingBox(buildings, "bldg-steps-e");
  if (!box || box.maxZ - box.minZ < 8) {
    return null;
  }
  const laneX = box.minX - 2.45;
  const cornerZ = Math.max(box.minZ + 10, Math.min(box.maxZ - 10, -76.2));
  const onHarbor = nearestOnPolyline(harbor.points, laneX, cornerZ);
  if (!onHarbor || onHarbor.dist < 5 || onHarbor.dist > 16) {
    return null;
  }
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  const rotationY = Math.atan2(onHarbor.dx, onHarbor.dz);
  let zx = onHarbor.x;
  let zz = onHarbor.z;
  if (Math.hypot(zx - shop.x, zz - shop.z) < 8.2) {
    zx -= onHarbor.dx * 4.2;
    zz -= onHarbor.dz * 4.2;
  }
  if (Math.hypot(zx - spawn.x, zz - spawn.z) < CORNER_SKIP_SPAWN_M) {
    return null;
  }
  if (inSpawnKeepOutXZ(zx, zz)) {
    return null;
  }
  if (Math.hypot(zx - shop.x, zz - shop.z) < CORNER_SKIP_LANTERN_M) {
    return null;
  }
  const crosswalk: StreetCrosswalk = {
    id: CORNER_CROSSWALK_ID,
    x: zx,
    z: zz,
    rotationY,
    across: STREET_WIDTH_M - 0.35,
    stripes: CORNER_ZEBRA_STRIPES,
    stripeAlong: CORNER_ZEBRA_ALONG_M,
    stripeGap: CORNER_ZEBRA_GAP_M,
  };
  const stopLine: StreetStopLine = {
    id: CORNER_STOP_LINE_ID,
    x: zx - onHarbor.dx * 2.15,
    z: zz - onHarbor.dz * 2.15,
    rotationY,
    across: STREET_WIDTH_M - 0.45,
    thick: CORNER_STOP_THICK_M,
  };
  const curbReturns: StreetCurbReturn[] = [];
  for (const [tag, along] of [
    ["s", -CORNER_MOUTH_HALF_M],
    ["n", CORNER_MOUTH_HALF_M],
  ] as const) {
    const at = {
      x: zx + onHarbor.dx * along,
      z: zz + onHarbor.dz * along,
      dx: onHarbor.dx,
      dz: onHarbor.dz,
    };
    const stem = offsetSide(
      at.x,
      at.z,
      at.dx,
      at.dz,
      1,
      STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2,
    );
    curbReturns.push({
      id: `curb-return-harbor-steps-${tag}`,
      x: stem.x,
      z: stem.z,
      rotationY,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ALONG_M,
    });
    const armAcross = STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2 + CORNER_CURB_ARM_M / 2;
    const arm = offsetSide(at.x, at.z, at.dx, at.dz, 1, armAcross);
    curbReturns.push({
      id: `curb-return-steps-east-${tag}`,
      x: arm.x,
      z: arm.z,
      rotationY: rotationY + Math.PI / 2,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ARM_M,
    });
  }
  return { kind: CORNER_CROSSING_KIND, crosswalk, stopLine, curbReturns };
}

/**
 * Cheap zebra + stop-line + curb return at the Harbor Walk / Steps West
 * mouth only. Same Harbor stripe sizes as the east mouth. Zebra sits on
 * the west inner ribbon so it does not stack on the east Harbor zebra.
 * Curb returns hook the Harbor west curb. Not a fifth street. Not OSM.
 */
export function harborStepsWestCrossing(
  streets: WorldStreet[],
  buildings: WorldBuilding[],
): CornerCrossing | null {
  const harbor = streets.find((street) => street.id === "street-harbor-walk");
  if (!harbor) {
    return null;
  }
  const box = unionBuildingBox(buildings, "bldg-steps-w");
  if (!box || box.maxZ - box.minZ < 8) {
    return null;
  }
  const laneX = box.maxX + 2.45;
  const cornerZ = Math.max(box.minZ + 10, Math.min(box.maxZ - 10, -76.2));
  const onHarbor = nearestOnPolyline(harbor.points, laneX, cornerZ);
  if (!onHarbor || onHarbor.dist < 5 || onHarbor.dist > WEST_CORNER_DIST_MAX_M) {
    return null;
  }
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  const rotationY = Math.atan2(onHarbor.dx, onHarbor.dz);
  const zx = laneX;
  const zz = onHarbor.z;
  if (Math.hypot(zx - spawn.x, zz - spawn.z) < CORNER_SKIP_SPAWN_M) {
    return null;
  }
  if (inSpawnKeepOutXZ(zx, zz)) {
    return null;
  }
  if (Math.hypot(zx - shop.x, zz - shop.z) < CORNER_SKIP_LANTERN_M) {
    return null;
  }
  const crosswalk: StreetCrosswalk = {
    id: WEST_CROSSWALK_ID,
    x: zx,
    z: zz,
    rotationY,
    across: WEST_ZEBRA_ACROSS_M,
    stripes: CORNER_ZEBRA_STRIPES,
    stripeAlong: CORNER_ZEBRA_ALONG_M,
    stripeGap: CORNER_ZEBRA_GAP_M,
  };
  const stopLine: StreetStopLine = {
    id: WEST_STOP_LINE_ID,
    x: zx - onHarbor.dx * 2.15,
    z: zz - onHarbor.dz * 2.15,
    rotationY,
    across: WEST_ZEBRA_ACROSS_M - 0.1,
    thick: CORNER_STOP_THICK_M,
  };
  const curbReturns: StreetCurbReturn[] = [];
  for (const [tag, along] of [
    ["s", -CORNER_MOUTH_HALF_M],
    ["n", CORNER_MOUTH_HALF_M],
  ] as const) {
    const at = {
      x: onHarbor.x + onHarbor.dx * along,
      z: onHarbor.z + onHarbor.dz * along,
      dx: onHarbor.dx,
      dz: onHarbor.dz,
    };
    const stem = offsetSide(
      at.x,
      at.z,
      at.dx,
      at.dz,
      -1,
      STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2,
    );
    curbReturns.push({
      id: `curb-return-harbor-steps-west-${tag}`,
      x: stem.x,
      z: stem.z,
      rotationY,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ALONG_M,
    });
    const armAcross = STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2 + CORNER_CURB_ARM_M / 2;
    const arm = offsetSide(at.x, at.z, at.dx, at.dz, -1, armAcross);
    curbReturns.push({
      id: `curb-return-steps-west-${tag}`,
      x: arm.x,
      z: arm.z,
      rotationY: rotationY + Math.PI / 2,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ARM_M,
    });
  }
  return { kind: CORNER_CROSSING_KIND, crosswalk, stopLine, curbReturns };
}

/**
 * Cheap zebra + stop-line + curb return at the Harbor Walk / Tram Approach
 * mouth only. Same Harbor stripe sizes as the Steps mouths. Zebra sits on
 * Tram Approach just east of Harbor so it does not stack on the lantern
 * zebra or the two Steps mouths. Not a fifth street. Not OSM.
 */
export function harborTramCrossing(streets: WorldStreet[]): CornerCrossing | null {
  const harbor = streets.find((street) => street.id === "street-harbor-walk");
  const tram = streets.find((street) => street.id === "street-tram-approach");
  if (!harbor || !tram) {
    return null;
  }
  let join: {
    hx: number;
    hz: number;
    hdx: number;
    hdz: number;
    tx: number;
    tz: number;
    tdx: number;
    tdz: number;
    dist: number;
  } | null = null;
  const harborLen = polylineLength(harbor.points);
  for (let dist = 0; dist <= harborLen + 0.01; dist += 3) {
    const at = pointAtDistance(harbor.points, dist);
    if (!at) {
      continue;
    }
    const near = nearestOnPolyline(tram.points, at.x, at.z);
    if (!near) {
      continue;
    }
    if (!join || near.dist < join.dist) {
      join = {
        hx: at.x,
        hz: at.z,
        hdx: at.dx,
        hdz: at.dz,
        tx: near.x,
        tz: near.z,
        tdx: near.dx,
        tdz: near.dz,
        dist: near.dist,
      };
    }
  }
  if (!join || join.dist > TRAM_JOIN_MAX_M) {
    return null;
  }
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  const east = join.tdx >= 0 ? 1 : -1;
  const tdx = join.tdx * east;
  const tdz = join.tdz * east;
  const zx = join.tx + tdx * TRAM_MOUTH_ALONG_M;
  const zz = join.tz + tdz * TRAM_MOUTH_ALONG_M;
  if (Math.hypot(zx - spawn.x, zz - spawn.z) < CORNER_SKIP_SPAWN_M) {
    return null;
  }
  if (inSpawnKeepOutXZ(zx, zz)) {
    return null;
  }
  if (Math.hypot(zx - shop.x, zz - shop.z) < CORNER_SKIP_LANTERN_M + 8) {
    return null;
  }
  if (zz < TRAM_SKIP_STEPS_Z) {
    return null;
  }
  const rotationY = Math.atan2(tdx, tdz);
  const harborRot = Math.atan2(join.hdx, join.hdz);
  const crosswalk: StreetCrosswalk = {
    id: TRAM_CROSSWALK_ID,
    x: zx,
    z: zz,
    rotationY,
    across: STREET_WIDTH_M - 0.35,
    stripes: CORNER_ZEBRA_STRIPES,
    stripeAlong: CORNER_ZEBRA_ALONG_M,
    stripeGap: CORNER_ZEBRA_GAP_M,
  };
  const stopLine: StreetStopLine = {
    id: TRAM_STOP_LINE_ID,
    x: zx - tdx * 2.15,
    z: zz - tdz * 2.15,
    rotationY,
    across: STREET_WIDTH_M - 0.45,
    thick: CORNER_STOP_THICK_M,
  };
  const curbReturns: StreetCurbReturn[] = [];
  for (const [tag, along] of [
    ["s", -CORNER_MOUTH_HALF_M],
    ["n", CORNER_MOUTH_HALF_M],
  ] as const) {
    const at = {
      x: join.hx + join.hdx * along,
      z: join.hz + join.hdz * along,
      dx: join.hdx,
      dz: join.hdz,
    };
    const stem = offsetSide(
      at.x,
      at.z,
      at.dx,
      at.dz,
      1,
      STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2,
    );
    curbReturns.push({
      id: `curb-return-harbor-tram-${tag}`,
      x: stem.x,
      z: stem.z,
      rotationY: harborRot,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ALONG_M,
    });
    const armAcross = STREET_WIDTH_M / 2 + CURB_WIDTH_M / 2 + CORNER_CURB_ARM_M / 2;
    const arm = offsetSide(at.x, at.z, at.dx, at.dz, 1, armAcross);
    curbReturns.push({
      id: `curb-return-tram-approach-${tag}`,
      x: arm.x,
      z: arm.z,
      rotationY: harborRot + Math.PI / 2,
      width: CURB_WIDTH_M,
      length: CORNER_CURB_ARM_M,
    });
  }
  return { kind: CORNER_CROSSING_KIND, crosswalk, stopLine, curbReturns };
}

function streetNearMain(street: WorldStreet, mains: WorldStreet[]): boolean {
  const total = polylineLength(street.points);
  const samples = [0.4, total * 0.5, Math.max(0.4, total - 0.4)];
  for (const dist of samples) {
    const at = pointAtDistance(street.points, dist);
    if (!at) {
      continue;
    }
    for (const main of mains) {
      const near = nearestOnPolyline(main.points, at.x, at.z);
      if (near && near.dist <= INNER_NEAR_MAIN_M) {
        return true;
      }
    }
  }
  return false;
}

/**
 * Authored lamp / zebra / planter / parked-scooter layout from Harbor Walk
 * + Tram Approach, plus a few lamps and parked scooters on inner lanes.
 * Curb and sidewalk edge only — the driving lane stays walkable.
 * Scooters are STATIC props, not riders / traffic / people.
 */
export function streetPropsFromStreets(
  streets: WorldStreet[],
  buildings: WorldBuilding[] = [],
): StreetProps {
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  const lamps: StreetLamp[] = [];
  const asphalt = streets.filter((street) => street.surface === "asphalt");
  const mains = asphalt.filter((street) => !isInnerStreet(street));
  const inners = asphalt.filter((street) => isInnerStreet(street));

  const tryLamp = (
    streetId: string,
    at: { x: number; z: number; dx: number; dz: number },
    side: 1 | -1,
    id: string,
    opts?: { ignoreSpawnSkip?: boolean; across?: number },
  ): void => {
    const placed = offsetSide(at.x, at.z, at.dx, at.dz, side, opts?.across ?? LAMP_CURB_M);
    const spawnDist = Math.hypot(placed.x - spawn.x, placed.z - spawn.z);
    if (spawnDist < 2.6) {
      return;
    }
    if (!opts?.ignoreSpawnSkip && spawnDist < LAMP_SKIP_SPAWN_M) {
      return;
    }
    if (Math.hypot(placed.x, placed.z) < LAMP_SKIP_CROSSING_M) {
      return;
    }
    if (lamps.some((lamp) => Math.hypot(lamp.x - placed.x, lamp.z - placed.z) < 8)) {
      return;
    }
    lamps.push({
      id,
      x: placed.x,
      z: placed.z,
      yaw: placed.yaw,
      glow: false,
      streetId,
    });
  };

  for (const street of mains) {
    const total = polylineLength(street.points);
    if (total < LAMP_SPACING_M) {
      continue;
    }
    const start = 18;
    const end = total - 18;
    let index = 0;
    for (let dist = start; dist <= end + 0.01; dist += LAMP_SPACING_M) {
      const at = pointAtDistance(street.points, dist);
      if (!at) {
        continue;
      }
      for (const side of [1, -1] as const) {
        tryLamp(street.id, at, side, `lamp-${street.id}-${index}-${side > 0 ? "e" : "w"}`);
      }
      index += 1;
    }
  }

  const harbor = asphalt.find((street) => street.id === "street-harbor-walk");
  if (harbor) {
    const atShop = nearestOnPolyline(harbor.points, shop.x, shop.z);
    if (atShop) {
      tryLamp(harbor.id, atShop, 1, "lamp-harbor-shop-e");
      tryLamp(harbor.id, atShop, -1, "lamp-harbor-shop-w");
    }
    const walkNear = nearestOnPolyline(harbor.points, spawn.x, spawn.z + 11);
    if (walkNear) {
      tryLamp(harbor.id, walkNear, 1, "lamp-harbor-near-e", { ignoreSpawnSkip: true });
      tryLamp(harbor.id, walkNear, -1, "lamp-harbor-near-w", { ignoreSpawnSkip: true });
    }
    const walkAhead = nearestOnPolyline(harbor.points, spawn.x, spawn.z + 22);
    if (walkAhead) {
      tryLamp(harbor.id, walkAhead, 1, "lamp-harbor-walk-e");
      tryLamp(harbor.id, walkAhead, -1, "lamp-harbor-walk-w");
    }
  }
  const glowRank = lamps
    .map((lamp, i) => ({
      i,
      d: Math.hypot(lamp.x - shop.x, lamp.z - shop.z),
      harbor: lamp.streetId === "street-harbor-walk",
    }))
    .filter((row) => row.harbor && row.d < 58)
    .sort((a, b) => a.d - b.d)
    .slice(0, LAMP_GLOW_MAX);
  for (const row of glowRank) {
    const lamp = lamps[row.i];
    if (lamp) {
      lamp.glow = true;
    }
  }

  const crosswalks: StreetCrosswalk[] = [];
  const stopLines: StreetStopLine[] = [];
  const curbReturns: StreetCurbReturn[] = [];
  if (harbor) {
    const onRoad = nearestOnPolyline(harbor.points, shop.x, shop.z);
    if (onRoad && onRoad.dist < 8) {
      crosswalks.push({
        id: "crosswalk-harbor-lantern",
        x: onRoad.x,
        z: onRoad.z,
        rotationY: Math.atan2(onRoad.dx, onRoad.dz),
        across: STREET_WIDTH_M - 0.35,
        stripes: 7,
        stripeAlong: 0.58,
        stripeGap: 0.42,
      });
    }
  }
  const corner = harborStepsEastCrossing(streets, buildings);
  if (corner) {
    crosswalks.push(corner.crosswalk);
    stopLines.push(corner.stopLine);
    curbReturns.push(...corner.curbReturns);
  }
  const westCorner = harborStepsWestCrossing(streets, buildings);
  if (westCorner) {
    crosswalks.push(westCorner.crosswalk);
    stopLines.push(westCorner.stopLine);
    curbReturns.push(...westCorner.curbReturns);
  }
  const tramCorner = harborTramCrossing(streets);
  if (tramCorner) {
    crosswalks.push(tramCorner.crosswalk);
    stopLines.push(tramCorner.stopLine);
    curbReturns.push(...tramCorner.curbReturns);
  }

  const planters: StreetPlanter[] = [];
  for (const spec of PLANTER_SPECS) {
    const street = streets.find((row) => row.id === spec.streetId);
    if (!street) {
      continue;
    }
    const total = polylineLength(street.points);
    const at = pointAtDistance(street.points, spec.along * total);
    if (!at) {
      continue;
    }
    const placed = offsetSide(at.x, at.z, at.dx, at.dz, spec.side, spec.across);
    if (Math.hypot(placed.x, placed.z) > SLAB_SIZE_M / 2 - 8) {
      continue;
    }
    if (Math.hypot(placed.x - spawn.x, placed.z - spawn.z) < 8) {
      continue;
    }
    planters.push({ id: spec.id, x: placed.x, z: placed.z });
  }

  const scooters: StreetScooter[] = [];
  const tryScooter = (
    streetId: string,
    at: { x: number; z: number; dx: number; dz: number },
    side: 1 | -1,
    id: string,
    across = SCOOTER_CURB_M,
  ): void => {
    const placed = offsetSide(at.x, at.z, at.dx, at.dz, side, across);
    if (Math.hypot(placed.x, placed.z) > SLAB_SIZE_M / 2 - 8) {
      return;
    }
    if (Math.hypot(placed.x - spawn.x, placed.z - spawn.z) < SCOOTER_SKIP_SPAWN_M) {
      return;
    }
    if (Math.hypot(placed.x - shop.x, placed.z - shop.z) < SCOOTER_SKIP_LANTERN_M) {
      return;
    }
    if (Math.hypot(placed.x, placed.z) < SCOOTER_SKIP_CROSSING_M) {
      return;
    }
    if (nearAnyCrosswalk(placed.x, placed.z, crosswalks, SCOOTER_SKIP_ZEBRA_M)) {
      return;
    }
    if (lamps.some((lamp) => Math.hypot(lamp.x - placed.x, lamp.z - placed.z) < SCOOTER_MIN_LAMP_M)) {
      return;
    }
    if (
      planters.some((planter) => Math.hypot(planter.x - placed.x, planter.z - placed.z) < SCOOTER_MIN_PLANTER_M)
    ) {
      return;
    }
    if (scooters.some((row) => Math.hypot(row.x - placed.x, row.z - placed.z) < SCOOTER_MIN_PEER_M)) {
      return;
    }
    const yawJitter = ((colorIndex(id) % 11) - 5) * 0.035;
    scooters.push({
      id,
      x: placed.x,
      z: placed.z,
      yaw: placed.yaw + yawJitter,
      color: scooterColorForId(id),
      streetId,
    });
  };

  if (harbor) {
    const nearE = nearestOnPolyline(harbor.points, spawn.x, spawn.z + 9.2);
    const nearW = nearestOnPolyline(harbor.points, spawn.x, spawn.z + 6.6);
    if (nearE) {
      tryScooter(harbor.id, nearE, 1, "scooter-harbor-near-e");
    }
    if (nearW) {
      tryScooter(harbor.id, nearW, -1, "scooter-harbor-near-w");
    }
    const past = nearestOnPolyline(harbor.points, shop.x, shop.z + 18);
    if (past) {
      tryScooter(harbor.id, past, 1, "scooter-harbor-past-e");
      tryScooter(harbor.id, past, -1, "scooter-harbor-past-w");
    }
  }

  for (const street of mains) {
    const total = polylineLength(street.points);
    if (total < SCOOTER_SPACING_M) {
      continue;
    }
    let index = 0;
    for (
      let dist = SCOOTER_START_M;
      dist <= total - SCOOTER_END_PAD_M + 0.01;
      dist += SCOOTER_SPACING_M
    ) {
      const at = pointAtDistance(street.points, dist);
      if (!at) {
        continue;
      }
      for (const side of [1, -1] as const) {
        const id = `scooter-${street.id}-${index}-${side > 0 ? "e" : "w"}`;
        if (!keepHashedScooter(id)) {
          continue;
        }
        const jitterM = (colorIndex(id) % 9 - 4) * 0.55;
        const atJ = pointAtDistance(street.points, dist + jitterM) ?? at;
        const placed = offsetSide(atJ.x, atJ.z, atJ.dx, atJ.dz, side, SCOOTER_CURB_M);
        if (Math.hypot(placed.x, placed.z) > SLAB_SIZE_M / 2 - 8) {
          continue;
        }
        if (Math.hypot(placed.x - spawn.x, placed.z - spawn.z) < SCOOTER_SKIP_SPAWN_M) {
          continue;
        }
        if (Math.hypot(placed.x - shop.x, placed.z - shop.z) < SCOOTER_SKIP_LANTERN_M) {
          continue;
        }
        if (Math.hypot(placed.x, placed.z) < SCOOTER_SKIP_CROSSING_M) {
          continue;
        }
        if (nearAnyCrosswalk(placed.x, placed.z, crosswalks, SCOOTER_SKIP_ZEBRA_M)) {
          continue;
        }
        if (lamps.some((lamp) => Math.hypot(lamp.x - placed.x, lamp.z - placed.z) < SCOOTER_MIN_LAMP_M)) {
          continue;
        }
        if (
          planters.some(
            (planter) => Math.hypot(planter.x - placed.x, planter.z - placed.z) < SCOOTER_MIN_PLANTER_M,
          )
        ) {
          continue;
        }
        if (
          scooters.some((row) => Math.hypot(row.x - placed.x, row.z - placed.z) < SCOOTER_MIN_PEER_M)
        ) {
          continue;
        }
        const yawJitter = ((colorIndex(id) % 11) - 5) * 0.035;
        scooters.push({
          id,
          x: placed.x,
          z: placed.z,
          yaw: placed.yaw + yawJitter,
          color: scooterColorForId(id),
          streetId: street.id,
        });
      }
      index += 1;
    }
  }

  const branch = inners.filter((street) => streetNearMain(street, mains));
  const innerLampCount = () => lamps.filter((lamp) => isInnerStreetId(lamp.streetId)).length;
  const innerScooterCount = () => scooters.filter((row) => isInnerStreetId(row.streetId)).length;
  for (const street of branch) {
    if (innerLampCount() >= INNER_LAMP_MAX) {
      break;
    }
    const total = polylineLength(street.points);
    if (total < 8) {
      continue;
    }
    const at = pointAtDistance(street.points, total * 0.55);
    if (!at) {
      continue;
    }
    const side: 1 | -1 = innerLampCount() % 2 === 0 ? 1 : -1;
    tryLamp(street.id, at, side, `lamp-${street.id}`, {
      across: innerPropAcross(street, "lamp"),
    });
  }
  const scooterHosts = branch.length > 0 ? branch : inners;
  for (const street of scooterHosts) {
    if (innerScooterCount() >= INNER_SCOOTER_MAX) {
      break;
    }
    const total = polylineLength(street.points);
    if (total < 8) {
      continue;
    }
    const at = pointAtDistance(street.points, total * 0.62);
    if (!at) {
      continue;
    }
    const side: 1 | -1 = innerScooterCount() % 2 === 0 ? -1 : 1;
    const before = scooters.length;
    tryScooter(
      street.id,
      at,
      side,
      `scooter-${street.id}`,
      innerPropAcross(street, "scooter"),
    );
    if (scooters.length === before && innerScooterCount() < INNER_SCOOTER_MAX) {
      tryScooter(
        street.id,
        at,
        side === 1 ? -1 : 1,
        `scooter-${street.id}-b`,
        innerPropAcross(street, "scooter"),
      );
    }
  }

  return { lamps, crosswalks, planters, scooters, stopLines, curbReturns };
}

export function streetPropsFromCollection(data: FeatureCollection): StreetProps {
  return streetPropsFromStreets(
    worldFromCollection(data).streets,
    buildingsToWorld(buildingsFromCollection(data)),
  );
}

export type StreetPlaqueRole = "official" | "inner";

export type StreetPlaque = {
  id: string;
  streetId: string;
  name: string;
  line2: string;
  role: StreetPlaqueRole;
  x: number;
  z: number;
  yaw: number;
  poleH: number;
  boardY: number;
  boardW: number;
  boardH: number;
  collide: boolean;
  kind: typeof STREET_PLAQUE_KIND;
};

type OfficialPlaqueSpec = {
  id: string;
  streetId: string;
  name: string;
  line2: string;
  along: number;
  side: 1 | -1;
  across: number;
};

/** Harbor Walk + Tram Approach only. Names already in the authored fixture. */
const OFFICIAL_PLAQUE_SPECS: OfficialPlaqueSpec[] = [
  {
    id: "plaque-harbor-walk",
    streetId: "street-harbor-walk",
    name: "Harbor Walk",
    line2: "official street",
    along: 0.285,
    side: -1,
    across: 7.45,
  },
  {
    id: "plaque-tram-approach",
    streetId: "street-tram-approach",
    name: "Tram Approach",
    line2: "official street",
    along: 0.56,
    side: 1,
    across: 7.45,
  },
];

function unionBuildingBox(
  buildings: WorldBuilding[],
  idPrefix: string,
): { minX: number; maxX: number; minZ: number; maxZ: number } | null {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  let n = 0;
  for (const building of buildings) {
    if (!building.id.startsWith(idPrefix)) {
      continue;
    }
    minX = Math.min(minX, building.cx - building.width / 2);
    maxX = Math.max(maxX, building.cx + building.width / 2);
    minZ = Math.min(minZ, building.cz - building.depth / 2);
    maxZ = Math.max(maxZ, building.cz + building.depth / 2);
    n += 1;
  }
  return n > 0 ? { minX, maxX, minZ, maxZ } : null;
}

function finishStreetPlaque(input: {
  id: string;
  streetId: string;
  name: string;
  line2: string;
  role: StreetPlaqueRole;
  x: number;
  z: number;
  yaw: number;
}): StreetPlaque | null {
  const spawn = lngLatToWorld(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  const shop = lngLatToWorld(LANTERN_SHOP_LL.lon, LANTERN_SHOP_LL.lat);
  if (Math.hypot(input.x - spawn.x, input.z - spawn.z) < SPAWN_KEEP_OUT_M) {
    return null;
  }
  if (inSpawnKeepOutXZ(input.x, input.z)) {
    return null;
  }
  if (Math.hypot(input.x - shop.x, input.z - shop.z) < PLAQUE_SKIP_LANTERN_M) {
    return null;
  }
  return {
    id: input.id,
    streetId: input.streetId,
    name: input.name,
    line2: input.line2,
    role: input.role,
    x: input.x,
    z: input.z,
    yaw: input.yaw,
    poleH: PLAQUE_POLE_H,
    boardY: PLAQUE_BOARD_Y,
    boardW: PLAQUE_BOARD_W,
    boardH: PLAQUE_BOARD_H,
    collide: true,
    kind: STREET_PLAQUE_KIND,
  };
}

/**
 * Walk-visible corner plaques for the two official streets plus Steps East/West.
 * Fixture names only. Not OSM. Not a downtown grid. Thin planter collision.
 */
export function streetPlaquesFromWorld(
  streets: WorldStreet[],
  buildings: WorldBuilding[],
): StreetPlaque[] {
  const out: StreetPlaque[] = [];
  for (const spec of OFFICIAL_PLAQUE_SPECS) {
    const street = streets.find((row) => row.id === spec.streetId);
    if (!street) {
      continue;
    }
    const total = polylineLength(street.points);
    const at = pointAtDistance(street.points, total * spec.along);
    if (!at) {
      continue;
    }
    const placed = offsetSide(at.x, at.z, at.dx, at.dz, spec.side, spec.across);
    const row = finishStreetPlaque({
      id: spec.id,
      streetId: spec.streetId,
      name: spec.name,
      line2: spec.line2,
      role: "official",
      x: placed.x,
      z: placed.z,
      yaw: placed.yaw,
    });
    if (row) {
      out.push(row);
    }
  }
  const stepsEast = unionBuildingBox(buildings, "bldg-steps-e");
  if (stepsEast) {
    const row = finishStreetPlaque({
      id: "plaque-steps-east",
      streetId: "steps-east",
      name: "Steps East",
      line2: "inner lane",
      role: "inner",
      x: stepsEast.minX - 2.45,
      z: Math.max(stepsEast.minZ + 10, Math.min(stepsEast.maxZ - 10, -76.2)),
      yaw: Math.PI / 2,
    });
    if (row) {
      out.push(row);
    }
  }
  const stepsWest = unionBuildingBox(buildings, "bldg-steps-w");
  if (stepsWest) {
    const row = finishStreetPlaque({
      id: "plaque-steps-west",
      streetId: "steps-west",
      name: "Steps West",
      line2: "inner lane",
      role: "inner",
      x: stepsWest.maxX + 2.45,
      z: Math.max(stepsWest.minZ + 10, Math.min(stepsWest.maxZ - 10, -76.2)),
      yaw: -Math.PI / 2,
    });
    if (row) {
      out.push(row);
    }
  }
  return out;
}

export function streetPlaquesFromCollection(data: FeatureCollection): StreetPlaque[] {
  return streetPlaquesFromWorld(
    worldFromCollection(data).streets,
    buildingsToWorld(buildingsFromCollection(data)),
  );
}

export type StreetHudRole = StreetPlaqueRole;

export type NamedStreetHudLane = {
  id: string;
  name: string;
  role: StreetHudRole;
  streetId: string;
  points: [number, number][];
  halfM: number;
};

export type NamedStreetHud = {
  id: string;
  name: string;
  role: StreetHudRole;
  streetId: string;
  distM: number;
};

function namedInnerHudLane(
  buildings: WorldBuilding[],
  idPrefix: string,
  streetId: string,
  name: string,
  side: "west-of" | "east-of",
): NamedStreetHudLane | null {
  const box = unionBuildingBox(buildings, idPrefix);
  if (!box) {
    return null;
  }
  const x = side === "west-of" ? box.minX - 2.45 : box.maxX + 2.45;
  if (box.maxZ - box.minZ < 8) {
    return null;
  }
  return {
    id: `hud-${streetId}`,
    name,
    role: "inner",
    streetId,
    points: [
      [x, box.minZ],
      [x, box.maxZ],
    ],
    halfM: 4.6,
  };
}

/**
 * The four plaque names as walk bands. Official streets use the GeoJSON
 * centerline; Steps East/West use the Harbor-facing inner gap. Fixture
 * names only — not GPS, not OSM, not a downtown grid. Nearest in-band
 * wins so a Harbor sidewalk does not steal the Steps East walk.
 */
export function namedStreetHudLanes(
  streets: WorldStreet[],
  buildings: WorldBuilding[],
): NamedStreetHudLane[] {
  const out: NamedStreetHudLane[] = [];
  for (const street of streets) {
    if (street.id === "street-harbor-walk") {
      out.push({
        id: "hud-harbor-walk",
        name: "Harbor Walk",
        role: "official",
        streetId: street.id,
        points: street.points,
        halfM: WALK_WIDTH_M / 2,
      });
    }
    if (street.id === "street-tram-approach") {
      out.push({
        id: "hud-tram-approach",
        name: "Tram Approach",
        role: "official",
        streetId: street.id,
        points: street.points,
        halfM: WALK_WIDTH_M / 2,
      });
    }
  }
  const stepsEast = namedInnerHudLane(buildings, "bldg-steps-e", "steps-east", "Steps East", "west-of");
  const stepsWest = namedInnerHudLane(buildings, "bldg-steps-w", "steps-west", "Steps West", "east-of");
  if (stepsEast) {
    out.push(stepsEast);
  }
  if (stepsWest) {
    out.push(stepsWest);
  }
  return out;
}

export function namedStreetHudAt(
  lon: number,
  lat: number,
  lanes: NamedStreetHudLane[],
): NamedStreetHud | null {
  const p = lngLatToWorld(lon, lat);
  let best: NamedStreetHud | null = null;
  for (const lane of lanes) {
    const hit = nearestOnPolyline(lane.points, p.x, p.z);
    if (!hit || hit.dist > lane.halfM) {
      continue;
    }
    if (!best || hit.dist < best.distM) {
      best = {
        id: lane.id,
        name: lane.name,
        role: lane.role,
        streetId: lane.streetId,
        distM: hit.dist,
      };
    }
  }
  return best;
}

export function namedStreetHudAtLonLat(
  data: FeatureCollection,
  lon: number,
  lat: number,
): NamedStreetHud | null {
  const streets = worldFromCollection(data).streets;
  const buildings = buildingsToWorld(buildingsFromCollection(data));
  return namedStreetHudAt(lon, lat, namedStreetHudLanes(streets, buildings));
}

export function streetHudLabel(hit: NamedStreetHud | null): string {
  return hit?.name ?? STREET_HUD_EMPTY;
}

export type MinimapHudLane = {
  id: string;
  name: string;
  role: StreetHudRole;
  streetId: string;
  coordinates: [number, number][];
};

export type MinimapHudLaneCount = {
  official: number;
  inner: number;
  total: number;
};

export type MinimapHudLaneCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    id: string;
    geometry: { type: "LineString"; coordinates: [number, number][] };
    properties: {
      id: string;
      kind: "hud-lane";
      name: string;
      role: StreetHudRole;
      streetId: string;
      active: number;
    };
  }>;
};

/** Same four HUD bands as lon/lat lines. Local memory only — not a GeoJSON street add. */
export function namedStreetHudLanesLonLat(
  streets: WorldStreet[],
  buildings: WorldBuilding[],
): MinimapHudLane[] {
  return namedStreetHudLanes(streets, buildings).map((lane) => ({
    id: lane.id,
    name: lane.name,
    role: lane.role,
    streetId: lane.streetId,
    coordinates: lane.points.map(([x, z]) => {
      const ll = worldToLngLat(x, z);
      return [ll.lon, ll.lat];
    }),
  }));
}

export function minimapHudLanesFromCollection(data: FeatureCollection): MinimapHudLane[] {
  return namedStreetHudLanesLonLat(
    worldFromCollection(data).streets,
    buildingsToWorld(buildingsFromCollection(data)),
  );
}

export function minimapHudLaneCollection(
  lanes: MinimapHudLane[],
  activeName = "",
): MinimapHudLaneCollection {
  return {
    type: "FeatureCollection",
    features: lanes.map((lane) => ({
      type: "Feature" as const,
      id: lane.id,
      geometry: { type: "LineString" as const, coordinates: lane.coordinates },
      properties: {
        id: lane.id,
        kind: "hud-lane" as const,
        name: lane.name,
        role: lane.role,
        streetId: lane.streetId,
        active: activeName && lane.name === activeName ? 1 : 0,
      },
    })),
  };
}

export function countMinimapHudLanes(lanes: MinimapHudLane[]): MinimapHudLaneCount {
  return {
    official: lanes.filter((row) => row.role === "official").length,
    inner: lanes.filter((row) => row.role === "inner").length,
    total: lanes.length,
  };
}

export function streetPlaqueSolids(plaques: StreetPlaque[]): BuildingPoly[] {
  return plaques
    .filter((row) => row.collide)
    .map((row) => solidFromWorld(row.id, row.x, row.z, PLAQUE_COLLIDE_HALF_M));
}

export function streetPlaqueSolidsFromCollection(data: FeatureCollection): BuildingPoly[] {
  return streetPlaqueSolids(streetPlaquesFromCollection(data));
}

export function streetPropSolids(props: StreetProps): BuildingPoly[] {
  return [
    ...props.lamps.map((lamp) => solidFromWorld(lamp.id, lamp.x, lamp.z, LAMP_COLLIDE_HALF_M)),
    ...props.planters.map((planter) =>
      solidFromWorld(planter.id, planter.x, planter.z, PLANTER_COLLIDE_HALF_M),
    ),
    ...props.scooters.map((scooter) =>
      solidFromWorld(scooter.id, scooter.x, scooter.z, SCOOTER_COLLIDE_HALF_M),
    ),
  ];
}

export function streetPropSolidsFromCollection(data: FeatureCollection): BuildingPoly[] {
  return streetPropSolids(streetPropsFromCollection(data));
}

export function countStreetProps(props: StreetProps): {
  lamps: number;
  glows: number;
  crosswalks: number;
  planters: number;
  scooters: number;
  innerLamps: number;
  innerScooters: number;
  stopLines: number;
  curbReturns: number;
} {
  return {
    lamps: props.lamps.length,
    glows: props.lamps.filter((lamp) => lamp.glow).length,
    crosswalks: props.crosswalks.length,
    planters: props.planters.length,
    scooters: props.scooters.length,
    innerLamps: props.lamps.filter((lamp) => isInnerStreetId(lamp.streetId)).length,
    innerScooters: props.scooters.filter((row) => isInnerStreetId(row.streetId)).length,
    stopLines: props.stopLines.length,
    curbReturns: props.curbReturns.length,
  };
}
