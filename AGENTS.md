# AGENTS.md — HH Game Studio

Bạn là AI agent triển khai sản phẩm. Repo này CHƯA có code sản phẩm cho đến khi
bạn (hoặc agent khác) làm work package. Mục tiêu: IDE làm game AI-native,
2D hoàn thiện (M-1 → M9). Không đụng mạng xã hội Hoan Hao.

## Đọc theo thứ tự này — không nhảy cóc

1. File này (`AGENTS.md`).
2. `zdocs/16-8-game-studio-execution-plan-cho-ai-agent.txt` — **Phần A**
   (giao thức), rồi **WP chưa tick đầu tiên** ở Phần B/C/E.
3. Chỉ những mục SPEC được WP trỏ tới trong
   `zdocs/16-8-game-studio-ai-native-ide-2d-first-master-plan.txt`.
4. Làm đúng WP đó. Không tự mở WP sau, không tự thêm ngôn ngữ/framework.

SPEC (master plan) = WHAT/WHY. Execution plan = THỨ TỰ + VERIFY + TIẾN ĐỘ.
Xung đột: SPEC thắng. Viết đề xuất vào `docs/DECISIONS.md` rồi **STOP**,
báo người — không sửa spec ngầm.

## Bất biến (vi phạm = reject PR) — chi tiết I1–I13 ở master 0.3

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

## Verify chuẩn (mỗi WP, trừ khi WP ghi khác)

```
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --workspace
```

E2E smoke (từ M0 khi có CLI): phiên master 10.2. Bằng chứng dán vào ô LOG của WP.

## STOP — dừng, không tự quyết

Gate G1, G3–G6 (G2 đã resolved); spike M-1a fail (fallback Bevy); cần lệch spec;
acceptance fail 2 lần;
cần người (API key, review, cắt scope). Xem execution plan Phần A.

## Tiến độ & commit

- Tick `[x]` WP trong execution plan Phần E + ngày. Milestone xong: tick thêm
  bảng 0.1 master plan.
- Commit: `M<x>-WP<n>: <mô tả ngắn>` (vd `M-1-WP-a: renderer 3-target spike`).
- Code ở **root repo** (Cargo.toml ở gốc). `gamestudio/` trong spec = root này.
