import type { SelectHandler } from "../lib/types";
import { sceneConfig } from "./sceneConfig";

const WATER_PATCHES = [
  { position: [-24, 0.026, -16] as const, size: [16, 0.018, 5] as const, rotation: -0.04, tone: "band" as const },
  { position: [-10, 0.028, -18] as const, size: [8, 0.018, 3.2] as const, rotation: 0.08, tone: "rim" as const },
  { position: [11, 0.026, -17] as const, size: [18, 0.018, 4.6] as const, rotation: -0.05, tone: "band" as const },
  { position: [25, 0.028, -9] as const, size: [9, 0.018, 5.2] as const, rotation: 0.12, tone: "rim" as const },
  { position: [-28, 0.026, -3] as const, size: [8, 0.018, 9] as const, rotation: 0.04, tone: "rim" as const },
  { position: [-14, 0.027, -7.4] as const, size: [10, 0.018, 2.5] as const, rotation: -0.09, tone: "band" as const },
  { position: [15, 0.027, -5.8] as const, size: [11, 0.018, 2.8] as const, rotation: 0.05, tone: "rim" as const },
  { position: [26, 0.026, 2.8] as const, size: [8, 0.018, 3.4] as const, rotation: -0.08, tone: "band" as const },
  { position: [-27, 0.028, 9] as const, size: [13, 0.018, 4.5] as const, rotation: -0.03, tone: "band" as const },
  { position: [-14, 0.026, 13] as const, size: [9, 0.018, 2.8] as const, rotation: 0.08, tone: "rim" as const },
  { position: [13, 0.028, 13.5] as const, size: [17, 0.018, 4.2] as const, rotation: -0.05, tone: "band" as const },
  { position: [27, 0.026, 9.5] as const, size: [8, 0.018, 2.8] as const, rotation: 0.06, tone: "rim" as const },
  { position: [-20, 0.027, 21] as const, size: [14, 0.018, 3] as const, rotation: -0.06, tone: "rim" as const },
  { position: [2, 0.026, 20] as const, size: [10, 0.018, 4] as const, rotation: 0.04, tone: "band" as const },
  { position: [23, 0.028, 21] as const, size: [13, 0.018, 3.2] as const, rotation: -0.03, tone: "rim" as const },
] as const;

export function Ocean({ onClear }: { onClear: SelectHandler }) {
  const { y, size, color, bandColor, rimColor } = sceneConfig.ocean;

  return (
    <group name="ocean">
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, y, 0]}
        receiveShadow
        onClick={(event) => {
          event.stopPropagation();
          onClear(null);
        }}
      >
        <planeGeometry args={[size, size, 1, 1]} />
        <meshStandardMaterial color={color} roughness={0.82} metalness={0.04} />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0.15, y + 0.012, 0.05]}
      >
        <ringGeometry args={[7.05, 8.85, 48]} />
        <meshBasicMaterial
          color="#d5f0ea"
          transparent
          opacity={0.32}
          depthWrite={false}
        />
      </mesh>
      <group name="water-patches">
        {WATER_PATCHES.map((patch, index) => (
          <mesh
            key={`${patch.position.join(",")}-${index}`}
            position={[patch.position[0], y + patch.position[1], patch.position[2]]}
            rotation={[0, patch.rotation, 0]}
          >
            <boxGeometry args={[...patch.size]} />
            <meshBasicMaterial
              color={patch.tone === "band" ? bandColor : rimColor}
              transparent
              opacity={patch.tone === "band" ? 0.28 : 0.2}
              depthWrite={false}
            />
          </mesh>
        ))}
      </group>
      <DistantIslands />
    </group>
  );
}

/** Quiet silhouettes give the bay a sense of depth without becoming more playable terrain. */
function DistantIslands() {
  return (
    <group name="distant-islands">
      <group position={[-38, 0.06, -30]} rotation={[0, -0.16, 0]} scale={0.85}>
        <mesh position={[0, 1.1, 0]}>
          <coneGeometry args={[3.1, 2.2, 7]} />
          <meshStandardMaterial color="#789d8d" roughness={1} />
        </mesh>
        <mesh position={[-0.7, 1.85, 0.08]} scale={[0.65, 0.28, 0.7]}>
          <coneGeometry args={[2.3, 1.2, 7]} />
          <meshStandardMaterial color="#8eaf9b" roughness={1} />
        </mesh>
        <mesh position={[0.35, 0.2, 0.35]}>
          <boxGeometry args={[5.8, 0.4, 1.7]} />
          <meshStandardMaterial color="#9bb8a1" roughness={1} />
        </mesh>
      </group>
      <group
        position={[36, 0.04, -32]}
        rotation={[0, 0.24, 0]}
        scale={0.58}
      >
        <mesh position={[0, 1.25, 0]}>
          <dodecahedronGeometry args={[2.45, 0]} />
          <meshStandardMaterial color="#76998b" roughness={1} />
        </mesh>
        <mesh position={[0.25, 0.25, 0.2]}>
          <boxGeometry args={[4.9, 0.46, 1.8]} />
          <meshStandardMaterial color="#91b09b" roughness={1} />
        </mesh>
      </group>
    </group>
  );
}
