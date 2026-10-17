# Superfighters — “src trước khi build” (2026-10-17)

Mục tiêu: gom **mọi nguồn có thể** coi là material **trước build** (SWF, decompile, bundle Y8, repo cộng đồng).  
**Không có** `.fla` / project Animate / repo TypeScript Godot **chính thức** từ MythoLogic cho bản Y8.

---

## 0. Bản “khôi phục project” (2026-10-17)

**`reference/src-superfighter/restored-project/`** — gom SWF + 8017 asset decompile + **XFL CS5.5 (~2834 file)**.  
Đọc `README-RESTORED.md`. **Không** bằng `.fla` gốc MythoLogic; là tái dựng tối đa từ SWF.

---

## 1. Bản gần “full source classic Flash” nhất (trong workspace)

| Path | Nội dung | File count (ước) |
|------|----------|------------------|
| **`reference/src-superfighter/full-ffdec-export/`** | Export **đầy đủ** từ `superfighters-classic.swf` (gstore): **594 `.as`**, **6015 PNG**, **72 MP3**, SVG, font, text, binary | **8017** |
| `reference/src-superfighter/decompiled/scripts/` | Chỉ script (cùng SWF gstore) — trùng logic với `full-ffdec-export/scripts/` | 594 |
| `reference/swf-extract/exported/` | Sprite PNG export cũ (cùng game) | ~5800+ |

Tool: `reference/tools/ffdec.jar` (JPEXS 21.1.0).  
SWF nguồn: `reference/src-superfighter/superfighters-classic.swf` (= `mirrors/github-gstore-superfighters.swf`).

**Lưu ý:** Đây là **decompile + extract**, không phải `.fla` gốc. Sửa `.as` xong **không** tự build lại SWF/Y8 trừ khi bạn dùng Animate + pipeline riêng.

---

## 2. Nhiều bản SWF (mirror) — hash khác nhau

`reference/src-superfighter/mirrors/` + `MANIFEST.csv`

| File | AS3 classes (ffdec dump) | Ghi chú |
|------|--------------------------|---------|
| `github-gstore-superfighters.swf` | 594 | Bản dùng cho full export |
| `archive-575163_Superfighters.swf` | **599** | Newgrounds / Archive — **nhiều class nhất** trong bộ mirror |
| `github-swfgalaxy-superfightersultimate.swf` | 601 | Biến thể “ultimate” |
| `archive-superfighters.swf` | 442 | Archive — **cũ/hẹp hơn** |

Script-only thêm:

- `mirrors/decompiled-575163-scripts/` (599 `.as`)
- `mirrors/decompiled-ultimate-scripts/` (601 `.as`)

---

## 3. Y8 HTML5 — **không có** src trước build

Chỉ **artifact đã build** (IceStone / Flash→JS+WASM):

| Path | Ghi chú |
|------|---------|
| `reference/y8-html5-bundle/game-rvvASMiM/` | `index.html`, `sdk.1.2.js`, **`Superfighters.js` (~21 MB)**, `GDConfig.json` |
| CDN gốc | `https://html5.gamedistribution.com/rvvASMiM/a7a878d376bf4223adc51d2ba04fb77c/` |

CDN **không** public thêm file `.fla`/TypeScript; chỉ bundle trên.  
Chơi local: HTTP → `index.html` (đã có `GDConfig.json`).

---

## 4. Repo GitHub / cộng đồng (đã clone)

Xem `docs/OPEN-SOURCE-INDEX.md` và `reference/third-party-repos/README.txt`.

| Loại | Ví dụ | “Pre-build”? |
|------|-------|----------------|
| Recreation C++ | HaydenBat-Superfighters | Source C++ + PNG, **không** SF gốc |
| SFD mod C# | MythoFame-SFR | Mod **Deluxe Steam**, cần game gốc |
| Decompile mirror | Hammad-hab-Super-Fighters | Giống export FFDec |
| Mini clone JS | retrooper-superfighters | Sprig, không phải SF Y8 |
| Tool | NearHuscarl-ScriptLinker | SFD scripting |

Catalog tìm kiếm: `catalog/github-search-superfighters.json`.

---

## 5. Nguồn web (chưa / không tải full)

| Nguồn | URL | Trạng thái |
|-------|-----|------------|
| Internet Archive | [superfighters-flash-game](https://archive.org/details/superfighters-flash-game) | Đã tải 2 SWF + `superfighters.swf` |
| SWFChan decompile snippet | [96849](http://swfchan.com/20/96849/info.shtml) | Partial AS online — tham khảo |
| MythoLogic `.zip` official | mythologicinteractive.com/Superfighters.zip | **404** tại thời điểm crawl |
| MythoLogic **`.fla` SF** | Forum: chưa open source (2020) | **Không có public** |
| Barbarian Onslaught `.fla` | Forum MythoLogic (game khác) | Không phải Superfighters |

---

## 6. Project code **của bạn** (sửa được thật)

`8-9-hh3d-3/superagent/` — Godot, `choigame.bat`.  
Port mechanics từ `full-ffdec-export/scripts/Code/` → GDScript; **không** ship rip nguyên art/audio nếu chưa rõ license.

---

## Tóm tắt một câu

**“Src đầy đủ trước build” cho Superfighters classic = SWF + `full-ffdec-export/` (8017 file) + mirror SWF/script; Y8 = chỉ `Superfighters.js`; `.fla` MythoLogic không public.**
