import { Canvas, useFrame } from "@react-three/fiber";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CHAT_VISIBLE_MS,
  normalizeChatMessage,
  type PlayerChatBubble,
} from "./lib/chat";
import { clearPlayerInput, usePlayerInput } from "./lib/input";
import { playStatus, type PlayHud } from "./lib/play";
import {
  getQualitySettings,
  nextQualityTier,
  type QualityTier,
} from "./lib/quality";
import type { SelectedObject } from "./lib/types";
import { cameraFovFor, cameraLookFor } from "./scene/CameraRig";
import { getLandmark } from "./scene/sceneConfig";
import { viewModeFromQuery, type ViewMode } from "./scene/viewMode";
import { LandmarkDock, World } from "./scene/World";
import { BoatPrompt } from "./ui/BoatPrompt";
import { CameraNav } from "./ui/CameraNav";
import { ChatComposer } from "./ui/ChatComposer";
import { ErrorBoundary, ErrorFallback } from "./ui/ErrorFallback";
import { Header } from "./ui/Header";
import { HelpPanel } from "./ui/HelpPanel";
import { LoadingOverlay } from "./ui/LoadingOverlay";
import { ObjectCard } from "./ui/ObjectCard";
import { StoryCard } from "./ui/StoryCard";
import { TouchPad } from "./ui/TouchPad";

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => {
      setReduced(media.matches);
    };
    media.addEventListener("change", onChange);
    return () => {
      media.removeEventListener("change", onChange);
    };
  }, []);

  return reduced;
}

function FrameBudgetProbe({ enabled }: { enabled: boolean }) {
  const lastFrame = useRef(0);
  const lastUpdate = useRef(0);

  useFrame(() => {
    if (!enabled) {
      return;
    }
    const node = document.getElementById("hon-gio-frame-budget");
    if (!node) {
      return;
    }
    const now = performance.now();
    const ms = lastFrame.current > 0 ? now - lastFrame.current : 0;
    lastFrame.current = now;
    if (now - lastUpdate.current < 250) {
      return;
    }
    lastUpdate.current = now;
    if (ms > 0 && ms < 250) {
      node.textContent = `${ms.toFixed(1)} ms (${(1000 / ms).toFixed(0)} fps runtime)`;
    }
  });
  return null;
}

function CrashProbe() {
  const shouldCrash = new URLSearchParams(window.location.search).has("error");
  if (shouldCrash) {
    throw new Error("Forced runtime error for fallback smoke.");
  }
  return null;
}

function readStart(): { viewMode: ViewMode; boarded: boolean; autoWalk: boolean } {
  const params = new URLSearchParams(window.location.search);
  const boarded = params.has("boat");
  const autoWalk = params.has("walk");
  const requested = params.get("preset") ?? params.get("mode");
  if ((boarded || autoWalk) && !requested) {
    return { viewMode: "play", boarded, autoWalk };
  }
  return { viewMode: viewModeFromQuery(requested), boarded, autoWalk };
}

function requestPlayLookLock(): void {
  const canvas = document.querySelector(".canvas-layer canvas");
  if (!(canvas instanceof HTMLElement) || !canvas.requestPointerLock) {
    return;
  }
  void canvas.requestPointerLock();
}

function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    target.tagName === "BUTTON"
  );
}

export default function App() {
  const reducedMotion = usePrefersReducedMotion();
  const webglOk = useMemo(() => detectWebGL(), []);
  const start = useMemo(() => readStart(), []);
  const inputRef = usePlayerInput();
  const [forceFallback, setForceFallback] = useState(() => {
    return new URLSearchParams(window.location.search).has("fallback");
  });
  const [canvasReady, setCanvasReady] = useState(false);
  const [boundaryKey, setBoundaryKey] = useState(0);
  const [runtimeError, setRuntimeError] = useState<Error | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(start.viewMode);
  const [helpOpen, setHelpOpen] = useState(false);
  const [hud, setHud] = useState<PlayHud>({
    boarded: start.boarded,
    nearBoat: start.boarded,
    hasMoved: false,
  });
  const [selected, setSelected] = useState<SelectedObject | null>(() => {
    const requested = new URLSearchParams(window.location.search).get("select");
    if (
      requested === "lighthouse" ||
      requested === "harbor" ||
      requested === "boat" ||
      requested === "houses"
    ) {
      return getLandmark(requested);
    }
    return null;
  });
  const showFallback = forceFallback || !webglOk || runtimeError !== null;
  const closeSelected = useCallback(() => {
    setSelected(null);
  }, []);
  const [qualityTier, setQualityTier] = useState<QualityTier>(() => {
    return new URLSearchParams(window.location.search).get("quality") === "low"
      ? "low"
      : "high";
  });
  const quality = getQualitySettings(qualityTier);
  const showDebug = new URLSearchParams(window.location.search).has("debug");
  const startAspect =
    window.innerWidth / Math.max(window.innerHeight, 1);
  const startLook = useMemo(() => {
    return cameraLookFor(start.viewMode, start.boarded, startAspect);
  }, [start, startAspect]);
  const headerStatus =
    viewMode === "play" ? playStatus(hud.boarded) : "Diorama WebGL";
  const [lookLocked, setLookLocked] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [spokenChat, setSpokenChat] = useState("");
  const chatBubble = useMemo<PlayerChatBubble | null>(() => {
    if (viewMode !== "play") {
      return null;
    }
    if (chatOpen && chatDraft.trim()) {
      return { text: chatDraft, phase: "typing" };
    }
    if (!chatOpen && spokenChat) {
      return { text: spokenChat, phase: "spoken" };
    }
    return null;
  }, [chatDraft, chatOpen, spokenChat, viewMode]);
  const inputBlocked = chatOpen || helpOpen || showFallback;

  const cancelChat = useCallback(() => {
    setChatOpen(false);
    setChatDraft("");
  }, []);

  const submitChat = useCallback(() => {
    const message = normalizeChatMessage(chatDraft);
    setChatOpen(false);
    setChatDraft("");
    if (message) {
      setSpokenChat(message);
    }
    window.requestAnimationFrame(() => {
      requestPlayLookLock();
    });
  }, [chatDraft]);

  const openChat = useCallback(() => {
    if (viewMode !== "play" || helpOpen || showFallback) {
      return;
    }
    clearPlayerInput(inputRef.current);
    setSpokenChat("");
    setChatDraft("");
    setChatOpen(true);
    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  }, [helpOpen, inputRef, showFallback, viewMode]);

  useEffect(() => {
    inputRef.current.lookEnabled =
      viewMode === "play" && !inputBlocked;
  }, [inputBlocked, inputRef, viewMode]);

  useEffect(() => {
    if (inputBlocked || viewMode !== "play") {
      clearPlayerInput(inputRef.current);
    }
  }, [inputBlocked, inputRef, viewMode]);

  useEffect(() => {
    const onChange = () => {
      setLookLocked(document.pointerLockElement !== null);
    };
    document.addEventListener("pointerlockchange", onChange);
    return () => {
      document.removeEventListener("pointerlockchange", onChange);
    };
  }, []);

  useEffect(() => {
    if (
      (viewMode !== "play" || inputBlocked) &&
      document.pointerLockElement
    ) {
      document.exitPointerLock();
    }
  }, [inputBlocked, viewMode]);

  useEffect(() => {
    if (!spokenChat) {
      return;
    }
    const timer = window.setTimeout(() => {
      setSpokenChat("");
    }, CHAT_VISIBLE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [spokenChat]);

  useEffect(() => {
    if (viewMode === "play" && !helpOpen && !showFallback) {
      return;
    }
    if (chatOpen) {
      cancelChat();
    }
  }, [cancelChat, chatOpen, helpOpen, showFallback, viewMode]);

  useEffect(() => {
    if (showFallback) {
      setCanvasReady(true);
    }
  }, [showFallback]);

  useEffect(() => {
    if (showFallback || canvasReady) {
      return;
    }
    const timer = window.setTimeout(() => {
      setCanvasReady(true);
    }, 2000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [canvasReady, showFallback]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        event.key === "Enter" &&
        !event.repeat &&
        !chatOpen &&
        !isTextEntryTarget(event.target)
      ) {
        event.preventDefault();
        openChat();
        return;
      }
      if (event.key === "Escape" && helpOpen) {
        event.preventDefault();
        setHelpOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [chatOpen, helpOpen, openChat]);

  return (
    <div
      className={reducedMotion ? "app reduced-motion" : "app"}
      data-reduced-motion={reducedMotion ? "true" : "false"}
      data-view={viewMode}
      data-boarded={hud.boarded ? "true" : "false"}
      data-look-locked={lookLocked ? "true" : "false"}
    >
      <div className="canvas-layer" aria-hidden={showFallback}>
        {!showFallback ? (
          <ErrorBoundary
            key={boundaryKey}
            onError={(error) => {
              setRuntimeError(error);
            }}
          >
            <CrashProbe />
            <Canvas
              camera={{
                position: [...startLook.position],
                fov: cameraFovFor(startAspect),
              }}
              style={{ width: "100%", height: "100%", display: "block" }}
              dpr={quality.dpr}
              gl={{ antialias: quality.tier === "high" }}
              // R3F's boolean default still requests PCFSoftShadowMap, which
              // is deprecated in the pinned Three.js release. Basic shadows
              // are enough for this small diorama and avoid that warning.
              shadows={quality.shadows ? "basic" : false}
              onCreated={({ camera }) => {
                camera.lookAt(
                  startLook.target[0],
                  startLook.target[1],
                  startLook.target[2],
                );
                setCanvasReady(true);
              }}
            >
              <World
                viewMode={viewMode}
                reducedMotion={reducedMotion}
                selectedId={selected?.id ?? null}
                quality={quality}
                onSelect={setSelected}
                inputRef={inputRef}
                startBoarded={start.boarded}
                boarded={hud.boarded}
                autoWalk={start.autoWalk}
                onHud={setHud}
                inputBlocked={inputBlocked}
                chat={chatBubble}
              />
              <FrameBudgetProbe enabled={showDebug} />
            </Canvas>
          </ErrorBoundary>
        ) : null}
      </div>

      <div className="ui-layer">
        <LoadingOverlay visible={!canvasReady && !showFallback} />
        {showFallback ? (
          <ErrorFallback
            reason={runtimeError ? "runtime" : webglOk ? "forced" : "webgl"}
            message={runtimeError?.message}
            onRetry3d={
              webglOk
                ? () => {
                    setRuntimeError(null);
                    setForceFallback(false);
                    setCanvasReady(false);
                    setBoundaryKey((value) => value + 1);
                  }
                : undefined
            }
          />
        ) : (
          <div className="hud">
            <Header
              status={headerStatus}
              qualityLabel={qualityTier === "high" ? "Cao" : "Thấp"}
              qualityPressed={qualityTier === "low"}
              helpOpen={helpOpen}
              onToggleQuality={() => {
                setQualityTier((tier) => nextQualityTier(tier));
              }}
              onToggleHelp={() => {
                setHelpOpen((open) => !open);
              }}
            />
            {viewMode === "play" && !lookLocked ? (
              <p className="control-hint">
                Bấm vào cảnh để khóa chuột — WASD đi · Space nhảy · click/F đấm
                (pose) · Enter chat
              </p>
            ) : !hud.hasMoved ? (
              <p className="control-hint">
                {viewMode === "play"
                  ? "Chuột xoay · click/F đấm (pose) · WASD đi · Space nhảy · Shift chạy · E thuyền · Enter chat"
                  : "Kéo chuột để xoay · chọn một điểm · Chơi để đi bộ"}
              </p>
            ) : null}
            <HelpPanel
              open={helpOpen}
              onClose={() => {
                setHelpOpen(false);
              }}
              onShowStatic={() => {
                setHelpOpen(false);
                setForceFallback(true);
              }}
            />
            <BoatPrompt
              visible={viewMode === "play" && hud.nearBoat}
              boarded={hud.boarded}
            />
            <ChatComposer
              open={chatOpen}
              value={chatDraft}
              onChange={setChatDraft}
              onSubmit={submitChat}
              onCancel={cancelChat}
            />
            {selected ? (
              <ObjectCard object={selected} onClose={closeSelected} />
            ) : null}
            {viewMode === "overview" ? <StoryCard /> : null}
            <div className="hud-bottom">
              <CameraNav viewMode={viewMode} onChange={setViewMode} />
              {showDebug ? (
                <p id="hon-gio-frame-budget" className="frame-budget">
                  UNMEASURED
                </p>
              ) : null}
            </div>
            {viewMode !== "play" ? (
              <LandmarkDock
                selectedId={selected?.id ?? null}
                onSelect={setSelected}
              />
            ) : null}
            {viewMode === "play" && !chatOpen ? (
              <TouchPad inputRef={inputRef} />
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
