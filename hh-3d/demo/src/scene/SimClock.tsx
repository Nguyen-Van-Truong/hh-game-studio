import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, type MutableRefObject, type RefObject } from "react";
import { Vector3, type Group } from "three";
import {
  consumeInteract,
  consumeJump,
  consumeLook,
  consumePunch,
  type PlayerInput,
} from "../lib/input";
import {
  BOAT_SPEED,
  GRAVITY,
  JUMP_SPEED,
  PUNCH_DURATION,
  RUN_SPEED,
  WALK_SPEED,
  clampDelta,
  type PlayHud,
} from "../lib/play";
import {
  BOARD_DISTANCE,
  PLAYER_RADIUS,
  boatAllowed,
  clampBoat,
  nearestWalkable,
  resolveWalk,
  surfaceAt,
} from "../lib/walk";
import { applyWalkPose, type PersonLimbs } from "./Person";
import {
  layout,
  playFollow,
  playLookCamera,
  playSpawn,
  sceneConfig,
} from "./sceneConfig";
import type { ViewMode } from "./viewMode";

type OrbitLike = {
  target: Vector3;
  update: () => void;
  minDistance: number;
  maxDistance: number;
};

type SimClockProps = {
  viewMode: ViewMode;
  reducedMotion: boolean;
  inputRef: RefObject<PlayerInput>;
  playerRef: RefObject<Group | null>;
  boatRef: RefObject<Group | null>;
  foliageRef: RefObject<Group | null>;
  limbsRef: RefObject<PersonLimbs | null>;
  startBoarded: boolean;
  autoWalk: boolean;
  onHud: (hud: PlayHud) => void;
  inputBlocked: boolean;
  cameraGoal: MutableRefObject<{
    transitioning: boolean;
    userOrbit: boolean;
    position: Vector3;
    target: Vector3;
  }>;
};

type Body = {
  x: number;
  y: number;
  z: number;
  yaw: number;
};

const PLAY_MIN = sceneConfig.camera.playMinDistance;
const PLAY_MAX = sceneConfig.camera.playMaxDistance;
const LOOK_MIN = sceneConfig.camera.minDistance;
const LOOK_MAX = sceneConfig.camera.maxDistance;
const CLOSE_EPSILON = 0.04;

function distance2(ax: number, az: number, bx: number, bz: number): number {
  const dx = ax - bx;
  const dz = az - bz;
  return Math.hypot(dx, dz);
}

export function SimClock({
  viewMode,
  reducedMotion,
  inputRef,
  playerRef,
  boatRef,
  foliageRef,
  limbsRef,
  startBoarded,
  autoWalk,
  onHud,
  inputBlocked,
  cameraGoal,
}: SimClockProps) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as OrbitLike | null;
  const player = useRef<Body>({
    x: startBoarded ? playSpawn.boardX : layout.dummy[0],
    y: startBoarded
      ? layout.boat[1] + playFollow.sitLift
      : (surfaceAt(layout.dummy[0], layout.dummy[2]) ?? layout.dummy[1]),
    z: startBoarded ? playSpawn.boardZ : layout.dummy[2],
    yaw: startBoarded ? playSpawn.boardYaw : Math.PI,
  });
  const boat = useRef<Body>({
    x: startBoarded ? playSpawn.boardX : layout.boat[0],
    y: layout.boat[1],
    z: startBoarded ? playSpawn.boardZ : layout.boat[2],
    yaw: startBoarded ? playSpawn.boardYaw : 0.18,
  });
  const boarded = useRef(startBoarded);
  const hasMoved = useRef(false);
  const moving = useRef(false);
  const running = useRef(false);
  const stridePhase = useRef(1.2);
  const vertical = useRef({ vy: 0, airborne: false });
  const punchLeft = useRef(0);
  const hudRef = useRef<PlayHud>({
    boarded: startBoarded,
    nearBoat: startBoarded,
    hasMoved: false,
  });
  const look = useRef<{ yaw: number; pitch: number; distance: number }>({
    yaw: startBoarded ? playSpawn.boardYaw : Math.PI,
    pitch: playFollow.defaultPitch,
    distance: startBoarded ? playFollow.boardDistance : playFollow.standDistance,
  });

  useEffect(() => {
    if (controls) {
      controls.minDistance = viewMode === "play" ? PLAY_MIN : LOOK_MIN;
      controls.maxDistance = viewMode === "play" ? PLAY_MAX : LOOK_MAX;
    }
  }, [controls, viewMode]);

  useEffect(() => {
    if (viewMode !== "play") {
      return;
    }
    const onWheel = (event: WheelEvent) => {
      if ((event.target as Element | null)?.tagName !== "CANVAS") {
        return;
      }
      event.preventDefault();
      look.current.distance += event.deltaY * 0.01;
      if (look.current.distance < PLAY_MIN) {
        look.current.distance = PLAY_MIN;
      } else if (look.current.distance > PLAY_MAX) {
        look.current.distance = PLAY_MAX;
      }
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      window.removeEventListener("wheel", onWheel);
    };
  }, [viewMode]);

  useFrame((state, delta) => {
    const dt = clampDelta(delta);
    const input = inputRef.current;
    const clockTime = state.clock.elapsedTime;
    const playing = viewMode === "play";
    const gameplayActive = playing && !inputBlocked;

    const boatPos = boat.current;
    const playerPos = player.current;
    const nearBoat =
      boarded.current ||
      distance2(playerPos.x, playerPos.z, boatPos.x, boatPos.z) <=
        BOARD_DISTANCE;

    if (gameplayActive && consumeInteract(input) && nearBoat) {
      if (boarded.current) {
        const land = nearestWalkable(boatPos.x, boatPos.z, PLAYER_RADIUS);
        playerPos.x = land.x;
        playerPos.y = land.y;
        playerPos.z = land.z;
        boarded.current = false;
      } else {
        boarded.current = true;
        playerPos.x = boatPos.x;
        playerPos.y = boatPos.y;
        playerPos.z = boatPos.z;
        playerPos.yaw = boatPos.yaw;
      }
    }

    if (!gameplayActive) {
      // Keyboard input belongs to Chơi. Do not let an accidental key press
      // move a hidden player while the visitor is inspecting a static shot.
      input.interactEdge = false;
      input.lookDx = 0;
      input.lookDy = 0;
      input.jumpEdge = false;
      input.punchEdge = false;
    }
    const glance = gameplayActive ? consumeLook(input) : { dx: 0, dy: 0 };
    if (gameplayActive && (glance.dx !== 0 || glance.dy !== 0)) {
      // Pointer Lock: movementX > 0 = mouse-right, movementY > 0 = mouse-down.
      // yaw+ looks right. pitch+ looks up, so mouse-down lowers pitch.
      look.current.yaw +=
        glance.dx *
        sceneConfig.camera.lookYawScale *
        sceneConfig.camera.lookYawSign;
      look.current.pitch -= glance.dy * sceneConfig.camera.lookPitchScale;
      if (look.current.pitch < playFollow.minPitch) {
        look.current.pitch = playFollow.minPitch;
      } else if (look.current.pitch > playFollow.maxPitch) {
        look.current.pitch = playFollow.maxPitch;
      }
      hasMoved.current = true;
      cameraGoal.current.transitioning = false;
      cameraGoal.current.userOrbit = false;
    }

    playerPos.yaw = look.current.yaw;
    if (boarded.current) {
      boatPos.yaw = look.current.yaw;
    }

    const ix = gameplayActive ? input.x : 0;
    const autoActive = gameplayActive && autoWalk && clockTime > 0.45 && clockTime < 3.8;
    const iz = autoActive && input.z === 0 ? 1 : input.z;
    const hasStick = Math.abs(ix) + Math.abs(iz) > 0.01;
    if (hasStick) {
      hasMoved.current = true;
    }

    const facingX = Math.sin(look.current.yaw);
    const facingZ = Math.cos(look.current.yaw);
    // Screen/camera right (cross(forward, up)), not anatomical right.
    // From behind, character-left is screen-right — A must use this or
    // it feels inverted.
    const rightX = -Math.cos(look.current.yaw);
    const rightZ = Math.sin(look.current.yaw);

    const wantsJump = gameplayActive && consumeJump(input);
    if (!gameplayActive || boarded.current) {
      input.punchEdge = false;
      punchLeft.current = 0;
    } else if (consumePunch(input)) {
      punchLeft.current = PUNCH_DURATION;
    }
    if (punchLeft.current > 0) {
      punchLeft.current = Math.max(0, punchLeft.current - dt);
    }
    if (boarded.current) {
      vertical.current.vy = 0;
      vertical.current.airborne = false;
      const step = iz * BOAT_SPEED * dt;
      const nx = boatPos.x + facingX * step;
      const nz = boatPos.z + facingZ * step;
      const clamped = clampBoat(boatPos.x, boatPos.z, nx, nz);
      if (boatAllowed(clamped.x, clamped.z)) {
        boatPos.x = clamped.x;
        boatPos.z = clamped.z;
      }
      playerPos.x = boatPos.x;
      playerPos.z = boatPos.z;
      playerPos.yaw = look.current.yaw;
      moving.current = Math.abs(iz) > 0.01;
      running.current = false;
    } else {
      const speed = (gameplayActive && input.run ? RUN_SPEED : WALK_SPEED) * dt;
      let dx = 0;
      let dz = 0;
      if (autoActive || hasStick) {
        dx = (facingX * iz + rightX * ix) * speed;
        dz = (facingZ * iz + rightZ * ix) * speed;
      }
      const next = resolveWalk(
        playerPos.x,
        playerPos.z,
        dx,
        dz,
        PLAYER_RADIUS,
      );
      const moved =
        Math.hypot(next.x - playerPos.x, next.z - playerPos.z) > 0.00012;
      playerPos.x = next.x;
      playerPos.z = next.z;
      if (wantsJump && !vertical.current.airborne) {
        vertical.current.vy = JUMP_SPEED;
        vertical.current.airborne = true;
        hasMoved.current = true;
      }
      if (vertical.current.airborne) {
        vertical.current.vy -= GRAVITY * dt;
        playerPos.y += vertical.current.vy * dt;
        const ground = surfaceAt(playerPos.x, playerPos.z) ?? next.y;
        if (playerPos.y <= ground && vertical.current.vy <= 0) {
          playerPos.y = ground;
          vertical.current.vy = 0;
          vertical.current.airborne = false;
        }
      } else {
        playerPos.y = next.y;
      }
      moving.current = moved || vertical.current.airborne;
      running.current = moved && gameplayActive && input.run && !vertical.current.airborne;
    }

    const bob = reducedMotion
      ? 0
      : Math.sin(clockTime * 1.35) * 0.045;
    boatPos.y = layout.boat[1] + bob;
    if (boarded.current) {
      playerPos.y = boatPos.y + playFollow.sitLift;
    }

    const boatGroup = boatRef.current;
    if (boatGroup) {
      boatGroup.position.set(boatPos.x, boatPos.y, boatPos.z);
      boatGroup.rotation.y = boatPos.yaw;
      boatGroup.rotation.z = reducedMotion
        ? 0
        : Math.sin(clockTime * 0.9) * 0.035;
    }

    const playerGroup = playerRef.current;
    if (playerGroup) {
      playerGroup.position.set(playerPos.x, playerPos.y, playerPos.z);
      playerGroup.rotation.y = playerPos.yaw;
    }
    if (moving.current && !reducedMotion) {
      const cadence = boarded.current ? 3.35 : running.current ? 10.4 : 7.1;
      stridePhase.current += dt * cadence;
    }
    applyWalkPose(
      limbsRef.current,
      boarded.current || !moving.current ? clockTime : stridePhase.current,
      boarded.current,
      moving.current && !vertical.current.airborne,
      running.current,
      reducedMotion,
      boarded.current && moving.current,
      vertical.current.airborne,
      punchLeft.current > 0,
    );

    const foliage = foliageRef.current;
    if (foliage) {
      foliage.rotation.y = reducedMotion
        ? 0
        : Math.sin(clockTime * 0.32) * 0.025;
    }

    const hud: PlayHud = {
      boarded: boarded.current,
      nearBoat,
      hasMoved: hasMoved.current,
    };
    const prev = hudRef.current;
    if (
      prev.boarded !== hud.boarded ||
      prev.nearBoat !== hud.nearBoat ||
      prev.hasMoved !== hud.hasMoved
    ) {
      hudRef.current = hud;
      onHud(hud);
    }

    const orbit = controls;
    if (!orbit) {
      return;
    }

    if (viewMode === "play") {
      const framed = playLookCamera(
        boarded.current,
        playerPos,
        look.current.yaw,
        look.current.pitch,
        look.current.distance,
      );
      camera.position.set(
        framed.position[0],
        framed.position[1],
        framed.position[2],
      );
      camera.lookAt(framed.target[0], framed.target[1], framed.target[2]);
      orbit.target.set(framed.target[0], framed.target[1], framed.target[2]);
      cameraGoal.current.transitioning = false;
      return;
    }

    if (!cameraGoal.current.transitioning) {
      return;
    }
    const step = reducedMotion ? 1 : 1 - Math.pow(0.012, dt);
    camera.position.lerp(cameraGoal.current.position, step);
    orbit.target.lerp(cameraGoal.current.target, step);
    orbit.update();
    if (
      camera.position.distanceTo(cameraGoal.current.position) < CLOSE_EPSILON &&
      orbit.target.distanceTo(cameraGoal.current.target) < CLOSE_EPSILON
    ) {
      camera.position.copy(cameraGoal.current.position);
      orbit.target.copy(cameraGoal.current.target);
      orbit.update();
      cameraGoal.current.transitioning = false;
    }
  });

  return null;
}
