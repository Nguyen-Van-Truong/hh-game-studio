# Superfighters classic — bản “khôi phục source” (2026-10-17)

## Thật lòng trước

**Không thể khôi phục 100%** file `.fla` / project Adobe Animate **gốc** của MythoLogic (không public).  
Folder này là **tái dựng tối đa** từ bản **Newgrounds `575163`** (đầy đủ hơn bản GitHub gstore: có Survival, scoreboard, timer). Bản gstore cũ giữ ở `00-gstore.swf` và `../full-ffdec-export/`.

| Thành phần | Ý nghĩa | Giống src studio? |
|------------|---------|-------------------|
| `00-original.swf` | SWF Newgrounds 575163 (3 051 851 bytes) | Đúng build chơi được |
| `00-gstore.swf` | Bản GitHub gstore (thiếu Survival) | Giữ để so |
| `01-actionscript` … `10-morphshapes` | 599 `.as`, sprite, sound, morph | Decompile từ 575163 |
| **`xfl-export/Superfighters/`** | XFL CS5.5 (~2874 file) | Gần “src trước build” nhất |
| `package-index.json` | 599 file `.as` | Có `ScoreboardSurvival`, `SurvivalTimePackage` |
| `ruffle/` | Player Flash | Để `chay-game.bat` chạy offline |

Sửa `.as` / XFL **không tự build lại SWF** trừ khi bạn dùng Adobe Animate hoặc pipeline FFDec import — và kết quả có thể lệch bản gốc.

---

## Cấu trúc thư mục

```
restored-project/
  00-original.swf          SWF classic (SHA256 gstore)
  01-actionscript/         594 ActionScript 3 (Code.*, wpn_*, …)
  02-sprites/              Frame PNG theo sprite
  03-sounds/               MP3/WAV
  04-images/               Bitmap embed
  05-shapes/               SVG shapes
  06-fonts/                TTF
  07-texts/                Text export
  08-buttons/
  09-symbolClass/symbols.csv   characterId → class name
  xfl-export/Superfighters/    ~2834 file XFL (mở trong Animate)
  play-local.html + chay-game.bat
  tools/reexport-from-swf.ps1
```

Entry code game: `01-actionscript/Code/Main.as` → `GameMain`, `MenuMain`.

---

## Chơi bản đã khôi phục

```bat
chay-game.bat
```

Hoặc từ thư mục này: `python -m http.server 8766` → mở `http://127.0.0.1:8766/play-local.html`  
(Cần `../ruffle/` — cùng cấp với `restored-project`.)

---

## Mở / sửa như project Flash

1. **Adobe Animate** (hoặc JPEXS GUI): File → Open → `xfl-export/Superfighters/` (thư mục XFL).
2. Hoặc sửa trực tiếp `01-actionscript/` trong IDE (FlashDevelop, VS Code + AS3 plugin) — **chỉ đọc/sửa text**, build lại SWF là bước riêng.

Tái export từ SWF:

```powershell
.\tools\reexport-from-swf.ps1
```

---

## Giới hạn so với “nguyên src”

- Timeline, layer name, library link gốc: **mất một phần**  
- Code: decompiler đặt tên `param1`, `loc3_`, v.v.  
- Newgrounds API trong SWF: vẫn gọi khi chạy online features  
- **Y8 HTML5** (`Superfighters.js`) là **nhánh build khác** — không nằm trong folder này  

Game **sửa và phát hành riêng** (Godot): `8-9-hh3d-3/superagent/`.

---

## Pháp lý

Reference / học / mod cá nhân theo `asset-superfighter/NOTICE.txt` và waiver owner. Không ship thương mại asset gốc MythoLogic mà không có license.
