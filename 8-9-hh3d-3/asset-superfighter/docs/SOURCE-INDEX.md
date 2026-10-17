# Superfighters — nguồn tải về (2026-10-17)

MythoLogic **không công bố** repo source chính thức cho bản Y8 HTML5. Trong workspace chỉ lưu bản **build công khai** + **decompile Flash classic** để tham chiếu parity (waiver `zdoc/16-10-owner-reference-asset-waiver.txt`).

## 1. Y8 / GameDistribution (HTML5 — bản đang chơi trên Y8)

| Mục | Đường dẫn local | URL gốc |
|-----|-----------------|---------|
| Wrapper + SDK | `reference/y8-html5-bundle/index.html`, `gamedistribution-sdk/main.min.js` | `https://html5.gamedistribution.com/a7a878d376bf4223adc51d2ba04fb77c/` |
| Game runtime | `reference/y8-html5-bundle/game-rvvASMiM/Superfighters.js` (~20.8 MB) | `https://html5.gamedistribution.com/rvvASMiM/a7a878d376bf4223adc51d2ba04fb77c/Superfighters.js` |
| Entry HTML game | `reference/y8-html5-bundle/game-rvvASMiM/index.html` | cùng thư mục `rvvASMiM/.../index.html` |

**Bản chất:** `Superfighters.js` là runtime **Adobe Animate → Apache Royale / WASM** (Flash API trong JS), **không phải** mã nguồn ActionScript đọc được. Logic gốc vẫn nằm trong SWF được nhúng/biên dịch.

Chạy offline (tham khảo): mở `game-rvvASMiM/index.html` qua HTTP local (file:// thường chặn WASM).

## 2. Flash classic (2011) — gần “source” nhất

| Mục | Đường dẫn local | URL gốc |
|-----|-----------------|---------|
| SWF gốc | `reference/src-superfighter/superfighters-classic.swf` (3 039 889 bytes, SHA256 `150507DA…E05D0`) | `https://github.com/BinBashBanana/gstore/raw/master/superfighters.swf` |
| Bản copy cũ | `reference/swf-extract/superfighters.swf` | (cùng hash nếu chưa đổi) |
| **ActionScript decompile** | `reference/src-superfighter/decompiled/scripts/` — **594 file `.as`** | JPEXS ffdec 21.1.0, lệnh trong `reference/src-superfighter/PROVENANCE.txt` |
| Sprite/image đã export trước | `reference/swf-extract/exported/` | (tool export sprite PNG) |

**Logic game (đọc code):** package `Code.*`, ví dụ:

- `decompiled/scripts/Code/Handler/GameMain.as`
- `decompiled/scripts/Code/Data/Players/Player.as`
- `decompiled/scripts/Code/Handler/Fires.as`, `Weapons.as`, `Projectiles.as`

Decompile **không** bằng source gốc của studio; dùng để hiểu hằng số, state, spawn — không copy nguyên văn vào sản phẩm phát hành.

## 3. Repo cộng đồng (không phải bản Y8)

| Repo | Local | Ghi chú |
|------|-------|---------|
| HaydenBat/Superfighters | `reference/third-party-repos/HaydenBat-Superfighters/` | Recreation C++ (2021), không phải code MythoLogic |

## 4. Công cụ trong folder

- `reference/tools/ffdec.jar` — JPEXS Free Flash Decompiler 21.1.0 (export script/sprite/sound).

## 5. Không có / không tìm thấy công khai

- GitHub chính thức MythoLogic cho Superfighters (Flash hoặc HTML5).
- Source `.fla` / project Animate gốc.
- Bundle HTML5 dạng TypeScript/Godot — chỉ có `Superfighters.js` monolith.

Official play: [Y8 Superfighters](https://www.y8.com/games/superfighters), [MythoLogic game page](https://mythologicinteractive.com/games/superfighters.aspx).
