# Tích hợp bản đồ Hoàn Hảo sau gameplay

## G01 — Nguồn và phạm vi

Báo cáo owner cung cấp mô tả OSM → OpenFreeMap/Protomaps PMTiles, MapLibre,
PostGIS, Nominatim và dữ liệu shop/địa điểm riêng. Đây là **báo cáo kiến trúc**,
chưa là bằng chứng mọi service đang chạy/đủ dữ liệu/được phép dùng cho game.
H2-P7-01 kiểm tra contract/provider thực tế trước tích hợp, read-only trước.

Game trước: khu authored nguyên bản, fixtures local. Sau v0.1: một polygon
pilot Việt Nam rõ ràng, giới hạn dataset/bytes/date/refresh/cost; không tải
toàn quốc chỉ vì file PBF tồn tại. Chưa tích hợp thì UI không gọi là OSM thật.
Không dùng screenshots/tile raster Google để trace/bake làm cảnh.

OSM không tự cung cấp asset 3D nhà đẹp, indoor, collision, navmesh, shop inventory
hay toàn bộ POI chính xác. Cần converter + bộ art stylized + human/art review.
MapLibre là trình vẽ cho Web/map interface, không là nguồn game logic; PMTiles
là packaging, không tự thành collision/scene. Camera bbox không chứng minh
dataset chỉ Việt Nam; dùng polygon allowlist phù hợp và policy biển đảo có review.

## G02 — Hợp đồng spatial ngay từ đầu

- Lưu địa lý nguồn WGS84 lon/lat/height và source CRS/units/height datum.
  Physics dùng mét quanh local origin của chunk/instance, không Vector3 với
  longitude/latitude của cả nước. Không đặt tất cả scene xa origin hàng triệu m.
- Default chunk logical 256 m, tuning theo Q01; playable instance authored
  ~256–400 m. Geography scale sau có chunk streaming, vẫn room bounded.
- Chọn converter CRS/local tangent phù hợp khi có pilot; ghi thuật toán,
  axis mapping (Godot Y up), handedness, origin, rotation và roundtrip test.
  Tránh mix longitude/latitude thứ tự, degrees/meters, ellipsoid/terrain height.
- Không bật double precision/custom build làm mặc định. Nếu geographic extent
  vượt range đủ chính xác, ưu tiên chunk-local/origin rebase tại ranh an toàn.
  Double precision có chi phí/build implications; chỉ mở sau gap đo được.

`WorldPackage` phải có schema_version, world_id, release_id, chunk IDs/bounds,
origin/CRS, feature_id mapping, source/acquired/generated timestamps, units,
geometry/nav/collision/art hashes, accuracy/height confidence, attribution,
license reference, min_client_version và dependency hashes.

`Anchor` nội bộ: anchor_id, world_id, source_feature_refs[], transform local,
placement_policy, version, owner relation. `shop_id`/`house_id` không bằng
`osm_id`; source feature có thể xóa/chia/gộp mà tài sản player vẫn tồn tại.

## G03 — Pipeline chuyển đổi

1. Source registry + quyền sử dụng/attribution/refresh/cost và bounded acquire.
2. Snapshot bất biến với checksum; validate geometry/CRS/extent/size.
3. Normalize roads/water/building footprints và stable internal IDs.
4. Tạo local chunks; height thật nếu có nguồn hợp lệ, estimated có nhãn.
5. Sinh base geometry bằng kit art nguyên bản; material/LOD/culling budgets.
6. Collision/nav riêng, sửa lối đi/spawn/gameplay anchors bằng overlay authored.
7. Validate seams, continuity, accessibility, render/perf và artifact hashes.
8. Publish world package vào môi trường test; preserve old package for rollback.

Một đường OSM cho xe không tự là đường đi bộ hợp gameplay. Không tạo route
xuyên vùng nguy hiểm/riêng tư dựa trên completeness giả định. Không quảng cáo
game navigation là dịch vụ chỉ đường ngoài đời; đi trong game khác chỉ đường thật.

## G04 — Update không phá tài sản

Provider refresh tạo release mới, không sửa dataset dưới chân một live room.
Diff IDs/geometry, tombstones/remap/merge-split; anchors giữ hoặc chuyển theo
policy rõ (nearest approved surface trong radius có giới hạn, nếu không thì
quarantine chờ review, không tự xóa shop). Test với source feature xóa/chia/
di chuyển, failure giữa migration; layout/currency không bị mất.

Room đang chơi pin package cũ cho đến drain/transition; client/server handshake
world_release_id; CDN/content hash cache, timeout/incomplete chunk không spawn
player rơi vô hạn. Có authored fallback/lobby và error state gọn.
Rollback phải tương thích DB mapping + asset package, không rollback một phía.

## G05 — Hoàn Hảo integration

Adapters riêng: PlaceDirectory, MarketplaceDirectory, GeoProvider, IdentityProvider.
Contract test với fixtures trước; actual endpoints/auth/rate limits/error codes
được kiểm ở P7, không hardcode port từ report như production endpoint.

Mapping shop Hoàn Hảo → địa điểm/biển/quầy directory: nhãn “cửa hàng ngoài đời”,
read-only listing trước. Virtual shop → item game/soft currency. Hai loại có
ID namespace, quyền và UI khác nhau. Không trừ currency game để tạo đơn thật.
Login linking qua user consent + issuer identity, không match chỉ bằng tên.
Offline cached listings có age/stale/unavailable/empty khác nhau.

## G06 — License và gate pháp lý

Nguồn open không có nghĩa không điều kiện. Ledger ghi source, rights, ODbL/
attribution obligations, produced work vs derived database assessment, nơi
đặt credits và cách cung cấp dữ liệu nếu nghĩa vụ áp dụng. Không tự kết luận
license hết nghĩa vụ vì chỉ ship mesh. Policy map tile/geocoder service riêng
với license dữ liệu; self-host không tự vô hạn bandwidth/cost/coverage.

Việc phân loại legal, brand/địa điểm nhạy cảm và policy biển đảo phải có reviewer
thực trước public. Agent chuẩn bị artifact/ledger/diff để quyết định cụ thể,
không tự ký legal. License/cost/provider không đạt thì giữ game authored hoạt
động; tích hợp map là gap riêng, không quay lại phá gameplay đã nghiệm thu.
