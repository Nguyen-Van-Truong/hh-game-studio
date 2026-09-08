# Agent Godot runbook — HH Game Studio

Hướng dẫn **cách agent phải chạy Godot trên máy này**. Không phải tutorial Godot
chung. Pin, `--path`, leftover-0, và host `WaitForExit` là hợp đồng nghiệm thu.

Display title: **Vault Fighters**. Không Superfighters trên title card / nhân
vật / map display / metadata phát hành. Parent platform vẫn **59/60**; không
mở G6 / GX / R9-WP4.

Nguồn pin: [`docs/VERSIONS_GODOT.md`](../VERSIONS_GODOT.md),
[`tools/godot/pin.json`](../../tools/godot/pin.json).
Product: `godot/dogfood/superfighters/`.
Play người: [`godot/dogfood/superfighters/README.md`](../../godot/dogfood/superfighters/README.md).

---

## 0. Thẻ lệnh tối thiểu (copy)

```powershell
$bin = Join-Path $env:LOCALAPPDATA "HHGodotAgent\tooling\godot-4.7.1-stable\bin"
$gui = Join-Path $bin "Godot_v4.7.1-stable_win64.exe"
$con = Join-Path $bin "Godot_v4.7.1-stable_win64_console.exe"
$prod = "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters"

# 1) leftover trên ĐÚNG --path này phải = 0 trước khi spawn
@(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match "Godot" -and $_.CommandLine -like "*$prod*"
}).Count

# 2) cài / xác nhận pin nếu exe thiếu
#    từ repo root: python tools/godot/doctor.py --install
#    --version phải là: 4.7.1.stable.official.a13da4feb

# 3) smoke headless (không phải official leftover-0)
& $con --headless --path $prod --quit-after 1

# 4) chạy một test script; host phải WaitForExit, lấy ExitCode thật
#    mẫu official: godot/dogfood/superfighters/tests/run_bots_official.ps1
```

Nếu lookup `%LOCALAPPDATA%\HHGodotAgent\...` thất bại: **đó không phải bằng
chứng Godot không có**. Pin nằm trên máy user, không trong git.

---

## 1. Pin — chỉ một Godot được phép

| Trường | Giá trị |
|---|---|
| Flavor | Standard **win64**, **không** Mono / .NET |
| Tag | `4.7.1-stable` |
| `--version` đúng | `4.7.1.stable.official.a13da4feb` |
| Cache (không git) | `%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\` |
| Cài / verify | `python tools/godot/doctor.py --install` rồi `python tools/godot/doctor.py` |

Hai binary **cùng zip**:

| File | Dùng khi |
|---|---|
| `bin\Godot_v4.7.1-stable_win64.exe` | Editor GUI; một số official **headless** (`--headless --script`) |
| `bin\Godot_v4.7.1-stable_win64_console.exe` | CLI, `--headless`, `--version`; **windowed official** (console twin) để host bắt stdout/stderr + `ExitCode` |

**Cấm:** `godot` trên PATH, Steam, Godot Hub, scoop/winget “latest”,
`npx -y latest`, TuxFamily, `*_mono_*`, **mọi 4.7.2\***, **mọi 4.8\***, fork
C++ / GDExtension (V-A1) trừ khi owner mở gate sau gap report.

Doctor phải fail nếu bị yêu cầu nhận version refuse. Chi tiết refuse:
`docs/VERSIONS_GODOT.md`.

In đường console exe: `python tools/godot/doctor.py --print-bin`.

---

## 2. `--path` là project, không phải repo root

Product hiện hành:

```
<repo>/godot/dogfood/superfighters
```

`project.godot` ở đó. `config/name="Vault Fighters"`. Main scene
`res://scenes/main.tscn`. Physics **60 Hz**. Viewport **1280×720**.

Luôn truyền `--path` **tuyệt đối** tới folder có `project.godot`. Không chạy
Godot với `--path` = repo root, `godot/plugin-project/`, `kho-bi-an`, hay
`snake`.

`res://` trong `--script` là relative **trong product**, ví dụ
`res://tests/run_all.gd` = `godot/dogfood/superfighters/tests/run_all.gd`.

### Một `--path` = một worker

V-A7: object Godot chỉ trên main thread; editor và Play/test là process tách.
**Không** mở Godot thứ hai trên cùng `--path` (cùng product, cùng critic iso,
cùng clone). Hai process ghi `.godot/`, evidence, `user://` đè nhau → evidence
vô giá trị.

Critic / implementer chạy song song **chỉ** khi `--path` khác nhau
(ví dụ product tree vs `.hh-agent/critic-*/iso`). Đếm leftover theo
**CommandLine chứa đúng `--path` đó**, không đếm Godot của iso khác rồi
kết luận leftover≠0 / giết nhầm.

---

## 3. leftover-0

**leftover-0** = sau mỗi bước (check / headless / window / `run_all`), số
process `Win32_Process` có `Name` khớp `Godot` **và** `CommandLine` chứa
đúng product/`--path` đang chạy = **0**.

Scan mẫu (PowerShell):

```powershell
function Count-Leftover([string]$Path) {
  @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "Godot" -and $_.CommandLine -and
    $_.CommandLine -like "*$Path*"
  }).Count
}
```

Quy tắc:

1. Trước official: leftover trên `--path` đó phải 0. Nếu ≠0 → **không spawn**;
   tìm PID, đợi exit, hoặc kill **chỉ** process của path mình (không đụng critic).
2. Sau `WaitForExit`: sleep ~2s rồi đếm lại. leftover≠0 = FAIL dù banner PASS.
3. Hung / bị kill / agent abort giữa chừng = **không phải PASS**. Banner
   `FINISHED=1` không thay `ExitCode`.
4. `leftover_proof.json` phải do host ghi (số đếm + `headless_host_exit` +
   elapsed). Packer fail-closed nếu caller bịa integer / parse banner thành exit.

---

## 4. Host exit — đây là chỗ agent hay FAIL

Godot in banner rồi `quit(code)`:

```
HH_VF_BOTS PROCESS_EXIT=0
HH_VF_ALL  PROCESS_EXIT=0
```

**PASS nghiệm thu = `System.Diagnostics.Process.WaitForExit` rồi đọc
`ExitCode`.** Không:

- remap `FINISHED=1` / `PROCESS_EXIT=0` trên log thành host exit 0
- `Start-Process` không `-Wait`
- coi job PowerShell “xong” khi thấy banner rồi kill
- wrapper lồng nhau làm `ExitCode` unset (hay ra **fake 1**)
- tin `PROCESS_EXIT=` trong log hơn host

Mẫu host trong `godot/dogfood/superfighters/tests/run_bots_official.ps1`:
C# `HhGodotHost.Runner` redirect stdout/stderr UTF-8, `WaitForExit()`,
`WaitForExit(10000)` lần hai để drain async readers, **return `p.ExitCode`**.
Không đổi banner thành 0.

Windowed official: exe **console twin**, `CreateNoWindow=false` (`-ShowWindow`),
**không** `--headless`, để stdout vẫn vào file và cửa sổ 1280×720 thật.

Headless official: `--headless --script res://tests/<run_*.gd>`. WP5 hiện
dùng GUI exe + `--headless` cho headless/`run_all`, console twin cho window.
Packer một số WP bắt window **phải** là `*_console.exe`. Đừng đảo ngược.

---

## 5. Ba cấp chạy (đừng lẫn)

| Cấp | Khi nào | Host | leftover-0? |
|---|---|---|---|
| **A. Chơi / editor** | Người xem, sửa scene | GUI exe, `--path $prod` hoặc `--editor --path $prod` | Kill leftover **cùng path** trước |
| **B. Diagnose** | Sửa bug, 1 script, python check | `WaitForExit` vẫn nên dùng | Cùng path: 1 process |
| **C. Official** | Evidence / critic / tick WP | Đúng script `run_*_official.ps1` của WP | **Bắt buộc** leftover-0 + freeze + packer |

`python tools/godot/vf_trace_harness.py --window` **không** phải official.

`cargo test --workspace` **không** phải verify product.

RPA / click pixel **không** phải nguồn mutation (semantic API / GDScript).

---

## 6. Official leftover-0 — thứ tự bắt buộc

Mẫu sống: `godot/dogfood/superfighters/tests/run_bots_official.ps1`.

1. `git status`, leftover=0 trên `--path` product (hoặc iso critic).
2. Freeze **trước** Godot official (V-A18): packer `--write-freeze` →
   `freeze.json` (cây source + hash). Godot sau freeze phải khớp hash đó.
   Sửa source sau freeze = remint `RUN_ID` / `COMMAND_ID`.
3. Python gate của WP (ví dụ `tests/check_bots.py`) — không spawn Godot, leftover
   vẫn 0.
4. **Một** Godot: `--headless --script res://tests/run_<wp>.gd` với
   `HH_VF_EVIDENCE_DIR` trỏ thư mục evidence headless. `WaitForExit`. leftover=0.
5. **Một** Godot: console twin, **không** `--headless`, cùng script, evidence
   window riêng. leftover=0.
6. Nếu WP đụng suite dùng chung: **một** Godot `--headless --script res://tests/run_all.gd`.
   **Cấm** `HH_VF_BOTS_COMPACT=1` trên official `run_all` (bị check_bots từ chối).
7. Ghi `leftover_proof.json` + `exits_proof.json` từ số host thật.
8. Packer đọc log + proof; `PACK_EXIT=0` và `READY_FOR_CRITICS=yes` mới được
   đưa critic. `SameFileError` rồi REPACK thành READY = FAIL lịch sử; packer
   phải fail-closed.

Hai critic hostile, iso **khác nhau** dưới `.hh-agent/critic-*/iso`, **cùng**
freeze hash. Không tick khi mới một `TICK=yes`. `TICK=no` → remint, không tick.
Critic **không** sửa product / plan / 20-8, **không** giết Godot của critic kia.

---

## 7. Biến môi trường product

Set **trên process Godot** (host env trước spawn):

| Biến | Việc |
|---|---|
| `HH_VF_EVIDENCE_DIR` | Thư mục ghi stills / `run_partial.json` / outcomes. Headless và window **khác folder**. |
| `HH_VF_RUN_ID` | Một số runner set trong GDScript; official pin `RUN_ID` trong `run_*.gd`. |
| `HH_VF_STAGE_STORE` | File progress stage (tránh đè save người). Official WP5: `progress_vf6wp5_stage.json`. |
| `HH_VF_SURVIVAL_STORE` | File record survival. Official WP5: `records_vf6wp5.json`. |
| `HH_VF_SURVIVAL_SOAK_SEC` | Official nên **xóa** (không soak dài). `run_all` default 8s nếu trống. |
| `HH_VF_BOTS_COMPACT` | **Không set** trên official `run_all`. Compact = không đủ DoD. |

Timezone evidence: **Asia/Saigon**. Mỗi run: `run_id`, `command_id`, seed,
map/mode, source hash, repro command (V-A18).

---

## 8. Lệnh thường dùng

`$con` / `$gui` / `$prod` như mục 0. Làm **tuần tự**, leftover-0 giữa các lệnh
nếu cùng `--path`.

### Chơi (người / quan sát)

```powershell
& $gui --path $prod
```

Editor:

```powershell
& $gui --editor --path $prod
```

### Suite đầy đủ (headless, lâu — WP5 `run_all` ~ hàng nghìn giây)

```powershell
& $gui --headless --path $prod --script res://tests/run_all.gd
```

### Script một WP (đổi tên file theo WP đang mở)

```powershell
& $con --headless --path $prod --script res://tests/run_bots.gd
```

Cùng script, có cửa sổ (console twin):

```powershell
& $con --path $prod --script res://tests/run_bots.gd
```

### Python check (không Godot)

```powershell
python $prod\tests\check_bots.py
```

Cặp điển hình: `tests/check_<feature>.py` rồi `res://tests/run_<feature>.gd`.

### Parse GDScript không chạy game

```powershell
& $con --headless --path $prod --check-only --script res://src/bot_brain.gd
```

### Import cache nếu `.godot` thiếu (iso mới)

```powershell
& $con --headless --editor --path $prod --import --quit
```

Iso critic: copy **product** (và freeze-listed files), không copy `.godot`
bẩn từ máy khác nếu không cần; import một lần trên iso đó rồi mới `run_*.gd`.

### Diagnose ngắn (không official)

```powershell
& $con --headless --path $prod --quit-after 1
& $con --headless --path $prod --script res://tests/run_window_hygiene.gd
```

---

## 9. `--script` vs Play vs Editor

| Cách | Process | Dùng cho |
|---|---|---|
| `--script res://tests/run_*.gd` | `SceneTree` test runner, thường `test_driven=true` | Official + unit/E2E trong `tests/` |
| `--path $prod` không `--script` | Play `main.tscn` | Người chơi, still thủ công |
| `--editor --path $prod` | Editor | Sửa scene/resource; **không** mutate runtime Play (V-A11) |

Test runner `extends SceneTree`, `quit(code)` khi xong. Official không được
`force_kill` / teleport / `apply_eval` làm **bằng chứng E2E duy nhất** (V-A16).

Stills official: viewport 1280×720; pause still SHA phải **khác** fight still.

---

## 10. `run_*.gd` trong product

Nằm dưới `godot/dogfood/superfighters/tests/`. `run_all.gd` preload toàn bộ
case scripts (sprint, dive, combat, maps, rooftop, warehouse, station, sewer,
vs roster, match, vs flow, stage, survival, bots, …).

Đổi suite dùng chung → official phải chạy leftover-0 `run_all`, không chỉ
script WP.

In-game observe (không đoán pixel HUD): `docs/runtime-diagnostics.md`
(`vf.runtime.request.v1`). Đó **không** phải MCP editor socket (VF8).

---

## 11. Iso critic

```
<repo>/.hh-agent/critic-<run>-<ii|hh>/iso/
```

`--path` = iso đó (folder có `project.godot`, thường copy `superfighters`).
Leftover scan **chỉ** CommandLine chứa iso path. Freeze hash phải MATCH
claimed official. Host `WaitForExit` trên iso, không tin pack sẵn.

Không sửa file dưới product từ critic. Không `TICK` plan.

---

## 12. Cấm / FAIL đã lặp

- Hai Godot cùng `--path`
- leftover≠0 rồi vẫn pack READY
- Banner / `FINISHED=1` / kill-as-exit
- `HH_VF_BOTS_COMPACT=1` trên official `run_all`
- Freeze drift (source đổi sau `freeze.json`)
- Gọi `apply_eval` / `set_paused` / emit nút làm **E2E duy nhất**
- Rip Y8 (SWF/HTML5/sprite/audio/screenshot/title card)
- Đụng `godot/dogfood/kho-bi-an/`, Snake, `tools/godot/drive_snake*.py`
- Sửa Godot C++ / bump 4.7.2
- Tick WP / 20-8 / G6 khi chưa đủ hai critic `TICK=yes` cùng hash
- Commit token, `.godot`, zip engine, evidence secret (V-A8)

---

## 13. Platform sidecar (không phải Vault Fighters WP)

`tools/godot/launch.py --project <user-project> --godot` mở **GUI pin** +
sidecar Node. `--provider plan` giữ nguyên; không bịa API key.

Đó là đường plugin-project / hh_agent. **WP Vault Fighters không đi đường
này** để nghiệm thu. Official product = pin exe + `--path` superfighters +
`run_*.gd`.

MCP vendor **không** enable trong product Vault Fighters.

---

## 14. Checklist trước khi spawn

1. Exe pin tồn tại; `--version` khớp `a13da4feb`.
2. `--path` = folder `project.godot` định chạy (product **hoặc** iso).
3. Leftover trên path đó = 0.
4. Không có official khác đang giữ path đó.
5. Official: freeze đã ghi, `RUN_ID`/`COMMAND_ID` chưa dùng (không tái `-01`…void).
6. Host sẽ `WaitForExit` + ghi log stdout/stderr riêng.
7. Sau exit: leftover=0, `ExitCode` từ process, packer đọc proof — không tự tick.
