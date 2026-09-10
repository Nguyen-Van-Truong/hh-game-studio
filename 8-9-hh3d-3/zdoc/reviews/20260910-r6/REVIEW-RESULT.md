# S18 / GT-01: work in progress, no acceptance

The two canonical TXT plans remain the sole progress authority. Tools GT-01
is active; GT-02 and HH World have not opened. S17 was a plan audit, not a
runtime implementation or an independent design ACCEPT.

## Adjudication of the S17 report

The main findings are valid: the old pin/test used 4.7.1; lock/evidence included
machine paths; the runner accepted exit codes without trace/log/tree proof;
worker deliverables needed machine checks; studio source needed a WIP checkpoint.
Rechecked S17: 31/31 static mutation tests. S16 snapshot fails the nine new
checks. These tests establish specified clauses, not semantic completeness.

Two corrections matter:

- The old runner's report said DIAGNOSTIC, not PASS. It returned exit0 on
  two successful processes; that still did not prove GT-01 acceptance.
- Godot --version returns an abbreviated source commit. Map it to the full
  source tag in godotengine/godot, not the godot-builds repository tag.
  The supplied user conversation does not establish the quoted owner words
  "Godot stock 4.7.2"; S18 describes the pin as a coordinator choice within
  the owner's implementation authorization.

## Verified implementation progress

Godot4.7.2 official editor archive and matching templates have been downloaded
and compared against SHA256 and the release SHA512-SUMS (see
godot-official-artifacts.json). Console and GUI hashes are in the portable lock.
Machine installation paths live under ignored studio/.local/.

Headless run GT01-S17-20260910-04 completed import, trace parse and input trace
with actual exit0, empty stderr and zero active Job Object processes. The trace
observed QUITTING after the real input path. This is partial runtime evidence,
not full GT-01 acceptance. Subsequent changes require a new source freeze/run.

Initial --editor --quit diagnostics produced shutdown warnings; --import
waits for import completion and fixed those warnings on the tested snapshot.
Several failed template download verifications came from transcription mistakes
in the temporary downloader's expected hashes, not corrupt official releases.
The final verification streams both hashes and reads SHA512 directly from SUMS.

## Grok batch review (20260910T054739Z)

Four exact grok-4.6 / xhigh sessions exited0 with completion notices. All four
deliverables were rejected as supplied; raw responses and hashes are retained.
No ACCEPT was invented.

- Runner audit falsely says Godot emits only a hyphenated version; actual
  output is 4.7.2.stable.official.ed1daf0bf. It also incorrectly denies child
  Job inheritance and suggests querying a closed Job handle. Do not apply.
  Its concern about missing timeout metadata and weak negative tests is useful;
  record unavailable target exits honestly, never synthesize exit0.
- Fixture audit falsely says default ui_left/ui_right actions are unbound and
  idle frames can never include physics. Actual movement passed. The useful
  refinement is to wait physics frames explicitly and assert both body and tick
  freeze. Its suggested 30-second quit delay is unnecessary.
- Acquisition source uses wrong cwd/root paths, reads the 1.28GB file into RAM,
  removes pre-existing files/staging and lacks required URL/path validation.
  No canonical source was replaced by this bundle.
- Blender source has an indentation error, unsupported enum, incorrect output
  argument parsing, leftover default objects and unsafe final save. Not run.

The next batch uses isolated writable copies with actual py_compile/unittest
requirements, no canonical write permission, no model fallback, at most two
polls and a bounded supervisor. A notification is only a request for review.

## Remaining GT-01 gates

Runner hardening and stronger negative tests, reproducible toolchain bootstrap,
rollback on an isolated package copy and two valid independent critics.
The headed and Blender cases below are functional evidence, not WP closure. No runtime, human, legal or
hundreds-of-millions capacity acceptance is claimed.

## Primary references

- [Godot official 4.7.2 artifacts](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable)
- [Godot CLI import/parse semantics](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
- [Windows Job inheritance and cleanup](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Official Grok CLI](https://docs.x.ai/build/cli/reference)
- [Blender publisher checksums](https://download.blender.org/release/Blender5.2/blender-5.2.1.sha256)

## Verified partial run 20260910T131143Z

The coordinator host process exited0. All nine subprocess checks met their
expected exits (eight exit0; existing Blender output rejection exit2). Godot
version/import/parse, headless movement/pause/resume/quit, menu-quit, windowed
trace/menu-quit, Blender save/reopen and existing-output rejection completed.
Every Job Object reported zero active processes; successful cases had no
stdout WARNING/ERROR or stderr. Copy hashes matched and source remained unchanged.
The existing .blend hash was unchanged after rejection. A screenshot of the
actual menu was inspected. Synthetic input went through Godot's native event
path; this is not a human playtest or an OS input automation claim.

The prior harness print failed on a Unicode path; it was fixed to use UTF-8 and
the complete run reminted. Another run revealed factory Blender brush references
in stdout, despite empty stderr; the final fixture removes unused factory brush
data and the harness now examines both streams. Earlier runs remain diagnostic.

Portable evidence: studio/evidence/gt01-partial-20260910T131143Z. package.json
binds redacted artifacts and raw hashes; source manifest includes the exact
runner, fixture, lock and tests. Blender output itself remains local and
reproducible from original source. Nothing has been accepted by critics.

## Review-folder tidy

Inventory found about2.23MB, mostly useful historical reports/snapshots/diffs.
Added reviews/README.md and ignored machine-specific *.local.json; caches were
already ignored. No historical artifacts removed. An attempted removal of
untracked Python bytecode was rejected by automatic approval review with only
blocked-by-policy detail; no bypass or alternative deletion was attempted.

## Executable worker batch 20260910T125404Z

- Acquisition exited0 without deliverable/report. Rejected.
- Blender exited1/max-turns after wrong Windows Python/shell assumptions; no
  source delivery. Coordinator fallback created and ran the fixture above.
- Runner was still pending at poll2/2. Its output must be reviewed on resume;
  its isolated files have never been copied over canonical source.

Current runner WIP still has known validation gaps. Its five tests pass but
the duplicate-output main test uses invalid setup and does not establish that
rejection contract; this is explicitly queued for repair, not a coverage claim.
