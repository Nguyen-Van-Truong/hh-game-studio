# S49 — complete managed Godot fixture bundle and publication boundary

AUTHORITY=0. READ_ONLY_DESIGN=1. IMPLEMENTATION=NONE. TESTS_RUN=NONE.
Date: 2026-09-17, Asia/Saigon. Baseline Git HEAD:
`933c13491f10d9ecc738cf465968c1b2dba9a4c5`.
This report is the only file written by this design task. No engine, test,
publication, core change, acceptance signature, commit or plan tick was made.
S48 implementation/evidence was read while the coordinator retained its freeze.

The next bounded lane should implement **a new complete-bundle codec and actual
private-blob staging/readback**, with public save/script capabilities still
disabled. Keep the accepted core and existing v1 bundle/journal semantics
unchanged. A protected selection owner and generic restart write authority are
subsequent gates, not consequences of storing a new manifest.

## Observed omission and exact source inputs

GT-01 in `../8-9-godot-blender-agent-studio-plan.txt`, lines 578–580, classifies
Godot-generated script `.uid` files as fixture source retained in VCS, while
`.godot/` is excluded cache. The actual S48 package
`20260917-gt03-s48-editor-01` supplies these concrete inputs:

* `packed-scene.tscn`: 572 bytes, SHA256
  `8e6b2737b2fddefac1ac6ef40667f5624e6674ed15e5539e86e4cecfd629aba8`.
  Its scene UID is `uid://c4p3hprrm2xq3`; the external Script entry binds
  `uid://dc8011bj471fi` to `res://scripts/fixture_actor.gd`. The root attaches
  that resource and retains the exported `fixture_value = 23`.
* `fixture_actor.gd.uid`: 20 exact bytes,
  `b'uid://dc8011bj471fi\n'`, SHA256
  `1dd4f1d29d1cfc30a4777088c4fa9ddf63577cbda38ccad658abb2ec58eb5b42`.
* The runner authors the trusted script as
  `extends Node3D\n@export var fixture_value: int = 7\n`; its hash in
  `fixture-inputs.json` is
  `7baa116876bb347f265768f93cf6d0821a6c6b082e8d84f1434267fb69d31c7f`.
  This report did not execute or regenerate that script.
* The package reports 103 edit, 10 reopen and 31 contract checks; edit/reopen
  saved semantic revision is
  `sha256:55dd888f474d6f0f29b5d9957cbc07adcdab51f3221429d6b3c760604d6e430d`.
  Its capture identifies source closure
  `f07f818f092bbb57b4d810e10eda2d3ac0ba126022786e250b8d4d905946c386` and retains
  `production_save_verified=false`, `hostile_script_sandbox_verified=false`.
  These are existing package contents, not a new test or acceptance verdict.

The v1 codec includes only scene/script bytes. The initial fixture-input map
also predates generated UID capture. Thus neither its two-file project revision
nor that initial map is a complete selected runtime source manifest. The S48
script attachment evidence does not silently repair the bundle contract.

Reviewed implementation bytes, paths relative to `studio/`:

| Input | SHA256 |
| --- | --- |
| `godot-addon/bundle.py` | `c246403fb0e40e49d33c638c29fd097a32d72631d22166b19f6acc483c25824f` |
| `godot-addon/publication_state.py` | `cee38e70be71c0d143dff7fa07103246bbbec0ea9d56e7d51ed4fb1077e5fbf1` |
| `godot-addon/publication_journal.py` | `aa230fc6f31bec6ae69c7192cba92bbd6438cf00a4a0680fd2ce26f55cd02f23` |
| `host/core/private_store.py` | `c914b5a66a45660c782ecd43fd2321c238702340f3b33062e284feada4d46476` |
| `host/core/private_events.py` | `5beb556dda4e9c7f137ece366b1ed231bf3b5039e365299f657b089911cf9171` |
| `host/core/safe_replace.py` | `369459bb5fca4ebaf11a4ce9ac848024a9f63502a0df4bbe68d5aa585e2e3fb9` |
| `host/core/custody.py` | `aa4320faeccb3b729d0eebf29ac3e962d2590bca1e3aba14b0aef620b021fbc9` |
| `tests/godot/run_editor_probe.py` | `94e875368aa30057b760fe1ce257182c7e846b7779d8e778af89e08cf4766380` |

## Minimal versioned content contract

Add `bundle_v2.py` with schema `hh-godot-fixture-bundle-2`; retain `bundle.py`
and its v1 decoding/revisions unchanged. Do not supply optional UID fields to
v1 or reinterpret existing hashes. An explicit v1-to-v2 construction requires
the actual missing UID and trusted source bytes; no default UID, regenerated
source substitute, or automatic journal migration is allowed.

The immutable v2 bundle contains the **actual bytes** of every file in one
closed fixture profile. Trusted source hashes alone are insufficient unless
their exact bytes are also available and verified for materialization. Use one
flat fixed path map with `{sha256, size_bytes, role}` entries; role is determined
by the host profile, never chosen by the requester.

| Paths / role | Ownership and allowed change |
| --- | --- |
| `scenes/fixture.tscn` / `managed_scene` | Approved main-thread scene serializer; owner checkpoint before destructive edits. Preserve the scene's embedded UID and approved attached script reference. |
| `scripts/fixture_actor.gd` / `managed_script` | Bounded `script_text.replace` only after its separate admission/validation gate. |
| `scripts/fixture_actor.gd.uid` / `managed_uid` | Source owned with that fixed script identity; immutable during text replacement and ordinary save. A UID/rename change requires a separately specified migration. |
| `project.godot` / `trusted_config` | Exact host-pinned configuration; never worker-editable. Any config change creates a different trusted profile/revision and invalidates prior validation. |
| `addons/hh_studio/plugin.cfg` / `trusted_addon` | Exact release bytes. The S48 diagnostic plugin.cfg rewrite is a different profile, not a production default. |
| `addons/hh_studio/plugin.gd`, `scene_commands.gd`, `jcs_godot.gd`, and each adjacent `.gd.uid` / `trusted_addon` or `trusted_uid` | Copy only from the reviewed trusted release; verify exact source mapping before engine access. `jcs_godot.gd` originates from the pinned protocol source copy, not an editable duplicate. |

This managed profile has eleven content files. Do not include the S48
diagnostic plugin/probe in a production profile implicitly. Any future trusted
readback bootstrap is pinned separately in the validation execution manifest;
if the selected project itself references it, it becomes an explicit trusted
content entry. The profile forbids all other dependencies, autoloads, importers,
extensions, extra scenes and script references until their exact paths and
ownership are separately versioned. `.godot`, logs, reports, temporary output
and duplicate packed scene copies are never selected content.

The evidence above retains the actor UID but does not supply an authoritative
complete set of addon UID sidecars. Before publishing a v2 trusted profile,
capture those sidecars once through owned trusted import, retain them as source,
and freeze their exact bytes. Do not invent their values or call missing sidecars
optional. A recreated fresh cache must consume those same source sidecars.

Suggested closed manifest body:

```text
schema: hh-godot-fixture-bundle-2
profile: hh-godot-managed-fixture-1
files: exact profile path -> {sha256, size_bytes, role}
trusted_source_revision: sha256:JCS({profile, trusted file metadata})
caller_observations: {scene_revision, engine_sha256}
project_revision: sha256:JCS(all fields above except project_revision)
```

The host independently checks the trusted subset against its approved release
before constructing the bundle; a self-consistent caller-provided trusted hash
does not confer trust. Keep the manifest itself outside `files` to avoid a
recursive self-hash. Store it as a separate blob with its own exact byte hash.
Use shared JCS unchanged and reject unknown fields/paths, aliases, traversal,
case collisions, malformed UTF-8, noncanonical manifest bytes and all content
hash/length mismatches. UID lexical screening is bounded ASCII with one LF;
actual Godot UID resolution and scene/reference agreement remain engine checks,
not claims inferred from a regex.

Proposed codec bounds: at most 16 fixed-profile content files; scene ≤1 MiB,
script ≤16 KiB, each UID ≤128 bytes, project config ≤16 KiB, plugin config
≤4 KiB, each trusted `.gd` ≤128 KiB, manifest ≤16 KiB, entire bundle including
manifest ≤2 MiB. These are new explicit profile limits, not increases to GT-02.
Reject before allocating/copying unbounded inputs. Exact profile path count
remains mandatory even when it is below the general cap.

## Revisions and preconditions must remain separate

* Envelope `expected_revision`: complete live semantic scene hash. Dirty
  in-memory edits may change it before a selected bundle changes.
* Payload `expected_project_revision`: complete selected v2 bundle revision,
  including UID/config/addon metadata. UID-only or trusted-source-only changes
  invalidate stale mutation/save admission even if semantic scene state agrees.
* Editor session ID and generation: process/reload identity, separately fenced;
  neither is a content revision.
* `parent_selection={generation, identity}` and native `FileVersion`: logical
  selection CAS and actual protected active-manifest file CAS. Restoring equal
  content still creates a distinct selection generation/identity.
* Validation execution identity: source closure, profile, bootstrap bytes,
  binary hash, host-owned job/run ID and actual outputs. This is evidence about
  a particular candidate, not part of an unverified client assertion.

In a later catalog revision, `scene.save.expected_files` must contain the exact
complete profile hash map; retain the existing semantic/project CAS fields.
The trusted context supplies full verified file hashes and profile identity.
`script_text.replace` additionally keeps `expected_sha256` and a required
`expected_uid_sha256`; its result preserves UID, scene and trusted bytes unless
the separately specified engine serialization requires an explicitly reviewed
scene candidate. All non-inspect commands/previews bind the complete project
revision, and both preview layers must agree. Continue stripping host-only
preconditions from the narrow scene-engine projection.

Do not change shared protocol schemas. A subsequent Godot catalog/digest and
vector schema revision identify these changed addon payloads. Inspection reports
the semantic revision, selected complete-project revision and selection identity
distinctly. Receipt lookup remains before new admission: changed digest is an
ordinary no-effect conflict; original lookup and Stop remain usable.

The initial bounded implementation should use one pinned runtime binary in the
bundle's `engine_sha256`, consistent with v1. Linux validation under a different
binary is separately recorded evidence. Do not substitute that binary into an
existing project revision or treat same source commit as an already proven
cross-platform equivalence/readback policy.

## Actual private staging and readback

Add an internal `bundle_staging.py`, importing only `studio.host.core` native
types. It takes an exact validated v2 bundle and the lifecycle owner's exact
`PrivateBlobStore`; no raw store path, callback, client-supplied descriptor or
preexisting external filename is an authority.

1. The owner acquires its one lifecycle lock and rechecks live root/custody,
   Stop, lease/deadline, project/selection CAS and resource reservations. Before
   any staging effect, persist bounded PREPARED ownership identifying command,
   candidate, source manifest hash and worst-case pending allocations. For the
   next isolated storage test lane this intent is explicitly test-owned; it is
   not represented as a public publication command.
2. For each fixed path, call `put_bytes(exact_bytes)`. Keep the returned exact
   `StagedBlob` type and actual FileIdentity. Immediately call `read_blob(blob)`
   and independently compare raw bytes, length and SHA256 against the bundle.
   Stage and read back the canonical manifest last. Do not trust copied JSON
   fields or a successful `put_bytes` call without the subsequent complete-set
   readback/decode.
3. Reconstruct the full mapping only from the verified returned descriptors,
   call the v2 decoder, and require byte-identical canonical manifest and
   project revision. Return an immutable internal stage record binding native
   store identity, complete descriptors and manifest descriptor; no active
   selection, engine-valid flag or public ACK is returned.
4. Replay uses descriptors from the protected typed journal only. Convert them
   to exact `StagedBlob`/`FileIdentity`, then perform actual `read_blob` on every
   object; compare identity, size and hash and decode the whole bundle again.
   Merely matching a descriptor's volume or project metadata is insufficient.
   The current journal deliberately does not perform these candidate reads.
5. A failed/ambiguous put, read, close, barrier or descriptor persistence keeps
   the reservation/data and holds the owner. Never repeat a put on same-ID retry
   to manufacture a second candidate. A crash after a native object is created
   but before its descriptor is durable remains an orphan/unknown allocation;
   no public API currently enumerates and safely adopts that orphan.

The existing store caps remain 64 blobs, 8 MiB aggregate, 1 MiB per blob.
Worst-case full checkpoint + last-good + candidate under the proposed codec
bounds consume ≤51 blobs and ≤6 MiB including their manifests, leaving room
only if actual existing/orphan reservations permit it. Compute real remaining
budgets before each allocation; do not assume the nominal remainder is free.
Reuse verified immutable trusted blobs by exact descriptor when available,
without relaxing within-manifest path/identity rules. No garbage collector or
deletion permission is introduced in this lane.

`PrivateBlobStore` proves native file flush and retained-handle byte readback,
but its documented public API does not expose a generic blob-namespace directory
durability acknowledgment. Therefore the new stage record must not claim
power-loss-safe publication merely from repeated reads or a durable journal
descriptor. Full publication needs a separately verified namespace/barrier
solution inside the authorized addon boundary, or an explicitly opened core
change; neither is silently supplied by this report.

## Protected selection and restart boundary

The later **Godot-specific selection owner** uses the same lifecycle/native
resources as the journal; it must not create a competing writer or inject a
Godot consumer into the fixed inert FixtureSelector. Use one compact, closed
`hh-godot-active-selection-1` `active.json` (proposed cap 4 KiB) that names the
project/profile, candidate/project revision, complete manifest blob descriptor,
parent/current selection identity, command/digest and tool/source binding.
It selects one complete manifest, never independent scene/script/UID files.

For a fresh root only, the existing `create_new`/`atomic_replace(...,
expected=FileVersion)` can supply native file selection CAS. Persist ACTIVATING
intent first; compare the actual previous selection and original admission;
perform native replace; read back the active file and full candidate blobs;
require `confirm_barrier`; then reopen the selected complete project under an
owned verified engine context before READBACK/terminal acknowledgment. Stop
and source/CAS/lease checks recur after slow validation and before each effect.
The active marker's rename/flush is one link in that chain, not the ACK.

Do not seed public last-good authority from today's caller-supplied CONFIG.
A new v2 owner requires an explicit bootstrap-incomplete state and a typed
INITIALIZED transition after actual baseline staging, selected-manifest
readback and engine verification. Failed/partial bootstrap stays unadvertised
and preserved. Define this in `hh-godot-publication-event-2` before implementing
selection; old event-1 histories remain read-only with their original meaning.
Carry the full v2 profile/file set through PREPARED, candidate, observations,
current-state guards and receipts. Check actual canonical event sizes against
the existing 12 KiB reducer and 16 KiB native frame limits before admitting a
profile; do not simply raise core limits to fit an oversized object.

Restart remains **read-only**: `ProtectedFileRoot.reopen_readonly` and
`PublicationJournal.reopen` cannot authorize writes. The private
`_rearm_verified_snapshot` requires the fixed `_fixture_file_consumer`; do not
set that marker, flip `_readonly`, subclass/spoof the consumer, or wrap an inert
COMMITTED receipt as Godot permission. Generic Godot rearm is unavailable.
Implement/review an addon-specific native lifecycle with its own recovery proof
in a later bounded lane, or request an explicit scope decision for a core API.

Until then: exact completed receipts may be returned historically; pending
staging, a witnessed active change without terminal completion, mismatched
selection or an event suffix ahead of custody remains held. No automatic
activation, retry put, rollback, witness advance or fresh lease can turn that
history into resumed effects. Preserve all relevant candidates/checkpoints.

## Immediate implementation lane and required evidence

Limit the next lane to `bundle_v2.py`, `bundle_staging.py`, their documents and
Godot-scope tests. Keep publication_state/journal v1, protocol/core, native
rearm and public capability flags untouched. The lane may establish real
protected-byte staging and complete-file hash binding, not engine validation
or public save availability. Bundle materialization, validated script profile,
selection/INITIALIZED event-2, namespace durability and restart writes follow
as dependency-gated work.

The concrete tests to author next, **not executed by this report**, are:

* v1 remains byte-for-byte compatible; v2 rejects missing UID/trusted files,
  extra paths, malformed/case-alias paths, false roles, oversized/noncanonical
  manifests and copied metadata inconsistent with bytes. A v1 bundle alone
  cannot convert to a complete v2 bundle.
* UID-only, config-only and addon-only changes alter complete project revision
  while a supplied semantic scene revision remains unchanged. Text replacement
  preserves exact UID/trusted bytes and rejects stale script/UID/project hashes.
* Actual fresh protected roots: stage all bytes, read all native descriptors,
  reopen store by typed root identity, reconstruct and decode the complete
  manifest. Wrong root/FileID, swapped content, truncated UID/manifest and a
  descriptor with a valid-looking hash fail actual readback.
* Fault cuts before/after each put/read/descriptor record; late errors preserve
  unknown allocations and reservations, do not retry effects, and retain exact
  cleanup owners. Exact command retry returns the same internal stage receipt;
  changed same-ID content rejects without blocking Stop or original lookup.
* Count/byte exhaustion accounts for last-good, checkpoint, candidate and
  orphan allocations. Owned process deadlines, captured real exits/tree drain,
  before/after source manifests and preserved failure logs accompany the native
  run. No fake engine result makes a stage receipt public COMMITTED.

For later engine proof, a clean cache must resolve the exact retained script
UID and attached script/hash/export from the selected manifest; a duplicate
scene UID copy must not exist in the imported project. All generated-script
validation remains subject to the separate S48 attribution/closed-profile
design and executor availability gate. Hashing trusted bootstrap/config bytes
or observing process exit cannot authenticate a report produced after hostile
candidate code has executed in the same process.

Public status after the proposed immediate lane remains: internal complete
bundle codec and native staging/readback available to the trusted owner only;
`scene.save`/`script_text.replace` runtime enablement unchanged/false; engine
facts are attestations until independently established; no production save,
generic restart rearm, arbitrary-script validation or GT-03 acceptance claimed.
