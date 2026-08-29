# AGENTS.md — HH Game Studio

## ROUTE HIỆN TẠI — VAULT FIGHTERS / Y8-LIKE CLEAN-ROOM

Đây là route sản phẩm hiện hành cho `godot/dogfood/superfighters/`.
Kế hoạch thực thi theo scope duy nhất là:

`zdocs/29-8-vault-fighters-y8-parity-plan.txt`

File đó dùng `PLAN_SCOPE=godot/dogfood/superfighters` và
`PRODUCT_PLAN_AUTHORITY=1` theo scope product (không thêm một dòng
`AUTHORITATIVE_PLAN=1`, vì checker platform yêu cầu đúng một marker toàn repo).
WP hiện hành là `CURRENT_VALID_WP` trong plan 29-8 — trùng WP đầu tiên chưa
tick. Agent không nhảy cóc, không làm lại WP đã `[x]`, và không tự tick
checkbox.

Đường product hiện hành **là** làm **Vault Fighters** trong
`godot/dogfood/superfighters/`. Chỉ dẫn đóng băng closeout 20-8 về việc không
mở folder Superfighter **không** áp dụng cho route này; nó chỉ giữ lịch sử
59/60. Không rip Y8; tên hiển thị vẫn **Vault Fighters**.

Mục tiêu: làm **Vault Fighters**, một game Godot 2D arena platform shooter có
cơ chế và topology chức năng gần trải nghiệm Superfighters trên Y8 nhất có thể,
nhưng code, art, audio, tên hiển thị và asset nguyên bản. Người dùng chỉ đưa
brief/bấm Start và xem/review; agent tự làm, tự test, tự chơi bằng công cụ,
tự sửa, checkpoint và tạo review package.

### Parent platform closeout (đã đóng băng)

`zdocs/20-8-godot-agent-autopilot-plan.txt` vẫn là nguồn lịch sử/platform cho
closeout đang dừng ở `59/60`, `CURRENT_VALID_WP=R9-WP4`. Không tự mở hoặc tick
R9-WP4, G6, GX hay 60/60. Không dùng con số 59/60 làm tiến độ game Vault
Fighters. Không chạy tiếp WP Rust/`gs-*` sản phẩm mới. Snake
(`godot/plugin-project/snake/`, `tools/godot/drive_snake*.py`) không phải WP
tiếp theo.

`docs/DECISIONS.md` entries `GODOT-VF-Y8-2026-08-28` (new folder) and
`GODOT-VF-PLAN-2026-08-29` (29-8 product routing) là quyết định owner.
Nếu có xung đột giữa parent closeout và product scope, parent thắng cho
platform files; plan 29-8 thắng cho product files.

## ĐỌC THEO THỨ TỰ

1. File này.
2. Bảng tổng quan đầu `zdocs/29-8-vault-fighters-y8-parity-plan.txt`.
3. WP đầu tiên chưa tick trong plan 29-8 và chỉ các invariant/reference mà WP
   đó trỏ tới.
4. `PROJECT_BRIEF.md`, `KNOWN_ISSUES.md` và `NOTICE.md` trong product folder
   khi WP yêu cầu.

Không lấy hai file `zdocs/16-8-*` làm nguồn WP. Không lấy các checkbox trong
README, chat, evidence folder hoặc plan cũ làm tiến độ product.

## BẤT BIẾN PRODUCT (V-A1…V-A20)

Vi phạm một bất biến thì không merge/tick WP; ghi gap report và dừng phần lệch.

- V-A1: Godot stock 4.7.1-stable; không sửa C++/fork/GDExtension nếu owner
  chưa mở gate riêng sau gap report.
- V-A2: mọi mutation có semantic command, schema và validate trước apply.
- V-A3: editor mutation dùng UndoRedo/transaction atomic; không partial write.
- V-A4: mutating command có unique `command_id`; retry idempotent/dedup.
- V-A5: ACK chỉ sau postcondition đọc lại từ Godot/runtime.
- V-A6: path ghi/tham chiếu nằm dưới product root; chặn traversal/symlink.
- V-A7: Godot object chỉ trên main thread; editor và Play là process tách biệt.
- V-A8: bridge loopback + token; không ghi secret vào log/evidence/screenshot.
- V-A9: một writer/file; lease có owner/expiry/FIFO; conflict phải reconcile.
- V-A10: checkpoint trước destructive change; rollback có kiểm chứng.
- V-A11: Play từ immutable/snapshot phù hợp; editor không sửa runtime state.
- V-A12: Pause/Stop ưu tiên; drain/cancel an toàn, không mất ACK.
- V-A13: save temp+rename/atomic replace; schema/hash trong manifest.
- V-A14: input trace fixed 60 Hz, pressed/held/released rõ, có seed.
- V-A15: physics/combat deterministic trong pin/seed; epsilon được ghi.
- V-A16: fixture/teleport/force-kill không phải bằng chứng E2E duy nhất.
- V-A17: typed GDScript; official run không có warning/error chưa giải thích.
- V-A18: evidence có timestamp, run/trace/source hash và repro command.
- V-A19: không claim feature từ code/ảnh chưa chạy và chưa có postcondition.
- V-A20: claim “giống Y8” trỏ reference ledger; tuning/uncertainty phải ghi rõ.

## CLEAN-ROOM VÀ PHẠM VI GAME

- Có thể quan sát trang/game Y8 và nguồn công khai để hiểu behavior; không tải,
  rip, trace, reverse-engineer, bundle hay ship SWF/Flash/HTML5 package,
  sprite, audio, code, screenshot hoặc trademarked title card.
- Dùng tên sản phẩm **Vault Fighters**; không dùng Superfighters/Super Fighter
  trong title card, nhân vật, map display name hoặc metadata phát hành.
- Giữ functional beats (side-view, platform/pit, ladder, cover, pickup,
  hazards, combat loop), nhưng đổi geometry dimensions/coordinates, landmarks,
  tile language, item placement, characters và audio. Nếu layout quá gần để
  phát hành thương mại, dừng và yêu cầu legal review; không tự kết luận.
- Không đụng `godot/dogfood/kho-bi-an/`, Hoan Hao social, engine Rust cũ,
  `godot/plugin-project/snake/` hoặc `tools/godot/drive_snake*.py`. Snake là
  out-of-scope/untracked; không dùng làm evidence hay commit Vault Fighters.
- Không chạy RPA/pixel-click làm mutation source. Agent dùng EditorPlugin/API
  semantic; UI cursor/gizmo chỉ replay để người xem thấy thao tác.

## QUY TẮC THỰC THI CHO AGENT

- Kiểm tra `git status`, baseline hash và active processes trước khi làm.
- Một WP một commit (mẫu `VF<n>-WP<n>: <mô tả>`), hoặc ghi rõ vì sao chưa
  commit. Không đưa generated cache, token, `.godot`, build output, Snake hay
  reference asset vào commit.
- Mỗi run ghi `run_id`, `command_id`, seed, map/mode, source hash và evidence.
- Test nhanh bằng Godot pin/headless và test riêng của WP; không dùng
  `cargo test --workspace` làm verify cho product.
- Không mở Godot/test thứ hai nếu WP đang yêu cầu single-process official run.
- Coordinator mới được tick plan sau dependency + Verify + DoD + LOG + critic.
  Agent/critic không tự giả chữ ký V5 (human review) hoặc G6/E3.
- Chỉ hỏi người ở E1–E4: secret/tiền, ký-publish, legal/brand, hoặc đổi mục
  tiêu lớn. Mọi phần còn lại phải tự hoàn thành và tự báo gap.

## PARENT PLATFORM / LEGACY SAFETY

Các invariant I1–I13 của engine Rust chỉ áp dụng khi audit/khôi phục legacy,
không áp dụng để mở WP product mới. Không xóa/move hàng loạt code/asset/crate
cũ. Không rewrite Git phá hủy. Giữ Godot pin, MCP vendor lock và platform
tests nguyên trạng trừ khi một WP product ghi rõ file scope.

## VERIFY VÀ STOP

Mỗi WP phải dùng verify ghi trong chính plan 29-8. Routing/governance
(VF0-WP3): `python tests/bootstrap/test_authoritative_plan.py` và
`python tests/bootstrap/test_vault_fighters_plan.py` (cả hai exit 0). Nếu
source thay đổi sau critic, phải audit lại đúng source hash. PASS functional
nhưng còn leaked ObjectDB/AudioStream, duplicate/lost update, secret,
unproven postcondition, hoặc dirty source ngoài lease thì **chưa** là PASS
nghiệm thu.

STOP ngay khi agent định rip asset, fork Godot, mở G6/GX/R9-WP4, sửa Kho Bí Ẩn,
đưa Snake vào product, hoặc thay acceptance để hợp code đã lỡ viết.

## TIẾN ĐỘ

Chỉ `zdocs/29-8-vault-fighters-y8-parity-plan.txt` giữ checkbox VF0–VF10.
Parent `zdocs/20-8-*` giữ lịch sử 59/60 riêng. Không gộp hai bảng, không suy ra
% hoàn thành từ số checkbox.
