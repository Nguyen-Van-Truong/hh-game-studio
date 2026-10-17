export const clamp = (v: number, min: number, max: number): number => Math.max(min, Math.min(max, v));
export const approach = (v: number, target: number, amount: number): number => v < target ? Math.min(v + amount, target) : Math.max(v - amount, target);
export const overlaps = (ax: number, ay: number, aw: number, ah: number, bx: number, by: number, bw: number, bh: number): boolean => Math.abs(ax - bx) * 2 < aw + bw && Math.abs(ay - by) * 2 < ah + bh;
export function segmentRect(x: number, y: number, nx: number, ny: number, rx: number, ry: number, w: number, h: number): number | null {
  let entry = 0, exit = 1;
  for (const [p, d, min, max] of [[x, nx-x, rx, rx+w], [y, ny-y, ry, ry+h]]) {
    if (Math.abs(d) < 0.000001) { if (p < min || p > max) return null; }
    else { const a=(min-p)/d, b=(max-p)/d; entry=Math.max(entry,Math.min(a,b)); exit=Math.min(exit,Math.max(a,b)); if(entry>exit) return null; }
  }
  return entry;
}
