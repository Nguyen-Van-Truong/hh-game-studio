# S106 coordinator preflight decision

AUTHORITY=0. Implementation review, not either final GT-06 critic verdict.

The coordinator reviewed the new GateObserver, frozen-helper loading, exact
batch reconstruction, Stop handling and truthful lifecycle classification.
Thirty fake-only integration tests and the source-pin check exited 0. The
tests execute relocated child hooks with real retained sample/context shapes;
they cover the integration failures that the older syntax-only check missed.

The runtime's 53 files, profile, native gate and S103 generated overlay remain
unchanged. The new collector records the original gate before PSS, captures
b0 for preflight and b4/b5 for the bounded comparison, preserves a primary gate
error when instrumentation fails, and stops on UNKNOWN capture/cleanup. It
reconstructs 1000 HTTP commands plus 100 native cycles per completed batch from
exact references. These checks authorize one actual one-batch preflight, not
benchmark acceptance. Only a clean bound preflight permits one six-batch prefix.
No identical-prefix retry loop is authorized by this review.

`observe_runner.ps1` passively observes the outer Python runner using a retained
System.Diagnostics.Process handle. It records the actual exit after WaitForExit
and never reopens a numeric PID. It adds no outer Job, avoiding interference with
the existing nested Job process limits. The runner enforces its own 180/1200s
bound; the passive observer has no independent timeout. Its managed Dispose is
reported separately from an unobserved native CloseHandle return.

An independent API check used a short Python child exiting 7 and observed the
same retained Process API sequence successfully; no engine was launched. The
review found two Python candidates on PATH and the wrapper was fixed to select
and bind one scalar executable. The helper-SHA negative check rejected an all-zero
hash before creating output or dispatching any process. Parser errors were zero.

PSS can affect the next READY interval and provides only partial type information.
No time or memory is subtracted. Forced diagnostic teardown may leave editor
natural exit UNKNOWN; import wrapper native-handle-close proof remains separate.
The external observer's raw exit supplement does not rewrite the inner result.
All diagnostic data remains ineligible for F13/F14, leak or root-cause claims.

The independent native-save research gives a specific preview-path cost to
investigate, but changing the formal benchmark's save path would change coverage.
No runtime/save-path optimization or formal retry is approved by this packet.
