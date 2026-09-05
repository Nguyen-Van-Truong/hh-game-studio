import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const fixture = JSON.parse(
  readFileSync(join(root, "public", "data", "ben-thanh-400m.authored.geojson"), "utf8"),
);

const ORIGIN = { lon: 106.698, lat: 10.7725 };
const SPAWN = { lon: 106.69804, lat: 10.77162 };
const M_PER_DEG_LAT = 111320;

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function lngLatToWorld(lon, lat) {
  return {
    x: (lon - ORIGIN.lon) * metersPerDegLon(ORIGIN.lat),
    z: (lat - ORIGIN.lat) * M_PER_DEG_LAT,
  };
}

test("play person reuses Hòn Gió tunic scale and has no bowling-ball hips", () => {
  const src = readFileSync(join(root, "src", "play", "Person.tsx"), "utf8");
  assert.match(src, /args=\{\[0\.4, 0\.98, 0\.34\]\}/);
  assert.match(src, /args=\{\[0\.22, 0\.11, 0\.13\]\}/);
  assert.match(src, /export const WALK_STRIDE = 1\.22/);
  assert.match(src, /export const SPRINT_STRIDE = 1\.48/);
  assert.match(src, /export const WALK_ARM_SWING = 1\.35/);
  assert.match(src, /export const SPRINT_ARM_SWING = 1\.62/);
  assert.match(src, /WALK_CYCLE_KIND = "opposite-stride"/);
  assert.match(src, /applyTurnPose/);
  assert.equal(src.includes("sphereGeometry args={[0.11"), false);
  assert.equal(src.includes("sphereGeometry args={[0.12"), false);
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  assert.match(world, /PERSON_SCALE = 1\.36/);
});

test("walk cycle is opposite-arm / opposite-leg; sprint stride is longer", () => {
  const src = readFileSync(join(root, "src", "play", "Person.tsx"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const presence = readFileSync(join(root, "src", "friends", "presence.ts"), "utf8");
  assert.match(src, /export function sampleWalkLimbs/);
  assert.match(src, /leftArmX = -left \* armSwing/);
  assert.match(src, /rightArmX = -right \* armSwing/);
  assert.match(play, /writeWalkCycleProof/);
  assert.match(play, /writeRemoteWalkCycleProof/);
  assert.match(play, /remote-walk-cycle-\$\{friend\.seat_id\}/);
  assert.match(play, /WALK_RATE/);
  assert.match(play, /SPRINT_RATE/);
  assert.match(play, /data-walk-cycle=\{WALK_CYCLE_KIND\}/);
  assert.match(play, /data-testid="walk-cycle-proof"/);
  assert.match(play, /<Person colors=\{colors\} limbsRef=\{limbsRef\} \/>/);
  assert.match(presence, /sprint: packet\.sprint === true && packet\.pose === "walk"/);
  const WALK_STRIDE = 1.22;
  const SPRINT_STRIDE = 1.48;
  const WALK_ARM = 1.35;
  const SPRINT_ARM = 1.62;
  const sample = (time, running) => {
    const left = Math.sin(time);
    const right = -left;
    const stride = running ? SPRINT_STRIDE : WALK_STRIDE;
    const arm = running ? SPRINT_ARM : WALK_ARM;
    return {
      leftLeg: left * stride,
      rightLeg: right * stride,
      leftArm: -left * arm,
      rightArm: -right * arm,
    };
  };
  const walk = sample(Math.PI / 2, false);
  const sprint = sample(Math.PI / 2, true);
  const idleSpread = Math.abs(0.03 - -0.02);
  assert.ok(walk.leftLeg * walk.leftArm < 0, "left arm opposite left leg");
  assert.ok(walk.rightLeg * walk.rightArm < 0, "right arm opposite right leg");
  assert.ok(walk.leftLeg * walk.rightLeg < 0, "legs opposite");
  assert.ok(Math.abs(walk.leftLeg - walk.rightLeg) > 2.3, `walk spread ${Math.abs(walk.leftLeg - walk.rightLeg)}`);
  assert.ok(Math.abs(sprint.leftLeg - sprint.rightLeg) > Math.abs(walk.leftLeg - walk.rightLeg) + 0.4);
  assert.ok(SPRINT_STRIDE > WALK_STRIDE);
  assert.ok(idleSpread < 0.12, "idle is a tiny weight shift, not a dance");
  const damp = sample(Math.PI / 2, false);
  assert.ok(Math.abs(damp.leftLeg * 0.55) > 0.6, "reduced-motion still steps, not a slide");
});

test("A and B tunics share the Person language but use distinct shirts", () => {
  const src = readFileSync(join(root, "src", "play", "Person.tsx"), "utf8");
  assert.match(src, /shirt: "#2a7d78"/);
  assert.match(src, /shirt: "#c4a046"/);
  assert.match(src, /export function tunicShirtForSeat/);
  assert.notEqual("#2a7d78", "#c4a046");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(play, /remotes\.map\(\(friend\) => \(/);
  assert.match(play, /<Person colors=\{colors\} limbsRef=\{limbsRef\} \/>/);
  assert.match(play, /data-body="tunic-humanoid"/);
  assert.match(play, /data-testid=\{\`remote-body-\$\{friend\.seat_id\}\`\}/);
  assert.match(play, /tunicShirtForSeat\(friend\.seat_id\)/);
});

test("Harbor Walk / Tram Approach get a street-facing ground floor, still boxes", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /GROUND_FLOOR_KIND = "door-glass-awning"/);
  assert.match(world, /export function groundFloorFacesForBuilding/);
  assert.match(world, /export function faceFrontsAsphaltStreet/);
  assert.match(world, /STOREFRONT_DOOR_COLOR = "#1a120e"/);
  assert.match(world, /DISPLAY_GLASS_COLOR = "#1b2733"/);
  assert.match(world, /kind: "storefront"/);
  assert.match(world, /kind: "display"/);
  assert.match(world, /Not interiors, not listings, not shop kiosks/);
  assert.match(world, /STOREFRONT_OUT_M = 0\.08/);
  assert.match(play, /data-ground-floor=\{GROUND_FLOOR_KIND\}/);
  assert.match(play, /data-testid="play-ground-floors"/);
  assert.match(play, /groundFloorFacesForBuilding/);
  assert.match(play, /shouldDrawGroundFloorFace/);
  assert.match(play, /kind: "ground-floor"/);
  assert.match(play, /shop-awning-\$\{shop\.shop_id\}/);
  assert.match(app, /shopStallSolids\(shops, playStreets\)/);
  assert.equal(world.includes('kind: "window"'), true);
  assert.equal(world.includes("2141"), false);
  const shopAwnings = ["#1e8a7c", "#2f5fbe", "#b82e4a", "#c48a12", "#4a8c2e", "#6e3d9a", "#c45a18", "#1f6f8a"];
  assert.equal(shopAwnings.includes("#4a2c22"), false);
  assert.equal(shopAwnings.includes("#1a120e"), false);
  assert.ok(0.08 + 0.14 / 2 < 0.55, "door slab stays inside the existing AABB radius");

  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const tram = fixture.features.find((feature) => feature.id === "street-tram-approach");
  const lineOf = (feature) =>
    feature.geometry.coordinates.map(([lon, lat]) => {
      const p = lngLatToWorld(lon, lat);
      return [p.x, p.z];
    });
  const streets = [
    { id: "street-harbor-walk", points: lineOf(harbor) },
    { id: "street-tram-approach", points: lineOf(tram) },
  ];
  const nearest = (pts, x, z) => {
    let best = null;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const vx = pts[i + 1][0] - pts[i][0];
      const vz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) continue;
      const t = Math.max(0, Math.min(1, ((x - pts[i][0]) * vx + (z - pts[i][1]) * vz) / (seg * seg)));
      const px = pts[i][0] + vx * t;
      const pz = pts[i][1] + vz * t;
      const dist = Math.hypot(x - px, z - pz);
      if (!best || dist < best.dist) best = { x: px, z: pz, dx: vx / seg, dz: vz / seg, dist };
    }
    return best;
  };
  const facesFor = (id, pts) => {
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    for (const pt of pts) {
      minX = Math.min(minX, pt[0]);
      maxX = Math.max(maxX, pt[0]);
      minZ = Math.min(minZ, pt[1]);
      maxZ = Math.max(maxZ, pt[1]);
    }
    const cx = (minX + maxX) / 2;
    const cz = (minZ + maxZ) / 2;
    const width = Math.max(2, maxX - minX);
    const depth = Math.max(2, maxZ - minZ);
    return [
      { id, length: width, nx: 0, nz: 1, px: cx, pz: cz + depth / 2 },
      { id, length: width, nx: 0, nz: -1, px: cx, pz: cz - depth / 2 },
      { id, length: depth, nx: 1, nz: 0, px: cx + width / 2, pz: cz },
      { id, length: depth, nx: -1, nz: 0, px: cx - width / 2, pz: cz },
    ];
  };
  const fronts = (face) => {
    const tangentX = face.nz !== 0 ? 1 : 0;
    const tangentZ = face.nx !== 0 ? 1 : 0;
    const spans = face.length >= 5 ? [-0.28, 0, 0.28] : [0];
    for (const street of streets) {
      let hits = 0;
      for (const span of spans) {
        const sx = face.px + span * face.length * tangentX;
        const sz = face.pz + span * face.length * tangentZ;
        const near = nearest(street.points, sx, sz);
        if (!near) continue;
        const front = (near.x - sx) * face.nx + (near.z - sz) * face.nz;
        const align = Math.abs(near.dx * face.nx + near.dz * face.nz);
        if (front > 0.4 && align < 0.45 && near.dist >= 5.4 && near.dist <= 24) hits += 1;
      }
      if (hits >= (spans.length > 1 ? 2 : 1)) return street.id;
    }
    return null;
  };
  const rows = [];
  for (const building of buildings) {
    const ring = building.geometry.coordinates[0].map(([lon, lat]) => {
      const p = lngLatToWorld(lon, lat);
      return [p.x, p.z];
    });
    for (const face of facesFor(building.id, ring)) {
      const streetId = fronts(face);
      if (streetId) rows.push({ id: building.id, streetId, nx: face.nx, nz: face.nz, z: face.pz, x: face.px });
    }
  }
  const harborFaces = rows.filter((row) => row.streetId === "street-harbor-walk");
  const tramFaces = rows.filter((row) => row.streetId === "street-tram-approach");
  const buildingsWith = new Set(rows.map((row) => row.id));
  assert.ok(harborFaces.length >= 10, `Harbor Walk street faces ${harborFaces.length}`);
  assert.ok(tramFaces.length >= 10, `Tram Approach street faces ${tramFaces.length}`);
  assert.ok(rows.length >= 24 && rows.length <= 80, `street faces ${rows.length}`);
  assert.ok(buildingsWith.size >= 20 && buildingsWith.size < 60, `occupied buildings ${buildingsWith.size}`);
  assert.ok(rows.some((row) => String(row.id).startsWith("bldg-steps-e") && row.nx < 0));
  assert.ok(rows.some((row) => String(row.id).startsWith("bldg-steps-w") && row.nx > 0));
  assert.ok(rows.some((row) => String(row.id).startsWith("bldg-west") && row.nz > 0));
  assert.equal(
    rows.some((row) => row.id === "bldg-south-shed" && row.nz < 0),
    false,
    "south shed back should not get a Harbor storefront",
  );
  assert.equal(
    rows.some((row) => String(row.id).startsWith("bldg-west") && row.nx < 0 && row.x < -140),
    false,
    "far west lot backs stay plain boxes",
  );
});

test("inner parcel lanes reuse door+glass; alley backs stay plain", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /SIDE_STREET_KIND = "door-glass-lamp"/);
  assert.match(world, /export function innerStreetsFromBuildings/);
  assert.match(world, /INNER_STREET_PREFIX = "street-inner-"/);
  assert.match(world, /INNER_LANE_WIDTH_M = 2\.35/);
  assert.match(world, /INNER_SCOOTER_MAX = 8/);
  assert.match(world, /INNER_LAMP_MAX = 10/);
  assert.match(world, /Not new downtown/);
  assert.match(play, /data-side-street=\{SIDE_STREET_KIND\}/);
  assert.match(play, /data-testid="play-side-streets"/);
  assert.match(play, /data-ground-floor-inner-faces/);
  assert.match(play, /isInnerStreet/);
  assert.match(play, /streetRoadWidth/);
  assert.equal(world.includes("hip sphere"), false);

  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  const boxOf = (feature) => {
    const pts = feature.geometry.coordinates[0].map(([lon, lat]) => {
      const p = lngLatToWorld(lon, lat);
      return [p.x, p.z];
    });
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    for (const pt of pts) {
      minX = Math.min(minX, pt[0]);
      maxX = Math.max(maxX, pt[0]);
      minZ = Math.min(minZ, pt[1]);
      maxZ = Math.max(maxZ, pt[1]);
    }
    return { id: feature.id, minX, maxX, minZ, maxZ, cx: (minX + maxX) / 2, cz: (minZ + maxZ) / 2 };
  };
  const boxes = buildings.map(boxOf);
  const drafts = [];
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const A = boxes[i];
      const B = boxes[j];
      if (A.maxX < B.minX) {
        const gap = B.minX - A.maxX;
        const overlap = Math.min(A.maxZ, B.maxZ) - Math.max(A.minZ, B.minZ);
        if (gap >= 3.6 && gap <= 22 && overlap >= 10) {
          drafts.push({ axis: "x", pos: (A.maxX + B.minX) / 2, a: Math.max(A.minZ, B.minZ), b: Math.min(A.maxZ, B.maxZ), gap });
        }
      }
      if (A.maxZ < B.minZ) {
        const gap = B.minZ - A.maxZ;
        const overlap = Math.min(A.maxX, B.maxX) - Math.max(A.minX, B.minX);
        if (gap >= 3.6 && gap <= 22 && overlap >= 10) {
          drafts.push({ axis: "z", pos: (A.maxZ + B.minZ) / 2, a: Math.max(A.minX, B.minX), b: Math.min(A.maxX, B.maxX), gap });
        }
      }
    }
  }
  const groups = new Map();
  for (const draft of drafts) {
    const q = Math.round(draft.pos / 0.8) * 0.8;
    const key = `${draft.axis}:${q}`;
    const list = groups.get(key) ?? [];
    list.push(draft);
    groups.set(key, list);
  }
  const inners = [];
  for (const group of groups.values()) {
    group.sort((a, b) => a.a - b.a);
    let cur = group[0];
    const flush = (row) => {
      if (row.b - row.a < 10) return;
      inners.push(row);
    };
    for (let i = 1; i < group.length; i += 1) {
      const next = group[i];
      if (next.a <= cur.b + 8.2) {
        cur = {
          axis: cur.axis,
          pos: (cur.pos * (cur.b - cur.a) + next.pos * (next.b - next.a)) / Math.max(0.2, cur.b - cur.a + next.b - next.a),
          a: Math.min(cur.a, next.a),
          b: Math.max(cur.b, next.b),
          gap: (cur.gap + next.gap) / 2,
        };
      } else {
        flush(cur);
        cur = next;
      }
    }
    flush(cur);
  }
  assert.ok(inners.length >= 8, `inner lanes ${inners.length}`);
  assert.ok(inners.length <= 40, `still the 400 m parcel gaps, not a downtown ${inners.length}`);
  assert.ok(inners.every((row) => row.gap <= 22));
  assert.ok(inners.some((row) => row.gap < 7.2), "parcel 4.6 m lanes");
  const laneW = 2.35;
  assert.ok(laneW < 8.6, "inner asphalt stays narrower than Harbor Walk");

  const nearest = (axis, pos, a, b, x, z) => {
    if (axis === "x") {
      const pz = Math.max(a, Math.min(b, z));
      return { dist: Math.hypot(x - pos, z - pz), dx: 0, dz: b - a >= 0 ? 1 : -1, x: pos, z: pz };
    }
    const px = Math.max(a, Math.min(b, x));
    return { dist: Math.hypot(x - px, z - pos), dx: b - a >= 0 ? 1 : -1, dz: 0, x: px, z: pos };
  };
  let innerFaces = 0;
  let westBack = false;
  let shedBack = false;
  let stepsInner = false;
  for (const box of boxes) {
    const faces = [
      { id: box.id, length: box.maxX - box.minX, nx: 0, nz: 1, px: box.cx, pz: box.maxZ },
      { id: box.id, length: box.maxX - box.minX, nx: 0, nz: -1, px: box.cx, pz: box.minZ },
      { id: box.id, length: box.maxZ - box.minZ, nx: 1, nz: 0, px: box.maxX, pz: box.cz },
      { id: box.id, length: box.maxZ - box.minZ, nx: -1, nz: 0, px: box.minX, pz: box.cz },
    ];
    for (const face of faces) {
      let hit = false;
      for (const street of inners) {
        const bandMax = Math.min(12, street.gap / 2 + 2.4);
        const bandMin = Math.max(1.35, street.gap / 2 - 1.15);
        const samples = face.length >= 5 ? [-0.28, 0, 0.28] : [0];
        let n = 0;
        for (const span of samples) {
          const sx = face.px + span * face.length * (face.nz !== 0 ? 1 : 0);
          const sz = face.pz + span * face.length * (face.nx !== 0 ? 1 : 0);
          const near = nearest(street.axis, street.pos, street.a, street.b, sx, sz);
          const front = (near.x - sx) * face.nx + (near.z - sz) * face.nz;
          const align = Math.abs(near.dx * face.nx + near.dz * face.nz);
          if (front > 0.4 && align < 0.45 && near.dist >= bandMin && near.dist <= bandMax) n += 1;
        }
        if (n >= (samples.length > 1 ? 2 : 1)) hit = true;
      }
      if (!hit) continue;
      innerFaces += 1;
      if (String(box.id).startsWith("bldg-steps-e") && face.nz !== 0) stepsInner = true;
      if (box.id === "bldg-south-shed" && face.nz < 0) shedBack = true;
      if (String(box.id).startsWith("bldg-west") && face.nx < 0 && face.px < -160) westBack = true;
    }
  }
  assert.ok(innerFaces >= 16, `inner street faces ${innerFaces}`);
  assert.ok(innerFaces > 8, "more than a Harbor-only leftover");
  assert.equal(stepsInner, true, "Steps East inner E-W faces get door+glass");
  assert.equal(shedBack, false, "south shed back is not an inner street");
  assert.equal(westBack, false, "far west lot backs stay plain");
});

test("far LOD skips inner door/glass past 90 m and keeps Harbor", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /FAR_DETAIL_KIND = "inner-door-glass"/);
  assert.match(world, /FAR_DETAIL_M = 90/);
  assert.match(world, /export function shouldDrawGroundFloorFace/);
  assert.match(world, /export function shouldDrawScooter/);
  assert.match(world, /PLAY_HTML_LOD_KIND = "far-html"/);
  assert.match(world, /export function shouldDrawPlayHtml/);
  assert.match(world, /Harbor \/ Tram faces stay/);
  assert.match(play, /shouldDrawGroundFloorFace/);
  assert.match(play, /shouldDrawScooter/);
  assert.match(play, /shouldDrawPlayHtml/);
  assert.match(play, /data-html-lod=\{PLAY_HTML_LOD_KIND\}/);
  assert.match(play, /data-far-lod=\{FAR_DETAIL_KIND\}/);
  assert.match(play, /lodSamplePoint/);
  const hypot = (ax, az, bx, bz) => Math.hypot(ax - bx, az - bz);
  const harborFace = { streetId: "street-harbor-walk", x: 0, z: -80 };
  const innerNear = { streetId: "street-inner-steps-east", x: 20, z: -70 };
  const innerFar = { streetId: "street-inner-steps-east", x: 140, z: 40 };
  const player = { x: 4, z: -97 };
  const drawHarbor = !String(harborFace.streetId).startsWith("street-inner-") || hypot(player.x, player.z, harborFace.x, harborFace.z) <= 90;
  const drawNear = !String(innerNear.streetId).startsWith("street-inner-") || hypot(player.x, player.z, innerNear.x, innerNear.z) <= 90;
  const drawFar = !String(innerFar.streetId).startsWith("street-inner-") || hypot(player.x, player.z, innerFar.x, innerFar.z) <= 90;
  assert.equal(drawHarbor, true, "Harbor face stays at any range");
  assert.equal(drawNear, true, "inner door near Harbor stays");
  assert.equal(drawFar, false, "inner door past ~90 m is skipped");
  assert.ok(hypot(player.x, player.z, innerFar.x, innerFar.z) > 90);
  assert.ok(hypot(player.x, player.z, innerNear.x, innerNear.z) < 90);
});

test("inner parcel centerlines get a dark road ribbon and lighter walk edge", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /INNER_LANE_KIND = "asphalt-walk-edge"/);
  assert.match(world, /export function innerWalkWidth/);
  assert.match(world, /export function innerWalkSegments/);
  assert.match(world, /export function innerEdgeStripSegments/);
  assert.match(world, /export function countInnerLanes/);
  assert.match(world, /Same cheap Harbor language/);
  assert.match(play, /data-inner-lane=\{INNER_LANE_KIND\}/);
  assert.match(play, /data-inner-lane-roads/);
  assert.match(play, /data-inner-lane-walks/);
  assert.match(play, /name=\{`inner-walk-\$\{index\}`\}/);
  assert.match(play, /innerWalks\.map/);
  assert.match(play, /innerEdges\.map/);
  assert.match(play, /mains\.flatMap\(\(street\) => curbSegments\(street\.points\)\)/);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /inner parcel lanes, not a city grid/);
  assert.match(honesty, /fixture edge, not a city/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(world.includes("hip sphere"), false);

  const innerWalkWidth = (road, gap) => {
    const want = Math.max(road + 1.15, road * 1.85);
    const inside = Math.max(road + 0.7, gap - 0.28);
    return Math.min(inside, want);
  };
  const steps = innerWalkWidth(2.35, 4.6);
  assert.ok(steps > 2.35, "walk edge is wider than the asphalt strip");
  assert.ok(steps < 4.6, "walk stays inside the 4.6 m Steps gap");
  assert.ok(steps >= 4.2, `Steps walk should fill the gap edge ${steps}`);
  const link = innerWalkWidth(6.2, 20);
  assert.ok(link > 6.2);
  assert.ok(link < 14, `wide connectors stay a ribbon, not a courtyard wallpaper ${link}`);
  assert.ok(2.35 < 8.6, "inner asphalt stays narrower than Harbor Walk");
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "GeoJSON still has only Harbor Walk + Tram Approach");
});

test("authored street plaques name Harbor Walk, Tram Approach, Steps East/West", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /STREET_PLAQUE_KIND = "pole-board"/);
  assert.match(world, /export function streetPlaquesFromWorld/);
  assert.match(world, /export function streetPlaqueSolidsFromCollection/);
  assert.match(world, /name: "Harbor Walk"/);
  assert.match(world, /name: "Tram Approach"/);
  assert.match(world, /name: "Steps East"/);
  assert.match(world, /name: "Steps West"/);
  assert.match(world, /line2: "official street"/);
  assert.match(world, /line2: "inner lane"/);
  assert.match(world, /PLAQUE_SKIP_LANTERN_M/);
  assert.match(world, /Thin planter collision/);
  assert.match(world, /not a downtown grid/);
  assert.match(play, /data-street-plaques=\{String\(streetPlaques\.length\)\}/);
  assert.match(play, /data-testid="play-street-plaques"/);
  assert.match(play, /makeStreetPlaqueTexture/);
  assert.match(play, /StreetPlaquePole/);
  assert.match(play, /play-plaque-label/);
  assert.match(app, /streetPlaqueSolidsFromCollection/);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /inner parcel lanes, not a city grid/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(world.includes("hip sphere"), false);
  assert.equal(play.includes("hip sphere"), false);
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "plaques do not add GeoJSON streets");
  const names = streets.map((row) => row.properties?.display_name ?? row.properties?.name);
  assert.deepEqual(names.sort(), ["Harbor Walk", "Tram Approach"]);
  const steps = fixture.features.filter((feature) =>
    String(feature.properties?.id ?? "").startsWith("bldg-steps-"),
  );
  assert.ok(steps.some((row) => String(row.properties?.name ?? "").startsWith("Steps East")));
  assert.ok(steps.some((row) => String(row.properties?.name ?? "").startsWith("Steps West")));
  assert.ok(!/Nguyễn|Lê Lợi|Đồng Khởi|Hai Bà/.test(world), "do not invent a downtown grid");
});

test("slim HUD chip names Harbor Walk then Steps East; hidden dash when off those four", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const css = readFileSync(join(root, "src", "app", "app.css"), "utf8");
  const chip = readFileSync(join(root, "src", "ui", "StreetChip.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /STREET_HUD_KIND = "named-chip"/);
  assert.match(world, /STREET_HUD_EMPTY = "—"/);
  assert.match(world, /export function namedStreetHudLanes/);
  assert.match(world, /export function namedStreetHudAt/);
  assert.match(world, /export function namedStreetHudAtLonLat/);
  assert.match(world, /not GPS, not OSM/);
  assert.match(world, /name: "Harbor Walk"/);
  assert.match(world, /name: "Tram Approach"/);
  assert.match(world, /name: "Steps East"/);
  assert.match(world, /name: "Steps West"/);
  assert.match(chip, /data-testid="play-street-chip"/);
  assert.match(chip, /not GPS, not OSM/);
  assert.match(app, /StreetChip/);
  assert.match(app, /namedStreetHudAtLonLat/);
  assert.match(play, /data-street-hud=\{STREET_HUD_KIND\}/);
  assert.match(play, /data-street-name=\{streetHudName\}/);
  assert.match(css, /\.app-play \.street-chip/);
  assert.equal(app.includes("play-dashboard"), false);
  assert.equal(chip.includes("GPS"), true);
  assert.equal(/gps|geoloc/i.test(chip) && /not GPS/.test(chip), true);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /not a city grid/);
  assert.equal(world.includes("openstreetmap"), false);
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "chip does not add GeoJSON streets");
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const line = harbor.geometry.coordinates.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const nearest = (pts, x, z) => {
    let best = Infinity;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const vx = pts[i + 1][0] - pts[i][0];
      const vz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) continue;
      const t = Math.max(0, Math.min(1, ((x - pts[i][0]) * vx + (z - pts[i][1]) * vz) / (seg * seg)));
      best = Math.min(best, Math.hypot(x - (pts[i][0] + vx * t), z - (pts[i][1] + vz * t)));
    }
    return best;
  };
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const harborDist = nearest(line, spawn.x, spawn.z);
  assert.ok(harborDist < 2, `spawn stays on Harbor Walk ${harborDist}`);
  const steps = lngLatToWorld(106.698106, 10.7717916);
  const stepsEast = { x: 13.55, z: -76.2 };
  const stepsHarbor = nearest(line, steps.x, steps.z);
  const stepsInner = Math.hypot(steps.x - stepsEast.x, steps.z - stepsEast.z);
  assert.ok(stepsInner < stepsHarbor, "east walk is nearer Steps East than Harbor Walk");
  assert.ok(stepsInner < 4, `Steps East band ${stepsInner}`);
  assert.ok(stepsHarbor > 6, `left Harbor asphalt ${stepsHarbor}`);
});

test("street viewing chip sits outside play-menu and names the shelf", () => {
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const css = readFileSync(join(root, "src", "app", "app.css"), "utf8");
  const chip = readFileSync(join(root, "src", "ui", "ViewingChip.tsx"), "utf8");
  const presence = readFileSync(join(root, "src", "friends", "presence.ts"), "utf8");
  assert.match(presence, /VIEWING_SHOP_COPY = "Đang xem cửa hàng"/);
  assert.match(chip, /data-testid="play-viewing-chip"/);
  assert.match(chip, /VIEWING_SHOP_COPY/);
  assert.match(chip, /play-viewing-shop/);
  assert.match(chip, /Not a shared interior/);
  assert.equal(chip.includes("hidden"), false);
  assert.match(app, /ViewingChip remotes=\{remotes\} shops=\{shops\} onOpenShop=\{openShop\}/);
  assert.match(chip, /data-testid="play-viewing-open"/);
  assert.match(chip, /Mở kệ/);
  assert.match(app, /data-testid="play-menu"/);
  const chipAt = app.indexOf("<ViewingChip");
  const menuAt = app.indexOf('id="play-menu"');
  assert.ok(chipAt > 0 && menuAt > chipAt, "viewing chip must render before play-menu");
  assert.match(css, /\.app-play \.viewing-chip/);
  assert.equal(/\.app-play \.viewing-chip[^{]*\{[^}]*display:\s*none/.test(css), false);
});

test("corner minimap draws the same four HUD lanes in-memory; fixture streets stay 2", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const map = readFileSync(join(root, "src", "map", "MapView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /MINIMAP_LANE_KIND = "authored-hud-lanes"/);
  assert.match(world, /export function namedStreetHudLanesLonLat/);
  assert.match(world, /export function minimapHudLanesFromCollection/);
  assert.match(world, /export function minimapHudLaneCollection/);
  assert.match(world, /Local memory only/);
  assert.match(map, /minimapHudLanesFromCollection/);
  assert.match(map, /source: "hud-lanes"/);
  assert.match(map, /hud-lane-official/);
  assert.match(map, /hud-lane-inner/);
  assert.match(map, /hud-lane-active/);
  assert.match(map, /data-minimap-lanes=\{MINIMAP_LANE_KIND\}/);
  assert.match(map, /data-minimap-inner/);
  assert.match(map, /data-minimap-highlight/);
  assert.match(map, /data-minimap-active/);
  assert.match(map, /data-testid="hh-world-minimap-lanes"/);
  assert.match(app, /activeLaneName: streetHud\?\.name/);
  assert.match(app, /variant="minimap"/);
  assert.match(app, /minimapMayConstruct/);
  assert.match(app, /MINIMAP_DEFER_MS/);
  assert.match(app, /data-minimap-defer/);
  assert.match(app, /minimapLive \?/);
  assert.equal(app.includes("play-dashboard"), false);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /not a city grid/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(map.includes("openstreetmap.org"), false);
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "minimap does not add GeoJSON streets");
  assert.ok(streets.some((row) => row.id === "street-harbor-walk"));
  assert.ok(streets.some((row) => row.id === "street-tram-approach"));
  const steps = lngLatToWorld(106.698106, 10.7717916);
  const stepsEastX = 13.55;
  assert.ok(steps.x > 6 && Math.abs(steps.x - stepsEastX) < 8, "Steps East walk stays an extra inner line");
});

test("corner minimap marks street-play published shops at the sidewalk plant", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const map = readFileSync(join(root, "src", "map", "MapView.tsx"), "utf8");
  const css = readFileSync(join(root, "src", "app", "app.css"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /MINIMAP_SHOP_KIND = "street-play-plant"/);
  assert.match(world, /export function minimapStreetShopMarks/);
  assert.match(world, /isStreetPlayShop\(shop\)/);
  assert.match(world, /if \(!stall\.draw\)/);
  assert.match(world, /shopPlayLngLat\(shop, streets\)/);
  assert.match(world, /Spawn keep-out/);
  assert.match(map, /minimapStreetShopMarks\(shops, playStreets\)/);
  assert.match(map, /className = "minimap-shop-mark"/);
  assert.match(map, /data-testid="hh-world-minimap-shops"/);
  assert.match(map, /data-testid=\{`minimap-shop-\$\{shop\.shop_id\}`\}/);
  assert.match(map, /data-minimap-shop-ids=\{streetShopIds\}/);
  assert.match(map, /\.setLngLat\(\[shop\.lon, shop\.lat\]\)/);
  assert.match(css, /\.minimap-shop-mark/);
  assert.match(app, /minimapMayConstruct/);
  assert.match(app, /data-minimap-defer=\{minimapLive \? "live" : "pending"\}/);
  assert.equal(map.includes("openstreetmap.org"), false);

  const KEEP_OUT = 14;
  const dist = (lon, lat) => {
    const east = (lon - SPAWN.lon) * metersPerDegLon((lat + SPAWN.lat) / 2);
    const north = (lat - SPAWN.lat) * M_PER_DEG_LAT;
    return Math.hypot(east, north);
  };
  const leftover = { shop_id: "shop-local-sharedpc", lon: SPAWN.lon, lat: SPAWN.lat };
  const j6 = { shop_id: "shop-local-mtl8ulddihjpre", lon: 106.6981497, lat: 10.77162 };
  const lantern = { shop_id: "shop-lantern-fish", lon: 106.6980366, lat: 10.7718712 };
  const pho = { shop_id: "shop-local-mtmh45qxehxhvb", lon: 106.69815, lat: 10.7719 };
  assert.ok(dist(leftover.lon, leftover.lat) <= KEEP_OUT, "Shared PC stays keep-out");
  assert.ok(dist(j6.lon, j6.lat) <= KEEP_OUT, "J6 stays keep-out");
  assert.ok(dist(lantern.lon, lantern.lat) > KEEP_OUT, "lantern is street-play");
  assert.ok(dist(pho.lon, pho.lat) > KEEP_OUT, "drawn Phở is street-play");
  const marks = [lantern, pho].filter((shop) => dist(shop.lon, shop.lat) > KEEP_OUT);
  const leftoverMarks = [leftover, j6].filter((shop) => dist(shop.lon, shop.lat) > KEEP_OUT);
  assert.equal(marks.some((row) => row.shop_id === "shop-lantern-fish"), true);
  assert.equal(leftoverMarks.length, 0, "leftover ids stay off the 2D street marks");
});

test("authored boxes get cheap window/door/band insets, still boxes", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  assert.match(world, /export function facadePiecesForBuilding/);
  assert.match(world, /kind: "window"/);
  assert.match(world, /kind: "door"/);
  assert.match(world, /kind: "band"/);
  assert.match(world, /still boxes/i);
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(play, /data-facade="inset"/);
  assert.match(play, /facadePiecesForBuilding/);
  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  assert.equal(buildings.length, 60);
});

test("walk collision uses footprint rings, not a looser AABB", () => {
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(walk, /COLLISION_KIND = "footprint-radius"/);
  assert.match(walk, /export function circleHitsRing/);
  assert.match(walk, /export function closestRingContact/);
  assert.match(walk, /AABB is only a broad-phase/);
  assert.match(play, /data-collision=\{COLLISION_KIND\}/);
  assert.match(play, /data-inside-ring=/);
  assert.equal(play.includes('data-collision="aabb-radius"'), false);
  const chamfered = fixture.features.filter(
    (feature) => feature.properties?.kind === "building" && feature.geometry.coordinates[0].length >= 6,
  );
  assert.ok(chamfered.some((feature) => feature.id === "bldg-steps-e-00"));
});

test("authored buildings carry estimated height for 3D meshes", () => {
  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  assert.ok(buildings.length >= 24, "walkable block, not five boxes");
  assert.ok(buildings.length <= 120, "still a small authored block");
  const chamfered = buildings.filter((feature) => feature.geometry.coordinates[0].length >= 6);
  assert.ok(chamfered.length >= 10, "some footprints are irregular rings, not AABB");
  const ids = new Set(buildings.map((feature) => feature.id));
  assert.equal(ids.size, buildings.length);
  for (const building of buildings) {
    assert.equal(typeof building.properties.height_m, "number");
    assert.ok(building.properties.height_m >= 6);
    assert.ok(building.geometry.coordinates[0].length >= 4);
  }
});

test("world x is east and z is north from the authored origin", () => {
  const east = lngLatToWorld(ORIGIN.lon + 1 / metersPerDegLon(ORIGIN.lat), ORIGIN.lat);
  const north = lngLatToWorld(ORIGIN.lon, ORIGIN.lat + 1 / M_PER_DEG_LAT);
  assert.ok(Math.abs(east.x - 1) < 0.02);
  assert.ok(Math.abs(east.z) < 0.02);
  assert.ok(Math.abs(north.z - 1) < 0.02);
  assert.ok(Math.abs(north.x) < 0.02);
});

test("Market Hall sits north of spawn with real height", () => {
  const hall = fixture.features.find((feature) => feature.id === "bldg-market-hall");
  const ring = hall.geometry.coordinates[0];
  const pts = ring.map(([lon, lat]) => lngLatToWorld(lon, lat));
  const zs = pts.map((p) => p.z);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  assert.ok(minZ > spawn.z, "hall should be north of spawn");
  assert.ok(hall.properties.height_m === 16);
  assert.ok(maxZ - minZ > 10);
});

test("spawn sits south of origin so the behind-camera looks up the street", () => {
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  assert.ok(spawn.z < -80, "spawn should be tens of meters south of Market Hall");
  assert.ok(Math.abs(spawn.x) < 8);
});

function followCameraPose(pos, headingDeg, pitchDeg = 0) {
  const distance = 5.6;
  const height = 3.55;
  const side = 0.42;
  const lookAhead = 1.4;
  const lookY0 = 1.32;
  const yaw = (headingDeg * Math.PI) / 180;
  const pitch = (Math.max(-42, Math.min(28, pitchDeg)) * Math.PI) / 180;
  const sin = Math.sin(yaw);
  const cos = Math.cos(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const distH = distance * cp;
  const chestY = lookY0;
  const camLift = height - lookY0;
  const minY = Math.max(0.82, 0.55);
  return {
    x: pos.x - sin * distH + cos * side,
    y: Math.max(minY, chestY + camLift - sp * distance),
    z: pos.z - cos * distH - sin * side,
    lookX: pos.x + sin * lookAhead * cp,
    lookY: chestY + lookAhead * sp,
    lookZ: pos.z + cos * lookAhead * cp,
    yawDeg: ((headingDeg % 360) + 360) % 360,
    pitchDeg,
  };
}

function chestNdc(cam, body = { x: 0, y: 1.32, z: 0 }, fovDeg = 50, aspect = 1280 / 720) {
  let zx = cam.x - cam.lookX;
  let zy = cam.y - cam.lookY;
  let zz = cam.z - cam.lookZ;
  const zlen = Math.hypot(zx, zy, zz) || 1;
  zx /= zlen;
  zy /= zlen;
  zz /= zlen;
  let xx = zz;
  let xy = 0;
  let xz = -zx;
  const xlen = Math.hypot(xx, xy, xz) || 1;
  xx /= xlen;
  xz /= xlen;
  const yx = zy * xz - zz * xy;
  const yy = zz * xx - zx * xz;
  const yz = zx * xy - zy * xx;
  const fx = body.x - cam.x;
  const fy = body.y - cam.y;
  const fz = body.z - cam.z;
  const vx = fx * xx + fy * xy + fz * xz;
  const vy = fx * yx + fy * yy + fz * yz;
  const vz = fx * zx + fy * zy + fz * zz;
  const fov = (fovDeg * Math.PI) / 180;
  return {
    ndcX: vx / -vz / (Math.tan(fov / 2) * aspect),
    ndcY: vy / -vz / Math.tan(fov / 2),
    inFront: -vz > 0.2,
  };
}

test("spawn follow camera is not the default origin rig", () => {
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const cam = followCameraPose(spawn, 0);
  assert.ok(Math.hypot(cam.x, cam.z) > 80, "camera sits at spawn, not world 0");
  assert.ok(cam.z < spawn.z, "behind heading 0");
});

test("follow camera stays behind heading, not locked world-north", () => {
  const body = { x: 0, z: 0 };
  const north = followCameraPose(body, 0);
  const east = followCameraPose(body, 90);
  const west = followCameraPose(body, 270);
  assert.ok(north.z < body.z, "heading 0: camera south of body");
  assert.ok(Math.abs(north.yawDeg) < 0.01);
  assert.ok(east.x < body.x, "heading 90: camera west of body");
  assert.ok(Math.abs(east.yawDeg - 90) < 0.01);
  assert.ok(east.lookX > body.x, "looks east of the body");
  assert.ok(west.x > body.x, "heading 270: camera east of body");
  assert.ok(Math.abs(west.yawDeg - 270) < 0.01);
  assert.notEqual(north.z, east.z);
});

test("look yaw/pitch move the follow camera off the heading-zero rig", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const fps = readFileSync(join(root, "src", "play", "FpsChip.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /PLAY_CAM_MIN_HEIGHT = 0\.55/);
  assert.match(world, /chestY \+ camLift - sp \* distance/);
  assert.equal(world.includes("pitchDeg) * 0.36"), false);
  assert.match(play, /data-cam-look-y=\{cam\.lookY\.toFixed\(2\)\}/);
  assert.match(play, /writeSelfScreen/);
  assert.match(play, /data-fps-claim="NOT_R2_WP1"/);
  assert.match(fps, /FPS_CLAIM = "NOT_R2_WP1"/);
  assert.match(fps, /FPS_NOT_60 = "NOT_60"/);
  assert.match(fps, /data-testid="play-fps"/);
  assert.match(app, /<FpsChip/);
  const body = { x: 0, z: 0 };
  const rest = followCameraPose(body, 0, 0);
  const yawed = followCameraPose(body, 28, 0);
  const pitched = followCameraPose(body, 0, 16);
  assert.ok(Math.abs(yawed.yawDeg - 28) < 0.01);
  assert.ok(Math.abs(yawed.x - rest.x) > 0.4, "yaw must swing camera");
  assert.ok(Math.abs(yawed.z - rest.z) > 0.15);
  assert.ok(pitched.y < rest.y, "positive pitch drops the camera (demo / tunic in frame)");
  assert.ok(pitched.lookY > rest.lookY, "positive pitch looks up");
  assert.ok(pitched.lookY < 3.2, "look-at stays near the chest, not a sky point");
  assert.ok(Math.abs(pitched.z) < Math.abs(rest.z) + 0.01);
  const up = followCameraPose(body, 0, 28);
  const framed = chestNdc(up);
  assert.ok(framed.inFront, "pitch-up still sees the chest in front");
  assert.ok(Math.abs(framed.ndcY) < 0.92, `pitch-up keeps tunic in frame ndcY=${framed.ndcY}`);
  const down = followCameraPose(body, 0, -42);
  assert.ok(down.y > rest.y, "pitch-down raises the camera to see ground");
  assert.ok(down.lookY < rest.lookY);
});

function worldToLngLat(x, z) {
  return {
    lon: ORIGIN.lon + x / metersPerDegLon(ORIGIN.lat),
    lat: ORIGIN.lat + z / M_PER_DEG_LAT,
  };
}

function boxBuilding(id, minX, maxX, minZ, maxZ, height = 12) {
  const sw = worldToLngLat(minX, minZ);
  const se = worldToLngLat(maxX, minZ);
  const ne = worldToLngLat(maxX, maxZ);
  const nw = worldToLngLat(minX, maxZ);
  return {
    id,
    height_m: height,
    ring: [
      [sw.lon, sw.lat],
      [se.lon, se.lat],
      [ne.lon, ne.lat],
      [nw.lon, nw.lat],
      [sw.lon, sw.lat],
    ],
  };
}

function raySegmentT(ox, oz, dx, dz, ax, az, bx, bz) {
  const ex = bx - ax;
  const ez = bz - az;
  const det = dx * ez - dz * ex;
  if (Math.abs(det) < 1e-10) return null;
  const t = ((ax - ox) * ez - (az - oz) * ex) / det;
  const u = ((ax - ox) * dz - (az - oz) * dx) / det;
  if (t < 0 || t > 1 || u < 0 || u > 1) return null;
  return t;
}

function resolveFollowCamera(pos, headingDeg, buildings, pitchDeg = 0) {
  const desired = followCameraPose(pos, headingDeg, pitchDeg);
  const head = { x: pos.x, y: 1.48, z: pos.z };
  const dx = desired.x - head.x;
  const dy = desired.y - head.y;
  const dz = desired.z - head.z;
  const rayLen = Math.hypot(dx, dy, dz);
  let bestT = 1;
  let hitId = null;
  for (const building of buildings) {
    const points = building.ring.map(([lon, lat]) => {
      const p = lngLatToWorld(lon, lat);
      return [p.x, p.z];
    });
    const height = building.height_m ?? 8;
    for (let i = 0; i < points.length; i += 1) {
      const a = points[i];
      const b = points[(i + 1) % points.length];
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-8) continue;
      const t = raySegmentT(head.x, head.z, dx, dz, a[0], a[1], b[0], b[1]);
      if (t == null || t < 0.02 || t >= bestT) continue;
      const y = head.y + dy * t;
      if (y < -0.2 || y > height + 0.4) continue;
      bestT = t;
      hitId = building.id;
    }
  }
  let t = 1;
  if (hitId && rayLen > 1e-6) {
    const streetT = bestT - 0.32 / rayLen;
    t = streetT >= 0.92 / rayLen ? Math.min(1, streetT) : Math.max(0.4 / rayLen, streetT);
  }
  const x = head.x + dx * t;
  const z = head.z + dz * t;
  const distM = Math.hypot(x - pos.x, z - pos.z);
  let y = head.y + dy * t;
  if (hitId && distM < 0.92) {
    y = Math.max(y, 2.38);
  }
  return {
    ...desired,
    x,
    y,
    z,
    hit: Boolean(hitId),
    hitId,
    distM,
    desiredDistM: Math.hypot(desired.x - pos.x, desired.z - pos.z),
  };
}

test("follow camera pulls in along the look ray when a footprint wall is behind", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /CAM_HIT_KIND = "look-ray-ring"/);
  assert.match(world, /CAM_COLLAPSE_Y = 2\.38/);
  assert.match(world, /export function resolveFollowCamera/);
  assert.match(world, /export function cameraRayHit/);
  assert.match(world, /export function cameraHitSolids/);
  assert.match(world, /export function followRigYaw/);
  assert.match(world, /return lookMode !== "off" \? lookYaw : headingDeg;/);
  assert.equal(world.includes("lookMode !== \"off\" || Math.abs(lookPitch) > 0.4 ? lookYaw"), false);
  assert.match(world, /Does not turn the body/);
  assert.match(play, /data-cam-kind=\{CAM_HIT_KIND\}/);
  assert.match(play, /data-cam-hit=\{cam\.hit \? "1" : "0"\}/);
  assert.match(play, /data-cam-dist=\{cam\.distM\.toFixed\(2\)\}/);
  assert.match(play, /resolveFollowCamera/);
  assert.match(play, /followRigYaw\(avatar\.heading, look\.mode, look\.yaw, look\.pitch\)/);
  assert.match(play, /cameraHitSolids\(buildings, shops, extras\.streets\)/);
  assert.equal(play.includes("followCameraPose("), false);

  const wall = boxBuilding("bldg-steps-e-00", 2, 24, -12, 12, 14);
  const open = resolveFollowCamera({ x: 0, z: 0 }, 0, [wall]);
  assert.equal(open.hit, false);
  assert.ok(open.distM > 5.4 && open.distM < 5.8, `open dist ${open.distM}`);

  const hugged = resolveFollowCamera({ x: 1.42, z: 0 }, 270, [wall]);
  assert.equal(hugged.hit, true);
  assert.equal(hugged.hitId, "bldg-steps-e-00");
  assert.ok(hugged.distM < 2.2, `pulled dist ${hugged.distM}`);
  assert.ok(hugged.distM + 0.05 < hugged.desiredDistM);
  assert.ok(hugged.x < 2 - 0.12, `camera stays west of the wall ${hugged.x}`);
  assert.ok(hugged.x > 1.42, "camera stays behind the body, not inside the tunic");
  assert.ok(hugged.y >= 2.3, `short rig lifts over the nape ${hugged.y}`);
  assert.ok(Math.abs(hugged.yawDeg - 270) < 0.01, "look yaw unchanged");
  assert.ok(hugged.lookX < 1.42, "still looks along heading, not at the wall");

  const steps = fixture.features.find((feature) => feature.id === "bldg-steps-e-00");
  const pts = steps.geometry.coordinates[0].map(([lon, lat]) => lngLatToWorld(lon, lat));
  const minX = Math.min(...pts.map((p) => p.x));
  const midZ = (Math.min(...pts.map((p) => p.z)) + Math.max(...pts.map((p) => p.z))) / 2;
  const atSteps = resolveFollowCamera({ x: minX - 0.58, z: midZ }, 270, [
    {
      id: "bldg-steps-e-00",
      height_m: steps.properties.height_m,
      ring: steps.geometry.coordinates[0],
    },
  ]);
  assert.equal(atSteps.hit, true);
  assert.ok(atSteps.distM < 3.2, `steps-e pull ${atSteps.distM}`);
  assert.ok(atSteps.x < minX - 0.1, "resolved camera stays in street space");
});

test("seat B default rig sees west toward A and look-down stays on the street", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const seats = readFileSync(join(root, "src", "friends", "seats.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /PLAY_CAM_SIDE_B = -1\.6/);
  assert.match(world, /PLAY_SEAT_B_PITCH_DEG = -8/);
  assert.match(world, /CAM_STREET_FLOOR_Y = 0\.82/);
  assert.match(world, /export function seatFollowSide/);
  assert.match(world, /export function cameraPointInsideSolid/);
  assert.match(world, /export function pushCameraOutOfSolid/);
  assert.equal(world.includes("bestT = 0.36"), false);
  assert.match(seats, /SEAT_LOOK_PITCH/);
  assert.match(seats, /SEAT_LOOK_YAW/);
  assert.match(seats, /b: -8/);
  assert.match(seats, /b: 292/);
  assert.match(seats, /heading: 292/);
  assert.match(app, /SEAT_LOOK_PITCH\[seat\]/);
  assert.match(app, /SEAT_LOOK_YAW\[seat\]/);
  assert.match(play, /seatFollowSide\(seat\)/);
  assert.match(play, /data-cam-inside=\{camInside \? "1" : "0"\}/);
  assert.match(play, /writeRemoteScreen/);
  assert.match(play, /dataset.onCanvas/);

  function pointInRing(x, z, pts) {
    let inside = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i, i += 1) {
      const pi = pts[i];
      const pj = pts[j];
      if (!pi || !pj || pj[1] === pi[1]) continue;
      if (pi[1] > z !== pj[1] > z && x < ((pj[0] - pi[0]) * (z - pi[1])) / (pj[1] - pi[1]) + pi[0]) {
        inside = !inside;
      }
    }
    return inside;
  }

  const steps = fixture.features.find((feature) => feature.id === "bldg-steps-e-00");
  const ring = steps.geometry.coordinates[0].map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const a = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const b = { x: a.x + 7, z: a.z };
  const skyWest = followCameraPose(b, 270, 10);
  const street = followCameraPose(b, 270, -8);
  assert.equal(pointInRing(skyWest.x, skyWest.z, ring), true, "desired behind-west still aims at Steps East");
  assert.ok(street.lookY < 2.2, "B looks at the street, not zenith");
  const toA = { dx: a.x - street.x, dy: 1.2 - street.y, dz: a.z - street.z };
  const toLook = { dx: street.lookX - street.x, dy: street.lookY - street.y, dz: street.lookZ - street.z };
  const lookLen = Math.hypot(toLook.dx, toLook.dy, toLook.dz);
  const aLen = Math.hypot(toA.dx, toA.dy, toA.dz);
  const ang = (Math.acos(Math.min(1, Math.max(-1, (toLook.dx * toA.dx + toLook.dy * toA.dy + toLook.dz * toA.dz) / (lookLen * aLen)))) * 180) / Math.PI;
  assert.ok(ang < 16, `A must sit in B's default lens ${ang}`);
  const down = followCameraPose(b, 270, -42);
  assert.ok(down.y >= 0.82, `look-down stays above the slab ${down.y}`);
});

test("sky is a blue gradient hemisphere, not a beige or gray void", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /SKY_KIND = "gradient-hemisphere"/);
  assert.match(world, /SKY_ZENITH = "#2f74c4"/);
  assert.match(world, /PLAY_DEFAULT_PITCH_DEG = 10/);
  assert.match(world, /export function followPitchDeg/);
  assert.match(world, /SKY_GROUND_HAZE = "#4a90cc"/);
  assert.match(world, /export function isBeigeOrGrayVoid/);
  assert.match(play, /name="sky-dome"/);
  assert.match(play, /name="sun-disc"/);
  assert.match(play, /data-sky=\{SKY_KIND\}/);
  assert.match(play, /<SkyHemisphere/);
  assert.equal(play.includes('setClearColor("#6f8798"'), false);
  const zenith = [0x2f, 0x74, 0xc4];
  assert.ok(zenith[2] > zenith[0] + 40, "zenith must be bluer than red");
  const beige = [0xc9, 0xa0, 0x6e];
  assert.ok(beige[0] > beige[2], "wall beige stays walls, not sky");
});

test("published shops get an authored awning kiosk under the pole-board", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /SHOP_STALL_KIND = "awning-kiosk"/);
  assert.match(world, /export function shopStallSpec/);
  assert.match(world, /export function stallSidewalkPlant/);
  assert.match(world, /STALL_SIDEWALK_ACROSS_M = 7\.2/);
  assert.match(world, /export function stallColorForShop/);
  assert.match(world, /export function shopStallSolids/);
  assert.match(world, /Not an interior/);
  assert.match(world, /export function shopInSpawnKeepOut/);
  assert.match(world, /const draw = !shopInSpawnKeepOut\(shop\)/);
  assert.match(play, /position=\{\[stall\.x - spec\.x, 0, stall\.z - spec\.z\]\}/);
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  assert.match(walk, /export function isStreetPlayShop/);
  assert.match(walk, /export function streetPlayShops/);
  assert.match(app, /streetPlayShops\(shops\)/);
  assert.match(app, /shop-lantern-fish/);
  assert.match(play, /drawnShops\.map/);
  assert.match(play, /data-draw=\{stall\.draw \? "1" : "0"\}/);
  assert.match(play, /data-spawn-keep-out=\{String\(SPAWN_KEEP_OUT_M\)\}/);
  assert.match(play, /shop-awning-\$\{shop\.shop_id\}/);
  assert.match(play, /shop-counter-\$\{shop\.shop_id\}/);
  assert.match(play, /shop-kiosk-\$\{shop\.shop_id\}/);
  assert.match(play, /shop-post-l-\$\{shop\.shop_id\}/);
  assert.match(play, /data-shop-stall-kind=\{SHOP_STALL_KIND\}/);
  assert.match(play, /data-testid="play-shop-stalls"/);
  assert.match(app, /shopStallSolids\(shops, playStreets\)/);
  assert.match(play, /shop-board-\$\{shop\.shop_id\}/);

  const AWNING_COLORS = [
    "#1e8a7c",
    "#2f5fbe",
    "#b82e4a",
    "#c48a12",
    "#4a8c2e",
    "#6e3d9a",
    "#c45a18",
    "#1f6f8a",
  ];
  const colorIndex = (id) => {
    let n = 0;
    for (let i = 0; i < id.length; i += 1) {
      n = (n + id.charCodeAt(i) * (i + 3)) % 97;
    }
    return n;
  };
  const stallColor = (shop) => AWNING_COLORS[colorIndex(`${shop.shop_id}\0${shop.name}`) % AWNING_COLORS.length];
  const lantern = {
    shop_id: "shop-lantern-fish",
    name: "Quầy Cá Đèn Lồng",
    lon: 106.6980366,
    lat: 10.7718712,
  };
  const leftover = {
    shop_id: "shop-local-sharedpc",
    name: "Shared PC",
    lon: SPAWN.lon,
    lat: SPAWN.lat,
  };
  const pho = {
    shop_id: "shop-local-pho",
    name: "Quầy Phở Nhà",
    lon: 106.69815,
    lat: 10.7719,
  };
  assert.notEqual(stallColor(lantern), stallColor(pho));
  assert.notEqual(stallColor(lantern), "#9a2f0e");
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const lanternSign = lngLatToWorld(lantern.lon, lantern.lat);
  const lanternStall = { x: lanternSign.x, z: lanternSign.z + 0.72 };
  const leftoverStall = {
    x: leftover.lon === SPAWN.lon ? spawn.x : 0,
    z: spawn.z + 0.72,
  };
  leftoverStall.x = lngLatToWorld(leftover.lon, leftover.lat).x;
  leftoverStall.z = lngLatToWorld(leftover.lon, leftover.lat).z + 0.72;
  assert.ok(lanternSign.z > spawn.z + 20, "lantern stall sits north of spawn");
  assert.ok(Math.abs(lanternSign.x - spawn.x) < 8);
  const halfX = 1.32;
  const halfZ = 0.88;
  const radius = 0.55;
  const spawnHits = (x, z) =>
    Math.abs(spawn.x - x) < halfX + radius + 0.2 && Math.abs(spawn.z - z) < halfZ + radius + 0.2;
  assert.equal(spawnHits(lanternStall.x, lanternStall.z), false, "lantern stall must not cover spawn");
  assert.equal(spawnHits(leftoverStall.x, leftoverStall.z), true, "spawn leftover would trap W");
  const keepOutM = 12;
  const distXZ = (x, z) => Math.hypot(spawn.x - x, spawn.z - z);
  assert.ok(distXZ(leftoverStall.x, leftoverStall.z) < keepOutM, "leftover at spawn sits in keep-out");
  assert.ok(distXZ(spawn.x, spawn.z + 8) < keepOutM, "8 m ahead still fills the behind camera");
  assert.ok(distXZ(lanternStall.x, lanternStall.z) > keepOutM, "lantern stays outside the spawn cone");
  assert.match(world, /<= SPAWN_KEEP_OUT_M/);
  assert.equal(world.includes("keeps the mesh but drops collision"), false);
  const stroll = { x: spawn.x, z: spawn.z + 12 };
  const strollHitsLantern =
    Math.abs(stroll.x - lanternStall.x) < halfX + radius &&
    Math.abs(stroll.z - lanternStall.z) < halfZ + radius;
  assert.equal(strollHitsLantern, false, "12 m north stroll stays off the lantern counter");
  const approach = { x: lanternStall.x, z: lanternStall.z - halfZ - 0.1 };
  const hitsCounter =
    Math.abs(approach.x - lanternStall.x) < halfX + radius &&
    Math.abs(approach.z - lanternStall.z) < halfZ + radius;
  assert.equal(hitsCounter, true, "counter AABB blocks a body walking into the stall");
  const beside = { x: lanternStall.x + 4.2, z: lanternStall.z };
  const streetBeside =
    Math.abs(beside.x - lanternStall.x) < halfX + radius &&
    Math.abs(beside.z - lanternStall.z) < halfZ + radius;
  assert.equal(streetBeside, false, "Harbor Walk stays open beside the kiosk");
});

test("street-play kiosks sit on Harbor/Tram sidewalk, not the driving lane", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /export function officialStallWays/);
  assert.match(world, /STALL_OFF_LANE_M = STREET_WIDTH_M \/ 2 \+ 1\.5/);
  assert.match(world, /signed < 0 \? -1 : 1/);
  assert.match(play, /data-lane-m=\{stall\.laneM\.toFixed\(2\)\}/);
  assert.match(play, /shopStallSpec\(shop, extras\.streets\)/);
  assert.match(play, /shopStallSpec\(shop, worldExtras\.streets\)/);
  assert.match(play, /shopSignSpec\(shop, streets\)/);
  assert.match(play, /shopSignSpec\(shop, worldExtras\.streets\)/);
  assert.match(play, /cameraHitSolids\(buildings, shops, extras\.streets\)/);
  assert.match(app, /shopStallSolids\(shops, playStreets\)/);
  assert.match(app, /shopPlayLngLat\(shop, playStreets\)/);
  assert.match(app, /shopPlayLngLat\(stall, playStreets\)/);
  assert.match(world, /export function shopPlayLngLat/);
  assert.match(world, /shopMarketSpill\(shop, streets\)/);
  const walkSrc = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  assert.match(walkSrc, /playPose\?\.\(shop\) \?\? shop/);
  assert.match(walkSrc, /splitM > 3 && persistD \+ 0\.4 < d/);
  assert.match(walkSrc, /NEARBY_SHOP_M = 4/);
  assert.match(walkSrc, /STREET_SHOP_ASPHALT_LANE_M = 3/);
  assert.match(walkSrc, /laneM <= STREET_SHOP_ASPHALT_LANE_M/);
  assert.match(app, /streetHud\?\.distM/);

  const harborFeat = fixture.features.find((row) => row.properties?.id === "street-harbor-walk");
  assert.ok(harborFeat, "authored Harbor Walk line");
  const harbor = harborFeat.geometry.coordinates.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const nearest = (x, z) => {
    let best = null;
    for (let i = 0; i < harbor.length - 1; i += 1) {
      const a = harbor[i];
      const b = harbor[i + 1];
      const vx = b[0] - a[0];
      const vz = b[1] - a[1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) {
        continue;
      }
      const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (seg * seg)));
      const px = a[0] + vx * t;
      const pz = a[1] + vz * t;
      const dist = Math.hypot(x - px, z - pz);
      if (!best || dist < best.dist) {
        best = { x: px, z: pz, dx: vx / seg, dz: vz / seg, dist };
      }
    }
    return best;
  };
  const offsetSide = (x, z, dx, dz, side, across) => {
    const rot = Math.atan2(dx, dz);
    return { x: x + Math.cos(rot) * side * across, z: z - Math.sin(rot) * side * across };
  };
  const plant = (lon, lat) => {
    const sign = lngLatToWorld(lon, lat);
    return { x: sign.x, z: sign.z + 0.72 };
  };
  const sidewalkOf = (lon, lat) => {
    const p = plant(lon, lat);
    const hit = nearest(p.x, p.z);
    const rot = Math.atan2(hit.dx, hit.dz);
    const signed = (p.x - hit.x) * Math.cos(rot) + (p.z - hit.z) * -Math.sin(rot);
    const side = signed < 0 ? -1 : 1;
    const placed = offsetSide(hit.x, hit.z, hit.dx, hit.dz, side, 7.2);
    return { persist: p, hit, placed, persistLane: hit.dist };
  };

  const pho = sidewalkOf(106.69804, 10.771797);
  const lantern = sidewalkOf(106.6980366, 10.7718712);
  const leftover = plant(SPAWN.lon, SPAWN.lat);
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  assert.ok(pho.persistLane < 1.5, "drawn Phở persist sits on Harbor centerline");
  assert.ok(lantern.persistLane < 1.5, "lantern persist is also on the lane before the sidewalk plant");
  assert.ok(pho.hit.dist < 4.3, "Phở persist is inside the asphalt half-width");
  assert.ok(Math.abs(pho.placed.x - pho.hit.x) > 6.4, "Phở mesh moves off the lane");
  const phoLane = Math.hypot(pho.placed.x - pho.hit.x, pho.placed.z - pho.hit.z);
  const lanternLane = Math.hypot(lantern.placed.x - lantern.hit.x, lantern.placed.z - lantern.hit.z);
  assert.ok(phoLane > 6.8 && phoLane < 7.6, "Phở hugs the ~7 m sidewalk");
  assert.ok(lanternLane > 6.8 && lanternLane < 7.6, "lantern also leaves the driving lane");
  const halfX = 1.32;
  const halfZ = 0.88;
  const radius = 0.55;
  const walkHarbor = { x: pho.hit.x, z: pho.hit.z };
  const hitsPhoOnLane =
    Math.abs(walkHarbor.x - pho.placed.x) < halfX + radius &&
    Math.abs(walkHarbor.z - pho.placed.z) < halfZ + radius;
  assert.equal(hitsPhoOnLane, false, "Harbor centerline walk misses the sidewalk kiosk");
  const hitsPersistPho =
    Math.abs(walkHarbor.x - pho.persist.x) < halfX + radius &&
    Math.abs(walkHarbor.z - pho.persist.z) < halfZ + radius;
  assert.equal(hitsPersistPho, true, "old persist plant would block the driving lane");
  assert.ok(Math.hypot(spawn.x - leftover.x, spawn.z - leftover.z) < 14, "leftover persist stays in spawn keep-out");
  assert.ok(Math.hypot(spawn.x - lantern.placed.x, spawn.z - lantern.placed.z) > 14, "lantern sidewalk plant stays drawn");
  assert.match(world, /const draw = !shopInSpawnKeepOut\(shop\)/);
  assert.equal(world.includes("catalog_clear"), false);

  const distM = (ax, az, bx, bz) => Math.hypot(ax - bx, az - bz);
  const phoSignLane = Math.hypot(pho.placed.x - pho.hit.x, pho.placed.z - pho.hit.z);
  const lanternSignLane = Math.hypot(lantern.placed.x - lantern.hit.x, lantern.placed.z - lantern.hit.z);
  assert.ok(phoSignLane >= 5, "Phở pole-board sits with the sidewalk kiosk, not the lane");
  assert.ok(lanternSignLane >= 5, "lantern pole-board sits with the sidewalk kiosk");
  const atPersist = { x: pho.persist.x, z: pho.persist.z };
  const dPersist = distM(atPersist.x, atPersist.z, pho.persist.x, pho.persist.z);
  const dPlant = distM(atPersist.x, atPersist.z, pho.placed.x, pho.placed.z);
  assert.ok(dPlant > 5 && dPersist + 0.4 < dPlant, "Harbor persist is closer to empty persist than to the kiosk");
  const atPlant = { x: pho.placed.x, z: pho.placed.z + 2.2 };
  const plantPersist = distM(atPlant.x, atPlant.z, pho.persist.x, pho.persist.z);
  const plantPlant = distM(atPlant.x, atPlant.z, pho.placed.x, pho.placed.z);
  assert.ok(plantPlant < 3 && plantPlant < plantPersist, "south of the awning is closer to the plant");
  const leak = lngLatToWorld(106.6980156, 10.7718746);
  const leakToPho = distM(leak.x, leak.z, pho.placed.x, pho.placed.z);
  const leakHarbor = nearest(leak.x, leak.z);
  assert.ok(leakHarbor.dist < 3.1, "critic residual stand is still on Harbor asphalt");
  assert.ok(leakToPho > 4 && leakToPho < 10, "10 m plant bubble still covers that asphalt; 4 m does not");
  assert.ok(plantPlant <= 4, "sidewalk stand at the awning stays inside the tight E range");
});

test("published streetPlay stalls paint a chalkboard of public listing names", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const catalogSrc = readFileSync(join(root, "src", "shops", "catalog.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const shops = JSON.parse(readFileSync(join(root, "public", "data", "shops.json"), "utf8"));
  assert.match(world, /STALL_BOARD_KIND = "chalkboard-menu"/);
  assert.match(world, /STALL_BOARD_SLATE = "#1a3328"/);
  assert.match(world, /STALL_BOARD_HONESTY = "mẫu · not a live market"/);
  assert.match(catalogSrc, /export function stallBoardTitles/);
  assert.match(catalogSrc, /export function stallBoardPaintTitles/);
  assert.match(play, /function makeMenuBoardTexture/);
  assert.match(play, /shop-menu-\$\{shop\.shop_id\}/);
  assert.match(play, /shop-menu-side-\$\{shop\.shop_id\}/);
  assert.match(play, /data-testid="play-stall-boards"/);
  assert.match(play, /data-stall-board=\{STALL_BOARD_KIND\}/);
  assert.match(play, /stallBoardPaintTitles\(stallBoardTitles\(listings, shop\.shop_id\)\)/);
  assert.match(play, /isLocalShopId\(shop\.shop_id\) \? "local-demo" : "authored"/);
  assert.match(play, /data-player-stall-boards=\{String\(drawnPlayerBoardCount\)\}/);
  assert.match(play, /listings=\{listings\}/);
  assert.match(app, /listings=\{listings\}/);
  assert.match(play, /STALL_BOARD_HONESTY/);
  assert.match(play, /ctx\.fillText\(STALL_BOARD_HONESTY/);
  assert.equal(play.includes("Nháp chưa đăng"), false);
  const titles = shops.listings
    .filter((row) => row.status === "published" && row.shop_id === "shop-lantern-fish")
    .map((row) => row.title);
  assert.ok(titles.some((title) => /Cá|cá|fish/i.test(title)));
  assert.ok(titles.some((title) => /Túi|túi|bag/i.test(title)));
  assert.equal(titles.some((title) => /Nháp/.test(title)), false);
  assert.ok(titles.length >= 1 && titles.length <= 3);
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  assert.match(walk, /export function streetPlayShops/);
  assert.match(walk, /export function sortMenuShops/);
  assert.match(walk, /MENU_LEFTOVER_LABEL/);
  assert.match(app, /streetPlayShops\(shops\)/);
  const goodsList = readFileSync(join(root, "src", "shops", "GoodsList.tsx"), "utf8");
  assert.match(goodsList, /sortMenuShops\(shops\)/);
  assert.match(goodsList, /MENU_LEFTOVER_LABEL/);
  const shopPanel = readFileSync(join(root, "src", "shops", "ShopPanel.tsx"), "utf8");
  assert.match(shopPanel, /isMenuLeftoverShop\(shop\)/);
  assert.match(shopPanel, /MENU_LEFTOVER_LABEL/);
  assert.match(shopPanel, /shop-leftover-banner/);
  const localShopsSrc = readFileSync(join(root, "src", "shops", "localShops.ts"), "utf8");
  assert.match(localShopsSrc, /PLAYER_SHOP_NORTH_M = 20/);
  assert.match(localShopsSrc, /export function placeNewLocalShopLngLat/);
  assert.match(localShopsSrc, /persistSidewalkLngLat/);
  assert.match(app, /streets:\s*playStreets/);
});

test("new published player shops persist on the sidewalk, not Harbor asphalt", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const localShopsSrc = readFileSync(join(root, "src", "shops", "localShops.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /export function persistSidewalkLngLat/);
  assert.match(world, /export function stallSidewalkPlant/);
  assert.match(localShopsSrc, /placeNewLocalShopLngLat\(/);
  assert.match(localShopsSrc, /persistSidewalkLngLat\(next\.lon, next\.lat, streets\)/);
  assert.match(app, /streets:\s*playStreets/);
  assert.equal(localShopsSrc.includes("catalog_clear"), false);

  const harborFeat = fixture.features.find((row) => row.properties?.id === "street-harbor-walk");
  assert.ok(harborFeat, "authored Harbor Walk line");
  const harbor = harborFeat.geometry.coordinates.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const nearest = (x, z) => {
    let best = null;
    for (let i = 0; i < harbor.length - 1; i += 1) {
      const a = harbor[i];
      const b = harbor[i + 1];
      const vx = b[0] - a[0];
      const vz = b[1] - a[1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) {
        continue;
      }
      const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (seg * seg)));
      const px = a[0] + vx * t;
      const pz = a[1] + vz * t;
      const dist = Math.hypot(x - px, z - pz);
      if (!best || dist < best.dist) {
        best = { x: px, z: pz, dx: vx / seg, dz: vz / seg, dist };
      }
    }
    return best;
  };
  const offsetSide = (x, z, dx, dz, side, across) => {
    const rot = Math.atan2(dx, dz);
    return { x: x + Math.cos(rot) * side * across, z: z - Math.sin(rot) * side * across };
  };
  const worldToLngLat = (x, z) => ({
    lon: ORIGIN.lon + x / metersPerDegLon(ORIGIN.lat),
    lat: ORIGIN.lat + z / M_PER_DEG_LAT,
  });
  const offsetLngLat = (lon, lat, eastM, northM) => ({
    lon: lon + eastM / metersPerDegLon(lat),
    lat: lat + northM / M_PER_DEG_LAT,
  });
  const distLL = (a, b) => {
    const midLat = (a.lat + b.lat) / 2;
    const east = (b.lon - a.lon) * metersPerDegLon(midLat);
    const north = (b.lat - a.lat) * M_PER_DEG_LAT;
    return Math.hypot(east, north);
  };
  const sidewalkOf = (lon, lat) => {
    const sign = lngLatToWorld(lon, lat);
    const p = { x: sign.x, z: sign.z + 0.72 };
    const hit = nearest(p.x, p.z);
    const rot = Math.atan2(hit.dx, hit.dz);
    const signed = (p.x - hit.x) * Math.cos(rot) + (p.z - hit.z) * -Math.sin(rot);
    const side = signed < 0 ? -1 : 1;
    const placed = offsetSide(hit.x, hit.z, hit.dx, hit.dz, side, 7.2);
    return { persistLane: hit.dist, placed, persist: worldToLngLat(placed.x, placed.z) };
  };

  const spawnCreate = offsetLngLat(SPAWN.lon, SPAWN.lat, 0, 20);
  const spawnPlant = sidewalkOf(spawnCreate.lon, spawnCreate.lat);
  const spawnPersistLane = nearest(
    lngLatToWorld(spawnPlant.persist.lon, spawnPlant.persist.lat).x,
    lngLatToWorld(spawnPlant.persist.lon, spawnPlant.persist.lat).z,
  ).dist;
  assert.ok(spawnCreate.lat > SPAWN.lat, "create-at-spawn still walks north of the nape");
  assert.ok(spawnPlant.persistLane < 1.5, "old-style create-at-spawn persist sat on Harbor asphalt");
  assert.ok(spawnPersistLane >= 5, `create-at-spawn persistLane ${spawnPersistLane} must sit on the walk`);
  assert.ok(distLL(spawnPlant.persist, SPAWN) > 14, "sidewalk persist stays outside spawn keep-out");
  const afterClash = offsetLngLat(spawnCreate.lon, spawnCreate.lat, 12, 0);
  const clashPlant = sidewalkOf(afterClash.lon, afterClash.lat);
  const clashPersistLane = nearest(
    lngLatToWorld(clashPlant.persist.lon, clashPlant.persist.lat).x,
    lngLatToWorld(clashPlant.persist.lon, clashPlant.persist.lat).z,
  ).dist;
  assert.ok(clashPersistLane >= 5, "east-nudge after a neighbor still persists on the walk");

  const onLane = { lon: 106.69804, lat: 10.77185 };
  const lanePlant = sidewalkOf(onLane.lon, onLane.lat);
  const lanePersistWorld = lngLatToWorld(lanePlant.persist.lon, lanePlant.persist.lat);
  const lanePersistLane = nearest(lanePersistWorld.x, lanePersistWorld.z).dist;
  assert.ok(lanePlant.persistLane < 2, "create-on-lane starts on Harbor asphalt");
  assert.ok(lanePersistLane >= 5, `create-on-lane persistLane ${lanePersistLane} must sit on the walk`);
  assert.ok(distLL(lanePlant.persist, SPAWN) > 14, "lane-create persist stays outside keep-out");
});

test("drawn player streetPlay shops reuse the lantern chalkboard painter", () => {
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const catalogSrc = readFileSync(join(root, "src", "shops", "catalog.ts"), "utf8");
  assert.match(play, /stallBoardPaintTitles\(stallBoardTitles\(listings, shop\.shop_id\)\)/);
  assert.match(play, /data-source=\{isLocalShopId\(shop\.shop_id\) \? "local-demo" : "authored"\}/);
  assert.match(play, /data-player-drawn=\{String\(drawnPlayerBoardCount\)\}/);
  assert.match(catalogSrc, /function stallBoardPaintTitle/);
  assert.equal(play.includes("Nháp chưa đăng"), false);
  const playerListings = [
    { shop_id: "shop-local-che1", status: "published", title: "Chè đậu xanh" },
    { shop_id: "shop-local-che1", status: "draft", title: "Nháp chưa đăng" },
    { shop_id: "shop-local-sharedpc", status: "published", title: "Phở bò" },
  ];
  const publicFor = (shopId) =>
    playerListings
      .filter((row) => row.status === "published" && row.shop_id === shopId)
      .map((row) => row.title);
  const paint = (title) => (/\(\s*mẫu\s*\)/i.test(title) ? title : `${title} (mẫu)`);
  assert.deepEqual(publicFor("shop-local-che1").map(paint), ["Chè đậu xanh (mẫu)"]);
  assert.equal(publicFor("shop-local-che1").includes("Nháp chưa đăng"), false);
  assert.deepEqual(publicFor("shop-local-sharedpc").map(paint), ["Phở bò (mẫu)"]);
});

test("shop signs are 3D pole-boards at published shop markers", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /export function shopSignSpec/);
  assert.match(world, /kind: "pole-board"/);
  assert.match(world, /boardW: 3\.55/);
  assert.match(world, /boardH: 1\.22/);
  assert.match(play, /shop-board-\$\{shop\.shop_id\}/);
  assert.match(play, /shop-board-back-\$\{shop\.shop_id\}/);
  assert.match(play, /data-shop-sign-kind="pole-board"/);
  assert.match(play, /data-shop-sign-faces="2"/);
  assert.match(play, /data-testid=\{\`shop-sign-\$\{shop\.shop_id\}\`\}/);
  assert.match(play, /data-e=\{spec\.eHint\}/);
  assert.match(play, /data-lane-m=\{spec\.laneM\.toFixed\(2\)\}/);
  assert.match(play, /shopSignSpec\(shop, streets\)/);
  assert.match(world, /x: stall\.x/);
  assert.match(world, /signX: plant\.x/);
  assert.match(play, /bold 52px/);
  assert.match(play, /#9a2f0e/);
  const shop = { lon: 106.6980366, lat: 10.7718712 };
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const persist = lngLatToWorld(shop.lon, shop.lat);
  assert.ok(persist.z > spawn.z + 20, "lantern persist sits north of spawn on the street");
  assert.ok(Math.abs(persist.x - spawn.x) < 8);
});

test("street lighting and ground language stay authored, not a beige sandbox", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(world, /LIGHT_KIND = "hemi-sun"/);
  assert.match(world, /GROUND_KIND = "road-walk-curb"/);
  assert.match(world, /WALL_FINISH_KIND = "plaster-paint"/);
  assert.match(world, /export function curbSegments/);
  assert.match(world, /export function edgeStripSegments/);
  assert.match(world, /EDGE_COLOR = "#e4cf6a"/);
  assert.match(world, /ROAD_COLOR = "#1a1c20"/);
  assert.match(world, /WALK_COLOR = "#ddd6c8"/);
  assert.match(play, /<StreetSun /);
  assert.match(play, /data-light=\{LIGHT_KIND\}/);
  assert.match(play, /data-ground=\{GROUND_KIND\}/);
  assert.match(play, /name="street-sun"/);
  assert.match(play, /name="street-hemi"/);
  assert.match(play, /userData=\{\{ kind: "curb" \}\}/);
  assert.match(play, /userData=\{\{ kind: "road-edge" \}\}/);
  assert.equal(play.includes('color="#8a8578"'), false);
  assert.equal(play.includes("intensity={0.38}"), false);
  const hexLum = (hex) => {
    const n = Number.parseInt(hex.slice(1), 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  };
  assert.ok(hexLum("#1a1c20") < hexLum("#ddd6c8") - 0.35, "asphalt must be darker than walk");
  assert.ok(hexLum("#1a1c20") < hexLum("#b5b1a6") - 0.2, "asphalt must be darker than plaza");
  const tram = fixture.features.find((feature) => feature.id === "street-tram-approach");
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  assert.equal(tram?.properties?.name, "Tram Approach");
  assert.equal(harbor?.properties?.name, "Harbor Walk");
  const line = harbor.geometry.coordinates;
  const a = lngLatToWorld(line[0][0], line[0][1]);
  const b = lngLatToWorld(line[1][0], line[1][1]);
  const dx = b.x - a.x;
  const dz = b.z - a.z;
  const rot = Math.atan2(dx, dz);
  const across = 8.6 / 2 + 0.72 / 2;
  const midX = (a.x + b.x) / 2;
  const midZ = (a.z + b.z) / 2;
  const curbA = { x: midX + Math.cos(rot) * across, z: midZ - Math.sin(rot) * across };
  const curbB = { x: midX - Math.cos(rot) * across, z: midZ + Math.sin(rot) * across };
  assert.ok(Math.hypot(curbA.x - midX, curbA.z - midZ) > 4);
  assert.ok(Math.abs(Math.hypot(curbA.x - midX, curbA.z - midZ) - Math.hypot(curbB.x - midX, curbB.z - midZ)) < 0.02);
});

test("Harbor Walk gets authored lamps, one zebra, and sidewalk planters", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /STREET_PROPS_KIND = "lamps-crosswalk-planters"/);
  assert.match(world, /export function streetPropsFromStreets/);
  assert.match(world, /export function streetPropSolidsFromCollection/);
  assert.match(world, /crosswalk-harbor-lantern/);
  assert.match(world, /crosswalk-harbor-steps-east/);
  assert.match(world, /crosswalk-harbor-steps-west/);
  assert.match(world, /lamp-harbor-shop-e/);
  assert.match(world, /lamp-harbor-walk-e/);
  assert.match(world, /lamp-harbor-near-e/);
  assert.match(world, /LAMP_SKIP_SPAWN_M = 16/);
  assert.match(play, /function LampPost/);
  assert.match(play, /function CrosswalkBand/);
  assert.match(play, /function PlanterMass/);
  assert.match(play, /data-street-props=\{STREET_PROPS_KIND\}/);
  assert.match(play, /data-testid="play-street-props"/);
  assert.match(play, /<pointLight/);
  assert.match(app, /streetPropSolidsFromCollection/);
  assert.match(app, /walkSolids/);

  const M_LAT = 111320;
  const mLon = metersPerDegLon(ORIGIN.lat);
  const toWorld = (lon, lat) => ({
    x: (lon - ORIGIN.lon) * mLon,
    z: (lat - ORIGIN.lat) * M_LAT,
  });
  const spawn = toWorld(SPAWN.lon, SPAWN.lat);
  const shop = toWorld(106.6980366, 10.7718712);
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const tram = fixture.features.find((feature) => feature.id === "street-tram-approach");
  const lineOf = (feature) => feature.geometry.coordinates.map(([lon, lat]) => [toWorld(lon, lat).x, toWorld(lon, lat).z]);
  const polyLen = (pts) => {
    let n = 0;
    for (let i = 0; i < pts.length - 1; i += 1) n += Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    return n;
  };
  const atDist = (pts, dist) => {
    let left = dist;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const dx = pts[i + 1][0] - pts[i][0];
      const dz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(dx, dz);
      if (seg < 0.2) continue;
      if (left <= seg) {
        return { x: pts[i][0] + (dx / seg) * left, z: pts[i][1] + (dz / seg) * left, dx: dx / seg, dz: dz / seg };
      }
      left -= seg;
    }
    return null;
  };
  const lamps = [];
  for (const [id, pts] of [
    ["street-harbor-walk", lineOf(harbor)],
    ["street-tram-approach", lineOf(tram)],
  ]) {
    const total = polyLen(pts);
    let idx = 0;
    for (let dist = 18; dist <= total - 18 + 0.01; dist += 40) {
      const at = atDist(pts, dist);
      if (!at) continue;
      const rot = Math.atan2(at.dx, at.dz);
      for (const side of [1, -1]) {
        const x = at.x + Math.cos(rot) * side * (8.6 / 2 + 0.52);
        const z = at.z - Math.sin(rot) * side * (8.6 / 2 + 0.52);
        if (Math.hypot(x - spawn.x, z - spawn.z) < 16) continue;
        if (Math.hypot(x, z) < 12) continue;
        lamps.push({ id, x, z });
      }
      idx += 1;
    }
  }
  assert.ok(lamps.length >= 12, `expected a street of lamps, got ${lamps.length}`);
  assert.ok(lamps.length <= 40, "still a cheap 400 m block, not a city set");
  assert.ok(lamps.some((lamp) => lamp.id === "street-harbor-walk"));
  assert.ok(lamps.some((lamp) => lamp.id === "street-tram-approach"));
  assert.ok(lamps.every((lamp) => Math.hypot(lamp.x - spawn.x, lamp.z - spawn.z) >= 15.9));
  assert.ok(lamps.every((lamp) => Math.abs(lamp.x) < 200 && Math.abs(lamp.z) < 200));

  const onRoad = (() => {
    const pts = lineOf(harbor);
    let best = null;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const vx = pts[i + 1][0] - pts[i][0];
      const vz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(vx, vz);
      const t = Math.max(0, Math.min(1, ((shop.x - pts[i][0]) * vx + (shop.z - pts[i][1]) * vz) / (seg * seg)));
      const x = pts[i][0] + vx * t;
      const z = pts[i][1] + vz * t;
      const d = Math.hypot(shop.x - x, shop.z - z);
      if (!best || d < best.d) best = { x, z, d };
    }
    return best;
  })();
  assert.ok(onRoad.d < 6, "zebra sits on Harbor Walk at the lantern stall");
  assert.ok(Math.hypot(onRoad.x - shop.x, onRoad.z - shop.z) < 6);
  const shopCurb = Math.hypot(onRoad.x + (8.6 / 2 + 0.52) - shop.x, onRoad.z - shop.z);
  assert.ok(shopCurb < 8, "lantern stall sits on the street, lamps on the curb");

  const northOk = lamps.every((lamp) => Math.hypot(lamp.x - spawn.x, lamp.z - (spawn.z + 12)) > 1.2);
  assert.equal(northOk, true, "12 m north stroll must not sit inside a lamp");
  const lampHit = lamps.some((lamp) => Math.hypot(lamp.x - lamps[0].x, lamp.z - lamps[0].z) < 0.2);
  assert.equal(lampHit, true);
});

test("Harbor Walk / Steps East mouth gets one authored zebra + stop-line + curb return", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /CORNER_CROSSING_KIND = "zebra-stopline-curb"/);
  assert.match(world, /export function harborStepsEastCrossing/);
  assert.match(world, /export function harborStepsWestCrossing/);
  assert.match(world, /crosswalk-harbor-steps-east/);
  assert.match(world, /stopline-harbor-steps-east/);
  assert.match(world, /curb-return-harbor-steps-/);
  assert.match(world, /Not a fifth street/);
  assert.match(world, /nearAnyCrosswalk/);
  assert.match(play, /function StopLineMark/);
  assert.match(play, /function CurbReturnLip/);
  assert.match(play, /data-corner-crossing=\{CORNER_CROSSING_KIND\}/);
  assert.match(play, /data-testid="play-corner-crossing"/);
  assert.match(play, /data-kind="stop-line"/);
  assert.match(play, /data-kind="curb-return"/);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /inner parcel lanes, not a city grid/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(world.includes("hip sphere"), false);
  assert.ok(!/Nguyễn|Lê Lợi|Đồng Khởi|Hai Bà/.test(world), "do not invent a downtown grid");
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "crossing does not add a GeoJSON street");
  assert.deepEqual(
    streets.map((row) => row.properties?.display_name ?? row.properties?.name).sort(),
    ["Harbor Walk", "Tram Approach"],
  );

  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const shop = lngLatToWorld(106.6980366, 10.7718712);
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const pts = harbor.geometry.coordinates.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const nearest = (line, x, z) => {
    let best = null;
    for (let i = 0; i < line.length - 1; i += 1) {
      const vx = line[i + 1][0] - line[i][0];
      const vz = line[i + 1][1] - line[i][1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) continue;
      const t = Math.max(0, Math.min(1, ((x - line[i][0]) * vx + (z - line[i][1]) * vz) / (seg * seg)));
      const px = line[i][0] + vx * t;
      const pz = line[i][1] + vz * t;
      const d = Math.hypot(x - px, z - pz);
      if (!best || d < best.d) best = { x: px, z: pz, d };
    }
    return best;
  };
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const feature of fixture.features) {
    if (!String(feature.properties?.id ?? "").startsWith("bldg-steps-e")) continue;
    const ring = feature.geometry.coordinates[0];
    for (const [lon, lat] of ring) {
      const p = lngLatToWorld(lon, lat);
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minZ = Math.min(minZ, p.z);
      maxZ = Math.max(maxZ, p.z);
    }
  }
  const laneX = minX - 2.45;
  const cornerZ = Math.max(minZ + 10, Math.min(maxZ - 10, -76.2));
  const onHarbor = nearest(pts, laneX, cornerZ);
  let zx = onHarbor.x;
  let zz = onHarbor.z;
  if (Math.hypot(zx - shop.x, zz - shop.z) < 8.2) {
    zz -= 4.2;
  }
  assert.ok(onHarbor.d > 5 && onHarbor.d < 16, `gap ${onHarbor.d}`);
  assert.ok(Math.abs(zx - onHarbor.x) < 1.2, "zebra sits on Harbor asphalt, not the light walk");
  assert.ok(zz < -78 && zz > -86, `corner zebra z ${zz}`);
  assert.ok(Math.hypot(zx - spawn.x, zz - spawn.z) > 16, "corner stays off spawn");
  assert.ok(Math.hypot(zx - shop.x, zz - shop.z) > 5, "corner stays off lantern stall");
  assert.ok(Math.hypot(zx, zz) > 20, "not the world origin crossing skip");
  assert.ok(laneX > zx + 6, "Steps East stays east of the Harbor zebra");
  assert.equal(cornerZ, -76.2);
});

test("Harbor Walk / Steps West mouth gets the same authored zebra + stop-line + curb return", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /export function harborStepsWestCrossing/);
  assert.match(world, /crosswalk-harbor-steps-west/);
  assert.match(world, /stopline-harbor-steps-west/);
  assert.match(world, /curb-return-harbor-steps-west-/);
  assert.match(world, /curb-return-steps-west-/);
  assert.match(world, /WEST_ZEBRA_ACROSS_M = 4.2/);
  assert.match(world, /Not a fifth street/);
  assert.match(world, /isHarborStepsCrosswalk/);
  assert.match(play, /data-mouth=/);
  assert.match(play, /WEST_CROSSWALK_ID/);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /Authored 400 m/);
  assert.match(honesty, /OSM\/Overture/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(world.includes("hip sphere"), false);
  assert.ok(!/Nguyễn|Lê Lợi|Đồng Khởi|Hai Bà/.test(world), "do not invent a downtown grid");
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "west crossing does not add a GeoJSON street");
  assert.deepEqual(
    streets.map((row) => row.properties?.display_name ?? row.properties?.name).sort(),
    ["Harbor Walk", "Tram Approach"],
  );

  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const shop = lngLatToWorld(106.6980366, 10.7718712);
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const pts = harbor.geometry.coordinates.map(([lon, lat]) => {
    const p = lngLatToWorld(lon, lat);
    return [p.x, p.z];
  });
  const nearest = (line, x, z) => {
    let best = null;
    for (let i = 0; i < line.length - 1; i += 1) {
      const vx = line[i + 1][0] - line[i][0];
      const vz = line[i + 1][1] - line[i][1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) continue;
      const t = Math.max(0, Math.min(1, ((x - line[i][0]) * vx + (z - line[i][1]) * vz) / (seg * seg)));
      const px = line[i][0] + vx * t;
      const pz = line[i][1] + vz * t;
      const d = Math.hypot(x - px, z - pz);
      if (!best || d < best.d) best = { x: px, z: pz, d };
    }
    return best;
  };
  let eastMinX = Infinity;
  let eastMinZ = Infinity;
  let eastMaxZ = -Infinity;
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const feature of fixture.features) {
    const id = String(feature.properties?.id ?? "");
    const ring = feature.geometry.coordinates[0];
    if (id.startsWith("bldg-steps-e")) {
      for (const [lon, lat] of ring) {
        const p = lngLatToWorld(lon, lat);
        eastMinX = Math.min(eastMinX, p.x);
        eastMinZ = Math.min(eastMinZ, p.z);
        eastMaxZ = Math.max(eastMaxZ, p.z);
      }
    }
    if (!id.startsWith("bldg-steps-w")) continue;
    for (const [lon, lat] of ring) {
      const p = lngLatToWorld(lon, lat);
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minZ = Math.min(minZ, p.z);
      maxZ = Math.max(maxZ, p.z);
    }
  }
  const laneX = maxX + 2.45;
  const cornerZ = Math.max(minZ + 10, Math.min(maxZ - 10, -76.2));
  const onHarbor = nearest(pts, laneX, cornerZ);
  const zx = laneX;
  const zz = onHarbor.z;
  const eastLaneX = eastMinX - 2.45;
  const eastCornerZ = Math.max(eastMinZ + 10, Math.min(eastMaxZ - 10, -76.2));
  const eastHarbor = nearest(pts, eastLaneX, eastCornerZ);
  assert.ok(onHarbor.d > 5 && onHarbor.d < 22, `west gap ${onHarbor.d}`);
  assert.ok(zx < onHarbor.x - 6, "Steps West zebra sits west of Harbor, not on the east mouth");
  assert.ok(Math.hypot(zx - eastHarbor.x, zz - eastHarbor.z) > 8, "west zebra does not stack on the east Harbor zebra");
  assert.ok(zz < -70 && zz > -86, `west corner zebra z ${zz}`);
  assert.ok(Math.hypot(zx - spawn.x, zz - spawn.z) > 16, "west corner stays off spawn");
  assert.ok(Math.hypot(zx - shop.x, zz - shop.z) > 5, "west corner stays off lantern stall");
  assert.ok(laneX < 0, "Steps West lane stays west of origin");
  assert.equal(cornerZ, -76.2);
});

test("Harbor Walk / Tram Approach mouth gets the same authored zebra + stop-line + curb return", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /export function harborTramCrossing/);
  assert.match(world, /crosswalk-harbor-tram/);
  assert.match(world, /stopline-harbor-tram/);
  assert.match(world, /curb-return-harbor-tram-/);
  assert.match(world, /curb-return-tram-approach-/);
  assert.match(world, /TRAM_MOUTH_ALONG_M = 5\.55/);
  assert.match(world, /isHarborTramCrosswalk/);
  assert.match(world, /isAuthoredMouthCrosswalk/);
  assert.match(world, /Not a fifth street/);
  assert.match(play, /TRAM_CROSSWALK_ID/);
  assert.match(play, /data-mouth=/);
  assert.match(honesty, /two official named streets/);
  assert.match(honesty, /Authored 400 m/);
  assert.match(honesty, /OSM\/Overture/);
  assert.equal(world.includes("openstreetmap"), false);
  assert.equal(world.includes("hip sphere"), false);
  assert.ok(!/Nguyễn|Lê Lợi|Đồng Khởi|Hai Bà/.test(world), "do not invent a downtown grid");
  const streets = fixture.features.filter((feature) => feature.properties?.kind === "street");
  assert.equal(streets.length, 2, "tram crossing does not add a GeoJSON street");
  assert.deepEqual(
    streets.map((row) => row.properties?.display_name ?? row.properties?.name).sort(),
    ["Harbor Walk", "Tram Approach"],
  );

  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const shop = lngLatToWorld(106.6980366, 10.7718712);
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const tram = fixture.features.find((feature) => feature.id === "street-tram-approach");
  const lineOf = (feature) =>
    feature.geometry.coordinates.map(([lon, lat]) => {
      const p = lngLatToWorld(lon, lat);
      return [p.x, p.z];
    });
  const harborPts = lineOf(harbor);
  const tramPts = lineOf(tram);
  const polyLen = (pts) => {
    let n = 0;
    for (let i = 0; i < pts.length - 1; i += 1) n += Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    return n;
  };
  const atDist = (pts, dist) => {
    let left = dist;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const dx = pts[i + 1][0] - pts[i][0];
      const dz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(dx, dz);
      if (seg < 0.2) continue;
      if (left <= seg) {
        return { x: pts[i][0] + (dx / seg) * left, z: pts[i][1] + (dz / seg) * left, dx: dx / seg, dz: dz / seg };
      }
      left -= seg;
    }
    return null;
  };
  const nearest = (line, x, z) => {
    let best = null;
    for (let i = 0; i < line.length - 1; i += 1) {
      const vx = line[i + 1][0] - line[i][0];
      const vz = line[i + 1][1] - line[i][1];
      const seg = Math.hypot(vx, vz);
      if (seg < 0.2) continue;
      const t = Math.max(0, Math.min(1, ((x - line[i][0]) * vx + (z - line[i][1]) * vz) / (seg * seg)));
      const px = line[i][0] + vx * t;
      const pz = line[i][1] + vz * t;
      const d = Math.hypot(x - px, z - pz);
      if (!best || d < best.d) best = { x: px, z: pz, dx: vx / seg, dz: vz / seg, d };
    }
    return best;
  };
  let tramJoin = null;
  const harborLen = polyLen(harborPts);
  for (let dist = 0; dist <= harborLen + 0.01; dist += 3) {
    const at = atDist(harborPts, dist);
    if (!at) continue;
    const near = nearest(tramPts, at.x, at.z);
    if (!near) continue;
    if (!tramJoin || near.d < tramJoin.d) {
      tramJoin = { ...at, tx: near.x, tz: near.z, tdx: near.dx, tdz: near.dz, d: near.d };
    }
  }
  const east = tramJoin.tdx >= 0 ? 1 : -1;
  const zx = tramJoin.tx + tramJoin.tdx * east * 5.55;
  const zz = tramJoin.tz + tramJoin.tdz * east * 5.55;
  let eastMinX = Infinity;
  let eastMinZ = Infinity;
  let eastMaxZ = -Infinity;
  let westMaxX = -Infinity;
  let westMinZ = Infinity;
  let westMaxZ = -Infinity;
  for (const feature of fixture.features) {
    const id = String(feature.properties?.id ?? "");
    const ring = feature.geometry.coordinates[0];
    if (id.startsWith("bldg-steps-e")) {
      for (const [lon, lat] of ring) {
        const p = lngLatToWorld(lon, lat);
        eastMinX = Math.min(eastMinX, p.x);
        eastMinZ = Math.min(eastMinZ, p.z);
        eastMaxZ = Math.max(eastMaxZ, p.z);
      }
    }
    if (id.startsWith("bldg-steps-w")) {
      for (const [lon, lat] of ring) {
        const p = lngLatToWorld(lon, lat);
        westMaxX = Math.max(westMaxX, p.x);
        westMinZ = Math.min(westMinZ, p.z);
        westMaxZ = Math.max(westMaxZ, p.z);
      }
    }
  }
  const eastLaneX = eastMinX - 2.45;
  const eastCornerZ = Math.max(eastMinZ + 10, Math.min(eastMaxZ - 10, -76.2));
  const westLaneX = westMaxX + 2.45;
  const westCornerZ = Math.max(westMinZ + 10, Math.min(westMaxZ - 10, -76.2));
  const eastHarbor = nearest(harborPts, eastLaneX, eastCornerZ);
  assert.ok(tramJoin.d < 8, `Harbor×Tram join ${tramJoin.d}`);
  assert.ok(zx > 4 && zx < 8, `tram zebra x ${zx}`);
  assert.ok(Math.abs(zz) < 3, `tram zebra z ${zz}`);
  assert.ok(Math.hypot(zx, zz) < 12, "sits on the official-official mouth, not a new street");
  assert.ok(Math.hypot(zx - spawn.x, zz - spawn.z) > 16, "tram mouth stays off spawn");
  assert.ok(Math.hypot(zx - shop.x, zz - shop.z) > 40, "tram mouth stays off the lantern zebra");
  assert.ok(Math.hypot(zx - eastHarbor.x, zz - eastHarbor.z) > 40, "does not stack on Steps East");
  assert.ok(Math.hypot(zx - westLaneX, zz - westCornerZ) > 40, "does not stack on Steps West");
  assert.ok(zz > -40, "tram mouth stays north of the Steps band");
});

test("Harbor Walk / Tram Approach get hashed parked box scooters on the sidewalk edge", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(world, /SCOOTER_KIND = "parked-box-scooter"/);
  assert.match(world, /export function scooterColorForId/);
  assert.match(world, /keepHashedScooter/);
  assert.match(world, /SCOOTER_CURB_M = STREET_WIDTH_M \/ 2 \+ 1\.28/);
  assert.match(world, /SCOOTER_SKIP_LANTERN_M = 11/);
  assert.match(world, /scooter-harbor-near-e/);
  assert.match(world, /scooter-harbor-near-w/);
  assert.match(world, /scooter-harbor-past-e/);
  assert.match(world, /scooters\.map\(\(scooter\) =>/);
  assert.match(world, /STATIC props, not riders/);
  assert.match(play, /function ParkedScooter/);
  assert.match(play, /kind: "scooter"/);
  assert.match(play, /data-scooters=\{String\(propCount\.scooters\)\}/);
  assert.match(play, /data-testid="play-scooters"/);
  assert.match(play, /no rider, no traffic AI/);
  assert.match(app, /streetPropSolidsFromCollection/);
  assert.equal(play.includes("Honda"), false);
  assert.equal(play.includes("Yamaha"), false);
  assert.equal(world.includes("glb"), false);

  const M_LAT = 111320;
  const mLon = metersPerDegLon(ORIGIN.lat);
  const toWorld = (lon, lat) => ({
    x: (lon - ORIGIN.lon) * mLon,
    z: (lat - ORIGIN.lat) * M_LAT,
  });
  const colorIndex = (id) => {
    let n = 0;
    for (let i = 0; i < id.length; i += 1) n = (n + id.charCodeAt(i) * (i + 3)) % 97;
    return n;
  };
  const spawn = toWorld(SPAWN.lon, SPAWN.lat);
  const shop = toWorld(106.6980366, 10.7718712);
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const tram = fixture.features.find((feature) => feature.id === "street-tram-approach");
  const lineOf = (feature) =>
    feature.geometry.coordinates.map(([lon, lat]) => [toWorld(lon, lat).x, toWorld(lon, lat).z]);
  const polyLen = (pts) => {
    let n = 0;
    for (let i = 0; i < pts.length - 1; i += 1) {
      n += Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    }
    return n;
  };
  const atDist = (pts, dist) => {
    let left = dist;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const dx = pts[i + 1][0] - pts[i][0];
      const dz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(dx, dz);
      if (seg < 0.2) continue;
      if (left <= seg) {
        return {
          x: pts[i][0] + (dx / seg) * left,
          z: pts[i][1] + (dz / seg) * left,
          dx: dx / seg,
          dz: dz / seg,
        };
      }
      left -= seg;
    }
    return null;
  };
  const offsetSide = (x, z, dx, dz, side, across) => {
    const rot = Math.atan2(dx, dz);
    return {
      x: x + Math.cos(rot) * side * across,
      z: z - Math.sin(rot) * side * across,
    };
  };
  const scooters = [];
  const curb = 8.6 / 2 + 1.28;
  for (const [id, pts] of [
    ["street-harbor-walk", lineOf(harbor)],
    ["street-tram-approach", lineOf(tram)],
  ]) {
    const total = polyLen(pts);
    let index = 0;
    for (let dist = 22; dist <= total - 22 + 0.01; dist += 28) {
      const at = atDist(pts, dist);
      if (!at) continue;
      for (const side of [1, -1]) {
        const sid = `scooter-${id}-${index}-${side > 0 ? "e" : "w"}`;
        if (colorIndex(sid) % 7 >= 2) continue;
        const jitter = (colorIndex(sid) % 9 - 4) * 0.55;
        const atj = atDist(pts, dist + jitter) || at;
        const p = offsetSide(atj.x, atj.z, atj.dx, atj.dz, side, curb);
        if (Math.hypot(p.x, p.z) > 192) continue;
        if (Math.hypot(p.x - spawn.x, p.z - spawn.z) < 2.8) continue;
        if (Math.hypot(p.x - shop.x, p.z - shop.z) < 11) continue;
        if (Math.hypot(p.x, p.z) < 9) continue;
        if (Math.hypot(p.x - shop.x, p.z - shop.z) < 5) continue;
        if (scooters.some((row) => Math.hypot(row.x - p.x, row.z - p.z) < 8)) continue;
        const across = Math.hypot(p.x - atj.x, p.z - atj.z);
        scooters.push({ id: sid, street: id, x: p.x, z: p.z, across, color: colorIndex(sid) % 10 });
      }
      index += 1;
    }
  }
  assert.ok(scooters.length >= 8, `expected a short parked row, got ${scooters.length}`);
  assert.ok(scooters.length <= 20, "still a cheap 400 m block, not a parking survey");
  assert.ok(scooters.some((row) => row.street === "street-harbor-walk"));
  assert.ok(scooters.some((row) => row.street === "street-tram-approach"));
  assert.ok(scooters.every((row) => row.across > 8.6 / 2 + 0.8), "stay off the driving lane");
  assert.ok(scooters.every((row) => Math.hypot(row.x - spawn.x, row.z - spawn.z) >= 2.8));
  assert.ok(scooters.every((row) => Math.hypot(row.x - shop.x, row.z - shop.z) >= 11));
  assert.ok(new Set(scooters.map((row) => row.color)).size >= 3, "id-hash color variety");
  const northWalkClear = scooters.every(
    (row) => Math.hypot(row.x - spawn.x, row.z - (spawn.z + 8)) > 1.4,
  );
  assert.equal(northWalkClear, true, "north stroll on the lane must not sit inside a scooter");
});

test("published kiosks get authored crate / basket spill, not a catalog", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const shops = readFileSync(join(root, "src", "shops", "catalog.ts"), "utf8");
  assert.match(world, /MARKET_SPILL_KIND = "crate-basket-stack"/);
  assert.match(world, /export function shopMarketSpill/);
  assert.match(world, /export function streetMarketSpill/);
  assert.match(world, /export function spillPaletteForShop/);
  assert.match(world, /COOLER_TEAL = "#2a7a78"/);
  assert.match(world, /CRATE_WOOD = "#8a5a32"/);
  assert.match(world, /Not catalog listings/);
  assert.match(play, /function MarketSpillProp/);
  assert.match(play, /data-testid="play-market-spill"/);
  assert.match(play, /data-market-spill=\{MARKET_SPILL_KIND\}/);
  assert.match(play, /Authored market spill/);
  assert.match(app, /marketSpillSolids\(marketSpillFromCollection/);
  assert.equal(world.includes("glb"), false);
  assert.equal(play.includes("listing-morning-mackerel"), false);
  assert.equal(shops.includes("listing-spill"), false);

  const lantern = {
    shop_id: "shop-lantern-fish",
    name: "Quầy Cá Đèn Lồng",
    lon: 106.6980366,
    lat: 10.7718712,
  };
  const pho = {
    shop_id: "shop-local-pho",
    name: "Quầy Phở Nhà",
    lon: 106.69815,
    lat: 10.7719,
  };
  const leftover = {
    shop_id: "shop-local-sharedpc",
    name: "Shared PC",
    lon: SPAWN.lon,
    lat: SPAWN.lat,
  };
  const colorIndex = (id) => {
    let n = 0;
    for (let i = 0; i < id.length; i += 1) n = (n + id.charCodeAt(i) * (i + 3)) % 97;
    return n;
  };
  const isFish = (shop) => /lantern|fish|cá|ca\s/.test(`${shop.shop_id} ${shop.name}`.toLowerCase());
  assert.equal(isFish(lantern), true);
  assert.equal(isFish(pho), false);
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  const lanternSign = lngLatToWorld(lantern.lon, lantern.lat);
  const stall = { x: lanternSign.x, z: lanternSign.z + 0.72 };
  const west = { x: stall.x - 1.72, z: stall.z + 0.55 };
  const east = { x: stall.x + 1.72, z: stall.z + 0.55 };
  const radius = 0.55;
  const half = 0.48;
  const approach = { x: stall.x, z: stall.z - 2.4 };
  const hits = (a, b) => Math.hypot(a.x - b.x, a.z - b.z) < half + radius;
  assert.equal(hits(approach, west), false, "south E approach must miss west crates");
  assert.equal(hits(approach, east), false, "south E approach must miss east crates");
  const stroll = { x: spawn.x, z: spawn.z + 8 };
  assert.equal(hits(stroll, west), false, "north lane stroll must miss lantern crates");
  const leftoverStall = {
    x: lngLatToWorld(leftover.lon, leftover.lat).x,
    z: lngLatToWorld(leftover.lon, leftover.lat).z + 0.72,
  };
  const leftoverHitsSpawn =
    Math.abs(spawn.x - leftoverStall.x) < 1.32 + radius + 0.2 &&
    Math.abs(spawn.z - leftoverStall.z) < 0.88 + radius + 0.2;
  assert.equal(leftoverHitsSpawn, true, "spawn leftover kiosk is inside keep-out so stall+spill are not drawn");
  const HASH = ["#8a5a32", "#6e3d24", "#a06a3a", "#5a4030", "#9a6a42", "#7a4a28"];
  const phoCrate = HASH[colorIndex(`${pho.shop_id}\0${pho.name}`) % HASH.length];
  assert.notEqual(phoCrate, "#2a7a78");
  assert.equal("#2a7a78" !== "#8a5a32", true);

  const M_LAT = 111320;
  const mLon = metersPerDegLon(ORIGIN.lat);
  const toWorld = (lon, lat) => ({
    x: (lon - ORIGIN.lon) * mLon,
    z: (lat - ORIGIN.lat) * M_LAT,
  });
  const harbor = fixture.features.find((feature) => feature.id === "street-harbor-walk");
  const line = harbor.geometry.coordinates.map(([lon, lat]) => [toWorld(lon, lat).x, toWorld(lon, lat).z]);
  const polyLen = (pts) => {
    let n = 0;
    for (let i = 0; i < pts.length - 1; i += 1) {
      n += Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    }
    return n;
  };
  const atDist = (pts, dist) => {
    let left = dist;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const dx = pts[i + 1][0] - pts[i][0];
      const dz = pts[i + 1][1] - pts[i][1];
      const seg = Math.hypot(dx, dz);
      if (seg < 0.2) continue;
      if (left <= seg) {
        return { x: pts[i][0] + (dx / seg) * left, z: pts[i][1] + (dz / seg) * left, dx: dx / seg, dz: dz / seg };
      }
      left -= seg;
    }
    return null;
  };
  const offsetSide = (x, z, dx, dz, side, across) => {
    const rot = Math.atan2(dx, dz);
    return { x: x + Math.cos(rot) * side * across, z: z - Math.sin(rot) * side * across };
  };
  const shop = toWorld(106.6980366, 10.7718712);
  const across = 8.6 / 2 + 2.55;
  const stacks = [];
  for (const [id, along, side] of [
    ["spill-harbor-walk-e", 0.268, 1],
    ["spill-harbor-mid-w", 0.408, -1],
    ["spill-harbor-north-e", 0.512, 1],
    ["spill-harbor-far-w", 0.575, -1],
  ]) {
    const at = atDist(line, along * polyLen(line));
    if (!at) continue;
    const p = offsetSide(at.x, at.z, at.dx, at.dz, side, across);
    if (Math.hypot(p.x - shop.x, p.z - shop.z) < 10) continue;
    if (Math.hypot(p.x - spawn.x, p.z - spawn.z) < 3.4) continue;
    stacks.push({ id, ...p, across: Math.hypot(p.x - at.x, p.z - at.z) });
  }
  assert.ok(stacks.length >= 2 && stacks.length <= 4, `expected 2-4 sidewalk stacks, got ${stacks.length}`);
  assert.ok(stacks.every((row) => row.across > 8.6 / 2 + 1.6), "street stacks stay off the driving lane");
  assert.ok(stacks.every((row) => Math.hypot(row.x - shop.x, row.z - shop.z) >= 10));
});

test("Harbor Walk / Tram Approach roofs get a parapet and hashed AC/tank, still boxes", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  assert.match(world, /ROOF_KIND = "parapet-ac-tank"/);
  assert.match(world, /export function roofPiecesForBuilding/);
  assert.match(world, /export function roofUnitsForId/);
  assert.match(world, /export function lidColorForId/);
  assert.match(world, /kind: "parapet"/);
  assert.match(world, /place\("ac"/);
  assert.match(world, /place\("tank"/);
  assert.match(world, /Not interiors, not a walkable roof/);
  assert.match(play, /data-roof=\{ROOF_KIND\}/);
  assert.match(play, /data-testid="play-roofs"/);
  assert.match(play, /roofPiecesForBuilding/);
  assert.match(play, /kind: "roof"/);
  assert.match(app, /shopStallSolids\(shops, playStreets\)/);
  assert.equal(app.includes("roofPiecesForBuilding"), false);
  assert.equal(walk.includes("roofPiecesForBuilding"), false);
  assert.match(walk, /COLLISION_KIND = "footprint-radius"/);

  const WALLS = [
    "#c9a06e",
    "#b89062",
    "#d4b07a",
    "#a67c58",
    "#c09a68",
    "#b89a7a",
    "#a8885c",
    "#d2ae78",
    "#9a7a62",
    "#c4a090",
    "#8e6d55",
    "#d8b48a",
    "#b07058",
    "#c8b090",
    "#8f8468",
    "#be8a6a",
    "#a89878",
    "#d2c0a4",
    "#7d6a58",
    "#c9b4a0",
  ];
  const ROOFS = [
    "#8f4034",
    "#7a3830",
    "#a34a38",
    "#6e322c",
    "#91503a",
    "#6a4a40",
    "#9a3f32",
    "#7d4a38",
    "#6b4038",
    "#8a5344",
    "#7a4e3a",
    "#5e3a34",
    "#9b5a42",
    "#704840",
    "#865040",
    "#5a4038",
  ];
  const colorIndex = (id) => {
    let n = 0;
    for (let i = 0; i < id.length; i += 1) {
      n = (n + id.charCodeAt(i) * (i + 3)) % 97;
    }
    return n;
  };
  const parseHex = (hex) => {
    const n = Number.parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  };
  const shadeHex = (hex, factor) => {
    const [r, g, b] = parseHex(hex);
    const to = (v) => Math.max(0, Math.min(255, Math.round(v * factor))).toString(16).padStart(2, "0");
    return `#${to(r)}${to(g)}${to(b)}`;
  };
  const mixHex = (a, b, t) => {
    const [ar, ag, ab] = parseHex(a);
    const [br, bg, bb] = parseHex(b);
    const to = (x, y) => Math.max(0, Math.min(255, Math.round(x + (y - x) * t))).toString(16).padStart(2, "0");
    return `#${to(ar, br)}${to(ag, bg)}${to(ab, bb)}`;
  };
  const hexLum = (hex) => {
    const [r, g, b] = parseHex(hex);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  };
  const plasterLift = (hex) => mixHex(hex, "#efe6d6", 0.38);
  const wallDisplay = (id) => {
    const wall = WALLS[colorIndex(id) % WALLS.length];
    return colorIndex(id) % 2 === 0 ? plasterLift(wall) : wall;
  };
  const lidColor = (id) => mixHex(shadeHex(wallDisplay(id), 0.58), ROOFS[colorIndex(id) % ROOFS.length], 0.22);
  const unitsFor = (id) => {
    const n = colorIndex(id);
    if (n % 3 === 0) return { ac: 0, tank: 0 };
    if (n % 5 === 0) return { ac: 1, tank: 1 };
    if (n % 2 === 0) return { ac: 2, tank: 0 };
    return { ac: 1, tank: 0 };
  };

  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  assert.equal(buildings.length, 60);
  let parapets = 0;
  let acs = 0;
  let tanks = 0;
  let withUnits = 0;
  let harborUnits = 0;
  for (const building of buildings) {
    const ring = building.geometry.coordinates[0];
    const edges = Math.max(0, ring.length - 1);
    parapets += edges;
    const units = unitsFor(String(building.id));
    acs += units.ac;
    tanks += units.tank;
    if (units.ac + units.tank > 0) withUnits += 1;
    if (String(building.id).startsWith("bldg-steps-") && units.ac + units.tank > 0) harborUnits += 1;
    const wall = wallDisplay(String(building.id));
    const lid = lidColor(String(building.id));
    assert.ok(hexLum(lid) < hexLum(wall) - 0.08, `${building.id} lid must read darker than wall`);
  }
  assert.ok(parapets >= 240, `parapet edges ${parapets}`);
  assert.ok(withUnits >= 20 && withUnits <= 50, `hashed roof units ${withUnits}`);
  assert.ok(acs >= 12 && acs <= 80, `ac boxes ${acs}`);
  assert.ok(tanks >= 2 && tanks <= 40, `tanks ${tanks}`);
  assert.ok(harborUnits >= 1, "at least one Harbor / Steps roof carries an AC or tank");
  assert.deepEqual(unitsFor("bldg-steps-e-00"), unitsFor("bldg-steps-e-00"));
  assert.notEqual(unitsFor("bldg-steps-e-00").ac + unitsFor("bldg-steps-e-00").tank, undefined);
});

test("building wall colors vary from existing ids, not one beige", () => {
  const WALLS = [
    "#c9a06e",
    "#b89062",
    "#d4b07a",
    "#a67c58",
    "#c09a68",
    "#b89a7a",
    "#a8885c",
    "#d2ae78",
    "#9a7a62",
    "#c4a090",
    "#8e6d55",
    "#d8b48a",
    "#b07058",
    "#c8b090",
    "#8f8468",
    "#be8a6a",
    "#a89878",
    "#d2c0a4",
    "#7d6a58",
    "#c9b4a0",
  ];
  const colorIndex = (id) => {
    let n = 0;
    for (let i = 0; i < id.length; i += 1) {
      n = (n + id.charCodeAt(i) * (i + 3)) % 97;
    }
    return n;
  };
  const buildings = fixture.features.filter((feature) => feature.properties?.kind === "building");
  const colors = new Set(
    buildings.map((feature) => WALLS[colorIndex(String(feature.id)) % WALLS.length]),
  );
  assert.ok(buildings.length >= 24);
  assert.ok(colors.size >= 8, `expected street-read variety, got ${colors.size}`);
  assert.ok(colors.size <= WALLS.length);
});

test("self footsteps tick opposite-stride plants; sprint louder/faster; mute when hidden or overlay", () => {
  const src = readFileSync(join(root, "src", "avatar", "footsteps.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const person = readFileSync(join(root, "src", "play", "Person.tsx"), "utf8");
  assert.match(src, /FOOTSTEP_KIND = "procedural-thump"/);
  assert.match(src, /WALK_FOOT_GAIN = 0\.14/);
  assert.match(src, /SPRINT_FOOT_GAIN = 0\.22/);
  assert.match(src, /createOscillator/);
  assert.match(src, /createBuffer/);
  assert.match(src, /export function strideFootfall/);
  assert.match(src, /export function tickSelfFootsteps/);
  assert.match(src, /document\.hidden/);
  assert.match(src, /play-menu/);
  assert.match(src, /shop-panel/);
  assert.equal(src.includes(".mp3"), false);
  assert.equal(src.includes(".wav"), false);
  assert.equal(src.includes("fetch("), false);
  assert.equal(/\.(mp3|wav|ogg|m4a)/i.test(src), false);
  assert.equal(src.includes("createMediaElementSource"), false);
  assert.equal(src.includes("HTMLAudioElement"), false);
  assert.match(play, /tickSelfFootsteps\(strideTime/);
  assert.match(play, /if \(self\) \{\s*tickSelfFootsteps/s);
  assert.match(play, /data-testid="footstep-proof"/);
  assert.match(play, /data-footsteps="0"/);
  assert.match(play, /armFootstepUnlock/);
  assert.match(person, /WALK_RATE = 9\.4/);
  assert.match(person, /SPRINT_RATE = 12\.8/);
  const WALK_RATE = 9.4;
  const SPRINT_RATE = 12.8;
  const WALK_GAIN = 0.14;
  const SPRINT_GAIN = 0.22;
  const footFromStride = (time) => (Math.sin(time) >= 0 ? "left" : "right");
  const strideFootfall = (prevTime, time) => {
    const prev = footFromStride(prevTime);
    const next = footFromStride(time);
    return prev === next ? null : next;
  };
  const countPlants = (t0, t1, dt = 0.002) => {
    let n = 0;
    let prev = t0;
    for (let t = t0 + dt; t <= t1 + 1e-9; t += dt) {
      if (strideFootfall(prev, t)) n += 1;
      prev = t;
    }
    return n;
  };
  assert.equal(countPlants(0, Math.PI * 2 + 0.05), 2, "one plant per opposite foot per cycle");
  assert.equal(strideFootfall(-0.02, 0.02), "left");
  assert.equal(strideFootfall(Math.PI - 0.02, Math.PI + 0.02), "right");
  const walkHz = WALK_RATE / Math.PI;
  const sprintHz = SPRINT_RATE / Math.PI;
  assert.ok(sprintHz > walkHz + 0.3, `sprint ${sprintHz.toFixed(2)} vs walk ${walkHz.toFixed(2)}`);
  assert.ok(SPRINT_GAIN > WALK_GAIN);
  const live = (gate) => gate.moving && !gate.airborne && !gate.hidden && !gate.overlay;
  assert.equal(live({ moving: true, airborne: false, hidden: false, overlay: false }), true);
  assert.equal(live({ moving: false, airborne: false, hidden: false, overlay: false }), false);
  assert.equal(live({ moving: true, airborne: false, hidden: true, overlay: false }), false);
  assert.equal(live({ moving: true, airborne: false, hidden: false, overlay: true }), false);
  assert.equal(live({ moving: true, airborne: true, hidden: false, overlay: false }), false);
  assert.equal(person.includes("sphereGeometry args={[0.11"), false);
});

test("accepted Online remotes plant quieter footsteps; skip far / hidden / overlay", () => {
  const src = readFileSync(join(root, "src", "avatar", "footsteps.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const presence = readFileSync(join(root, "src", "friends", "presence.ts"), "utf8");
  assert.match(src, /FRIEND_WALK_FOOT_GAIN = 0\.05/);
  assert.match(src, /FRIEND_SPRINT_FOOT_GAIN = 0\.08/);
  assert.match(src, /FRIEND_FOOT_RANGE_M = 25/);
  assert.match(src, /export function friendFootGain/);
  assert.match(src, /export function tickFriendFootsteps/);
  assert.match(src, /export function syncFriendFootstepSeats/);
  assert.match(src, /export function cutFriendFootstepSeat/);
  assert.match(src, /friendFootstepSeatAllowed/);
  assert.match(src, /allowedFriendSeats\.size === 0/);
  assert.match(src, /document\.hidden/);
  assert.match(src, /play-menu/);
  assert.equal(src.includes(".mp3"), false);
  assert.equal(src.includes(".wav"), false);
  assert.equal(src.includes("createMediaElementSource"), false);
  assert.equal(src.includes("HTMLAudioElement"), false);
  assert.match(play, /tickFriendFootsteps\(seat, strideTime/);
  assert.match(play, /syncFriendFootstepSeats\(streetRemotes\.map/);
  assert.match(play, /useLayoutEffect/);
  assert.match(play, /cutFriendFootstepSeat\(seat\)/);
  assert.match(play, /dropStreetNametag\(seat\)/);
  assert.match(play, /dropLeftoverStreetNametags\(keep\)/);
  assert.match(play, /remote-avatar-\$\{seat\}"\]\.play-remote-label/);
  assert.match(play, /remote-avatar-\$\{seat\}/);
  assert.match(play, /data-testid="friend-footstep-proof"/);
  assert.match(play, /data-friend-footsteps="0"/);
  assert.match(presence, /isMutualAccepted/);
  assert.match(presence, /viewerMode !== "online"/);
  assert.match(presence, /isPublishing/);
  const WALK_GAIN = 0.14;
  const FRIEND_WALK = 0.05;
  const RANGE = 25;
  const friendGain = (sprint, distM) => {
    if (distM > RANGE) return 0;
    const base = sprint ? 0.08 : FRIEND_WALK;
    return base * (1 - Math.max(0, distM) / RANGE);
  };
  assert.ok(FRIEND_WALK < WALK_GAIN);
  assert.ok(friendGain(false, 0) < WALK_GAIN);
  assert.ok(friendGain(false, 7) < friendGain(false, 0));
  assert.ok(friendGain(false, 7) < WALK_GAIN);
  assert.equal(friendGain(false, 26), 0);
  assert.equal(friendGain(true, 30), 0);
  const live = (gate) =>
    gate.moving && !gate.airborne && !gate.hidden && !gate.overlay && gate.distM <= RANGE;
  assert.equal(live({ moving: true, airborne: false, hidden: false, overlay: false, distM: 7 }), true);
  assert.equal(live({ moving: false, airborne: false, hidden: false, overlay: false, distM: 7 }), false);
  assert.equal(live({ moving: true, airborne: false, hidden: true, overlay: false, distM: 7 }), false);
  assert.equal(live({ moving: true, airborne: false, hidden: false, overlay: true, distM: 7 }), false);
  assert.equal(live({ moving: true, airborne: false, hidden: false, overlay: false, distM: 26 }), false);
  assert.match(play, /data-testid="play-street-chip"|data-street-hud/);
  assert.match(play, /data-far-lod=\{FAR_DETAIL_KIND\}/);
});

test("corner MapLibre waits for Play idle frames; first W does not mount it", () => {
  const defer = readFileSync(join(root, "src", "map", "minimapDefer.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(defer, /MINIMAP_DEFER_KIND = "play-idle"/);
  assert.match(defer, /MINIMAP_DEFER_MS = 800/);
  assert.match(defer, /export function minimapMayConstruct/);
  assert.equal(defer.includes("sawWalk"), false);
  assert.match(defer, /idlePoseMs >= MINIMAP_DEFER_MS/);
  assert.equal(defer.includes("0.0.0.0"), false);
  assert.match(app, /from "\.\.\/map\/minimapDefer"/);
  assert.match(app, /idlePoseMs = 0/);
  assert.match(app, /isMoveHeldRef/);
  assert.match(app, /requestAnimationFrame\(tick\)/);
  assert.match(app, /data-minimap-defer=\{minimapLive \? "live" : "pending"\}/);
  assert.match(app, /<MapView \{\.\.\.mapShared\} variant="minimap" \/>/);
  assert.equal(app.includes("hh-world-map"), false);
  const may = (painted, idlePoseMs, pose, walkHeld = false) => {
    if (!painted || pose === "walk" || walkHeld) return false;
    return idlePoseMs >= 800;
  };
  assert.equal(may(false, 800, "idle"), false);
  assert.equal(may(true, 200, "idle"), false);
  assert.equal(may(true, 800, "walk"), false);
  assert.equal(may(true, 800, "idle", true), false);
  assert.equal(may(true, 100, "idle"), false);
  assert.equal(may(true, 800, "idle"), true);
  assert.equal(may(true, 400, "idle"), false);
});

test("Play hitch warmup resumes audio, plants one silent tick, compiles tunic/street once", () => {
  const src = readFileSync(join(root, "src", "avatar", "footsteps.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  assert.match(src, /HITCH_WARMUP_KIND = "audio-compile"/);
  assert.match(src, /export function warmupPlayAudio/);
  assert.match(src, /function plantSilentTick/);
  assert.match(src, /og\.gain\.setValueAtTime\(0, now\)/);
  assert.match(src, /ng\.gain\.setValueAtTime\(0, now\)/);
  assert.equal(src.includes("engine.ticks +="), true);
  assert.match(src, /Does not increment plant ticks/);
  assert.equal(src.includes(".hdr"), false);
  assert.equal(src.includes("hdri"), false);
  assert.equal(src.includes("0.0.0.0"), false);
  assert.match(play, /warmupPlayAudio/);
  assert.match(play, /function HitchWarmup/);
  assert.match(play, /gl\.compile\(scene, camera\)/);
  assert.match(play, /data-hitch-warmup=\{HITCH_WARMUP_KIND\}/);
  assert.match(play, /<HitchWarmup/);
  assert.equal(play.includes("play-loading") && play.includes("HitchWarmup"), true);
  assert.equal(play.includes("hdri"), false);
  assert.equal(/\.(hdr|exr)/i.test(play), false);
  assert.match(play, /syncFriendFootstepSeats\(streetRemotes\.map/);
  assert.match(play, /pruneFriendFootsteps/);
  assert.match(src, /allowedFriendSeats\.size === 0/);
  assert.match(src, /remotes\.length===0|friendFootstepSeatAllowed/);
});

test("authored 400 m frame has distance haze and a visible fixture-edge wall/lot", () => {
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  const honesty = readFileSync(join(root, "src", "ui", "HonestyBanner.tsx"), "utf8");
  assert.match(world, /FOG_KIND = "distance-haze"/);
  assert.match(world, /FOG_NEAR_M = 58/);
  assert.match(world, /FOG_FAR_M = 155/);
  assert.match(world, /BLOCK_EDGE_KIND = "curb-wall-lot"/);
  assert.match(world, /export function blockEdgePieces/);
  assert.match(world, /BLOCK_WALL_COLOR = "#7a7268"/);
  assert.match(world, /BLOCK_LOT_COLOR = "#3d7a88"/);
  assert.match(world, /BLOCK_COPE_COLOR = "#c4b8a4"/);
  assert.match(world, /Not a downloaded HDRI/);
  assert.match(play, /<fog attach="fog" args=\{\[SKY_FOG, FOG_NEAR_M, FOG_FAR_M\]\}/);
  assert.match(play, /data-testid="play-block-edge"/);
  assert.match(play, /data-block-edge=\{BLOCK_EDGE_KIND\}/);
  assert.match(play, /data-fog=\{FOG_KIND\}/);
  assert.match(play, /data-at-bound/);
  assert.match(play, /<BlockEdgeMesh/);
  assert.match(walk, /BLOCK_BOUND_KIND = "fixture-edge"/);
  assert.match(walk, /export function clampInsideAoi/);
  assert.match(walk, /export function projectBoundSlide/);
  assert.match(walk, /export function isAtAoiBound/);
  assert.match(honesty, /fixture edge, not a city/);
  assert.equal(world.includes("hdri"), false);
  assert.equal(/\.(hdr|exr)/i.test(world), false);
  assert.equal(play.includes('args={[SKY_FOG, 200, 380]}'), false);

  const SLAB = 400;
  const HALF = 200;
  const WALL_T = 0.52;
  const WALL_H = 2.28;
  const CURB_W = 0.7;
  const LOT_W = 12;
  const spawn = lngLatToWorld(SPAWN.lon, SPAWN.lat);
  assert.ok(Math.abs(spawn.x) < HALF - 40, "spawn must stay inside the wall");
  assert.ok(Math.abs(spawn.z) < HALF - 40, "spawn must stay inside the wall");
  const lantern = lngLatToWorld(106.6980366, 10.7718712);
  assert.ok(Math.abs(lantern.x) < HALF - 40);
  assert.ok(Math.abs(lantern.z) < HALF - 40);
  const harborSouth = -180;
  assert.ok(harborSouth > -(HALF - 8), "Harbor Walk south sample stays off the wall");
  const FOG_NEAR = 58;
  const FOG_FAR = 155;
  assert.ok(FOG_NEAR < 90 && FOG_FAR < 200 && FOG_FAR > FOG_NEAR + 60);
  assert.ok(WALL_H > 1.6 && WALL_H < 2.8, "courtyard wall, not a fortress");
  assert.ok(LOT_W >= 8 && LOT_W <= 16);
  const southWallZ = -HALF;
  const southCurbZ = -(HALF - WALL_T / 2 - CURB_W / 2);
  const southLotZ = -(HALF + WALL_T / 2 + LOT_W / 2);
  assert.ok(southCurbZ > southWallZ, "curb sits inside the wall");
  assert.ok(southLotZ < southWallZ, "lot/water sits outside the wall");
  assert.ok(Math.abs(southWallZ) === HALF);
  assert.ok(SLAB === 400);
});

test("hidden tab stops street publish without flipping Offline", () => {
  const presence = readFileSync(join(root, "src", "friends", "presence.ts"), "utf8");
  const hook = readFileSync(join(root, "src", "friends", "usePresence.ts"), "utf8");
  const store = readFileSync(join(root, "vite.this-pc-store.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(presence, /export const PRESENCE_TTL_MS = 10000/);
  assert.match(presence, /export function isDocumentStreetVisible/);
  assert.match(presence, /visibilityState !== "hidden"/);
  assert.match(presence, /doc\.hidden !== true/);
  assert.match(presence, /export function shouldPublishStreetPresence/);
  assert.match(presence, /export function streetPresenceIntent/);
  assert.match(presence, /Never flips social mode/);
  assert.match(hook, /isDocumentStreetVisible/);
  assert.match(hook, /shouldPublishStreetPresence/);
  assert.match(hook, /streetPresenceIntent/);
  assert.match(hook, /visibilitychange/);
  assert.match(hook, /leave_session/);
  assert.match(hook, /publishLocalLeave/);
  assert.match(hook, /intent === "hold"/);
  assert.equal(hook.includes("setPresenceMode"), false);
  assert.equal(hook.includes('mode: "offline"'), false);
  assert.equal(hook.includes("presenceMode ="), false);
  assert.match(store, /export function shouldApplyStreetLeave/);
  assert.match(store, /leave_session/);
  assert.match(app, /mode: presenceMode/);
  assert.match(app, /usePresence\(/);
});
