# S103 retained-handle attribution design

This is a read-only design record. It does not alter the formal runtime,
baseline, gate, workload, source closure or acceptance dataset, and no engine
was launched for this record.

The S103 prefix measured editor `GetProcessHandleCount` values
`565, 563, 559, 555, 555, 561` for batches 0–5. The unchanged
`screen_sample()` gate compares measured batch 5 with exact batch 4, so the
561 value is a valid `CAMPAIGN_RETAINED_COUNTER_GROWTH` failure. The sequence
is non-monotonic and the raw packet has no handle type, object identity or
post-idle stabilization. It therefore shows a counter excursion only; it does
not establish a leak or its cause.

The narrowest useful future probe is two supplemental snapshots only: one
after the exact batch-4 post-quiescent observation and one after the exact
batch-5 observation, after the original counter and gate have already been
recorded. Keep both snapshots outside the measured status-gap interval and
never substitute them for the original counter. Record the capture start/end,
walk duration, `HandlesCaptured`, original counter, target PID plus process
start and executable binding, source/profile hashes, and the observer's own
handle count before/after. A missing or failed snapshot is `UNKNOWN`.

Windows Process Snapshotting (PSS) is the candidate API:

* [`PssCaptureSnapshot`](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot)
  with only handle/basic/type-specific capture flags;
* [`PssWalkSnapshot`](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalksnapshot)
  using `PSS_WALK_HANDLES`; and
* [`PSS_HANDLE_ENTRY`](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry)
  plus [`PSS_HANDLE_INFORMATION`](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_information).

Copy and hash type/name bytes while the walk marker is alive; do not log raw
object names. Numeric handles are reusable, so identity matching requires the
handle, type, redacted name hash/length and type-specific PID/TID where valid;
unnamed entries remain `UNKNOWN`. Always free the marker and snapshot in a
`finally` block. Bind capture to the already-owned child process handle and
its PID/start/executable; do not enumerate or open unrelated processes and do
not request `SeDebugPrivilege`.

PSS documentation does not guarantee zero observer overhead or no target
quiescence. The two snapshots are supplemental attribution only, and their
capture time must not enter the original measured gap. If the narrow probe is
implemented, it needs a fresh diagnostic ID and a fresh static review before a
formal campaign. S102/S103 raw evidence remains immutable and no formal
launch2 is authorized by this design.
