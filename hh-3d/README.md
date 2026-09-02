# hh-3d

Playground web 3D (Vite + React + Three.js + React Three Fiber).
Không phải work package Vault Fighters. Không đụng `godot/`, Kho Bí Ẩn, hay Snake.

Demo hiện tại (`demo/`):

- Vite + React + TypeScript
- `three` + `@react-three/fiber` + `@react-three/drei`
- UI HTML đè lên canvas
- Voxel bằng `InstancedMesh`, không bắt buộc file `.glb` ở vòng 1

Mở demo Hòn Gió:

```bash
cd hh-3d/demo
npm ci
npm run dev -- --host 127.0.0.1
```

Trang mở đầu ở **Toàn cảnh**; chọn **Chơi** nếu muốn đi bộ/lên thúng. Đây là
developer-only WebGL diorama, chưa phải HH World, bản đồ thật hay GTA.

Full application và native Unreal (nếu sau này cần) vẫn nằm trong các plan
riêng dưới `zdoc/`, không phải dependency của demo này.

Danh sách ý tưởng: `IDEAS.md`.
