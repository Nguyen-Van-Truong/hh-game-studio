import { Html } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import { STEP_MESHES } from "../lib/walk";
import type { LandmarkId, SelectHandler } from "../lib/types";
import { getLandmark, layout, palette } from "./sceneConfig";

type HarborProps = {
  highlighted: boolean;
  showLabel: boolean;
  onSelect: SelectHandler;
  onHover: (id: LandmarkId | null) => void;
};

export function Harbor({
  highlighted,
  showLabel,
  onSelect,
  onHover,
}: HarborProps) {
  const landmark = getLandmark("harbor");
  const [x, y, z] = layout.harbor;
  const [width, height, depth] = layout.pierSize;

  const select = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(landmark);
  };

  return (
    <group
      name="harbor"
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
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial
          color={palette.wood}
          roughness={0.88}
          emissive={highlighted ? "#e0b56a" : "#000000"}
          emissiveIntensity={highlighted ? 0.22 : 0}
        />
      </mesh>
      {[-2.6, -0.7, 1.2, 2.8].map((offset) => (
        <mesh key={offset} position={[offset, -0.62, 0]} castShadow>
          <boxGeometry args={[0.16, 1.18, 0.16]} />
          <meshStandardMaterial color={palette.woodLight} roughness={0.86} />
        </mesh>
      ))}
      {[-2.4, 0.15, 2.55].map((offset) => (
        <mesh key={`pile-front-${offset}`} position={[offset, -0.58, 0.62]} castShadow>
          <cylinderGeometry args={[0.07, 0.09, 1.12, 7]} />
          <meshStandardMaterial color={palette.wood} roughness={0.88} />
        </mesh>
      ))}
      {[-2.4, 2.55].map((offset) => (
        <mesh key={`pile-back-${offset}`} position={[offset, -0.58, -0.58]} castShadow>
          <cylinderGeometry args={[0.07, 0.09, 1.12, 7]} />
          <meshStandardMaterial color={palette.wood} roughness={0.88} />
        </mesh>
      ))}
      <mesh position={[-0.4, 0.16, 0]} receiveShadow>
        <boxGeometry args={[width * 0.92, 0.04, depth * 0.82]} />
        <meshStandardMaterial color={palette.woodLight} roughness={0.8} />
      </mesh>
      {[-2.7, -1.8, -0.9, 0, 0.9, 1.8, 2.7].map((offset) => (
        <mesh key={`plank-${offset}`} position={[offset, 0.13, 0]} receiveShadow>
          <boxGeometry args={[0.035, 0.035, depth * 0.9]} />
          <meshStandardMaterial color={palette.wood} roughness={0.86} />
        </mesh>
      ))}
      {[-2.95, 2.95].map((offset) => (
        <mesh key={`post-${offset}`} position={[offset, 0.36, 0]} castShadow>
          <cylinderGeometry args={[0.09, 0.11, 0.42, 8]} />
          <meshStandardMaterial color={palette.woodLight} roughness={0.84} />
        </mesh>
      ))}
      {STEP_MESHES.map((step) => (
        <mesh
          key={step.position.join(",")}
          position={[
            step.position[0] - x,
            step.position[1] - y,
            step.position[2] - z,
          ]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[...step.size]} />
          <meshStandardMaterial color={palette.woodLight} roughness={0.84} />
        </mesh>
      ))}
      {showLabel ? (
        <Html
          position={[0, 1.15, 0]}
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
}
