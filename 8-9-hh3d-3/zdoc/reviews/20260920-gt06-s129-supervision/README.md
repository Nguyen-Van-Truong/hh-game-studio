# S129 passive launcher supervision

AUTHORITY=0; no benchmark acceptance. The observer owns only its exact child
Popen handle. It uses process creation time, image checked while live, argv and
source hashes, then waits on that retained handle and reads actual exit via
GetExitCodeProcess. It never creates a Job, kills a workload, retries or restarts.
Native CloseHandle BOOL is captured; timeout closes observer ownership without
inventing an exit. Observer loss, missing receipts and power loss remain UNKNOWN.

The frozen core validation attempt04 completed exit0 in 3.469s. It covered actual
controller exits 0 and 7, injected owned-controller termination47, a timeout with
actual exit null while the controller remained live, and four pin rejections.
The harness separately cleaned its owned controller/leaf with retained handles;
these artificial interventions are not evidence of any historical engine cause.
Earlier failed/provisional attempts remain in this packet. The first probe
revealed that QueryFullProcessImageName may fail after exit; image is now checked
while live and creation FILETIME binds the signaled retained handle afterward.

Coordinator additionally registered and dispatched the prepared demand-only
`gt06-s129-scheduler-probe-04` after the core tests. Launcher45340 actual exit0,
checked native handle close, terminal EXIT_OBSERVED and scheduler state3/result0
were recorded. This proves this short non-engine scheduled path; it does not
promise survival of app/machine loss or infer descendant cleanup from scheduler0.
The task was retired after its definition and terminal metadata were retained.

For an engine diagnostic, prepare a fresh request with make_request using the
frozen integration launcher, argv --launch, HH3D cwd, source_files absolute pins,
observation_seconds7770 and scheduler_seconds7800. Use prepare_task.ps1 with
-Command prepare, then register, then start and the same RunId. Every dispatch
is one-use, fixed same-user/normal-priority/demand-only, no retries. status reads
only COM and the small retained XML; it performs no source audit during a run.
Always query actual PID/start/executable and short raw progress as well.
