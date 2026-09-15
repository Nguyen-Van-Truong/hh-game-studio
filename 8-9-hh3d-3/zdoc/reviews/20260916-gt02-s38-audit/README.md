# S38 fixture activation and explicit recovery — CANDIDATE

Frozen closure: `370e98395f8e75f7b48b4b290790a026ca5fdb27008da14cd584b4c51db32b59`.
Source/evidence checkpoint: `2e24912f704110cde4b1d09521e9e26072ffba62`;
exact index and HEAD reconstruction both passed.
82 source files, 9 candidate artifacts. Protocol **263/267 passed + 4 explicit
skips**; bootstrap **56/56**. Actual owned host exits/tree checks passed and
source/snapshot stayed unchanged. Python/Node/Godot agree on 2,396 canonical
rows; nine Godot invalid cases reject. This is coordinator verification only:
no independent review, safe-write capability or gate acceptance.

The selector persists complete intent and quota reservations before staging,
checks lease/fence/source/game/parent state, and separates selected generation
from actual consumer adoption/readback and COMMITTED. Reopening never resumes
pending effects automatically. Explicit reconciliation can discover a complete
old manifest after its STAGED record was lost, avoiding duplicate files.
Partial/ambiguous staging remains preserved. Restore appends a generation and
records UNKNOWN/restored after verified consumer readback; it does not erase
history or roll back a newer observed owner revision.

27 selector tests passed, including nine real child-process cuts. Each cut has
an armed marker, actual PID/exit 81, reopened phase and generation/blob count
after explicit recovery. The full candidate contains all nine structured
records. These expected crash exits are recovery evidence, not application
success. Other tests cover quota refusal before intent, two-parent contention,
expired lease recovery, false readback, receipt loss and Stop arriving during
quota/pin I/O. Log, store and consumer each have one selector owner.

Five focused runs are preserved with their exact four source snapshots and
invocation/host/log records: 17, 21, 21, 24 and 27 tests passed respectively.
Only run05 is compared to current runtime source. The 45-file diagnostic
manifest prevents earlier run evidence from being transferred to later code.
Earlier S36/S37 diagnostics remain tied to their original Git checkpoints.

`verification.json` maps P-01–P-22 and the later storage/transport/selector
requirements to passing test IDs, verifies source/artifact hashes and parses
the real completion markers. `verifier-negative-checks.json` records rejection
of six malformed crash-evidence variants plus optimized-Python execution.
The previous S35 native counter source remains a byte-identical 73-file subset;
its AppContainer proof does **not** exercise the S38 transaction.

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s38-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s38-audit/verify_git_bytes.py index
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s38-audit/verify_git_bytes.py HEAD
```

Git reconstruction verifies exact source, candidate, diagnostics and the prior
native subset using isolated Python. It does not rerun engines or clients.
Checkpoint IDs are recorded in the Git proof files and the main plan.

Next: authenticate a real confined client into this selector and private
staging, with wrong-token/PID/fence, response loss, lookup and Stop/Cancel proof
on one frozen closure. S38 is an inert in-memory fixture, with trusted clock/
revision observations; it does not prove external source scanning, physical
power-loss durability, witness custody or Godot/Blender adoption. General
safe_write/atomic_replace stay unsupported; GT-03–GT-10 remain gated.
