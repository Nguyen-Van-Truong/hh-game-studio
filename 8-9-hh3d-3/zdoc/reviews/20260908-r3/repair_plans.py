from pathlib import Path
import hashlib, os, tempfile, json

ROOT = Path(__file__).resolve().parents[3]
Z = ROOT / 'zdoc'
TOOLS = Z / '8-9-godot-blender-agent-studio-plan.txt'
GAME = Z / '8-9-hh-world-gameplay-viet-nam-plan.txt'
SNAP = Path(__file__).resolve().parent / 'before'

def load(p):
    return p.read_text(encoding='utf-8-sig')

def atomic(p, s):
    fd, name = tempfile.mkstemp(prefix=p.name+'.', suffix='.tmp', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(s)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name): os.unlink(name)

def once(s, old, new, label):
    n=s.count(old)
    if n != 1: raise RuntimeError(f'{label}: expected 1, got {n}')
    return s.replace(old,new,1)

def line_once(s, predicate, new, label):
    lines=s.splitlines(True); hits=[i for i,x in enumerate(lines) if predicate(x)]
    if len(hits)!=1: raise RuntimeError(f'{label}: expected 1, got {len(hits)}')
    i=hits[0]; nl='\n' if lines[i].endswith('\n') else ''
    lines[i]=new+nl
    return ''.join(lines)

def between(s, start, end, new, label):
    a=s.find(start); b=s.find(end, a+len(start))
    if a<0 or b<0: raise RuntimeError(f'{label}: anchor missing')
    return s[:a]+new+s[b:]

# Tools: only routing/claims that were stale; the technical contract remains intact.
t=load(TOOLS)
t=line_once(t, lambda x: 'repo hoan-hao do owner' in x,
       'repo mới `hh-game-studio/8-9-hh3d-3/zdoc/`; chỉ mở quyền tài liệu, không quyền dịch vụ.', 'tools-root')
t=once(t, 'ứng viên Godot4.7.2-stable standard + matching export templates, Blender5.2.1LTS;',
       'Godot và Blender theo candidate lock được kiểm chứng tại GT-01', 'tools-version-claim')
t=once(t, './8-9-hh-studio-godot-blender-hh-world-plan.txt (history only)\n./8-9-hh-studio-godot-blender-hh-world-plan.txt',
       'File gộp lịch sử: `./8-9-hh-studio-godot-blender-hh-world-plan.txt` (chỉ đọc, không có hiệu lực và không phải dependency).', 'tools-history')
t=once(t, './reviews/20260908/REVIEW-RESULT.md',
       './reviews/20260908-r3/REVIEW-RESULT.md', 'tools-review-path')
t=t.replace('bỏ tools→game dependency', 'bỏ việc bắt tool chờ gameplay; dependency một chiều GT-10→H2-P0-01 vẫn giữ')
atomic(TOOLS,t)

# Game: restore missing decision/consumer sections, correct package ownership, and make scale gates measurable.
g=load(GAME)
g=between(g, 'File TXT ở sibling hoan-hao', 'Bản gộp U2',
       'Hai plan hiệu lực nằm trong `hh-game-studio/8-9-hh3d-3/zdoc/`; chỉ coordinator cập nhật plan.\nKhông cho phép sửa các dịch vụ xã hội/địa lý đang vận hành.\n\n', 'game-root')
g=once(g, 'Mục lục: 1 Lựa chọn; 2 Consumer contract; 3 Game/online/durability/geo;',
       'Mục lục: 1 Lựa chọn; 2 Consumer contract; 3 Game/online/durability/geo;', 'toc-anchor')
decision='''1. LỰA CHỌN VÀ QUYẾT ĐỊNH KIẾN TRÚC\n\nGodot native + Blender là tuyến chính cho client 3D và pipeline asset. Không fork/clone/sửa C++ Godot ở v0.1: chi phí rebase, build template, bảo mật và tương thích plugin vượt lợi ích khi chưa có profiling chứng minh. Dùng stock pin, adapter và contract để có thể mở gate fork riêng sau benchmark nếu một thiếu hụt đo được không thể giải bằng plugin/GDExtension.\n\nGameplay authored chạy trước; dữ liệu bản đồ Hoàn Hảo/OSM chỉ tích hợp sau alpha. Bản đồ là lớp dữ liệu, không phải authority gameplay. Mobile/desktop là client; server headless chỉ mô phỏng và không render.\n\nMục tiêu “hàng trăm triệu” là account/record dài hạn với sharding, CDN, queue và room placement; không hứa hàng trăm triệu người trong một room. v0.1 giới hạn 32 người/room, tăng chỉ khi Q04 có số đo.\n\n'''
consumer='''2. HỢP ĐỒNG CONSUMER NHẬN GÓI GT-10\n\nGame chỉ nhận package GT-10 có manifest bất biến: engine/template hash, schema/protocol version, addon/API version, asset manifest, license/attribution, source closure hash và rollback pointer. H2-P0-01 phải kiểm chữ ký/hash, compatibility matrix, path dưới product root và capability allowlist trước khi cài. Không copy studio source, không chạy Blender trong runtime, không để game tự tải binary/plugin từ mạng.\n\nImport là PREPARED → VALIDATED → ACTIVATING → COMMITTED; lỗi/timeout/đóng editor quay về last-good, không partial write. Mọi command có command_id duy nhất, retry dedupe, lease/fencing và readback postcondition. Editor và Play là process riêng; object Godot chỉ main thread; token loopback không ghi log.\n\nGame được phép dùng adapter consumer, fixture và evidence; không sửa `studio/**` trực tiếp. Nếu package thiếu capability, ghi GAP và dừng WP phụ thuộc; không lặng lẽ dùng bản engine khác.\n\n'''
g=once(g, '3. GAME HH WORLD: GAMEPLAY TRƯỚC, VIỆT NAM SAU', decision+consumer+'3. GAME HH WORLD: GAMEPLAY TRƯỚC, VIỆT NAM SAU', 'insert-sections')
g=once(g, 'H2-P0-01 — Toolchain', 'H2-P0-01 — Consumer package intake', 'p001-title')
g=once(g, 'BUILD: verify Godot4.7.2 standard + matching templates/full commit/SHA256; Blender5.2.1 LTS (fallback4.5.13 theo mục1), bundled Python/addon/exporter versions;\npin tool versions/path và room_server_os=Linux x86_64/headless; no clone/core edit;',
       'BUILD: nhận package GT-10 theo manifest; kiểm candidate Godot/Blender version, template, Python/addon/exporter, SHA256 và compatibility matrix bằng launcher. Pin version/path và room_server_os=Linux x86_64/headless; không clone/core edit; nếu candidate chưa được xác minh thì để UNKNOWN và không nghiệm thu.', 'p001-build')
g=once(g, '### H2-P1-01 — Editor tools\nALLOWED: game/addons/hh_world_tools/ generated từ package GT-10 và consumer tests; studio/** chỉ read-only package input, không source owner trong game.\nBUILD: consumer contract package GT-10 cho Godot-only editor mutations, loopback token/main-thread/',
       '### H2-P1-01 — Game consumer integration\nALLOWED: `game/addons/hh_world_tools/` generated từ package GT-10 và consumer tests; `studio/**` chỉ read-only package input.\nBUILD: tích hợp adapter theo consumer contract cho Godot-only editor mutations, loopback token/main-thread/', 'p101')
g=once(g, 'ALLOWED: local house placement, catalog shop mẫu, menus/settings, slice tests.\nBUILD: 1 phòng/12 catalog props (placeholder có plan thay), đặt/xoay/undo/save,',
       'ALLOWED: local house placement, catalog shop mẫu, menus/settings, slice tests.\nBUILD: 1 phòng/12 catalog props (placeholder có plan thay), đặt/xoay/undo/save; kiểm asset đi từ `.blend` thuộc user copy qua package GT-10 vào scene Godot, play/readback, reimport và rollback.', 'p204')
g=once(g, '100/300/1k/10k CCU fleet và synthetic records phải đo trước capacity review lớn\nhơn.',
       '100/300/1k CCU là các gate đo tăng dần khi có workload và ngân sách; 10k chỉ là thử nghiệm fleet có giới hạn trước capacity review, không phải điều kiện bắt buộc của v0.1. Account/record cardinality và realtime CCU là hai trục riêng; mọi claim phải ghi cap, p95/p99, RAM, egress, lỗi và cost.', 'scale-ladder')
g=once(g, '8.1 Các đợt làm việc, không phải bảng tiến độ thứ hai\n\nA: P0-01→P0-02→P0-03.',
       '8.1 Các đợt làm việc, không phải bảng tiến độ thứ hai\n\nA: GT-01→GT-10 của plan công cụ; sau khi GT-10 ACCEPTED mới H2-P0-01→P0-02→P0-03. P0-02/P0-03 có thể chuẩn bị tài liệu song song nhưng nghiệm thu theo bảng.\n', 'waves')
g=once(g, '9.2 Trạng thái thiết kế và lịch sử\nPLAN_DESIGN_REVIEW=SEE_EXACT_HASH_REPORT',
       '9.2 Trạng thái thiết kế và lịch sử\nPLAN_DESIGN_REVIEW=SEE_EXACT_HASH_REPORT', 'review-anchor')
g=once(g, './reviews/20260908/REVIEW-RESULT.md', './reviews/20260908-r3/REVIEW-RESULT.md', 'game-review-path')
g=once(g, 'scale envelope: account-record khác realtime CCU, stateless/', 'scale envelope: account-record khác realtime CCU, stateless/', 'scale-anchor')
g=once(g, 'Hàng trăm triệu là mục tiêu dài hạn về tài khoản/record và phân vùng dữ liệu,\nkhông phải sức chứa một room/client.',
       'Hàng trăm triệu là mục tiêu dài hạn về account/record và phân vùng dữ liệu, không phải sức chứa một room/client. Trước public phải có migration rehearsal, shard-directory/placement, hot-key mitigation, deletion/tombstone propagation, quota/cost guard và capacity evidence cho từng tier. Không chuyển từ một PostgreSQL sang shard bằng phép đổi config; phải dual-read/dual-write có kiểm chứng, backfill idempotent, reconcile và rollback.', 'scale-final')
atomic(GAME,g)

print(json.dumps({'tools_sha256':hashlib.sha256(TOOLS.read_bytes()).hexdigest(), 'game_sha256':hashlib.sha256(GAME.read_bytes()).hexdigest()}, ensure_ascii=False))
