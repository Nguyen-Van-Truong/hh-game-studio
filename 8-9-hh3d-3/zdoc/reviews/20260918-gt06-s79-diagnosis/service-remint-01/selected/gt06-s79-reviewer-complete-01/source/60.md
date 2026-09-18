# Managed fixture service

`ManagedPipeService` owns one managed broker, work/control endpoints and four
non-daemon threads. Its `ManagedFixtureOwner` remains caller-owned. The local
launcher must retain its worker process and Job, create both endpoints, bind
them to that process and connect them before constructing the service. The
constructor checks exact types, roles, package, process identity, live peer and
managed storage binding before transferring ownership. Rejected construction
leaves endpoint cleanup with the caller.

`start()` writes one `hh-selector-session-1` bootstrap frame on the verified work
pipe: project/session ID, expiry, sorted scopes and bearer. This is a private
credential channel; it never goes through argv, environment, discovery or
diagnostic logs. The worker consumes and validates the bootstrap before handing
its two connected pipe owners to `ManagedFixtureClient`. The client constructor
does not read a second bootstrap. Neither object launches arbitrary programs.

Work and control have separate readers. One pump waits on a broker admission
event published with the job before reply delivery. It advances only that
locally admitted job, rechecking authorization at every phase. It never rebuilds
jobs from durable pending history, retries an unknown effect, or clears Stop.
Clearing the event precedes checking the queue, avoiding lost wakeups. A slow or
lost ACCEPTED_PENDING response cannot prevent already-admitted work from being
observed by the pump.
A separate deadline watcher revokes admission and cancels both pipes even if
the pump is blocked inside an already admitted native storage phase. Putting
the only timer in the pump would allow session expiry to slip during that I/O.

Work read/write failure permanently holds further phases and work admission;
an already admitted synchronous phase may finish. Healthy control can still
inspect, look up, Cancel and Stop. Failure of control or the finite overall
session deadline holds work, revokes every rotation of the bound session ID and
requests cancellation on both pipes. Cancellation does not imply completion.
An idle pipe read timeout is terminal for that lane, not an empty poll that may
be retried on its poisoned handle. Configure the broker's finite request timeout
for the intended idle interval (e.g. ten seconds for the native fixture).

`close()` holds admission, requests cancellation, then joins all threads under
one absolute drain deadline. Any live thread leaves the complete resource chain
owned by this object; the exception carries `cleanup_owner`. Once all threads
exit, endpoint cleanup uses the existing bounded native cancellation primitive.
Each next cleanup checks the same deadline; a native call itself is not a hard
real-time operation. The enclosing owned Job deadline remains mandatory for a
driver or storage call that cannot return. No Python thread is killed.

Only after both endpoints close does service close the broker and release its
owner binding. A failed native close or broker close retains that binding for
explicit retry. Managed owner close refuses while a broker/service is attached,
so a failed drain cannot close storage beneath a live thread. Service close is
not an application Stop receipt; durable pending work remains for reconciliation.

`test_managed_service.py` uses real registry/storage and real threads with
substituted endpoint peer/frame operations. It covers wake before blocked reply,
separate control after work failure, rotated-session invalidation, startup
failure, finite session timeout, retained handles and close retry. It is not OS
sandbox evidence; the native AppContainer run must bind the same frozen closure.

References consulted on 2026-09-16:

- [Python threading](https://docs.python.org/3/library/threading.html): timed
  join needs a subsequent liveness check; threads cannot be forcibly stopped.
- [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex):
  cancellation requests must be followed by completion before reusing I/O state.
