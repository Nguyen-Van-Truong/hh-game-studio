# S164 DbgEng index-repair attempt (AUTHORITY=0)

This bounded attempt preserved S163 and tested a proposed vtable-index repair.
It compiled both the harness and the already-owned S163 native fixture with
actual compiler exit `0`; the harness exited `1`. The attempt used
`WaitForEvent=90` and `Execute=63` after an incomplete header count. The full
Windows SDK interface includes three `STDMETHODV` entries, so the authoritative
indices are `WaitForEvent=93` and `Execute=66`, the values used by S163.

The attempted path returned `WaitForEvent=0` but then
`GetCurrentProcessSystemId=0x8000FFFF`; no fixture output or breakpoint proof
was produced. This is an invalid diagnostic boundary, not debugger attribution,
not a leak/root-cause result, and not GT06 evidence. It is retained to explain
why the proposed repair was rejected. Automatic retry is disabled.
