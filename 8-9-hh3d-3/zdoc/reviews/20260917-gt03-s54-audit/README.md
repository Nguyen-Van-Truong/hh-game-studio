# S54 integration WIP checkpoint

GT-01 and GT-02 remain accepted. GT-03 and GT-04 remain in progress. The
checkpoint curates source plus separately scoped, byte-verified components;
their different closures are not one final conformance closure.

- Godot edit03: 61 native harness checks, audit 391 portable files and eight
  corruption rejections. Frozen source `0fa75dac3afe05a7476ad12c852be221eb84c512f46f853d4c8ee1fab2042a32`.
- Godot recovery-publication01: 14 checks, actual publisher crash92 and
  fresh-authority last-good recovery; 20 audit corruptions rejected. Frozen
  source `469b22d6788ef63c7ca4d6e7dc91e703494db439834dffacdef7d476a9464bdc`.
- Blender publication03: 135 Python tests and 16 native checks, protected
  bundle/receipt and actual fresh Blender reopen. Frozen source
  `fc54433ac4a373e6e79aac33de1e6641e1a434cf2894a8ced622a445db36cd20`.
  Public ACK and live scene recovery remain false.
- Godot units01: frozen source
  `ad72fff7d3a4856f959a5da38c2db1d40d5c2cdfb1ab971aca11b256ccfdf77c`.
  The other lane completed 627 tests with zero failures/errors/skips and
  actual clean process exits. The journal lane reached its 600-second cap
  in V5 with no completion marker; its owned Job was cleaned. **The full
  matrix is incomplete.** Individual `ok` lines in that aborted lane are
  diagnostic and do not supply the missing process completion.

The original controller is retained in units01 with its invocation digest.
Its failure-report formatting did not handle absent counts after timeout;
the current controller preserves incomplete results and uses per-module
journal partitions with separate bounds and completion records. No result
from units01 has been rewritten as a success.

`checkpoint.py` validates curated manifest bytes, excludes live private
storage/caches, and optionally compares exact Git index/HEAD blobs. It is
only a WIP checkpoint inventory, not a semantic verifier or critic verdict.
Each component audit retains its own scope and reproduction instructions.
Final integration still needs the outstanding native recovery/FIFO/Stop
cases and two independent reviews of one final frozen closure.
