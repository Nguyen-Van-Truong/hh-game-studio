# S108: one bounded save attribution attempt

AUTHORITY=0. Implementation review and diagnostic evidence only; no GT-06
acceptance, F13/F14 dataset, root-cause claim, or final critic verdict.

S107 measured a preview cost of approximately 71–95 ms per ABBA group. Its
largest original save dispatch interval was 174.147 ms, so it did not explain
the S102 2109.351 ms native heartbeat gap. The ABBA branch is closed. S106 did
not reproduce retained handle growth, so repeated PSS captures are also closed.

S108 preserves the original full workload and stock save path for at most seven
batches (0–6), with a 1200-second outer bound. Original gates run before the
diagnostic boundary. It adds the exact S103 call-return observation and samples
CPU accounting of the owned editor's native GUI thread during native batches
5 and 6. No other application is modified, stopped, or reprioritized.

The generated native startup record identifies the main window HWND. Godot's
logical thread ID is not a Windows thread ID. The host independently checks
the announced window's PID and native thread, process start time and
executable, and retained thread identity/creation time. S108-02 showed the
announced main HWND on TID 8840 and two secondary owned windows on TID 15316.
The main HWND's PID/TID remains the binding anchor; the complete bounded
topology is retained in the identity record, so secondary GUI threads do not
make the announced main thread ambiguous. The query handle is opened at READY
0, before the original batch-4 baseline. Sampling
uses the existing polling loop; it creates no observer thread at batch 5.

CPU samples have 50 ms minimum spacing, a maximum of 8000 records, and query
timestamps. They remain in memory until original child cleanup finishes.
Checked CloseHandle results and uncertain cleanup are distinct. A first
constructor/cleanup failure must remain visible even if a later close succeeds.

Clock alignment uses a timestamp BEFORE the original ACK publisher, the
native ACK-observed timestamp after verified reading, and a timestamp after
the host receives that receipt. Publisher return time is not a valid lower
bound. The pure reader retains the conservative offset interval and encloses
the native interval with CPU samples; it does not interpolate, subtract
overhead, attribute an exact call's CPU, or infer disk/GPU/lock causes. Missing
or contradictory evidence is UNKNOWN.

The passive PowerShell observer retains the outer runner Process handle and
records its actual exit. The original owned Jobs still control the workload.
Managed Process.Dispose is not reported as an observed native CloseHandle BOOL.
Natural editor exit may remain UNKNOWN after original diagnostic teardown.

The runtime remains source checkpoint
56bfd448e83aa2512c0c2561e8e1a29f12134360, 53-file closure
7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467,
profile 0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85.
All edits are diagnostic helpers/documentation outside the frozen runtime.

Do not repeat this prefix automatically if it yields no discriminating
interval. Preserve its raw evidence and cleanup, then make the next decision
from the observed boundary. Reader/report failures after engine completion
must be repaired from sufficient existing raw evidence instead of repeating
the engine workload.

The S107 terminal plan was archived byte-for-byte with a hash and AUTHORITY=0
under archive/. The current tools plan remains the sole progress authority.
