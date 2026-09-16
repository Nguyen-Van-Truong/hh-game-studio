# GT-02 S43 candidate: create-only native experiment

Source closure: `6b7707a126449d46aac937504113e8c7e6fb9aa5db4f73948b7e65df0e0ce7fc`.
Source commit: `08f70cf`. Candidate: `GT02-S43-20260916-01`.
This is not GT-02 acceptance and does not enable a public mutation capability.

The new `safe_create.py` supports one smaller operation: publishing a fresh
file without replacing an existing name. It holds ancestors, writes through
a delete-pending stage handle, checks pending/link metadata before writing,
flushes and reads back, clears pending only once bytes are final, renames from
the same handle with replacement disabled, checks the final path/identity and
bytes, then flushes the parent. Late failures poison the object and report an
unknown outcome; it does not blindly retry or remove a pathname after close.

The final parent must share WRITE for the kernel's rename destination open.
It still does not share DELETE. This corrects S42's overly broad conclusion
that retaining an ancestor chain prevents publication. Allowing parent WRITE
also allows a competing child entry: a fresh-name collision is rejected, but
this does **not** prove an identity-conditional replacement operation.

Evidence:

- Full owned snapshot run: 294 protocol tests, 290 passed and 4 explicit
  platform skips; bootstrap 56/56. Host/wrapper exits and owned trees clean.
- 11 new Windows tests: actual create/readback, collision, path rejection,
  pre-pending and during-write hardlinks, missing rename postcondition,
  failed parent flush after publication, root swap and exact Unicode names.
- Native AppContainer selector regression reminted as `GT02-S43-NATIVE-01`:
  seven cases with exit 61, Job/PID zero, exact 86-file candidate closure.
  This native client tests selector IPC, **not** the new create-only module.
- The older focused RPC run is reused only after checking the two relevant
  source files are byte-identical. Four verifier negative cases reject stale
  native closure, changed file hash, missing file map and missing digest.

Reproduce from the repository root:

```text
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s43-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s43-audit/test_native_binding.py
```

Outstanding: independent adversarial review, native pre-opened-handle tests
in the candidate suite, constructor/close-ownership failure coverage, process
crash and recovery custody, power-loss durability, transport integration and
replacement target CAS. `safe_open.capabilities()` remains unchanged/false.
S41 FAIL reviews belong to the old closure and are not signatures for S43.

API references: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information),
[FILE_LINK_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_link_information).
Observed behavior here is limited to this Windows/NTFS host; these references
do not replace its native test evidence.
