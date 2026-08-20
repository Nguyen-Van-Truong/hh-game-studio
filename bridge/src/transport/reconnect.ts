/** Exponential backoff for plugin reconnects. Deterministic; no PRNG jitter. */

export function backoffMs(attempt: number, baseMs: number, capMs: number): number {
  if (attempt <= 0) {
    return baseMs;
  }
  let ms = baseMs;
  for (let i = 0; i < attempt; i++) {
    if (ms >= capMs) {
      return capMs;
    }
    ms *= 2;
  }
  return ms > capMs ? capMs : ms;
}
