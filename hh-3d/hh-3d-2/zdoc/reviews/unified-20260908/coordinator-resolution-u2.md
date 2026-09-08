# Coordinator resolution U1 -> U2

U1 critics A and B independently matched freeze
a6fe3e49d81f93b6dd4db81cc20e9a7db5155a0be9466b9995ede7356761de93,
both REVISE (host exits0). No acceptance carried forward.

A1 P1-01 vs ST-05: Godot-only staged save/readback, not cross-app activation.
ST-03 only disposable fixture/snapshot import; ST-05 active last-good publish.
A2 protocol owner: ST-01 owns studio/protocol/envelope; P1-01 operation catalog
lives in studio/godot-addon with envelope read-only. No duplicate DoD.
A3 observation: P1-01 proves editor/Play process separation through bootstrap;
ST-04 owns real input/pause-clock/capture/reviewer UI.
A nits: assets-src unified; studio/pipeline and studio/package added to tree;
P6-02 leftover English replaced.
B1 EX01: one active/account and at most one target-pending during cross-room
handoff; same-room device rebind needs no extra slot; no universal unique
account constraint blocking valid pending target.
B2 multi-grant: one attempt row lock/terminal, all grants+quota/outbox commit
one transaction, expiry only before RESULT_RECORDED.
Coordinator: removed dangling D04 ref; DB-D2 lookup barrier explicitly requires
new protected COMMIT for UNKNOWN recovery on current fenced primary/timeline,
never visible-row/cache/health-only success. Fault tests at P3/P6 required.
40WP order/status,54edges,48EX unchanged, no runtime/engine/server changes.

Static U2 PASS_STATIC_ONLY,15source files,36links, arithmetic consistent.
U2 source manifest:
0fa81a96099432e9d6f2b086600780b2580e222a8b88b5dc591579279c5cab22

One first critic-B U2 CLI invocation failed EPERM renaming cli-config; output
empty, hostexit1, not a verdict. Retry launched as separate exact-model session.
Do not read/dump config content or treat exception as model failure.
CLAUDE.md exact-doc routing exception added separately after freeze; it is
not part of U2 critics source set and changes no plan requirement. Coordinator
validated path and records its separate hash in claude-routing-addition.json.

Final U2 reruns ended without verdict: critic A hostexit1 at18:31:25+07 and
critic B retry hostexit1 at18:31:21+07, both stdout0 and ActionRequiredError
out of usage. First B invocation remains EPERM/hostexit1, not a review.
No fallback model or further quota retry used. Independent U2 review remains
PENDING_CURSOR_USAGE_LIMIT; coordinator resolutions and static PASS do not
constitute critic acceptance. See REVIEW-RESULT.md and actual host records.
