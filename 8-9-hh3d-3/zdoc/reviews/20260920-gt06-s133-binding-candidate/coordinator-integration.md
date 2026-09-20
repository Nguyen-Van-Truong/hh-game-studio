# S133 current execution binding

AUTHORITY=0. Implementation validation, not GT06 acceptance or final critic.

The accepted GT05 manifest and its three consumed input assets remain pinned to
their original exact hashes. Their source map describes historical provenance.
The new installed execution binding separately pins current executable and data
dependencies. No GT05 publication verifier or gameplay binding field changed.

The fixed selector chooses an exact binding digest at a fixed local path. Neither
metadata file is inside that binding's source map. Both verified metadata hashes
are included in the returned execution map and thus in native owner source checks,
source copies and run closure. A deployment/functional freeze must pin this whole
map; the selector is not a remote request field or a permission to remint on drift.

The dependency binding has 215 files; the full execution map has 217. It preserves
the inherited 143 source paths and includes the full declared GT03 domain,
replay modules/profile/perf schema, observe scripts and fixture resources. This
also covers the dynamically loaded publication_transport.py missing from the
historical backend174 map. Lane drivers/reviewer code/outer launchers are frozen
separately by the functional runner. Missing/new dependencies and changed bytes
fail before native execution; metadata changes during verification are rejected.

Supported dispatch is a fresh owned Python interpreter for each lane. The native
runner captures the installed selection before importing its studio dependencies
and rejects later generation changes. It does not establish safe hot upgrade in
a mixed-purpose interpreter that cached other studio modules before first importing
native_runner. Do not use that unsupported launch arrangement.

Validation retained here: candidate reader17 and combined candidate33 tests;
installed execution/generation36 tests; backend20 and repair/replay20 tests.
All final invocations exit0. integration-tests-01 retains one backend fixture
failure: its synthetic sources() still omitted the perf schema formerly appended
by backend. The fixture now supplies the full verified map, retaining the original
schema assertion. integration-tests-02 passed20+20; runtime did not change for that
fixture correction. The 36 tests needed no repeat.

Independent implementation review found no blocker for fresh owned interpreters,
with the cached-module limitation above. This review is not a final critic verdict.
Native functional lanes, performance acceptance and final critics remain pending.
