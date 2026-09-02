import { RoundedBox } from "@react-three/drei";
import { useLayoutEffect, useRef, type RefObject } from "react";
import type { Group } from "three";
import { personPalette } from "./sceneConfig";

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
  oar: Group;
};

type PersonProps = {
  seated: boolean;
  limbsRef: RefObject<PersonLimbs | null>;
};

const skin = personPalette.skin;
const hair = personPalette.hair;
const shirt = personPalette.shirt;
const collar = personPalette.collar;
const pants = personPalette.pants;
const shoe = personPalette.shoe;

/**
 * Original coastal villager. Bind pose is standing (origin at feet).
 * Walk / idle / sit / oar live in applyWalkPose — do not bake sit into JSX.
 *
 * Construction: one long áo-bà-ba tunic that hangs past the hip joint,
 * over a slim pelvis slab + ordinary thighs. No skin, cream yoke, or
 * tan sash at the waist. Do not close gaps with giant hip spheres —
 * those read as a bowling-ball seat from the high-behind play camera.
 */
export function Person({ seated, limbsRef }: PersonProps) {
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
  const oar = useRef<Group>(null);

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
      rightShin.current &&
      oar.current
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
        oar: oar.current,
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
        <meshBasicMaterial
          color="#163230"
          transparent
          opacity={0.3}
          depthWrite={false}
        />
      </mesh>

      {/* Slim crotch fill on ROOT so walk flare / sit cannot open a hole. Hidden under the tunic. */}
      <RoundedBox
        position={[0, 0.5, 0]}
        args={[0.22, 0.11, 0.13]}
        radius={0.028}
        smoothness={3}
        castShadow
      >
        <meshStandardMaterial color={pants} roughness={0.92} />
      </RoundedBox>

      <group ref={leftLeg} position={[-0.105, 0.56, 0]}>
        <mesh position={[0, -0.14, 0]} castShadow>
          <capsuleGeometry args={[0.062, 0.2, 4, 8]} />
          <meshStandardMaterial color={pants} roughness={0.9} />
        </mesh>
        <group ref={leftShin} position={[0, -0.32, 0]}>
          <mesh position={[0, -0.12, 0]} castShadow>
            <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
            <meshStandardMaterial color={pants} roughness={0.9} />
          </mesh>
          <mesh position={[0, -0.26, 0.06]} castShadow>
            <boxGeometry args={[0.13, 0.055, 0.2]} />
            <meshStandardMaterial color={shoe} roughness={0.88} />
          </mesh>
        </group>
      </group>
      <group ref={rightLeg} position={[0.105, 0.56, 0]}>
        <mesh position={[0, -0.14, 0]} castShadow>
          <capsuleGeometry args={[0.062, 0.2, 4, 8]} />
          <meshStandardMaterial color={pants} roughness={0.9} />
        </mesh>
        <group ref={rightShin} position={[0, -0.32, 0]}>
          <mesh position={[0, -0.12, 0]} castShadow>
            <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
            <meshStandardMaterial color={pants} roughness={0.9} />
          </mesh>
          <mesh position={[0, -0.26, 0.06]} castShadow>
            <boxGeometry args={[0.13, 0.055, 0.2]} />
            <meshStandardMaterial color={shoe} roughness={0.88} />
          </mesh>
        </group>
      </group>

      <group ref={torso} position={[0, 0.62, 0]}>
        {/* One tunic — hem well below the hip joint so the high-behind camera never sees a seat gap. */}
        <RoundedBox
          position={[0, 0.02, -0.02]}
          args={[0.4, 0.98, 0.34]}
          radius={0.12}
          smoothness={3}
          castShadow
        >
          <meshStandardMaterial color={shirt} roughness={0.9} />
        </RoundedBox>
        <mesh position={[0, 0.4, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <capsuleGeometry args={[0.08, 0.3, 4, 8]} />
          <meshStandardMaterial color={shirt} roughness={0.88} />
        </mesh>
        <mesh position={[0, 0.48, 0]} castShadow>
          <cylinderGeometry args={[0.07, 0.08, 0.07, 10]} />
          <meshStandardMaterial color={collar} roughness={0.86} />
        </mesh>
        <mesh position={[0, 0.54, 0]} castShadow>
          <cylinderGeometry args={[0.038, 0.044, 0.08, 8]} />
          <meshStandardMaterial color={skin} roughness={0.62} />
        </mesh>

        <group position={[0, 0.7, 0]} name="head">
          <mesh castShadow>
            <sphereGeometry args={[0.136, 14, 12]} />
            <meshStandardMaterial color={skin} roughness={0.58} />
          </mesh>
          {/* Hair is a closed helmet with nape/side mass — not a flat bowl stamp. */}
          <mesh position={[0, 0.05, -0.018]} scale={[1.04, 0.82, 1.08]} castShadow>
            <sphereGeometry args={[0.138, 12, 10]} />
            <meshStandardMaterial color={hair} roughness={0.86} />
          </mesh>
          <mesh position={[0, 0.01, -0.12]} scale={[0.95, 0.78, 0.92]} castShadow>
            <sphereGeometry args={[0.108, 10, 8]} />
            <meshStandardMaterial color={hair} roughness={0.86} />
          </mesh>
          <mesh position={[-0.11, 0.0, -0.035]} scale={[0.52, 0.72, 0.7]} castShadow>
            <sphereGeometry args={[0.09, 8, 6]} />
            <meshStandardMaterial color={hair} roughness={0.86} />
          </mesh>
          <mesh position={[0.11, 0.0, -0.035]} scale={[0.52, 0.72, 0.7]} castShadow>
            <sphereGeometry args={[0.09, 8, 6]} />
            <meshStandardMaterial color={hair} roughness={0.86} />
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
            <meshStandardMaterial color={personPalette.skinShadow} />
          </mesh>
          <mesh position={[0.128, 0.0, 0.01]} rotation={[0, 0, 0.18]} castShadow>
            <sphereGeometry args={[0.02, 6, 5]} />
            <meshStandardMaterial color={skin} />
          </mesh>
          <mesh position={[-0.128, 0.0, 0.01]} rotation={[0, 0, -0.18]} castShadow>
            <sphereGeometry args={[0.02, 6, 5]} />
            <meshStandardMaterial color={skin} />
          </mesh>
        </group>

        <group ref={leftArm} position={[-0.24, 0.4, 0.02]}>
          <mesh position={[0, -0.13, 0]} castShadow>
            <capsuleGeometry args={[0.062, 0.18, 4, 8]} />
            <meshStandardMaterial color={shirt} roughness={0.88} />
          </mesh>
          <group ref={leftFore} position={[0, -0.28, 0]}>
            <mesh position={[0, -0.11, 0]} castShadow>
              <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
              <meshStandardMaterial color={skin} roughness={0.58} />
            </mesh>
            <mesh position={[0, -0.22, 0.03]} castShadow>
              <sphereGeometry args={[0.056, 8, 6]} />
              <meshStandardMaterial color={skin} roughness={0.58} />
            </mesh>
          </group>
        </group>
        <group ref={rightArm} position={[0.24, 0.4, 0.02]}>
          <mesh position={[0, -0.13, 0]} castShadow>
            <capsuleGeometry args={[0.062, 0.18, 4, 8]} />
            <meshStandardMaterial color={shirt} roughness={0.88} />
          </mesh>
          <group ref={rightFore} position={[0, -0.28, 0]}>
            <mesh position={[0, -0.11, 0]} castShadow>
              <capsuleGeometry args={[0.05, 0.16, 4, 8]} />
              <meshStandardMaterial color={skin} roughness={0.58} />
            </mesh>
            <mesh position={[0, -0.22, 0.03]} castShadow>
              <sphereGeometry args={[0.056, 8, 6]} />
              <meshStandardMaterial color={skin} roughness={0.58} />
            </mesh>
          </group>
        </group>

        <group
          ref={oar}
          name="oar"
          visible={seated}
          position={[0.16, 0.02, 0.3]}
        >
          <mesh
            rotation={[0.95, 0, 0.15]}
            position={[0.08, -0.12, 0.22]}
            castShadow
          >
            <cylinderGeometry args={[0.02, 0.024, 0.98, 6]} />
            <meshStandardMaterial color="#a56d48" roughness={0.7} />
          </mesh>
          <mesh
            position={[0.12, -0.48, 0.52]}
            rotation={[0.95, 0.05, 0.1]}
            castShadow
          >
            <boxGeometry args={[0.2, 0.3, 0.04]} />
            <meshStandardMaterial color="#8b5a3c" roughness={0.75} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

export function applyWalkPose(
  limbs: PersonLimbs | null,
  time: number,
  seated: boolean,
  moving: boolean,
  running: boolean,
  reducedMotion: boolean,
  sailing = false,
  jumping = false,
  punching = false,
): void {
  if (!limbs) {
    return;
  }

  if (seated) {
    applySitPose(limbs, time, sailing, reducedMotion);
    return;
  }

  limbs.oar.visible = false;

  if (jumping) {
    applyJumpPose(limbs);
    return;
  }

  if (punching) {
    applyPunchPose(limbs, time);
    return;
  }
  limbs.root.position.x = 0;
  limbs.root.position.z = 0;

  if (!moving || reducedMotion) {
    const breath = reducedMotion ? 0 : Math.sin(time * 1.7);
    limbs.root.position.y = breath * 0.012;
    limbs.root.rotation.set(0, 0, breath * 0.03);
    limbs.torso.rotation.set(0.05 + breath * 0.02, 0, 0);
    limbs.leftArm.rotation.set(0.1, 0.05, 0.24);
    limbs.rightArm.rotation.set(0.1, -0.05, -0.24);
    limbs.leftFore.rotation.set(0.24, 0, 0);
    limbs.rightFore.rotation.set(0.24, 0, 0);
    limbs.leftLeg.rotation.set(0.04, 0.03, 0.03);
    limbs.rightLeg.rotation.set(-0.03, -0.03, -0.03);
    limbs.leftShin.rotation.set(0.08, 0, 0);
    limbs.rightShin.rotation.set(0.07, 0, 0);
    return;
  }

  const phase = time;
  const left = Math.sin(phase);
  const right = -left;
  const stride = running ? 1.08 : 0.86;
  const armSwing = running ? 1.12 : 0.9;
  const flare = running ? 0.64 : 0.52;
  const bob = (running ? 0.05 : 0.032) * Math.abs(Math.sin(phase));
  const lean = running ? 0.15 : 0.08;
  const knee = running ? 1.18 : 0.88;
  const twist = left * (running ? 0.2 : 0.14);

  limbs.root.position.y = bob;
  limbs.root.rotation.set(0, twist * 0.4, -left * 0.09);
  limbs.torso.rotation.set(lean, -twist, 0);
  limbs.leftLeg.rotation.set(left * stride, left * 0.08, 0.04);
  limbs.rightLeg.rotation.set(right * stride, right * 0.08, -0.04);
  limbs.leftShin.rotation.set(Math.max(0.14, -left) * knee, 0, 0);
  limbs.rightShin.rotation.set(Math.max(0.14, -right) * knee, 0, 0);
  limbs.leftArm.rotation.set(-left * armSwing, left * 0.22, flare + left * 0.14);
  limbs.rightArm.rotation.set(
    -right * armSwing,
    right * 0.22,
    -(flare + right * 0.14),
  );
  limbs.leftFore.rotation.set(0.3 + Math.max(0, left) * 0.5, 0, 0);
  limbs.rightFore.rotation.set(0.3 + Math.max(0, right) * 0.5, 0, 0);
}

function applyJumpPose(limbs: PersonLimbs): void {
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

function applyPunchPose(limbs: PersonLimbs, time: number): void {
  const jab = 0.5 + 0.5 * Math.sin(time * 18);
  limbs.root.position.set(0, 0.01, 0.02);
  limbs.root.rotation.set(0, 0, 0);
  limbs.torso.rotation.set(0.1, -0.22, 0);
  limbs.leftLeg.rotation.set(0.12, 0.03, 0.03);
  limbs.rightLeg.rotation.set(-0.18, -0.03, -0.03);
  limbs.leftShin.rotation.set(0.16, 0, 0);
  limbs.rightShin.rotation.set(0.28, 0, 0);
  limbs.leftArm.rotation.set(0.35, 0.2, 0.62);
  limbs.rightArm.rotation.set(-1.15 - jab * 0.25, -0.12, -0.18);
  limbs.leftFore.rotation.set(0.55, 0, 0);
  limbs.rightFore.rotation.set(0.08, 0, 0);
}

function applySitPose(
  limbs: PersonLimbs,
  time: number,
  sailing: boolean,
  reducedMotion: boolean,
): void {
  const dip =
    sailing && !reducedMotion ? Math.sin(time * 3.35) * 0.48 : 0.08;
  limbs.root.position.set(0, 0.06, 0.02);
  limbs.root.rotation.set(0, 0, 0);
  limbs.torso.rotation.set(0.16, 0, 0);
  limbs.leftLeg.rotation.set(-1.08, 0.08, 0.1);
  limbs.rightLeg.rotation.set(-1.04, -0.08, -0.1);
  limbs.leftShin.rotation.set(1.62, 0, 0);
  limbs.rightShin.rotation.set(1.58, 0, 0);
  limbs.leftArm.rotation.set(0.92 + dip * 0.1, 0.34, 0.58);
  limbs.rightArm.rotation.set(0.88 + dip * 0.1, -0.28, -0.58);
  limbs.leftFore.rotation.set(0.28, 0.12, 0.06);
  limbs.rightFore.rotation.set(0.26, -0.1, -0.06);
  limbs.oar.visible = true;
  limbs.oar.rotation.set(0.12 + dip, 0.08, 0.06);
}
