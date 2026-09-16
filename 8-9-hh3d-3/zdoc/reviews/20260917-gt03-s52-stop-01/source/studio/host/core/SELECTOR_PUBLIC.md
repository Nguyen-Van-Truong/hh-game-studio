# Managed active-release scope

`SelectorFixtureBroker.from_managed(owner)` registers only an exact live
`ManagedFixtureOwner`, under its lifecycle lock. It verifies native roots,
registry custody, event high-water and all selector/consumer ownership links.
Dispatch and the mutation pump recheck these bindings. Direct
`SelectorFixtureBroker(selector)` construction remains an unregistered fixture.
The factory does not launch or authenticate a worker. The caller/service owns
the verified WORK/CONTROL endpoints, session credentials and process lifetime.

The exact descriptor is `selector_contract.SELECTOR_DESCRIPTOR`; its RFC8785
SHA-256 is exported as `SELECTOR_SCHEMA_DIGEST`. Discovery uses the existing
typed `Discovery` envelope with server `gt02-managed-selector`, build `1.0`,
protocol `1.0`, and schema `hh-studio-0.1`. Clients must verify that descriptor
digest, project and negotiated operations before mutation.

| Route | Endpoint | Exact request fields | Result |
| --- | --- | --- | --- |
| `/v1/discovery` | WORK | `project_id`, `protocol_version` | typed Discovery |
| `/v1/inspect` | CONTROL | `project_id`, `protocol_version` | bounded safe snapshot |
| `/v1/lease` | WORK | `project_id`, `ttl_ms` | existing lease ID/fence/expiry |
| `/v1/commands` | WORK | existing typed Request | existing Response |
| `/v1/lookup`, `/v1/cancel`, `/v1/stop` | CONTROL | `project_id`, `command_id` | existing receipt/control result |

Every route uses the existing SessionAuthority and bound endpoint/session;
authentication precedes body parsing. Wrong version/project/role, extra fields,
expired/revoked sessions and absent read/write scope are rejected. Discovery
does not issue a lease, append an event, advance custody or schedule a job.
Native validation may perform persistence barriers while reading metadata.

`fixture.release.inspect` exposes read scope `fixture.active-release` only to
sessions with `fixture.read`. `fixture.release.activate` exposes write scope
`fixture.active-release` only to sessions with `fixture.write` while file
mutation preflight succeeds and the selector has no Stop, broker hold, or
pending command. A read-only restart remains inspectable. A poisoned component
keeps UNKNOWN semantics. Capability availability is a current observation;
every later command still performs normal validation, lease/fence/revision
checks and consumer admission. Duplicate IDs retain their original receipts.

Activation still targets exactly `{"stable_id":"active-release"}`. Its entire
canonical payload is limited to 8192 bytes and contains only `assets`,
`entrypoint`, expected generation/selection hash and expected source/game
revisions. There are 1–16 inert assets, each with exactly `value` and
`references`; asset IDs match `[a-z][a-z0-9_-]{0,47}`. References are sorted,
unique, at most 16 per asset, and resolve inside the complete reachable graph.
JSON remains bounded by the existing depth/member/array/string limits. Asset
values are never evaluated or used as filesystem paths.

Inspection is capped at 4096 bytes and the configured response cap. It returns
exactly project/protocol/schema digest, generation, selection hash, bounded
source/game revisions, stopped/ready, pending command ID, selected and last
verified adopted selection. Each selection is null or the four logical values
generation/selection hash/release ID/manifest SHA-256; release fields may be
null for a restored empty selection. No asset/source text, blob identity,
FileID, native handle, filesystem/registry path or credential is returned.
Discovery states finite request/response/inspection/payload/lease/pending caps.

One command can be pending. A new job sets the broker wake event under its
state lock before response I/O, so lost response delivery cannot lose the pump
notification. A service retains exclusive lifecycle ownership until readers,
pump and both endpoints are drained; broker close rejects while that owner is
attached. A shutdown/work-failure hold denies new leases and admission while
receipt lookup and Stop remain available. Restart never reconstructs a pump
job for inherited pending work.

These operations publish only the fixed inert fixture through the managed
consumer and durable custody. They do not advertise arbitrary file writes,
engine operations, a public recovery switch or general `safe_open` capability;
global safe-write/atomic-replace flags remain false. Unit frame substitutions
are not native AppContainer or production-service evidence.
