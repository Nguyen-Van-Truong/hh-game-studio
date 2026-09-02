import { Html, RoundedBox } from "@react-three/drei";
import { forwardRef, useLayoutEffect, useRef } from "react";
import type { ThreeEvent } from "@react-three/fiber";
import { InstancedMesh, Object3D, type Group } from "three";
import { BEACH_MESHES } from "../lib/walk";
import type { LandmarkId, SelectHandler } from "../lib/types";
import { getLandmark, layout, palette } from "./sceneConfig";

type IslandProps = {
  highlighted: boolean;
  showLabel: boolean;
  treeCount: number;
  rockCount: number;
  onSelect: SelectHandler;
  onHover: (id: LandmarkId | null) => void;
};

const scratch = new Object3D();

const SHORE_ACCENTS = [
  { position: [-5.9, 0.3, 4.2] as const, size: [1.65, 0.18, 0.34] as const, rotation: 0.02 },
  { position: [-1.2, 0.3, 4.2] as const, size: [1.15, 0.18, 0.3] as const, rotation: -0.04 },
  { position: [3.55, 0.3, 4.2] as const, size: [1.4, 0.18, 0.32] as const, rotation: 0.03 },
  { position: [6.55, 0.3, 2.9] as const, size: [0.34, 0.18, 1.4] as const, rotation: -0.05 },
  { position: [-6.55, 0.3, -2.7] as const, size: [0.34, 0.18, 1.2] as const, rotation: 0.04 },
  { position: [3.9, 0.3, -4.55] as const, size: [1.55, 0.18, 0.32] as const, rotation: -0.03 },
] as const;

const CLIFF_FACETS = [
  { position: [-5.25, 0.42, 5.04] as const, size: [1.8, 0.34, 0.12] as const, color: "#d9c7a0" },
  { position: [-2.25, 0.91, 5.04] as const, size: [1.3, 0.24, 0.12] as const, color: "#d4c097" },
  { position: [0.35, 0.38, 5.04] as const, size: [2.05, 0.3, 0.12] as const, color: "#dccaa3" },
  { position: [3.7, 0.83, 5.04] as const, size: [1.45, 0.26, 0.12] as const, color: "#d4c097" },
  { position: [6.88, 0.5, 2.82] as const, size: [0.12, 0.42, 1.45] as const, color: "#d9c7a0" },
  { position: [6.88, 0.94, 0.12] as const, size: [0.12, 0.24, 1.0] as const, color: "#d4c097" },
] as const;

export const Island = forwardRef<Group, IslandProps>(function Island(
  { highlighted, showLabel, treeCount, rockCount, onSelect, onHover },
  foliageRef,
) {
  const houses = getLandmark("houses");
  const treeRef = useRef<InstancedMesh>(null);
  const treeTopRef = useRef<InstancedMesh>(null);
  const trunkRef = useRef<InstancedMesh>(null);
  const rockRef = useRef<InstancedMesh>(null);

  useLayoutEffect(() => {
    const trees = treeRef.current;
    const treeTops = treeTopRef.current;
    const rocks = rockRef.current;
    const trunks = trunkRef.current;
    if (!trees || !treeTops || !trunks || !rocks) {
      return;
    }

    const treeSlots = layout.trees.slice(0, treeCount);
    treeSlots.forEach((position, index) => {
      scratch.position.set(position[0], position[1], position[2]);
      scratch.rotation.set(0, index * 0.35, 0);
      scratch.scale.setScalar(1);
      scratch.updateMatrix();
      trees.setMatrixAt(index, scratch.matrix);
      scratch.position.set(position[0], position[1] + 0.4, position[2]);
      scratch.rotation.set(0, index * 0.35 + 0.2, 0);
      scratch.scale.setScalar(0.72);
      scratch.updateMatrix();
      treeTops.setMatrixAt(index, scratch.matrix);
      scratch.position.set(position[0], position[1] - 0.5, position[2]);
      scratch.rotation.set(0, index * 0.35, 0);
      scratch.scale.setScalar(1);
      scratch.updateMatrix();
      trunks.setMatrixAt(index, scratch.matrix);
    });
    trees.instanceMatrix.needsUpdate = true;
    treeTops.instanceMatrix.needsUpdate = true;
    trunks.instanceMatrix.needsUpdate = true;

    const rockSlots = layout.rocks.slice(0, rockCount);
    rockSlots.forEach((position, index) => {
      scratch.position.set(position[0], position[1], position[2]);
      scratch.rotation.set(0.15, index * 0.7, 0.08);
      scratch.scale.set(1, 0.75, 1);
      scratch.updateMatrix();
      rocks.setMatrixAt(index, scratch.matrix);
    });
    rocks.instanceMatrix.needsUpdate = true;
  }, [rockCount, treeCount]);

  const selectHouses = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(houses);
  };

  return (
    <group name="island">
      <RoundedBox
        position={[0.1, 0.72, 0.15]}
        args={[13.6, 1.44, 9.8]}
        radius={0.78}
        smoothness={4}
        bevelSegments={3}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color={palette.landCream} roughness={0.92} />
      </RoundedBox>
      <mesh position={[-4.9, 0.58, 2.55]} castShadow receiveShadow>
        <cylinderGeometry args={[2.35, 2.55, 1.12, 10]} />
        <meshStandardMaterial color={palette.landCream} roughness={0.93} />
      </mesh>
      <mesh position={[5.15, 0.52, -2.05]} castShadow receiveShadow>
        <cylinderGeometry args={[2.05, 2.25, 1.02, 10]} />
        <meshStandardMaterial color="#dfc9a4" roughness={0.93} />
      </mesh>
      <mesh position={[0.55, 0.42, 3.55]} rotation={[0.08, 0.2, 0]} receiveShadow>
        <cylinderGeometry args={[1.7, 1.95, 0.72, 9]} />
        <meshStandardMaterial color={palette.landSand} roughness={0.96} />
      </mesh>
      <RoundedBox
        position={[0.35, 1.92, -0.35]}
        args={[9.4, 1.05, 6.5]}
        radius={0.52}
        smoothness={4}
        bevelSegments={3}
        rotation={[0, 0.07, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color={palette.landGreen} roughness={0.9} />
      </RoundedBox>
      <mesh position={[-1.4, 1.78, 0.85]} castShadow receiveShadow>
        <cylinderGeometry args={[2.15, 2.35, 0.72, 10]} />
        <meshStandardMaterial color="#7f9770" roughness={0.91} />
      </mesh>
      <RoundedBox
        position={[1.45, 2.78, -1.15]}
        args={[5.5, 0.78, 3.7]}
        radius={0.38}
        smoothness={4}
        bevelSegments={3}
        rotation={[0, -0.05, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color={palette.landMoss} roughness={0.88} />
      </RoundedBox>
      <RoundedBox
        position={[-3.8, 1.18, 2.4]}
        args={[3.4, 0.28, 2.2]}
        radius={0.1}
        smoothness={1}
        bevelSegments={1}
        receiveShadow
      >
        <meshStandardMaterial color={palette.landSand} roughness={0.95} />
      </RoundedBox>
      {BEACH_MESHES.map((beach) => (
        <RoundedBox
          key={beach.position.join(",")}
          position={[...beach.position]}
          args={[...beach.size]}
          radius={0.08}
          smoothness={1}
          bevelSegments={1}
          receiveShadow
        >
          <meshStandardMaterial color={palette.landSand} roughness={0.96} />
        </RoundedBox>
      ))}

      <group name="terrace-details">
        <RoundedBox
          position={[0.35, 1.47, -0.35]}
          args={[9.5, 0.1, 6.58]}
          radius={0.08}
          smoothness={1}
          bevelSegments={1}
          receiveShadow
        >
          <meshStandardMaterial color="#718864" roughness={0.95} />
        </RoundedBox>
        <RoundedBox
          position={[1.45, 2.37, -1.15]}
          args={[5.58, 0.1, 3.78]}
          radius={0.08}
          smoothness={1}
          bevelSegments={1}
          receiveShadow
        >
          <meshStandardMaterial color="#9eb47f" roughness={0.95} />
        </RoundedBox>
      </group>

      <group name="shore-accents">
        {SHORE_ACCENTS.map((accent) => (
          <RoundedBox
            key={accent.position.join(",")}
            position={[...accent.position]}
            args={[...accent.size]}
            rotation={[0, accent.rotation, 0]}
            radius={0.08}
            smoothness={1}
            bevelSegments={1}
            receiveShadow
          >
            <meshStandardMaterial color="#c5a979" roughness={0.96} />
          </RoundedBox>
        ))}
      </group>

      <group name="cliff-facets">
        {CLIFF_FACETS.map((facet) => (
          <RoundedBox
            key={facet.position.join(",")}
            position={[...facet.position]}
            args={[...facet.size]}
            radius={0.035}
            smoothness={1}
            bevelSegments={1}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={facet.color} roughness={0.96} />
          </RoundedBox>
        ))}
      </group>

      <group
        name="houses"
        onClick={selectHouses}
        onPointerOver={(event) => {
          event.stopPropagation();
          onHover(houses.id);
        }}
        onPointerOut={() => {
          onHover(null);
        }}
      >
        {layout.houses.map((position, index) => (
          <House
            key={position.join(",")}
            position={position}
            wide={index !== 1}
            highlighted={highlighted}
          />
        ))}
        {showLabel ? (
          <Html
            position={[0.5, 4.15, -0.5]}
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
                onSelect(houses);
              }}
            >
              {houses.title}
            </button>
          </Html>
        ) : null}
      </group>

      <group ref={foliageRef} name="foliage">
        <instancedMesh
          ref={treeRef}
          args={[undefined, undefined, treeCount]}
          castShadow
        >
          <coneGeometry args={[0.48, 1.05, 7]} />
          <meshStandardMaterial color={palette.foliage} roughness={0.85} />
        </instancedMesh>
        <instancedMesh
          ref={treeTopRef}
          args={[undefined, undefined, treeCount]}
          castShadow
        >
          <coneGeometry args={[0.38, 0.72, 7]} />
          <meshStandardMaterial color="#78975a" roughness={0.85} />
        </instancedMesh>
        <instancedMesh
          ref={trunkRef}
          args={[undefined, undefined, treeCount]}
          castShadow
        >
          <cylinderGeometry args={[0.07, 0.09, 0.34, 6]} />
          <meshStandardMaterial color={palette.wood} roughness={0.9} />
        </instancedMesh>
        <instancedMesh
          ref={rockRef}
          args={[undefined, undefined, rockCount]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[0.45, 0.28, 0.38]} />
          <meshStandardMaterial color={palette.rock} roughness={0.95} />
        </instancedMesh>
      </group>
    </group>
  );
});

function House({
  position,
  wide,
  highlighted,
}: {
  position: readonly [number, number, number];
  wide: boolean;
  highlighted: boolean;
}) {
  const width = wide ? 1.15 : 0.9;
  const depth = 0.82;
  const roof = {
    color: palette.roof,
    roughness: 0.7,
    emissive: highlighted ? "#f0b08a" : "#000000",
    emissiveIntensity: highlighted ? 0.3 : 0,
  };
  return (
    <group position={[...position]}>
      <mesh position={[0, 0.34, 0]} castShadow receiveShadow>
        <boxGeometry args={[width, 0.68, depth]} />
        <meshStandardMaterial color={palette.wall} roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.2, depth / 2 + 0.012]} castShadow>
        <boxGeometry args={[0.2, 0.38, 0.03]} />
        <meshStandardMaterial color={palette.wood} roughness={0.84} />
      </mesh>
      <mesh position={[wide ? 0.32 : 0.22, 0.42, depth / 2 + 0.012]}>
        <boxGeometry args={[0.16, 0.14, 0.03]} />
        <meshStandardMaterial color="#8ec9c4" roughness={0.35} />
      </mesh>
      <mesh
        position={[-width * 0.22, 0.86, 0]}
        rotation={[0, 0, 0.5]}
        castShadow
      >
        <boxGeometry args={[width * 0.74, 0.08, depth + 0.16]} />
        <meshStandardMaterial {...roof} />
      </mesh>
      <mesh
        position={[width * 0.22, 0.86, 0]}
        rotation={[0, 0, -0.5]}
        castShadow
      >
        <boxGeometry args={[width * 0.74, 0.08, depth + 0.16]} />
        <meshStandardMaterial {...roof} />
      </mesh>
    </group>
  );
}
