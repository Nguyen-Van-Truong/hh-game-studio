"""Plan-only revision from exact S3 bytes; prepare both files before replacing either."""
from pathlib import Path
import datetime, hashlib, json, os, re, tempfile

OUT = Path(__file__).resolve().parent
Z = OUT.parents[1]
NAMES = ['8-9-godot-blender-agent-studio-plan.txt', '8-9-hh-world-gameplay-viet-nam-plan.txt']
EXPECTED = ['1d409988dd778477326e8da1bbe42430106552eaa227707a55d46605e34986a3', '8c46741a30514ad0bae1571266db527ec246ebf3ad2b98a0a839a01a5ccae024']
old_bytes = [(Z/n).read_bytes() for n in NAMES]
assert [hashlib.sha256(b).hexdigest() for b in old_bytes] == EXPECTED, 'Source changed: reconcile before editing'
t,g = [b.decode('utf-8') for b in old_bytes]

def once(s,a,b):
    assert s.count(a)==1, f'Expected unique anchor: {a[:100]!r}; got {s.count(a)}'
    return s.replace(a,b,1)

def region(s,a,b,new):
    assert s.count(a)==s.count(b)==1, f'Ambiguous boundaries {a!r} / {b!r}'
    i,j=s.index(a),s.index(b)
    assert j>i
    return s[:i]+new.rstrip()+'\n\n'+s[j:]

def add_wp(s, wp, line):
    pattern=rf'(^### {re.escape(wp)} — [^\n]+\n)'
    s,n=re.subn(pattern, lambda m:m.group(1)+line.rstrip()+'\n',s,flags=re.M)
    assert n==1,wp
    return s

def common(s):
    s=once(s,'Ngày 08-09-2026, Asia/Saigon | Revision S2','Ngày 09-09-2026, Asia/Saigon | Revision S4')
    s=once(s,'PLAN_REVISION=S3','PLAN_REVISION=S4')
    s=once(s,'BASELINE_STUDIO=3cc7a85f730c99963a5a64079a0e02dc20edbd40',
        'REVIEW_BASE_COMMIT=5d19ba66d4476928e564f165b6396743dccde620\nHISTORICAL_STUDIO_COMMIT=3cc7a85f730c99963a5a64079a0e02dc20edbd40')
    s=s.replace('BASELINE_SOCIAL=', 'HISTORICAL_SOCIAL_COMMIT=')
    s=once(s,'DATE=2026-09-08 Asia/Saigon','DATE=2026-09-09 Asia/Saigon')
    return s
t,g=common(t),common(g)

# Tools: merge the S3 appendix into the actual contracts and owning WPs.
t=region(t,'10. RÀ SOÁT BỔ SUNG S3','END_OF_TOOLS_PLAN','')
t=once(t,'repo mới `hh-game-studio/8-9-hh3d-3/zdoc/`;', 'thư mục `hh-game-studio/8-9-hh3d-3/zdoc/` trong repo hiện tại;')
t=once(t,'Trong root HH2 dự kiến','Trong root HH3D-3 dự kiến')
t=region(t,'GT-01 kiểm official artifacts và capability reuse.', 'GT-01/08 chứng minh', '''GT-01 kiểm official artifacts và capability reuse. Trang archive Godot và LTS
Blender đã được đối chiếu trong lượt 08-09: ứng viên Godot 4.7.2-stable standard
+ matching export templates, Blender 5.2.1 LTS; fallback Blender 4.5.13 LTS chỉ
khi addon không tương thích đã tái hiện. Đây là ứng viên, chưa là installed pin.
GT-01 phải lấy artifact từ nguồn official, xác minh full commit/SHA256/license/
--version, nền tảng và exporter; sai thì GAP, không tự tải latest hoặc tin tên
folder. Một bộ duy nhất trong studio/toolchain.lock.json; game nhận đúng bộ đó.
Godot không được gắn nhãn LTS của Blender. Pin bảo mật được nâng bằng release
đã review/regression; không đóng băng dependency lỗi vô hạn để giữ checksum.
''')
t=once(t,'Safety baseline phải có ngay GT-02', '''Canonical wire contract GT-02: JSON UTF-8, duplicate keys/invalid Unicode/NaN/
Infinity reject; integer ngoài safe range truyền decimal string. Dùng JCS
(RFC 8785) hoặc một profile tương đương đã khóa với golden vectors Python/
Node/Godot; không tự normalize Unicode trong payload_hash. Name NFC là bước
domain validation riêng trước tạo command. Scope dedupe=(project_id,command_id),
digest phủ operation+target+payload+schema; đổi lease không làm ID cũ thành lệnh
mới. Persistent results/tombstones không giữ toàn bộ trong RAM. Hết retry horizon
chỉ reject command đã hết hạn và tra cứu archive, không thực thi lại ID cũ.

Path protection phải chống race ở thời điểm dùng file: private staged root,
OS handle/descriptor không follow link, kiểm final resolved path/file identity,
deny reparse/junction/hardlink/ADS/device paths và case alias theo platform.
realpath rồi kiểm lại vẫn chưa loại TOCTOU; nếu pin/OS không cung cấp safe open
thì operation trên root có thể bị writer ngoài lease đổi link phải UNSUPPORTED.
Fuzz đổi link giữa validate/open/replace trên disposable root; không ghi ra ngoài.
Loopback HTTP/WebSocket cần Host/Origin allowlist, session auth trên read lẫn
write, chống DNS rebinding/CSRF và caps trước auth; không wildcard CORS. IPC
stdio có session binding/OS access, không ép HTTP Origin lên stdio. Credential
chỉ kênh riêng, redaction test bao gồm lỗi parser, argv, environment dump/capture.
External URL fetch chỉ host allowlist, validate từng redirect/DNS/IP, chặn local/
metadata/private endpoints không được cấp; source text/tool output không trao quyền.

Safety baseline phải có ngay GT-02''')
t=once(t,'không network thread gọi bpy.', '''không network thread gọi bpy. Host network chạy process ngoài Blender; UI
chỉ poll IPC không blocking với bounded work trên main-thread timer. Không để
Python background threads sống dai bên trong Blender dù thread không gọi bpy;
đây cũng là rủi ro theo tài liệu threading, phải test đúng pin.''')
t=once(t,'Bundled Python/Blender/addons/exporter versions ghi lock;', '''Preflight GLB/texture trong job riêng có CPU/RAM/disk/time cap; giới hạn cả
decoded bytes, dimensions, accessor/buffer bounds, mesh/bones/clip/material count,
URI, extension allowlist và recursion. Khronos validator chỉ là một lớp kiểm;
import sandbox Godot và visual/readback vẫn bắt buộc. Không nhận shader/script
do người lạ gửi; generated code từ agent phải qua source review/parse/lease trước
chạy sandbox. Disable autoexec không được coi là isolation cho parser.
Bundled Python/Blender/addons/exporter versions ghi lock;''')
t=once(t,'3. ĐẶC TẢ CÔNG VIỆC GT', '''2.6 Trust package, UX và support contract

Package manifest schema HH-STUDIO-0.1 phải bind package_id/version/target,
artifact hashes, source closure, protocol/schema, expiration/security floor,
trust-key ID và rollback compatibility. Local GT-08/GT-10 dùng test signer/
pinned trust key riêng; không cần production signing credential để đạt fixture.
Consumer verify manifest signature qua key đã pin ngoài artifact trước giải nén;
SHA tải cùng file không tự xác thực publisher. Public signing là gate riêng.
Test key rotation/revocation, expired metadata, hash/target mismatch, download
gián đoạn và replay version cũ. Không downgrade xuống dưới security floor;
last-good bị revoke thì giữ source/saves, chặn tool mutation và báo recovery
package cần thiết. Last-good còn trusted/compatible mới được rollback activation.
Offline không cho cài metadata đã hết hạn; bản đã cài hợp lệ vẫn dùng offline
trong policy được công bố, không network kill-switch phá source của người dùng.
TUF là reference thiết kế, không yêu cầu tự viết hệ thống signing mới từ đầu.

Mutating operations công bố dry-run/diff/affected files và undo hoặc recovery
policy; inspect/input/Stop không giả có undo hay bắt preview gây trễ. Owner đã
authorize scope thì agent tự thực thi và show replay, không popup mỗi command.
Destructive edit có checkpoint. Undo nhiều bước kiểm revision, không ghi đè
manual edit mới hơn. UI dùng queued/running/draining/unknown/committed/rejected,
có next action, progress hoặc trạng thái chưa biết, keyboard focus/shortcuts,
reconnect không tự resume job đã Stop. Pagination/filter/result byte cap cho
inspector; dropped telemetry có counter, không drop command receipts.

Mỗi lần update: old/new compatibility fixture, migration/rollback, SBOM/license/
dependency scan và affected capability regression. Lần phát hành đầu GT-10 kiểm
consumer fixture độc lập; consumer HH World smoke chỉ áp sau khi game đã tồn tại.
Critical exploitable dependency không phát hành; waiver rủi ro thấp cần reviewer,
owner xử lý, expiry và test, không blanket ignore. Security fixes giữ last-good
hợp lệ trong upgrade window. Dùng source/runtime hashes trong support package,
scrub secrets/PII, có reproduction nhỏ; không upload toàn project mặc định.

3. ĐẶC TẢ CÔNG VIỆC GT''')
t=once(t,'No public upload/sign/install scope khác.', 'Chỉ ký bằng test trust key local; không public upload/production sign/install scope khác.')
t=once(t,'2critics cho mutation/security', '2critics cho mọi release package thay đổi')
t=once(t,'TQ02–TQ08/TX01–TX14','TQ02–TQ08/TX01–TX18')
t=once(t,'Case mới có TX ID, WP owner', '''TX15 — Canonicalization/TOCTOU/loopback attack; GT-02/GT-03/GT-09.
Golden vectors qua các client; swap link/alias giữa validate/open/replace,
HTTP bad Host/Origin, malformed token và redirect private endpoint bị reject,
không mutation ngoài scope hoặc lộ secret. Safe-open unavailable là GAP.
TX16 — Supply chain/expired key/downgrade; GT-08/GT-10.
Ký local fixture, tamper/truncate/revoke/mix version/target; verify trước unpack.
Rollback chỉ về bản còn trusted/compatible; key mất hoặc expired metadata có
recovery UX, không tự bypass security floor hay xóa source người dùng.
TX17 — Prompt injection/tool output/source code privilege; GT-02/GT-09.
Seed instructions độc hại trong asset metadata/README/log/URL; agent không đổi
root/model/quyền, không exfiltrate hay chạy eval theo dữ liệu. Capability token
enforced tại host, không chỉ trong prompt. Test generated script sandbox import.
TX18 — Quota/UI starvation/worker amplification; GT-06/GT-07/GT-09.
Flood inspect/export/capture và disconnect mid-job; queue/result/memory caps,
fairness theo project+session, Stop priority, no retry multiplication, bounded
diagnostic retention. Mất quota ghi GAP, không replay task tốn tiền vô hạn.

Case mới có TX ID, WP owner''')
t=once(t,'- package_id/semver, protocol_version/schema_digest', '- signed manifest/trust-key ID/security floor/expiry/target và policy mục2.6;\n- package_id/semver, protocol_version/schema_digest')
for wp,line in {
'GT-02':'CONTRACT/VERIFY: mục2.2 canonical/path/loopback, TX15/TX17; limits profile có số trước adapter consumer, cross-language golden vectors và no-effect reject.',
'GT-03':'CONTRACT/VERIFY: safe file open/revision mục2.2; Godot transaction và mutation UX mục2.6, TX15.',
'GT-04':'CONTRACT/VERIFY: mục2.3 external IPC host, không persistent Python threads trong Blender; resource-bounded hostile-input fixtures.',
'GT-05':'CONTRACT/VERIFY: mục2.3/2.4 preflight/allowlisted glTF extensions, decoded texture/accessor caps; Khronos validation + actual Godot import.',
'GT-06':'CONTRACT/VERIFY: mục2.6 reviewer UX và TX18; human Stop/reconnect không resume ngầm, keyboard/error/UNKNOWN có next action.',
'GT-07':'CONTRACT/VERIFY: mục2.5/2.6 crash consistency, TX18 fair quotas; publish/cancel race cùng journal không ACK sớm.',
'GT-08':'CONTRACT/VERIFY: mục2.6 và TX16; test signer/local trusted package; Android ABI/native libs 4 KB/16 KB compatibility. Emulator chỉ dùng page-size/ABI proof, không GPU acceptance.',
'GT-09':'CONTRACT/VERIFY: mọi TX01–TX18, prompt-injection/capability/UX trên đúng Cursor client; độc lập fixture, không chờ game.',
'GT-10':'CONTRACT/VERIFY: mục2.6/TX16 install/upgrade/revocation/security-floor/local signer, compatibility và support runbook.'
}.items(): t=add_wp(t,wp,line)
t=once(t,'TQ00–08/TX01–14 đủ','TQ00–08/TX01–18 đủ')
t=region(t,'Nguồn trên được các Cursor researcher lượt08-09', '9.2 Trạng thái', '''S14 https://www.rfc-editor.org/rfc/rfc8785.html
  JCS hỗ trợ canonical JSON; project phải test numeric/Unicode contract riêng.
S15 https://theupdateframework.github.io/specification/latest/
  Trust/update threats; test key local không phải production release signature.
S16 https://www.khronos.org/gltf/
  Asset interchange và validation; hợp lệ glTF không bảo đảm look/perf Godot.
S17 https://developer.android.com/guide/practices/page-sizes
  Android native libs/page-size test; store requirements kiểm lại trước publish.

Nguồn official đã được coordinator đối chiếu 08–09/09; các URL động không là
lock. Researcher cũ research.host.json timeout/exit1: research.md chỉ là gợi ý
chưa hoàn tất, không critic hay runtime acceptance. Nguồn/API chưa đọc lại đúng
pin ghi UNVERIFIED trước implementation. Không cài binary trong lượt review.
''')
t=region(t,'9.2 Trạng thái thiết kế và bàn giao','Từ vựng:', '''9.2 Trạng thái thiết kế và bàn giao
PLAN_DESIGN_REVIEW=SEE_EXACT_HASH_REPORT
Review hiện hành:
./reviews/20260908-r3/REVIEW-RESULT.md
File gộp cũ chỉ lịch sử, không dependency hay bảng tiến độ thứ ba. S4 tích hợp
contract S3 vào đúng mục2/GT/TQ/TX, bỏ mâu thuẫn routing, pin, package trust và
consumer vòng. Verdict S1/S2/S3 không chứng nhận S4. Report phải có đúng hash
của hai plan; static PASS không thay hai critic/runtime/human.

Bàn giao: 10GT/10spec, DAG một chiều GT-10→game, TQ00–08/TX01–18, source scope
và verify đầy đủ. PLAN_ONLY và tất cả PLANNED vẫn giữ; chưa triển khai từ review.
Snapshot/diff/freeze/validator/report là evidence dưới reviews, không nguồn WP.
Base commit chỉ provenance: cả root HH3D-3 đang untracked nên source hash từng
file mới xác định nội dung; không coi Git HEAD là bản freeze của các plan.
''')

# Game: repair routing and integrate requirements where the implementation reads them.
g=region(g,'10. RÀ SOÁT BỔ SUNG S3','END_OF_GAME_PLAN','')
g=once(g,'1 phòng instance/account, 12 món nội thất catalog, đặt/xoay/undo/lưu; tối đa 8 visitor đã được reserve theo policy, trong đó party tối đa 4 người, mời party',
    '1 phòng/account, 12 món catalog, đặt/xoay/undo/lưu; cap 8 người tổng gồm chủ nhà và holds, party tối đa 4 người')
g=region(g,'2. HỢP ĐỒNG CONSUMER NHẬN GÓI GT-10','3. GAME HH WORLD:', '''2. HỢP ĐỒNG CONSUMER NHẬN GÓI GT-10

H2-P0-01 nhận HH-STUDIO-0.1 manifest: package_id/version, engine/templates/
addon/API/schema/hash, artifact/license/asset source closure, target matrix,
trust-key ID/security floor/expiry và rollback compatibility. Verify chữ ký
qua trust key đã pin ngoài artifact và hashes trước install. GT-10 cung cấp
local test trust cho dev fixture; public keys/signing do release gate quản.
Game không chốt Godot/Blender candidate khác, không tải plugin/binary ngầm;
developer launcher chỉ fetch đúng artifact official+digest khi lock yêu cầu.

Không copy/sửa source studio; generated addon theo lock/readback digest.
Editor/Play tách process, object main thread, mỗi mutation có command_id/
lease/fence/revision/journal/readback. Import PREPARED→VALIDATED→ACTIVATING→
COMMITTED dùng contract package. Lỗi giữ active last-good còn trusted; source
manual mới hơn phải reconcile, không cứ timeout là rollback đè mọi file.
Revoke/incompatible package giữ source/save và báo recovery; không bypass trust.
H2-P1-01 kiểm package trên game, H2-P2-04 kiểm .blend→GLB→game loop thực.
Capability thiếu tạo GAP/minimal repro tại GT owner; không sửa generated addon.
''')
g=once(g,'1. LỰA CHỌN VÀ QUYẾT ĐỊNH KIẾN TRÚC\n', '1. LỰA CHỌN VÀ QUYẾT ĐỊNH KIẾN TRÚC\n')
g=once(g,'2. HỢP ĐỒNG CONSUMER NHẬN GÓI GT-10\n', '''Khi benchmark gate thất bại: profile/minimal repro, tối đa hai vòng tối ưu
theo giả thuyết rồi ADR scope/renderer/engine với cùng workload. Không tự hạ
acceptance để hợp code; đổi mục tiêu lớn cần owner. Hai vòng là điểm ra quyết
định, không giới hạn tổng thời gian hoàn thiện trước public.

2. HỢP ĐỒNG CONSUMER NHẬN GÓI GT-10
''')
g=once(g,'## P05 — UI và art direction', '''House/session policy: cap house=8 bao gồm chủ nếu đang có mặt và mọi active/
pending/reconnect hold; không phải 8 khách cộng chủ. Party cap=4, có thể mời
thêm party khác nếu đủ chỗ và quyền. Chủ rời nhà/logout: v0.1 đóng visit mới,
thông báo khách và đưa về lobby qua handoff có deadline profile; layout/items
đã commit vẫn giữ. Khi không còn active/hold/pending result, flush/readback
layout rồi idle timeout kết thúc process. Hàng triệu nhà/quầy offline chỉ là
DB rows/catalog/CDN, không mỗi account giữ một Godot process trong RAM.

Solo first-run không cần mạng; account provider outage vẫn chơi Solo. Chuyển
Online lần đầu giải thích sandbox, cấp starter kit Online qua một grant key
duy nhất/account, không bắt làm lại tutorial. Achievement cosmetic/tình trạng
đã đọc hướng dẫn có thể lưu preference; không import tiền/item/nhà Solo.

## P05 — UI và art direction''')
g=once(g,'3.2 KIẾN TRÚC VÀ HỢP ĐỒNG GAME ONLINE', '''P08 — Quy tắc gameplay cần khóa trước bulk content (H2-P2-03/P3-03/P5-01)

Activity descriptor versioned: input/cue/success/fail/cancel, time window, seed
policy, reward distribution/rarity công khai, quota/cooldown, max bundle và
reservation. Online RNG/seed bí mật tại authority; client nhận cue tối thiểu,
không nhận seed/reward table bí mật để reroll. Retry cùng descriptor/attempt,
không login/đổi room để reset cooldown. Latency allowance khóa trước; server
không tin client timestamp để mở rộng cửa sổ vô hạn. Visual/audio/haptic cue
có thay thế khi mute/reduced motion; touch và keyboard cùng luật thành công.
Quest state prerequisites/reset/timezone/claim/reward dùng catalog; reward chỉ
một lần ở Online, spam skip/reload không nhân. V0.1 không daily streak ép chơi,
paid random reward hay user script. Balancing profile có nguồn mint/sink,
price bands, rounding/overflow, quota và bot-abuse simulation; không thay luật
của attempt đang chạy khi cập nhật catalog. P5-01 có test thời gian nhận đồ,
inventory churn, cảm giác câu/trang trí và 6 outfit mix trên animation extremes;
human 5-person usability chưa chứng minh retention dài hạn.

3.2 KIẾN TRÚC VÀ HỢP ĐỒNG GAME ONLINE''')
g=g.replace('3.1 HỢP ĐỒNG TRẢI NGHIỆM GAME (P01–P07)','3.1 HỢP ĐỒNG TRẢI NGHIỆM GAME (P01–P08)')
g=once(g,'Local test: room server', '''Dedicated release = Linux export template + dedicated-server PCK/hash;
không chạy editor binary cho room. Strip visual resource phù hợp, giữ collision,
nav và sim catalog; test server package load/movement khác client package.
Một dedicated process/room ở v0.1; packing nhiều PROCESS trên node chỉ sau
Q04-P. Nhiều room trong một process cần ADR isolation riêng. Không load toàn
bộ accounts/friends/shop history/geo vào room; caches/quota actor/message/results
có hard cap. HTTP/DB/asset import/log upload không blocking hot tick. Room
gửi outcome bất đồng bộ có deadline/correlation, backpressure trước start activity.

Local test: room server''')
g=once(g,'Seq 64-bit/epoch có upper bound', '''Network profile có MTU/datagram cap sau DTLS, bounded reassembly và distinct
reliable command/unreliable pose channels. Test duplicate/loss/reorder/jitter,
IPv6/NAT rebinding/Wi-Fi→mobile/UDP blocked, handshake flood trước auth; server
không cấp room resources cho packet chưa auth, không amplification/reflection.
Rate limit theo account/session có ceiling IP để tránh NAT false positives.
Không replay input accumulated khi app resume; cap fixed-step catch-up tránh
spiral of death. Under overload ưu tiên correctness, shed join/optional updates;
không giảm simulation time để speedhack hoặc gửi reward chưa xác nhận.
Seq 64-bit/epoch có upper bound''')
g=once(g,'  mới và fence epoch cũ cùng lúc.', '  mới và fence epoch cũ cùng lúc.')
g=once(g,'Room/session router:\n', '''Auth boundary P3-02: OIDC Authorization Code + PKCE S256 cho native public
client, system browser, exact redirect URI/state/nonce; không embed client
secret trong APK. Bind account bằng (issuer,subject), không email/name match.
Validate issuer/audience/algorithm/key/expiry, JWKS rotation bounded; refresh
token secure OS store, rotation/reuse detection và reauth cho link/delete.
Room→API cần workload identity/least-privilege credential riêng, room epoch
không phải secret; check assigned room/attempt và service auth lúc commit.
Test giả server, confused deputy, credential rotate, provider outage và takeover.
Monotonic clock dùng duration trong một process; persistent deadlines do DB
authority/UTC có skew bound và fail-closed khi clock uncertain. Không persist
monotonic timestamp qua reboot/host; epoch+lease owner quyết định authority.

Room/session router:
''')
g=once(g,'Economy/catalog:\n', '''Admission authority: registry PostgreSQL transaction khóa room capacity+
hold/transition/account rows theo order cố định; create ticket nonce+reserve
cap atomic, cache router chỉ gợi ý. Takeover/block/hold expiry cùng CAS/locks.
Không check-then-increment counter RAM; retry ticket cũ không tiêu slot mới.
Region failover phải fence registry writer cũ trước cấp authority mới.

AOI/privacy filter là AND: quyền+block+room epoch rồi mới chọn distance/party/
interaction tiers trong cap. Far friend chỉ presence hợp quyền, không mọi
friend transform. Nếu dùng MultiplayerSynchronizer thì public_visibility=false
trước peer exposure; configure intervals rõ, spawn/despawn theo cùng policy
và điều kiện MultiplayerSpawner/root_path. Custom sync cũng phải fail closed.
Không replicate wallet/inventory/attempt seed/admin flags trong avatar state.
RPC targeted, snapshot, late join, reconnect/history/cached directory cùng test
privacy. Block/unhide không thể xóa packet attacker đã ghi; revoke ngăn dữ liệu
mới, flush queued private output và increment visibility epoch. Unblock chỉ
resubscribe state hiện tại sau policy check, không replay pose/chat lúc bị ẩn.

Economy/catalog:
''')
g=region(g,'API/gateway stateless để scale ngang;', 'Asset/map/catalog dùng object storage', '''API/gateway stateless để scale ngang, modular boundaries trước microservices.
V0.1 có một economic_realm_id và một PostgreSQL writer authority cho wallet,
inventory/escrow/listing, commands/attempts/mailbox/outbox và security fences liên
quan; protected sync replica không là writer thứ hai. Buyer/seller/item/price/
block checks nằm trong một local transaction. Shop purchase v0.1 không xuyên
realm; cross-realm currency/item transfer là GAP riêng, không chắp saga tại runtime.
Sharding account identity/directory sau này không tự shard economy; mọi consumer
resolve owner realm/placement version qua API, không hardcode DB host trong client.

Schema P3-01: bảng dedupe/terminal attempts/ownership của realm v0.1 không range-
partition theo thời gian. Unique commands=(realm,account,command_id), attempts
có PK và grant uniqueness dưới một attempt authority. PostgreSQL partitioned
UNIQUE phải gồm mọi partition key; thêm date vào unique KHÔNG còn chặn replay
cross-date. Chỉ time-partition audit/history khi dedupe authority giữ riêng và
đã test archive/drop/restore/retry. Later hash partition/shard phải có key/unique
mapping review; không coi một global unique index là mặc định có sẵn.
Retention có hot/cold archive, tối thiểu dữ liệu cần cho audit; watermark/terminal
authority từ chối lệnh cũ khi hot receipt đã compact. Đừng giữ mọi payload vô hạn
trong RAM/DB nóng; cũng không xóa dedupe rồi coi ID cũ là command mới.

DB pool cap toàn fleet (không mỗi room một pool lớn), connection/lock/statement
timeout, query/index budget và lock ordering được khóa. Deadlock/serialization
retry bounded dùng cùng command ID sau lookup; cancellation HTTP không suy DB
rollback. Transaction scope không giữ row lock khi chờ HTTP/network/UI.
Pagination keyset có stable tie-breaker, field projection, batch fetch tránh N+1;
friendship/block và private listing không bị read replica/cache lag làm lộ quyền.
Cache key chứa authorization scope/version, revocation có invalidation/TTL bound;
miss gộp request, fallback không chuyển private data thành public.
''')
g=region(g,'Scale ladder: 32 người/room', 'Kiểm EX16/20/29/30/35', '''Scale ladder CCU: 32/room ở P6; pilot 100→300, sau đó 1.000→10.000 tổng fleet
chỉ khi có gate/workload/budget cho nấc đó. Mỗi nấc có private-house fragmentation,
hotspot, reconnect, DB/economy, node-loss; không ép 10k để nghiệm thu alpha.
Dataset/index scale là trục độc lập: P3-01 xây generator và 100k records; P6-01
kiểm 1M cùng data skew; P8-02 tối thiểu 10M synthetic accounts/related rows hoặc
2× forecast 90 ngày nếu lớn hơn, có cardinality riêng từng table. Không spawn
Godot clients theo account count. Đo cold/warm indexed lookup/search/receipt/
friendship, privacy checks, DB size/index bloat, vacuum/WAL, backfill/backup/
restore elapsed dưới cùng query SLO mục7.3 và p99 profile khóa trước run.
100M/300M accounts là capacity gate tương lai phải đo đúng cardinality hoặc
công bố extrapolation + uncertainty; không chứng nhận bằng 10M hay 32 clients.
Nếu owner muốn hàng trăm triệu CCU thực thì cần chương trình đa vùng và capacity
review khác; hai plan hiện chưa cam kết năng lực đó. Không tự gắn SCALE_PASS.
''')
g=once(g,'A08 release N-only mặc định:', '''Outbox/async contract P3-01/P3-04: DB state commit và event delivery là hai
trạng thái riêng. Event retry at-least-once theo aggregate_id+sequence, consumer
dedupe và reject stale version; retry budget process, một tầng retry cho mỗi
boundary, exponential backoff+jitter, next-attempt cap và DLQ/quarantine durable.
Hết retry delivery không đổi một receipt COMMITTED thành UNKNOWN/FAILED. Alert
event age/backlog/DLQ; operator replay giữ event/command ID cũ sau sửa lỗi.
Queue/storage cap trước admission, không drop protected results. Receipt lookup
và revoke/security control có resource budget riêng, không bị bulk job chặn.

A08 release N-only mặc định:''')
g=once(g,'3.3 DURABILITY:', '''A09 migration/scale evolution: trước public pilot chỉ cần local migration,
indexed scale evidence, immutable owner/realm IDs và API placement abstraction;
không bắt deploy global shards chưa có nhu cầu. Khi mở nhiều shards: schema
compatibility + snapshot/backfill/CDC, reconcile counts/ledger, shadow reads,
drain/fence single writer và CAS routing version để cutover. Không dual-write
hai authority độc lập. Rollback sau new writes cần reverse replication hoặc
drain+reconcile, không trỏ client về snapshot cũ làm mất TX. Hold/deletion/security
epochs/command dedupe phải chuyển cùng owner data; test retry xuyên cutover,
hot shard/region outage và residency. New scale tier được accept bằng evidence
mới, giữ last measured cap đến khi gate đạt.

3.3 DURABILITY:''')
# Domain-specific data and privacy considerations, not legal conclusions.
g=once(g,'## G02 — Hợp đồng spatial ngay từ đầu', '''Provider selection P7-01: OSM data license khác policy endpoint. Không dùng
tile.openstreetmap.org để bulk/offline prefetch; public Nominatim không là
autocomplete/geocoder chung cho lượng user lớn. Chọn extract/provider cho phép
hoặc self-host đã đo/có quyền, quota/caching/attribution/cost rõ; không fallback
ngầm sang public service khi provider lỗi. PMTiles Range/ETag/hash/size validate,
chặn URL redirect/SSRF private endpoints và decompress bomb trên converter.

## G02 — Hợp đồng spatial ngay từ đầu''')
g=once(g,'6. Collision/nav riêng, sửa lối đi/spawn/gameplay anchors bằng overlay authored.', '''6. Collision/nav riêng, sửa lối đi/spawn/gameplay anchors bằng overlay authored.
   Giữ layer/bridge/tunnel/elevation: đường cắt nhau trên hình không tự nối nav.
   Multipolygon holes, self-intersection, duplicate ID, coast/water/height void
   được validate/sửa có lineage hoặc quarantine; không silent geometry repair.''')
g=once(g,'## Q00 — Gate chung cho mọi WP', '''3.5 DATA/UX/RELEASE CONTRACTS DÙNG NGAY TỪ ĐẦU

P0-02 ghi inventory dữ liệu/SDK dự kiến, purpose/retention/delete/export/audience/
residency draft. P3-01 triển khai trước thu dữ liệu, P6-02 chốt policy/người chịu
trách nhiệm trước tester, P8-03 kiểm lại release market. Analytics tùy chọn tách
operational metrics, consent/disable và queued telemetry capped/scrubbed. Không
gọi opaque stable ID là anonymized. Log support ID không raw token/chat/location;
moderation evidence tối thiểu tách kho access-controlled+TTL khỏi telemetry.
Deletion reauth→epoch revoke→pending commands/escrow/house/shop/friend/link state
reconcile→tombstone→purge/retain theo policy; không cascade xóa ledger của bên
mua/người khác. Bán đang commit vs delete phải serialize, tài sản in-flight vào
quarantine có audit nếu chưa quyết định disposition. Restore replay tombstone
trước read traffic; export request async/reauth/TTL download, không public link.
Không thêm audience trẻ em/public monetization khi chưa review/policy staffing;
đây là gate quyết định thực, không tự chứng nhận pháp lý.

UX trạng thái: optimistic preview khác receipt đã nhận. Pending sau 10s chuyển
copy chờ/tra cứu+support ID, cho đóng dialog và theo dõi trong lịch sử; server
status vẫn UNKNOWN đến khi có proof, không tự đổi FAILED sau UI timeout.
Thiếu quyền/private/blocked dùng chung thông báo “Không thể tham gia lúc này”;
full/queue/offline/update/maintenance có next action khi không lộ quan hệ.
Loading cancel không đồng nghĩa hủy durable TX. Giữ draft bằng revision, save
atomic có last-good; uninstalled Solo data theo OS không được hứa giữ mãi,
trước reset/delete có export và confirm rõ. Settings persist, first-run audio
không bất ngờ quá lớn. Touch/IME/keyboard remap/game focus + 200% text/notch/
reduced motion/cue không phụ thuộc màu/âm, accessibility labels và focus order
test bằng assistive technology thực trên target; missing capability là GAP.

H2-P8-03 public-ready: artifact signature/trusted update manifest, SBOM/licenses/
dependency risk triage, native ABI/4KB+16KB Android compatibility, target SDK và
store policy đọc lại lúc release. Emulator chỉ page/ABI, GPU phải máy thật.
Test patch/delta interrupted, disk space gồm old+new+staging peak, cache pinning/
eviction, corrupt CDN chunk, save N+1, key rotation/revoke và supported rollback.
Executable code chỉ qua release channel; catalog/content update không được lén
thêm GDScript/native plugin. Secrets/update key không ở client hay logs.
N-only drain giữ nguyên: canary là environment/cohort có version/DB compatibility
đã test, không tự mở N/N-1 shared realm vì ghi “phased rollout”. Security-floor
chặn rollback vulnerable build; phục hồi bằng bản sửa hợp lệ và giữ saves.

H2-P9-02 vận hành 7 ngày đề xuất phải có stop/rollback/admission triggers khóa
P8-03 trước traffic: critical dupe/data leak/durability mất protection→disable
affected writes/chat/public và incident runbook ngay; p95/p99/error/ANR/crash/
reconnect vượt profile theo window+sample floor→pause rollout/investigate. Dashboard
có numerator/denominator, kể cả timeout/queue reject, low-traffic zero sample là
NO_DATA. Synthetic fault drills riêng khỏi user metrics, không làm số đẹp bằng
bỏ failed requests. Error budget và customer impact/cost quyết định mở thêm tải.

## Q00 — Gate chung cho mọi WP''')
# Move the added contract before the quality chapter, preserving the order.
start=g.index('3.5 DATA/UX/')
end=g.index('## Q00 —',start)
block=g[start:end]
g=g[:start]+g[end:]
g=once(g,'4. QUALITY GATES —',block+'4. QUALITY GATES —')
g=once(g,'### H2-P0-01 — Consumer package intake', '5. ĐẶC TẢ 32 H2 — HỢP ĐỒNG, VERIFY VÀ ĐIỀU KIỆN XONG\n\n## P0 — Nhận tools và bootstrap\n\n### H2-P0-01 — Consumer package intake')
g=once(g,'EX01 — Hai máy một account;', '6. EX — NGOẠI LỆ, VALIDATE VÀ RECOVERY\n\nEX01 — Hai máy một account;')
g=region(g,'BUILD: nhận package GT-10 theo manifest;', '### H2-P0-02 —', '''BUILD: nhận nguyên gói GT-10 theo mục2; verify local trust/signature, manifest,
capability/target và digest; tạo consumer lock từ toolchain lock đã nghiệm thu.
Pin Linux x86_64/headless, không engine candidate khác, không sửa VF/cache cũ.
Missing artifact chỉ launcher dev fetch đúng URL/digest locked, chưa có thì GAP.
VERIFY: --version/readback package bằng launcher, tamper/wrong target/template/
trust/key/profile phải reject; Unicode/space paths, baseline/process owners.
DoD: consumer lock tái tạo, rollback hợp trust/schema và không ảnh hưởng root
khác; hai critics. Chưa được dùng package manifest làm proof gameplay/CCU.
''')
g=once(g,'reviewer toolbar là gói công cụ GT-10, cross-app activation quy trình gói GT-10 là gói công cụ GT-10.', 'reviewer toolbar/cross-app activation đều là capability gói GT-10 được tiêu thụ và kiểm lại.')
g=once(g,'Không dùng primitive-only benchmark thay avatar load, không chờ toàn bộ công cụ editor.', 'Không dùng primitive-only benchmark thay avatar load; package GT-10 đã là dependency được bàn giao.')
g=once(g,'BUILD: 1 phòng/12 catalog props (placeholder có plan thay), đặt/xoay/undo/save; kiểm asset đi từ `.blend` thuộc user copy qua package GT-10 vào scene Godot, play/readback, reimport và rollback.\nquầy demo', 'BUILD: 1 phòng/12 catalog props (placeholder có plan thay), đặt/xoay/undo/save,\nasset-source có lease trong assets-src/ qua GT-10→GLB→scene Godot và play/\nreadback/reimport/rollback; quầy demo')
g=once(g,'asset-source có lease trong assets-src/', '.blend source có lease trong assets-src/')
g=once(g,'authority/transaction/security/geo/release, P1-03/P5-03/P6/P8 và mọi ST cần2', 'authority/transaction/security/geo/release, P1-03/P5-03/P6/P8 cần2')
g=region(g,'A: GT-01→GT-10 của plan công cụ;', 'Concurrency starting2workers+1critic', '''A: GT-10 ACCEPTED → H2-P0-01 intake → P0-02 profile → P0-03 bootstrap.
B: sau P0-03, P1-01 consumer integration || P1-02 network spike trên snapshot
riêng; P1-03 kết hợp cả hai bằng workload/device đại diện. Không xây lại tools.
C: sau P1-03, P2 controller→avatar→activity→Solo house; art/UI schema/concept
có lane riêng. P3-01 chuẩn bị schema theo input khóa nhưng chỉ accept khi P2-03
đạt. P2-04 và P3 có thể triển khai song song đúng file lease.
D: P3-01→P3-02→P3-03→P3-04; P4 social→shop→house→moderation. Backend/client
trong một WP có thể song song sau schema freeze; không accept trước dependency.
E: P5 content→polish→device; P6 capacity→WAN/operator→human alpha.
F: P7 source/rights→converter→Hoàn Hảo adapter; P8 district→pilot→RC;
P9 publish theo quyền→observation. Tools maintenance sau handoff dùng change
request đúng GT owner, regression affected consumer; không thêm dependency vòng.
Mỗi lane có schemas/basehash/lease và artifact paths riêng; dependency bảng đầu
file là nguồn duy nhất. Concept chuẩn bị sớm không chứng minh WP đã hoàn thành.
''')
# Remove the accidentally duplicated EX36 body after EX39 and replace appendix profile.
g=region(g,'EX37 — Client compromise/', '7. SERVER CẦN CẤU HÌNH NÀO?', '''EX37 — Privacy/logs/delete/cross-account data; P0-02/P3-01/P4-04/P6-02.
  Mục3.5: parser lỗi/crash/support/analytics scrub, private cache/read-replica
  isolation, account delete vs trade/award/block và restore. Reauth/export
  link TTL/retention; không xóa ledger bên khác hoặc hồi sinh profile đã xóa.
EX38 — Update trust/security floor; P0-01/P1-01/P8-03/P9-01.
  Mục2/3.5: test signer khác release signer, verify signed manifest trước unpack,
  tamper/revoked key/partial CDN/wrong target/N-only drain/downgrade rejected.
  Recovery last-good phải còn trusted/schema-compatible; preserve source/save.
EX39 — Device/ABI/assistive tech; P0-02/P1-03/P5-02/P5-03/P8-03.
  Mục3.5/Q01: 4KB+16KB page-size native libs, OS reclaim/background/GPU loss,
  thermal, disk peak update, IME/200% text/focus/screen reader. Không lấy emulator
  làm FPS proof; refresh store requirements khi release, missing target là GAP.
EX40 — Partition/dedupe/realm migration; P3-01/P3-04/P6-01/P8-02.
  Mục3.2.1/A09: schema UNIQUE đúng partition key, retry cross-date/archive/drop/
  restore và placement-version cutover. Một owner economic realm, v0.1 cross-
  realm transfer reject; owner migration không dual-write independent ledgers.
EX41 — Bounded room/API/outbox resources; P1-02/P3-01/P3-04/P6-01/P8-02.
  Hot tick không HTTP blocking, dedicated export giữ sim, memory0/8/32 và packed
  node. Poison event→DLQ không đổi COMMITTED receipt; retry budget/jitter/order/
  dedupe/replay, pool exhausted/backlog recovery không double grant.
EX42 — Auth/transport/workload identity/clock; P1-02/P3-02/P3-03/P6-02.
  PKCE/nonce/redirect/JWKS/refresh reuse, giả room→API, preauth flood, MTU/IPv6/
  NAT rebinding/Wi-Fi→mobile, process restart clock. Secure fallback chỉ được
  mở sau same profile tests; role/epoch/attempt kiểm tại authority commit.
EX43 — AOI all channels/revoke/resubscribe; P3-03/P4-01/P4-04.
  Snapshot/spawn/RPC/late-join/cache đều theo AND permission; public_visibility
  default không leak actor/seed/wallet. Block purge queued data, revoke epoch;
  unblock không replay hidden history. Party priority không vượt permission/cap.
EX44 — House sleep/starter kit/activity balancing; P2-03/P3-04/P4-01/P4-03/P5-01.
  House cap8 gồm chủ+holds, party4, owner leave→lobby đúng TTL; empty house
  process ends, offline shop vẫn persistent. Starter grant chỉ một/account,
  quest/catalog update giữa attempt không reroll hoặc đổi reward đã phát.

P3-02 khóa numeric timeout/rate/size/MTU/retention profile trước consumer.
Mục3.5/P0-02/P3-01 khóa data/UX profile trước collection. Mỗi test ID có WP owner,
fixture/fault injection, expected invariant + player-facing result, raw metrics
và recovery. Incident mới thêm regression vào đúng owner, không giả đã phủ mọi lỗi.
''')
g=g.replace('EX01–EX39','EX01–EX44')
g=once(g,'  mem_room = resident incremental bytes/room + imported world/caches;', '''  mem_room = charged RAM/process room gồm base runtime+world+caches+buffers;
             đo empty process, empty world, 8/32 players và peak; RSS/PSS/cgroup
             semantics ghi rõ, không bỏ base process hoặc double-count shared pages;''')
g=region(g,'Fleet: required_rooms=', '7.2 Băng thông và chi phí', '''Fleet tính theo disjoint active categories, không đếm một player hai lần:
  rooms_plaza=ceil(CCU_plaza/(32*occupancy_plaza));
  rooms_house=observed concurrent active house sessions (cap8, often 1–4);
  required_rooms=rooms_plaza+rooms_house+distinct other active room types
                 + measured reconnect/transition headroom chưa gồm ở trên.
Offline houses không thêm process. Hold source-active+target-pending, empty
warm pool và reconnect grace có RAM/chỗ riêng trong workload; phân loại rõ để
không trừ reserve hai lần. Dùng measured r_node theo room MIX, không lấy max
packing toàn plaza áp cho houses. N+1 homogeneous node bound:
  node_count>=ceil(required_rooms/r_node)+1,
vẫn cần node-loss/admission/DB proof; heterogeneous/AZ loss phải reserve đúng
failure domain. Ví dụ CHỈ plaza, peak1000, occupancy1, r_node8:32rooms→5nodes;
occupancy0.6:53rooms→8nodes. Đây là giả định, không estimate 1000-user house mix.
''')
g=once(g,'Normal-path join p95≤5s', '''Load harness dùng open-loop offered rate độc lập response để không che overload
bằng coordinated omission; báo offered/admitted/completed/rejected/timed-out,
queue wait và end-to-end latency. Percentile histogram có sample count/min-max,
fixed measurement windows, CPU loadgenerator/clock sync error. Test 1x cap và
1.5–2x offered load trong bounded environment: shed ổn định, receipts sống,
recovery về SLO sau giảm tải trong time budget profile. P6-01 cần room/API/DB
concurrent; P8-02 thêm dataset/backup/restore/cost mix. Crash/ANR/availability
SLO và sample floor khóa P8-03 theo release audience, không gắn số reliability
đã đạt từ một giờ load hoặc 8 tester.
Normal-path join p95≤5s''')
for wp,line in {
'H2-P0-02':'CONTRACT/VERIFY: mục3.5/P08; profile baseline dữ liệu, UX/accessibility và support OS/ABI, targets có số/test IDs trước build; unknown không là kết quả.',
'H2-P1-02':'CONTRACT/VERIFY: dedicated template+PCK và async room boundary mục3.2; empty process/world RAM, preauth/MTU risk fixtures (DEV_ONLY loopback).',
'H2-P2-03':'CONTRACT/VERIFY: P08 activity/quest descriptor và mục3.5 Solo save/UX, EX44; không cần DB Online để nghiệm thu phần Solo.',
'H2-P3-01':'CONTRACT/VERIFY: mục3.2.1/A09/3.5, EX37/EX40/EX41; schema locks/unique/realm, data lifecycle, 100k dataset và query/index report.',
'H2-P3-02':'CONTRACT/VERIFY: auth/admission/clock/service identity mục3.2, EX42; reserve+ticket atomic, pinned limits/cert/PKCE; no client secret.',
'H2-P3-03':'CONTRACT/VERIFY: P08 server seed/latency fairness, hot tick không blocking, EX42/EX43; outcomes còn UNKNOWN khi chưa protected receipt.',
'H2-P3-04':'CONTRACT/VERIFY: realm/unique/retention/outbox/starter kit mục3.2, EX40/EX41/EX44; same-ID replay, poison events, deadlock và delete-vs-trade races.',
'H2-P4-01':'CONTRACT/VERIFY: P04/3.2 AOI/house cap/reservations, EX43/EX44; auth filter mọi channel, unhide không replay lịch sử.',
'H2-P4-02':'CONTRACT/VERIFY: một realm transaction mục3.2.1, slot/escrow/item/price/block race; owner delete/retire item và offline shop thuộc EX37/EX40.',
'H2-P4-03':'CONTRACT/VERIFY: P04 cap8 gồm owner+holds, sleep/owner-leave/close policy, EX44; layout persistence không giữ process cho account offline.',
'H2-P4-04':'CONTRACT/VERIFY: mục3.5/EX37/EX43; privacy evidence store riêng, RBAC/audit/appeal, revoke live và cached output.',
'H2-P5-01':'CONTRACT/VERIFY: P08 versioned balancing, worst outfit/pose mix, muted/touch cue fairness; original content đủ P03, EX44.',
'H2-P5-02':'CONTRACT/VERIFY: mục3.5 UX/assistive tech/resource-bounded streaming, EX39; UNKNOWN→history/support, no raw internal details.',
'H2-P6-01':'CONTRACT/VERIFY: EX40–EX43, mục7.3 offered load 1x/overload + 1M records độc lập CCU, queue/RAM/DB/outbox recovery và same-ID correctness.',
'H2-P6-02':'CONTRACT/VERIFY: mục3.5 data/audience/operator trước tester, DB-D2/D3/D4, EX37/EX42; credential có quyền riêng, không tự gửi lời mời.',
'H2-P8-02':'CONTRACT/VERIFY: EX40/EX41 + 10M hoặc 2×forecast records theo mục3.2.1, room mix/houses/no double count mục7.1, backup/restore và measured cap.',
'H2-P8-03':'CONTRACT/VERIFY: mục3.5 release trust/OS/keys/N-only cohort/data/UX, EX37–EX39; operational thresholds+sample floor+rollback triggers khóa trước rollout.',
'H2-P9-01':'CONTRACT/VERIFY: mục3.5 trusted artifact/clean install, N-only drain hoặc compatible canary đã test, signed/public chỉ quyền thực; EX38.',
'H2-P9-02':'CONTRACT/VERIFY: mục3.5/7.3 7-day observation scope, crash/ANR/errors/receipt/backlog/cost và privacy incident, NO_DATA khi thiếu mẫu; không tạo automation từ plan.'
}.items(): g=add_wp(g,wp,line)
g=region(g,'Hàng trăm triệu là mục tiêu dài hạn về account/record', 'Từ vựng:', '''Scale public chỉ trong cap đã đo tại P6/P8 và lượng account/data đã kiểm. Trước
mở tier lớn hơn phải có capacity/migration/fault-domain/cost/operator gate riêng
theo mục3.2.1/A09; không bắt dual-write global shards cho pilot. 100M/300M account
và 100M CCU là những claim khác nhau, đều chưa được chứng minh. Quy tắc giữ
source of truth/owner realm/quotas/evidence tạo đường mở rộng có kiểm soát, không
bảo đảm sau này không cần migration hay sửa đổi. Thiếu dữ liệu/SKU/WAN/policy
thì SCALE_GAP/UNVERIFIED, không “best/final” bằng độ dài tài liệu.
''')
g=region(g,'Nghiên cứu/review trước khi tách:', '9.3 Kiểm bàn giao', '''Lịch sử trước S4 không chứng nhận hash hiện tại. S4 sửa routing/workflow S2,
gộp appendix S3 vào contract gốc, bổ sung realm/dedupe/admission/AOI/RAM/outbox/
identity/UX/release và EX01–EX44. Không có plan thứ ba hay tiến độ từ report.
Base commit chỉ provenance vì hai TXT còn untracked; freeze dựa full bytes.
Tất cả 32 H2 vẫn PLANNED, implementation/runtime/human đều chưa nghiệm thu.
''')
g=once(g,'EX01–EX44, P01–P07/A/DB/G', 'EX01–EX44, P01–P08/A/DB/G')
g=once(g,'Blender UI timer/operator queue là thiết kế', '''S26 https://www.postgresql.org/docs/18/ddl-partitioning.html
  UNIQUE partition constraint; project chọn một economic owner realm ở v0.1.
S27 https://docs.godotengine.org/en/stable/classes/class_multiplayersynchronizer.html
  Public visibility mặc định và spawner/root_path; privacy/AOI phải tự enforce.
S28 https://sre.google/sre-book/handling-overload/
  Overload/retry controls; cap/SLO của game vẫn phải benchmark, không từ docs.
S29 https://www.rfc-editor.org/rfc/rfc9700.html
  OAuth security; native PKCE/redirect/refresh validation cần integration tests.
S30 https://developer.android.com/guide/practices/page-sizes
  Native page-size compatibility; deadline/store policy kiểm lại trước release.
S31 https://operations.osmfoundation.org/policies/tiles/
S32 https://operations.osmfoundation.org/policies/nominatim/
  OSM data khác public service policies; không chọn các endpoint này để scale.
S33 https://theupdateframework.github.io/specification/latest/
  Reference cho authenticated update/rollback/freeze threats, không runtime proof.

Coordinator đã đối chiếu nguồn official 08–09/09; research.host.json cũ timeout/
exit1 nên research.md chỉ provisional notes, không verdict. Docs động cần khóa
đúng version khi implementation. Phiên bản có trang không đồng nghĩa binary
đã cài/chạy hoặc engine tốt nhất cho mọi workload.

Blender UI timer/operator queue là thiết kế''')

# A bounded, table-driven traceability policy makes the long plans executable.
t=once(t,'TQ00: mỗi GT có', 'TQ00: bảng dependency đầu file + spec GT + mục2 + TQ/TX được spec trỏ tới\n+là acceptance closure. Limits/fixtures/test IDs phải khóa trước code consumer;\n+coverage map liên kết requirement→test→artifact/hash, orphan requirement là GAP.\n+Mỗi GT có')
g=once(g,'Dependency ACCEPTED; files đúng lease;', 'Bảng dependency + spec H2 + P/A/DB/G/3.5 và Q/EX được spec trỏ tới là acceptance\n+closure. Requirement→WP→test ID→artifact/hash phải có mapping, threshold trước\n+code consumer. Không spec nào tự giảm contract chung; orphan requirement là GAP.\n+Dependency ACCEPTED; files đúng lease;')

for name,s in zip(NAMES,[t,g]):
    assert '\ufffd' not in s and '\x00' not in s
    assert s.count('PLAN_REVISION=S4')==1 and s.count('END_OF_')==1
    assert len(re.findall(r'^\d{2} \| (?:GT-\d{2}|H2-P\d-\d{2}) \|',s,re.M))==(10 if name==NAMES[0] else 32)

snap=OUT/'before-s4'; snap.mkdir(exist_ok=True)
for name,b in zip(NAMES,old_bytes):
    p=snap/(name+'.snapshot')
    if p.exists(): assert p.read_bytes()==b
    else: p.write_bytes(b)
new_bytes=[s.encode('utf-8') for s in [t,g]]
staged=[]
for name,b in zip(NAMES,new_bytes):
    fd,tmp=tempfile.mkstemp(prefix=name+'.s4.',suffix='.tmp',dir=Z)
    with os.fdopen(fd,'wb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
    staged.append(Path(tmp))
# Compare both source hashes immediately before mutation; never replay a stale script.
assert [(Z/n).read_bytes() for n in NAMES]==old_bytes
for name,tmp in zip(NAMES,staged): os.replace(tmp,Z/name)
assert [(Z/n).read_bytes() for n in NAMES]==new_bytes
files=[{'path':n,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)} for n,b in zip(NAMES,new_bytes)]
manifest={'revision':'S4','proof_class':'PLAN_DESIGN','created_at':datetime.datetime.now().astimezone().isoformat(),'base_commit':'5d19ba66d4476928e564f165b6396743dccde620','files':files}
manifest['manifest_sha256']=hashlib.sha256('\n'.join(f"{x['path']} {x['sha256']}" for x in sorted(files,key=lambda f:f['path'])).encode()).hexdigest()
(OUT/'freeze-s4.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=True,indent=2))
