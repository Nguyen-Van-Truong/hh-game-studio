import { RoundedBox } from "@react-three/drei";
import { useLayoutEffect, useRef, type RefObject } from "react";
import type { Group } from "three";

export type PersonLimbs = {
  root: Group;
  torso: Group;
  leftArm: Group;
  rightArm: Group;
  leftFore: Group;
  rightFore: Group;
  leftLeg: Group;
  rightLeg: Group;
  leftShin: Group;
  rightShin: Group;
};

export type PersonColors = {
  skin: string;
  skinShadow: string;
  hair: string;
  shirt: string;
  collar: string;
  pants: string;
  shoe: string;
};

export const DEFAULT_COLORS: PersonColors = {
  skin: "#e8c09a",
  skinShadow: "#d4a882",
  hair: "#1f1916",
  shirt: "#2a7d78",
  collar: "#1a5552",
  pants: "#2a3331",
  shoe: "#5c4030",
};

export const SEAT_COLORS: Record<string, PersonColors> = {
  a: DEFAULT_COLORS,
  b: {
    skin: "#e8c09a",
    skinShadow: "#d4a882",
    hair: "#1f1916",
    shirt: "#c4a046",
    collar: "#8a7028",
    pants: "#2a3331",
    shoe: "#5c4030",
  },
  c: {
    skin: "#e8c09a",
    skinShadow: "#d4a882",
    hair: "#1f1916",
    shirt: "#7a6a7a",
    collar: "#4e4450",
    pants: "#2a3331",
    shoe: "#5c4030",
  },
};

export function colorsForSeat(seat: string): PersonColors {
  return SEAT_COLORS[seat] ?? DEFAULT_COLORS;
}

export function tunicShirtForSeat(seat: string): string {
  return colorsForSeat(seat).shirt;
}

type PersonProps = {
  colors: PersonColors;
  limbsRef: RefObject<PersonLimbs | null>;
};

/**
 * Stylized walker. Hòn Gió proportion language (not the island).
 * Bind pose standing, origin at feet. Long áo-bà-ba tunic past the hip.
 * Slim pelvis slab + ordinary thighs. No bowling-ball hip spheres.
 */
export function Person({ colors, limbsRef }: PersonProps) {
  const root = useRef<Group>(null);
  const torso = useRef<Group>(null);
  const leftArm = useRef<Group>(null);
  const rightArm = useRef<Group>(null);
  const leftFore = useRef<Group>(null);
  const rightFore = useRef<Group>(null);
  const leftLeg = useRef<Group>(null);
  const rightLeg = useRef<Group>(null);
  const leftShin = useRef<Group>(null);
  const rightShin = useRef<Group>(null);

  useLayoutEffect(() => {
    if (
      root.current &&
      torso.current &&
      leftArm.current &&
      rightArm.current &&
      leftFore.current &&
      rightFore.current &&
      leftLeg.current &&
      rightLeg.current &&
      leftShin.current &&
      rightShin.current
    ) {
      limbsRef.current = {
        root: root.current,
        torso: torso.current,
        leftArm: leftArm.current,
        rightArm: rightArm.current,
        leftFore: leftFore.current,
        rightFore: rightFore.current,
        leftLeg: leftLeg.current,
        rightLeg: rightLeg.current,
        leftShin: leftShin.current,
        rightShin: rightShin.current,
      };
    }
    return () => {
      limbsRef.current = null;
    };
  }, [limbsRef]);

  return (
    <group name="person" ref={root}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.018, 0]}>
        <circleGeometry args={[0.3, 16]} />
        <meshBasicMaterial color="#163230" transparent opacity={0.3} depthWrite={false} />
      </mesh>
      <RoundedBox position={[0, 0.5, 0]} args={[0.22, 0.11, 0.13]} radius={0.028} smoothness={3} castShadow>
        <meshStandardMaterial color={colors.pants} roughness={0.92} />
      </RoundedBox>
      <group ref={leftLeg} position={[-0.105, 0.56, 0]}>
        <mesh position={[0, -0.14, 0]} castShadow>
          <capsuleGeometry args={[0.062, 0.2, 4, 8]} />
          <meshStandardMaterial color={colors.pants} roughness={0.9} />
        </mesh>
        <group ref={leftShin} position={[0, -0.32, 0]}>
          <mesh position={[0, -0.12, 0]} castShadow>
            <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
            <meshStandardMaterial color={colors.pants} roughness={0.9} />
          </mesh>
          <mesh position={[0, -0.26, 0.06]} castShadow>
            <boxGeometry args={[0.13, 0.055, 0.2]} />
            <meshStandardMaterial color={colors.shoe} roughness={0.88} />
          </mesh>
        </group>
      </group>
      <group ref={rightLeg} position={[0.105, 0.56, 0]}>
        <mesh position={[0, -0.14, 0]} castShadow>
          <capsuleGeometry args={[0.062, 0.2, 4, 8]} />
          <meshStandardMaterial color={colors.pants} roughness={0.9} />
        </mesh>
        <group ref={rightShin} position={[0, -0.32, 0]}>
          <mesh position={[0, -0.12, 0]} castShadow>
            <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
            <meshStandardMaterial color={colors.pants} roughness={0.9} />
          </mesh>
          <mesh position={[0, -0.26, 0.06]} castShadow>
            <boxGeometry args={[0.13, 0.055, 0.2]} />
            <meshStandardMaterial color={colors.shoe} roughness={0.88} />
          </mesh>
        </group>
      </group>
      <group ref={torso} position={[0, 0.62, 0]}>
        <RoundedBox position={[0, 0.02, -0.02]} args={[0.4, 0.98, 0.34]} radius={0.12} smoothness={3} castShadow>
          <meshStandardMaterial color={colors.shirt} roughness={0.9} />
        </RoundedBox>
        <mesh position={[0, 0.4, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <capsuleGeometry args={[0.08, 0.3, 4, 8]} />
          <meshStandardMaterial color={colors.shirt} roughness={0.88} />
        </mesh>
        <mesh position={[0, 0.48, 0]} castShadow>
          <cylinderGeometry args={[0.07, 0.08, 0.07, 10]} />
          <meshStandardMaterial color={colors.collar} roughness={0.86} />
        </mesh>
        <mesh position={[0, 0.54, 0]} castShadow>
          <cylinderGeometry args={[0.038, 0.044, 0.08, 8]} />
          <meshStandardMaterial color={colors.skin} roughness={0.62} />
        </mesh>
        <group position={[0, 0.7, 0]} name="head">
          <mesh castShadow>
            <sphereGeometry args={[0.136, 14, 12]} />
            <meshStandardMaterial color={colors.skin} roughness={0.58} />
          </mesh>
          <mesh position={[0, 0.05, -0.018]} scale={[1.04, 0.82, 1.08]} castShadow>
            <sphereGeometry args={[0.138, 12, 10]} />
            <meshStandardMaterial color={colors.hair} roughness={0.86} />
          </mesh>
          <mesh position={[0, 0.01, -0.12]} scale={[0.95, 0.78, 0.92]} castShadow>
            <sphereGeometry args={[0.108, 10, 8]} />
            <meshStandardMaterial color={colors.hair} roughness={0.86} />
          </mesh>
          <mesh position={[-0.11, 0.0, -0.035]} scale={[0.52, 0.72, 0.7]} castShadow>
            <sphereGeometry args={[0.09, 8, 6]} />
            <meshStandardMaterial color={colors.hair} roughness={0.86} />
          </mesh>
          <mesh position={[0.11, 0.0, -0.035]} scale={[0.52, 0.72, 0.7]} castShadow>
            <sphereGeometry args={[0.09, 8, 6]} />
            <meshStandardMaterial color={colors.hair} roughness={0.86} />
          </mesh>
          <mesh position={[0.128, 0.0, 0.01]} rotation={[0, 0, 0.18]} castShadow>
            <sphereGeometry args={[0.02, 6, 5]} />
            <meshStandardMaterial color={colors.skin} />
          </mesh>
          <mesh position={[-0.128, 0.0, 0.01]} rotation={[0, 0, -0.18]} castShadow>
            <sphereGeometry args={[0.02, 6, 5]} />
            <meshStandardMaterial color={colors.skin} />
          </mesh>
          <mesh position={[0.072, 0.012, 0.108]} castShadow>
            <sphereGeometry args={[0.015, 6, 5]} />
            <meshStandardMaterial color="#2a3334" />
          </mesh>
          <mesh position={[-0.072, 0.012, 0.108]} castShadow>
            <sphereGeometry args={[0.015, 6, 5]} />
            <meshStandardMaterial color="#2a3334" />
          </mesh>
          <mesh position={[0, -0.012, 0.122]} castShadow>
            <sphereGeometry args={[0.016, 6, 5]} />
            <meshStandardMaterial color={colors.skinShadow} />
          </mesh>
        </group>
        <group ref={leftArm} position={[-0.24, 0.4, 0.02]}>
          <mesh position={[0, -0.13, 0]} castShadow>
            <capsuleGeometry args={[0.062, 0.18, 4, 8]} />
            <meshStandardMaterial color={colors.shirt} roughness={0.88} />
          </mesh>
          <group ref={leftFore} position={[0, -0.28, 0]}>
            <mesh position={[0, -0.11, 0]} castShadow>
              <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
              <meshStandardMaterial color={colors.skin} roughness={0.58} />
            </mesh>
            <mesh position={[0, -0.22, 0.03]} castShadow>
              <sphereGeometry args={[0.056, 8, 6]} />
              <meshStandardMaterial color={colors.skin} roughness={0.58} />
            </mesh>
          </group>
        </group>
        <group ref={rightArm} position={[0.24, 0.4, 0.02]}>
          <mesh position={[0, -0.13, 0]} castShadow>
            <capsuleGeometry args={[0.062, 0.18, 4, 8]} />
            <meshStandardMaterial color={colors.shirt} roughness={0.88} />
          </mesh>
          <group ref={rightFore} position={[0, -0.28, 0]}>
            <mesh position={[0, -0.11, 0]} castShadow>
              <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
              <meshStandardMaterial color={colors.skin} roughness={0.58} />
            </mesh>
            <mesh position={[0, -0.22, 0.03]} castShadow>
              <sphereGeometry args={[0.056, 8, 6]} />
              <meshStandardMaterial color={colors.skin} roughness={0.58} />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
}

/** Stylized opposite-arm / opposite-leg. Not mocap. */
export const WALK_CYCLE_KIND = "opposite-stride" as const;
export const WALK_STRIDE = 1.22;
export const SPRINT_STRIDE = 1.48;
export const WALK_ARM_SWING = 1.35;
export const SPRINT_ARM_SWING = 1.62;
export const WALK_RATE = 9.4;
export const SPRINT_RATE = 12.8;

export type WalkLimbSample = {
  leftLegX: number;
  rightLegX: number;
  leftArmX: number;
  rightArmX: number;
  leftShinX: number;
  rightShinX: number;
  stride: number;
  armSwing: number;
  opposite: boolean;
};

/** Pure sample so tests / CDP can prove opposite limbs without Three. */
export function sampleWalkLimbs(time: number, running: boolean, scale = 1): WalkLimbSample {
  const left = Math.sin(time);
  const right = -left;
  const stride = (running ? SPRINT_STRIDE : WALK_STRIDE) * scale;
  const armSwing = (running ? SPRINT_ARM_SWING : WALK_ARM_SWING) * scale;
  const knee = running ? 1.36 : 1.05;
  const leftLegX = left * stride;
  const rightLegX = right * stride;
  const leftArmX = -left * armSwing;
  const rightArmX = -right * armSwing;
  return {
    leftLegX,
    rightLegX,
    leftArmX,
    rightArmX,
    leftShinX: Math.max(0.16, -left) * knee,
    rightShinX: Math.max(0.16, -right) * knee,
    stride,
    armSwing,
    opposite: leftLegX * leftArmX <= 0 && rightLegX * rightArmX <= 0,
  };
}

export type WalkCycleProof = {
  kind: typeof WALK_CYCLE_KIND;
  moving: boolean;
  running: boolean;
  leftLeg: number;
  rightLeg: number;
  leftArm: number;
  rightArm: number;
  spread: number;
  armSpread: number;
  opposite: boolean;
};

export function readWalkCycleProof(): WalkCycleProof | null {
  const held = (globalThis as { __hhWalkCycle?: WalkCycleProof }).__hhWalkCycle;
  return held ?? null;
}

function measureWalkCycle(
  limbs: PersonLimbs,
  moving: boolean,
  running: boolean,
): WalkCycleProof {
  const leftLeg = limbs.leftLeg.rotation.x;
  const rightLeg = limbs.rightLeg.rotation.x;
  const leftArm = limbs.leftArm.rotation.x;
  const rightArm = limbs.rightArm.rotation.x;
  const spread = Math.abs(leftLeg - rightLeg);
  const armSpread = Math.abs(leftArm - rightArm);
  const opposite = leftLeg * leftArm <= 0.04 && rightLeg * rightArm <= 0.04;
  return {
    kind: WALK_CYCLE_KIND,
    moving,
    running,
    leftLeg,
    rightLeg,
    leftArm,
    rightArm,
    spread,
    armSpread,
    opposite,
  };
}

function writeProofToEl(node: Element | null, live: WalkCycleProof): void {
  if (!(node instanceof HTMLElement)) {
    return;
  }
  node.dataset.walkCycle = live.kind;
  node.dataset.limbMoving = live.moving ? "1" : "0";
  node.dataset.limbRunning = live.running ? "1" : "0";
  node.dataset.limbLeftLeg = live.leftLeg.toFixed(3);
  node.dataset.limbRightLeg = live.rightLeg.toFixed(3);
  node.dataset.limbLeftArm = live.leftArm.toFixed(3);
  node.dataset.limbRightArm = live.rightArm.toFixed(3);
  node.dataset.limbSpread = live.spread.toFixed(3);
  node.dataset.limbArmSpread = live.armSpread.toFixed(3);
  node.dataset.limbOpposite = live.opposite ? "1" : "0";
}

export function writeWalkCycleProof(
  limbs: PersonLimbs,
  moving: boolean,
  running: boolean,
): void {
  const live = measureWalkCycle(limbs, moving, running);
  (globalThis as { __hhWalkCycle?: WalkCycleProof }).__hhWalkCycle = live;
  writeProofToEl(document.querySelector("canvas.play-canvas"), live);
  writeProofToEl(document.querySelector("[data-testid='walk-cycle-proof']"), live);
}

/** Second-seat proof: B can read A's opposite-stride from the remote label. */
export function writeRemoteWalkCycleProof(
  seat: string,
  limbs: PersonLimbs,
  moving: boolean,
  running: boolean,
): void {
  const live = measureWalkCycle(limbs, moving, running);
  const bag =
    ((globalThis as { __hhRemoteWalkCycle?: Record<string, WalkCycleProof> }).__hhRemoteWalkCycle ??=
      {});
  bag[seat] = live;
  writeProofToEl(document.querySelector(`[data-testid="remote-avatar-${seat}"]`), live);
  writeProofToEl(document.querySelector(`[data-testid="remote-walk-cycle-${seat}"]`), live);
}

export function applyJumpPose(limbs: PersonLimbs): void {
  limbs.root.position.set(0, 0.04, 0);
  limbs.root.rotation.set(0, 0, 0);
  limbs.torso.rotation.set(0.12, 0, 0);
  limbs.leftLeg.rotation.set(-0.55, 0.06, 0.06);
  limbs.rightLeg.rotation.set(-0.22, -0.05, -0.05);
  limbs.leftShin.rotation.set(0.95, 0, 0);
  limbs.rightShin.rotation.set(0.72, 0, 0);
  limbs.leftArm.rotation.set(-0.85, 0.18, 0.72);
  limbs.rightArm.rotation.set(-0.7, -0.16, -0.72);
  limbs.leftFore.rotation.set(0.35, 0, 0);
  limbs.rightFore.rotation.set(0.32, 0, 0);
}

/** In-place turn. Weight shift + opposite arms so the behind camera sees it. */
export function applyTurnPose(limbs: PersonLimbs, time: number, reducedMotion: boolean): void {
  const sway = reducedMotion ? 0 : Math.sin(time * 7.2);
  limbs.root.position.set(0, 0.012, 0);
  limbs.root.rotation.set(0, sway * 0.12, sway * 0.08);
  limbs.torso.rotation.set(0.1, 0.32 + sway * 0.1, 0);
  limbs.leftLeg.rotation.set(0.28, 0.1, 0.08);
  limbs.rightLeg.rotation.set(-0.22, -0.08, -0.06);
  limbs.leftShin.rotation.set(0.2, 0, 0);
  limbs.rightShin.rotation.set(0.42, 0, 0);
  limbs.leftArm.rotation.set(-0.42 + sway * 0.12, 0.22, 0.62);
  limbs.rightArm.rotation.set(0.48 - sway * 0.1, -0.18, -0.68);
  limbs.leftFore.rotation.set(0.38, 0, 0);
  limbs.rightFore.rotation.set(0.28, 0, 0);
}

export function applyWalkPose(
  limbs: PersonLimbs | null,
  time: number,
  moving: boolean,
  reducedMotion: boolean,
  jumping = false,
  running = false,
  turning = false,
): void {
  if (!limbs) {
    return;
  }
  if (jumping) {
    applyJumpPose(limbs);
    return;
  }
  if (turning && !moving) {
    applyTurnPose(limbs, time, reducedMotion);
    return;
  }
  limbs.root.position.x = 0;
  limbs.root.position.z = 0;
  if (!moving) {
    const breath = reducedMotion ? 0 : Math.sin(time * 1.55);
    const weight = reducedMotion ? 0 : Math.sin(time * 0.85);
    limbs.root.position.y = breath * 0.01;
    limbs.root.rotation.set(0, 0, weight * 0.018);
    limbs.torso.rotation.set(0.04 + breath * 0.012, 0, 0);
    limbs.leftArm.rotation.set(0.08, 0.04, 0.22);
    limbs.rightArm.rotation.set(0.08, -0.04, -0.22);
    limbs.leftFore.rotation.set(0.2, 0, 0);
    limbs.rightFore.rotation.set(0.2, 0, 0);
    limbs.leftLeg.rotation.set(0.03, 0.02, 0.02);
    limbs.rightLeg.rotation.set(-0.02, -0.02, -0.02);
    limbs.leftShin.rotation.set(0.06, 0, 0);
    limbs.rightShin.rotation.set(0.05, 0, 0);
    return;
  }
  const damp = reducedMotion ? 0.55 : 1;
  const left = Math.sin(time);
  const right = -left;
  const sample = sampleWalkLimbs(time, running, damp);
  const flare = (running ? 0.7 : 0.56) * damp;
  const bob = (running ? 0.055 : 0.036) * Math.abs(Math.sin(time)) * damp;
  const lean = (running ? 0.18 : 0.1) * damp;
  const twist = left * (running ? 0.24 : 0.16) * damp;
  limbs.root.position.y = bob;
  limbs.root.rotation.set(0, twist * 0.42, -left * 0.1);
  limbs.torso.rotation.set(lean, -twist, 0);
  limbs.leftLeg.rotation.set(sample.leftLegX, left * 0.1, 0.05);
  limbs.rightLeg.rotation.set(sample.rightLegX, right * 0.1, -0.05);
  limbs.leftShin.rotation.set(sample.leftShinX, 0, 0);
  limbs.rightShin.rotation.set(sample.rightShinX, 0, 0);
  limbs.leftArm.rotation.set(sample.leftArmX, left * 0.28, flare + left * 0.18);
  limbs.rightArm.rotation.set(sample.rightArmX, right * 0.28, -(flare + right * 0.18));
  limbs.leftFore.rotation.set(0.28 + Math.max(0, left) * 0.62, 0, 0);
  limbs.rightFore.rotation.set(0.28 + Math.max(0, right) * 0.62, 0, 0);
}
