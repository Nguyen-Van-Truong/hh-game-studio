import { Html } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ACESFilmicToneMapping,
  BackSide,
  BasicShadowMap,
  CanvasTexture,
  ExtrudeGeometry,
  SRGBColorSpace,
  Shape,
  Vector3,
  type Camera,
  type DirectionalLight,
  type Group,
  type PerspectiveCamera,
} from "three";
import {
  armFootstepUnlock,
  cutFriendFootstepSeat,
  FOOTSTEP_KIND,
  HITCH_WARMUP_KIND,
  pruneFriendFootsteps,
  syncFriendFootstepSeats,
  tickFriendFootsteps,
  tickSelfFootsteps,
  warmupPlayAudio,
} from "../avatar/footsteps";
import type { LookMode, LookState } from "../avatar/look";
import {
  BLOCK_BOUND_KIND,
  COLLISION_KIND,
  GROUND_Y,
  hitBuildingId,
  isAtAoiBound,
  isInsideBuildingAabb,
  isInsideBuildingRing,
  ringAabb,
  SPAWN_KEEP_OUT_M,
  type AvatarState,
  type BuildingPoly,
} from "../avatar/walk";
import { AOI_BBOX } from "../map/aoi";
import type { FeatureCollection } from "../contracts/types";
import { isStreetFriend, VIEWING_SHOP_COPY, type VisibleFriend } from "../friends/presence";
import { DEMO_SEATS, type SeatId } from "../friends/seats";
import { stallBoardPaintTitles, stallBoardTitles } from "../shops/catalog";
import { isLocalShopId } from "../shops/localShops";
import type { Listing, Shop } from "../shops/types";
import {
  applyWalkPose,
  colorsForSeat,
  Person,
  SPRINT_RATE,
  tunicShirtForSeat,
  WALK_CYCLE_KIND,
  WALK_RATE,
  writeRemoteWalkCycleProof,
  writeWalkCycleProof,
  type PersonLimbs,
} from "./Person";
import {
  AMBIENT_INTENSITY,
  BLOCK_EDGE_KIND,
  blockEdgePieces,
  buildingsToWorld,
  CAM_HIT_KIND,
  cameraHitSolids,
  cameraPointInsideSolid,
  seatFollowSide,
  countBlockEdge,
  countFacadePieces,
  countGroundFloorPieces,
  countRoofPieces,
  BASKET_IN,
  countMarketSpill,
  CORNER_CROSSING_KIND,
  CORNER_CROSSWALK_ID,
  WEST_CROSSWALK_ID,
  TRAM_CROSSWALK_ID,
  isAuthoredMouthCrosswalk,
  countStreetProps,
  CROSSWALK_COLOR,
  CURB_COLOR,
  CURB_HEIGHT_M,
  curbSegments,
  EDGE_COLOR,
  edgeStripSegments,
  facadePiecesForBuilding,
  FAR_DETAIL_KIND,
  FAR_DETAIL_M,
  FILL_INTENSITY,
  FOG_FAR_M,
  FOG_KIND,
  FOG_NEAR_M,
  followPitchDeg,
  followRigYaw,
  resolveFollowCamera,
  GROUND_FLOOR_KIND,
  GROUND_KIND,
  isInnerStreet,
  isInnerStreetId,
  INNER_LANE_KIND,
  innerEdgeStripSegments,
  innerWalkSegments,
  innerWalkWidth,
  countInnerLanes,
  SIDE_STREET_KIND,
  streetRoadWidth,
  groundFloorFacesForBuilding,
  headingToYaw,
  HEMI_INTENSITY,
  LAMP_COLOR,
  LAMP_GLOW_COLOR,
  LAMP_LIGHT_COLOR,
  LIGHT_KIND,
  lngLatToWorld,
  lodSamplePoint,
  marketSpillForPlay,
  MARKET_SPILL_KIND,
  PERSON_SCALE,
  PLAQUE_COLOR,
  PLAQUE_CREAM,
  PLAQUE_POLE,
  PLANTER_BOX_COLOR,
  PLANTER_CANOPY_COLOR,
  PLANTER_TRUNK_COLOR,
  PLAZA_COLOR,
  plasterLift,
  ROAD_COLOR,
  ROOF_KIND,
  roofPiecesForBuilding,
  SCOOTER_BAR,
  SCOOTER_KIND,
  SCOOTER_PLASTIC,
  SCOOTER_WHEEL,
  shouldDrawGroundFloorFace,
  shouldDrawPlayHtml,
  shouldDrawScooter,
  PLAY_HTML_LOD_KIND,
  shopSignSpec,
  shopStallSpec,
  STALL_BOARD_CHALK,
  STALL_BOARD_FRAME,
  STALL_BOARD_HONESTY,
  STALL_BOARD_KIND,
  STALL_BOARD_SLATE,
  SHADOW_EXTENT_M,
  SHOP_STALL_KIND,
  SKY_CLEAR,
  SKY_DOME_R,
  SKY_FOG,
  SKY_GROUND_HAZE,
  SKY_HEMI_DOWN,
  SKY_HEMI_UP,
  SKY_HORIZON,
  SKY_KIND,
  SKY_MID,
  SKY_SUN,
  SKY_ZENITH,
  SLAB_SIZE_M,
  STREET_PROPS_KIND,
  STREET_HUD_KIND,
  STREET_PLAQUE_KIND,
  namedStreetHudAt,
  namedStreetHudLanes,
  streetHudLabel,
  streetPlaquesFromWorld,
  streetPropsFromCollection,
  streetPropsFromStreets,
  streetSegments,
  SUN_COLOR,
  SUN_DISC_R,
  SUN_INTENSITY,
  SUN_KEY,
  SUN_LOCAL,
  SURROUND_COLOR,
  SURROUND_SIZE_M,
  WALK_COLOR,
  walkSegments,
  WALL_FINISH_KIND,
  wallRoughnessForFinish,
  worldFromCollection,
  type BlockEdgePiece,
  type FacadeKind,
  type MarketSpillPiece,
  type StreetCrosswalk,
  type StreetCurbReturn,
  type StreetLamp,
  type StreetPlaque,
  type StreetPlanter,
  type StreetScooter,
  type StreetStopLine,
  type WorldBuilding,
  type WorldPark,
  type WorldStreet,
} from "./world";

function detectReducedMotion(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function closedRing(points: [number, number][]): [number, number][] {
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

function polygonGeometry(points: [number, number][], height: number, y0 = 0): ExtrudeGeometry {
  const shape = new Shape();
  const ring = closedRing(points);
  ring.forEach((pt, index) => {
    if (index === 0) {
      shape.moveTo(pt[0], -pt[1]);
    } else {
      shape.lineTo(pt[0], -pt[1]);
    }
  });
  const geo = new ExtrudeGeometry(shape, {
    depth: Math.max(0.06, height),
    bevelEnabled: false,
  });
  geo.rotateX(-Math.PI / 2);
  if (y0 !== 0) {
    geo.translate(0, y0, 0);
  }
  return geo;
}

function facadeRoughness(kind: FacadeKind): number {
  if (kind === "display") {
    return 0.16;
  }
  if (kind === "window") {
    return 0.28;
  }
  if (kind === "awning") {
    return 0.74;
  }
  return 0.88;
}

function facadeMetalness(kind: FacadeKind): number {
  if (kind === "display") {
    return 0.26;
  }
  if (kind === "window") {
    return 0.14;
  }
  return 0;
}

function BuildingMesh({
  building,
  streets,
  lodX,
  lodZ,
}: {
  building: WorldBuilding;
  streets: WorldStreet[];
  lodX: number;
  lodZ: number;
}) {
  const h = building.height_m;
  const wall = useMemo(() => polygonGeometry(building.points, h), [building.points, h]);
  const roof = useMemo(
    () => polygonGeometry(building.points, 0.28, h),
    [building.points, h],
  );
  const facades = useMemo(() => facadePiecesForBuilding(building), [building]);
  const ground = useMemo(
    () =>
      groundFloorFacesForBuilding(building, streets).flatMap((face) =>
        shouldDrawGroundFloorFace(face, lodX, lodZ) ? face.pieces : [],
      ),
    [building, lodX, lodZ, streets],
  );
  const roofs = useMemo(() => roofPiecesForBuilding(building), [building]);
  useEffect(
    () => () => {
      wall.dispose();
      roof.dispose();
    },
    [wall, roof],
  );
  return (
    <group
      name={building.id}
      userData={{
        kind: "building",
        mesh: "extrude",
        facade: "inset",
        groundFloor: ground.length > 0 ? GROUND_FLOOR_KIND : "none",
        roof: ROOF_KIND,
        finish: building.finish,
      }}
    >
      <mesh geometry={wall} castShadow receiveShadow name={`${building.id}-extrude`}>
        <meshStandardMaterial
          color={building.finish === "plaster" ? plasterLift(building.wall) : building.wall}
          roughness={wallRoughnessForFinish(building.finish)}
        />
      </mesh>
      <mesh geometry={roof} castShadow name={`${building.id}-roof`}>
        <meshStandardMaterial color={building.roof} roughness={0.62} />
      </mesh>
      {facades.map((piece, index) => (
        <mesh
          key={`${building.id}-${piece.kind}-${index}`}
          name={`${building.id}-${piece.kind}-${index}`}
          userData={{ kind: "facade", mesh: piece.kind }}
          position={[piece.x, piece.y, piece.z]}
          rotation={[0, piece.rotationY, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[piece.sx, piece.sy, piece.sz]} />
          <meshStandardMaterial
            color={piece.color}
            roughness={facadeRoughness(piece.kind)}
            metalness={facadeMetalness(piece.kind)}
          />
        </mesh>
      ))}
      {ground.map((piece, index) => (
        <mesh
          key={`${building.id}-gf-${piece.kind}-${index}`}
          name={`${building.id}-gf-${piece.kind}-${index}`}
          userData={{ kind: "ground-floor", mesh: piece.kind }}
          position={[piece.x, piece.y, piece.z]}
          rotation={[0, piece.rotationY, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[piece.sx, piece.sy, piece.sz]} />
          <meshStandardMaterial
            color={piece.color}
            roughness={facadeRoughness(piece.kind)}
            metalness={facadeMetalness(piece.kind)}
          />
        </mesh>
      ))}
      {roofs.map((piece, index) => (
        <mesh
          key={`${building.id}-rf-${piece.kind}-${index}`}
          name={`${building.id}-rf-${piece.kind}-${index}`}
          userData={{ kind: "roof", mesh: piece.kind }}
          position={[piece.x, piece.y, piece.z]}
          rotation={[0, piece.rotationY, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[piece.sx, piece.sy, piece.sz]} />
          <meshStandardMaterial
            color={piece.color}
            roughness={piece.kind === "ac" ? 0.38 : piece.kind === "tank" ? 0.48 : 0.78}
            metalness={piece.kind === "ac" ? 0.22 : piece.kind === "tank" ? 0.12 : 0}
          />
        </mesh>
      ))}
    </group>
  );
}

function ParkMesh({ park }: { park: WorldPark }) {
  const geo = useMemo(() => polygonGeometry(park.points, 0.08), [park]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <mesh geometry={geo} receiveShadow name={park.id}>
      <meshStandardMaterial color="#7fa86a" roughness={0.95} />
    </mesh>
  );
}

function LampPost({ lamp }: { lamp: StreetLamp }) {
  return (
    <group
      name={lamp.id}
      userData={{ kind: "lamp", glow: lamp.glow ? 1 : 0, street: lamp.streetId }}
      position={[lamp.x, 0, lamp.z]}
      rotation={[0, lamp.yaw, 0]}
    >
      <mesh name={`${lamp.id}-pole`} position={[0, 2.55, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.14, 5.1, 8]} />
        <meshStandardMaterial color={LAMP_COLOR} roughness={0.72} metalness={0.18} />
      </mesh>
      <mesh name={`${lamp.id}-arm`} position={[0, 5.02, 0.46]} castShadow>
        <boxGeometry args={[0.1, 0.1, 1.02]} />
        <meshStandardMaterial color={LAMP_COLOR} roughness={0.7} metalness={0.16} />
      </mesh>
      <mesh name={`${lamp.id}-head`} position={[0, 4.86, 0.88]} castShadow>
        <boxGeometry args={[0.36, 0.2, 0.46]} />
        <meshStandardMaterial color="#1c1e22" roughness={0.55} metalness={0.22} />
      </mesh>
      <mesh name={`${lamp.id}-glow`} position={[0, 4.72, 0.88]}>
        <sphereGeometry args={[0.16, 8, 8]} />
        <meshBasicMaterial color={LAMP_GLOW_COLOR} />
      </mesh>
      {lamp.glow ? (
          <pointLight
          name={`${lamp.id}-light`}
          color={LAMP_LIGHT_COLOR}
          intensity={0.68}
          distance={15}
          decay={2}
          position={[0, 4.72, 0.88]}
        />
      ) : null}
    </group>
  );
}

function CrosswalkBand({ spec }: { spec: StreetCrosswalk }) {
  const span = spec.stripes * spec.stripeAlong + (spec.stripes - 1) * spec.stripeGap;
  const start = -span / 2 + spec.stripeAlong / 2;
  const stripes = Array.from({ length: spec.stripes }, (_, index) => start + index * (spec.stripeAlong + spec.stripeGap));
  return (
    <group
      name={spec.id}
      userData={{ kind: "crosswalk" }}
      position={[spec.x, 0, spec.z]}
      rotation={[0, spec.rotationY, 0]}
    >
      {stripes.map((along, index) => (
        <mesh
          key={`${spec.id}-${index}`}
          name={`${spec.id}-stripe-${index}`}
          userData={{ kind: "crosswalk-stripe" }}
          position={[0, 0.09, along]}
          receiveShadow
        >
          <boxGeometry args={[spec.across, 0.055, spec.stripeAlong]} />
          <meshStandardMaterial color={CROSSWALK_COLOR} roughness={0.62} />
        </mesh>
      ))}
    </group>
  );
}

function StopLineMark({ spec }: { spec: StreetStopLine }) {
  return (
    <mesh
      name={spec.id}
      userData={{ kind: "stop-line" }}
      position={[spec.x, 0.076, spec.z]}
      rotation={[0, spec.rotationY, 0]}
      receiveShadow
    >
      <boxGeometry args={[spec.across, 0.03, spec.thick]} />
      <meshStandardMaterial color={CROSSWALK_COLOR} roughness={0.6} />
    </mesh>
  );
}

function CurbReturnLip({ spec }: { spec: StreetCurbReturn }) {
  return (
    <mesh
      name={spec.id}
      userData={{ kind: "curb-return" }}
      position={[spec.x, CURB_HEIGHT_M / 2, spec.z]}
      rotation={[0, spec.rotationY, 0]}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[spec.width, CURB_HEIGHT_M, spec.length]} />
      <meshStandardMaterial color={CURB_COLOR} roughness={0.88} />
    </mesh>
  );
}

function PlanterMass({ planter }: { planter: StreetPlanter }) {
  return (
    <group
      name={planter.id}
      userData={{ kind: "planter" }}
      position={[planter.x, 0, planter.z]}
    >
      <mesh name={`${planter.id}-box`} position={[0, 0.22, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.15, 0.44, 1.15]} />
        <meshStandardMaterial color={PLANTER_BOX_COLOR} roughness={0.9} />
      </mesh>
      <mesh name={`${planter.id}-trunk`} position={[0, 1.15, 0]} castShadow>
        <cylinderGeometry args={[0.13, 0.16, 1.5, 8]} />
        <meshStandardMaterial color={PLANTER_TRUNK_COLOR} roughness={0.88} />
      </mesh>
      <mesh name={`${planter.id}-canopy`} position={[0, 2.15, 0]} castShadow>
        <boxGeometry args={[1.85, 1.35, 1.75]} />
        <meshStandardMaterial color={PLANTER_CANOPY_COLOR} roughness={0.92} />
      </mesh>
    </group>
  );
}

/** Parked box scooter. STATIC prop — no rider, no traffic AI. */
function ParkedScooter({ scooter }: { scooter: StreetScooter }) {
  return (
    <group
      name={scooter.id}
      userData={{ kind: "scooter", color: scooter.color, street: scooter.streetId }}
      position={[scooter.x, 0, scooter.z]}
      rotation={[0, scooter.yaw, 0]}
      scale={1.34}
    >
      <mesh name={`${scooter.id}-deck`} position={[0, 0.3, -0.04]} castShadow receiveShadow>
        <boxGeometry args={[0.4, 0.09, 1.36]} />
        <meshStandardMaterial color={SCOOTER_PLASTIC} roughness={0.78} />
      </mesh>
      <mesh name={`${scooter.id}-body`} position={[0, 0.56, -0.14]} castShadow receiveShadow>
        <boxGeometry args={[0.46, 0.42, 0.86]} />
        <meshStandardMaterial color={scooter.color} roughness={0.5} />
      </mesh>
      <mesh name={`${scooter.id}-seat`} position={[0, 0.8, -0.2]} castShadow>
        <boxGeometry args={[0.3, 0.11, 0.52]} />
        <meshStandardMaterial color={SCOOTER_PLASTIC} roughness={0.86} />
      </mesh>
      <mesh name={`${scooter.id}-wheel-r`} position={[0, 0.22, -0.6]} castShadow receiveShadow>
        <boxGeometry args={[0.12, 0.44, 0.44]} />
        <meshStandardMaterial color={SCOOTER_WHEEL} roughness={0.92} />
      </mesh>
      <mesh name={`${scooter.id}-wheel-f`} position={[0, 0.22, 0.62]} castShadow receiveShadow>
        <boxGeometry args={[0.12, 0.44, 0.44]} />
        <meshStandardMaterial color={SCOOTER_WHEEL} roughness={0.92} />
      </mesh>
      <mesh name={`${scooter.id}-fork`} position={[0, 0.56, 0.54]} castShadow>
        <boxGeometry args={[0.08, 0.5, 0.08]} />
        <meshStandardMaterial color={SCOOTER_BAR} roughness={0.7} />
      </mesh>
      <mesh name={`${scooter.id}-bar`} position={[0, 0.9, 0.58]} castShadow>
        <boxGeometry args={[0.72, 0.08, 0.08]} />
        <meshStandardMaterial color={SCOOTER_BAR} roughness={0.62} />
      </mesh>
      <mesh name={`${scooter.id}-lamp`} position={[0, 0.62, 0.76]} castShadow>
        <boxGeometry args={[0.18, 0.11, 0.09]} />
        <meshStandardMaterial color="#d8c48a" roughness={0.35} />
      </mesh>
    </group>
  );
}

/** Authored market spill. Boxes/cylinders only — not a real inventory. */
function MarketSpillProp({ piece }: { piece: MarketSpillPiece }) {
  return (
    <group
      name={piece.id}
      userData={{
        kind: "market-spill",
        mesh: piece.kind,
        shop: piece.shop_id ?? "",
        source: piece.source,
        collide: piece.collide ? 1 : 0,
        color: piece.color,
      }}
      position={[piece.x, 0, piece.z]}
      rotation={[0, piece.yaw, 0]}
    >
      {piece.kind === "crate" ? (
        <>
          <mesh name={`${piece.id}-box`} position={[0, 0.22, 0]} castShadow receiveShadow>
            <boxGeometry args={[0.62, 0.44, 0.52]} />
            <meshStandardMaterial color={piece.color} roughness={0.86} />
          </mesh>
          <mesh name={`${piece.id}-lid`} position={[0, 0.45, 0]} castShadow>
            <boxGeometry args={[0.66, 0.06, 0.56]} />
            <meshStandardMaterial color={piece.accent} roughness={0.8} />
          </mesh>
        </>
      ) : null}
      {piece.kind === "stack" ? (
        <>
          <mesh name={`${piece.id}-low`} position={[0, 0.2, 0]} castShadow receiveShadow>
            <boxGeometry args={[0.7, 0.4, 0.58]} />
            <meshStandardMaterial color={piece.color} roughness={0.88} />
          </mesh>
          <mesh name={`${piece.id}-mid`} position={[0.04, 0.52, 0.02]} castShadow>
            <boxGeometry args={[0.56, 0.28, 0.46]} />
            <meshStandardMaterial color={piece.accent} roughness={0.84} />
          </mesh>
          <mesh name={`${piece.id}-top`} position={[-0.06, 0.76, -0.03]} castShadow>
            <boxGeometry args={[0.42, 0.2, 0.36]} />
            <meshStandardMaterial color={piece.color} roughness={0.82} />
          </mesh>
        </>
      ) : null}
      {piece.kind === "cooler" ? (
        <>
          <mesh name={`${piece.id}-body`} position={[0, 0.28, 0]} castShadow receiveShadow>
            <boxGeometry args={[0.78, 0.56, 0.52]} />
            <meshStandardMaterial color={piece.color} roughness={0.42} />
          </mesh>
          <mesh name={`${piece.id}-lid`} position={[0, 0.58, 0]} castShadow>
            <boxGeometry args={[0.82, 0.08, 0.56]} />
            <meshStandardMaterial color={piece.accent} roughness={0.38} />
          </mesh>
        </>
      ) : null}
      {piece.kind === "basket" ? (
        <>
          <mesh name={`${piece.id}-bowl`} position={[0, 0.16, 0]} castShadow receiveShadow>
            <cylinderGeometry args={[0.32, 0.26, 0.22, 10]} />
            <meshStandardMaterial color={piece.color} roughness={0.9} />
          </mesh>
          <mesh name={`${piece.id}-goods`} position={[0, 0.28, 0]} castShadow>
            <cylinderGeometry args={[0.2, 0.22, 0.1, 8]} />
            <meshStandardMaterial color={piece.accent} roughness={0.78} />
          </mesh>
          <mesh name={`${piece.id}-rim`} position={[0, 0.27, 0]} castShadow>
            <cylinderGeometry args={[0.33, 0.33, 0.04, 10]} />
            <meshStandardMaterial color={BASKET_IN} roughness={0.72} />
          </mesh>
        </>
      ) : null}
    </group>
  );
}

function makeSkyGradientTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 8;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("sky canvas");
  }
  const g = ctx.createLinearGradient(0, 0, 0, 256);
  g.addColorStop(0, SKY_ZENITH);
  g.addColorStop(0.58, SKY_MID);
  g.addColorStop(0.82, SKY_HORIZON);
  g.addColorStop(1, SKY_GROUND_HAZE);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 8, 256);
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function makeShopSignTexture(name: string, selected: boolean): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("shop sign canvas");
  }
  ctx.fillStyle = selected ? "#e06a18" : "#9a2f0e";
  ctx.fillRect(0, 0, 768, 256);
  ctx.fillStyle = "#fff3d0";
  ctx.fillRect(0, 0, 768, 14);
  ctx.fillRect(0, 242, 768, 14);
  ctx.fillStyle = "#ffd36a";
  ctx.fillRect(22, 58, 92, 92);
  ctx.fillStyle = "#141814";
  ctx.font = "bold 68px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("E", 68, 106);
  ctx.fillStyle = "#fff8ee";
  ctx.font = "bold 52px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(name.slice(0, 18), 136, 104);
  ctx.font = "bold 28px system-ui, sans-serif";
  ctx.fillStyle = "#ffe7c2";
  ctx.fillText("shop · hold E at the stall", 136, 168);
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function makeMenuBoardTexture(titles: string[]): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 640;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("stall board canvas");
  }
  ctx.fillStyle = STALL_BOARD_SLATE;
  ctx.fillRect(0, 0, 1024, 640);
  ctx.strokeStyle = STALL_BOARD_FRAME;
  ctx.lineWidth = 28;
  ctx.strokeRect(14, 14, 996, 612);
  ctx.fillStyle = "rgba(232,217,168,0.09)";
  for (let i = 0; i < 72; i += 1) {
    ctx.fillRect((i * 97) % 1000, (i * 53) % 620, 3, 2);
  }
  ctx.fillStyle = STALL_BOARD_CHALK;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "bold 40px system-ui, Segoe UI, sans-serif";
  ctx.fillText("Hôm nay / today", 512, 86);
  ctx.font = "bold 78px system-ui, Segoe UI, sans-serif";
  const lines = titles.slice(0, 3);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    ctx.fillText(line.slice(0, 22), 512, 210 + i * 118);
  }
  ctx.font = "bold 30px system-ui, Segoe UI, sans-serif";
  ctx.fillStyle = "#c8b888";
  ctx.fillText(STALL_BOARD_HONESTY, 512, 562);
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function makeEPlaqueTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("E plaque canvas");
  }
  ctx.fillStyle = "#243028";
  ctx.fillRect(0, 0, 64, 64);
  ctx.fillStyle = "#f0b15a";
  ctx.font = "bold 44px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("E", 32, 36);
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function makeStreetPlaqueTexture(name: string, line2: string): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 224;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("street plaque canvas");
  }
  ctx.fillStyle = PLAQUE_COLOR;
  ctx.fillRect(0, 0, 640, 224);
  ctx.fillStyle = PLAQUE_CREAM;
  ctx.fillRect(0, 0, 640, 12);
  ctx.fillRect(0, 212, 640, 12);
  ctx.fillRect(0, 0, 12, 224);
  ctx.fillRect(628, 0, 12, 224);
  ctx.fillStyle = PLAQUE_CREAM;
  ctx.font = "bold 54px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(name.slice(0, 18), 320, 92);
  ctx.font = "bold 26px system-ui, sans-serif";
  ctx.fillStyle = "#d8c89a";
  ctx.fillText(line2.slice(0, 22), 320, 154);
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function StreetPlaquePole({
  plaque,
  playerX,
  playerZ,
}: {
  plaque: StreetPlaque;
  playerX: number;
  playerZ: number;
}) {
  const boardTex = useMemo(
    () => makeStreetPlaqueTexture(plaque.name, plaque.line2),
    [plaque.line2, plaque.name],
  );
  useEffect(
    () => () => {
      boardTex.dispose();
    },
    [boardTex],
  );
  return (
    <group
      name={plaque.id}
      userData={{ kind: "street-plaque", mesh: plaque.kind, street: plaque.streetId, role: plaque.role }}
      position={[plaque.x, 0, plaque.z]}
    >
      <mesh name={`${plaque.id}-pole`} position={[0, plaque.poleH / 2, 0]} castShadow>
        <cylinderGeometry args={[0.06, 0.08, plaque.poleH, 8]} />
        <meshStandardMaterial color={PLAQUE_POLE} roughness={0.84} />
      </mesh>
      <mesh
        name={`${plaque.id}-board`}
        userData={{ kind: "street-plaque-board", face: "front" }}
        position={[0, plaque.boardY, 0]}
        rotation={[0, plaque.yaw, 0]}
        castShadow
      >
        <boxGeometry args={[plaque.boardW, plaque.boardH, 0.1]} />
        <meshBasicMaterial map={boardTex} />
      </mesh>
      <mesh
        name={`${plaque.id}-board-back`}
        userData={{ kind: "street-plaque-board", face: "back" }}
        position={[0, plaque.boardY, 0]}
        rotation={[0, plaque.yaw + Math.PI, 0]}
        castShadow
      >
        <boxGeometry args={[plaque.boardW, plaque.boardH, 0.1]} />
        <meshBasicMaterial map={boardTex} />
      </mesh>
      {shouldDrawPlayHtml(plaque.x, plaque.z, playerX, playerZ) ? (
      <Html position={[0, plaque.boardY + 0.72, 0]} center distanceFactor={24} style={{ pointerEvents: "none" }}>
        <div
          className="play-plaque-label"
          data-testid={`street-plaque-label-${plaque.id}`}
          data-street={plaque.streetId}
          data-role={plaque.role}
          data-name={plaque.name}
        >
          {plaque.name}
        </div>
      </Html>
      ) : null}
    </group>
  );
}

function BlockEdgeMesh({ piece }: { piece: BlockEdgePiece }) {
  return (
    <mesh
      name={piece.id}
      userData={{ kind: piece.kind, bound: BLOCK_EDGE_KIND }}
      position={[piece.x, piece.y, piece.z]}
      castShadow={piece.kind === "wall" || piece.kind === "cope"}
      receiveShadow
    >
      <boxGeometry args={[piece.sx, piece.sy, piece.sz]} />
      <meshStandardMaterial
        color={piece.color}
        roughness={piece.kind === "lot" ? 0.28 : piece.kind === "cope" ? 0.55 : 0.88}
        metalness={piece.kind === "lot" ? 0.18 : 0}
      />
    </mesh>
  );
}

function SkyHemisphere() {
  const skyTex = useMemo(() => makeSkyGradientTexture(), []);
  useEffect(
    () => () => {
      skyTex.dispose();
    },
    [skyTex],
  );
  return (
    <group name="sky-hemisphere" userData={{ kind: "sky", mesh: SKY_KIND }}>
      <mesh name="sky-dome" userData={{ kind: "sky-dome" }}>
        <sphereGeometry args={[SKY_DOME_R, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshBasicMaterial map={skyTex} side={BackSide} fog={false} depthWrite={false} />
      </mesh>
      <mesh
        name="sky-ring"
        userData={{ kind: "sky-ring" }}
        position={[0, 42, 0]}
      >
        <cylinderGeometry args={[SKY_DOME_R - 4, SKY_DOME_R - 4, 140, 32, 1, true]} />
        <meshBasicMaterial color={SKY_ZENITH} side={BackSide} fog={false} depthWrite={false} />
      </mesh>
      <mesh
        name="sun-disc"
        userData={{ kind: "sun" }}
        position={[SUN_LOCAL[0], SUN_LOCAL[1], SUN_LOCAL[2]]}
      >
        <sphereGeometry args={[SUN_DISC_R, 16, 12]} />
        <meshBasicMaterial color={SKY_SUN} fog={false} />
      </mesh>
    </group>
  );
}

function ShopPole({
  shop,
  listings,
  selected,
  onSelect,
  streets,
  playerX,
  playerZ,
}: {
  shop: Shop;
  listings: Listing[];
  selected: boolean;
  onSelect: (id: string) => void;
  streets: WorldStreet[];
  playerX: number;
  playerZ: number;
}) {
  const spec = shopSignSpec(shop, streets);
  const stall = shopStallSpec(shop, streets);
  const htmlLive = shouldDrawPlayHtml(spec.x, spec.z, playerX, playerZ);
  const menuTitles = useMemo(
    () => stallBoardPaintTitles(stallBoardTitles(listings, shop.shop_id)),
    [listings, shop.shop_id],
  );
  const menuKey = menuTitles.join("\u0000");
  const boardTex = useMemo(
    () => makeShopSignTexture(shop.name, selected),
    [shop.name, selected],
  );
  const menuTex = useMemo(
    () => (menuTitles.length === 0 ? null : makeMenuBoardTexture(menuTitles)),
    [menuKey, menuTitles.length],
  );
  const eTex = useMemo(() => makeEPlaqueTexture(), []);
  useEffect(
    () => () => {
      boardTex.dispose();
    },
    [boardTex],
  );
  useEffect(
    () => () => {
      menuTex?.dispose();
    },
    [menuTex],
  );
  useEffect(
    () => () => {
      eTex.dispose();
    },
    [eTex],
  );
  return (
    <group
      name={`shop-sign-${shop.shop_id}`}
      userData={{
        kind: "shop-sign",
        mesh: spec.kind,
        stall: stall.kind,
        shop_id: shop.shop_id,
      }}
      position={[spec.x, 0, spec.z]}
    >
      <group
        name={`shop-stall-${shop.shop_id}`}
        userData={{
          kind: "shop-stall",
          mesh: stall.kind,
          shop_id: shop.shop_id,
          collide: stall.collide ? 1 : 0,
          awning: stall.awning,
        }}
        position={[stall.x - spec.x, 0, stall.z - spec.z]}
      >
        <mesh
          name={`shop-kiosk-${shop.shop_id}`}
          userData={{ kind: "shop-kiosk" }}
          position={[0, 0.86, 1.12]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[2.65, 1.72, 0.62]} />
          <meshStandardMaterial color={stall.body} roughness={0.86} />
        </mesh>
        <mesh
          name={`shop-counter-${shop.shop_id}`}
          userData={{ kind: "shop-counter" }}
          position={[0, 0.45, 0.38]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[2.55, 0.9, 0.68]} />
          <meshStandardMaterial color={stall.counter} roughness={0.78} />
        </mesh>
        <mesh
          name={`shop-post-l-${shop.shop_id}`}
          userData={{ kind: "shop-post" }}
          position={[-1.18, 1.24, 0.62]}
          castShadow
        >
          <cylinderGeometry args={[0.08, 0.1, 2.48, 8]} />
          <meshStandardMaterial color={stall.post} roughness={0.8} />
        </mesh>
        <mesh
          name={`shop-post-r-${shop.shop_id}`}
          userData={{ kind: "shop-post" }}
          position={[1.18, 1.24, 0.62]}
          castShadow
        >
          <cylinderGeometry args={[0.08, 0.1, 2.48, 8]} />
          <meshStandardMaterial color={stall.post} roughness={0.8} />
        </mesh>
        <mesh
          name={`shop-awning-${shop.shop_id}`}
          userData={{ kind: "shop-awning", color: stall.awning }}
          position={[0, stall.awningY, 0.55]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[stall.awningW, stall.awningH, stall.awningD]} />
          <meshStandardMaterial color={stall.awning} roughness={0.7} />
        </mesh>
        <mesh
          name={`shop-awning-stripe-${shop.shop_id}`}
          userData={{ kind: "shop-awning-stripe" }}
          position={[0, stall.awningY - 0.1, -0.92]}
          castShadow
        >
          <boxGeometry args={[stall.awningW + 0.04, 0.1, 0.22]} />
          <meshStandardMaterial color={stall.stripe} roughness={0.55} />
        </mesh>
        {menuTex ? (
          <>
            <mesh
              name={`shop-menu-${shop.shop_id}`}
              userData={{
                kind: "shop-menu-board",
                mesh: STALL_BOARD_KIND,
                titles: menuTitles.join("|"),
              }}
              position={[0, 1.34, 0.78]}
              castShadow
            >
              <boxGeometry args={[2.28, 1.12, 0.06]} />
              <meshBasicMaterial map={menuTex} />
            </mesh>
            <mesh
              name={`shop-menu-side-${shop.shop_id}`}
              userData={{ kind: "shop-menu-board", face: "east", mesh: STALL_BOARD_KIND }}
              position={[1.36, 1.28, 1.12]}
              rotation={[0, Math.PI / 2, 0]}
              castShadow
            >
              <boxGeometry args={[0.98, 0.98, 0.05]} />
              <meshBasicMaterial map={menuTex} />
            </mesh>
          </>
        ) : null}
        {menuTex && htmlLive ? (
          <Html
            position={[0, 1.42, 0.7]}
            center
            distanceFactor={15}
            style={{ pointerEvents: "none" }}
          >
            <div
              className="play-menu-board"
              data-testid={`shop-menu-board-${shop.shop_id}`}
              data-shop-id={shop.shop_id}
              data-source={isLocalShopId(shop.shop_id) ? "local-demo" : "authored"}
              data-kind={STALL_BOARD_KIND}
              data-titles={menuTitles.join(" | ")}
              data-honesty={STALL_BOARD_HONESTY}
            >
              {menuTitles.map((title) => (
                <span key={title}>{title}</span>
              ))}
              <small>{STALL_BOARD_HONESTY}</small>
            </div>
          </Html>
        ) : null}
      </group>
      <mesh
        name={`shop-pole-${shop.shop_id}`}
        position={[0, spec.poleH / 2, 0]}
        castShadow
      >
        <cylinderGeometry args={[0.07, 0.09, spec.poleH, 8]} />
        <meshStandardMaterial color="#5c3a22" roughness={0.82} />
      </mesh>
      <mesh
        name={`shop-board-${shop.shop_id}`}
        userData={{ kind: "shop-board", face: "south" }}
        position={[0, spec.boardY, 0]}
        rotation={[0, spec.yaw, 0]}
        castShadow
      >
        <boxGeometry args={[spec.boardW, spec.boardH, 0.12]} />
        <meshBasicMaterial map={boardTex} />
      </mesh>
      <mesh
        name={`shop-board-back-${shop.shop_id}`}
        userData={{ kind: "shop-board", face: "north" }}
        position={[0, spec.boardY, 0]}
        rotation={[0, spec.yaw + Math.PI, 0]}
        castShadow
      >
        <boxGeometry args={[spec.boardW, spec.boardH, 0.12]} />
        <meshBasicMaterial map={boardTex} />
      </mesh>
      <mesh
        name={`shop-e-${shop.shop_id}`}
        userData={{ kind: "shop-e" }}
        position={[0, 1.58, 0]}
        castShadow
      >
        <boxGeometry args={[0.46, 0.46, 0.1]} />
        <meshBasicMaterial map={eTex} />
      </mesh>
      {htmlLive ? (
      <Html
        position={[0, spec.boardY + 0.82, 0]}
        center
        distanceFactor={22}
        style={{ pointerEvents: "auto" }}
      >
        <button
          type="button"
          className={selected ? "play-shop-label is-active" : "play-shop-label"}
          data-testid={`shop-marker-${shop.shop_id}`}
          data-shop-id={shop.shop_id}
          data-kind={spec.kind}
          data-stall={stall.kind}
          data-awning={stall.awning}
          data-e={spec.eHint}
          data-lon={shop.lon.toFixed(7)}
          data-lat={shop.lat.toFixed(7)}
          data-source={shop.shop_id.startsWith("shop-local-") ? "local-demo" : "authored"}
          onClick={(event) => {
            event.stopPropagation();
            onSelect(shop.shop_id);
          }}
        >
          Shop · {shop.name}
        </button>
      </Html>
      ) : null}
    </group>
  );
}

function writeSelfScreen(x: number, y: number, onCanvas: boolean): void {
  const el = document.querySelector('[data-testid="self-avatar"]');
  if (el instanceof HTMLElement) {
    el.dataset.screenX = x.toFixed(1);
    el.dataset.screenY = y.toFixed(1);
    el.dataset.onCanvas = onCanvas ? "1" : "0";
  }
}

function writeRemoteScreen(seat: string, x: number, y: number, onCanvas: boolean): void {
  const sx = x.toFixed(1);
  const sy = y.toFixed(1);
  const vis = onCanvas ? "1" : "0";
  for (const sel of [
    `[data-testid="remote-avatar-${seat}"]`,
    `[data-testid="remote-body-${seat}"]`,
    `[data-testid="remote-walk-cycle-${seat}"]`,
  ]) {
    const el = document.querySelector(sel);
    if (el instanceof HTMLElement) {
      el.dataset.screenX = sx;
      el.dataset.screenY = sy;
      el.dataset.onCanvas = vis;
    }
  }
}

/** Drei Html portals outlive the Walker mesh for one paint if cleanup is useEffect. */
function dropStreetNametag(seat: string): void {
  for (const node of document.querySelectorAll(
    `[data-testid="remote-avatar-${seat}"].play-remote-label`,
  )) {
    node.remove();
  }
}

function dropLeftoverStreetNametags(keep: ReadonlySet<string>): void {
  for (const node of document.querySelectorAll("div.play-remote-label[data-testid^='remote-avatar-']")) {
    const testid = node.getAttribute("data-testid") ?? "";
    const seat = testid.slice("remote-avatar-".length);
    if (seat && !keep.has(seat)) {
      node.remove();
    }
  }
}

function Walker({
  state,
  seat,
  self,
  label,
  listenerX = 0,
  listenerZ = 0,
}: {
  state: AvatarState;
  seat: SeatId;
  self: boolean;
  label?: string;
  listenerX?: number;
  listenerZ?: number;
}) {
  const group = useRef<Group>(null);
  const limbsRef = useRef<PersonLimbs | null>(null);
  const reduced = detectReducedMotion();
  const pos = lngLatToWorld(state.lon, state.lat);
  const colors = colorsForSeat(seat);
  const camera = useThree((three) => three.camera);
  const gl = useThree((three) => three.gl);

  useLayoutEffect(() => {
    if (self) {
      return;
    }
    return () => {
      cutFriendFootstepSeat(seat);
      dropStreetNametag(seat);
    };
  }, [self, seat]);

  useFrame(({ clock }) => {
    const node = group.current;
    if (!node) {
      return;
    }
    node.position.set(pos.x, GROUND_Y + state.alt, pos.z);
    node.rotation.y = headingToYaw(state.heading);
    const moving = state.pose === "walk" && !state.airborne;
    const strideTime =
      clock.elapsedTime * (moving ? (state.sprint ? SPRINT_RATE : WALK_RATE) : state.turning ? 4.4 : 1);
    applyWalkPose(
      limbsRef.current,
      strideTime,
      moving,
      reduced,
      state.airborne,
      state.sprint,
      state.turning,
    );
    if (self) {
      tickSelfFootsteps(strideTime, {
        moving,
        airborne: state.airborne,
        sprint: state.sprint && moving,
      });
      const projected = new Vector3(pos.x, 1.15 + state.alt, pos.z).project(camera);
      const rect = gl.domElement.getBoundingClientRect();
      const sx = rect.left + (projected.x * 0.5 + 0.5) * rect.width;
      const sy = rect.top + (-projected.y * 0.5 + 0.5) * rect.height;
      const onCanvas =
        projected.z > -1 &&
        projected.z < 1 &&
        sx > rect.left + 8 &&
        sx < rect.right - 8 &&
        sy > rect.top + 8 &&
        sy < rect.bottom - 8;
      writeSelfScreen(sx, sy, onCanvas);
    } else {
      tickFriendFootsteps(seat, strideTime, {
        moving,
        airborne: state.airborne,
        sprint: state.sprint && moving,
        distM: Math.hypot(pos.x - listenerX, pos.z - listenerZ),
      });
    }
    if (limbsRef.current) {
      if (self) {
        writeWalkCycleProof(limbsRef.current, moving, state.sprint && moving);
      } else {
        writeRemoteWalkCycleProof(seat, limbsRef.current, moving, state.sprint && moving);
        const projected = new Vector3(pos.x, 1.15 + state.alt, pos.z).project(camera);
        const rect = gl.domElement.getBoundingClientRect();
        const sx = rect.left + (projected.x * 0.5 + 0.5) * rect.width;
        const sy = rect.top + (-projected.y * 0.5 + 0.5) * rect.height;
        const onCanvas =
          projected.z > -1 &&
          projected.z < 1 &&
          sx > rect.left + 8 &&
          sx < rect.right - 8 &&
          sy > rect.top + 8 &&
          sy < rect.bottom - 8;
        writeRemoteScreen(seat, sx, sy, onCanvas);
      }
    }
  });

  return (
    <group
      ref={group}
      position={[pos.x, GROUND_Y + state.alt, pos.z]}
      rotation={[0, headingToYaw(state.heading), 0]}
      scale={PERSON_SCALE}
      name={self ? "self-walker" : `remote-${seat}`}
    >
      <Person colors={colors} limbsRef={limbsRef} />
      {self ? null : (
        <Html position={[0, 2.05, 0]} center distanceFactor={16} style={{ pointerEvents: "none" }}>
          <div
            className="play-remote-label"
            data-testid={`remote-avatar-${seat}`}
            data-remote-avatar={seat}
            data-seat={seat}
            data-body="tunic-humanoid"
            data-walk-cycle={WALK_CYCLE_KIND}
            data-tunic={colors.shirt}
            data-pose={state.pose}
            data-heading={String(Math.round(state.heading))}
            data-lon={state.lon.toFixed(7)}
            data-lat={state.lat.toFixed(7)}
            data-friend-footsteps="0"
            style={{ borderLeft: `4px solid ${colors.shirt}` }}
          >
            {label ?? DEMO_SEATS[seat].short_name}
          </div>
        </Html>
      )}
    </group>
  );
}

function applyFollowCamera(
  camera: Camera,
  avatar: AvatarState,
  look: LookState,
  solids: BuildingPoly[],
  side: number,
): void {
  const pose = resolveFollowCamera(
    lngLatToWorld(avatar.lon, avatar.lat),
    followRigYaw(avatar.heading, look.mode, look.yaw, look.pitch),
    solids,
    avatar.alt,
    followPitchDeg(look.mode, look.pitch),
    undefined,
    undefined,
    side,
  );
  const cam = camera as PerspectiveCamera;
  cam.position.set(pose.x, pose.y, pose.z);
  cam.lookAt(pose.lookX, pose.lookY, pose.lookZ);
  cam.updateProjectionMatrix();
}

function FollowCamera({
  avatar,
  look,
  solids,
  side,
}: {
  avatar: AvatarState;
  look: LookState;
  solids: BuildingPoly[];
  side: number;
}) {
  const camera = useThree((state) => state.camera);

  useLayoutEffect(() => {
    applyFollowCamera(camera, avatar, look, solids, side);
  }, [camera, avatar, look, solids, side]);

  useFrame(() => {
    applyFollowCamera(camera, avatar, look, solids, side);
  });
  return null;
}

function PlayLook({
  onLookDelta,
  onLookMode,
}: {
  onLookDelta: (dx: number, dy: number) => void;
  onLookMode: (mode: LookMode) => void;
}) {
  const gl = useThree((state) => state.gl);
  const deltaRef = useRef(onLookDelta);
  const modeRef = useRef(onLookMode);
  deltaRef.current = onLookDelta;
  modeRef.current = onLookMode;

  useEffect(() => {
    const el = gl.domElement;
    el.tabIndex = 0;
    el.style.cursor = "grab";
    el.dataset.lookHint = "click-or-right-drag";
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onContextMenu = (event: Event) => {
      event.preventDefault();
    };
    const onPointerDown = (event: PointerEvent) => {
      if (event.button === 2) {
        event.preventDefault();
        dragging = true;
        lastX = event.clientX;
        lastY = event.clientY;
        el.style.cursor = "grabbing";
        try {
          el.setPointerCapture(event.pointerId);
        } catch {
          /* capture is optional */
        }
        modeRef.current("drag");
        return;
      }
      if (event.button === 0 && event.target === el) {
        const lock = el.requestPointerLock?.();
        if (lock && typeof (lock as Promise<void>).catch === "function") {
          void (lock as Promise<void>).catch(() => {
            /* headless / denied: right-drag still looks */
          });
        }
      }
    };
    const onPointerMove = (event: PointerEvent) => {
      if (document.pointerLockElement === el) {
        deltaRef.current(event.movementX, event.movementY);
        return;
      }
      if (!dragging) {
        return;
      }
      deltaRef.current(event.clientX - lastX, event.clientY - lastY);
      lastX = event.clientX;
      lastY = event.clientY;
    };
    const endDrag = (event: PointerEvent) => {
      if (!dragging) {
        return;
      }
      if (event.button !== 2 && event.type !== "pointercancel") {
        return;
      }
      dragging = false;
      el.style.cursor = document.pointerLockElement === el ? "none" : "grab";
      if (document.pointerLockElement !== el) {
        modeRef.current("off");
      }
    };
    const onLockChange = () => {
      if (document.pointerLockElement === el) {
        el.style.cursor = "none";
        modeRef.current("pointer-lock");
        return;
      }
      el.style.cursor = dragging ? "grabbing" : "grab";
      if (!dragging) {
        modeRef.current("off");
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (document.pointerLockElement === el) {
          document.exitPointerLock();
        }
        if (dragging) {
          dragging = false;
          el.style.cursor = "grab";
          modeRef.current("off");
        }
      }
    };
    el.addEventListener("contextmenu", onContextMenu);
    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    document.addEventListener("pointerlockchange", onLockChange);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      el.removeEventListener("contextmenu", onContextMenu);
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", endDrag);
      el.removeEventListener("pointercancel", endDrag);
      document.removeEventListener("pointerlockchange", onLockChange);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [gl]);

  return null;
}

/** Skip GPU work while the tab is hidden. Does not claim R2-WP1. */
function PlayLoopGate() {
  const set = useThree((state) => state.set);
  const invalidate = useThree((state) => state.invalidate);

  useEffect(() => {
    const sync = () => {
      if (typeof document !== "undefined" && document.hidden) {
        set({ frameloop: "never" });
        return;
      }
      set({ frameloop: "always" });
      invalidate();
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => {
      document.removeEventListener("visibilitychange", sync);
    };
  }, [invalidate, set]);

  return null;
}

/** Resume audio + one silent plant + one scene compile after first paint. */
function HitchWarmup() {
  const gl = useThree((state) => state.gl);
  const scene = useThree((state) => state.scene);
  const camera = useThree((state) => state.camera);
  const done = useRef(false);
  const frames = useRef(0);

  useLayoutEffect(() => {
    warmupPlayAudio();
  }, []);

  useFrame(() => {
    frames.current += 1;
    if (done.current || frames.current < 2) {
      return;
    }
    done.current = true;
    warmupPlayAudio();
    try {
      gl.compile(scene, camera);
    } catch {
      /* compile is optional; street already painted */
    }
  });
  return null;
}

function FirstFrameReady({
  ok,
  onReady,
}: {
  ok: boolean;
  onReady?: () => void;
}) {
  const size = useThree((state) => state.size);
  const gl = useThree((state) => state.gl);
  const sent = useRef(false);

  useFrame(() => {
    if (sent.current || !ok || !onReady) {
      return;
    }
    if (
      size.width >= 200 &&
      size.height >= 200 &&
      gl.domElement.width >= 200 &&
      gl.domElement.height >= 200
    ) {
      sent.current = true;
      queueMicrotask(() => onReady());
    }
  });
  return null;
}

/** Follow-player key + fill so spawn (south of origin) is not a shadow hole. */
function StreetSun({ avatar }: { avatar: AvatarState }) {
  const lightRef = useRef<DirectionalLight>(null);
  const fillRef = useRef<DirectionalLight>(null);
  const pos = lngLatToWorld(avatar.lon, avatar.lat);

  useLayoutEffect(() => {
    const node = lightRef.current;
    if (!node) {
      return;
    }
    if (!node.target.parent && node.parent) {
      node.parent.add(node.target);
    }
  }, []);

  useFrame(() => {
    const p = lngLatToWorld(avatar.lon, avatar.lat);
    const node = lightRef.current;
    if (node) {
      node.position.set(p.x + SUN_KEY[0], SUN_KEY[1], p.z + SUN_KEY[2]);
      node.target.position.set(p.x, GROUND_Y + 0.4, p.z);
      node.target.updateMatrixWorld();
    }
    const fill = fillRef.current;
    if (fill) {
      fill.position.set(p.x - 10, 20, p.z - 26);
    }
  });

  return (
    <group name="street-light" userData={{ kind: LIGHT_KIND }}>
      <hemisphereLight
        name="street-hemi"
        args={[SKY_HEMI_UP, SKY_HEMI_DOWN, HEMI_INTENSITY]}
      />
      <ambientLight intensity={AMBIENT_INTENSITY} />
      <directionalLight
        ref={lightRef}
        name="street-sun"
        userData={{ kind: "sun-key" }}
        castShadow
        color={SUN_COLOR}
        intensity={SUN_INTENSITY}
        position={[pos.x + SUN_KEY[0], SUN_KEY[1], pos.z + SUN_KEY[2]]}
        shadow-mapSize={[1024, 1024]}
        shadow-bias={-0.00028}
        shadow-normalBias={0.06}
        shadow-radius={3.2}
        shadow-camera-near={4}
        shadow-camera-far={160}
        shadow-camera-left={-SHADOW_EXTENT_M}
        shadow-camera-right={SHADOW_EXTENT_M}
        shadow-camera-top={SHADOW_EXTENT_M}
        shadow-camera-bottom={-SHADOW_EXTENT_M}
      >
        <object3D attach="target" position={[pos.x, 0.4, pos.z]} />
      </directionalLight>
      <directionalLight
        ref={fillRef}
        name="street-fill"
        color="#d4e4f4"
        intensity={FILL_INTENSITY}
        position={[pos.x - 10, 20, pos.z - 26]}
      />
    </group>
  );
}

function CityScene({
  collection,
  buildings,
  avatar,
  look,
  seat,
  remotes,
  shops,
  listings,
  selectedShopId,
  onSelectShop,
  onLookDelta,
  onLookMode,
  onFirstFrame,
}: {
  collection: FeatureCollection;
  buildings: BuildingPoly[];
  avatar: AvatarState;
  look: LookState;
  seat: SeatId;
  remotes: VisibleFriend[];
  shops: Shop[];
  listings: Listing[];
  selectedShopId: string | null;
  onSelectShop: (id: string) => void;
  onLookDelta: (dx: number, dy: number) => void;
  onLookMode: (mode: LookMode) => void;
  onFirstFrame?: () => void;
}) {
  const worldBuildings = useMemo(() => buildingsToWorld(buildings), [buildings]);
  const extras = useMemo(() => worldFromCollection(collection), [collection]);
  const camSolids = useMemo(
    () => cameraHitSolids(buildings, shops, extras.streets),
    [buildings, extras.streets, shops],
  );
  const walks = useMemo(
    () =>
      extras.streets
        .filter((street) => !isInnerStreet(street))
        .flatMap((street) => walkSegments(street.points)),
    [extras.streets],
  );
  const innerWalks = useMemo(
    () => extras.streets.filter((street) => isInnerStreet(street)).flatMap(innerWalkSegments),
    [extras.streets],
  );
  const roads = useMemo(
    () => extras.streets.filter((street) => street.surface === "asphalt"),
    [extras.streets],
  );
  const mains = useMemo(() => roads.filter((street) => !isInnerStreet(street)), [roads]);
  const inners = useMemo(() => roads.filter((street) => isInnerStreet(street)), [roads]);
  const segs = useMemo(
    () => roads.flatMap((street) => streetSegments(street.points, streetRoadWidth(street))),
    [roads],
  );
  const curbs = useMemo(
    () => mains.flatMap((street) => curbSegments(street.points)),
    [mains],
  );
  const edges = useMemo(
    () => mains.flatMap((street) => edgeStripSegments(street.points)),
    [mains],
  );
  const innerEdges = useMemo(() => inners.flatMap(innerEdgeStripSegments), [inners]);
  const furniture = useMemo(
    () => streetPropsFromStreets(extras.streets, worldBuildings),
    [extras.streets, worldBuildings],
  );
  const plaques = useMemo(
    () => streetPlaquesFromWorld(extras.streets, worldBuildings),
    [extras.streets, worldBuildings],
  );
  const spill = useMemo(
    () => marketSpillForPlay(extras.streets, shops, furniture),
    [extras.streets, furniture, shops],
  );
  const drawnShops = useMemo(
    () => shops.filter((shop) => shopStallSpec(shop, extras.streets).draw),
    [extras.streets, shops],
  );
  const edge = useMemo(() => blockEdgePieces(), []);
  const playerWorld = lngLatToWorld(avatar.lon, avatar.lat);
  const lod = lodSamplePoint(playerWorld.x, playerWorld.z);

  return (
    <>
      <color attach="background" args={[SKY_CLEAR]} />
      <fog attach="fog" args={[SKY_FOG, FOG_NEAR_M, FOG_FAR_M]} />
      <SkyHemisphere />
      <StreetSun avatar={avatar} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.04, 0]} receiveShadow>
        <planeGeometry args={[SURROUND_SIZE_M, SURROUND_SIZE_M]} />
        <meshStandardMaterial color={SURROUND_COLOR} roughness={1} />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, GROUND_Y, 0]}
        receiveShadow
        name="authored-slab"
        userData={{ kind: "plaza" }}
      >
        <planeGeometry args={[SLAB_SIZE_M, SLAB_SIZE_M]} />
        <meshStandardMaterial color={PLAZA_COLOR} roughness={0.96} />
      </mesh>
      {edge.map((piece) => (
        <BlockEdgeMesh key={piece.id} piece={piece} />
      ))}
      {walks.map((seg, index) => (
        <mesh
          key={`wk-${index}`}
          name={`sidewalk-${index}`}
          userData={{ kind: "walk" }}
          position={[seg.x, 0.03, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          receiveShadow
        >
          <boxGeometry args={[seg.width, 0.05, seg.length]} />
          <meshStandardMaterial color={WALK_COLOR} roughness={0.92} />
        </mesh>
      ))}
      {innerWalks.map((seg, index) => (
        <mesh
          key={`iwk-${index}`}
          name={`inner-walk-${index}`}
          userData={{ kind: "walk", lane: "inner" }}
          position={[seg.x, 0.032, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          receiveShadow
        >
          <boxGeometry args={[seg.width, 0.05, seg.length]} />
          <meshStandardMaterial color={WALK_COLOR} roughness={0.92} />
        </mesh>
      ))}
      {segs.map((seg, index) => (
        <mesh
          key={`st-${index}`}
          name={`asphalt-${index}`}
          userData={{ kind: "road" }}
          position={[seg.x, 0.055, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          receiveShadow
        >
          <boxGeometry args={[seg.width, 0.06, seg.length]} />
          <meshStandardMaterial color={ROAD_COLOR} roughness={0.94} />
        </mesh>
      ))}
      {edges.map((seg, index) => (
        <mesh
          key={`ed-${index}`}
          name={`road-edge-${index}`}
          userData={{ kind: "road-edge" }}
          position={[seg.x, 0.09, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          receiveShadow
        >
          <boxGeometry args={[seg.width, 0.04, seg.length]} />
          <meshStandardMaterial color={EDGE_COLOR} roughness={0.7} />
        </mesh>
      ))}
      {innerEdges.map((seg, index) => (
        <mesh
          key={`ied-${index}`}
          name={`inner-road-edge-${index}`}
          userData={{ kind: "road-edge", lane: "inner" }}
          position={[seg.x, 0.09, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          receiveShadow
        >
          <boxGeometry args={[seg.width, 0.04, seg.length]} />
          <meshStandardMaterial color={EDGE_COLOR} roughness={0.7} />
        </mesh>
      ))}
      {curbs.map((seg, index) => (
        <mesh
          key={`cb-${index}`}
          name={`curb-${index}`}
          userData={{ kind: "curb" }}
          position={[seg.x, CURB_HEIGHT_M / 2, seg.z]}
          rotation={[0, seg.rotationY, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[seg.width, CURB_HEIGHT_M, seg.length]} />
          <meshStandardMaterial color={CURB_COLOR} roughness={0.88} />
        </mesh>
      ))}
      {furniture.crosswalks.map((spec) => (
        <CrosswalkBand key={spec.id} spec={spec} />
      ))}
      {furniture.stopLines.map((spec) => (
        <StopLineMark key={spec.id} spec={spec} />
      ))}
      {furniture.curbReturns.map((spec) => (
        <CurbReturnLip key={spec.id} spec={spec} />
      ))}
      {extras.parks.map((park) => (
        <ParkMesh key={park.id} park={park} />
      ))}
      {plaques.map((plaque) => (
        <StreetPlaquePole
          key={plaque.id}
          plaque={plaque}
          playerX={playerWorld.x}
          playerZ={playerWorld.z}
        />
      ))}
      {furniture.planters.map((planter) => (
        <PlanterMass key={planter.id} planter={planter} />
      ))}
      {furniture.scooters
        .filter((scooter) => shouldDrawScooter(scooter, lod.x, lod.z))
        .map((scooter) => (
          <ParkedScooter key={scooter.id} scooter={scooter} />
        ))}
      {spill.map((piece) => (
        <MarketSpillProp key={piece.id} piece={piece} />
      ))}
      {furniture.lamps.map((lamp) => (
        <LampPost key={lamp.id} lamp={lamp} />
      ))}
      {worldBuildings.map((building) => (
        <BuildingMesh
          key={building.id}
          building={building}
          streets={extras.streets}
          lodX={lod.x}
          lodZ={lod.z}
        />
      ))}
      {extras.places
        .filter((place) => shouldDrawPlayHtml(place.x, place.z, playerWorld.x, playerWorld.z))
        .map((place) => (
        <Html key={place.id} position={[place.x, 2.4, place.z]} center distanceFactor={28}>
          <div className="play-place-label">{place.name}</div>
        </Html>
      ))}
      {drawnShops.map((shop) => (
        <ShopPole
          key={shop.shop_id}
          shop={shop}
          listings={listings}
          selected={shop.shop_id === selectedShopId}
          onSelect={onSelectShop}
          streets={extras.streets}
          playerX={playerWorld.x}
          playerZ={playerWorld.z}
        />
      ))}
      <Walker state={avatar} seat={seat} self />
      {remotes.map((friend) => (
        <Walker
          key={friend.seat_id}
          state={friend}
          seat={friend.seat_id}
          self={false}
          label={friend.display_name}
          listenerX={playerWorld.x}
          listenerZ={playerWorld.z}
        />
      ))}
      <FollowCamera avatar={avatar} look={look} solids={camSolids} side={seatFollowSide(seat)} />
      <PlayLook onLookDelta={onLookDelta} onLookMode={onLookMode} />
      <PlayLoopGate />
      <HitchWarmup />
      <FirstFrameReady ok={worldBuildings.length > 0} onReady={onFirstFrame} />
    </>
  );
}

export function detectPlayWebgl(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

type PlayViewProps = {
  collection: FeatureCollection;
  buildings: BuildingPoly[];
  avatar: AvatarState;
  look: LookState;
  seat: SeatId;
  remotes: VisibleFriend[];
  shops: Shop[];
  listings: Listing[];
  selectedShopId: string | null;
  onSelectShop: (id: string) => void;
  onLookDelta: (dx: number, dy: number) => void;
  onLookMode: (mode: LookMode) => void;
  onFirstFrame?: () => void;
  blocked?: boolean;
  slid?: boolean;
};

export function PlayLoading() {
  return (
    <div className="play-loading" data-testid="play-loading" role="status" aria-live="polite">
      <p className="play-loading-brand">HH World</p>
      <div className="play-loading-road" aria-hidden="true" />
      <p className="play-loading-title">Loading the authored 400 m block</p>
      <p className="play-loading-copy">
        Ground, buildings, and your character. Authored approximation — not a
        city, not OSM, not 1:1.
      </p>
    </div>
  );
}

export function PlayAvatarHud({
  avatar,
  look,
  seat,
  buildings,
  blocked,
  slid,
}: {
  avatar: AvatarState;
  look: LookState;
  seat: SeatId;
  buildings: BuildingPoly[];
  blocked: boolean;
  slid: boolean;
}) {
  const inside = isInsideBuildingAabb(avatar.lon, avatar.lat, buildings);
  const insideRing = isInsideBuildingRing(avatar.lon, avatar.lat, buildings);
  const atBound = isAtAoiBound(avatar.lon, avatar.lat, AOI_BBOX);
  return (
    <div
      className="play-self-hit"
      data-testid="self-avatar"
      data-engine="r3f"
      data-seat={seat}
      data-pose={avatar.pose}
      data-heading={String(Math.round(avatar.heading))}
      data-lon={avatar.lon.toFixed(7)}
      data-lat={avatar.lat.toFixed(7)}
      data-ground-y={String(GROUND_Y)}
      data-alt={avatar.alt.toFixed(2)}
      data-airborne={avatar.airborne ? "1" : "0"}
      data-inside-aabb={inside ? "1" : "0"}
      data-inside-ring={insideRing ? "1" : "0"}
      data-at-bound={atBound ? "1" : "0"}
      data-blocked={blocked ? "1" : "0"}
      data-slide={slid ? "1" : "0"}
      data-look={look.mode}
      data-sprint={avatar.sprint ? "1" : "0"}
      data-turning={avatar.turning ? "1" : "0"}
      data-collision={COLLISION_KIND}
      data-body="tunic-humanoid"
      data-walk-cycle={WALK_CYCLE_KIND}
      data-tunic={tunicShirtForSeat(seat)}
      data-screen-x=""
      data-screen-y=""
      data-on-canvas="0"
      data-footsteps="0"
      data-footstep-kind={FOOTSTEP_KIND}
      data-friend-footsteps="0"
      aria-label="Your character"
    />
  );
}

export function PlayView({
  collection,
  buildings,
  avatar,
  look,
  seat,
  remotes,
  shops,
  listings,
  selectedShopId,
  onSelectShop,
  onLookDelta,
  onLookMode,
  onFirstFrame,
  blocked = false,
  slid = false,
}: PlayViewProps) {
  const streetRemotes = remotes.filter(isStreetFriend);
  const viewingRemotes = remotes.filter((row) => !isStreetFriend(row));
  const [painted, setPainted] = useState(false);
  const worldExtras = useMemo(() => worldFromCollection(collection), [collection]);
  const camSolids = useMemo(
    () => cameraHitSolids(buildings, shops, worldExtras.streets),
    [buildings, shops, worldExtras.streets],
  );
  const follow = look.mode !== "off" ? "look" : "heading";
  const camSide = seatFollowSide(seat);
  const cam = resolveFollowCamera(
    lngLatToWorld(avatar.lon, avatar.lat),
    followRigYaw(avatar.heading, look.mode, look.yaw, look.pitch),
    camSolids,
    avatar.alt,
    followPitchDeg(look.mode, look.pitch),
    undefined,
    undefined,
    camSide,
  );
  const camInside = cameraPointInsideSolid(cam.x, cam.y, cam.z, camSolids);
  const insideAabb = isInsideBuildingAabb(avatar.lon, avatar.lat, buildings);
  const insideRing = isInsideBuildingRing(avatar.lon, avatar.lat, buildings);
  const hitId = hitBuildingId(avatar.lon, avatar.lat, buildings);
  const worldBuildings = useMemo(() => buildingsToWorld(buildings), [buildings]);
  const facade = useMemo(() => countFacadePieces(worldBuildings), [worldBuildings]);
  const facadeById = useMemo(() => {
    const out: Record<string, number> = {};
    for (const building of worldBuildings) {
      out[building.id] = facadePiecesForBuilding(building).length;
    }
    return out;
  }, [worldBuildings]);
  const groundFloors = useMemo(
    () =>
      worldBuildings.flatMap((building) =>
        groundFloorFacesForBuilding(building, worldExtras.streets),
      ),
    [worldBuildings, worldExtras.streets],
  );
  const groundCount = useMemo(
    () => countGroundFloorPieces(worldBuildings, worldExtras.streets),
    [worldBuildings, worldExtras.streets],
  );
  const roofCount = useMemo(() => countRoofPieces(worldBuildings), [worldBuildings]);
  const roofById = useMemo(() => {
    const out: Record<string, { parapets: number; acs: number; tanks: number }> = {};
    for (const building of worldBuildings) {
      const rows = roofPiecesForBuilding(building);
      out[building.id] = {
        parapets: rows.filter((row) => row.kind === "parapet").length,
        acs: rows.filter((row) => row.kind === "ac").length,
        tanks: rows.filter((row) => row.kind === "tank").length,
      };
    }
    return out;
  }, [worldBuildings]);
  const streetProps = useMemo(() => streetPropsFromCollection(collection), [collection]);
  const propCount = useMemo(() => countStreetProps(streetProps), [streetProps]);
  const marketSpill = useMemo(
    () => marketSpillForPlay(worldExtras.streets, shops, streetProps),
    [streetProps, shops, worldExtras.streets],
  );
  const spillCount = useMemo(() => countMarketSpill(marketSpill), [marketSpill]);
  const drawnShopCount = useMemo(
    () => shops.filter((shop) => shopStallSpec(shop, worldExtras.streets).draw).length,
    [shops, worldExtras.streets],
  );
  const stallBoards = useMemo(
    () =>
      shops.map((shop) => {
        const stall = shopStallSpec(shop, worldExtras.streets);
        const titles = stallBoardPaintTitles(stallBoardTitles(listings, shop.shop_id));
        return {
          shop,
          stall,
          titles,
          source: isLocalShopId(shop.shop_id) ? "local-demo" : "authored",
          draw: stall.draw && titles.length > 0,
        };
      }),
    [listings, shops, worldExtras.streets],
  );
  const drawnPlayerBoardCount = useMemo(
    () => stallBoards.filter((row) => row.draw && row.source === "local-demo").length,
    [stallBoards],
  );
  const drawnBoardCount = useMemo(
    () => stallBoards.filter((row) => row.draw).length,
    [stallBoards],
  );
  const edgePieces = useMemo(() => blockEdgePieces(), []);
  const edgeCount = useMemo(() => countBlockEdge(edgePieces), [edgePieces]);
  const innerLaneCount = useMemo(() => countInnerLanes(worldExtras.streets), [worldExtras.streets]);
  const streetPlaques = useMemo(
    () => streetPlaquesFromWorld(worldExtras.streets, worldBuildings),
    [worldBuildings, worldExtras.streets],
  );
  const streetHudLanes = useMemo(
    () => namedStreetHudLanes(worldExtras.streets, worldBuildings),
    [worldBuildings, worldExtras.streets],
  );
  const streetHud = useMemo(
    () => namedStreetHudAt(avatar.lon, avatar.lat, streetHudLanes),
    [avatar.lat, avatar.lon, streetHudLanes],
  );
  const streetHudName = streetHudLabel(streetHud);
  const atBound = isAtAoiBound(avatar.lon, avatar.lat, AOI_BBOX);
  const playerWorld = lngLatToWorld(avatar.lon, avatar.lat);
  const lod = lodSamplePoint(playerWorld.x, playerWorld.z);
  const drawnInnerFaces = groundFloors.filter(
    (face) => isInnerStreetId(face.streetId) && shouldDrawGroundFloorFace(face, lod.x, lod.z),
  ).length;
  const drawnScooters = streetProps.scooters.filter((row) =>
    shouldDrawScooter(row, lod.x, lod.z),
  ).length;
  syncFriendFootstepSeats(streetRemotes.map((row) => row.seat_id));
  useEffect(() => {
    warmupPlayAudio();
    return armFootstepUnlock();
  }, []);
  useLayoutEffect(() => {
    const keep = new Set(streetRemotes.map((row) => row.seat_id));
    pruneFriendFootsteps(keep);
    dropLeftoverStreetNametags(keep);
  }, [streetRemotes]);
  return (
    <div
      className="play-host"
      data-testid="play-view"
      data-engine="r3f"
      data-play-ready={painted ? "yes" : "no"}
      data-look={look.mode}
      data-footsteps="0"
      data-footstep-kind={FOOTSTEP_KIND}
      data-friend-footsteps="0"
      data-friend-footstep-ticks="0"
      data-fog={FOG_KIND}
      data-block-edge={BLOCK_EDGE_KIND}
      data-at-bound={atBound ? "1" : "0"}
      data-side-street={SIDE_STREET_KIND}
      data-inner-lane={INNER_LANE_KIND}
      data-street-plaques={String(streetPlaques.length)}
      data-street-plaque-kind={STREET_PLAQUE_KIND}
      data-street-hud={STREET_HUD_KIND}
      data-street-name={streetHudName}
      data-street-role={streetHud?.role ?? ""}
      data-corner-crossing={CORNER_CROSSING_KIND}
      data-crosswalks={String(propCount.crosswalks)}
      data-stop-lines={String(propCount.stopLines)}
      data-curb-returns={String(propCount.curbReturns)}
      data-far-lod={FAR_DETAIL_KIND}
      data-far-lod-m={String(FAR_DETAIL_M)}
      data-far-lod-drawn-inner={String(drawnInnerFaces)}
      data-far-lod-drawn-scooters={String(drawnScooters)}
      data-hitch-warmup={HITCH_WARMUP_KIND}
      data-stall-board={STALL_BOARD_KIND}
      data-stall-boards={String(drawnBoardCount)}
      data-player-stall-boards={String(drawnPlayerBoardCount)}
    >
      <Canvas
        shadows
        className="play-canvas-wrap"
        style={{ width: "100%", height: "100%", display: "block" }}
        resize={{ debounce: 0, scroll: false }}
        dpr={[1, 1.25]}
        gl={{ alpha: false, antialias: true, powerPreference: "high-performance" }}
        camera={{ fov: 50, near: 0.1, far: 480, position: [cam.x, cam.y, cam.z] }}
        onCreated={({ gl, camera, setSize }) => {
          gl.domElement.classList.add("play-canvas");
          gl.domElement.dataset.testid = "play-canvas";
          gl.domElement.dataset.engine = "three";
          gl.toneMapping = ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.08;
          gl.shadowMap.enabled = true;
          gl.shadowMap.type = BasicShadowMap;
          gl.setClearColor(SKY_CLEAR, 1);
          const host = gl.domElement.closest(".play-host");
          const w = host instanceof HTMLElement ? host.clientWidth : 0;
          const h = host instanceof HTMLElement ? host.clientHeight : 0;
          if (w >= 2 && h >= 2) {
            setSize(w, h);
          }
          applyFollowCamera(camera, avatar, look, camSolids, camSide);
        }}
      >
        <CityScene
          collection={collection}
          buildings={buildings}
          avatar={avatar}
          look={look}
          seat={seat}
          remotes={streetRemotes}
          shops={shops}
          listings={listings}
          selectedShopId={selectedShopId}
          onSelectShop={onSelectShop}
          onLookDelta={onLookDelta}
          onLookMode={onLookMode}
          onFirstFrame={() => {
            setPainted(true);
            onFirstFrame?.();
          }}
        />
      </Canvas>
      <div data-testid="walk-cycle-proof" hidden data-walk-cycle={WALK_CYCLE_KIND} />
      <div
        data-testid="footstep-proof"
        hidden
        data-footsteps="0"
        data-footstep-kind={FOOTSTEP_KIND}
        data-friend-footsteps="0"
        data-friend-footstep-ticks="0"
      />
      <div
        data-testid="friend-footstep-proof"
        hidden
        data-friend-footsteps="0"
        data-friend-footstep-ticks="0"
        data-friend-footstep-kind={FOOTSTEP_KIND}
      />
      {streetRemotes.map((friend) => (
        <div
          key={`remote-walk-${friend.seat_id}`}
          data-testid={`remote-walk-cycle-${friend.seat_id}`}
          hidden
          data-walk-cycle={WALK_CYCLE_KIND}
          data-seat={friend.seat_id}
          data-friend-footsteps="0"
          data-friend-footstep-ticks="0"
        />
      ))}
      <div
        className="play-proof"
        data-testid="play-proof"
        data-engine="r3f"
        data-camera="behind"
        data-follow={follow}
        data-look={look.mode}
        data-heading={avatar.heading.toFixed(1)}
        data-cam-yaw={cam.yawDeg.toFixed(1)}
        data-cam-pitch={cam.pitchDeg.toFixed(1)}
        data-cam-x={cam.x.toFixed(2)}
        data-cam-y={cam.y.toFixed(2)}
        data-cam-z={cam.z.toFixed(2)}
        data-cam-look-x={cam.lookX.toFixed(2)}
        data-cam-look-y={cam.lookY.toFixed(2)}
        data-cam-look-z={cam.lookZ.toFixed(2)}
        data-fps-claim="NOT_R2_WP1"
        data-html-lod={PLAY_HTML_LOD_KIND}
        data-cam-kind={CAM_HIT_KIND}
        data-cam-hit={cam.hit ? "1" : "0"}
        data-cam-hit-id={cam.hitId ?? ""}
        data-cam-dist={cam.distM.toFixed(2)}
        data-cam-desired={cam.desiredDistM.toFixed(2)}
        data-cam-side={camSide.toFixed(2)}
        data-cam-inside={camInside ? "1" : "0"}
        data-cam-inside-id={camInside?.id ?? ""}
        data-buildings={String(buildings.length)}
        data-extruded="footprint"
        data-facade="inset"
        data-facade-windows={String(facade.windows)}
        data-facade-doors={String(facade.doors)}
        data-facade-bands={String(facade.bands)}
        data-facade-total={String(facade.total)}
        data-ground-floor={GROUND_FLOOR_KIND}
        data-ground-floor-buildings={String(groundCount.buildings)}
        data-ground-floor-faces={String(groundCount.faces)}
        data-ground-floor-displays={String(groundCount.displays)}
        data-ground-floor-storefronts={String(groundCount.storefronts)}
        data-ground-floor-awnings={String(groundCount.awnings)}
        data-ground-floor-main-faces={String(groundCount.mainFaces)}
        data-ground-floor-inner-faces={String(groundCount.innerFaces)}
        data-side-street={SIDE_STREET_KIND}
        data-side-street-streets={String(
          worldExtras.streets.filter((street) => isInnerStreet(street)).length,
        )}
        data-side-street-faces={String(groundCount.innerFaces)}
        data-side-street-lamps={String(propCount.innerLamps)}
        data-side-street-scooters={String(propCount.innerScooters)}
        data-inner-lane={INNER_LANE_KIND}
        data-inner-lane-roads={String(innerLaneCount.roads)}
        data-inner-lane-walks={String(innerLaneCount.walks)}
        data-inner-lane-edges={String(innerLaneCount.edges)}
        data-street-plaques={String(streetPlaques.length)}
        data-street-plaque-kind={STREET_PLAQUE_KIND}
        data-street-plaque-official={String(streetPlaques.filter((row) => row.role === "official").length)}
        data-street-plaque-inner={String(streetPlaques.filter((row) => row.role === "inner").length)}
        data-street-hud={STREET_HUD_KIND}
        data-street-name={streetHudName}
        data-street-role={streetHud?.role ?? ""}
        data-corner-crossing={CORNER_CROSSING_KIND}
        data-roof={ROOF_KIND}
        data-roof-buildings={String(roofCount.buildings)}
        data-roof-parapets={String(roofCount.parapets)}
        data-roof-acs={String(roofCount.acs)}
        data-roof-tanks={String(roofCount.tanks)}
        data-collision={COLLISION_KIND}
        data-ground-y={String(GROUND_Y)}
        data-alt={avatar.alt.toFixed(2)}
        data-airborne={avatar.airborne ? "1" : "0"}
        data-inside-aabb={insideAabb ? "1" : "0"}
        data-inside-ring={insideRing ? "1" : "0"}
        data-at-bound={atBound ? "1" : "0"}
        data-block-bound={BLOCK_BOUND_KIND}
        data-block-edge={BLOCK_EDGE_KIND}
        data-block-edge-walls={String(edgeCount.walls)}
        data-block-edge-curbs={String(edgeCount.curbs)}
        data-block-edge-lots={String(edgeCount.lots)}
        data-block-edge-copes={String(edgeCount.copes)}
        data-fog={FOG_KIND}
        data-fog-near={String(FOG_NEAR_M)}
        data-fog-far={String(FOG_FAR_M)}
        data-far-lod={FAR_DETAIL_KIND}
        data-far-lod-m={String(FAR_DETAIL_M)}
        data-far-lod-drawn-inner={String(drawnInnerFaces)}
        data-far-lod-drawn-scooters={String(drawnScooters)}
        data-hitch-warmup={HITCH_WARMUP_KIND}
        data-blocked={blocked ? "1" : "0"}
        data-slide={slid ? "1" : "0"}
        data-hit-building={hitId ?? ""}
        data-sprint={avatar.sprint ? "1" : "0"}
        data-turning={avatar.turning ? "1" : "0"}
        data-body="tunic-humanoid"
        data-walk-cycle={WALK_CYCLE_KIND}
        data-tunic={tunicShirtForSeat(seat)}
        data-footsteps="0"
        data-footstep-kind={FOOTSTEP_KIND}
        data-friend-footsteps="0"
        data-friend-footstep-ticks="0"
        data-shops={String(shops.length)}
        data-drawn-shops={String(drawnShopCount)}
        data-spawn-keep-out={String(SPAWN_KEEP_OUT_M)}
        data-sky={SKY_KIND}
        data-sun="disc"
        data-light={LIGHT_KIND}
        data-ground={GROUND_KIND}
        data-wall-finish={WALL_FINISH_KIND}
        data-shop-signs={String(drawnShopCount)}
        data-shop-sign-kind="pole-board"
        data-shop-sign-faces="2"
        data-shop-stalls={String(drawnShopCount)}
        data-shop-stall-kind={SHOP_STALL_KIND}
        data-stall-board={STALL_BOARD_KIND}
        data-stall-boards={String(drawnBoardCount)}
        data-player-stall-boards={String(drawnPlayerBoardCount)}
        data-street-props={STREET_PROPS_KIND}
        data-lamps={String(propCount.lamps)}
        data-lamp-glows={String(propCount.glows)}
        data-crosswalks={String(propCount.crosswalks)}
        data-stop-lines={String(propCount.stopLines)}
        data-curb-returns={String(propCount.curbReturns)}
        data-planters={String(propCount.planters)}
        data-scooters={String(propCount.scooters)}
        data-scooter-kind={SCOOTER_KIND}
        data-inner-lamps={String(propCount.innerLamps)}
        data-inner-scooters={String(propCount.innerScooters)}
        data-market-spill={MARKET_SPILL_KIND}
        data-market-spill-count={String(spillCount.total)}
        data-market-spill-shop={String(spillCount.shop)}
        data-market-spill-street={String(spillCount.street)}
        data-market-spill-coolers={String(spillCount.coolers)}
        data-market-spill-baskets={String(spillCount.baskets)}
      />
      <ol
        data-testid="play-street-props"
        hidden
        data-kind={STREET_PROPS_KIND}
        data-lamps={String(propCount.lamps)}
        data-crosswalks={String(propCount.crosswalks)}
        data-stop-lines={String(propCount.stopLines)}
        data-curb-returns={String(propCount.curbReturns)}
        data-planters={String(propCount.planters)}
        data-scooters={String(propCount.scooters)}
      >
        {streetProps.lamps.map((lamp) => (
          <li
            key={lamp.id}
            data-testid={lamp.id}
            data-kind="lamp"
            data-street={lamp.streetId}
            data-glow={lamp.glow ? "1" : "0"}
            data-x={lamp.x.toFixed(2)}
            data-z={lamp.z.toFixed(2)}
          >
            {lamp.id}
          </li>
        ))}
        {streetProps.crosswalks.map((row) => (
          <li
            key={row.id}
            data-testid={row.id}
            data-kind="crosswalk"
            data-corner={isAuthoredMouthCrosswalk(row.id) ? "1" : "0"}
            data-mouth={
              row.id === WEST_CROSSWALK_ID
                ? "west"
                : row.id === CORNER_CROSSWALK_ID
                  ? "east"
                  : row.id === TRAM_CROSSWALK_ID
                    ? "tram"
                    : ""
            }
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
            data-stripes={String(row.stripes)}
          >
            {row.id}
          </li>
        ))}
        {streetProps.stopLines.map((row) => (
          <li
            key={row.id}
            data-testid={row.id}
            data-kind="stop-line"
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
        {streetProps.curbReturns.map((row) => (
          <li
            key={row.id}
            data-testid={row.id}
            data-kind="curb-return"
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
        {streetProps.planters.map((row) => (
          <li
            key={row.id}
            data-testid={row.id}
            data-kind="planter"
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
        {streetProps.scooters.map((row) => (
          <li
            key={row.id}
            data-testid={row.id}
            data-kind="scooter"
            data-street={row.streetId}
            data-color={row.color}
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-corner-crossing"
        hidden
        data-kind={CORNER_CROSSING_KIND}
        data-crosswalks={String(
          streetProps.crosswalks.filter((row) => isAuthoredMouthCrosswalk(row.id)).length,
        )}
        data-stop-lines={String(propCount.stopLines)}
        data-curb-returns={String(propCount.curbReturns)}
      >
        {streetProps.crosswalks
          .filter((row) => isAuthoredMouthCrosswalk(row.id))
          .map((row) => (
            <li
              key={`corner-${row.id}`}
              data-testid={`play-corner-${row.id}`}
              data-kind="crosswalk"
              data-mouth={
                row.id === WEST_CROSSWALK_ID
                  ? "west"
                  : row.id === TRAM_CROSSWALK_ID
                    ? "tram"
                    : "east"
              }
              data-x={row.x.toFixed(2)}
              data-z={row.z.toFixed(2)}
              data-stripes={String(row.stripes)}
            >
              {row.id}
            </li>
          ))}
        {streetProps.stopLines.map((row) => (
          <li
            key={`corner-${row.id}`}
            data-testid={`play-corner-${row.id}`}
            data-kind="stop-line"
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
        {streetProps.curbReturns.map((row) => (
          <li
            key={`corner-${row.id}`}
            data-testid={`play-corner-${row.id}`}
            data-kind="curb-return"
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-scooters"
        hidden
        data-kind={SCOOTER_KIND}
        data-count={String(propCount.scooters)}
      >
        {streetProps.scooters.map((row) => (
          <li
            key={`proof-${row.id}`}
            data-testid={`play-scooter-${row.id}`}
            data-kind="scooter"
            data-street={row.streetId}
            data-color={row.color}
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-market-spill"
        hidden
        data-kind={MARKET_SPILL_KIND}
        data-count={String(spillCount.total)}
        data-shop={String(spillCount.shop)}
        data-street={String(spillCount.street)}
        data-coolers={String(spillCount.coolers)}
        data-baskets={String(spillCount.baskets)}
      >
        {marketSpill.map((row) => (
          <li
            key={row.id}
            data-testid={`play-spill-${row.id}`}
            data-kind={row.kind}
            data-source={row.source}
            data-shop={row.shop_id ?? ""}
            data-color={row.color}
            data-collide={row.collide ? "1" : "0"}
            data-x={row.x.toFixed(2)}
            data-z={row.z.toFixed(2)}
          >
            {row.id}
          </li>
        ))}
      </ol>
      <ol data-testid="play-shop-signs" hidden data-count={String(shops.length)} data-kind="pole-board">
        {shops.map((shop) => {
          const spec = shopSignSpec(shop, worldExtras.streets);
          return (
            <li
              key={shop.shop_id}
              data-testid={`shop-sign-${shop.shop_id}`}
              data-shop-id={shop.shop_id}
              data-kind={spec.kind}
              data-e={spec.eHint}
              data-draw={spec.draw ? "1" : "0"}
              data-name={shop.name}
              data-lon={shop.lon.toFixed(7)}
              data-lat={shop.lat.toFixed(7)}
              data-x={spec.x.toFixed(2)}
              data-z={spec.z.toFixed(2)}
              data-lane-m={spec.laneM.toFixed(2)}
            >
              {shop.name}
            </li>
          );
        })}
      </ol>
      <ol
        data-testid="play-shop-stalls"
        hidden
        data-count={String(shops.length)}
        data-drawn={String(drawnShopCount)}
        data-kind={SHOP_STALL_KIND}
      >
        {shops.map((shop) => {
          const stall = shopStallSpec(shop, worldExtras.streets);
          return (
            <li
              key={shop.shop_id}
              data-testid={`shop-stall-${shop.shop_id}`}
              data-shop-id={shop.shop_id}
              data-kind={stall.kind}
              data-awning={stall.awning}
              data-collide={stall.collide ? "1" : "0"}
              data-draw={stall.draw ? "1" : "0"}
              data-name={shop.name}
              data-lon={shop.lon.toFixed(7)}
              data-lat={shop.lat.toFixed(7)}
              data-x={stall.x.toFixed(2)}
              data-z={stall.z.toFixed(2)}
              data-lane-m={stall.laneM.toFixed(2)}
              data-street={stall.streetId ?? ""}
            >
              {shop.name}
            </li>
          );
        })}
      </ol>
      <ol
        data-testid="play-stall-boards"
        hidden
        data-kind={STALL_BOARD_KIND}
        data-count={String(stallBoards.length)}
        data-drawn={String(drawnBoardCount)}
        data-player-drawn={String(drawnPlayerBoardCount)}
        data-honesty={STALL_BOARD_HONESTY}
      >
        {stallBoards.map((row) => (
          <li
            key={row.shop.shop_id}
            data-testid={`stall-board-${row.shop.shop_id}`}
            data-shop-id={row.shop.shop_id}
            data-source={row.source}
            data-kind={STALL_BOARD_KIND}
            data-draw={row.draw ? "1" : "0"}
            data-keep-out={row.stall.draw ? "0" : "1"}
            data-titles={row.titles.join(" | ")}
            data-count={String(row.titles.length)}
          >
            {row.titles.join(" | ")}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-ground-floors"
        hidden
        data-kind={GROUND_FLOOR_KIND}
        data-count={String(groundCount.faces)}
        data-buildings={String(groundCount.buildings)}
        data-displays={String(groundCount.displays)}
        data-storefronts={String(groundCount.storefronts)}
        data-awnings={String(groundCount.awnings)}
        data-main-faces={String(groundCount.mainFaces)}
        data-inner-faces={String(groundCount.innerFaces)}
      >
        {groundFloors.map((face, index) => (
          <li
            key={`${face.buildingId}-${face.streetId}-${index}`}
            data-testid={`ground-floor-${face.buildingId}-${index}`}
            data-building-id={face.buildingId}
            data-street={face.streetId}
            data-lane={isInnerStreetId(face.streetId) ? "inner" : "main"}
            data-kind={GROUND_FLOOR_KIND}
            data-displays={String(face.pieces.filter((piece) => piece.kind === "display").length)}
            data-storefronts={String(face.pieces.filter((piece) => piece.kind === "storefront").length)}
            data-awnings={String(face.pieces.filter((piece) => piece.kind === "awning").length)}
            data-x={face.x.toFixed(2)}
            data-z={face.z.toFixed(2)}
          >
            {face.buildingId}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-street-plaques"
        hidden
        data-kind={STREET_PLAQUE_KIND}
        data-count={String(streetPlaques.length)}
        data-official={String(streetPlaques.filter((row) => row.role === "official").length)}
        data-inner={String(streetPlaques.filter((row) => row.role === "inner").length)}
      >
        {streetPlaques.map((plaque) => (
          <li
            key={plaque.id}
            data-testid={plaque.id}
            data-kind={plaque.kind}
            data-street={plaque.streetId}
            data-role={plaque.role}
            data-name={plaque.name}
            data-line2={plaque.line2}
            data-collide={plaque.collide ? "1" : "0"}
            data-x={plaque.x.toFixed(2)}
            data-z={plaque.z.toFixed(2)}
          >
            {plaque.name}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-side-streets"
        hidden
        data-kind={SIDE_STREET_KIND}
        data-lane-kind={INNER_LANE_KIND}
        data-count={String(worldExtras.streets.filter((street) => isInnerStreet(street)).length)}
        data-faces={String(groundCount.innerFaces)}
        data-lamps={String(propCount.innerLamps)}
        data-scooters={String(propCount.innerScooters)}
        data-roads={String(innerLaneCount.roads)}
        data-walks={String(innerLaneCount.walks)}
      >
        {worldExtras.streets
          .filter((street) => isInnerStreet(street))
          .map((street) => (
            <li
              key={street.id}
              data-testid={street.id}
              data-street={street.id}
              data-lane="inner"
              data-width={street.widthM.toFixed(2)}
              data-walk-width={innerWalkWidth(street).toFixed(2)}
            >
              {street.id}
            </li>
          ))}
      </ol>
      <ol
        hidden
        data-testid="play-remote-labels"
        data-count={String(streetRemotes.length)}
        data-street="1"
      />
      <ol data-testid="play-remote-bodies" hidden data-count={streetRemotes.length} data-body="tunic-humanoid" data-walk-cycle={WALK_CYCLE_KIND}>
        {streetRemotes.map((friend) => (
          <li
            key={friend.seat_id}
            data-testid={`remote-body-${friend.seat_id}`}
            data-remote-avatar={friend.seat_id}
            data-seat={friend.seat_id}
            data-body="tunic-humanoid"
            data-walk-cycle={WALK_CYCLE_KIND}
            data-tunic={tunicShirtForSeat(friend.seat_id)}
            data-pose={friend.pose}
            data-heading={String(Math.round(friend.heading))}
            data-lon={friend.lon.toFixed(7)}
            data-lat={friend.lat.toFixed(7)}
            data-street="1"
          >
            {friend.display_name}
          </li>
        ))}
      </ol>
      <ol hidden data-testid="play-remote-viewing" data-count={viewingRemotes.length}>
        {viewingRemotes.map((friend) => (
          <li
            key={friend.seat_id}
            data-testid={`remote-viewing-${friend.seat_id}`}
            data-seat={friend.seat_id}
            data-shop={friend.viewing_shop_id ?? ""}
            data-street="0"
          >
            {VIEWING_SHOP_COPY}
          </li>
        ))}
      </ol>
      <ol
        data-testid="play-roofs"
        hidden
        data-kind={ROOF_KIND}
        data-buildings={String(roofCount.buildings)}
        data-parapets={String(roofCount.parapets)}
        data-acs={String(roofCount.acs)}
        data-tanks={String(roofCount.tanks)}
      >
        {worldBuildings.map((building) => {
          const row = roofById[building.id] ?? { parapets: 0, acs: 0, tanks: 0 };
          return (
            <li
              key={building.id}
              data-testid={`play-roof-${building.id}`}
              data-building-id={building.id}
              data-kind={ROOF_KIND}
              data-parapets={String(row.parapets)}
              data-acs={String(row.acs)}
              data-tanks={String(row.tanks)}
              data-height={String(building.height_m)}
              data-x={building.cx.toFixed(2)}
              data-z={building.cz.toFixed(2)}
            >
              {building.id}
            </li>
          );
        })}
      </ol>
      <ol
        data-testid="play-block-edge"
        hidden
        data-kind={BLOCK_EDGE_KIND}
        data-bound={BLOCK_BOUND_KIND}
        data-fog={FOG_KIND}
        data-fog-near={String(FOG_NEAR_M)}
        data-fog-far={String(FOG_FAR_M)}
        data-walls={String(edgeCount.walls)}
        data-curbs={String(edgeCount.curbs)}
        data-lots={String(edgeCount.lots)}
        data-copes={String(edgeCount.copes)}
      >
        {edgePieces.map((piece) => (
          <li
            key={piece.id}
            data-testid={piece.id}
            data-kind={piece.kind}
            data-x={piece.x.toFixed(2)}
            data-y={piece.y.toFixed(2)}
            data-z={piece.z.toFixed(2)}
            data-color={piece.color}
          >
            {piece.id}
          </li>
        ))}
      </ol>
      <ol data-testid="play-building-list" hidden>
        {buildings.map((building) => {
          const box = building.aabb ?? ringAabb(building.ring);
          const insets = facadeById[building.id] ?? 0;
          const gf = groundFloors.filter((face) => face.buildingId === building.id);
          const rf = roofById[building.id] ?? { parapets: 0, acs: 0, tanks: 0 };
          return (
            <li
              key={building.id}
              data-testid={`play-building-${building.id}`}
              data-building-id={building.id}
              data-mesh="extrude"
              data-facade={insets > 0 ? "inset" : "flat"}
              data-insets={String(insets)}
              data-ground-floor={gf.length > 0 ? GROUND_FLOOR_KIND : "none"}
              data-ground-floor-faces={String(gf.length)}
              data-roof={ROOF_KIND}
              data-roof-parapets={String(rf.parapets)}
              data-roof-acs={String(rf.acs)}
              data-roof-tanks={String(rf.tanks)}
              data-height={String(building.height_m ?? 8)}
              data-west={box ? box.west.toFixed(7) : ""}
              data-south={box ? box.south.toFixed(7) : ""}
              data-east={box ? box.east.toFixed(7) : ""}
              data-north={box ? box.north.toFixed(7) : ""}
            >
              {building.name ?? building.id}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
