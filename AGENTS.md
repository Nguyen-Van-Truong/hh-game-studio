# AGENTS.md — HH Game Studio

## Hướng hiện tại — Godot Agent Autopilot (R0-WP2 cutover)

Người dùng đã chọn reboot: dừng WP mới của engine Rust/`gs-*`, làm Godot stock
+ Agent Autopilot. Quyết định: `docs/DECISIONS.md` — `GODOT-REBOOT-2026-08-20`.
Kế hoạch quyền lực duy nhất: `zdocs/20-8-godot-agent-autopilot-plan.txt`
(`AUTHORITATIVE_PLAN=1`).

R0-WP1 (đóng băng engine cũ) đã xong. File này **là** cutover R0-WP2 — không làm
lại R0-WP1 hay R0-WP2. **WP sản phẩm đầu tiên của agent mới là R0-WP3** (pin
Godot/toolchain; tạo `godot/` và `bridge/`). Coordinator tick checkbox / cập nhật
`CURRENT_VALID_WP`; agent sản phẩm không đợi và không tự tick.

Không làm WP-M6/M7/M8 của engine cũ. Không xóa code/asset/crate/game cũ. Không
fork Godot C++. Không đụng mạng xã hội Hoan Hao. Không tải/pin Godot và không
tạo `godot/` hay `bridge/` trước R0-WP3.

## Đọc theo thứ tự này — không nhảy cóc

1. File này (`AGENTS.md`).
2. `zdocs/20-8-godot-agent-autopilot-plan.txt` — bảng tổng quan đầu file, rồi WP
   chưa tick đầu tiên có dependency xanh **sau R0-WP2**. Đó là **R0-WP3**.
3. Chỉ các invariant/mục mà WP đó trỏ tới (A1–A20 và mục SPEC trong cùng file
   20-8). Không tự mở milestone xa.

Plan 20-8 gộp WHAT/WHY + thứ tự + verify + tiến độ. Xung đột với chat, README,
hay file 16-8: plan 20-8 thắng. Đề xuất lệch spec ghi `docs/DECISIONS.md` rồi
STOP — không sửa spec ngầm.

Hai file `zdocs/16-8-game-studio-*.txt` là **LEGACY / NON-AUTHORITATIVE**
(`AUTHORITATIVE_PLAN=0`). Chỉ dùng khi audit, khôi phục tree archive
(`legacy-rust-engine-2026-08-20`), hoặc đọc lịch sử. Không lấy WP mới từ Phần
A/B/C/E của chúng. Không theo 16-8 làm nguồn WP tiếp theo.

## Không làm

- Không mở WP `gs-*` / Cargo sản phẩm mới. `cargo fmt` / `clippy` / `test` chỉ
  khi audit hoặc khôi phục legacy.
- Không tick checkbox trong plan 20-8 trừ coordinator sau DoD thật.
- Không xóa/move hàng loạt crates, games, hay engine cũ.
- Không fork Godot; không pin binary Godot ngoài R0-WP3.

## Bất biến sống — A1–A20 (plan 20-8 §3)

Vi phạm = không merge / không tick WP. Đọc đầy đủ trong plan 20-8 mục 3; không
dùng I1–I13 cho WP Godot.

- A1: Godot stock; không sửa C++ khi Gate GX chưa được người tick.
- A2–A6: mutation semantic + UndoRedo/atomic write + `command_id` + postcondition.
- A7–A9: object Godot trên main thread; path dưới project root; loopback + token;
  không log secret.
- A10–A14: checkpoint trước destructive; Play là runtime riêng; Pause ưu tiên.
- A15–A20: không rewrite Git phá huỷ; pin version/hash; một writer mỗi file;
  GDScript typed; tick WP chỉ sau Verify + DoD + LOG.

## Bất biến legacy I1–I13 (engine Rust — chỉ audit/khôi phục)

Áp dụng khi đọc/sửa tree đóng băng, không khi làm WP Godot. Chi tiết master 16-8
mục 0.3.

- I1: 100% mutation document qua CommandDispatcher. View-state UI miễn.
- I2: validate → WAL (full command+inverse) → FLUSH → apply → ACK.
- I3: Play = process riêng từ snapshot bất biến. Editor không load Luau game.
- I4: Luau sandbox + memory limit + interrupt; chỉ compile source; mutation buffer.
- I5: JSON canonical; unknown field giữ round-trip.
- I6: tmp+rename; WAL append-only + checksum; truncated-tail OK, hỏng giữa thì dừng.
- I7: path ghi/tham chiếu dưới project root (ngoại lệ: asset.import src, build out_dir).
- I8: bus 127.0.0.1 + token; actor_id do server cấp; secret không vào log.
- I9: không thêm ngôn ngữ/framework lớn ngoài master 2.1.
- I10: không để code chết; spike trong `experiments/` rồi xóa.
- I11: mọi lệnh mutating có `command_id` ULID; dedup WAL-backed.
- I12: capability + pause + confirmation một lần (bind actor/hash/revision).
- I13: số hiệu năng là mục tiêu — chỉ viện dẫn sau khi benchmark trong repo.

## Verify

Mỗi WP dùng verify ghi trong chính WP đó và plan 20-8 §7.3 (sidecar npm / Godot
headless / E2E). Không lấy `cargo test --workspace` làm verify mặc định cho WP
Godot.

R0-WP2: `python tests/bootstrap/test_authoritative_plan.py` (exit 0).

## STOP

S1–S7 và gate G0–G6/GX: plan 20-8 §7.5–7.6. Chỉ hỏi người ở E1–E4 (secret, tiền,
ký/publish, đổi mục tiêu lớn).

## Tiến độ & commit

- Checkbox tiến độ chỉ trong `zdocs/20-8-godot-agent-autopilot-plan.txt`.
- Commit: `R<n>-WP<n>: <mô tả ngắn>` (vd `R0-WP3: pin Godot 4.7.1-stable`).
- Layout đích: plan 20-8 §4.1. `godot/` và `bridge/` thuộc R0-WP3.
