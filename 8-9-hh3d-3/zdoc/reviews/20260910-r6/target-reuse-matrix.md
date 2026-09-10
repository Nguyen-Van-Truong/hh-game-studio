# GT01 scope and reuse inventory

| Target/artifact | Evidence | Status / next gate |
| --- | --- | --- |
| Windows x64 Godot4.7.2 stock | Official ZIP+SUMS, matching console/GUI SHA, version, import/parse and headed/headless input | Partial runtime verified on host-inventory.json hardware |
| Godot4.7.2 export templates | Official 1.28GB archive SHA256 and SHA512 verified | Local archive only; export/install matrix remains GT01/GT08 |
| Blender5.2.1 Windows x64 | Publisher SHA256, local extraction, original cube save/reopen, exclusive-output rejection | Fixture only; no GT04 adapter or GT05 GLB workflow |
| Linux headless artifact | Matching release templates pinned | Planned export target; Linux runtime untested on this Windows host |
| Android arm64 | Matching templates pinned | GT08 SDK/JDK/NDK, device and export validation still required |
| Python3.11.9 / Git2.51.1 | Host observed | No system PATH change |
| Vault Fighters Godot4.7.1 | Prior diagnostic use only | Not reused for HH3D candidate, project/pin/cache unchanged |
| Existing platform/HH game tools | No source imported into new studio | Compatibility unproven; no assumed reuse acceptance |
| Grok1.0.25, grok-4.6 xhigh | Per-attempt native/exit records and final modelUsage where present | Invocation works; delivery unreliable; no design ACCEPT |

This matrix records capabilities, not FPS, scalability, Blender bridge or full
GT01 acceptance. No custom Godot fork/GDExtension, game backend or production
server is introduced.
