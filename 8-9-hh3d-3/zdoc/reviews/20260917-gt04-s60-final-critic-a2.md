# GT-04 S60 — independent final critic A2

Verdict: **PASS / TICK=yes**, for the bounded GT-04 component and supported
profiles specified below, on these exact three hashes:

- Review closure: `8ea276e98f3137a5f3623fce00d0760ae0c1fe6d17a77a330e98fa8839a31950`
- Source closure: `f5ae5dfbb451d3204197c2b21486c586698089ac24d14d23641a9182b5e42673`
- Native execution closure: `407fff4e453fb1702a32fbc8ae1ee5eff7c3dcb0b99338a504ae39dc69d67824`

Reviewer: independent Codex critic A2, task `/root/gt04_s60_critic_a_retry`.
Review date: 2026-09-17; final verification at 10:38 UTC / 17:38 Asia/Saigon.
Inspected HEAD: `38f6b9abd261cfc0f85f5f119a1eeeba84e35c74`.

This is one critic's verdict. It does not change the plan, create coordinator
acceptance, supply a second signature, or open GT-05. I did not read another
critic's report, spawn agents, launch a native engine, stage, or commit. The only
file written by this review is this report. Existing untracked historical
packages were left alone. Tracked status was clean at entry and final check;
no Blender/Godot process was found by the entry/final process checks.

All paths below are relative to `8-9-hh3d-3/`. `A` denotes
`zdoc/reviews/20260917-gt04-s60-audit/`; `R` denotes
`studio/.local/reviews/`; `M` denotes `R/20260917-gt04-s60-matrix/`.
Raw JSON artifacts cited with line 1 are single-line records.

## Authority and independent verification

Read the scoped `AGENTS.md`, current tools-plan table and GT-04 at
`zdoc/8-9-godot-blender-agent-studio-plan.txt:693`, section 2.3, TQ01 at 830,
TQ04 at 848, and TX02–TX06 at 922–945. GT-02 is an accepted dependency;
GT-04 requires the Blender component and explicit supported operations, while
cross-app pipeline/activation remains assigned to later gates.

The check was not based on the headline test counts:

1. Independently recomputed the review hash from its two canonical file maps
   and SHA-256 checked **909 Git-bound working files and 1,385 retained raw
   files**. Separately read every blob with
   `git -c core.longpaths=true cat-file --batch`: all **910 files in
   files.json** match HEAD exactly. The extra file is `review-closure.json`
   itself; this explains 909 versus 910 without dropping a file.
2. Independently recomputed the **140-file source closure** using the documented
   sorted `8-9-hh3d-3/studio/path NUL sha256 NEWLINE` algorithm, and checked
   all **143 native execution files** against the execution map. The initial
   ad hoc source calculation used generic JSON hashing; after consulting
   `studio/build/bootstrap/run_fixture.py:80`, the correct source algorithm
   reproduced the stipulated hash. This was a reviewer calculation correction,
   not a source/evidence change.
3. `python -B A/checkpoint.py check` passed. `python -B A/verify_views.py
   --local-raw` passed all seven packages, including exact raw inventory and
   deterministic view transformations. `A/binding.py:16` was also invoked
   read-only: the pinned actual Blender executable SHA-256 matched
   `8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`.
4. Invoked each profile verifier's `verify()` in a fresh `python -B` process,
   **not its writing main**. Installed an audit hook rejecting filesystem
   writes/deletes/renames/mkdir and subprocess creation after import. All three
   passed with **3,723 assertions per profile**: actual HTTP wire digests,
   exact journal records, grants/discovery, native revision chains, preview
   bindings, selected bundle geometry/materials, unit inventories and actual
   GUI/client/host/wrapper exits. Stored raw units show 599 completed tests for
   scene and 328 for each other profile, zero failure/error/skip.
5. Invoked matrix `verify()` with a read-only raw reader replacing only the
   incidental-artifact copying helper, under the same mutation/subprocess
   audit prohibition. It passed **1,470 remaining semantic/binding assertions**
   over all **17 lanes / 240 top-level checks**. This covers every captured
   artifact hash, launch/runtime bindings, actual process identities and exits,
   unique completion records, crash witnesses and unchanged recovery graphs.
   No native handles were opened. Counts are corroboration, not the sole proof.

## Requirement findings

No blocking correctness or evidence defect was found within the declared
GT-04 scope. The following are the specific grounds for PASS.

### Main thread, native state and Undo — TQ04 / TX02

`studio/blender-addon/adapter.py:24` rejects off-main-thread entry before
importing/accessing bpy. `ui_adapter.py:51` uses Blender's actual UNDO operator;
`:84` resolves a checked owned window/view context, `:100` reads live Edit Mesh
geometry without a mode toggle, `:265` checks revision/context before export
preflight/effects, and `:322` re-resolves stable IDs and verifies the exact
history target after native undo/redo. Fresh inspect/context mismatch prevents
dispatch; history drift cannot silently undo a manual edit.

`studio/blender-addon/ipc_client.py:276` polls control before data and executes
the bounded queue on the Blender timer. Host network/log/watchdog threads are
in `studio/host/blender/ui_host.py`, outside Blender. Authenticated hello binds
the actual GUI PID and records one Python thread. `M/ui/native.json:1` and
the six GUI/background edit/reopen/checkpoint results supply real native
context, edit-mode, history and reopen evidence, not just a mock/UI screenshot.

### Input admission and exact supported profile — TQ04 / TX03 / TX04

`studio/blender-addon/contract.py:13`, `:31`, `:58`, `:69` bound command bytes,
identifiers, finite typed vectors, exact fields and selection state. Public
translation in `studio/host/blender/client_write_catalog.py` delegates to
those validators and provides no arbitrary path/script operation.

The S60 repair is effective at `studio/blender-addon/export_profile.py:35`:
library and image collections reject before filepath access, Blender-relative
resolution, exporter-file scanning, or filesystem probing. Adapter dependency
inspection (`adapter.py:47`) likewise does not dereference these paths.
`ui_adapter.py:235` and `:265` reject stale revision/context before exporter
preflight. `studio/tests/blender/test_export_admission.py:22` and its five
tests cover unreadable filepath properties, absolute/relative/UNC/device/ADS
spellings, packed/generated images and stale export preparation.

Native `M/ipc/admission.json` and `M/material/native.json`, their bound export
results, and `A/native-no-external-io.json` corroborate six library/image cases
with Path and bpy.path.abspath blocked. This is evidence of **rejection**,
not permission to intake external assets. Drivers/addons and unsupported
material grammar also have native rejection rows.

The closed profile is correctly limited to 1–16 independently owned boxes,
finite TRS, up to four opaque original Principled materials, no image/library/
rig/clip/modifier/driver/constraint/URI intake. Its exact declaration is
`studio/blender-addon/SUPPORTED_PROFILE.md:6` and `MATERIAL_PROFILE.md:3`.
Requiring future textures/libraries to be materialized and separately admitted
is consistent with TQ04; the present profile refuses them entirely.

### Lease, FIFO, deadlines, idempotency — TX05 / TX06

`studio/blender-addon/ui_queue.py:62`, `:75`, `:108`, `:164` enforce increasing
native fencing epochs, expiry, exact retry identity and deadline checks again
immediately before main-thread dispatch. The original absolute bound and a
monotonic budget are retained. `studio/host/blender/client_writer_session.py:87`
binds source, generation, actual owner/process/Job, and `:242` consumes the
one-use PREPARED permit. `writer_journal.py:61` prevents immediate acquisition
from bypassing the persisted FIFO; `:107` reserves/finishes the actual next
grant without replaying an unresolved native arm.

`M/fifo/native.json:1` contains distinct actual writer clients, ordered Alice/
Bob handoff, expired/canceled head handling, higher fences and native stale
writer no-effect checks. `M/durable/native.json:1` ties real create/readback to
exact retry bytes and read-only reopen; host death after effect/before terminal
leaves an orphan UNKNOWN and no redispatch. `M/deadline/absolute-deadline-native.json:1`
contains actual expired/null/bool denial records, unchanged scene observations,
one valid create and both past/future-deadline retries with identical receipt
hash `sha256:851e7f57da2e83eb8e5be1125565dce53e7f5643b666c08e1c04e2d59786606e`.

`studio/host/blender/client_writer_owner.py:369` checks historical replay before
fresh admission, persists the common INTENT before effect, and forwards the
original deadline. `:309` holds on an uncertain terminal-persistence reply
without overwriting a potentially durable true receipt. `:289` separates
delivery authorization from already-recorded effect truth. Raw HTTP traces in
all three profiles confirm same-command retries/lookup return the original
terminal, changed payload conflicts, foreign history is denied, and expired
fresh work has no effect.

### Background bounds, Stop, crash and publication

`studio/host/blender/export_job.py:27` sets and reads back Windows Job memory,
CPU and process limits; `:139` launches a gated, separate pinned background
Blender with autoexec disabled, isolated user/temp folders, bounded output/log
capture and a workspace watchdog. `:84` retains exact cleanup owners and
records append-only retry attempts. `studio/blender-addon/export_background.py:20`
checks fixed input hash, reopens with scripts disabled, verifies native semantic
state before export, and validates unchanged context afterward. This is not
claimed as an arbitrary hostile-.blend parser sandbox.

`studio/host/blender/client_writer_owner.py:495` signals all publication jobs
before persistent Stop can wait. `publication_owner.py:338`/`:342` signals
export and native control before its publication mutex. Separate transport
Stop admission and IPC control capacity are retained. IPC/fault/cleanup raw
results show the OOM probe's expected native exit 17, deadline/Stop cancellation,
and genuine zero owned-Job cleanup; an aborted diagnostic is never promoted
into a successful export. The native cleanup retry lane preserves the initial
unknown failure report and closes the same retained owner.

`studio/host/blender/publication_owner.py:123`, `:192`, `:200`, `:259` recheck
authority/deadline at phase boundaries, including before selection. `:165`,
`:174` and `:263` use protected immutable file versions, byte readback and
barriers. `:266` records TERMINAL only after complete selected-bundle readback.
`client_writer_owner.py:318` separately binds that publication terminal,
manifest/artifacts and common client receipt. File preview confers no effect
authority; capacity is checked again on apply.

Independent raw extraction confirmed all three profiles publish the observed
`probe_box`: location `[2,-3,4]`, rotation `[0.25,0,-0.5]`, scale `[1,2,0.5]`,
eight vertices/six faces, and opaque `probe_copper` with base color
`[0.25,0.5,0.75,1]`, metallic `0.5`, roughness `0.25`. Their native revision is
`sha256:9c2205007254681e23f3bcaf694532900c964e29ff3d960f79b024d7b621b569`.
The selected manifest snapshot equals the final native observation, with empty
external inputs and `original-fixture` license. Journals follow
GENESIS→CONFIG→INTENT→STAGED→SELECTING→TERMINAL→STOP, with actual GUI,
wrapper and separate client exits zero and owned Job zero observed.

The five crash cuts in `M/*/observed.json:1` have actual host exit 86 and dead
owned children. Recovery remains UNKNOWN after INTENT, before selector and
after selector; an unwitnessed terminal suffix is HELD; only the witnessed
terminal is COMMITTED. Four Stop cuts return native Stop in approximately
16–31 ms: UNKNOWN before the terminal, exact COMMITTED after it. Every recovery
graph remains byte-identical and `live_scene_recovered=false`. These are actual
cut-point/process proofs, not merely reducer predictions.

## TQ01, portability and limits of this verdict

The current committed evidence is explicitly a transformed explanatory view.
`A/evidence_view.py:84` omits source/binary content from transformed text and
retains their raw hash/length; `:157` verifies view inventory, raw inventory
and transformation identity independently. `A/README.md:42` explains the two
hash domains. I verified exact raw locally and the view transformation, rather
than treating sanitized process logs as original bytes. Known workstation-path
literals were absent from the portable text scan. `toolchain.lock.json` and
the complete original source mapping remain available from Git.

This is adequate for this **local exact-closure review and GT-04 component**:
TQ01 requires a portable pinned lock/fixture and clean evidence without personal
absolute paths; it does not turn a sanitized log into a native binary. A clean
checkout can inspect the view and rerun the fixture recipe, but cannot assert
possession of the old raw .blend/GLB/process bytes. `A/clean-checkout.json`
correctly says `exact_original_bytes_reconstructed=false`. Loss or alteration
of retained raw invalidates later exact-raw verification; this signature must
not be copied onto a reconstructed or freshly rerun closure.

The precise limitations are:

- Supported host here is the pinned Windows Blender 5.2.1 owned fixture.
  The GUI mutation contract and three fixed create-only protected publication
  profiles pass; arbitrary artist-file intake and arbitrary paths do not.
- All responses remain `public_ack=false`, and live edits remain
  `scene_state_durable=false`. Only the selected immutable bundle claims
  `durable_publication=true`. Historical response replay and read-only checkpoint
  inspection do not restore writable GUI state or Undo history.
- Deadline/Stop bounds admit already-started synchronous native/disk operations
  to drain. The disk-space bound is a watchdog, not a filesystem quota. Disk-full
  terminal persistence is fault-injected at
  `studio/tests/blender/test_durable_session.py:81`; this is not a physical
  disk-exhaustion or power-loss certification. The publication/storage threat
  model remains the accepted confined worker, not unrestricted broker/admin
  writes.
- This review revalidated frozen raw evidence and code. It did not repeat the
  native engine suite or the 599 unit executions, download the official tools
  afresh, or claim performance/visual/gameplay acceptance. Cross-app activation,
  Godot pipeline art parity, Android, product release, and HH World remain their
  later plan gates.

**Final: PASS / TICK=yes on the review, source and execution hashes stated at
the top. No blocking revision is requested within this explicitly bounded
GT-04 scope. Coordinator still needs the other independent same-closure
verdict and its own acceptance action.**
