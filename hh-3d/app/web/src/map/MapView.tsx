import { useEffect, useMemo, useRef } from "react";
import maplibregl, { GeoJSONSource } from "maplibre-gl";
import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AvatarState } from "../avatar/walk";
import type { FeatureCollection, Place } from "../contracts/types";
import { isStreetFriend, type VisibleFriend } from "../friends/presence";
import type { SeatId } from "../friends/seats";
import { DEMO_SEATS } from "../friends/seats";
import type { Shop } from "../shops/types";
import { tunicShirtForSeat } from "../play/Person";
import {
  MINIMAP_LANE_KIND,
  MINIMAP_SHOP_KIND,
  STREET_HUD_EMPTY,
  countMinimapHudLanes,
  minimapHudLaneCollection,
  minimapHudLanesFromCollection,
  minimapStreetShopMarks,
  stallColorForShop,
  worldFromCollection,
} from "../play/world";
import { AOI_CENTER, isLocalUrl } from "./aoi";

function canvasWebglOk(): boolean {
  const canvas = document.createElement("canvas");
  return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
}

function makeAvatarEl(state: AvatarState, seat: SeatId): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "self-avatar";
  wrap.dataset.testid = "self-avatar";
  wrap.dataset.seat = seat;
  wrap.dataset.pose = state.pose;
  wrap.dataset.heading = String(Math.round(state.heading));
  wrap.dataset.lon = state.lon.toFixed(7);
  wrap.dataset.lat = state.lat.toFixed(7);
  wrap.dataset.body = "tunic-humanoid";
  wrap.dataset.tunic = tunicShirtForSeat(seat);
  wrap.setAttribute("aria-label", "Your character");
  wrap.innerHTML =
    '<div class="avatar-shadow"></div><div class="avatar-figure"><div class="avatar-head"></div><div class="avatar-torso"></div><div class="avatar-leg avatar-leg-l"></div><div class="avatar-leg avatar-leg-r"></div></div>';
  const torso = wrap.querySelector(".avatar-torso");
  if (torso instanceof HTMLElement) {
    torso.style.background = tunicShirtForSeat(seat);
  }
  return wrap;
}

function makeRemoteEl(friend: VisibleFriend): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "self-avatar remote-avatar";
  wrap.dataset.testid = `remote-avatar-${friend.seat_id}`;
  wrap.dataset.seat = friend.seat_id;
  wrap.dataset.pose = friend.pose;
  wrap.dataset.heading = String(Math.round(friend.heading));
  wrap.dataset.lon = friend.lon.toFixed(7);
  wrap.dataset.lat = friend.lat.toFixed(7);
  wrap.dataset.body = "tunic-humanoid";
  wrap.dataset.tunic = tunicShirtForSeat(friend.seat_id);
  wrap.setAttribute("aria-label", DEMO_SEATS[friend.seat_id].display_name);
  wrap.innerHTML = `<div class="avatar-name">${DEMO_SEATS[friend.seat_id].short_name}</div><div class="avatar-shadow"></div><div class="avatar-figure"><div class="avatar-head"></div><div class="avatar-torso"></div><div class="avatar-leg avatar-leg-l"></div><div class="avatar-leg avatar-leg-r"></div></div>`;
  const torso = wrap.querySelector(".avatar-torso");
  if (torso instanceof HTMLElement) {
    torso.style.background = tunicShirtForSeat(friend.seat_id);
  }
  return wrap;
}

function syncAvatarEl(el: HTMLElement, state: AvatarState): void {
  el.dataset.pose = state.pose;
  el.dataset.heading = String(Math.round(state.heading));
  el.dataset.lon = state.lon.toFixed(7);
  el.dataset.lat = state.lat.toFixed(7);
  el.classList.toggle("is-walk", state.pose === "walk");
}

type MapViewProps = {
  collection: FeatureCollection | null;
  places: Place[];
  shops: Shop[];
  selectedId: string | null;
  selectedShopId: string | null;
  extrusionOn: boolean;
  avatar: AvatarState;
  followAvatar: boolean;
  seat: SeatId;
  remotes: VisibleFriend[];
  onSelect: (id: string) => void;
  onSelectShop: (id: string) => void;
  onWebgl: (ok: boolean) => void;
  onBearing: (deg: number) => void;
  onCameraFreed: () => void;
  variant?: "world" | "minimap";
  activeLaneName?: string;
  activeLaneRole?: string;
};

export function MapView({
  collection,
  places,
  shops,
  selectedId,
  selectedShopId,
  extrusionOn,
  avatar,
  followAvatar,
  seat,
  remotes,
  onSelect,
  onSelectShop,
  onWebgl,
  onBearing,
  onCameraFreed,
  variant = "world",
  activeLaneName = "",
  activeLaneRole = "",
}: MapViewProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const shopMarkersRef = useRef<Marker[]>([]);
  const avatarMarkerRef = useRef<Marker | null>(null);
  const remoteMarkersRef = useRef<Map<string, Marker>>(new Map());
  const followRef = useRef(followAvatar);
  const onSelectRef = useRef(onSelect);
  const onSelectShopRef = useRef(onSelectShop);
  const onWebglRef = useRef(onWebgl);
  const onBearingRef = useRef(onBearing);
  const onCameraFreedRef = useRef(onCameraFreed);
  followRef.current = followAvatar;
  onSelectRef.current = onSelect;
  onSelectShopRef.current = onSelectShop;
  onWebglRef.current = onWebgl;
  onBearingRef.current = onBearing;
  onCameraFreedRef.current = onCameraFreed;

  const hudLanes = useMemo(
    () => (collection ? minimapHudLanesFromCollection(collection) : []),
    [collection],
  );
  const hudLaneCount = useMemo(() => countMinimapHudLanes(hudLanes), [hudLanes]);
  const hudLaneNames = useMemo(() => hudLanes.map((row) => row.name).join(","), [hudLanes]);
  const highlightOn = Boolean(activeLaneName);
  const playStreets = useMemo(
    () => (collection ? worldFromCollection(collection).streets : []),
    [collection],
  );
  const streetShopMarks = useMemo(
    () => (variant === "minimap" ? minimapStreetShopMarks(shops, playStreets) : []),
    [playStreets, shops, variant],
  );
  const streetShopIds = useMemo(
    () => streetShopMarks.map((row) => row.shop_id).join(","),
    [streetShopMarks],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return;
    }
    if (!canvasWebglOk()) {
      onWebglRef.current(false);
      return;
    }
    onWebglRef.current(true);

    const map = new maplibregl.Map({
      container: host,
      style: "/styles/local-style.json",
      center: AOI_CENTER,
      zoom: 16.4,
      pitch: 45,
      bearing: -18,
      minZoom: 15,
      maxZoom: 18,
      attributionControl: false,
      hash: false,
      transformRequest: (url) => {
        const origin = window.location.origin;
        if (!isLocalUrl(url, origin)) {
          throw new Error(`Blocked non-local map request: ${url}`);
        }
        return { url };
      },
    });
    if (variant !== "minimap") {
      map.addControl(
        new maplibregl.AttributionControl({
          compact: true,
          customAttribution:
            "Authored approximation · not OSM · not a live survey · HH World",
        }),
      );
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    }
    map.on("dragstart", () => {
      if (variant !== "minimap") {
        onCameraFreedRef.current();
      }
    });
    map.on("rotatestart", (event) => {
      if (event.originalEvent) {
        onCameraFreedRef.current();
      }
    });
    map.on("move", () => {
      onBearingRef.current(map.getBearing());
    });
    mapRef.current = map;
    onBearingRef.current(map.getBearing());

    return () => {
      for (const marker of markersRef.current) {
        marker.remove();
      }
      markersRef.current = [];
      for (const marker of shopMarkersRef.current) {
        marker.remove();
      }
      shopMarkersRef.current = [];
      avatarMarkerRef.current?.remove();
      avatarMarkerRef.current = null;
      for (const marker of remoteMarkersRef.current.values()) {
        marker.remove();
      }
      remoteMarkersRef.current.clear();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !collection) {
      return;
    }

    const apply = () => {
      const source = map.getSource("aoi");
      if (source instanceof GeoJSONSource) {
        source.setData(collection as GeoJSON.GeoJSON);
      } else {
        map.addSource("aoi", { type: "geojson", data: collection as never });
        map.addLayer({
          id: "aoi-fill",
          type: "fill",
          source: "aoi",
          filter: ["==", ["get", "kind"], "aoi"],
          paint: {
            "fill-color": "#c5d4c8",
            "fill-opacity": 0.35,
          },
        });
        map.addLayer({
          id: "park-fill",
          type: "fill",
          source: "aoi",
          filter: ["==", ["get", "kind"], "park"],
          paint: {
            "fill-color": "#8fbf86",
            "fill-opacity": 0.85,
          },
        });
        map.addLayer({
          id: "building-fill",
          type: "fill",
          source: "aoi",
          filter: ["==", ["get", "kind"], "building"],
          paint: {
            "fill-color": "#c4b8a8",
            "fill-opacity": 0.95,
            "fill-outline-color": "#8d8274",
          },
        });
        if (variant !== "minimap") {
          map.addLayer({
            id: "building-extrusion",
            type: "fill-extrusion",
            source: "aoi",
            filter: ["==", ["get", "kind"], "building"],
            paint: {
              "fill-extrusion-color": "#b7a896",
              "fill-extrusion-height": ["coalesce", ["get", "height_m"], 8],
              "fill-extrusion-base": 0,
              "fill-extrusion-opacity": 0.88,
            },
          });
        }
        map.addLayer({
          id: "street-walk",
          type: "line",
          source: "aoi",
          filter: ["==", ["get", "kind"], "street"],
          paint: {
            "line-color": "#d7d2c8",
            "line-width": 12,
          },
        });
        map.addLayer({
          id: "street-line",
          type: "line",
          source: "aoi",
          filter: ["==", ["get", "kind"], "street"],
          paint: {
            "line-color": "#3e4248",
            "line-width": 6,
          },
        });
        map.addLayer({
          id: "aoi-outline",
          type: "line",
          source: "aoi",
          filter: ["==", ["get", "kind"], "aoi"],
          paint: {
            "line-color": "#4d5b52",
            "line-width": 2,
            "line-dasharray": [2, 1],
          },
        });
      }
      if (variant !== "minimap" && map.getLayer("building-extrusion")) {
        map.setLayoutProperty(
          "building-extrusion",
          "visibility",
          extrusionOn ? "visible" : "none",
        );
        map.setLayoutProperty(
          "building-fill",
          "visibility",
          extrusionOn ? "none" : "visible",
        );
        map.setPitch(extrusionOn ? 45 : 0);
      } else if (variant === "minimap") {
        map.setPitch(0);
      }
    };

    if (map.isStyleLoaded()) {
      apply();
    } else {
      map.once("load", apply);
    }
  }, [collection, extrusionOn]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || hudLanes.length === 0) {
      return;
    }
    const data = minimapHudLaneCollection(hudLanes, activeLaneName) as GeoJSON.GeoJSON;
    const apply = () => {
      const source = map.getSource("hud-lanes");
      if (source instanceof GeoJSONSource) {
        source.setData(data);
      } else {
        map.addSource("hud-lanes", { type: "geojson", data });
        map.addLayer({
          id: "hud-lane-official",
          type: "line",
          source: "hud-lanes",
          filter: ["==", ["get", "role"], "official"],
          paint: {
            "line-color": "#16191e",
            "line-width": 5.4,
            "line-opacity": 0.96,
          },
        });
        map.addLayer({
          id: "hud-lane-inner",
          type: "line",
          source: "hud-lanes",
          filter: ["==", ["get", "role"], "inner"],
          paint: {
            "line-color": "#6a6256",
            "line-width": 2.15,
            "line-opacity": 0.94,
          },
        });
        map.addLayer({
          id: "hud-lane-active",
          type: "line",
          source: "hud-lanes",
          filter: ["==", ["get", "name"], activeLaneName || "__none__"],
          paint: {
            "line-color": "#2f7a4a",
            "line-width": ["match", ["get", "role"], "official", 7.1, 3.55],
            "line-opacity": 1,
          },
        });
      }
      if (map.getLayer("hud-lane-active")) {
        map.setFilter("hud-lane-active", ["==", ["get", "name"], activeLaneName || "__none__"]);
      }
    };
    if (map.isStyleLoaded()) {
      apply();
    } else {
      map.once("load", apply);
    }
  }, [hudLanes, activeLaneName]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || variant === "minimap") {
      return;
    }
    for (const marker of markersRef.current) {
      marker.remove();
    }
    markersRef.current = places.map((place) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className =
        place.id === selectedId ? "map-marker map-marker-active" : "map-marker";
      el.textContent = place.name;
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectRef.current(place.id);
      });
      return new maplibregl.Marker({ element: el })
        .setLngLat([place.lon, place.lat])
        .addTo(map);
    });
  }, [places, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    for (const marker of shopMarkersRef.current) {
      marker.remove();
    }
    if (variant === "minimap") {
      shopMarkersRef.current = streetShopMarks.map((shop) => {
        const el = document.createElement("div");
        el.className = "minimap-shop-mark";
        el.dataset.testid = `minimap-shop-mark-${shop.shop_id}`;
        el.dataset.shopId = shop.shop_id;
        el.dataset.name = shop.name;
        el.dataset.draw = "1";
        el.dataset.keepOut = "0";
        el.dataset.lon = shop.lon.toFixed(7);
        el.dataset.lat = shop.lat.toFixed(7);
        el.dataset.persistLon = shop.persistLon.toFixed(7);
        el.dataset.persistLat = shop.persistLat.toFixed(7);
        el.dataset.kind = MINIMAP_SHOP_KIND;
        el.style.background = stallColorForShop(shop);
        el.title = shop.name;
        return new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([shop.lon, shop.lat])
          .addTo(map);
      });
      return;
    }
    shopMarkersRef.current = shops.map((shop) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className =
        shop.shop_id === selectedShopId
          ? "map-marker shop-marker shop-marker-active"
          : "map-marker shop-marker";
      el.dataset.testid = `shop-marker-${shop.shop_id}`;
      el.dataset.shopId = shop.shop_id;
      el.dataset.lon = shop.lon.toFixed(7);
      el.dataset.lat = shop.lat.toFixed(7);
      el.dataset.source = shop.shop_id.startsWith("shop-local-") ? "local-demo" : "authored";
      el.textContent = `Shop · ${shop.name}`;
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectShopRef.current(shop.shop_id);
      });
      return new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([shop.lon, shop.lat])
        .addTo(map);
    });
  }, [shops, selectedShopId, streetShopMarks, variant]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || variant === "minimap") {
      return;
    }
    let marker = avatarMarkerRef.current;
    if (!marker) {
      const el = makeAvatarEl(avatar, seat);
      marker = new maplibregl.Marker({
        element: el,
        anchor: "bottom",
        pitchAlignment: "map",
        rotationAlignment: "map",
      })
        .setLngLat([avatar.lon, avatar.lat])
        .setRotation(avatar.heading)
        .addTo(map);
      avatarMarkerRef.current = marker;
    } else {
      const el = marker.getElement();
      syncAvatarEl(el, avatar);
      el.dataset.seat = seat;
      marker.setLngLat([avatar.lon, avatar.lat]);
      marker.setRotation(avatar.heading);
    }
    if (followRef.current) {
      map.setCenter([avatar.lon, avatar.lat]);
    }
  }, [avatar, seat]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || variant === "minimap") {
      return;
    }
    const streetRemotes = remotes.filter(isStreetFriend);
    const keep = new Set(streetRemotes.map((row) => row.seat_id));
    for (const [id, marker] of remoteMarkersRef.current) {
      if (!keep.has(id as SeatId)) {
        marker.remove();
        remoteMarkersRef.current.delete(id);
      }
    }
    for (const friend of streetRemotes) {
      let marker = remoteMarkersRef.current.get(friend.seat_id);
      if (!marker) {
        marker = new maplibregl.Marker({
          element: makeRemoteEl(friend),
          anchor: "bottom",
          pitchAlignment: "map",
          rotationAlignment: "map",
        })
          .setLngLat([friend.lon, friend.lat])
          .setRotation(friend.heading)
          .addTo(map);
        remoteMarkersRef.current.set(friend.seat_id, marker);
      } else {
        const el = marker.getElement();
        syncAvatarEl(el, friend);
        el.dataset.seat = friend.seat_id;
        el.dataset.lon = friend.lon.toFixed(7);
        el.dataset.lat = friend.lat.toFixed(7);
        marker.setLngLat([friend.lon, friend.lat]);
        marker.setRotation(friend.heading);
      }
    }
  }, [remotes]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !followAvatar) {
      return;
    }
    map.setCenter([avatar.lon, avatar.lat]);
  }, [followAvatar, avatar.lon, avatar.lat]);

  useEffect(() => {
    const map = mapRef.current;
    const selected = places.find((place) => place.id === selectedId);
    if (!map || !selected || followAvatar) {
      return;
    }
    map.easeTo({
      center: [selected.lon, selected.lat],
      zoom: Math.max(map.getZoom(), 16.6),
      duration: 400,
    });
  }, [places, selectedId, followAvatar]);

  return (
    <>
      <div
        ref={hostRef}
        className={variant === "minimap" ? "map-host map-host-mini" : "map-host"}
        data-testid={variant === "minimap" ? "hh-world-minimap" : "hh-world-map"}
        data-minimap-lanes={MINIMAP_LANE_KIND}
        data-minimap-official={String(hudLaneCount.official)}
        data-minimap-inner={String(hudLaneCount.inner)}
        data-minimap-extra={String(hudLaneCount.inner)}
        data-minimap-names={hudLaneNames}
        data-minimap-active={activeLaneName || STREET_HUD_EMPTY}
        data-minimap-highlight={highlightOn ? "1" : "0"}
        data-minimap-active-role={activeLaneRole}
        data-minimap-shops={MINIMAP_SHOP_KIND}
        data-minimap-shop-count={String(streetShopMarks.length)}
        data-minimap-shop-ids={streetShopIds}
        data-minimap-attrib={variant === "minimap" ? "caption" : "control"}
      />
      <ol hidden data-testid="hh-world-minimap-lanes" data-minimap-lanes={MINIMAP_LANE_KIND}>
        {hudLanes.map((lane) => (
          <li
            key={lane.id}
            data-testid={`minimap-lane-${lane.streetId}`}
            data-name={lane.name}
            data-role={lane.role}
            data-street-id={lane.streetId}
            data-active={lane.name === activeLaneName ? "1" : "0"}
          >
            {lane.name}
          </li>
        ))}
      </ol>
      {variant === "minimap" ? (
        <ol hidden data-testid="hh-world-minimap-shops" data-minimap-shops={MINIMAP_SHOP_KIND}>
          {streetShopMarks.map((shop) => (
            <li
              key={shop.shop_id}
              data-testid={`minimap-shop-${shop.shop_id}`}
              data-shop-id={shop.shop_id}
              data-name={shop.name}
              data-draw="1"
              data-keep-out="0"
              data-lon={shop.lon.toFixed(7)}
              data-lat={shop.lat.toFixed(7)}
              data-persist-lon={shop.persistLon.toFixed(7)}
              data-persist-lat={shop.persistLat.toFixed(7)}
              data-kind={MINIMAP_SHOP_KIND}
            >
              {shop.name}
            </li>
          ))}
        </ol>
      ) : null}
    </>
  );
}
