# HH Game Studio

IDE làm game AI-native. **20-8-2026:** reboot sang Godot stock + Agent Autopilot.
Engine Rust/`gs-*` đã đóng băng; không mở WP M6/M7/M8 cũ.

## Chạy trên máy này (Windows)

1. Cài pin (một lần): `tools\godot\doctor.ps1 -Install`
2. **Bấm** [`hh-godot-editor.bat`](hh-godot-editor.bat) — mở Godot **4.7.1-stable** trên fixture `godot/test-projects/minimal-2d`.

Đó chưa phải game chơi được. Chưa có plugin agent / MCP (R2, khóa đến G1).

## Agent mới bắt đầu từ đây

1. Đọc [AGENTS.md](AGENTS.md)
2. Đọc [zdocs/20-8-godot-agent-autopilot-plan.txt](zdocs/20-8-godot-agent-autopilot-plan.txt) — bảng tổng quan, rồi WP chưa tick đầu tiên (**R0-WP4**)
3. Quyết định: [docs/DECISIONS.md](docs/DECISIONS.md) — `GODOT-REBOOT-2026-08-20`

Hai file `zdocs/16-8-game-studio-*.txt` là **LEGACY / NON-AUTHORITATIVE**. Không lấy WP mới từ chúng.
Khôi phục engine cũ: [legacy/README.md](legacy/README.md).
