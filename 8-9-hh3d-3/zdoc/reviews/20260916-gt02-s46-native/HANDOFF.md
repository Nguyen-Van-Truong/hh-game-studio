# S46 managed service native handoff

AUTHORITY=0. Diagnostic PASS; acceptance and general safe-write remain false.

Final run: `GT02-S46-NATIVE-01`, `run-01`, started
`2026-09-16T15:37:38.566927+00:00`. Exact 106-file runtime closure:
`f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf`.
The complete map is in `run-01/managed-native-stdout.txt`; original source and
immutable runtime snapshot were unchanged at completion.

| Native child | Verified behavior | Actual exit |
| --- | --- | --- |
| create | discovery/inspect/lease; activation to generation 1; COMMITTED control lookup; exact retry; final ready inspect | 86 |
| replace_stop | managed owner close/reopen by storage ID only; new worker/session/lease; replacement to generation 2; COMMITTED lookup/exact retry; durable Stop | 86 |
| drop_reply | work pipe closed without receiving reply; healthy control lookup UNKNOWN, inspect and durable Stop; generation remains 0 in this run | 86 |

No host direct dispatch or manual phase advancement substitutes for the service.
Credential bootstrap was server-to-child over the bound work channel, absent
from environment/argv and native artifacts. Plain/hex/base64 bearer scans passed.
The C parser is diagnostic only. Owner reopening occurred in the same broker
process and is not represented as a new process crash-recovery test.

All 21 denied-access rows returned ERROR_ACCESS_DENIED (seven attempts in each
child; exact rights recorded). Each child also queried/set/queried its accessible
same-prefix registry positive control; host readback verified CHILD_OK. Before
bootstrap, protected custody bytes/event binding/root names were unchanged.
For the replacement case, the existing active file identity and bytes were also
unchanged by those attempts. The field
`existing_active_file_identity_and_bytes_unchanged_before_bootstrap` is false
for fresh create/drop cases because no active file existed; that check applies
only when an active file exists.

Each child Job had zero active processes and an empty PID list. All service
threads joined; endpoint, I/O and event owner registries were empty. MSVC compile
and link exited 0; their owned helper Jobs were drained to zero. The outer runner
captured actual exit 0, `tree_verified=true`, `timed_out=false`, and final PID
sample `[]`. No worker was forcibly terminated. Three exact newly-created UUID
registry leaves, AppContainer profile, temporary directories and runtime snapshot
were removed; shared product keys were preserved.

Evidence SHA-256:

| File in run-01 | SHA-256 |
| --- | --- |
| capture.json | `d7b8d1c015218580b0c79e91dc5593670b2b0431737ca73c76b805a2ea7162c3` |
| managed-native-stdout.txt | `36b4c8de7ff771e67ac687b88884a0a6a5da061087e997353273fa4a786f961c` |
| managed-native-host.json | `17c31da13324d899d82bc75ff2741cf65ec907135237fe6e534a9a3c72168ade` |
| managed_probe.py | `d8241dfcb4c2cb6d8ee753b21250b5e27b45f658caef9490daa6d438a1e3f34b` |
| boundary_child.c | `035ab34dfade18844751480d3c7f088dbb75dfec3e8b8f48e0e5bda4dc3235f2` |

No production source, plan or commit was changed by this worker during S46.
The lifecycle design report is `../s46-lifecycle-design.md`; its initial model
predates the separately corrected deadline watcher. Final evidence above loads
the corrected frozen service, not that earlier draft.
