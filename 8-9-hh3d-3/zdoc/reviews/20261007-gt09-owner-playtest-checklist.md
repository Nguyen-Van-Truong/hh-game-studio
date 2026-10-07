# GT09 owner playtest checklist — 2026-10-07

This form is intentionally unsigned. The coordinator cannot fill in the
owner's observations or convert synthetic/native diagnostics into a human
playtest result.

## Frozen package

- Candidate package: `20261007-gt09-critic-package-candidate.md`
- Candidate review HEAD: `cd5c13392aefff881e06545f4b39257dc0a8fb9e`
- Runtime source commit: `5afb6386f084ad4527fe508a924c677b043bb3b6`
- Fixture closure: `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`
- Conformance report: `studio/.local/reviews/gt09-conformance-20261007-07/report.json`
- 2D raw: `studio/.local/reviews/o2-publication-gt09-arena-effects-20261007-18/`
- 3D raw: `studio/.local/reviews/o2-publication-gt09-room-effects-20261007-19/`
- Blender handoff: `gt07-native-queue-20261007-25/published/scene.glb`

## Owner run A — 2D arena (about 15 minutes)

- Date/time and host: ______________________________
- Build/source hash checked: _______________________
- Start from the normal fixture/game input path: yes / no
- Move and jump/platform traversal worked: yes / no
- Pickup changed observable gameplay state: yes / no
- Bot interaction/combat path was observable: yes / no
- Muzzle flash, hit ray, dust and explosion were visible/behaved correctly: yes / no
- Save, reload and replay remained consistent: yes / no
- Any warning, visible error, stuck input, or unexpected state: _____________
- Owner result: **OK / NOT OK**
- Notes: _________________________________________________________________

## Owner run B — 3D room (about 15 minutes)

- Date/time and host: ______________________________
- Build/source hash checked: _______________________
- Avatar movement and camera follow worked: yes / no
- Trigger/switch interaction was observable: yes / no
- Pickup interaction was observable: yes / no
- HUD/input/replay/save/reload remained consistent: yes / no
- Blender GLB and sprite asset appeared correctly: yes / no
- Any warning, visible error, stuck input, or unexpected state: _____________
- Owner result: **OK / NOT OK**
- Notes: _________________________________________________________________

Attach screenshots/video/source-before-after trace only as supplementary
context; the signed owner observations and the frozen hash are acceptance
inputs. This form remains unsigned until the owner performs the two runs.
