# GT04 opaque material candidate

Candidate only; public_ack=false; formal acceptance=false. Source closure:
`dc6c9f4dad98adb7250feec88eea40a0990d51eeb05b0a90775559669f77b28a`.
Run `../20260917-gt04-material-02/` passes 108 Python tests, 16 native checks,
14 actual admission rejections, two capped background material exports and one
fresh-process checkpoint reopen. All captured target/wrapper exits are zero,
runner trees are checked, and source/frozen source stayed unchanged. No Blender
process remained after the run.

The closed grammar admits at most four original opaque Principled materials,
each assigned to one mesh's sole material slot. Only RGB base color, metallic
and roughness vary; other native inputs remain exactly at pinned defaults.
The actual UI operator supports material creation/update and native undo/redo.
Duplicate material commands return their original internal receipt. Mesh,
transform and material snapshots agree after checkpoint reopen. GLB material
names and PBR factors bind to the background process's reopened source, alongside
the existing full vertex/TRS/name checks. There are no textures, custom shaders,
external URIs, material extensions, rigs or clips.

Native negative fixtures exercise missing libraries/textures, object/scene
drivers, unknown material, missing/unapproved addons, Geometry Nodes, material
transmission, alpha, procedural shader nodes, node drivers and extra slots.
Each rejection is followed by restoration and exact source readback before
export. The memory/disk/time/log constraints remain the previous bounded Job
profile; disk size is a reactive watchdog, not a quota.

Material01 is preserved as a failed capture: its first 14 native checks passed,
then fresh checkpoint reopen hit a missing test import path in Blender Python.
Material02 changes the harness import and profile documentation; source hashes
are kept separate. The original failed exit is not rewritten.

Repro (read-only, no engines or metadata writes):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-material-audit/verify_evidence.py --check-live
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-material-audit/test_evidence.py
```

Omit `--check-live` to validate this frozen historical closure after later source
changes. Only `--write-derived` writes this audit's own manifest/summary. Runtime
and captures remain untouched. The portable set excludes user/temp caches and
keeps frozen source, raw process records, saved `.blend`, staged inputs and GLBs.

Earlier cleanup/durable evidence remains under its own frozen closure and is
not relabelled as material02. GT04 still lacks protected publication custody,
FIFO scheduling, full scene recovery and independent critic acceptance. Public
ACK stays disabled. Rig/avatar/clip and Godot import belong to later GT05 work.
Edit Mode infrastructure was proved in the historical UI lane; this new material
run itself exercises Object Mode and makes no new material-specific Edit Mode
proof claim. The phrase "four default values" in frozen MATERIAL_PROFILE.md is
a wording error: all unsupported input defaults in material_profile.py are
checked exactly; four is the maximum material count.
