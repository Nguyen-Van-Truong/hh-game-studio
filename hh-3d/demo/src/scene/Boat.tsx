import { Html } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { forwardRef, useRef } from "react";
import { DoubleSide, Vector2, type Group } from "three";
import type { LandmarkId, SelectHandler } from "../lib/types";
import { getLandmark, layout, palette } from "./sceneConfig";

const THUNG_PROFILE = [
  new Vector2(0.05, -0.07),
  new Vector2(0.36, -0.05),
  new Vector2(0.5, 0.03),
  new Vector2(0.64, 0.16),
  new Vector2(0.73, 0.3),
  new Vector2(0.76, 0.4),
  new Vector2(0.69, 0.43),
];

type BoatProps = {
  highlighted: boolean;
  showLabel: boolean;
  occupied: boolean;
  onSelect: SelectHandler;
  onHover: (id: LandmarkId | null) => void;
};

type ThungHullProps = {
  highlighted?: boolean;
  showOar?: boolean;
};

/** Shared original thúng: open bowl, not a torus donut. */
export function ThungHull({
  highlighted = false,
  showOar = true,
}: ThungHullProps) {
  return (
    <group name="thung-hull">
      <mesh castShadow receiveShadow>
        <latheGeometry args={[THUNG_PROFILE, 28]} />
        <meshStandardMaterial
          color={palette.boat}
          roughness={0.62}
          side={DoubleSide}
          emissive={highlighted ? "#f0c27a" : "#000000"}
          emissiveIntensity={highlighted ? 0.28 : 0}
        />
      </mesh>
      <mesh position={[0, -0.05, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[0.36, 24]} />
        <meshStandardMaterial color="#9a4e1e" roughness={0.78} />
      </mesh>
      <mesh position={[0, 0.16, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.22, 0.48, 24]} />
        <meshStandardMaterial color="#b85a24" roughness={0.7} side={DoubleSide} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.42, 0]} castShadow>
        <torusGeometry args={[0.725, 0.045, 8, 28]} />
        <meshStandardMaterial color="#e4b07a" roughness={0.5} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.22, 0]}>
        <torusGeometry args={[0.68, 0.028, 6, 24]} />
        <meshStandardMaterial color="#a34d1c" roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.18, 0]} castShadow>
        <boxGeometry args={[0.78, 0.05, 0.16]} />
        <meshStandardMaterial color={palette.wood} roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.18, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
        <boxGeometry args={[0.62, 0.04, 0.1]} />
        <meshStandardMaterial color={palette.woodLight} roughness={0.78} />
      </mesh>
      {showOar ? (
        <>
          <mesh
            position={[0.42, 0.28, 0.08]}
            rotation={[0.15, 0.4, 0.55]}
            castShadow
          >
            <cylinderGeometry args={[0.03, 0.025, 0.95, 6]} />
            <meshStandardMaterial color={palette.woodLight} />
          </mesh>
          <mesh
            position={[0.62, 0.18, 0.28]}
            rotation={[1.15, 0.2, 0.1]}
            castShadow
          >
            <boxGeometry args={[0.12, 0.02, 0.22]} />
            <meshStandardMaterial color={palette.wood} />
          </mesh>
        </>
      ) : null}
    </group>
  );
}

export const Boat = forwardRef<Group, BoatProps>(function Boat(
  { highlighted, showLabel, occupied, onSelect, onHover },
  ref,
) {
  const landmark = getLandmark("boat");

  const select = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(landmark);
  };

  return (
    <group
      ref={ref}
      name="boat"
      onClick={select}
      onPointerOver={(event) => {
        event.stopPropagation();
        onHover(landmark.id);
      }}
      onPointerOut={() => {
        onHover(null);
      }}
    >
      <ThungHull highlighted={highlighted} showOar={!occupied} />
      {showLabel ? (
        <Html
          position={[0, 1.05, 0]}
          center
          distanceFactor={14}
          occlude={false}
          style={{ pointerEvents: "auto" }}
        >
          <button
            type="button"
            className="world-label"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(landmark);
            }}
          >
            {landmark.title}
          </button>
        </Html>
      ) : null}
    </group>
  );
});

/** Second thúng in the bay. Decoration only — no AI, not boardable. */
export function IdleThung({
  reducedMotion = false,
}: {
  reducedMotion?: boolean;
}) {
  const group = useRef<Group>(null);
  const [x, y, z] = layout.idleBoat;

  useFrame((state) => {
    const node = group.current;
    if (!node) {
      return;
    }
    if (reducedMotion) {
      node.position.y = y;
      node.rotation.z = 0;
      return;
    }
    node.position.y = y + Math.sin(state.clock.elapsedTime * 1.1 + 1.4) * 0.04;
    node.rotation.z = Math.sin(state.clock.elapsedTime * 0.7 + 0.6) * 0.03;
  });

  return (
    <group ref={group} name="idle-thung" position={[x, y, z]} rotation={[0, -0.95, 0]}>
      <group scale={0.92}>
        <ThungHull showOar />
      </group>
    </group>
  );
}
