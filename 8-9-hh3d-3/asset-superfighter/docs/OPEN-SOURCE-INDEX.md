# Superfighters — source mở & repo cộng đồng (2026-10-17)

## Không tồn tại (công khai)

| Nguồn | Trạng thái |
|-------|------------|
| MythoLogic — **Superfighters Flash / Y8 HTML5** | **Không open source.** Dev từng nói *có thể* mở sau, chưa release (forum 2020). |
| **Superfighters Deluxe** (Steam, C#) | **Engine obfuscated** — không có repo game gốc; chỉ script/mod cộng đồng trên nền bản mua. |
| Godot/JS **remake hoàn chỉnh** giống Y8 | Không có repo mature; cộng đồng đang tự làm (Reddit 2026). |

**Phiên bản riêng bạn đang xây:** `8-9-hh3d-3/superagent/` (Godot, source thật của HH).

---

## Đã tải vào `reference/third-party-repos/`

| Thư mục | GitHub | License | Dùng để |
|---------|--------|---------|---------|
| `HaydenBat-Superfighters/` | [HaydenBat/Superfighters](https://github.com/HaydenBat/Superfighters) | (none on repo) | Recreation **C++** Flash SF — skeleton, không phải Y8. |
| `MythoFame-SFR/` | [MythoFame/SFR](https://github.com/MythoFame/SFR) (= Odex64/SFR) | Other / mod terms | **Superfighters Redux** — mod **C#** cho **SFD Steam**; đọc weapon/skin logic, **cần game SFD** để chạy. |
| `Hammad-hab-Super-Fighters/` | [Hammad-hab/Super-Fighters](https://github.com/Hammad-hab/Super-Fighters) | (none) | Export decompile (scripts/, sprites/, sounds/) — trùng ý với `src-superfighter/decompiled/`. |
| `NearHuscarl-ScriptLinker/` | [NearHuscarl/ScriptLinker](https://github.com/NearHuscarl/ScriptLinker) | **BSD-3-Clause** | Tool hỗ trợ script **SFD** (không phải classic Y8). |
| `MythoFame-SFD-MapTranslationProject/` | [MythoFame/SFD.Scripting.MapTranslationProject](https://github.com/MythoFame/SFD.Scripting.MapTranslationProject) | **MIT** | DB dịch map SFD — tham khảo data map, không phải engine. |

Clone lệnh (đã chạy): `git clone --depth 1 <url> reference/third-party-repos/<folder>`

---

## “Source mở” gần classic Y8 nhất (trong workspace, không phải GitHub game)

| Mục | Path |
|-----|------|
| ActionScript decompile (594 class) | `reference/src-superfighter/decompiled/scripts/` |
| SWF gốc | `reference/src-superfighter/superfighters-classic.swf` |
| Tool decompile (GPL) | `reference/tools/ffdec.jar` — upstream [jpexs-decompiler](https://github.com/jindrapetrik/jpexs-decompiler) |

Đây là **reference để đọc/port**, không license “open source game” từ MythoLogic.

---

## Repo GitHub khác (chưa clone — ít liên quan Y8)

| Repo | Ghi chú |
|------|---------|
| [retrooper/superfighters](https://github.com/retrooper/superfighters) | Mini game **Sprig** (JS), không phải Superfighters thật. |
| [L4igi/PlatformFighterGodot](https://github.com/L4igi/PlatformFighterGodot) | Platform fighter kiểu **Smash**, không SF. |
| SFD script packs (LGPL/MIT) | BotExtended, SFDScripts, SFD.Items — cần **Superfighters Deluxe**. |

---

## Nên đọc code ở đâu cho game riêng (Godot)?

1. **Classic mechanics:** `reference/src-superfighter/decompiled/scripts/Code/`  
2. **Deluxe / weapon ideas (C#):** `reference/third-party-repos/MythoFame-SFR/SFR/`  
3. **Implement của bạn:** `superagent/game/`, `superagent/data/tuning.json`

Không merge asset SFD/SFR vào `superagent` mà không kiểm license + NOTICE.
