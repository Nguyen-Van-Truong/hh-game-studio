# Công cụ để người và agent cùng làm trong Godot

## T01 — Pin và bố trí engine

Godot 4.7.2-stable standard official là lựa chọn kế hoạch, không dùng floating
`latest`, không .NET cho game typed GDScript mặc định. P0 xác minh release,
full commit, checksum binary/editor/export templates cho từng OS, license,
download domain, archive hash và `--version`; tạo `tools/engine.lock.json`.
Không tải lại nếu cache đúng checksum đã có. Không chạy binary khác pin để
“test nhanh” rồi ghi official PASS. Version nguồn docs phải ghi cùng report.

Project Git chứa lock và launcher, không chứa toàn bộ source engine/binary.
Source mirror tùy chọn chỉ khi cần debug/đọc code, ở checkout riêng hoặc
`.local/godot-source/` ignored; khớp tag và read-only. Không clone trong lượt
PLAN_ONLY. Cần custom core: gap repro + stock comparison + extension analysis
+ upgrade/security/export burden + rollback + owner quyết định riêng.

Nâng engine: branch riêng, giữ binary cũ, snapshot trước import, run import/
logic/editor/replay/network/art/perf/device matrix, kiểm tra save/protocol.
Không tự chạy editor mới lên source đang mở hoặc hạ version với cache mới.
Rollback code/content/save theo schema, reimport sạch đúng version.

## T02 — Không biến việc làm tool thành dự án engine mới

Xây bộ semantic command nhỏ đủ cho slice: create/open scene, instantiate
approved asset, set typed properties, connect approved signal, save transaction,
run snapshot, read scene/runtime state, stop. Mở rộng tool khi WP game cụ thể
cần, không xây một editor tổng quát trước gameplay.

GDScript, shader, backend, schema, tests và tài liệu được worker sửa qua file
trong lease; phải parse/validate và dùng Git diff. Scene/resource editor-owned
(`.tscn/.tres`) ưu tiên semantic EditorPlugin + EditorUndoRedoManager. Bootstrap
project/template được tạo bằng generator/schema có output xác định rồi import
đọc lại; không cấm mọi text edit đến mức không thể tạo project đầu tiên.
Không sửa raw scene đang mở trong editor. Không viết `.godot` cache như source.

## T03 — Hợp đồng command/transaction

Mỗi mutation có command_id duy nhất, schema_version, project_id, lease_id,
expected_revision, target path/object, operation, payload và payload_hash.
Validate type/range/path/quyền/asset references trước apply. Canonical path
phải nằm trong project allowlist; chặn traversal, symlink/junction/reparse
escape. Path chứa Unicode/space phải có test. Loopback bind + token phiên,
không token trong argv/log/screenshot. Không expose editor API ra Internet.

Object Godot thao tác trên main thread. Command async từ worker phải queue
lên main thread; không giữ stale ObjectID qua scene reload. UndoRedo action
có do/undo cho toàn bộ thay đổi. Save multi-file dùng staged outputs + journal
+ rollback khi fail; không giả một `commit_action` tự làm mọi file atomic.
Sau apply/save đọc lại node/properties/resource từ Godot, compare hash/revision,
rồi ACK. Cùng id/payload retry trả cùng result; khác payload cùng id reject.

Test tối thiểu: create+undo+redo phục hồi cùng semantic state; invalid command
không đổi source; crash giữa save không partial scene; duplicate id không nhân
node; stale revision conflict; missing lease reject; postcondition thất bại
trả failure có rollback proof, không báo OK chỉ vì command đã gửi.

## T04 — Owner edit, lease và runtime

Một writer/file, lease ghi owner/paths/base_hash/expiry; writer khác hoặc
owner edit làm revision khác thì tạm dừng apply, refresh diff/reconcile.
Không overwrite thay đổi người dùng. Không locks vĩnh viễn; expiry kiểm tra
process và outstanding transaction trước giải phóng, FIFO cho hàng chờ.

Editor và Play tách process. Official run từ snapshot content-hash bất biến;
client A/B/server có runtime/user-data/log path riêng. Preview owner dùng
source được save rõ; không ghi runtime node từ editor như bằng chứng gameplay.
Cursor/gizmo replay chỉ giúp người xem thấy thao tác, không là mutation source.

Pause/Stop ưu tiên trên queue; phân biệt Solo pause và Online menu. Stop drain
pending commands, ghi ACK/failure/retryable status trước shutdown, host capture
exit/leftovers. Không `taskkill` rồi ghi PASS. Timeout là FAIL/INCOMPLETE có log.

## T05 — Pipeline art

Asset source của mình hoặc license rõ; Blender/DCC → glTF/GLB → import preset
đã pin. Ghi units (1 Godot unit = 1 m), axis/origin, scale, collision proxy,
material atlas, skeleton/bone names, animation names và license/source hash.
Không copy toàn bộ asset cũ chỉ vì cùng repo; phải audit quyền và style.

Một hero avatar look-dev với trang phục phối hợp, skin weights, loop chân,
root motion policy trước khi sinh thêm biến thể. Feet sliding, xuyên áo,
normal/tangent lỗi, chữ Việt vỡ là lỗi chất lượng. Collision đơn giản tách
render mesh. Prop lặp dùng instancing/MultiMesh theo chunk nhỏ phù hợp culling;
không gom cả thành phố thành một mesh không thể loại vùng khuất.

LODs avatar/prop/building, material count, texture size và animation update
rate theo budget Q02. Bóng local chỉ cho đối tượng có giá trị; bake/static
lighting nếu hợp cảnh. Nameplates pool và distance gating; UI layout không
update mỗi frame cho hàng trăm label. Tối ưu theo profile, không theo phỏng đoán.

## T06 — Agent tự kiểm tra và owner review

Tooling tạo screenshots/video có camera routes, input replay, simulation
snapshot và frame-time capture; owner có scene bookmark/replay để xem lại.
Replay authored input đi qua gameplay interface; teleport/debug fixture chỉ
bổ trợ. Mọi art/UX PASS cần cảnh đã chạy và góc nhìn player trên target.
Không dùng engine automation làm lý do hoãn feedback về game feel.
