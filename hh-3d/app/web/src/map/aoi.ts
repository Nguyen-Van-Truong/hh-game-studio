import { ringAabb, type BuildingPoly } from "../avatar/walk";
import type { FeatureCollection, GeoFeature, Place } from "../contracts/types";

export const AOI_CENTER: [number, number] = [106.698, 10.7725];

export const AOI_BBOX = {
  west: 106.6961711,
  south: 10.7707034,
  east: 106.6998289,
  north: 10.7742966,
};

export function isLocalUrl(url: string, origin: string): boolean {
  return (
    url.startsWith("/") ||
    url.startsWith("data:") ||
    url.startsWith("blob:") ||
    url.startsWith(origin)
  );
}

export function placesFromCollection(data: FeatureCollection): Place[] {
  const out: Place[] = [];
  for (const feature of data.features) {
    const place = placeFromFeature(feature);
    if (place) {
      out.push(place);
    }
  }
  return out;
}

export function buildingsFromCollection(data: FeatureCollection): BuildingPoly[] {
  const out: BuildingPoly[] = [];
  for (const feature of data.features) {
    if (feature.properties?.kind !== "building") {
      continue;
    }
    if (feature.geometry.type !== "Polygon") {
      continue;
    }
    const coords = feature.geometry.coordinates;
    if (!Array.isArray(coords) || !Array.isArray(coords[0])) {
      continue;
    }
    const ring: [number, number][] = [];
    for (const pt of coords[0] as unknown[]) {
      if (!Array.isArray(pt) || pt.length < 2) {
        continue;
      }
      const lon = pt[0];
      const lat = pt[1];
      if (typeof lon === "number" && typeof lat === "number") {
        ring.push([lon, lat]);
      }
    }
    if (ring.length >= 4) {
      const height =
        typeof feature.properties.height_m === "number" ? feature.properties.height_m : 8;
      const aabb = ringAabb(ring);
      out.push({
        id: String(feature.properties.id ?? feature.id ?? "bldg"),
        ring,
        height_m: height,
        name: feature.properties.display_name ?? feature.properties.name ?? "Building",
        aabb: aabb ?? undefined,
      });
    }
  }
  return out;
}

function placeFromFeature(feature: GeoFeature): Place | null {
  const props = feature.properties;
  if (!props || props.kind !== "place") {
    return null;
  }
  if (feature.geometry.type !== "Point") {
    return null;
  }
  const coords = feature.geometry.coordinates;
  if (!Array.isArray(coords) || coords.length < 2) {
    return null;
  }
  const lon = coords[0];
  const lat = coords[1];
  if (typeof lon !== "number" || typeof lat !== "number") {
    return null;
  }
  const id = String(props.id ?? feature.id ?? "");
  if (!id.startsWith("place-")) {
    return null;
  }
  return {
    id,
    name: props.display_name ?? props.name ?? id,
    summary:
      props.summary ??
      "Authored approximation. Not a surveyed place.",
    lon,
    lat,
    approx: true,
    acquired_at: props.acquired_at ?? "2026-09-03",
    accuracy_class: "authored",
    authored_or_source: "authored",
    geometry_confidence: props.geometry_confidence ?? "low",
    height_confidence: props.height_confidence ?? "unknown",
    height_m: typeof props.height_m === "number" ? props.height_m : null,
    honesty: props.honesty ?? "authored approximation; not 1:1",
  };
}
