# Superagent Classic

The project is a clean-room 2D arena platform shooter. The current product
route is Classic-first: SA-01's technical input contract is accepted, SA-02
reference parity is still under observation, and SA-03's movement room remains
provisional. It does not claim Y8 parity until the ledger and
`tools/check_parity.py --classic` pass on observed evidence.

The owner-approved Classic keyboard layout is documented in
[`docs/control-bindings.md`](docs/control-bindings.md). Ordinary characters
use only the four shared action roles; special-character skills and passives
remain reserved for the locked SA-14 phase.

Run the pinned Godot console executable through `tools/run_guarded.py` after the
shared-machine measurement lock is absent. Do not store reference captures or
generated builds in Git.
