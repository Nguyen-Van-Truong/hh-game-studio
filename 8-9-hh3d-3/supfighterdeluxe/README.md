# Superfighters Deluxe — source & modding bundle

**Ngày tải:** 2026-10-17  
**Thư mục:** `8-9-hh3d-3/supfighterdeluxe/`

## Quan trọng: không có “src game gốc” công khai

| Thành phần | Có trên GitHub? |
|------------|-----------------|
| **Superfighters Deluxe** (Steam, MythoLogic) | **Không.** Engine/client obfuscated (`Core.dll`, XNB, …). Cần mua Steam để chạy. |
| **Superfighters Redux (SFR)** | **Có** — mod C# mở, patch Harmony lên bản Steam; ~114 file `.cs` weapon/UI/sync. |
| **Script map (GameScriptInterface)** | **Có** — hàng trăm script C# cộng đồng (BotExtended, SFDScripts, …). |
| **Tool modding / RE docs** | **Có** — SFD.Modding, SFD-Repacker, ScriptLinker, DeluxeBench (repo đã gỡ — xem bên dưới). |

Deluxe **không** được MythoLogic publish như Flash decompile. Cộng đồng reverse/mod trên nền game đã mua; SFR/SFDCT là nguồn C# đọc được nhiều nhất.

---

## Cấu trúc

```
supfighterdeluxe/
  README.md          ← file này
  MANIFEST.csv       ← URL + commit từng repo
  repos/             ← git clone --depth 1
```

---

## Repo đã tải (`repos/`)

| Folder | GitHub | Đọc để |
|--------|--------|--------|
| **Odex64-SFR** | [Odex64/SFR](https://github.com/Odex64/SFR) | **Mod Redux** — weapons, projectiles, UI, sync; tham khảo API SFD qua Harmony. Entry: `SFR.sln`, `SFR/Weapons/`. |
| **Liokindy-SFDCT** | [Liokindy/SFDCT](https://github.com/Liokindy/SFDCT) | Addon tương thích vanilla; build cần Steam SFD + `Core.dll` (CONTRIBUTING). |
| **NearHuscarl-BotExtended** | [NearHuscarl/BotExtended](https://github.com/NearHuscarl/BotExtended) | Bot AI + vũ khí script; mẫu `GameScriptInterface`. |
| **Juansero29-SFDScripts** | [Juansero29/SFDScripts](https://github.com/Juansero29/SFDScripts) | Bộ script host map (INTERNAL/EXTERNAL), LGPL-2.1. |
| **NearHuscarl-ScriptLinker** | [NearHuscarl/ScriptLinker](https://github.com/NearHuscarl/ScriptLinker) | IDE ↔ SFD script compile (BSD-3). |
| **Juansero29-SFDScriptInjector** | [Juansero29/SFDScriptInjector](https://github.com/Juansero29/SFDScriptInjector) | Inject script vào `.sfdm`. |
| **MythoFame-SFD.Modding** | [MythoFame/SFD.Modding](https://github.com/MythoFame/SFD.Modding) | Ghi chú RE: texture, sound, map, cosmetic (MIT). |
| **MythoFame-SFD-MapTranslationProject** | [MapTranslationProject](https://github.com/MythoFame/SFD.Scripting.MapTranslationProject) | DB dịch map + script (MIT). |
| **Odex64-SFD-Repacker** | [Odex64/SFD-Repacker](https://github.com/Odex64/SFD-Repacker) | Pack/unpack XNB, PNG/WAV, cosmetic ITEM (MIT, C++). |
| **dsafxP-SFD.Templates** | [dsafxP/SFD.Templates](https://github.com/dsafxP/SFD.Templates) | Template project script SFD. |
| **dsafxP-SFD.ScriptTools** | [dsafxP/SFD.ScriptTools](https://github.com/dsafxP/SFD.ScriptTools) | F# tools: weld script, setup `GameScriptInterface.dll`. |
| **FrostiestBunny-SFDMaps** | [FrostiestBunny/SFDMaps](https://github.com/FrostiestBunny/SFDMaps) | Map mẫu (cũ, 2017). |

**Không clone được:** [Liokindy/DeluxeBench](https://github.com/Liokindy/DeluxeBench) — `remote: Repository not found` (có thể private/xóa). Tool item `.item` ↔ PNG vẫn có trong release cũ nếu bạn tìm mirror.

Bản trùng một phần (classic Flash, không phải Deluxe):  
`8-9-hh3d-3/asset-superfighter/reference/third-party-repos/MythoFame-SFR/`

---

## Công nghệ Deluxe (tham khảo khi port sang Godot)

- **C#**, **XNA 4.0** → runtime **FNA** / MonoGame lineage  
- **Box2D** (C# port), **Lidgren.Network**, **NAudio**, **Nuclex.Input**  
- Asset: **XNB**, `.item`, `.sfdx`, `.sfdm`, …

SFR/SFDCT **không** thay thế full source; chúng **patch** `Core.dll` và ship content mod.

---

## Chạy / build (cần Steam)

1. Cài [Superfighters Deluxe](https://store.steampowered.com/app/855860) trên Steam.  
2. **SFR:** release GitHub → giải nén vào thư mục game; launch options:  
   `cmd /k "%command%\..\SFR.exe"`  
3. **Script:** copy `.txt` script vào  
   `%USERPROFILE%\Documents\Superfighters Deluxe\Scripts\`  
   hoặc dùng ScriptLinker + `SFD.GameScriptInterface.dll` từ thư mục game.  
4. **SFDCT:** xem README trong `repos/Liokindy-SFDCT` (version lock theo release SFD).

Không copy asset SFR/SFD vào product Godot (`superagent` / Vault Fighters) mà chưa kiểm license và NOTICE.

---

## Đọc code nhanh

| Mục tiêu | Path |
|----------|------|
| Logic vũ khí mod | `repos/Odex64-SFR/SFR/Weapons/` |
| Projectile | `repos/Odex64-SFR/SFR/Projectiles/` |
| Script gameplay map | `repos/Juansero29-SFDScripts/SFDScripts/` |
| Bot / boss | `repos/NearHuscarl-BotExtended/src/` |
| Format file / modding | `repos/MythoFame-SFD.Modding/` |

Classic Flash (Y8) vẫn nằm ở `8-9-hh3d-3/asset-superfighter/reference/src-superfighter/` — **khác** engine với Deluxe.
