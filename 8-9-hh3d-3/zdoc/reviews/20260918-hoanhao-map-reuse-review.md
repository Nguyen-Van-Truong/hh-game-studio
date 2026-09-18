# Hoan Hao map reuse assessment — 2026-09-18

AUTHORITY=0. Read-only research requested by the owner while the S91 diagnostic runs.
This is not a tools acceptance verdict, a VPS deployment audit, or authorization to
start HH World before GT-10. No sibling-project source, service, or deployment was changed.
Three scoped Astra xhigh audits covered frontend, backend, and the attached six proposals.
References below describe inspected working-tree code, not a frozen deployment manifest.

## Conclusion

The quoted agent is substantially correct: Hoan Hao already has a useful open-map
stack. Reuse its geographical storage, authored features, POIs and publication
patterns where the data rights and quality are established. A map renderer or
PMTiles file is not a complete 3D-world generator, nor proof of a working live VPS.

## Source findings and qualifications

Sibling source root: `D:/dataDiskD/intellji/hoanhaosocial/hoanhaonew-20-6-2025/hoan-hao`.
Paths in this table are relative to that root; line numbers are audit-time references.

| Claim | Result and evidence |
| --- | --- |
| MapLibre renders the maps | Supported in main frontend `fe-hoan-hao/src/features/map/pages/MapPage.tsx:2539` and admin `admin-fe/src/components/map/MapFeatureCanvas.tsx:301`. |
| OpenFreeMap is the default | Qualified: frontend primarily requests LocationService `/map/style.json` (`fe-hoan-hao/src/features/map/config/mapProviders.ts:140`). Public OpenFreeMap Liberty is its fallback (`:153`); backend base-style default is also OpenFreeMap (`locationservice-rust/src/config.rs:156`). The actual deployed selection remains unverified. |
| PMTiles is supported | Yes. Backend selects bundled Protomaps style when `MAP_PMTILES_URL` is configured (`locationservice-rust/src/service/map_service.rs:297`); frontend has an explicit PMTiles override (`mapProviders.ts:157`) and protocol support (`mapStyle.ts:425`). This is configuration selection, not a live health check. A backend-supplied style can itself select PMTiles without a frontend override. |
| PostGIS is used | Actual spatial capability exists: extension migration `locationservice-rust/migrations/001_init.sql:4`, ward MultiPolygon `013_ward_boundaries.sql:31`, and MVT queries `src/repo/map_feature_repo.rs:1382`. Table support does not prove complete populated city coverage. |
| Nominatim may be unavailable on VPS2 | Deployment documentation says `RUN-DEGRADED (nominatim SKIP)` (`deployvps2/ENV-MAPPING.md:614`). Unset configuration does not disable all geocoding: URL defaults to localhost:8095 (`locationservice-rust/src/config.rs:121`); forward lookup has a circuit breaker and local fallback (`src/service/geocode_service.rs:655`). Reverse enrichment defaults off. No running VPS was inspected. |
| Imported streets are only points | Correct for `street_service.rs:274,350`: Overpass `out center tags` and center coordinates, not complete road polylines. Do not broaden this to all backend data: separate authored `map_features` supports line roads and polygon buildings (`migrations/022_map_features_authoring.sql:53`). Existing coverage and usable 3D heights remain unverified. |
| Tile worker creates shop clusters | Correct: `map-tile-builder-worker/src/main.rs:519,589,685` groups active shop pins, emits point GeoJSON, generates layer `shop_clusters`, and converts it to PMTiles. It does not create 3D roads/buildings. |
| Fully self-hosted | Not established. Frontend glyph URLs include Protomaps GitHub Pages (`mapStyle.ts:419,821`); sprite localization preserves some external atlases (`:367`). Source fallback remains external. Local fonts, sprites, fallback and cache behavior all need checking for a self-hosting claim. |
| Google Maps only opens external directions | The inspected path creates an outbound directions link (`mapFeatureLayers.ts:445`); inspected map directories/manifests did not show a Google Maps rendering SDK. This is not a repository-wide absence proof. |

Provenance fields exist (`022_map_features_authoring.sql:87`), but this audit has
not established a complete licensed/quality-checked HH World dataset. Backend
PMTiles source replacement constructs a new object without retaining the old
source attribution (`map_service.rs:432`). Frontend provider attribution is
configured separately (`mapProviders.ts:143,167,182`). Effective visible attribution
for each deployed branch is still unverified; this is a follow-up check, not a
conclusion that attribution is absent in production.

## Public documentation checked

- [OpenFreeMap](https://openfreemap.org/): public service is offered free, including commercial use; it does not promise an SLA. Self-hosting is possible. Attribution still applies.
- [PMTiles](https://docs.protomaps.com/pmtiles/): a read-only tiled archive accessed with HTTP range requests. Publishing changed contents means rewriting the archive. Storage, requests and egress can still cost money. Keep mutable player/shop state in a database, not this archive.
- [Protomaps basemap layers](https://docs.protomaps.com/basemaps/layers): the basemap selects and simplifies source data; buildings can be merged at lower zooms. Inference: rendered basemap tiles should not automatically be treated as authoritative, complete geometry for constructing game streets and buildings.
- [Nominatim public-service policy](https://operations.osmfoundation.org/policies/nominatim/): the public OSMF endpoint has an application-wide one-request-per-second ceiling and other restrictions, including no client autocomplete. These are not the rules for every independently hosted Nominatim instance. OpenFreeMap availability does not imply unlimited geocoding service.
- [OSM copyright/licensing](https://www.openstreetmap.org/copyright): ODbL and attribution obligations need to be preserved and assessed for the actual data transformation/publication. This is not a conclusion that all game source code must be open.
- [Vietnam source extracts](https://download.geofabrik.de/asia/vietnam.html): an available regional OSM input, subject to checking the selected area's coverage and provenance. No extract was downloaded during the measurement.
- [Godot 3D import formats](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html): glTF/GLB is a supported route from Blender. Import support is not proof of gameplay, navigation, networking or performance.

## Recommended reuse boundary

When the game plan reaches its existing geo work, export a bounded, versioned
set of roads, footprints, water and permitted POIs from suitable source data or
PostGIS; record missing height/geometry and any authored approximations. Apply a
reusable Vietnamese-building kit in Blender, publish GLB, then implement and
verify collision, navigation, interactions, streaming and performance in Godot.
MapLibre/PMTiles can continue serving the world-selection map. Player authority,
progress and shop changes remain separate server/database concerns.

Keep the existing authored playable-neighborhood milestone ahead of geo expansion.
One playable 256–400 m area with an enjoyable loop is a useful first product
proof. It does not establish a whole city, a finished multiplayer game or an
end-to-end general game-authoring agent. Blender supplies content; Godot supplies
the running game. For a 2D fighter, Blender is optional unless its asset workflow
adds value; a browser release also requires a distinct Web target and tests.

## Attached six proposals versus current plans

The attachment is a proposal, not a replacement for the two authoritative plans.

1. **Authoring capabilities:** a real tooling gap, already documented by tools plan lines 1036–1061. Game controller/avatar/activity/final art work is already planned. Fill missing public capabilities through scoped, versioned change requests; do not claim the box fixture proves general game creation.
2. **Novel brief, separate 2D/3D and Web proof:** tools already test a brief-to-fixture/play/repair loop (lines 294,801). A new game outside that fixture and Web support are additional scope, not current failed GT requirements.
3. **Earlier human playtest:** useful product-risk reduction. Game plan line 1470 currently makes early feedback optional; required small usability sessions occur at P6-03. Making an earlier session mandatory changes the game dependency/DoD; it is not a GT-06 fix or proof of retention.
4. **Cooperative objective:** social rooms, party, chat and adjacent fishing exist in the plan. Shared contribution/reward gameplay is a new product hypothesis requiring its own authority/reward contract, not an existing omitted checkbox.
5. **Early geo cost pilot:** bounded geometry, a modular kit and 256–400 m areas already exist (game lines 785,808,1800), intentionally after authored alpha. Measuring manual cleanup hours and reuse cost for a second area would improve planning; moving converter implementation earlier changes scope/order.
6. **Cost ceilings and demand-led scale:** infrastructure/model/CI costs and approval before paid resources are already covered. Content unit costs and concrete monetary ceilings still need real inputs. Current data gate is **max(10M, 2×90-day forecast)**, not permission to test fewer than 10M when forecast is smaller. Do not quietly lower it.

No new GT gates, game implementation, test reruns, or scope expansion were created
by this review. Current GT-06 work remains diagnosing the S86 ObjectDB change,
with S91 excluded from acceptance datasets. Reuse unchanged functional evidence;
repair metadata from preserved raw data when possible; only rerun affected work.
