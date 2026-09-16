# S55 bounded evidence gate map

Candidate source: `../20260917-gt03-s55-source-01`, all **176 files**, closure
`3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e`.
This is an evidence map, not a tools-plan update, acceptance verdict or tick.
The prior map reviewed here is `../20260917-gt03-s54-gap-audit/gt03-closeout-map.md`,
SHA256 `17d5071856be1dbfaa5b3b32b6d936da47f13f1ea23b1215713c070069387b3d`.
Its final requirement is affected regression on one source plus complete raw
evidence and two independent critics; it does not require every adjacent hook
or unrelated GT-06/GT-07 workload to be rerun.

| Requirement / fault class | Bounded S55 lane | Status observed by this audit |
| --- | --- | --- |
| Scene capture, Linux validation, selected bytes, original durable response/retry | `save` | `20260917-gt03-s55-save-01`: actual host 0, 18 producer checks; 11 final events, two Linux executions, canonical original/duplicate/lookup responses and same-editor readback verified. `native-exports02` binds 15 native records and 11 selected files. No raw HTTP reply wire was retained by this fixture; canonical durable bytes and decoded HTTP content are checked. |
| Script preview/publication, retirement, fresh generation and script readback | `script` | `20260917-gt03-s55-script-02`: actual host 0, 32 producer checks; 13 final events, two Linux executions, original raw reply wire/duplicate/lookup and old/new editor bindings verified. Explicit cleanup driver below. `native-exports02` binds 17 native records and 11 selected files. Failed `script-01` remains failure. |
| Authenticated CRUD, Undo/Redo, checkpoint observations, final save and idle durable Stop | `edit` | `20260917-gt03-s55-edit-01`: actual host 0, 61 producer checks; 29 events replayed, six original response wires, raw checkpoint/effect/readback files and two Linux executions verified. `native-exports01` binds 33 native records, 11 selected files and 18 checkpoint/observation blobs. |
| Canonical Stop while actual Linux validator runs; immediate latch and later drain | `stop` | `20260917-gt03-s55-stop-01`: actual host 0, 20 producer checks; five events replayed, actual running inspect/timing, dirty-state preservation, original UNKNOWN and two Linux executions verified. `native-exports01` binds nine native records and 11 selected files. |
| Two writers, FIFO, real expiry, stale fence, cancellation and Stop | `fifo` | Pending |
| Original capture before durable capture event; fresh registered recovery and last-good restoration | `recovery-publication` | Pending; expected original host exit 92 |
| Actual selector CAS before durable SELECTED | `scene-cas` | Pending; expected original host exit 93 |
| Durable witnessed terminal before original response returns | `script-committed` | Pending; expected original host exit 94 |
| Script editor retired before selector CAS | `script-retired` | Pending; expected original host exit 96 |
| Actual V5 edit effect after EDIT_READY but before EDIT_COMMITTED | `edit-applied` | Pending; expected original host exit 98 |
| Original terminal appended without saved custody witness | `script-unwitnessed` | Pending; expected original host exit 95 |

The pending rows are existing affected regressions, not new requirements.
`20260917-gt03-s55-units-01` completed **699/699**, zero failures/errors/skips.
This audit rebuilds all six sealed attempts from the pinned unit controller,
checks actual target/wrapper exits, identical full inventories and disjoint
complete selections, and binds the retained round to the unchanged 176 files.
`20260917-gt03-s55-recovery-inspection-native-01` additionally completed **4/4**;
these tests overlap the 699, use native storage with synthetic readback, and do
not supply a separately retained raw crash91 subprocess package. Existing S54
component evidence remains supplementary and
does not acquire an S55 closure by being cited here.

## Exact runtime and supplemental execution map

`script-01` is retained with actual target exit **1**, wrapper exit **0**, clean
owned Job and unchanged runtime. It called `owner.close()` while durable Stop
was `PENDING`, which correctly raised `GODOT_STOP_DRAIN_REQUIRED`. Earlier
successful assertions from that run are not counted as a completed lane.

Coordinator-owned `run_drained_publication_lane.py` is pinned at
`cf36f1c33fb7d76d18bdcac58b62b930913f05ded8f1f575fe8c4be68266e8e4`.
It creates a separately identified script/save driver from the original probe,
changes only its exact snapshot root binding, and waits up to the existing
25-second edit-fixture bound for durable Stop before close. It preserves the
pre-Stop events/snapshot and then records terminal events. The verifier rebuilds
the driver bytes and compares invocation, source reference, capture and the
effective-execution map. Script02 driver is
`65289bd65371ff1dd132d9a4ae82406db2238766d1d8975968d6a8c8d6eddf2b`.
Its saved initial Stop was `PENDING`; terminal `DURABLE` arrived after 4390 ms,
so HTTP 200 came from an actual poll. If initial Stop is already durable, the
helper's initial HTTP code is assumed; the report will not claim that code was
independently observed. Native terminal state remains required in either case.
Save01 driver is
`fc1f6498320de8340a8b8bbabcd8471a0cf092ec81a6e7b0929915bae662c09a`;
its initial Stop was also `PENDING`, followed by polled `DURABLE` after 3906 ms.

Every new semantic report writes `effective-execution-manifest.json`. It keeps
runtime closure `3a220b...` distinct from the effective execution closure, whose
canonical hash covers all 176 runtime/unit file hashes, exact external driver
and controller bytes, plus each lane's entrypoint/dependency map. The 699 unit
tests did not execute the external cleanup drivers. An incomplete map remains
candidate evidence; the final two critics must sign the same complete layered
manifest, not transfer signatures from an earlier source or partial map.

## Adjacent hooks: equivalence, not claimed execution

The frozen `publication_recovery.py::classify` uses typed phase, selected versus
last-good, original terminal witness and registered authority. Recovery always
uses a fresh editor; it never resumes a crashed editor's volatile UndoRedo.

| Unexecuted hook | Covered fault class and explicit boundary |
| --- | --- |
| `scene-committed` | `script-committed` exercises witnessed COMMITTED → original exact bytes with fresh registered authority; scene and script share this terminal route. Scene's normal capture/readback is separately exercised by `save` and `scene-cas`. This does not claim the scene-committed hook executed. |
| `edit-ready` | Both hooks persist `EDIT_READY` with selected last-good and no committed edit response. `edit-applied` additionally proves the effect already happened before that same recovery route restores a fresh mirror of selected last-good. The earlier no-effect cut is not individually executed or counted. |
| `script-cas` | `scene-cas` covers post-CAS versus missing SELECTED; `script-retired` covers retirement/last-good; script publication and the script terminal/unwitnessed cuts cover selected script bytes plus fresh script-aware readback. These are component coverage of the shared recovery branch, not direct execution of the combined script post-CAS hook. If final evidence reveals a different state/authority path, that concrete difference warrants this one additional hook. |

No generic arbitrary-path writes, unrestricted scripts, persistent FIFO queue,
dependency scheduler, Play/input or cross-app publication is inferred or newly
required for this GT-03 adapter gate. The supported profile and deferred scope
remain those in the authoritative tools plan.

## Verifier and native export boundary

`verify_semantic_evidence.py` runs without engines or native storage handles.
It verifies the complete shared inventory and common references, controller and
invocation, independent raw exits/PIDs, exact terminal responses, frozen pure
event folds, selected editor files, raw editor transitions and Linux evidence.
It reuses pinned S52 raw process/container checks and S53 receipt/observation
helpers through explicit adapters. Old code and evidence are unchanged.

`semantic-04/verification.json` is the preserved pre-export Stop/edit audit.
`semantic-05` additionally bound the completed units and correctly reported
script01's failed capture. Its missing-export and missing-lane entries reflect
that observation time. Fresh reports supersede only the audit snapshot, never
rewrite those historical bytes. The earlier
`semantic-01` failed due to the new verifier initially using Python JSON number
formatting; the verifier was corrected to the frozen JCS canonicalizer.
This was an auditor bug, not a native fixture failure. Earlier reports remain.

`test_semantic_evidence.py` uses in-memory overlays only: wrong source reference,
raw PID/exit, terminal response, selected FileID/file bytes, final readback and
raw edit observation must fail. Corruption counts are auditor checks, never
product acceptance. New audit runs use fresh report directories.

`export_native_evidence.py` runs only in a coordinator-granted native slot. It is
**non-publishing content verification with write-capable verification handles**:
existing event/blob constructors take existing exclusive handles and may flush
unchanged bytes. It does not create private stores, append events, persist a
Registry change, rearm publication or open a recovery writer. Registry bytes,
event bytes/head/identity, selected FileIDs/content and checkpoint blobs must
match before and after. Any unacknowledged suffix fails closed. A pinned owned
Job bounds the exporter at 300 seconds and records the actual raw exit.

The authorized Stop/edit export is `native-exports01`: actual target PID 20772
exit 0, wrapper PID 16944 exit 0, clean owned Job, no timeout, both resource
chains closed without cleanup errors. The full source remained unchanged.
The portable verifier separately binds Registry project/storage/root/stream
identity, genesis/bootstrap, witnessed head, final selected manifest/FileIDs and
blob content. Reopened stream size is checked against actual bytes; saved
creation-time identity size is not mistaken for current stream length.

`native-exports02` subsequently exported only script02/save01 in its authorized
slot: actual target PID 26288 exit 0, wrapper PID 6996 exit 0, clean owned Job,
no timeout and both native resource chains closed without cleanup errors. The
176-file runtime stayed unchanged. These exports bind the same layered script/
save execution maps already checked above; they do not imply that unit tests
executed the external cleanup drivers.

Each export is a fresh `native-exports*` directory under this audit; one lane
must not have ambiguous duplicate exports. Portable manifests exclude private
storage roots, `.writer`, `.godot`, caches, appdata and temp. The native export
can establish current Registry/FileID facts on the Windows host; the portable
checksum preserves those observations and does not independently recreate ACL
authority. Exports, complete final lane evidence and two same-source critics
remain required before any coordinator acceptance decision.
