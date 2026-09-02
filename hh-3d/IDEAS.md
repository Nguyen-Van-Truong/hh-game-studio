# Ý tưởng hh-3d

Một trang, không login, không database ở vòng 1. Mỗi ý tưởng phải gốc
(tên, địa hình, màu, landmark riêng) — không copy Pelago / Saltwind / Y8.

## Nên làm trước

### 1. Hòn Gió — vịnh voxel Việt Nam

Bản “xin chào kỹ thuật”. Biển khối pastel, 1 đảo, hải đăng sọc, cầu gỗ,
thuyền thúng, vài nhà mái ngói, 3 góc camera, 1 card editorial.

Vì sao trước: học đúng kỹ thuật của clip (instancing, overlay HTML, camera
preset) mà không sao cảnh Bắc Âu. Sau này đảo này thành “hồ sơ” hoặc
“cổng studio”.

Độ khó: thấp. Thời gian: 1–3 ngày agent + chỉnh tay.

### 2. Quần đảo Studio

Mỗi đảo = một sản phẩm: Harbor (HH Game Studio), Arena (Vault Fighters),
Vault (Kho Bí Ẩn — chỉ diorama, không port Godot). Click đảo mở card +
nút Play dẫn sang game thật.

Vì sao: dùng được ngay cho trang studio, không cần backend.

Độ khó: thấp–trung. Làm sau khi Hòn Gió chạy mượt.

## Gắn Hoan Hao social (sau, khi có khung 3D)

### 3. Đảo hồ sơ

User id → seed → hình dạng đảo, màu, 3 vật phẩm. Không cần MMO: một
người xem một đảo, URL `/island/:id`.

### 4. Chợ đêm voxel

Mỗi gian = một bài / một món. Hover sáng, click mở card. Camera đi dọc
phố đèn lồng.

### 5. Sân sự kiện

Một bến + sân khấu + đồng hồ countdown. Dùng cho drop game, watch party,
ra mắt map. Vẫn là một scene tĩnh + UI, không chat realtime ở v1.

### 6. Minigame xã hội nhỏ

Đạp xe quanh đảo, câu cá, đua thuyền thúng 1 người (ghost time). Lưu
điểm localStorage trước, bảng xếp hạng sau.

## Gắn game Godot (chỉ lobby / diorama)

### 7. Diorama Vault Fighters

Map 2D “dựng đứng” thành mô hình giấy, xoay xem, bấm landmark đọc lore.
Không chơi combat trên web. Nút Play mở bản Godot.

### 8. Phòng relic Kho Bí Ẩn

Một phòng 3D nhỏ, relic ở giữa, ánh sáng chậm. Không copy scene Godot,
không mở WP Kho Bí Ẩn.

## Ý tưởng “đẹp nhưng nên để sau”

- Bản đồ cộng đồng nhiều người cùng lúc (cần server + sync).
- Marketplace thanh toán trong scene 3D.
- Avatar editor đầy đủ + inventory.
- Port gameplay Vault Fighters sang Three.js — sai stack, đừng làm.

## Không làm

- Copy layout / tên / asset Pelago, Saltwind, Superfighters.
- Nhét `hh-3d` vào checkbox plan 29-8.
- Fork Godot hay mix process Godot + Vite trên cùng product path.
