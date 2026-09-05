# Roadmap A–Z — nguồn thứ tự và nghiệm thu duy nhất

PLAN_SCOPE=hh-3d/hh-3d-2
PLAN_ROLE=CANONICAL_WP_ORDER_AND_ACCEPTANCE
PLAN_DATE=2026-09-05
EXECUTION_STATUS=PLAN_ONLY_NOT_STARTED
CURRENT_VALID_WP=H2-P0-01

Mọi hàng còn PLANNED. Duyệt bộ plan không đồng nghĩa ACCEPTED một WP triển
khai. Không dùng số checkbox của Web/Vault Fighters làm tiến độ ở đây.

## Quy tắc thực thi

- Một WP = một deliverable reviewable + một source manifest + một record.
  Worker không tick/đổi trạng thái; coordinator ghi PLANNED → IN_PROGRESS →
  CANDIDATE → ACCEPTED hoặc GAP. Không dùng DONE mơ hồ.
- Thực thi theo thứ tự bảng. Dependencies là tối thiểu về kỹ thuật, không
  mặc nhiên cho agent nhảy trước CURRENT_VALID_WP. Coordinator có thể giao
  phần độc lập để tránh chờ device/human bằng dispatch ghi rõ WP, dependency,
  file lease và vì sao an toàn; không được accept downstream thiếu gate upstream.
- Để tránh tooling chặn spike engine: sau P0-03, coordinator **nên dispatch
  P1-02 song song P1-01** trên scenes/scripts riêng; P1-03 cần P1-02, không
  cần toàn bộ tool P1-01. Bootstrap scene dùng generator T02. P1-01 vẫn phải
  ACCEPTED trước worker dùng semantic mutation trong P2. P3-01 foundation
  có thể dispatch sau P1-03 độc lập, nhưng final domain schema cần P2-03.
- `ALLOWED` dưới là trần đường dẫn dự kiến, tất cả nằm dưới root mới. Handoff
  phải thay bằng file cụ thể, không giao wildcard rộng cho worker.
- Mọi DoD dưới cộng Q00. Quality profile ghi test IDs cụ thể: Q03-A gameplay,
  Q03-R art, Q03-H human; Q04-L local, Q04-N impairment, Q04-C load, Q04-W1
  devices WAN, Q04-W2 humans WAN. Feature test trong mỗi WP là subset được
  liệt kê rõ dưới; Q03-H/Q04-W2 toàn hành trình chỉ bắt buộc ở P6-03 và release.
- Risky WP (authority/transactions/tool mutations/security/geo/release) cần
  hai Cursor critic đọc độc lập đúng hash. Routine WP một critic; coordinator
  vẫn quyết định. Mỗi candidate đổi source phải review lại hash mới.
- Target dates không bịa trước khi biết tốc độ/thiết bị. Mốc là exit gate,
  không dự đoán vài ngày sẽ xong game/MMO.

## Bảng theo dõi

| WP | Kết quả | Dependency | Trạng thái |
|---|---|---|---|
| H2-P0-01 | Toolchain/engine lock riêng và baseline | Owner yêu cầu bắt đầu | PLANNED |
| H2-P0-02 | Device/quality/content budget khóa | H2-P0-01 | PLANNED |
| H2-P0-03 | Project/bootstrap/test harness | H2-P0-02 | PLANNED |
| H2-P1-01 | Editor semantic tools tối thiểu | H2-P0-03 | PLANNED |
| H2-P1-02 | Multiplayer authority risk spike | H2-P0-03 | PLANNED |
| H2-P1-03 | Godot technical/performance decision gate | H2-P1-02 | PLANNED |
| H2-P2-01 | Character/camera/touch chơi được | H2-P1-03, H2-P1-01 | PLANNED |
| H2-P2-02 | Avatar/animation/emote pipeline | H2-P2-01 | PLANNED |
| H2-P2-03 | Câu cá/nhiệm vụ/sưu tầm Solo | H2-P2-02 | PLANNED |
| H2-P2-04 | Nhà/quầy mẫu và vòng chơi offline | H2-P2-03 | PLANNED |
| H2-P3-01 | API/schema/database/migrations | H2-P1-03, H2-P2-03 | PLANNED |
| H2-P3-02 | Identity/session/secure room admission | H2-P3-01 | PLANNED |
| H2-P3-03 | Gameplay server authoritative | H2-P3-02 | PLANNED |
| H2-P3-04 | Inventory/wallet transaction correctness | H2-P3-03 | PLANNED |
| H2-P4-01 | Friends/party/room/AOI visibility | H2-P3-04 | PLANNED |
| H2-P4-02 | Shop durable và giao dịch vật phẩm ảo | H2-P4-01 | PLANNED |
| H2-P4-03 | Nhà online/visit/persistence | H2-P4-02 | PLANNED |
| H2-P4-04 | Chat/report/block/moderation | H2-P4-03 | PLANNED |
| H2-P5-01 | Art/animation/audio content hoàn chỉnh | H2-P4-04 | PLANNED |
| H2-P5-02 | Streaming/UI/accessibility/game polish | H2-P5-01 | PLANNED |
| H2-P5-03 | Performance/device acceptance | H2-P5-02 | PLANNED |
| H2-P6-01 | Network capacity/chaos/security evidence | H2-P5-03 | PLANNED |
| H2-P6-02 | Private WAN alpha environment/ops | H2-P6-01 | PLANNED |
| H2-P6-03 | Human alpha/fun gate — v0.1 | H2-P6-02 | PLANNED |
| H2-P7-01 | Hoàn Hảo/geo contract, nguồn, quyền | H2-P6-03 | PLANNED |
| H2-P7-02 | Geo converter/versioned chunk pipeline | H2-P7-01 | PLANNED |
| H2-P7-03 | Place/shop/map integration | H2-P7-02 | PLANNED |
| H2-P8-01 | Một khu Việt Nam chơi được | H2-P7-03 | PLANNED |
| H2-P8-02 | Pilot capacity/cost/restore/rollback | H2-P8-01 | PLANNED |
| H2-P8-03 | Release candidate — v0.2 | H2-P8-02 | PLANNED |
| H2-P9-01 | Phát hành có ký/approval thật | H2-P8-03 | PLANNED |
| H2-P9-02 | Vận hành sau release và quyết định mở rộng | H2-P9-01 | PLANNED |

## P0 — Khóa môi trường, có nền để kiểm tra

### H2-P0-01 — Toolchain
ALLOWED: `tools/engine.lock.json`, launcher, `.gitignore` mới và evidence WP.
INPUT: D02/T01, git/process/cache inventory, release ledger.
BUILD: verify Godot 4.7.2 standard + matching templates/full commit/SHA256;
pin tool versions/path và room_server_os=Linux x86_64/headless; no clone/core edit;
isolate from VF. Nếu binary chưa
có, download official đã kiểm source/hash; không dùng bản latest tự trôi.
VERIFY: chạy `--version` bằng launcher, mismatch checksum/version fail-closed,
path có dấu/space; ghi baseline dirty và process owners không token.
DoD: lock đủ tái tạo, rollback binary cũ, không đổi cache/project khác. 2 critics.

### H2-P0-02 — Device và benchmark contract
ALLOWED: `contracts/quality-profile.json`, fixture specification, evidence.
BUILD: ghi SKU/OS/GPU/RAM, desktop/touch preset, render resolution, support
floor, lịch lấy thiết bị thực; khóa Q01-B/Q01-F/Q01-C/Q01-W/Q02 và test IDs
theo mỗi WP; ghi server OS/transport matrix dự kiến và engine bake-off recipe.
VERIFY: schema và matrix coverage; phân biệt target/observed/missing.
DoD: không có “60 FPS” chưa đo; người thiếu thiết bị không bị giả thành emulator.
Thiếu Android ghi gap thiết bị; local bootstrap vẫn có thể được coordinator
dispatch độc lập. P1-03 cần Windows + ít nhất một Android (Q01-B); P5-03 cần
đủ matrix Q01-F. Không thiếu máy nào cũng bị diễn thành cấm mọi việc local.

### H2-P0-03 — Bootstrap
ALLOWED: `game/project.godot`, entry scene/scripts, `tools/`, `tests/`, CI local.
BUILD: minimal launch/menu/quit, first-run tên/preset/skip tutorial skeleton
không login wall, dev build label trong diagnostics, input
actions, test runner, snapshot/run/user_dir isolation, headless server entry.
VERIFY: import, parse typed scripts, launcher error paths, real exit codes;
window launch and clean close. Tool bootstrapping theo T02, không tạo full game.
DoD: một lệnh logic check và một lệnh headed smoke documented, artifacts versioned.

## P1 — Bằng chứng kỹ thuật trước đầu tư nội dung

### H2-P1-01 — Editor tools
ALLOWED: `game/addons/hh_world_tools/`, `contracts/editor/`, tool tests.
BUILD: T03 minimal operations, loopback token/main-thread/lease/UndoRedo,
staged save rollback, readback ACK; owner toolbar run/pause/stop/read scene.
VERIFY: invalid/duplicate/stale/conflict/path escape/crash/retry/undo/redo;
owner edit giữa lease; editor/Play tách. Không test chỉ happy-path.
DoD: report có state before/after/undo hash; no partial write; 2 critics.

### H2-P1-02 — Network risk spike
ALLOWED: `game/scripts/net/`, throwaway test scenes, `contracts/net/`, tests.
BUILD: 1 dedicated + 2 client thật; move/emote interaction prototype, input
seq/server authority/snapshot và gộp edge input 60→30 Hz theo A03; transport
feasibility matrix Windows/Android/Linux (thiếu target ghi chưa verify; Windows
local proof là DoD spike, không khóa transport WAN). DEV_ONLY chỉ loopback.
VERIFY: Q04-L, invalid actor authority/session/input; stop/reconnect;
host captures separate process exits. Không triển khai MMO/backend toàn quốc.
DoD: stock pipeline đáp ứng basic contract; gaps security/export ghi rõ; 2 critics.

### H2-P1-03 — Technical gate giữ Godot
ALLOWED: benchmark scene/assets có nguồn, quality config, diagnostics/evidence.
BUILD: representative stylized plaza + rigged avatar load Q01, export release
Windows/Android, touch interaction proof; stock renderer options đo có kiểm soát.
VERIFY: Q01-B 0/8/32 + stress 64, Q01-C/Q01-W và thermal observation 10 phút,
raw timings; Android export và transport API/DTLS capability probe không
cần account giả đi qua mạng (có thể loopback trên thiết bị); actual secure
cross-device session nằm ở P3-02/P6-02. Tooling bootstrap smoke.
Không dùng primitive-only benchmark thay avatar load, không chờ toàn bộ T03.
DoD: Q01-B Windows + ít nhất 1 Android thật đạt, 2 critics. Fail → D02 tối đa hai vòng
tối ưu có hypothesis rồi ADR/fallback; không tự đổi engine/fork/hạ ngưỡng.

## P2 — Vòng chơi Solo hoàn chỉnh

### H2-P2-01 — Controller/camera
ALLOWED: player/camera/input scenes/scripts, collision fixture/tests.
BUILD: movement/camera/touch đầy đủ P03; movement interface dùng lại server.
VERIFY: Q03-A 30/60/120 cap, slopes/steps/walls/landing, menu focus, camera near
wall; real-input route desktop+Android. Fixture bổ trợ, không teleport sole proof.
DoD: control video + snapshots, no inversion/slide/camera clipping tuyến chuẩn.

### H2-P2-02 — Avatar pipeline
ALLOWED: avatar assets-source/import/animation/data và tests.
BUILD: style guide v1, font/stack đủ dấu tiếng Việt + license, hero rig,
wardrobe slots, 6 emote, LOD pipeline và catalog IDs; trước
bulk content có look-dev original đã review. Bắt đầu đủ biến thể để test mixing.
VERIFY: Q03-R look-dev/font runtime, GLB import, animation blending,
costume intersections, LOD pop/skin,
reset/equip/relaunch, reference/license manifest.
DoD: 1 hero đạt style guide, catalog pipeline tái lập; bulk content đến P5-01.

### H2-P2-03 — Activity loop
ALLOWED: activity/quest/collection UI+data/scripts, Solo save/tests.
BUILD: câu cá nguyên bản, tutorial+3 quest có skip/xem lại, 6 item, readable success/fail/retry,
authority interface local riêng Online; seed/attempt id có giới hạn.
VERIFY: chơi từ spawn đến nhận reward, spam/retry/cancel/fail, input devices,
save/reload/migration schema_version/future-version safe reject, không frame-based timing đổi theo FPS.
DoD: 10 phút có loop hiểu được; automated correctness và reviewer play notes.

### H2-P2-04 — Offline slice
ALLOWED: local house placement, catalog shop mẫu, menus/settings, slice tests.
BUILD: 1 phòng/12 catalog props (placeholder có plan thay), đặt/xoay/undo/save,
quầy demo và rõ Solo inventory/house namespace tách Online, vòng onboarding
Solo đầy đủ dưới 10 phút không login. Không import nhà Solo khi mời bạn.
VERIFY: Q03-A full offline route; relaunch 10 vòng/backup corrupted save;
ghi feedback người thật nếu có, thiếu không ký thay. Collect issues cho P5.
DoD: playable slice video và package; no geometry/placeholders claim final art.

## P3 — Authority và dữ liệu bền vững

### H2-P3-01 — API/persistence foundation
ALLOWED: `backend/`, HTTP/save schemas, migration/transaction tests.
BUILD: khóa Node LTS/framework/DB/schema tool exact versions; modular API,
Postgres migrations, command journal/outbox, dev config không secrets Git.
VERIFY: clean DB boot, repeat migrate, version conflict, rollback/restore trên
DB copy; restore sau deletion replay tombstones, API schema invalid input fail.
Chưa gọi service Hoàn Hảo thật.
DoD: reproducible local backend + backup rehearsal, 2 critics.

### H2-P3-02 — Identity và admission
ALLOWED: auth provider adapter, room registry/tickets, net auth client/server.
BUILD: OIDC/provider adapter có issuer/audience/expiry validation; dev identity
không thể bật trong release; secure transport/cert và nonce/replay handling.
VERIFY: Q05 auth attacks, expired ticket, full-room reservations, stale epoch,
TLS/DTLS failure, UDP-block fail-closed, secret scan; đăng nhập/logout/refresh/
reconnect thật; Solo cold-start không bắt login.
DoD: local provider integration có contract tests; production issuer/secret
chưa có ghi gap và chặn P6-02; cấm DEV_ONLY trên LAN/WAN. Khóa transport matrix
cho Windows/Android/Linux + ticket/channel binding trước capacity test; 2 critics.

### H2-P3-03 — Gameplay authority
ALLOWED: room gameplay/movement/activity code, protocol schemas, tests.
BUILD: input validation, prediction/reconciliation/interpolation, authority
activity outcomes; disconnect/timer handling; no Solo economy injection.
VERIFY: Q04-L/Q04-N at 100/200 ms profiles, reward spoof, speedhack/cooldown/
dup seq, 60→30 edge aggregation, room/API crash trước/sau award commit,
actual two-client activity route; reward chỉ ACK received sau API committed receipt.
DoD: authority independently readback, tolerance documented, 2 critics.

### H2-P3-04 — Economy correctness
ALLOWED: inventory/wallet/journal services and activity award integration.
BUILD: idempotent durable grants, optimistic concurrency, unique item IDs,
API post-commit receipts, transactional outbox.
VERIFY: Q05 concurrent grant/spend/crash/timeout/retry/outbox duplicates;
100 repeated commands không nhân item; Solo save manipulation rejected Online.
DoD: reconciliation query/test chứng minh balances/items invariant; 2 critics.

## P4 — Social, nhà và shop thật

### H2-P4-01 — Friends/party/AOI
ALLOWED: social APIs/UI, room router/AOI schemas/tests.
BUILD: accept/request/block, mode privacy, party 4/house 8/plaza 32 caps,
join reservation và visibility hysteresis; direct interact mutual awareness.
VERIFY: Q04-L/Q04-N + join room full/blocked/private; reconnect reservation
30 s/actor TTL 10 s/party all-or-none reservation; race invite/logout; hidden peer
không lộ transform qua API; priority không phá cap/block.
DoD: 2 client + observer adversarial route, no ghost >TTL; 2 critics.

### H2-P4-02 — Shops
ALLOWED: shop API/UI/data, catalog transaction tests.
BUILD: 1 quầy/6 slots, draft/publish/hide/stock/version, display-only hoặc
soft-currency buy, owner offline vẫn tồn tại. Không real marketplace orders.
VERIFY: actor UI publish→logout→B view/buy; duplicate click/retry, race last item,
forged price/owner, hidden draft, failed payment rollback.
DoD: receipt + DB readback + player video + Q05; 2 critics.

### H2-P4-03 — House online
ALLOWED: placement durable/visit/permissions APIs and scenes.
BUILD: validate catalog/ownership/bounds/quotas; save layout version; party
invite/private visit, crash-safe load. Không visit nhà Solo/import local placement.
No visitors edit owner's house.
VERIFY: undo/save/rejoin/readback; 2 writer conflicts; blocked invite; stale
catalog asset; malicious transform; 10 enter/leave memory loops.
DoD: durable layout same semantic hash; safe conflict; 2 critics.

### H2-P4-04 — Communication/moderation
ALLOWED: chat/report/block/rate limit services/UI/admin tools scoped new project.
BUILD: text length/normalize, room chat, mute/block/report queue, operator
hide/suspend audit, limits. Chat off before control path works; preset emotes remain.
VERIFY: spam/bypass Unicode/oversized payload, blocked chat/history/lookup,
report to operator action to affected client; operator privileges least privilege.
DoD: technical flow tested; policies/real staffing remain P6-02; 2 critics.

## P5 — Chất lượng hình ảnh và mượt

### H2-P5-01 — Final content pass
ALLOWED: original assets/import/content catalogs/style guide updates từ P2-02.
BUILD: đủ P03 3 avatar presets/6 outfits/6 emotes/12 furniture/6 collectible
items, original plaza landmarks, ambient/SFX/music with manifests.
VERIFY: Q03-R on devices, LOD/rig/font/audio pooling, license closure,
no copyrighted reference assets; no placeholder counted final.
DoD: runtime art package 6 angles+video, signed critic notes (agent, not human owner).

### H2-P5-02 — Polish/streaming/accessibility
ALLOWED: chunk loading/pools/UI/settings/onboarding diagnostics.
BUILD: async resource loading/loading UI, shader first-use strategy, pooling,
safe area/text scale/touch focus/contrast, reconnect/error/empty states.
VERIFY: Q03-A/Q03-R + Q01-C first movement/menu/equip/house; interrupt load,
context/background/foreground; no unbounded growth.
DoD: playable package no technical banners in primary flows; repro each fixed hitch.

### H2-P5-03 — Device/performance acceptance
ALLOWED: focused performance fixes + benchmark/config/tests in explicit leases.
BUILD: profile fixes only measured bottlenecks; no unrelated gameplay changes.
VERIFY: Q01-F/Q02 with final content and Q03-A/Q03-R regression; Windows+Android
matrix, 20-minute thermal, memory loops, 32 avatar worst-case/64 stress labels.
DoD: 2 critics same final hash. Missing device/slow frames = GAP, not “probably PASS”.
Sau hai lượt tối ưu thất bại → D02 ADR scope/renderer, không hạ threshold để tick.

## P6 — v0.1 closed alpha

### H2-P6-01 — Load/chaos/security
ALLOWED: load clients/tests, focused server/API fixes, evidence.
BUILD: real network synthetic clients distinct from render dummies, metric
capture, reconnect/failure/rollback scenarios; room caps enforced.
VERIFY: Q04-L/Q04-N/Q04-C 32 connected/60-minute soak trên đúng Linux server
và transport khóa ở P3-02, impaired network, capacity bytes/cost,
Q05 transaction/adversarial regression, cold process exits/leftovers.
DoD: 32 đạt Q04-C và công bố config. Cap thấp hơn phải qua decision thay scope
của owner + sửa contract + đo lại, không tick 32 bằng kết quả 16. 2 critics.

### H2-P6-02 — Private WAN setup
ALLOWED: deployment templates/runbooks/config schema under new backend/tools;
runtime external actions only to approved environment with actual credentials.
BUILD: private allowlist environment, TLS/key rotation/backup/alert/drain,
invite adult testers, operator moderation/privacy/retention plan; no public URL listing.
VERIFY: Q04-W1 devices/different real networks, secure login/join, restore sau
account deletion không resurrect và alert
drill; secret/scope/cost approvals only where needed after review package ready.
DoD: operational private environment documented, real operator designated;
issuer/tickets thực + secure channel, không fixture DEV_ONLY; thiếu credentials
thực thì GAP, không mở WAN bằng local auth.
not a claim human fun gate has passed. 2 critics.

### H2-P6-03 — Human acceptance v0.1
ALLOWED: feedback/evidence, focused issue fixes via new source hashes/reviews.
BUILD: chuẩn bị test scripts/consent/5 người onboarding và 8 người adult WAN,
invites/operator và capture; nhóm có thể overlap, không giả tên.
VERIFY: Q03-H + Q04-W2 8-person/30-minute WAN social session, Q03-A/Q03-R
regression, device coverage Q01-F, report/block/shop/item/reconnect observed;
feedback anonymized.
DoD: thresholds met and critical issues closed, actual human records not agent
substitutes. Coordinator declares v0.1 closed alpha only with 2 critic review
of evidence. Missing humans remains UNVERIFIED, not fictitious names.

## P7 — Địa lý thật sau gameplay

### H2-P7-01 — Data/integration contract
ALLOWED: `geo/` contracts/manifests/tests, read-only API integration documentation.
BUILD: G01–G04 fixture and Hoàn Hảo adapter schema; verify actual provider/API
availability with permission, source/license/attribution/refresh/cost decision,
one VN pilot polygon, source data acquisition bound.
VERIFY: unknown fields/IDs/CRS, offline provider behavior, license matrix;
review rights before actual dataset acquire, no Google/reference package rip.
DoD: approved source+scope; missing rights/provider → keep authored game usable;
2 critics. Do not edit production Hoàn Hảo services from this WP.

### H2-P7-02 — Converter/chunks
ALLOWED: `geo/` converter/fixtures/manifests and `game/` chunk loader interface.
BUILD: WGS84→local meters, approved acquire limited data, roads/buildings/height
confidence, nav/collision authored adjustments, content hashes/IDs/tombstones.
VERIFY: Q06 roundtrip/seams/anchor migrations; reproducible artifact generation,
diff old/new package, offline input tests; no full-country import.
DoD: versioned pilot package with lineage and rollback, 2 critics.

### H2-P7-03 — Hoàn Hảo adapter
ALLOWED: new adapters for places/marketplace directory/identity link/map UI.
BUILD: read-only approved integration first; real place/shop mapping distinct
game inventory; cached freshness/error labels; map/index separate from simulation.
VERIFY: schema contract, permission/rate/timeout/offline, listing owner absent,
deleted/relocated place, linking account with consent and collision-free IDs.
DoD: actual provider evidence where available; fixture-only adapters labeled;
no write into old service without new scope grant. 2 critics.

## P8 — v0.2 pilot Việt Nam

### H2-P8-01 — Playable Vietnam district
ALLOWED: pilot content/anchors/game packages and scoped gameplay integration.
BUILD: one approved VN district resembling real topology with stylized art,
gameplay continuity, safe spawn/nav and house/shop anchors; dataset credits.
VERIFY: Q03-A/Q03-R/Q06 end-to-end walk/activity/shop/travel/map; real vs authored
accuracy labels; camera/physics close to origin; geometry update preserves owner data.
DoD: gameplay still fun; no “1:1 all Vietnam” claim; 2 critics.

### H2-P8-02 — Pilot capacity/ops
ALLOWED: new scope load/ops scripts, tuning leases, release evidence.
BUILD: multi-room orchestration/admission and measured cost scaling; seed
dispersed users and hotspot within caps; restore DB/world packages together.
VERIFY: Q04-L/Q04-N/Q04-C/Q04-W1/Q05/Q06 on pilot, bounded CCU test with config, room full/party
overflow, network egress and storage cost, backup restore/drain/update rollback.
DoD: release cap based on measured headroom and operator capacity, no arithmetic
CCU extrapolation; 2 critics. Seamless cell sharding still outside this WP.

### H2-P8-03 — Release candidate
ALLOWED: build/export/QA manifests, release docs/credits/policy drafts.
BUILD: candidate Windows/Android packages, install/update/uninstall, saves,
protocol compatibility N-only/drain by default (N/N-1 chỉ nếu tested), Solo
save migration, changelog/support/known issues, dataset attribution.
VERIFY: Q00/Q01-F/Q02/Q03-A/Q03-R/Q03-H/Q04-L/Q04-N/Q04-C/Q04-W1/Q04-W2/
Q05/Q06, regression only once per unchanged candidate; human pilot feedback
on actual geographic package; secrets/license/brand checks.
DoD: no open release blocker; ready-for-approval package, 2 critics. iOS excluded
unless its own real build/device/store gate completed; do not fake parity.

## P9 — Release và sau release

### H2-P9-01 — Ký/phát hành
ALLOWED: approved distribution environment/metadata, local release evidence.
BUILD: all artifacts staged and reviewed first; obtain actual owner signing/
publish/brand/required policy decisions; use official tools with secrets protected.
VERIFY: install từ distribution thật, API/server version compatibility, smoke,
operator rollback switch; record artifact hash/channel/time.
DoD: actual authorized release and observed smoke; no claimed release from
upload preparation. Never invent E1–E4 approvals or human names. 2 critics.

### H2-P9-02 — Observe/improve
ALLOWED: ops reports/focused fixes/new proposals within scope.
BUILD: bounded post-release observation window (đề xuất 7 ngày), crash/tick/
latency/transaction/moderation/cost dashboards, rollback/incident runbook.
VERIFY: alerts exercised, real metrics with time range/consent; no always-on
monitor created without user request. Fix/review/hash/release follows same rules.
DoD: operating review and prioritized next roadmap. Only propose new gate for
more regions, 64+ room, seamless cells, voice, UGC upload, money, iOS/Web or
countrywide map with measured demand/cost. Không gọi chúng đã hoàn thành.
