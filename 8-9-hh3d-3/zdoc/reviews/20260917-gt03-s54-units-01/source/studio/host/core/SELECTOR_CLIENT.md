# Typed managed fixture client

`ManagedFixtureClient` is the local typed client for the fixed
`fixture.active-release` scope. It uses the shared `Request`, `Response`, and
`Discovery` types and imports the exact descriptor digest from
`selector_contract.py`. It opens no pipe names, paths, sockets, URLs, processes,
or engine objects. Asset values remain inert JSON.

The trusted launcher first connects and verifies the two peers and consumes
the one WORK bootstrap frame sent by `ManagedPipeService.start()`. The optional
`parse_bootstrap(raw, expected_project_id=...)` helper validates that frame's
closed schema, project, session, expiry, scopes, and bearer syntax within
4096 bytes. It does not read a pipe. The launcher then passes the resulting
`SessionCredential` and the same two connected `OwnedPipe` objects to the
constructor. The constructor never reads a bootstrap frame or accepts a
credential from an argument vector/environment. The exact types establish
local ownership contracts; they do not prove remote process identity. The
trusted launcher remains responsible for peer verification and confinement.

## Calls

The WORK channel carries `discover()`, `lease(ttl_ms=...)`, and
`activate(request)`. The CONTROL channel carries `inspect()`, `lookup(id)`,
`cancel(id)`, and `stop(id)`. Each channel has its own serial call mutex, so a
stalled work reply does not hold the control mutex. Frames use the existing
`Bearer <credential> LF route LF canonical JSON` grammar, inside the owned
pipe's length-prefixed frame. The client does not log credentials or frames.

A typical caller obtains discovery, an inspection, and a server lease, then
calls `build_activation(command_id, assets=..., entrypoint=...,
inspection=..., lease=...)`. The builder requires the advertised activation
capability with the exact write scope and a session with `fixture.write`.
It copies and validates the asset graph, fixes the target to `active-release`,
and copies generation, selection hash and all three revisions from inspection.
The payload is at most 8192 canonical bytes. The deadline is bounded by the
caller-selected 1–30000 ms horizon, lease expiry, and credential expiry.
`activate()` validates the shared envelope, project, fixed operation/target,
payload size, and deadline before sending. Server admission still verifies
lease/fencing, current revisions, authority, and postconditions; a discovery
or inspection may become stale before admission.

Inspection returns a frozen `SelectorSnapshot` with frozen revisions and
selection descriptors, without assets, paths, blob IDs or FileIDs. Discovery
and inspection must match the expected project and exact schema digest.
Reply bounds are 4096 bytes for inspection and 65536 for other routes;
`OwnedPipe` additionally enforces its 256 KiB frame allocation limit. Unknown
fields and invalid nested shapes fail closed. A terminal `Response` remains
the server's receipt; successful byte delivery alone never means COMMITTED.

## Uncertainty and lifetime

Each call shares one monotonic budget (constructor `timeout_ms`, 1–30000 ms)
across acquiring its channel mutex, writing, and reading. A busy mutex expires
before sending. A native timeout can additionally spend the owned pipe's
bounded cancellation grace (at most 1000 ms) retaining/draining its operation;
there is no unbounded join or wait in the client.

If a send, read, or reply validation fails after sending may have started, the
result is UNKNOWN with `next_action=lookup`. Metadata methods raise
`SelectorClientError` with that typed response. The affected channel is
quarantined and cannot send again through that client. The independent
control channel can still look up an ambiguous activation. If control is also
unavailable, a trusted supervisor must recover and explicitly look up the
same command identity. The client never reconnects, retries, resubmits, or
starts a background pump. A fresh connection must not be used to assume the
previous operation failed or to invent a replacement command identity.

Successful construction transfers both distinct `OwnedPipe` lifetimes to the
client; the caller must stop using or closing them. Constructor refusal
transfers nothing. A bounded registry rejects duplicate client ownership and
retains live clients. `close()` requests Stop on both pipes, attempts each
channel mutex without waiting, and only closes idle channels. Busy operations
or native cleanup failures return `CLIENT_CLOSE_PENDING` with
`cleanup_owner=client`; the same owner remains reachable from
`pending_selector_client_cleanup()`. Retry `close()` after drain. Ownership
registrations are released only after both actual native closes succeed.
Neither an exception nor garbage collection discards an unclosed handle.

## Evidence scope

`test_selector_client.py` uses real connected Windows overlapped pipes and a
real `ManagedFixtureOwner`/`SelectorFixtureBroker`, including durable custody
and active-file readback. Controlled server threads exercise discovery,
activation, lookup, cancellation, Stop, lost replies, concurrent control,
read timeout and actual handle lifetime during injected close refusal.
Malformed reply and shared-budget injections supplement those native paths.
An additional integration test creates real `AppContainerEndpoint` pipes,
connects current-user overlapped clients, substitutes only each endpoint's
peer check, and assigns the same explicit fixture identity. It consumes the
actual service bootstrap before client construction, then exercises the
`ManagedPipeService` readers and phase pump through two replacements, bounded
lookup until COMMITTED, exact-command retry, inspection and Stop. It verifies
actual file bytes, hash and changed FileID, unchanged journal/adoption count
on retry, equal custody/log heads and zero service threads after cleanup.
The lookup loop permits transient UNKNOWN but never resubmits an activation.

The suite is captured by the owned Job runner with actual child exit and
empty process-tree proof. These tests do not independently prove the trusted
launcher, peer PID binding or AppContainer policy; the coordinator's separate
native lifecycle package must cover those boundaries on the frozen closure.

This client does not enable generic `safe_open.safe_write` or
`safe_open.atomic_replace`. It does not change recovered-root policy, claim
power-loss durability, or replace the two independent critics required for
the final frozen source closure.
