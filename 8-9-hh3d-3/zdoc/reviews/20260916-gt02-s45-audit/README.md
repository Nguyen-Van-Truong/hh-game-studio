# S45 coordinator checkpoint

Candidate `../20260916-gt02-s45-02`, closure
`26a225b45f8283796448512987595fd962cad204e6c57164c3929ee7a067c243`:
97 source files, 9 artifacts, protocol 375 run / 371 pass / 4 documented skips,
bootstrap 56/56. Actual suite exits are zero and owned process trees are clean.
Python/Node/Godot agree on 2396 serializer rows. This is **not GT-02 acceptance**.

New behavior:

- Read-only/poisoned consumer admission is checked before INTENT, after duplicate
  lookup. The S44 reviewer defect no longer strands fresh work after restart.
- A protected, nonvolatile Registry record owns bounded typed root/stream
  bindings and the event high-water witness. Event append cannot return until
  custody is stored, flushed and read back; uncertain persistence holds retries.
- The managed owner opens existing roots from that record, checks the exact
  chain/file/barriers, renews the recorded logical owner with a fresh lease ID
  and fence, then rearms only a complete terminal fixed-file snapshot. Pending
  commands/Stop/unknown namespace remain held; no prior effect is replayed.
- An actual child exits 87 after committing a second revision. A fresh process
  recovers using only storage ID and protected registry state, not test stdout
  as a witness. A separate event test exits 91 between event durability and
  custody; mismatched binding is refused. Registry tests include exit81 cuts.
- Constructor errors retain actual unclosed token ownership through the event
  wrapper; only successful native cleanup releases the owner slot.

Native registry package `../20260916-gt02-s45-registry-native/run-02/` matches
the exact complete candidate closure. It records 45 denied attempts, a real
package-granted positive control, 12 broker updates, unchanged protected final
State/Format, actual child exit89, native Job/PID0 and clean outer tree. Two
owned test leaves/profile/temp/snapshot were removed. This is Registry boundary
proof; it is not evidence of a public managed-selector IPC endpoint. S44's
file-consumer IPC/replace packages retain their original closure and scope.

## Requirement map

| Requirement | Evidence | Remaining limitation |
| --- | --- | --- |
| TQ02 / TX01 schema, JCS, bounded errors | candidate protocol/golden logs, 2396 rows per consumer | Serializer only; engine raw wire admission is separate |
| TX11 persistent dedupe/UNKNOWN | generic journal/transport suites; managed fixture and bound event custody tests | Ambiguous pending effects stay held, not silently resumed |
| §2.2 / TX15 no-effect invalid admission | added file-consumer/safe-replace tests | Public scoped capability/dispatch still absent |
| TX14 Stop and lease fencing | file-consumer/selector/transport plus managed restart before old TTL expiry | Stop is preserved; no old authenticated session restored |
| Durable restart bindings | managed fixture 12 tests, registry21 and private-events27 in full candidate | Blocking disk/hive flush requires owned process deadline; not physical power-loss certification |
| Confined-worker storage boundary | native registry run-02, 45/45 denied, positive control | Unrestricted broker account/admin is trusted per existing model |
| Ownership and cleanup | actual unclosed native token/key tests; owned Job captures | No broad process/filesystem cleanup |
| Two independent same-source PASS reviews | **OPEN** | S44 critics FAIL are historical; implementation workers are not S45 acceptance signatures |

Reproduction from repository root at this checkpoint:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s45-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s45-audit/test_native_binding.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s45-audit/verify_git_bytes.py HEAD
```

The verifier recomputes all source/artifact/native bindings and checks actual
completion/exit/tree records; four negative native-binding variants must fail.
The diagnostic manifest retains failed/superseded runs without treating them
as PASS. Git verification reconstructs source and evidence bytes from the index
or commit. After later source edits, use this checkpoint's checkout to rerun it.

## Retained failures and lessons

- S45-01 has one failed transport test: its 40 ms lease could expire before
  socket submission, and the test ignored the rejected submit result. The
  repaired test gates the real executor, requires ACCEPTED_PENDING, then advances
  only the test clock to the expiry boundary. Five focused repetitions and the
  full S45-02 suite pass. Production lease validation was not weakened.
- Event custody run-01 attempted path read while the native share0 handle was
  still open. Correct test ownership closes it before comparing raw bytes.
  Run-03 reproduces the real constructor token leak; run-04 verifies the fix.
- Source docs, tests and implementation all belong to the closure. Native
  registry run-01 matches the older failed candidate closure; run-02 was reminted
  after the test fix. No stale hash/signature is transferred.
- The product-owned registry base is retained configuration. Current runs verify
  its protected owner ACL and report no new base components. The earliest
  creation return was not retained, so no per-component creation provenance is
  invented. Disposable test UUID leaves are separately tracked and removed.

Next: scoped discovery/client/dispatch and owned endpoint lifecycle for the
managed fixed-file operation, new native end-to-end proof, then two independent
reviews on that final closure. GT-03 through GT-10 remain gated by GT-02.
