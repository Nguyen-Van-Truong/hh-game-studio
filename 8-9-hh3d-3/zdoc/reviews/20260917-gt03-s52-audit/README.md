# S52 integration evidence — candidate audit

AUTHORITY=0. This package checks historical source, process and observation
consistency. It does not accept GT03, create independent critic signatures,
launch an engine/container, reopen Registry custody or mutate protected files.

Final lanes are the full Python/editor capture `20260917-gt03-s52-editor-02`,
authenticated save `20260917-gt03-s52-publication-05`, real Stop during
native validation `20260917-gt03-s52-stop-01`, and the focused unit repair
`20260917-gt03-s52-unit-repair-02`. The original full suite remains **504 passed
of 522, 18 failures, exit 1, capture.passed=false**. Only two historical-fixture
provenance tests changed; their two modules then passed **30/30**. The checker
matches every raw test ID: the combined evidence covers 522 distinct tests,
including all 18 original failures. This is not one clean full-suite rerun.
Actual editor lanes passed 103 edit, 10 reopen and 31 contract checks.

Run the small evidence-corruption regression once after checker changes, then
verify the combined historical evidence without starting engines:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-audit/test_negative.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-audit/verify_integration.py --editor 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-editor-02 --happy 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-publication-05 --stop 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-stop-01 --repair 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s52-unit-repair-02 --expected-tests 522
```

After staging, append `--git-ref index`; after committing, use `--git-ref HEAD`.
These options recheck evidence without rewriting its timestamp/manifest, then
compare every portable artifact and all 145 current source files directly with
Git blob bytes. Their proof output is separate and does not hash itself.

The checker verifies every file of each complete frozen source closure and
retains each closure ID separately. It compares exact runtime maps across
lanes, excluding `tests/` and Markdown documentation only from this cross-lane
comparison. Those excluded source files remain included and hashed in each
full producer snapshot. Current runtime must also match; all current source
files must match the repaired snapshot. Stop01 and happy05
have 145 source files each; their only full-manifest difference is
`tests/godot/run_editor_probe.py`, whose watchdog budget changed from 720 to
600 seconds to meet the accepted runner limit. No old log is relabeled with a
new closure. The repair closure differs from editor02 only in
`tests/godot/test_profile_probe_evidence.py` and `tests/godot/test_profile_readback.py`.
Both repaired modules retain the historical fixture's exact original source
hashes and are pure replay tests, not new native executions of old data.
The source inventories stay strict: extra generated caches inside a frozen
source tree are rejected, not silently ignored.

Happy05 has 16 checks. The auditor verifies the actual outer process/streams,
native editor PID/exit/checked Job close, same-session capture and adoption,
all 11 editor input bytes, full semantic hashes, actual two Linux validations,
exact Docker CLI/inspect/wait/removal records, native scene bytes, selected
descriptor/selector hashes, public response and durable receipt binding,
duplicate/lookup/Stop response artifacts, and public state-event replay against
the journal and readonly reopen snapshots. Validation receipts are recalculated
from raw observation, source, input and evidence hashes. Event observations
must match the separately captured editor records.

Stop01 has 19 checks. The auditor verifies a separate raw Docker inspect showed
the exact owned validator running before the HTTP Stop, and requires the whole
Stop call, including its response, to precede that same container's actual exit.
The save becomes UNKNOWN;
public state replay contains only CONFIG, CAPTURE_PREPARED, CAPTURED, UNKNOWN;
the editor root/revision remains dirty and unadopted; the historical readonly
reopen retains its original selector. Stop latency is retained as measured,
including a possible zero at the capture clock's resolution.

`portable-artifacts.json` lists the minimum checked proof files plus complete
frozen source snapshots, with SHA256 for every entry. It excludes `.godot`,
Python/Blender caches, user configuration and the entire `owned/storage` tree
(raw Registry/private events/protected object storage). It includes editor
hello/effect/process records and working project bytes; Linux input manifests,
all flat CLI logs/host records, readonly snapshots and fixed harness are kept.
Historical failed packages are preserved separately and are not prerequisites
for this candidate verification. The pinned S49 raw host/Linux checker is an
explicit hashed dependency, not an old acceptance signature.

The portable observations are historical host evidence. They are not a new
live FileID/Registry durability test, proof against malicious fabrication of
all source and evidence, or a byte-for-byte relocation of the original Windows
and Docker filesystem context. Current verification uses the pinned local
Linux binary and original captured mount paths. The absence of extra stage
names in Stop01 and rejection of the foreign bearer in happy05 are identified
as producer assertions because those probes did not save separate raw responses
for those particular assertions. Gate acceptance still needs the remaining
GT03 requirements and two independent reviews on an agreed frozen closure.

Four focused corruption tests reject a changed runtime map, forged completed
response or editor event, Stop completion after the actual native exit, and
boolean host exit or an unclean process tree. They modify parsed copies only;
the saved evidence is untouched and the report is bound to checker/test hashes.

Preserved diagnostics: happy03 succeeded on its own frozen source but origin
changed during execution; happy04 collided with the global single-validator
admission lease; editor01 failed before tests because a 720-second timeout
exceeded the accepted runner's 600-second cap. Repair01 generated one `.pyc`
inside its source snapshot, so repair02 repeats only the 30 fast pure tests with
bytecode generation disabled. None is substituted for a final lane or treated
as a runtime acceptance failure.
