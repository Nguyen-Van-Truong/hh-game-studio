# 2D coverage TRACE REPORT (R5-WP7)

> Generated-style TRACE REPORT. Not `ACTIONS.md` / `CONTRACT_MATRIX.md`.
> Those catalogs stay coordinator-generated. This file is the R5-WP7 ledger.

Pin: **Godot 4.7.1-stable** (`4.7.1.stable.official.a13da4feb`).
Plugin: `addons/hh_agent` **EXISTS** under `godot/plugin-project/` (one sidecar).
Museum: `godot/plugin-project/r5w7/` via plugin MCP only. No second `project.godot`.
Play: `play.start` stays `E_UNVERIFIED`. Museum Play sạch = `scene.save` + reopen hash + structured readback, **not** F5.
P2 addon rows (CM-048/072/089/110/141/158) are excluded from P0/P1 2D percents.
Play/debug/export is listed for honesty and **not** counted in P0/P1 2D percents.

## Honesty

P0=100% / P1>=90% means every counted row is TRACEABLE to:

- named `action_id` + official E2E test path that ACKs it, or stock Godot CLI already proven; **or**
- typed Alternative/Gap with owner/backlog (R6 / R8 / R9).

It does **not** mean every P0 is Status=Supported.

## Counts

- 2D groups: TileMap, UI, animation, audio, filesystem, inspector, node, physics/navigation, project, scene, script
- P0 2D rows: 96; P0 traceable: 96 (100%)
- P1 2D rows: 40; P1 traceable: 40 (100%)
- P0 left (not Supported; still traced as Alternative/Gap): CM-001, CM-002, CM-003, CM-004, CM-006, CM-007, CM-008, CM-009, CM-010, CM-011, CM-018, CM-020, CM-033, CM-042, CM-044, CM-046, CM-047, CM-051, CM-052, CM-061, CM-062, CM-063, CM-067, CM-068, CM-076, CM-077, CM-078, CM-079, CM-080, CM-081, CM-086, CM-088, CM-096, CM-104, CM-119, CM-120, CM-125, CM-129, CM-134, CM-135, CM-138, CM-140
- Matrix IDs total: 159 (CM-001..CM-159). P2 addons excluded from percents.

## 2D P0/P1 rows

| ID | Group | Pri | Status | Action | Proof | Owner/backlog |
| --- | --- | --- | --- | --- | --- | --- |
| CM-001 | project | P0 | Alternative | project.create | stock project.godot + Godot CLI fixture | R8-WP1 |
| CM-002 | project | P0 | Alternative | project.settings | text project.godot / ProjectSettings | R8-WP1 |
| CM-003 | project | P0 | Alternative | project.settings | text application/run/main_scene | R8-WP2 |
| CM-004 | project | P0 | Alternative | project.settings | text viewport 1280x720 | R8-WP1 |
| CM-005 | project | P1 | Alternative | project.settings | text stretch mode/aspect | R8 |
| CM-006 | project | P0 | Alternative | project.settings | fixture default_texture_filter=0 | R8-WP1 |
| CM-007 | project | P0 | Alternative | project.input | text InputMap keyboard; gamepad loop is R8 | R8 |
| CM-008 | project | P0 | Alternative | project.input | gamepad bind not official-ACK'd (do not flip) | R8 |
| CM-009 | project | P0 | Alternative | project.input | text interact action | R8 |
| CM-010 | project | P0 | Alternative | project.input | text pause action | R8 |
| CM-011 | project | P0 | Alternative | project.autoload | text [autoload]; SaveService dogfood | R8 |
| CM-012 | project | P1 | Alternative | project.settings | physics_ticks_per_second text | R6 |
| CM-013 | project | P0 | Supported | project.open_editor | Godot CLI | — |
| CM-014 | project | P0 | Supported | project.import_headless | Godot CLI | — |
| CM-015 | project | P0 | Supported | project.settings | tests/bootstrap/test_project_settings.py | — |
| CM-016 | project | P1 | Alternative | project.settings | boot splash art later | R8-WP3 |
| CM-017 | project | P1 | Alternative | project.input | deadzone text | R8 |
| CM-018 | project | P0 | Alternative | export.preset | text export_presets.cfg stub | R9 |
| CM-019 | project | P0 | Supported | project.read_fixture | Godot CLI / godot/ file on disk | — |
| CM-020 | project | P0 | Alternative | project.settings | fixture untyped_declaration=1 | R8 |
| CM-021 | scene | P0 | Supported | scene.create | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-022 | scene | P0 | Supported | scene.open | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-023 | scene | P0 | Supported | scene.save | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-024 | scene | P1 | Supported | scene.save_as | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-025 | scene | P1 | Supported | scene.reload | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-026 | scene | P1 | Gap | scene.close | tests/bootstrap/test_scene_lifecycle.py ACK; not in scout flip | R8 |
| CM-027 | scene | P0 | Supported | scene.instantiate | tests/bootstrap/test_scene_lifecycle.py | — |
| CM-028 | scene | P1 | Alternative | scene.create | inherited ACK in test_scene_lifecycle.py; composition preferred | R8 |
| CM-029 | scene | P1 | Gap | scene.change_root_type | no stable Change Type action | R8 |
| CM-030 | scene | P1 | Gap | scene.mark_unsaved | mark_scene_as_unsaved not official-ACK'd | R8 |
| CM-031 | scene | P0 | Supported | scene.read_fixture | Godot CLI / godot/ file on disk | — |
| CM-032 | node | P0 | Supported | node.add | tests/bootstrap/test_node_crud.py | — |
| CM-033 | node | P0 | Alternative | node.add | unique_name_in_owner not official-ACK'd (do not flip) | R8 |
| CM-034 | node | P0 | Supported | camera.make_current | tests/bootstrap/test_transform_2d.py | — |
| CM-035 | node | P0 | Supported | node.rename | tests/bootstrap/test_node_crud.py | — |
| CM-036 | node | P0 | Supported | node.reparent | tests/bootstrap/test_node_crud.py | — |
| CM-037 | node | P1 | Supported | node.duplicate | tests/bootstrap/test_node_crud.py | — |
| CM-038 | node | P0 | Supported | node.remove | tests/bootstrap/test_node_crud.py | — |
| CM-039 | node | P1 | Supported | node.reorder | tests/bootstrap/test_node_crud.py | — |
| CM-040 | node | P0 | Supported | node.add | tests/bootstrap/test_node_crud.py | — |
| CM-041 | node | P0 | Supported | node.group | tests/bootstrap/test_node_crud.py | — |
| CM-042 | node | P0 | Alternative | property.set | process_mode ALWAYS on pause menu is R8-WP4 | R8-WP4 |
| CM-043 | node | P1 | Alternative | node.add | Marker2D graybox spawn | R8 |
| CM-044 | node | P0 | Alternative | node.query | %Player unique-name readback | R8 |
| CM-045 | node | P0 | Supported | property.set | tests/bootstrap/test_property_codec.py | — |
| CM-046 | node | P0 | Alternative | node.add | NPC CharacterBody2D composition | R8 |
| CM-047 | node | P0 | Alternative | node.add | Area2D interact volume composition | R8 |
| CM-049 | inspector | P0 | Supported | resource.assign | tests/bootstrap/test_resource_ops.py | — |
| CM-050 | inspector | P0 | Supported | physics.layers | tests/bootstrap/test_physics.py | — |
| CM-051 | inspector | P0 | Alternative | property.set | Camera2D limits dogfood | R8 |
| CM-052 | inspector | P0 | Alternative | property.set | @export NodePath assign | R8 |
| CM-053 | inspector | P1 | Alternative | property.set | visible/modulate/z_index polish | R8 |
| CM-054 | inspector | P0 | Supported | physics.body | tests/bootstrap/test_physics.py | — |
| CM-055 | inspector | P1 | Alternative | resource.edit | resource_local_to_scene | R8 |
| CM-056 | inspector | P0 | Supported | editor.focus | tests/bootstrap/test_coverage_2d.py | — |
| CM-057 | inspector | P1 | Alternative | property.set | AnimationPlayer.autoplay | R8 |
| CM-058 | inspector | P1 | Alternative | render.quality | PointLight2D polish; quality ACK is not this row | R8-WP4 |
| CM-059 | inspector | P0 | Supported | tilemap.tileset | tests/bootstrap/test_tilemap.py | — |
| CM-060 | filesystem | P0 | Supported | asset.import | tests/bootstrap/test_asset_ingest.py | — |
| CM-061 | filesystem | P0 | Alternative | asset.import | Nearest .import keys | R8-WP3 |
| CM-062 | filesystem | P0 | Alternative | asset.import | WAV/OGG; museum uses AudioStreamGenerator | R8-WP3 |
| CM-063 | filesystem | P0 | Alternative | asset.import | DirAccess mkdir under jail | R8 |
| CM-064 | filesystem | P0 | Supported | asset.rename | tests/bootstrap/test_coverage_2d.py | — |
| CM-065 | filesystem | P0 | Supported | asset.reimport | tests/bootstrap/test_asset_ingest.py | — |
| CM-066 | filesystem | P1 | Gap | editor.select | FileSystem select; test_editor_focus.py file select | R8 |
| CM-067 | filesystem | P0 | Alternative | asset.import | PLACEHOLDER PNG policy | R8-WP3 |
| CM-068 | filesystem | P0 | Alternative | asset.import | license/hash sidecar | R8-WP3 |
| CM-069 | filesystem | P1 | Supported | asset.delete | tests/bootstrap/test_asset_ingest.py | — |
| CM-070 | filesystem | P1 | Gap | asset.reimport | EditorFileSystem.scan not official-ACK'd | R8 |
| CM-071 | filesystem | P1 | Alternative | asset.import | SystemFont substitute in test_ui.py | R8-WP4 |
| CM-073 | script | P0 | Supported | script.write | tests/bootstrap/test_script_write.py | — |
| CM-074 | script | P0 | Supported | script.attach | tests/bootstrap/test_script_write.py | — |
| CM-075 | script | P1 | Supported | script.detach | tests/bootstrap/test_coverage_2d.py | — |
| CM-076 | script | P0 | Alternative | script.write | player move() runtime assert | R6 |
| CM-077 | script | P0 | Alternative | script.write | interact runtime assert | R6 |
| CM-078 | script | P0 | Alternative | script.write | inventory model unit | R8 |
| CM-079 | script | P0 | Alternative | script.write | door unlock runtime | R6 |
| CM-080 | script | P0 | Alternative | script.write | win/loss/restart runtime | R6 |
| CM-081 | script | P0 | Alternative | script.write | user:// save/load | R8 |
| CM-082 | script | P0 | Supported | script.check_only | Godot CLI --check-only | — |
| CM-083 | script | P1 | Supported | script.open_at | tests/bootstrap/test_script_write.py | — |
| CM-084 | script | P0 | Supported | script.write | tests/bootstrap/test_script_write.py | — |
| CM-085 | script | P0 | Supported | signal.connect | tests/bootstrap/test_resource_ops.py | — |
| CM-086 | script | P0 | Alternative | script.write | get_tree().paused in-game | R6 |
| CM-087 | script | P0 | Supported | script.read_fixture | Godot CLI / godot/ file on disk | — |
| CM-088 | script | P0 | Alternative | script.write | NPC chase/idle script | R8 |
| CM-090 | TileMap | P0 | Supported | tilemap.layer | tests/bootstrap/test_tilemap.py | — |
| CM-091 | TileMap | P0 | Supported | tilemap.tileset | tests/bootstrap/test_tilemap.py | — |
| CM-092 | TileMap | P0 | Supported | tilemap.source | tests/bootstrap/test_tilemap.py | — |
| CM-093 | TileMap | P0 | Supported | tilemap.cell | tests/bootstrap/test_tilemap.py | — |
| CM-094 | TileMap | P1 | Supported | tilemap.cell | tests/bootstrap/test_coverage_2d.py | — |
| CM-095 | TileMap | P0 | Supported | tilemap.layer | tests/bootstrap/test_tilemap.py | — |
| CM-096 | TileMap | P0 | Alternative | tilemap.source | tileset physics polygons; playtest is R6 | R8-WP2 |
| CM-097 | TileMap | P1 | Alternative | tilemap.tileset | atlas navigation polygons | R8 |
| CM-098 | TileMap | P1 | Alternative | property.set | y_sort / quadrant polish | R8 |
| CM-099 | TileMap | P0 | Supported | tilemap.fill | tests/bootstrap/test_tilemap.py | — |
| CM-100 | TileMap | P1 | Gap | editor.main_screen | no dedicated TileMap painter API | R8 |
| CM-101 | animation | P0 | Supported | node.add | tests/bootstrap/test_animation.py | — |
| CM-102 | animation | P0 | Supported | animation.animation | tests/bootstrap/test_animation.py | — |
| CM-103 | animation | P0 | Supported | animation.sprite_frames | tests/bootstrap/test_animation.py | — |
| CM-104 | animation | P0 | Alternative | animation.preview | play('walk') from game code | R6 |
| CM-105 | animation | P1 | Alternative | animation.track | method-call footstep track | R8 |
| CM-106 | animation | P1 | Alternative | property.set | AnimationMixer physics callback | R8 |
| CM-107 | animation | P0 | Supported | animation.sprite_frames | tests/bootstrap/test_animation.py | — |
| CM-108 | animation | P1 | Gap | animation.preview | tests/bootstrap/test_animation.py preview ACK; not Play | R8 |
| CM-109 | animation | P1 | Alternative | animation.animation | hit/interact oneshot polish | R8 |
| CM-111 | UI | P0 | Supported | node.add | tests/bootstrap/test_coverage_2d.py | — |
| CM-112 | UI | P0 | Supported | node.add | tests/bootstrap/test_ui.py | — |
| CM-113 | UI | P0 | Supported | node.add | tests/bootstrap/test_coverage_2d.py | — |
| CM-114 | UI | P0 | Supported | node.add | tests/bootstrap/test_ui.py | — |
| CM-115 | UI | P0 | Supported | property.set | tests/bootstrap/test_ui.py | — |
| CM-116 | UI | P1 | Alternative | node.add | TextureRect key icon art | R8-WP3 |
| CM-117 | UI | P1 | Alternative | ui.control | HSlider/CheckButton settings | R8-WP4 |
| CM-118 | UI | P0 | Supported | ui.theme | tests/bootstrap/test_ui.py | — |
| CM-119 | UI | P0 | Alternative | ui.control | interact prompt visibility runtime | R6 |
| CM-120 | UI | P0 | Alternative | ui.control | win/loss overlay runtime | R8 |
| CM-121 | UI | P1 | Alternative | property.set | mouse_filter gameplay vs pause | R8 |
| CM-122 | audio | P0 | Supported | audio.player | tests/bootstrap/test_audio_render.py | — |
| CM-123 | audio | P1 | Alternative | audio.player | AudioStreamPlayer2D positional | R8 |
| CM-124 | audio | P0 | Supported | audio.bus | tests/bootstrap/test_audio_render.py | — |
| CM-125 | audio | P0 | Alternative | audio.player | looping music heard in Play | R6 |
| CM-126 | audio | P0 | Supported | audio.bus | tests/bootstrap/test_audio_render.py | — |
| CM-127 | audio | P1 | Alternative | asset.import | WAV loop import keys | R8 |
| CM-128 | audio | P1 | Alternative | audio.bus | duck Music while paused | R6 |
| CM-129 | audio | P0 | Alternative | audio.player | heard pickup SFX | R6 |
| CM-130 | physics/navigation | P0 | Supported | physics.shape | tests/bootstrap/test_physics.py | — |
| CM-131 | physics/navigation | P0 | Supported | physics.body | tests/bootstrap/test_physics.py | — |
| CM-132 | physics/navigation | P0 | Supported | physics.shape | tests/bootstrap/test_physics.py | — |
| CM-133 | physics/navigation | P0 | Supported | physics.layers | tests/bootstrap/test_physics.py | — |
| CM-134 | physics/navigation | P0 | Alternative | script.write | move_and_slide runtime | R6 |
| CM-135 | physics/navigation | P0 | Alternative | node.add | RayCast2D interact targeting | R8 |
| CM-136 | physics/navigation | P1 | Supported | physics.nav_region | tests/bootstrap/test_physics.py | — |
| CM-137 | physics/navigation | P1 | Supported | physics.nav_agent | tests/bootstrap/test_physics.py | — |
| CM-138 | physics/navigation | P0 | Gap | runtime.state | stuck detect needs runtime bridge | R6 |
| CM-139 | physics/navigation | P1 | Gap | physics.debug | visible collision shapes in Play | R6 |
| CM-140 | physics/navigation | P0 | Alternative | project.settings | zero gravity / floating belt | R8 |

## Play/debug/export (not in 2D percent)

| ID | Pri | Status | Action | Proof | Owner/backlog |
| --- | --- | --- | --- | --- | --- |
| CM-142 | P0 | Gap | play.start | Gap: E_UNVERIFIED; do not paper-ACK F5 | R6 |
| CM-143 | P0 | Gap | play.start | Gap: play current scene unverified | R6 |
| CM-144 | P0 | Gap | play.stop | Gap: stop playing unverified | R6 |
| CM-145 | P0 | Supported | play.headless_quit_after | Supported: Godot CLI --quit-after 1 | — |
| CM-146 | P0 | Supported | play.version_pin | Supported: Godot CLI --version | — |
| CM-147 | P0 | Gap | runtime.screenshot | Gap: screenshots=SKIP; no dummy PNG | R6 |
| CM-148 | P0 | Alternative | export.build | Alternative: Godot CLI --export-release after templates | R9 |
| CM-149 | P0 | Alternative | export.validate | Alternative: 4.7.1 templates via doctor | R9 |
| CM-150 | P0 | Gap | runtime.tree | Gap: remote tree is not editor tree | R6 |
| CM-151 | P0 | Gap | input.action | Gap: inject stays E_UNVERIFIED | R6 |
| CM-152 | P1 | Supported | editor.main_screen | tests/bootstrap/test_coverage_2d.py | — |
| CM-153 | P0 | Supported | editor.select | tests/bootstrap/test_editor_focus.py | — |
| CM-154 | P1 | Gap | test.run | Gap: GUT not enabled in plugin-project | R9 |
| CM-155 | P1 | Alternative | play.write_movie | Alternative: Godot CLI --write-movie | R6 |
| CM-156 | P0 | Gap | export.build | Gap: release strip filters | R9 |
| CM-157 | P0 | Alternative | play.logs | Alternative: headless stdout; editor log scrape later | R6 |
| CM-159 | P0 | Gap | play.seed_rng | Gap: seed before inject | R6 |

## P2 addons (excluded)

| ID | Action | Owner |
| --- | --- | --- |
| CM-048 | plugin.phantom_camera | never enable in plugin-project |
| CM-072 | plugin.aseprite_importer | never enable in plugin-project |
| CM-089 | plugin.dialogue_manager | never enable in plugin-project |
| CM-110 | plugin.spine_runtime | never enable in plugin-project |
| CM-141 | plugin.beehave | never enable in plugin-project |
| CM-158 | plugin.godotsteam | never enable in plugin-project |

## 50-prompt corpus

See `tests/bootstrap/fixtures/r5w7_prompt_corpus.txt`.
Counts are measured from `bridge/generated/mcp-tools.json` (tool-select, not wall-clock).
Wall-clock/p95 benchmark is **Alternative** — no real perf harness in R5-WP7.
