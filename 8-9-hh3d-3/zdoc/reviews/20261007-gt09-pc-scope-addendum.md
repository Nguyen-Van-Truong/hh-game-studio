# GT‑09 / GT‑10‑PC scope addendum — 2026-10-07

`AUTHORITY=0`. This is a routing note, not an acceptance signature and not a
replacement for the frozen GT‑09 candidate package.

The owner decision O12 changes only the target split:

- `GT-08B=DEFERRED_OWNER_NO_ANDROID`. No Android device or emulator evidence is
  available, so no Android compatibility claim may be emitted.
- GT‑09 remains the current work package. Its technical, owner-playtest and
  two-critic gates are unchanged; the lack of Android does not waive them.
- After GT‑09 is coordinator-accepted, `GT-10-PC` may run on the frozen
  Windows/Linux/Linux-headless source. Its manifest must contain
  `supported_targets=Windows/Linux/Linux-headless` and
  `android=DEFERRED_NO_DEVICE`.
- Full GT‑10 remains a separate result and still requires physical GT‑08B if
  the owner later reopens Android. PC evidence must not be relabelled as full
  GT‑10 or Android evidence.

Current frozen GT‑09 evidence remains the candidate package
`20261007-gt09-critic-package-candidate.md`. Open gates are still the owner
playtests, native AUTH‑05/E2E and dependency-closure evidence, measured MCP
capability/reconnect checks, and two independent critics on the final hash.

The next safe action is to close those GT‑09 gates. Do not start GT‑10‑PC while
GT‑09 is still `IN_PROGRESS`, and do not dispatch native work while a competing
owner Docker/WSL workload holds the host.
