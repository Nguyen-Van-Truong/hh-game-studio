# Actual S52 Linux baseline remint

AUTHORITY=0. This is a new engine run for baseline data, not a gate acceptance.

`mint_baseline.py` froze the actual installed ValidationOwner runtime closure, then ran its real validate/semantic binding methods under the accepted bounded host runner. The exact prior test scene and script were used: fixture_value=9, move_speed=2.25, turn_speed=90.0, enabled=false; the unchanged scene overrides fixture_value=23. The current plugin SHA256 is `951b30efdc494b25117553d5bd34629ff7b5c29c5267c8df268a40c624acb157`.

The owned Linux run `hh-gt03-776beee14f2c41a6960eb402417406d3` completed cleanly. The outer host recorded exit 0, wrapper exit 0, no timeout and verified process tree. Snapshot bytes stayed unchanged. `baseline.json` preserves actual result/stdout/stderr fields and the exact scene/script recipe; it was copied byte-for-byte to `studio/tests/godot/fixtures/validation-run-semantic-baseline.json`. No old engine log or process facts were relabeled. `fixture-provenance.json` records old/new fixture hashes and runtime binding.

After copying, the existing command `python -B studio/tests/godot/test_validation_owner.py` passed **19/19 tests** in 5.893 seconds. Those tests still explicitly mock executor calls for issuer bookkeeping; the new saved facts come from this separate actual native run. The previous S51 fixture remains preserved in Git history and its frozen evidence.

No runtime module or test Python file changed for this task. The new fixture SHA256 is `f3f88dc4132f1e0c8c3c7da58f539c45ae81de29f920187a7d17cb7fb8f4cf09`.
