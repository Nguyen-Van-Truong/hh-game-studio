import { OrbitControls } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { MOUSE, Vector3 } from "three";
import {
  getCameraPreset,
  layout,
  playLookCamera,
  playSpawn,
  sceneConfig,
} from "./sceneConfig";
import { isCameraPreset, type ViewMode } from "./viewMode";

export type CameraGoal = {
  transitioning: boolean;
  userOrbit: boolean;
  position: Vector3;
  target: Vector3;
};

export type CameraLook = {
  position: [number, number, number];
  target: [number, number, number];
};

type CameraRigProps = {
  viewMode: ViewMode;
  reducedMotion: boolean;
  boarded: boolean;
  cameraGoal: MutableRefObject<CameraGoal>;
};

export function playFollowCamera(
  boarded: boolean,
): CameraLook {
  const x = boarded ? playSpawn.boardX : layout.dummy[0];
  const y = boarded ? layout.boat[1] : layout.dummy[1];
  const z = boarded ? playSpawn.boardZ : layout.dummy[2];
  const yaw = boarded ? playSpawn.boardYaw : Math.PI;
  return playLookCamera(boarded, { x, y, z }, yaw);
}

/** Keep authored shots readable on portrait screens without changing desktop framing. */
export function cameraLookFor(
  viewMode: ViewMode,
  boarded: boolean,
  aspect = 1,
): CameraLook {
  const base = isCameraPreset(viewMode)
    ? getCameraPreset(viewMode)
    : playFollowCamera(boarded);
  if (aspect >= 0.9) {
    return {
      position: [...base.position],
      target: [...base.target],
    };
  }

  const distanceScale =
    viewMode === "overview"
      ? 1.55
      : viewMode === "play"
        ? 1.12
        : Math.min(1.62, 1 + (0.9 - aspect) * 0.72);
  const [baseTx, ty, tz] = base.target;
  // On a portrait viewport the long island reads better when the camera's
  // focal point moves slightly toward the lighthouse; otherwise that focal
  // landmark sits just outside the narrow right edge.
  const tx = viewMode === "overview" ? baseTx + 1.7 : baseTx;
  return {
    position: [
      tx + (base.position[0] - tx) * distanceScale,
      ty + (base.position[1] - ty) * distanceScale,
      tz + (base.position[2] - tz) * distanceScale,
    ],
    target: [...base.target],
  };
}

export function cameraFovFor(aspect: number): number {
  if (aspect >= 0.9) {
    return sceneConfig.camera.fov;
  }
  return Math.min(58, sceneConfig.camera.fov + (0.9 - aspect) * 18);
}

export function CameraRig({
  viewMode,
  reducedMotion,
  boarded,
  cameraGoal,
}: CameraRigProps) {
  const camera = useThree((state) => state.camera);
  const viewport = useThree((state) => state.size);
  const controlsRef = useRef<{
    target: Vector3;
    update: () => void;
  } | null>(null);
  const seededTarget = useRef(false);
  const aspect = viewport.width / Math.max(viewport.height, 1);
  const look = useMemo(
    () => cameraLookFor(viewMode, boarded, aspect),
    [aspect, boarded, viewMode],
  );

  useEffect(() => {
    if ("fov" in camera && typeof camera.fov === "number") {
      camera.fov = cameraFovFor(aspect);
      camera.updateProjectionMatrix();
    }
  }, [aspect, camera]);

  useEffect(() => {
    cameraGoal.current.position.set(
      look.position[0],
      look.position[1],
      look.position[2],
    );
    cameraGoal.current.target.set(
      look.target[0],
      look.target[1],
      look.target[2],
    );

    cameraGoal.current.userOrbit = false;

    if (reducedMotion) {
      camera.position.copy(cameraGoal.current.position);
      const controls = controlsRef.current;
      if (controls) {
        controls.target.copy(cameraGoal.current.target);
        controls.update();
      }
      cameraGoal.current.transitioning = false;
      return;
    }

    cameraGoal.current.transitioning = true;
  }, [camera, cameraGoal, look, reducedMotion]);

  return (
    <OrbitControls
      ref={(value) => {
        controlsRef.current = value;
        if (value && !seededTarget.current) {
          value.target.set(look.target[0], look.target[1], look.target[2]);
          value.update();
          seededTarget.current = true;
        }
      }}
      makeDefault
      enabled={viewMode !== "play"}
      enablePan={false}
      enableRotate={viewMode !== "play"}
      enableZoom={viewMode !== "play"}
      enableDamping={!reducedMotion && viewMode !== "play"}
      dampingFactor={sceneConfig.camera.damping}
      minDistance={
        viewMode === "play"
          ? sceneConfig.camera.playMinDistance
          : sceneConfig.camera.minDistance
      }
      maxDistance={
        viewMode === "play"
          ? sceneConfig.camera.playMaxDistance
          : sceneConfig.camera.maxDistance
      }
      minPolarAngle={
        viewMode === "play"
          ? sceneConfig.camera.playMinPolar
          : sceneConfig.camera.minPolar
      }
      maxPolarAngle={
        viewMode === "play"
          ? sceneConfig.camera.playMaxPolar
          : sceneConfig.camera.maxPolar
      }
      mouseButtons={{
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
        RIGHT: MOUSE.ROTATE,
      }}
      onStart={() => {
        if (viewMode === "play") {
          return;
        }
        cameraGoal.current.transitioning = false;
        cameraGoal.current.userOrbit = true;
      }}
    />
  );
}
