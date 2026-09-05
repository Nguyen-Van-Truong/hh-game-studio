export type Place = {
  id: string;
  name: string;
  summary: string;
  lon: number;
  lat: number;
  approx: true;
  acquired_at: string;
  accuracy_class: "authored";
  authored_or_source: "authored";
  geometry_confidence: string;
  height_confidence: string;
  height_m: number | null;
  honesty: string;
};

export type WorldManifest = {
  display_name: string;
  aoi_label: string;
  center: { lon: number; lat: number };
  extent_m: { east_west: number; north_south: number };
  bbox: { west: number; south: number; east: number; north: number };
  acquired_at: string;
  generated_at: string;
  published_at: string;
  fresh_until: string;
  stale_after: string;
  accuracy_class: string;
  authored_or_source: string;
  source_hash: string;
  artifact_hash: string;
  honesty: string[];
};

export type Bookmark = {
  v: 1;
  id: string;
  savedAt: string;
};

export type GeoFeatureProps = {
  id?: string;
  kind?: string;
  name?: string;
  display_name?: string;
  summary?: string;
  acquired_at?: string;
  accuracy_class?: string;
  authored_or_source?: string;
  geometry_confidence?: string;
  height_confidence?: string;
  height_m?: number | null;
  honesty?: string;
};

export type GeoFeature = {
  type: "Feature";
  id?: string | number;
  geometry: {
    type: string;
    coordinates: unknown;
  };
  properties?: GeoFeatureProps | null;
};

export type FeatureCollection = {
  type: "FeatureCollection";
  features: GeoFeature[];
  bbox?: number[];
  hh_world?: {
    center?: [number, number];
  };
};
