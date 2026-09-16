# GT-02 S42 — bounded Windows primitive probe

- `RUN_ID=GT02-S42-20260916-SAFE-WRITE-PROBE`
- `DECISION=GAP_REMAINS`
- `FORMAL_ACCEPTANCE=0`

This is a disposable native probe, not a capability change or candidate
closure. It tested a possible way to remove the S40 hardlink counterexample:
mark a newly-created staging file delete-pending before `WriteFile`, flush and
read back through the retained handle, clear delete-pending, then publish by
`SetFileInformationByHandle(FileRenameInformation)`.

Observed in a unique TEMP root:

```json
{"open":true,"mark":true,"link":"blocked","link_err":5,"write":true,"write_n":3,"clear":true,"postclear_link":"allowed"}
```

The delete-pending state does block a new hardlink while mutable bytes are
being written; after clearing it, a later hardlink is possible, which is safe
only if the source handle is never written again. A separate full-path rename
probe succeeds with a reduced handle set, but the production-safe wrapper holds
the complete ancestor chain. With that chain retained, the handle-relative and
full-path rename attempts return `ERROR_SHARING_VIOLATION (32)` on this host.
The direct success therefore cannot be promoted to an atomic replace proof: it
would require weakening ancestor custody or using a different native primitive.
Directory `FlushFileBuffers` is available only through a separate
write-capable directory handle; that handle itself needs an identity/share
proof and has not been integrated.

No source capability was enabled, no user/project file was touched, and all
probe handles/TEMP roots were cleaned. `safe_write=false` and
`atomic_replace=false` remain correct. The next implementation must either
prove a protected namespace with an identity-conditional publish operation or
keep returning `UNSUPPORTED_SAFE_OPEN_WINDOWS`; an extra stat/link-count check
is insufficient.
