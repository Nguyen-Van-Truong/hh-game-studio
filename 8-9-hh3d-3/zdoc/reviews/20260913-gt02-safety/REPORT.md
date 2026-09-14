# GT-02 safety baseline (worker report)

Status: **CANDIDATE** (worker evidence; coordinator/critics must decide acceptance).

Implemented a side-effect-free safety policy in `studio/host/core/limits.py`:

- strict UTF-8 JSON parsing with duplicate-key, invalid Unicode, NaN/Infinity and unsafe integer rejection;
- deterministic UTF-8 RFC 8785 JCS canonical payload encoding (without Unicode normalization) and a digest bound to the typed request;
- envelope validation for required fields, bounded strings, deadline horizon and payload hash;
- conservative immutable `LimitsProfile` resource caps;
- lexical root/path checks for traversal, absolute/UNC/device/ADS paths, reparse/symlink components and hardlinks; mutation path resolution fails closed when an OS safe-open primitive is unavailable.

Tests in `studio/tests/protocol/test_limits.py` cover valid requests, hash binding, duplicate/invalid wire data, deadlines, safe integer bounds, Unicode normalization distinction, traversal, UNC/device/ADS and symlink rejection. Symlink cases are skipped when the host denies symlink creation.

## Verification

```text
python -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -p 'test_*.py' -v
Ran 35 tests in 0.07s; OK (skipped=3)
python -m py_compile 8-9-hh3d-3/studio/host/core/limits.py 8-9-hh3d-3/studio/host/core/journal.py
```

The suite includes protocol, journal, integration and hostile-input vectors.

## Deliberate limits / follow-up

This module does not claim a Windows `CreateFileW` no-reparse handle implementation, durable journal, lease store, token/session server, network policy or production quota fairness. It returns `UNSUPPORTED_SAFE_OPEN_WINDOWS`/`UNSUPPORTED_SAFE_OPEN_LINUX` for writes unless a reviewed primitive is explicitly supplied. Durable journal/recovery and adapter integration remain GT-02/GT-07 work and must add independent crash/full-disk/retry evidence before acceptance.

## Journal extension (2026-09-13)

`studio/host/core/journal.py` adds a stdlib-only durable newline journal. Records carry a SHA-256 checksum and are flushed with `fsync` before a receipt is returned. Startup rejects an incomplete final line, malformed record, or checksum mismatch. The command key is `(project_id, command_id)`; a retry with the same `sha256:<64-hex>` digest returns the original receipt, while a different digest is rejected. Terminal records remain as `EXPIRED_TOMBSTONE` during compaction so an old ID cannot be replayed after the retry horizon. Pending-command and journal-byte/record limits are enforced before append. Lease acquisition is FIFO-independent local fencing by monotonically increasing epoch, with expiry, busy-owner and stale-lease checks; expected revisions are compared before apply. Compaction uses fsync plus atomic `os.replace`.

Journal tests cover response-loss/reopen, conflict, pending/full limits, retry horizon, digest/status validation, truncated/tampered records, compaction tombstones, lease fencing/expiry and revision mismatch. Combined protocol suite result after this extension: **20 tests passed, 2 symlink tests skipped because this Windows host denies symlink creation**.

Known follow-up: this is a local single-process fixture journal. Inter-process file locking/CAS, remote durable storage, token/session auth, and production quota fairness remain later adapter/recovery work; consumers must not present this as distributed durability.
