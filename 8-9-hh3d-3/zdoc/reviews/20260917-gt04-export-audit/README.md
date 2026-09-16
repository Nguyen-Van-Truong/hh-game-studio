# GT04 internal owned-fixture export candidate

Status: CANDIDATE, public_ack=false, no formal acceptance. The authoritative run
is `../20260917-gt04-export-04/`; IPC05 and export01–03 remain historical source
closures and must not be relabelled as this implementation.

`export.prepare` requires the existing exact revision/context and fixed `export`
slot. A Blender main-thread timer admits a strictly owned box-only scene and
saves a private staged input copy. The external Python host verifies file identity
and digest, copies it into a separate owned workspace, and launches pinned
Blender 5.2.1 background behind the existing checked Windows Job gate. Heavy
export does not block the UI timer. No arbitrary path, script, addon, or artist
file is a command argument.

The host hashes all 128 bundled glTF exporter files and pins exporter 5.2.40.
Native admission supports 1–16 unparented eight-vertex/six-face mesh boxes, zero
materials/textures/rigs/animations/modifiers/constraints/GN/drivers/libraries.
The exact factory addon set is required. Missing library/texture and driver/addon
cases run inside actual Blender, restore the source, and cannot export invalid
input. Only this narrow profile is supported; unsupported dependencies are
rejected, not silently omitted.

Native Job settings are applied and queried before releasing the process gate:
2 GiB committed memory, 15 seconds user CPU, four processes. Wall timeout is
20 seconds; each log is bounded to 256 KiB. The 32 MiB workspace bound is a
reactive watchdog, **not a filesystem quota**. Inputs are at most 8 MiB; GLB is
at most 4 MiB. No compression, external URI, texture decode, extension, hierarchy,
or unbounded accessor is supported. The parser checks decoded finite positions,
normals, indices, counts, byte ranges and declared bounds. Actual output vertices,
names and TRS bind to the reopened source snapshot, including Blender XYZ to
glTF Y-up rotation conversion. This is not Khronos validation or a GT05 import.

Evidence: 83 Python tests and 31 native checks; nine native admission rejection
cases; two successful capped background jobs; real deadline, over-limit allocation
and active-export Stop. Deadline and Stop deliberately terminate the exact Job:
their helper cannot write process-exit.json, so null remains null. A retained
native process handle independently observes live→exited (exit2), plus checked
Job zero. The OOM case raises MemoryError under the queried 2 GiB cap and has
actual Blender/helper exit17. Failed jobs produce no output/result receipt.
The Stop/deadline fixtures deliberately pause the actual background worker after
reopen/preflight and before the fast glTF operator; they establish owned active-job
cancellation, not timing inside the glTF operator itself. The OOM fixture uses a
deliberate 3 GiB allocation, not an artist workload.
Export retries return the same original in-memory result without a second job;
an uncertain failure keeps a tombstone until this owner ends.

Run the read-only check from repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-export-audit/verify_evidence.py
```

The checker recomputes exact source inventories, source-map equality at each
launch, raw unittest/native markers, actual host exits, source/output digests,
GLB postconditions, caps and fault records. Portable artifacts include complete
frozen source plus the minimum raw logs, metadata and owned input/output needed
for these claims. Private user/temp caches and unrelated diagnostic trees are
excluded. Original failed or superseded evidence stays untouched.

Still open: durable public journal/recovery and writer lease, public ACK, general
artist-file sandboxing, power-loss publication, native handle-close fault recovery,
broader materials/texture profiles, and two independent reviewers. Do not equate
this candidate with complete GT04 or open GT05 from these results.

Relevant primary references: [Blender threading restrictions](https://docs.blender.org/api/main/info_gotchas_threading.html),
[Blender glTF operator](https://docs.blender.org/api/5.2/bpy.ops.export_scene.html),
[glTF 2.0 format](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html),
[Windows Job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).
