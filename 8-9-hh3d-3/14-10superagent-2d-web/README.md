# Superagent 2D Web — phạm vi tài liệu

Đây là nhánh Web độc lập. Plan riêng hiện hành là [14-10-superagent-2d-web-plan.md](zdoc/14-10-superagent-2d-web-plan.md). Tài liệu này có `AUTHORITY=0`: không thay thế, không tick và không đổi `CURRENT_VALID_WP` của [kế hoạch gốc](../../zdoc/18-9-superagent-2d-y8-plan.txt). Kế hoạch gốc hiện vẫn là nguồn tiến độ Classic của sản phẩm Godot và đang ở SA-02.

Khuyến nghị hiện tại:

- **Runtime:** Phaser 4.2.1, pin chính xác trong lockfile sau khi chạy vertical slice; nếu một plugin bắt buộc chưa tương thích thì spike lại trên Phaser 3.90 trước khi quyết định.
- **Ngôn ngữ:** TypeScript cho source; JavaScript thuần chỉ dùng cho spike rất nhỏ.
- **Build:** Vite, tạo static bundle `dist/` để phát hành HTTPS.
- **Bố cục:** Canvas/WebGL cho game world; HTML/CSS cho landing page, menu, HUD và touch overlay.
- **Classic trước:** local 1P-vs-bot và 2P cùng bàn phím; online, Hero/MUGEN, chỉnh trang phục, 2.5D/3D và WebGPU chỉ mở sau khi Classic đạt gate.

Bản Web giữ các hợp đồng gameplay của plan gốc: fixed-step 60 Hz, `InputFrame` immutable, pressed/held/released, seed/replay/hash, simulation tách presentation, clean-room asset và parity ledger R01–R15. Tên hiển thị, code, hình, âm thanh, UI và hình học map cụ thể phải nguyên bản.
