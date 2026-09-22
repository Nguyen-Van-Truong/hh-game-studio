# Clean reproduction lessons

The final clean-checkout run used the current wrapper source from a temporary
checkout whose path contained spaces. Python and Godot paths were quoted,
Godot performed a bounded headless import, generated `.blend`/`.blend1` files
were isolated during import and restored in `finally`, and all child processes
returned zero with the required postcondition markers.

A previous attempt is retained in the sibling `20260923-vertical-slice-clean-repro`
folder: it exposed the quoting and fresh-import defects before they were fixed.
This package is Track B evidence only (`AUTHORITY=0`).
