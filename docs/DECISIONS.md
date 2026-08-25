# Architecture decisions

## 2026-08-20 — Reboot sang Godot stock + Agent Autopilot (người đã chọn hướng mới)

`decision_id: GODOT-REBOOT-2026-08-20`
`status: approved-transition`
`supersedes-roadmap: zdocs/16-8-game-studio-*.txt`
`effective-scope: chọn WP mới ngay; product implementation chỉ sau R0 archive/cutover`
`legacy_base_commit=698e6088cc6d2c0a9a7b74021de409d46e5971aa`
`archive_tag=legacy-rust-engine-2026-08-20`
`archive_branch=archive/legacy-rust-engine-2026-08-20`

Người dùng yêu cầu bỏ hướng/game cũ vì chất lượng không đạt, chọn giải pháp tốt nhất để
AI agent có thể tự làm toàn bộ game còn người chỉ xem và review. Quyết định kiến trúc:

- Dừng mở WP mới của roadmap Rust/`gs-*`; giữ nguyên code/lịch sử cho tới khi R0 archive
  an toàn, không xóa ngầm.
- Nền mới là **Godot stock stable**; game và EditorPlugin dùng GDScript. Không fork C++
  trước. Chỉ mở GDExtension/fork nếu public API thất bại một capability bắt buộc và người
  tick Gate GX.
- Agent thao tác bằng semantic commands qua EditorPlugin/MCP, UndoRedo, atomic file write,
  postcondition và Git checkpoint. Pixel mouse/RPA không phải nguồn mutation.
- Editor thật hiển thị selection, Inspector, timeline và overlay/replay để người xem agent
  làm. `OWNER_AUTOPILOT` tự duyệt việc project-scoped; chỉ hỏi ở secret/spend/sign-publish
  hoặc thay đổi mục tiêu sản phẩm lớn.
- Kế hoạch reboot chi tiết và progress authority sau cutover:
  `zdocs/20-8-godot-agent-autopilot-plan.txt`.

Đây là quyết định thay hướng sản phẩm do người yêu cầu trực tiếp ngày 20-8-2026. Việc
triển khai bắt đầu ở R0-WP1; stanza TRANSITION trong AGENTS.md chỉ làm R0-WP1 có thể
được chọn. R0-WP2 mới hoàn tất bootstrap và banner legacy; không sửa checkbox lịch sử.

R0-WP1 đã đóng băng engine Rust/`gs-*` tại `legacy_base_commit` bằng annotated tag
`legacy-rust-engine-2026-08-20` và branch `archive/legacy-rust-engine-2026-08-20`.
Không tiếp tục WP-M6 / M7 / M8 của engine đó. Pointer phục hồi: `legacy/README.md`.

## 2026-08-20 — G1 base: in-house thin (architecture gate, không phải E1–E4)

`decision_id: GODOT-G1-BASE-2026-08-20`
`status: choice-approved`
`plan_tick: coordinator after critic — plan G1 checkbox stays [ ] until then`
`choice: in-house thin`
`g1_base: in-house-thin`
`mcp_vendor: none`

Đây là **lựa chọn** architecture cho gate G1 (in-house thin) sau R1 bake-off +
stock vertical slice — không phải xác nhận checkbox plan đã tick. Không phải
stop-gate người E1–E4 (không secret, không spend, không ký/publish, không đổi brief).
Không fork Godot C++. Không enable MCP trong `godot/plugin-project/`.
Mục 2026-08-16 «G1 chốt M-1» bên dưới là gate engine Rust legacy, không phải gate này.

### Chọn đúng một: (3) in-house thin

Engine pin: Godot **4.7.1-stable** only —
`4.7.1.stable.official.a13da4feb` /
commit `a13da4feb8d8aefc283c3763d33a2f170a18d541`. Refuse `4.7.2*`.

Cây sản phẩm tương lai (R2; **không** tạo addon/MCP server trong WP này):

- plugin: `godot/plugin-project/addons/hh_agent/`
- sidecar: `bridge/` (TypeScript MCP; scaffold `hh-godot-bridge` 0.0.0 + Node 24.19.0
  lockfile đã có)
- schema ownership (R2): `bridge/src/registry/`

Lock: `.hh-agent/capability-lock.json` và `docs/godot-agent/G1_BASE.md`.

### Bác (1) và (2)

- **Rejected (1) vendor exact MIT commit** — không copy A/C/B/D source vào product
  tree (`godot/plugin-project/`, `godot/test-projects/minimal-2d/`, `bridge/src/`).
- **Rejected (2) depend exact package** — không `npx -y`, không thêm
  `@satelliteoflove/godot-mcp` (hay Beckett/KeeVeeG/Sods2 npm) làm dependency sản phẩm.
  npm `@satelliteoflove/godot-mcp@4.1.0` (tag `godot-mcp-v4.1.0`, SHA
  `59da3d0dae06c79cc970d83828e54b2fc16d0769`) is **not** candidate A.

### Lý do — MUST-PATCH leftover còn mở

Plan §0.2 mặc định ưu tiên tái sử dụng/vendor một MCP MIT. R1-WP5 ghi mặc định ưu
tiên satelliteoflove **nếu** self-verify/security **đạt**. Chúng **không** đạt cho
enable-as-is: fail-hard enable-as-is = **yes** cho cả bốn ứng viên. WP R1-WP5 cho
phép “tự làm phần tối thiểu nếu audit thất bại” / “write the minimal sidecar +
plugin ourselves if MUST-PATCH stay open.” Các hàng MUST-PATCH **còn mở**. Đây
**không** phải silent spec rewrite: không sửa `zdocs/20-8-godot-agent-autopilot-plan.txt`
§0.2 `[CHỌN] Tái sử dụng/vendor một MCP MIT`; fallback ghi ở đây.

**A** satelliteoflove/godot-mcp `1b7d40537240fd54300f54bf6fda1ea91f06c878`: không
session token, cổng cố định **6550**, `godot_exec`, **zero UndoRedo**, `update_node`
trả empty success, `MCPGameBridge` đi vào export. Spike security (token + disable
exec) được vá **trong driver bake-off của ta**, không phải upstream.

**C** Beckett Lite `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d`: `call_method` /
`Object.callv`, token thiếu trên upgrade path, zero-sidecar **conflicts** với
TypeScript sidecar đã chọn (§0.2 / §2.2). Beckett Full itch = **E2 fail-hard**
(không mua).

Bake-off (`tests/e2e/bakeoff/SCORECARD.md`): agent-driven undo/redo **FAIL for both**
(undo=0). Weighted C 3.625 vs A 2.858 **không** ủy quyền vendor. Dummy PNG
screenshot = SKIP.

**B** KeeVeeG `9ea1a41b9ed6cd819c602a37cc111c50017707d8` và **D** Sods2
`78b2cee00d697f117d6875e07675101b867efe70`: fail-hard bake-off; coverage inventory
only; không copy.

### Boundary (G1)

- upstream boundary = **none** (SHA trên là reference-only, không phải product upstream)
- patch queue = **do not patch-vendor**
- update cadence = **none** cho MCP candidate (chỉ re-audit nếu WP sau đề xuất (1) hoặc (2))
- production fixture: `godot/plugin-project/` **không** có `addons/` / `plugin.cfg`

## 2026-08-16 — G1 chốt M-1 (người: tiếp tục, không dừng ở gate)

- Renderer: **bevy_ecs standalone + gs-render2d**, không fallback full Bevy.
  Constants: PPU 16, Y-up, pivot bottom-left, sRGB + premultiplied alpha,
  sort z_index then entity id, atlas pad 2px, nearest, pick alpha>0.1 CPU.
- WAL: full command+inverse JSONL + crc32; fsync every record; ACK after apply.
  Crash tests may simulate disk state (not only kill -9). Fsync ~5ms/txn on
  this machine — revisit group-commit if M0 measures worse.
- Luau: interrupt returns error (not Yield); must pierce pcall; mutation buffer.
  mlua 0.11.6 + Luau 0.709. Windows needs `vcvars64` for first C++ vendored build.
- Versions: see `docs/VERSIONS.md`. Pin the set; do not bump crates independently.
- MCP: `rmcp =3.1.2`. Inspector/Cursor still a human check (M8).
- `experiments/` kept until M0 crates absorb the lessons; then delete spikes.

## 2026-08-17 — G3 imagegen CHỐT: B+C (người: chọn cách tốt nhất lâu dài)

Người (chat 17-8-2026): “cứ chọn cách tốt nhất cho lâu dài” — ủy quyền chốt gate, không chờ thêm một vòng hỏi A/B/C.

- **Mặc định hỗ trợ chính thức: B** — ComfyUI local là prerequisite (MASTER 8.5). Không bundle model (A): size/license/build không bền vững trước M8.
- **Cấu hình tùy chọn: C** — HTTP API + key ngoài project (per-user, không bus, không git/WAL). Máy không GPU vẫn gen được.
- **A:** chỉ xét sau M8 nếu G5 = public boxed product.
- Máy dogfood hiện **chưa** có ComfyUI trong repo. `gs doctor` phải fail sạch (exit ≠ 0) khi thiếu Python/ComfyUI/API — không giả gen art.
- Secret C: `%APPDATA%/hh-game-studio/imagegen.json` (hoặc tương đương), không nằm dưới project root.

## 2026-08-17 — M7A-1 trước M6 (lệch thứ tự WP, không lệch SPEC T7A.1)

Người yêu cầu đóng gói/chạy game (`hh-play.bat`) ngay. WP-M7A-1 ghi phụ thuộc M6; M6 bị G3 chặn. **Làm T7A.1 trên asset đã có** (scene, scripts, player exe, color sprites). Không làm worker imagegen. Missing = script file không tồn tại hoặc asset đã import mà path mất — không fail chỉ vì `$asset` id chưa có PNG (quad màu, đúng game hiện tại).

Người bác thì dừng export, không tick M7A.

## 2026-08-17 — G4 installer CHỐT: Inno Setup (người: chọn lâu dài)

- **Chọn Inno Setup** cho editor dist (M7B). Unsigned OK trên Win10/11; rollback = uninstaller + giữ 1 bản cũ; CI Windows runner đơn giản.
- **Không chọn MSIX** lúc này: sideload/unsigned khó, chưa cần store identity.
- Game user (M7A) vẫn **unsigned**, cert editor ≠ cert game (C13).
- Signing editor + timestamp: M7B-2, cần cert người cấp (S5) — không giả ký.

## 2026-08-17 — GATE G3 báo cáo (STOP S1 — chờ người)

Đọc MASTER 8.5. Agent không chọn A/B/C.

- Máy dogfood đã có ComfyUI/GPU? **Chưa xác nhận.** Máy này chạy editor/player wgpu; repo không có ComfyUI, không có `workers/imagegen/`.
- Cần API remote (C)? **Chưa xác nhận.**
- Khuyến nghị SPEC (không chốt): **B** (ComfyUI local) ± **C** nếu GPU máy dogfood không đủ.
- **CẤM** cho đến khi người tick G3 = `[x]` và ghi A/B/C vào file này: `workers/imagegen/`, `asset.gen_image`, `asset.job_*`, `asset.ingest_staged`, `asset.make_flipbook` worker path, WP-M6-1..4, dogfood 1.5 phụ thuộc imagegen (WP-M8-2).

Người: ghi `A` / `B` / `C` (hoặc `B+C`) rồi tick G3 trong execution plan.

## 2026-08-17 — GATE G4 báo cáo (STOP S1 — chờ người)

Ưu/nhược ngắn (agent không chọn):

- **Inno Setup:** đơn giản Win10/11, unsigned OK, rollback = uninstaller + giữ 1 bản cũ. Khớp M7A unsigned. Script Pascal, CI dễ trên Windows runner.
- **MSIX:** update channel sạch, package identity; unsigned/sideload khó; SmartScreen/dev mode trên VM sạch.
- Signing editor ≠ signing game user (C13). Game M7A luôn unsigned.

Người: ghi `Inno` hoặc `MSIX` (+ chính sách signing) rồi tick G4. CẤM code `installer/` / M7B trước đó.

## 2026-08-17 — GATE G6 báo cáo (STOP — chưa đến lượt)

G6 chỉ sau M8 dogfood. Chưa có `zdocs/dogfood/`. **CẤM** mọi WP-M9* (kể cả mini-spec `docs/M9*_*.md`) cho đến G6 = `[x]`.

Đề xuất ưu tiên (dự kiến, không chốt): M9A (UI+save) → M9E pathfinding → M9B editor → M9C art → M9D render → M9F. Prefab FULL: nghiêng **cắt, giữ Blueprint 5.3** trừ dogfood chứng minh thiếu. Người được đổi thứ tự / cắt nhóm.

## 2026-08-17 — M7A-2 STOP S5 (không có VM sạch)

Không có Win10/11 clean VM (không Rust/Python) trong môi trường agent. `examples/kho-bi-an/` không tồn tại (`games/snake` + `games/platformer` là stand-in). **Không tick WP-M7A-2.** Không giả screenshot VM.

`hh-play.bat` trên máy dev **cần cargo** để *tạo* pack (trừ khi `GS_SKIP_BUILD=1` và đã có `target\release\gs-player.exe`). Máy sạch không Rust: chỉ chạy được folder pack sẵn (`gs-player.exe` + `manifest.json`) — `hh-play.bat <pack-dir>`. Không phải T7A.2.

## 2026-08-17 — Critic M7A/M8: không tick

Critic độc lập: **không tick** WP-M7A-1 / M7A-2 / M7A-3 / M8-1. Parent chấp nhận (kể cả sau spawn-exe + command_id).

Giữ code pack/`hh-play.bat`/`EXPORT_SIGNING.md`. Không tick: `build.cancel` stub (pack sync); missing = `dest_rel` import, không phải `$asset` không PNG; I11 build là sidecar không WAL; `build.game` không qua dispatcher; phụ thuộc M6 còn `[ ]`; M7A-3 DoD = VM sạch.

**G3 / G4 ticks giữ** — gate là chọn provider / Inno, không phải ComfyUI đã cài hay file `.iss` đã có.

## 2026-08-17 — Ngân sách biên dịch chunk = INIT_BUDGET (lấp khoảng trống 7.3)

MASTER 7.3 chỉ định ngân sách cho **callback**: per-script 2ms soft / 4ms hard mỗi
frame, `on_init` 100ms ("chạy 1 lần, cho phép nặng hơn"). SPEC **không** nói lần
biên dịch chunk (`ensure_compiled`, chunk `load:<id>`) tính vào bucket nào.

`vm.rs` đang tính nó vào `SCRIPT_HARD` (4ms). Hậu quả đo được: `fighter.luau`
của `games/scrap-yard` ở 777 dòng làm **9/9 test `wp_games_scrap` fail** với
`deadline exceeded`, `file: "load:e_000020"` — script chưa chạy một dòng gameplay
nào đã chết ở bước nạp. Trần thực tế cho một script gameplay là ~400 dòng, tức
không viết nổi một nhân vật brawler.

Đổi thành `INIT_BUDGET` (100ms). Lý do: biên dịch là chi phí **một lần** mỗi
instance, đúng cùng loại với `on_init` mà SPEC đã cho 100ms. Không đổi bất kỳ
ngân sách per-frame nào, nên GS-EC-26 (50 script x 4ms) và global 6/12ms giữ
nguyên; hot-reload cũng đi qua đường này nên hưởng cùng ngân sách.

Đây là **lấp khoảng trống**, không phải lệch SPEC. Nếu người đọc thấy SPEC hàm ý
compile phải nằm trong 4ms thì đây là chỗ cần bác — nói để hoàn tác một dòng.

## 2026-08-17 — Critic #2: hoàn tác tick M7A-1/M7A-3

Parent đã tick rồi hoàn tác. G3=B+C và G4=Inno giữ. M6-3 flipbook bị recall (phụ thuộc M6-2). `entity.lock` phải nằm trong `Dispatcher`, không editor RAM. Worker Python chỉ ghi staging.

## 2026-08-24 — R7-WP6 / G4: STOP — không tick, không planted REPAIR

`decision_id: GODOT-G4-REPAIR-2026-08-24`
`status: user-chose-door-2-2026-08-24`
`plan_tick: R7-WP6 and G4 stay [ ] until official 90 + two critics`

Zero-touch Host (`--provider plan`) là compiler heuristic + DAG walker, không LLM.
`ConfiguredProvider` hết `E_EXTERNAL` (không có API key — E1).

Hostile critics (I/J, K/L, M/N, O/P, Q/R) đã bác mọi cách **trồng** fail→sửa:

- lỗ `if same: pass` / `matches += 0` / `pair_bug`
- complete first write gọi là “pre-applied patch”
- `asset_ok` / `TILE_ART` / `planned_art` / `PlannedArt` tripwire
- vacuous REPAIR (bỏ label khỏi `G4_NEED` vì “không có bug”)

G3 đã tick trên **8 seed ngoài** (harness gieo, adapter sửa). WP6 zero-touch cấm người/harness sửa file game sau T0, nên Host vừa viết vừa sửa — mọi defect đều là plant hoặc không xảy ra.

Coordinator đã xóa inject `planned_art` / `PlannedArt` / cặp pause-resume kề nhau. `maybeQueueRepair` vẫn gọi `godot.test repair` nếu `test.run` thật sự fail. Không đốt official 90. Không tick.

Hai cửa, chỉ người chọn một:

1. **E1** — cấp credential model (không bịa key). Planner/repair không còn là tape Host.
2. **Chấp nhận G4 heuristic** — DoD chữ “không human-work; output chạy; test xanh”; Làm “repair” = khả năng, không bắt buộc planted defect. LOG giống G3 (heuristic, not LLM). `REPAIR` có thể unproven.

Người đã chọn cửa 2 và bảo “cứ chọn cách tốt nhất rồi làm”: Godot-control,
không API key, `--provider plan` stays. Không trồng bug. REPAIR = khả năng
(`maybeQueueRepair` + `godot.test repair` nếu test thật fail). DoD G4 thắng
Làm “repair” khi không có defect: stamp `unused` (không xóa khỏi `G4_NEED`).
Không mở R8 / G5 trước tick. GX vẫn khóa.
