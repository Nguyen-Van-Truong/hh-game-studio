import { useEffect, useRef } from "react";

export const FPS_CLAIM = "NOT_R2_WP1" as const;
export const FPS_NOT_60 = "NOT_60" as const;

/**
 * Honest on-street rAF readout. Not a claimed 60 and not R2-WP1.
 * Skips samples while the tab is hidden.
 */
export function FpsChip() {
  const elRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    let last = performance.now();
    let acc = 0;
    let frames = 0;
    let raf = 0;
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      if (typeof document !== "undefined" && document.hidden) {
        raf = requestAnimationFrame(tick);
        return;
      }
      if (dt > 0 && dt < 1000) {
        acc += dt;
        frames += 1;
        if (acc >= 400) {
          const fps = Math.round((frames * 1000) / acc);
          const node = elRef.current;
          if (node) {
            node.textContent = `${fps} FPS · ${FPS_NOT_60}`;
            node.dataset.fps = String(fps);
          }
          acc = 0;
          frames = 0;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <p
      ref={elRef}
      className="play-fps"
      data-testid="play-fps"
      data-claim={FPS_CLAIM}
      data-not-60={FPS_NOT_60}
      title="Live rAF. Not a 60 FPS claim. R2-WP1 thresholds still unfilled."
    >
      — FPS · {FPS_NOT_60}
    </p>
  );
}
