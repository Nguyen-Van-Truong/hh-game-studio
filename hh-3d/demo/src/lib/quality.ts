export type QualityTier = "low" | "high";

export const MAX_DPR = 1.5;

export type QualitySettings = {
  tier: QualityTier;
  dpr: number;
  shadows: boolean;
  treeCount: number;
  rockCount: number;
};

/**
 * Performance budget — starting targets, not a claimed pass.
 * - Desktop orbit p95 frame: ~16.7ms on high, if the machine can hold it.
 * - Low tier must be measurably cheaper: DPR 1, shadows off, fewer instances.
 * - Draw calls / triangles drop on low because tree/rock instance counts drop.
 * If a run cannot measure frame time, write UNMEASURED. Never invent FPS.
 */
export function getQualitySettings(tier: QualityTier): QualitySettings {
  if (tier === "low") {
    return {
      tier,
      dpr: 1,
      shadows: false,
      treeCount: 4,
      rockCount: 3,
    };
  }

  const displayDpr =
    typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;

  return {
    tier,
    // Respect the actual display density while keeping a hard ceiling. The
    // previous fixed 1.5x buffer made a normal 1x laptop and a phone pay the
    // same pixel cost for this small scene.
    dpr: Math.min(MAX_DPR, Math.max(1, displayDpr)),
    shadows: true,
    treeCount: 8,
    rockCount: 6,
  };
}

export function nextQualityTier(tier: QualityTier): QualityTier {
  return tier === "high" ? "low" : "high";
}
