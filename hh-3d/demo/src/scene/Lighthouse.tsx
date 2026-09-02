import { Html } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import type { LandmarkId, SelectHandler } from "../lib/types";
import { getLandmark, layout, palette } from "./sceneConfig";

type LighthouseProps = {
  highlighted: boolean;
  showLabel: boolean;
  onSelect: SelectHandler;
  onHover: (id: LandmarkId | null) => void;
};

export function Lighthouse({
  highlighted,
  showLabel,
  onSelect,
  onHover,
}: LighthouseProps) {
  const landmark = getLandmark("lighthouse");
  const [x, y, z] = layout.lighthouse;

  const select = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(landmark);
  };

  return (
    <group
      name="lighthouse"
      position={[x, y, z]}
      onClick={select}
      onPointerOver={(event) => {
        event.stopPropagation();
        onHover(landmark.id);
      }}
      onPointerOut={() => {
        onHover(null);
      }}
    >
      <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.85, 0.95, 0.24, 10]} />
        <meshStandardMaterial color={palette.landSand} roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.5, 0.44]} castShadow>
        <boxGeometry args={[0.2, 0.52, 0.04]} />
        <meshStandardMaterial color={palette.wood} roughness={0.82} />
      </mesh>
      <mesh position={[0, 2.15, 0]} castShadow>
        <cylinderGeometry args={[0.38, 0.46, 4.1, 12]} />
        <meshStandardMaterial
          color={palette.lighthouseWhite}
          roughness={0.45}
          emissive={highlighted ? "#fff1c8" : "#000000"}
          emissiveIntensity={highlighted ? 0.28 : 0}
        />
      </mesh>
      <mesh position={[0, 1.05, 0]} castShadow>
        <cylinderGeometry args={[0.42, 0.45, 0.78, 12]} />
        <meshStandardMaterial color={palette.lighthouseStripe} roughness={0.5} />
      </mesh>
      <mesh position={[0, 2.35, 0]} castShadow>
        <cylinderGeometry args={[0.4, 0.42, 0.78, 12]} />
        <meshStandardMaterial color={palette.lighthouseStripe} roughness={0.5} />
      </mesh>
      <mesh position={[0, 3.65, 0]} castShadow>
        <cylinderGeometry args={[0.39, 0.4, 0.72, 12]} />
        <meshStandardMaterial color={palette.lighthouseStripe} roughness={0.5} />
      </mesh>
      <mesh position={[0, 4.45, 0]} castShadow>
        <boxGeometry args={[0.95, 0.08, 0.95]} />
        <meshStandardMaterial color={palette.lighthouseWhite} />
      </mesh>
      <mesh position={[0, 4.51, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[0.53, 0.035, 6, 14]} />
        <meshStandardMaterial color={palette.wood} roughness={0.7} />
      </mesh>
      <mesh position={[0, 4.85, 0]} castShadow>
        <boxGeometry args={[0.62, 0.7, 0.62]} />
        <meshStandardMaterial
          color="#f7e7b0"
          emissive="#f2c56d"
          emissiveIntensity={0.25}
          roughness={0.3}
        />
      </mesh>
      <mesh position={[0, 5.35, 0]} castShadow>
        <coneGeometry args={[0.48, 0.42, 8]} />
        <meshStandardMaterial color={palette.lighthouseStripe} />
      </mesh>
      <mesh position={[0, 5.78, 0]} castShadow>
        <cylinderGeometry args={[0.018, 0.018, 0.5, 6]} />
        <meshStandardMaterial color={palette.wood} roughness={0.8} />
      </mesh>
      <mesh position={[0.13, 5.87, 0]} rotation={[0, 0.18, 0]} castShadow>
        <boxGeometry args={[0.26, 0.14, 0.025]} />
        <meshStandardMaterial color={palette.roof} roughness={0.78} />
      </mesh>
      {showLabel ? (
        <Html
          position={[0, 6.15, 0]}
          center
          distanceFactor={16}
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
}
