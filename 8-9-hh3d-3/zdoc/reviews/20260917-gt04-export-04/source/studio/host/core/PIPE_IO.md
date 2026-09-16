# Owned overlapped pipe I/O — internal GT-02 subset

`pipe_io.OwnedPipe` implements bounded binary frames for a trusted broker's
Windows named pipe. It does not create an endpoint, authenticate a worker,
grant a capability, dispatch a command, or publish a staged file. The existing
public safe-write/replace capability remains unsupported. Successful native
I/O is not an application `COMMITTED` receipt.

The trusted endpoint factory must create a non-inheritable, byte-mode,
`FILE_FLAG_OVERLAPPED` pipe with local-only policy and a checked ACL, then
transfer its sole handle ownership with `_adopt`. No other component may use,
close, duplicate or inherit that handle. Refused adoption leaves ownership
with the caller; successful adoption transfers it to the process-wide registry.
Raw handles, API implementations and limits are never request fields.

Each frame has a four-byte little-endian size, followed by 1–262144 bytes.
The same monotonic deadline covers header and body, including fragmented
reads; accepted timeout is 1–30000 ms. A short write, invalid size, timeout,
disconnect or failed native query poisons the channel. Writes are not retried.
`delivery_unknown` only describes byte-delivery uncertainty; the RPC layer
must preserve the original command ID and use durable lookup/reconciliation.
It must not translate a pipe error into an application no-effect rejection.

There are at most 32 owned pipes and one active operation per pipe. The
operation retains the buffer, OVERLAPPED, count storage and event. Even if a
caller drops every reference after an exception, the bounded registry keeps
them and the pipe alive. Future endpoint admission must reserve control slots
before opening work connections; the global cap alone is not that policy.

`request_stop()` sets a thread-safe flag without acquiring the I/O mutex.
The owner checks it between native operations and at waits of at most 20 ms.
Stop or timeout calls `CancelIoEx` on the exact OVERLAPPED, then observes
completion for a separately bounded 1–1000 ms grace (default 250 ms). Neither
success nor `ERROR_NOT_FOUND` from cancellation proves completion. An invalid
completion query cannot free storage either.

If completion remains unverified, `PIPE_DRAIN_PENDING` returns with a local
`cleanup_owner`; `pending_cleanup()` exposes retained owners to the trusted
supervisor. Calling `close()` later continues cancellation/readback on the
same operation. It never starts a replacement read/write. Native completion
must be observed before event close, and checked event close must precede pipe
close. A native close failure retains ownership for another cleanup attempt.
Closing from another thread requests Stop and returns `PIPE_BUSY` while the
I/O owner is active. There is no unsafe finalizer or unlimited background wait.
If a driver never completes, the owning broker process must be drained or
terminated by its supervisor; retaining bounded resources is intentional.

`python -B studio/tests/protocol/test_pipe_io.py` uses real owned Windows pipes.
It tests fragmented/maximum frames, EOF, shared deadlines, pending connect/read/
write, concurrent Stop/close, short native writes, lost caller references,
missing cancellation completion, failed wait/result/event/handle close and
resumed cleanup. Failure injections never invent a completion while Windows
still owns a buffer. These tests do not prove AppContainer identity, token
delivery, reserved control capacity, persistent effects or another OS.

Next integration: bind two endpoint roles to the retained worker identity and
session, pass the existing typed envelope through auth/lease/journal admission,
and keep Stop/lookup available when the work channel fails. Private staging
still needs the expected-generation selector and explicit crash reconciliation.

Primary API contracts checked 2026-09-16:
[CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex),
[GetOverlappedResult](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresult),
[cancellation considerations](https://learn.microsoft.com/en-us/windows/win32/fileio/canceling-pending-i-o-operations).
