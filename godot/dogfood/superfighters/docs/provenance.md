# Provenance — Vault Fighters (Q0)

31-8 Q0.2 inventory. **Not** a 29-8 checkbox. Plan 29-8 VF5-WP5 stays `[ ]`.
Parent 20-8 stays 59/60, R9-WP4 `[ ]`, G6 `[ ]`.

Hashed with SHA-256 on file bytes only. **Contents were not read**
(no SWF/JS/HTML/image inspection, no reverse-engineering, no asset
reuse). Files were then moved out of the repo workspace.

## Quarantine (2026-08-31 Asia/Saigon)

Destination (outside product tree and this git repo):

`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\_quarantine_vf_q0_20260831\`

| name | bytes | sha256 | reason |
|---|---:|---|---|
| tmp_gd.html | 7332 | `183124f67de7e42c0a5453fe1cfb59566d7cb3da57753c3e9ed0b39dfaea1b0b` | untracked web dump; not product |
| tmp_og.jpg | 78382 | `146396841f275193b6073d93a10656c6ff048a7a0b98948ff33ccce332bdff0e` | untracked web image; not product |
| tmp_sf.js | 20792689 | `e6c66c404fa8d4a037e0db46ee09bb638e8f9f040dde612b1e24107c6cc564ef` | untracked JS dump; clean-room risk |
| tmp_sf.swf | 49 | `409a640c6eb8b3f8179c7c01a0b55b2bd0f8cf30d71342df0e238f41d4275329` | untracked SWF dump; clean-room risk |
| tmp_sf_embedded.swf | 3876641 | `519004010f252b370463307006fa1839ac76a6211e15c4330d82f3bbc6b4bf44` | untracked SWF dump; clean-room risk |
| tmp_sf_index.html | 185 | `9ef9eee059a7a2e60ba62ad1726407560891589dbbaeb9e4cd38b39c03bfb0c6` | untracked HTML dump; not product |
| tmp_shot.png | 2096172 | `f28045da83e87dc0a8ad910a5d529787389a6b1878cee78233be7e5829a4b31b` | untracked screenshot dump; not product |
| tmp_thumb.webp | 4260 | `8b6a84f118ea63ce8fd14948d3da279c5e6b8aec94aa1ed724010199a6a4826c` | untracked web image; not product |
| tmp_y8.html | 693867 | `73427a5f127f4895371057ee6be04e1f70d7bd8db4aeff238b5c36acc36401e4` | untracked HTML dump; clean-room risk |

All nine lived at the **repo root**, not under `godot/dogfood/superfighters/`.
None are in the release manifest. None were used to derive VF5-WP5
geometry, locomotion, toxic rules, or art.

Product tree scan after move: no `tmp_sf*`, `tmp_y8*`, `tmp_shot*`,
`*.swf` under `godot/dogfood/superfighters/`.

Do **not** commit the quarantine folder. Do **not** re-import these
bytes as assets. Snake / `drive_snake*.py` stay out of product.
