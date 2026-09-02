import { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { Vector3, type Group } from "three";
import type { PlayerChatBubble as PlayerChatBubbleState } from "../lib/chat";
import type { PlayerInput } from "../lib/input";
import type { QualitySettings } from "../lib/quality";
import type { PlayHud } from "../lib/play";
import type { LandmarkId, SelectHandler, SelectedObject } from "../lib/types";
import { surfaceAt } from "../lib/walk";
import { CameraRig, type CameraGoal } from "./CameraRig";
import { Ocean } from "./Ocean";
import { Boat, IdleThung } from "./Boat";
import { Harbor } from "./Harbor";
import { Island } from "./Island";
import { Lighthouse } from "./Lighthouse";
import { Person, type PersonLimbs } from "./Person";
import { PlayerChatBubble } from "./PlayerChatBubble";
import { SimClock } from "./SimClock";
import { landmarks, layout, playFollow, playSpawn, sceneConfig } from "./sceneConfig";
import type { ViewMode } from "./viewMode";

type WorldProps = {
  viewMode: ViewMode;
  reducedMotion: boolean;
  selectedId: LandmarkId | null;
  quality: QualitySettings;
  onSelect: SelectHandler;
  inputRef: RefObject<PlayerInput>;
  startBoarded: boolean;
  boarded: boolean;
  autoWalk: boolean;
  onHud: (hud: PlayHud) => void;
  inputBlocked: boolean;
  chat: PlayerChatBubbleState | null;
};

export function World({
  viewMode,
  reducedMotion,
  selectedId,
  quality,
  onSelect,
  inputRef,
  startBoarded,
  boarded,
  autoWalk,
  onHud,
  inputBlocked,
  chat,
}: WorldProps) {
  const lights = sceneConfig.lights;
  const boatRef = useRef<Group>(null);
  const foliageRef = useRef<Group>(null);
  const playerRef = useRef<Group>(null);
  const limbsRef = useRef<PersonLimbs | null>(null);
  const cameraGoal = useRef<CameraGoal>({
    transitioning: false,
    userOrbit: false,
    position: new Vector3(),
    target: new Vector3(),
  });
  const [hoveredId, setHoveredId] = useState<LandmarkId | null>(null);
  // Close-up modes are intentionally quiet. The dock and object cards still
  // provide a reliable way to discover landmarks without labels being cut by
  // the viewport or sitting on top of the composition.
  const showLabels = viewMode === "overview";

  const isActive = (id: LandmarkId) => selectedId === id || hoveredId === id;

  useLayoutEffect(() => {
    const spawnX = startBoarded ? playSpawn.boardX : layout.dummy[0];
    const spawnZ = startBoarded ? playSpawn.boardZ : layout.dummy[2];
    const spawnY = startBoarded
      ? layout.boat[1] + playFollow.sitLift
      : (surfaceAt(spawnX, spawnZ) ?? layout.dummy[1]);
    const player = playerRef.current;
    if (player) {
      player.position.set(spawnX, spawnY, spawnZ);
      player.rotation.y = startBoarded ? playSpawn.boardYaw : Math.PI;
    }
    const boat = boatRef.current;
    if (boat) {
      boat.position.set(
        startBoarded ? playSpawn.boardX : layout.boat[0],
        layout.boat[1],
        startBoarded ? playSpawn.boardZ : layout.boat[2],
      );
      boat.rotation.y = startBoarded ? playSpawn.boardYaw : 0;
    }
  }, [startBoarded]);

  return (
    <>
      <color attach="background" args={[sceneConfig.sky.color]} />
      <fogExp2
        attach="fog"
        args={[sceneConfig.fog.color, sceneConfig.fog.density]}
      />
      <ambientLight intensity={lights.ambientIntensity} />
      <hemisphereLight
        args={[
          lights.hemisphereSky,
          lights.hemisphereGround,
          lights.hemisphereIntensity,
        ]}
      />
      <directionalLight
        castShadow={quality.shadows}
        intensity={lights.directionalIntensity}
        position={[...lights.directionalPosition]}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-20}
        shadow-camera-right={20}
        shadow-camera-top={20}
        shadow-camera-bottom={-20}
        shadow-camera-near={0.1}
        shadow-camera-far={60}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
      />
      <Ocean onClear={onSelect} />
      <Island
        ref={foliageRef}
        highlighted={isActive("houses")}
        showLabel={showLabels}
        treeCount={quality.treeCount}
        rockCount={quality.rockCount}
        onSelect={onSelect}
        onHover={setHoveredId}
      />
      <Lighthouse
        highlighted={isActive("lighthouse")}
        showLabel={showLabels}
        onSelect={onSelect}
        onHover={setHoveredId}
      />
      <Harbor
        highlighted={isActive("harbor")}
        showLabel={showLabels}
        onSelect={onSelect}
        onHover={setHoveredId}
      />
      <Boat
        ref={boatRef}
        highlighted={isActive("boat")}
        showLabel={showLabels}
        occupied={boarded}
        onSelect={onSelect}
        onHover={setHoveredId}
      />
      <IdleThung reducedMotion={reducedMotion || quality.tier === "low"} />
      <group ref={playerRef} name="player" scale={1.36}>
        <Person seated={boarded} limbsRef={limbsRef} />
        {chat ? <PlayerChatBubble chat={chat} /> : null}
      </group>
      <SimClock
        viewMode={viewMode}
        reducedMotion={reducedMotion || quality.tier === "low"}
        inputRef={inputRef}
        playerRef={playerRef}
        boatRef={boatRef}
        foliageRef={foliageRef}
        limbsRef={limbsRef}
        startBoarded={startBoarded}
        autoWalk={autoWalk}
        onHud={onHud}
        cameraGoal={cameraGoal}
        inputBlocked={inputBlocked}
      />
      <CameraRig
        viewMode={viewMode}
        reducedMotion={reducedMotion}
        boarded={boarded}
        cameraGoal={cameraGoal}
      />
    </>
  );
}

type LandmarkDockProps = {
  selectedId: SelectedObject["id"] | null;
  onSelect: SelectHandler;
};

export function LandmarkDock({ selectedId, onSelect }: LandmarkDockProps) {
  return (
    <nav className="landmark-dock" aria-label="Địa danh">
      <span className="dock-title">Điểm đến</span>
      <div className="dock-actions">
        {landmarks.map((landmark) => (
          <button
            key={landmark.id}
            type="button"
            className="dock-chip"
            aria-pressed={selectedId === landmark.id}
            onClick={() => {
              onSelect(landmark);
            }}
          >
            {landmark.title}
          </button>
        ))}
      </div>
    </nav>
  );
}
