# Authenticated read-only client slice

Candidate only. The external facade uses immutable GT02 Discovery, Capability,
Request and Response classes, with `scene.inspect` as its sole native operation.
Mutation and open execution lanes return explicit unsupported responses. No
writer lease, private receipt import, publication, restart adoption or durable
recovery is implemented. Command, lookup and Stop `Response` postconditions
declare `durable=false`, `read_only=true` and `public_ack=false`. Discovery uses
the common `Discovery` schema and advertises no write capability; the lease
envelope declares read access, `durable=false` and `public_ack=false`.

Trusted local bootstrap calls `BlenderClientOwner.from_host(exact_host,
project_id=...)` once for an exact live BlenderUIHost. It pins the host object,
process/Job owners, actual PID, generation, complete source map and owned GUI
deadline. It queries the live Job and takes one bounded baseline scene inspect.
It neither opens a `.blend` nor launches another engine. Failed registration
leaves native ownership with the caller. Transport close likewise never closes
the caller's native owner.

`owner.sessions.issue()` mints an immutable core SessionCredential with empty
fixture scopes. Separately registered Blender grants authorize read, lookup and
Stop. Copies or changes to a grant/read-lease object do not grant authority.
Rotation revokes old bearer/grant/read leases; same-session lookup keeps the
facade's existing volatile observations. A new session cannot read another
session's results. All issued bearer values remain in bounded redaction history.

Owner/transport interface:

| Method | Exact body | Return |
| --- | --- | --- |
| `discover` | `project_id` | Common Discovery with read capability and catalog digest |
| `lease` | `project_id`, `ttl_ms`, `access: read` | Registered read lease ID, fence0, expiry, fixed target and baseline revision |
| `submit` | Common Request | Common Response |
| `lookup` | `project_id`, `command_id` | Only this session's facade response |
| `stop` | `project_id`, `command_id` | Native Stop observation or UNKNOWN |

All methods accept keyword arguments `authorization` (raw Bearer header) and
`catalog_digest` (the exact `owner.catalog_digest`). The companion transport
uses `sessions.authenticate`, `authorize`, `validate_public_identifier`,
`encode_output` and `redact_output`; HTTP framing and auth primitives remain in
the unchanged GT02 core. Discovery is not an authority grant. Tokens, a generic
fixture scope, paths and saved PIDs cannot register the native owner.

The Request target is exactly `{"stable_id":"blender.owned-scene"}`, payload is
empty and expected_revision matches the registration observation. Request
payload/digest, schema, project, catalog, read grant, registered lease and
absolute deadline are checked before native admission. Read leases cannot
outlive the GUI deadline. A newly admitted read has at most 2 seconds of result
validity; the native queue gets the remaining TTL. Native IPC and cleanup have
their own bounded waits, so this is not a universal wall-clock response or Stop
latency guarantee. Source/PID/generation/Job, revision, session authorization,
lease and deadlines are checked again before the response is recorded.

The native revision string is preserved verbatim. Blender's native JSON float
encoding is not reconstructed from JCS. `result_hash` names exactly the JCS
bytes of `postconditions.observation`, with `hash_domain=jcs-observation-v1`.
The observation contains the native revision, normalized IPC scene, exact PID,
generation and producer source digest. It is a live read observation, not a
hash of `.blend` bytes or an assertion of durable scene state.
Before publication, the common redactor must preserve the exact response bytes;
path-shaped names or registered secrets produce `BLENDER_SENSITIVE_OBSERVATION`
without an observation. The actual output boundary repeats this check. If later
credential history makes a stored observation sensitive, transmission is denied
instead of rewriting its bytes under the original result hash. Stored history
is never rewritten or rehashed to hide that denial.

At most 32 command records exist in an owner. `(session_id,command_id)` scopes
lookup; the common Request digest binds operation/target/payload/schema.
Duplicates return detached copies of the exact cached canonical response;
changed digests conflict. In-flight duplicates return the cached pending row.
One native read runs at a time; excess work is rejected. Records are never
evicted to allow re-execution, imported from private journals, or resurrected
after process restart. Lookup of a known record does not launch an engine or
require a fresh read lease. Lookup remains available after Stop while the
client session is valid.

Session and owner locks do not span native waiting. Stop marks read admission
closed, takes the native control path and reports any active read as draining.
The HTTP Stop listener has independent connection capacity; native result polls
and Stop still share the native control channel. Measured Stop latency belongs
to its specific evidence workload, not all possible channel/OS contention.
Already-built response bytes publish under the session authorization lock,
so Stop or revocation cannot overtake successful new read publication. If they
win first, the new observation is withheld. Previously published volatile
results remain historical observations, subject to lookup authorization.
An ambiguous native read holds further native admission until owner cleanup;
unexpected final checks and Stop failures produce bounded UNKNOWN responses.
Existing native owners, producer runtime and common core
are unchanged. A later writable extension requires its own reviewed catalog,
grant and durable public-response binding; this read facade is not that grant.

Pure tests use an explicitly inert native double. They test envelope and scope
rejection, registered authority, exact volatile retry/lookup, deadline and source
drift, response-copy isolation, and concurrent Stop/revoke during read. Socket
tests exercise the companion transport separately. Actual external-client to
Blender readback still requires a frozen owned native run and independent
same-source review; unit or socket tests alone do not supply that proof.
