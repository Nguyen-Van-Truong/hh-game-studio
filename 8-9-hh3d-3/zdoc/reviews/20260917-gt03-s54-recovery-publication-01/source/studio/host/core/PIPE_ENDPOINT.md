# Bound fixture IPC — internal GT-02 Windows subset

The broker creates one `AppContainerEndpoint` for each `work`/`control` role
before launching its worker. The pair must be reserved together, so work
traffic cannot consume a control endpoint. The current internal global bound
is 16 endpoints (up to eight pairs); public discovery does not create them.
The launcher must use its owned Job, suspended creation, no handle inheritance,
AppContainer profile with zero capabilities and restricted child creation.
This module validates the resulting primary process token; it does not launch
the process or claim to verify every sandbox/Job policy by itself.

The pipe is local-only, first-instance, single-client, byte-mode and overlapped.
Its address uses the package SID namespace observed in the S33 native probe.
The protected DACL grants the broker full access, OWNER RIGHTS only READ_CONTROL,
and the package the individual mask 0x12019b. That mask excludes pipe-instance
creation, WRITE_DAC and WRITE_OWNER. A Low integrity label permits the intended
worker's data I/O. Owner/DACL/label are read back from the retained server handle
and compared exactly before operations. Windows reported SACL control bit `AI`
for this created object; the descriptor now authors that bit explicitly. It
does not drop label checking or ignore other security-descriptor differences.

`bind_worker` duplicates the trusted launcher's retained process handle with
QUERY_LIMITED_INFORMATION and SYNCHRONIZE only, non-inheritable. Before
accepting a connection and before/after a frame read it checks process liveness,
PID/creation time, primary token type, AppContainer SID, broker user/session,
Low integrity and zero capabilities. `GetNamedPipeClientProcessId` must match
that retained process. No PID lookup/open from an untrusted request is used.
The broker never impersonates the client. Another token, PID or role provided
inside a frame cannot change this local binding.

Endpoint owners are retained until I/O and auxiliary handle cleanup finish.
Constructor/close failures preserve any tracked pipe/process/token handles;
`pending_endpoint_cleanup()` lets the local supervisor continue cleanup.
`pipe_io` owns the pipe after transfer and retains pending native I/O memory.
One shared process handle is never closed through two owners. The shared
`_StoreApi` initialization helpers remain part of the broader review scope;
the tests do not claim every possible Win32 token/allocator failure is covered.

`FixturePipeServer` uses the existing fixed counter operation catalog, not a
new file writer or evaluator. Each binary frame contains an ASCII Bearer line,
an ASCII route line and the canonical request JSON bytes. Header bounds and
session authentication precede JSON parsing. The authenticated session must
match the locally bound session; expiry/revocation/rotation are checked again
at dispatch and apply through the shared host. Trusted relaunch/rebinding is
required to use a new session; it cannot be requested over the pipe.

Both endpoint roles use the same journal, queue, lease/fencing/revision and
Stop/Cancel handlers as HTTP. PENDING still follows durable admission;
COMMITTED still follows fixture readback and durable terminal persistence.
Transport loss propagates to the supervisor; it does not erase pending state,
reapply the effect or manufacture a no-effect rejection. HTTP and pipe share
the journal error-to-UNKNOWN mapping. All replies use the existing session
redactor; endpoint addresses, process handles and credentials are not discovery
or diagnostic fields.

The endpoint unit tests cover real descriptor readback/change, ordinary/dead
process rejection, cleanup ownership and bounded SID decoding. RPC unit tests
explicitly substitute frame I/O to isolate parser/dispatcher behavior; they
are not OS authentication proof. A separate fixed native AppContainer fixture
must exercise the unpatched modules, verify replies and actual host exit/Job
drain, and bind the full source closure before any integration claim.

Limitations: the state is still the in-process counter fixture. This does not
activate private staging, provide durable engine state, implement an immutable
release selector, accept open-lane execution or prove Godot/Blender isolation.
The current safe-write/replace capability remains false. Windows builds other
than the tested host and Linux require their own explicit evidence. Candidate
tests and a coordinator audit do not replace two independent frozen reviews.

Primary sources checked 2026-09-16:
[pipe client PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid),
[process times](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes),
[token information](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation),
[handle duplication](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle),
[descriptor control flags](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-string-format).
