# GT-01 bootstrap

This fixture is independent of H2/game products. Read `studio/toolchain.lock.json` first.
The lock records observed capabilities and missing Blender/Android capabilities; it does not claim acceptance.

Windows headless check (the runner uses the locked binary and an isolated Unicode snapshot):
`python studio/build/bootstrap/run_fixture.py --studio-root studio --godot-exe studio/.local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe --expected-version 4.7.2-stable --console-sha256 <lock value> --gui-sha256 <lock value> --run-id <new id> --command-id <new id> --output <new directory outside studio>`

A real target exit, exact `GT01_TRACE` postcondition, clean stderr, Job Object process-tree proof,
and stable source hash are required. `CANDIDATE` evidence is still subject to TQ01/TX12/TX14 and
two independent critics. Do not use the repo root as `--path`, do not fetch latest, and do not run
a second Godot process on the same fixture path.
