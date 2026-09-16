# GT04 private writer FIFO03 review package

AUTHORITY=0. Candidate only; public_ack=false; no formal GT04 acceptance.

Frozen source: `7eab49db44887486919d4d827a36f597260ca99e02797c293827a03fb37e58d1`.
FIFO is a current TX06 requirement for GT04. This slice adds durable admission
order, eight waiting tickets, expiry/cancel, fenced handoff and priority Stop
on the unchanged core Journal and existing owned Blender GUI transport.

The captured run passed 119 Python tests and 19 actual native checks. Two
independent client processes both wait before either receives its turn, then
each creates one box through the authenticated native queue. Their actual PIDs,
exit 0 records, requests, results and durable ticket/lease/response records are
bound by the verifier. The grant order is Alice then Bob; their native fencing
epochs are 2 then 3. Old Alice authority is rejected before durable intent and
by the authenticated native consumer, followed by an unchanged scene readback.
Stop cancels all eight waiting tickets and blocks another session's grant;
no scene/lease admission follows its durable marker. The last scene readback
is before Stop; the fixture does not claim a fresh post-Stop scene readback.
Actual GUI, native harness and wrapper exits are 0 with checked native Job zero.

Successful work uses normal 10-second leases and 30-second queue deadlines.
The journal proves each handoff followed the predecessor's actual expiration.
The short queue-expiry case is separate from successful native work.
Unit tests cover full-capacity progress, competing admissions, lost grant reply,
cancel during grant, exact retries, Stop without the scene lock and stale fences.

The clients are synthetic fixtures using bounded JSON over inherited stdio to
a trusted broker. They exercise production scheduler methods and existing
native IPC; this does not establish public authentication or GT09 conformance.
This slice is one owned GUI generation. No active-lease early release or
protected custody is exposed, and journal receipts do not recover scene state
across a different Blender generation. Material02, durable01 and cleanup01
remain separate frozen evidence; their native lanes were not rerun or relabeled.

FIFO01 is preserved as a failed diagnostic: its 300ms successful-work lease
expired during real journal/native costs. FIFO02 passed with a 1500ms lease but
was superseded by FIFO03's normal budget. No failed package is promoted.
The actual completion marker is 19 checks; an earlier progress message saying
20 was a counting error and is superseded by the parsed raw record.

From the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-fifo-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-fifo-audit/test_evidence.py -v
```

Default verification reads only the frozen package and creates no engine or
journal lock. `--check-live` additionally compares current source to the freeze.
`--write-derived` writes only this audit's `verification.json` and
`portable-artifacts.json`; the default does not rewrite them. The portable
inventory contains the full frozen source and required raw logs/records,
excluding caches, private user directories and temporary launcher files.
Inventory hashes are review evidence, not a cryptographic signature or a claim
of protection from same-user disk tampering.

Focused native reproduction (new output directory required; ~30 seconds):

```powershell
python -B 8-9-hh3d-3/studio/tests/blender/run_writer_fifo_probe.py --output 8-9-hh3d-3/zdoc/reviews/NEW-GT04-FIFO-RUN
```
