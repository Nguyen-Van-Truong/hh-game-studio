# Kiến trúc client, multiplayer và dữ liệu

Thiết kế mặc định cho v0.1; API wire/schema cụ thể phải được khóa ở WP trước
khi triển khai dependent feature. Không gọi một sơ đồ là capacity đã chứng minh.

## A01 — Các thành phần

```text
Godot native client
  | HTTPS: account / room ticket / catalog / inventory / shop / friends
  v
Application API (modular monolith) ---- PostgreSQL
  | room registry + short-lived join ticket      | outbox / audit journal
  v                                             v
Godot dedicated room server(s)               background jobs
  ^ real-time authenticated transport           | geo later
  | inputs, snapshots, gameplay commands         v
clients                                   versioned world packages
```

Không microservice hóa mỗi feature lúc đầu. Không PostGIS/DB query mỗi frame.
Room server chốt gameplay và đề nghị reward idempotent; API transaction chốt
durable item/currency/shop. Client không có DB credentials hoặc quyền tự mint.

Stack dự kiến: typed GDScript client + headless room server cùng version;
TypeScript API với Node LTS, HTTP framework nhỏ và PostgreSQL; schema JSON cho
HTTP/authoring, schema binary versioned cho snapshot nếu số đo cần. Chốt tên/
version framework, package lock, migration tool và license ở H2-P3-01; không
để agent mỗi WP tự thay stack. Redis chỉ thêm khi registry/queue thật cần.
Account tích hợp issuer OIDC/provider qua adapter; local fixture identity được
gắn nhãn DEV_ONLY. Không tự viết password auth rồi gọi là production identity.

Room-server target mặc định **Linux x86_64 headless**, pin cùng engine;
Windows server chỉ là local spike. H2-P0-01 ghi OS/toolchain và H2-P6-01 đo
trên đúng OS/transport dự kiến deploy; không chuyển Linux/transport sau load
test rồi dùng lại số Windows. Container/VM/WSL cần thiết được chọn theo máy
có sẵn, không tự cài system feature ngoài quyền thực tế.

## A02 — Cây project tương lai (chưa scaffold trong lượt plan)

```text
hh-3d-2/
  AGENTS.md, zdoc/
  game/                 # một project Godot, client và headless entrypoint
    addons/hh_world_tools/
    scenes/, scripts/, data/, assets/
  backend/              # API, migrations, jobs, room registry
  contracts/            # command/net/http/save/geo schemas, compatibility tests
  assets-src/           # source art của mình, manifest license; large assets LFS
  tools/                # launcher, replay, manifest, QA, build helpers
  tests/                # fixtures, integration, network/capacity scenarios
  geo/                  # adapter/converter sau; không đặt cả PBF vào Git
  evidence/             # index+small reports; media lớn ở artifact store được duyệt
  .local/               # ignored binaries/cache/snapshots/dev data, không secrets Git
```

Mỗi runtime dùng snapshot/path và user-data directory riêng. Một editor writer
trên project source; nhiều client/server được phép cho test mạng nhưng mỗi
process có role/run_id/log/user_dir riêng. Không áp quy tắc “chỉ 1 process tổng”
khi WP cần multiplayer; vẫn cấm hai writer/evidence worker trùng path.

## A03 — Authority và simulation

- Physics/input client fixed 60 Hz; render tách clock. Room simulation mục tiêu
  30 Hz, snapshots gần 10–20 Hz tùy budget, xa/đứng giảm tần suất. Đây là
  starting values, phải profile và khóa trong protocol contract.
- Client prediction cho di chuyển, server validation/reconciliation, interpolation
  remote. Frame rate không quyết định tốc độ; fixed-step khác nhau phải test
  motor tolerance, không tuyên bố bitwise physics deterministic giữa thiết bị.
- Input có session_id, sequence, client_tick, pressed/held/released; server
  giới hạn history/future window, speed, acceleration, jump cooldown và bounds.
- Server tiêu thụ input theo tick 30 Hz: held state cuối hợp lệ trong cửa sổ;
  pressed/released edge có sequence giữ thứ tự, không bỏ jump vì release đến
  cùng tick; edge mỗi action tối đa một lần, dedup bằng sequence. Cooldown,
  speed và activity time dùng server clock; client 60 Hz chỉ prediction. Late
  edges ngoài history window reject/resync có test; không tính thời gian chạy
  bằng số packet. P1-02 khóa cách gộp và cửa sổ ticks trong schema.
- Mỗi actor chỉ một authority; room migration là leave/join ở alpha, không
  hai server cùng có quyền. Private house/activities là instance tách biệt.
- Pause Solo đóng băng sim. Pause/menu Online không dừng room: khóa input
  người chơi, hiện rõ vẫn Online hoặc lựa chọn leave; server vẫn chạy.
- Disconnect: kết thúc quyền phát input, actor cleanup trong TTL; reconnect
  session mới lấy snapshot/resume durable state, không phát lại pose cache.

Server validates interaction distance, visibility, cooldown, actor epoch và
catalog ID. Không tin client gửi result “đã câu được cá hiếm”. Activity reward
gắn attempt_id/seed do authority sinh, outcome validate trên server. Solo
có sandbox economy riêng theo PRODUCT, không nhập thành tiền Online.

Reward room→API: room gửi durable award command với attempt_id/command_id và
proof authority; có pending journal/retry được phục hồi, API dedup và commit.
Client có thể thấy animation “bắt được”, nhưng inventory/notification “đã nhận”
chỉ sau API committed receipt/readback. Room crash sau API commit: reconnect
query receipt/inventory, không mint lại. Crash trước commit: recover pending
award từ journal hoặc báo retryable pending, không âm thầm mất thưởng đã ACK.
Test crash cả hai phía; room journal không thay DB ledger authority.

## A04 — Protocol và security gate

Local spike dùng Godot high-level multiplayer/ENet để kiểm tra input/snapshot.
Reliable channel cho commands/events quan trọng; unreliable ordered snapshots
có seq để loại cũ. Không để retry reliable của item chặn dòng movement.

**Trước WAN:** khóa transport thực tế, encryption, chứng chỉ/trust model,
MTU, rate limit, ticket replay prevention, timeout và NAT/firewall path. ENet
không tự là secure account protocol. DTLS nếu version/build/target hỗ trợ
được chứng minh; nếu không, chọn transport secure được hỗ trợ và chạy lại
network/perf tests. Không đưa UDP plaintext chứa thông tin nhạy cảm lên public.
TLS của API không đồng nghĩa movement channel đã mã hóa.
DEV_ONLY identity/tickets chỉ chạy loopback, không dùng trên LAN/WAN thật.
P3-02 khóa Win/Android/Linux transport matrix + binding ticket với channel
auth trước P6. UDP bị chặn: fail-closed và UI kết nối thất bại có retry; không
fallback plaintext. Nếu thêm transport fallback, phải đo lại authority/perf/
capacity trước mở cho người dùng, không ngầm coi WebSocket tương đương ENet.

Join ticket ngắn hạn: account, room, session epoch, expiry, nonce, permissions;
do API ký, room xác minh, tiêu thụ theo policy chống replay. Key rotation và
server trust là cấu hình ngoài Git. Bất kỳ client sửa account_id/owner_id đều
không được tự tăng quyền. Raw token/input chat không xuất evidence công khai.

Envelope command durable gồm schema_version, command_id, account/session,
expected_version, issued_at, type, payload. Kết quả có status/code, result_id,
committed_version và server timestamp. Cùng command_id + cùng payload trả
cùng kết quả; khác payload cùng id phải conflict, không apply lần hai.
Packet size/field count/length/range validate trước deserialization sâu/apply.

## A05 — AOI, capacity và room routing

Trần alpha: 32 người/room; private house tối đa 8, party 4. Ngoài room không
stream transform. AOI quyết định ai nhận actor liên quan; proximity + quyền
social + block + room policy. Trong trần ưu tiên party/bạn/đang tương tác;
priority không phá privacy và không làm ngân sách vô hạn.

AOI spawn/despawn có hysteresis để tránh nhấp nháy ở biên. Trước mở tương tác
trực tiếp avatar↔avatar (khác mua ở quầy public khi chủ offline),
server bảo đảm hai bên được replicate trong một khoảng grace đã test; nếu
ngân sách không còn, từ chối rõ hoặc chuyển room, không giao dịch “người vô hình”.
“Biết actor” = đã gửi spawn cùng actor_epoch và có ACK từ cả hai peer; grace
chờ tối đa 2 s, sau đó báo đang đồng bộ/từ chối retryable. ACK chỉ mở UI/interest,
không trao quyền validate distance/ownership cho client. Block/revoke làm
epoch/permission cũ vô hiệu ngay phía server; thao tác in-flight được kiểm lại.
Người xa dùng LOD/thưa animation/không nameplate; đây là tối ưu biểu diễn,
không tạo capacity server. Crowd proxy nếu có về sau chỉ biểu diễn mật độ,
không được giả là mọi người đang tương tác đầy đủ.

Friends lookup → kiểm tra quyền → tìm room → reserve slot có TTL → ticket
→ join ACK → release chỗ cũ. Retry không chiếm nhiều slot. Full/expired/block
là các kết quả khác nhau; reconnect không kick người khác để lấy chỗ.
Khi mất kết nối đột ngột, giữ một reservation reconnect **30 s**, actor pose
cleanup vẫn trong **10 s**; reservation vẫn tính vào cap. Sau expiry release
idempotent; reconnect hết hạn đi qua admission như lần mới, không kick peer.
Logout/leave chủ động release ngay. Session mới thắng session cũ theo epoch,
không tạo hai reservation. Party reserve đủ số slot trong một transaction
hoặc cả nhóm fail; deadline 15 s để join, hủy phần chưa vào và UI rõ người
đã join; không claim atomic network join khi chỉ reservation là atomic.

Load scale: 2 client thật local → 4 client LAN → 32 virtual network clients
với 2–4 client render → 2–4 máy WAN → alpha người dùng. 64 render dummies là
test art/perf riêng. CCU toàn backend phải ghi số room, cost và cấu hình;
không nhân 32 × server count rồi gọi là load test.

## A06 — Dữ liệu và giao dịch

ID nội bộ bất biến: account_id, avatar_id, item_instance_id, item_type_id,
house_id, placement_id, shop_id, listing_id, transaction_id, world_id,
instance_id, chunk_id, anchor_id. Provider geo ID là mapping có version;
không dùng osm way ID làm primary key shop hay item.

PostgreSQL là authority durable. Tables logical: accounts/profile, friendships/
blocks, inventory, wallets/ledger, houses/placements, shops/listings, commands,
outbox, reports/moderation_actions, world_releases/anchor_mappings. Pose runtime
ephemeral; không lưu position history từng frame vào DB.

Mua item game: khóa hoặc optimistic version stock/wallet → validate funds,
ownership, visibility → debit/credit/item transfer + journal + outbox trong
**một transaction** → ACK committed result. Retry sau timeout tra command_id.
Crash trước commit không nhận tiền/đồ; crash sau commit trả lại cùng receipt.
Hai người mua last item chỉ một thành công. Không transfer hai hệ qua socket
fire-and-forget. Client UI pending/failed/succeeded rõ, không báo thành công sớm.

House placement/catalog shop đều validate khoảng kích thước/quota/owner/version.
Published listing sống khi owner logout. Draft không lộ qua API/read model.
Delete/hide không xóa audit cần thiết; retention có policy ở release gate.
Backup trước migration; expand/migrate/contract; rollback phải đọc được dữ
liệu hoặc có restore đúng version, không chỉ checkout code cũ.

Account deletion: user request xác thực lại → revoke sessions/tickets → hide
profile/shop, remove friend edges/linking tokens, tombstone ID; ledger/audit
pseudonymize và giữ đúng retention/policy thay vì xóa dòng làm hỏng giao dịch.
Chat/reports theo retention đã chốt; không xóa chứng cứ đang cần xử lý ngoài
policy. Local Solo save có nút xóa riêng, account deletion không được hứa xóa
file trên thiết bị đang offline. Unlink Hoàn Hảo thu hồi token/mapping liên
quan, không tự xóa account ở service khác.
Deletion journal/tombstone lưu bền ngoài rollback snapshot của DB gameplay,
retention ít nhất backup horizon + restore safety window. Restore phải replay
tombstones mới hơn snapshot trước mở traffic, không resurrect account/shops.
P3-01/P6-02 phải có test restore sau deletion và báo đúng phạm vi dữ liệu còn giữ.

## A07 — Backend địa lý và Hoàn Hảo về sau

`GeoProvider`, `PlaceDirectory`, `MarketplaceDirectory`, `IdentityProvider`
là interfaces versioned. Fake fixture có test contract sớm, HTTP adapter thật
chỉ mở ở P7. MapLibre không nằm trong simulation loop. Game dùng world package
đã convert; Web Hoàn Hảo giữ map/search/shop nếu có backend phù hợp thực tế.
API integration chỉ dùng quyền tối thiểu, schema đã kiểm chứng và consent;
báo cáo về service cũ là đầu vào chưa audit, không bằng chứng deploy sẵn.

## A08 — Vận hành

Room health: tick lag, active actors, queue, packet drops, RTT, outbound bytes,
memory, session expiry. API: latency/error, transaction retry/conflict, queue
age, moderation backlog. Correlation run/request/command ID, không secret.
Graceful drain: ngừng admission, thông báo, flush durable ops, ACK kết quả hoặc
retryable status, chuyển/kết thúc session, xác minh không mất item.
Build hash/protocol/content version handshake; từ chối client không tương thích
có hướng dẫn update. Không nâng server giữa phiên mà quên migration policy.
Alpha dùng một protocol/content version N tại một thời điểm; drain rồi upgrade,
không hứa rolling N/N-1. P8-03 phải khóa policy coexistence: mặc định vẫn N-only
với maintenance window; chỉ mở N/N-1 sau schema/behavior/rollback tests tương ứng.
Solo save có schema_version/migration/backup; từ chối future version an toàn,
không ghi đè save mới bằng client cũ.
