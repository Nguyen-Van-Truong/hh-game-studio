from pathlib import Path
import hashlib, json, os, tempfile

ROOT = Path(__file__).resolve().parents[3]
Z = ROOT / "zdoc"
TOOLS = Z / "8-9-godot-blender-agent-studio-plan.txt"
GAME = Z / "8-9-hh-world-gameplay-viet-nam-plan.txt"
OUT = Path(__file__).resolve().parent
BEFORE = OUT / "before-s3"
EXPECTED = {
    TOOLS: "583d083b93747c368cb9f2b537f20cd0b5d1340b51ccc5aa1eb8e5a12c9f842a",
    GAME: "f20d4461ff5dec0ef119216e15f548220b47af1bacb2fff25bb403695beb8d34",
}

def read(p):
    return p.read_text(encoding="utf-8-sig")

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {n}")
    return s.replace(old, new, 1)

def atomic(p, s):
    fd, name = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(s); f.flush(); os.fsync(f.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name): os.unlink(name)

def build_tools(t):
    t = once(t, "PLAN_REVISION=S2", "PLAN_REVISION=S3", "tool revision")
    t = once(t, "END_OF_TOOLS_PLAN\nDATE=2026-09-08 Asia/Saigon", """10. RÀ SOÁT BỔ SUNG S3 — ĐIỀU KIỆN ĐỂ CÓ THỂ PUBLIC

S3 khóa thêm các điểm thường bị bỏ sót khi từ fixture chuyển sang sản phẩm:
- Command envelope phải canonicalize JSON (UTF-8, key order, integer/string và
  duplicate-key reject) trước payload_hash; giới hạn tổng bytes sau giải nén,
  số phần tử, độ sâu, thời gian CPU và kết quả đọc. Parser không được khác nhau
  giữa Python/Node/Godot. Target path được kiểm lại ngay trước open/write để
  tránh TOCTOU; cấm hard-link/reparse ngoài root và cấm symlink trong release.
- Loopback token chỉ bảo vệ một phần: mọi endpoint phải có origin/host policy,
  chống DNS rebinding/SSRF, rate limit theo session+IP, timeout và body limit;
  log redaction phải có test bằng token, cookie, Authorization, đường dẫn và
  payload lỗi. Cùng máy không phải ranh giới tin cậy giữa các user.
- Package cài đặt phải có chữ ký hoặc trust root được pin, key rotation/revocation,
  minimum-version chống rollback và staged activation. Hash một mình không chứng
  minh nguồn nếu manifest không được xác thực. Ghi rõ trường hợp dev offline;
  không biến dev bypass thành release capability.
- GLB/texture/shader/animation được parse trong process giới hạn tài nguyên,
  không dereference URI ngoài allowlist; archive ratio, file count, dimensions,
  bones, clips, material/shader complexity và decompression time đều có cap.
  Import cache là disposable; release chỉ nhận artifact đã hash và readback.
- Mỗi operation có dry-run/diff preview, affected-consumer list và undo/recovery
  path. UI phải hiển thị queued/running/draining/unknown, progress có nhịp hoặc
  “đang không xác định”, nút Stop không giả hủy. Pagination/field allowlist
  ngăn inspector làm treo UI khi scene lớn; keyboard focus và lỗi có next action.
  Đây là yêu cầu UX/conformance, không suy ra từ API tồn tại.
- Package update phải test downgrade bị chặn đúng policy, migration backup,
  revocation, mất mạng giữa download/activation và recovery về last-good. Patch
  bảo mật có expiry/upgrade window; không silent auto-upgrade engine/addon.

Các điều kiện này được phân công: GT-02/TQ02/TX03 (canonical parser, SSRF,
redaction), GT-05/TQ05/TX04/TX08 (asset bombs), GT-07/TQ07/TX09/TX11 (atomic
activation), GT-08/TQ08/TX10 (signed package/rollback), GT-06/TQ06/TX13 (UX
states), GT-09 (cross-client conformance), GT-10 (migration/support artifact).
Mỗi test ghi input size, limit, elapsed, exit và expected reject/commit; không
chấp nhận một “security review” chung thay cho case thực.

10.1 Cổng bảo trì dài hạn

Trước mỗi toolchain update phải chạy compatibility matrix cũ/mới trên fixture,
reproduce import/export hashes hoặc semantic diff, migration/rollback, then
consumer smoke. Giữ một last-good package và changelog không xóa evidence.
Dependency/CVE scan, SBOM, license/attribution và expiry của certificate/key
được kiểm trong CI; artifact hết hạn bị chặn trước publish. Metrics có baseline
và phân vị; không dùng median để che p99/rare crash. Bản update chỉ là CANDIDATE
cho đến khi hai critic đọc cùng source/package hash.

END_OF_TOOLS_PLAN
DATE=2026-09-08 Asia/Saigon""", "tool appendix")
    return t

def build_game(g):
    g = once(g, "PLAN_REVISION=S2", "PLAN_REVISION=S3", "game revision")
    g = once(g, "1 phòng instance/account, 12 món nội thất catalog, đặt/xoay/undo/lưu, mời party",
             "1 phòng instance/account, 12 món nội thất catalog, đặt/xoay/undo/lưu; tối đa 8 visitor đã được reserve theo policy, trong đó party tối đa 4 người, mời party",
             "house capacity")
    g = once(g, "Không có một cấu hình đúng cho “game đã xong”. Cần biết CCU peak/average, mức\nđông trong một room, số room/private houses, tần suất mua/chat, scene CPU/RAM,\nbytes/sec và vùng người chơi.",
             """Không có một cấu hình đúng cho “game đã xong”. Cần biết CCU peak/average, mức đông trong một room, số room/private houses, tần suất mua/chat, scene CPU/RAM, bytes/sec và vùng người chơi.

Trước khi gọi là public-scale, phải tách capacity theo API read/write, room tick,
DB protected write, CDN/origin, egress, moderation và operator; không chỉ nhân
CCU. Mỗi con số có workload mix, peak factor, fault domain, confidence interval
hoặc giới hạn đo được. Capacity review phải có overload test vượt rated capacity,
load-generator saturation được loại riêng, graceful degradation và cost guard.
Autoscaling không được tạo retry storm hoặc cấp hai authority; scale-out phải
giữ idempotency, migration compatibility, shard placement và audit.

""", "scale gate")
    g = once(g, "P3-02 khóa timeout/rate/size profiles bằng số và fixtures trước implementation\nconsumer.",
             """P3-02 khóa timeout/rate/size profiles bằng số và fixtures trước implementation consumer. P0-02 đồng thời khóa privacy/telemetry profile: trường dữ liệu, purpose, retention, deletion/export, access audit và data residency theo target phát hành. Mọi SDK/analytics bên thứ ba có inventory/consent switch và offline queue cap; crash report phải scrub PII. Không coi tắt tên người chơi là anonymization nếu ID vẫn link được.

""", "profile gate")
    g = once(g, "EX36 — Release/update/cost/brand/human gate; P6-03/P8-03/P9-01.",
             """EX36 — Release/update/cost/brand/human gate; P6-03/P8-03/P9-01.
  Clean install/update/uninstall/corrupt download/old save/protocol, staged
  rollout + verified rollback. Review age/audience/moderation/brand/rights,
  signed artifacts qua quyền thực. Thiếu 5+8 human tests = UNVERIFIED, thiếu
  owner publish approval = release-ready package, không tự đăng hay ký giả.
EX37 — Client compromise/observability/privacy leak; P3-02/P3-04/P4-04/P6-01.
  Fuzz protocol, replay valid packets with altered claims, inspect crash/log/
  analytics/export/support paths for tokens, PII, coordinates, hidden presence,
  and chat. Server remains authority; logs are redacted but useful with support
  correlation ID. Test log retention/deletion/export/access audit and operator
  least privilege. A passing TLS check does not prove authorization or privacy.
EX38 — Dependency/package/update supply chain; P0-01/P1-01/P3-01/P8-03/P9-01.
  Verify signature/trust root, SBOM/license/CVE policy, artifact hashes, key
  rotation/revocation/minimum version, corrupt or partial download, downgrade,
  offline activation and last-good rollback. Reject unsigned/untrusted plugins,
  duplicate JSON keys, archive bombs and manifest path escapes before activation.
  Do not auto-fetch latest or silently change engine/addon.
EX39 — Device lifecycle/background/OS policy; P0-02/P1-03/P5-03/P8-03.
  App suspend/resume, process reclaim, low storage/RAM, GPU context loss, 4 KB/
  16 KB page-size Android artifact, ABI/target SDK, permission denial, notch,
  thermal throttling and interrupted update. Preserve save/receipt semantics,
  keep core Solo usable, and fail release support for an untested OS/SKU. Android
  store policy and toolchain requirements are time-sensitive; recheck at release.

""", "new exceptions")
    g = once(g, "Mỗi candidate có run_id/command_id, seed/map/mode, complete source manifest",
             "Mỗi candidate có run_id/command_id, seed/map/mode, privacy/telemetry profile, complete source manifest", "evidence fields")
    g = once(g, "END_OF_GAME_PLAN\nDATE=2026-09-08 Asia/Saigon", """10. RÀ SOÁT BỔ SUNG S3 — CỔNG PUBLIC VÀ UX

Trước public, H2-P8-03 phải có threat model đã đóng findings, SBOM/CVE/license
report, dependency pin và rollback rehearsal, data inventory/retention/deletion
evidence, support/appeal/runbook, feature kill switches và status page copy.
P9-01 chỉ phát hành binary đã verify chữ ký/hash trên clean install; rollout
phased có canary, stop/rollback trigger và migration compatibility. P9-02 theo
dõi crash-free sessions, ANR, tick miss, reconnect success, protected-write
unknown, duplicate/reconciliation, queue/WAL, abuse reports, CDN/cache, cost
và privacy incidents theo cohort/device/region; alert có owner/runbook và không
đưa nội dung riêng tư vào dashboard rộng.

UX acceptance bổ sung: mọi thao tác online cho người chơi thấy trạng thái đang
xác minh/đang chờ/đã nhận/chưa xác định; UNKNOWN mở tra cứu receipt và có đường
thoát, không spinner vô hạn. Full/offline/blocked/expired/maintenance có thông
báo khác nhau, next action rõ và không lộ quan hệ riêng tư. Save/update có
progress, pause/resume/cancel semantics, giữ last-good và không mất draft. Text
tiếng Việt có dấu, IME composition, screen reader label cơ bản, 200% text,
safe-area và reduced-motion phải được chạy trên từng support preset. Người dùng
không cần hiểu ticket, shard, epoch, WAL hay CRC để hoàn thành hành trình.

“Hàng trăm triệu” vẫn là mục tiêu phân lớp. Để đi từ pilot đến quy mô đó cần
capacity review mới cho identity, directory, economy, shard migration, hot-key,
data residency, deletion propagation, backup restore, abuse and support staffing;
không mở bằng cách tăng cap room hoặc thêm vCPU. Nếu chưa có số đo và owner
policy, trạng thái phải là SCALE_GAP.

END_OF_GAME_PLAN
DATE=2026-09-08 Asia/Saigon""", "game appendix")
    return g

texts = {p: read(p) for p in EXPECTED}
for p, old_hash in EXPECTED.items():
    actual = sha(texts[p])
    if actual != old_hash:
        raise RuntimeError(f"baseline changed for {p.name}: {actual}")
new = {TOOLS: build_tools(texts[TOOLS]), GAME: build_game(texts[GAME])}
for p, s in new.items():
    if "END_OF_" not in s or "PLAN_REVISION=S3" not in s:
        raise RuntimeError(f"sentinel failure for {p.name}")
    BEFORE.mkdir(exist_ok=True)
    atomic(BEFORE / (p.name + ".snapshot"), texts[p])

manifest = {"revision":"S3", "files":[]}
for p, s in new.items():
    manifest["files"].append({"path":p.name, "sha256":sha(s), "bytes":len(s.encode("utf-8"))})
try:
    for p, s in new.items(): atomic(p, s)
except Exception:
    for p, old in texts.items(): atomic(p, old)
    raise
(OUT / "s3-freeze.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
