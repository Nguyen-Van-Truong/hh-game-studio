"""Prepare independent, bounded Grok jobs; canonical source is never leased."""
from pathlib import Path
import datetime, hashlib, json, shutil, tempfile, uuid

HERE = Path(__file__).resolve().parent
ZDOC = HERE.parents[1]
STUDIO = ZDOC.parent / "studio"
PREVIOUS = HERE.parent / "20260910-r5"
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
batch_root = Path(tempfile.gettempdir()) / ("hh3d-gt01-review-" + stamp)
batch_root.mkdir(exist_ok=False)

def source(paths):
    return "\n".join("FILE " + p + "\n" + (STUDIO / p).read_text(encoding="utf-8") for p in paths)

audit = """Independent code audit. Do not write files or invoke subprocesses. Do not claim tests ran.
Return valid JSON only: {"verdict":"REVISE or ACCEPT_CODE_SCOPE","findings":[{"severity":"P1/P2/P3","file":"relative path","evidence":"exact problematic source text","reason":"specific failure case","fix":"concrete correction","test":"test distinguishing correct from broken"}],"limits":["unproved gates"]}.
Audit only supplied implementation, not all GT01. Headless run passed on Godot4.7.2 with clean stderr and zero Job Object ActiveProcesses, but that is NOT GT01 acceptance. Report demonstrated flaws, not speculative preferences. Keep response under 2500 words. Read the entire supplied source. No need for tools.\n"""
tasks = {
    "runner-audit": audit + """Focus: gated helper assigned Windows Job before GO, descendants, actual target exit versus wrapper, timeout/launch failure, pin exact version, output validation before resolve, source copy closure, stdout/error false acceptance, report forgery, resource limits. Current four superficial tests are insufficient: distinguish tests that really exercise rejection. Do not demand that timeout has a graceful target exit. Suggest narrow fixes.\n""" + source(["build/bootstrap/run_fixture.py", "tests/bootstrap/test_run_fixture.py", "toolchain.lock.json"]),
    "fixture-audit": audit + """Focus: native focused Button via key press/release, menu Quit focus, physics ticks vs idle frames, pause body AND tick, post-QUITTING timing, failure exit, watchdog, headed parity. No direct fixture handler calls as E2E. Find code defects and concrete next patch, do not rewrite unrelated runner.\n""" + source(["fixtures/sample-game/project.godot", "fixtures/sample-game/main.tscn", "fixtures/sample-game/scripts/main.gd", "fixtures/sample-game/scripts/trace.gd"]),
    "toolchain-bootstrap": """Return valid JSON ONLY {"files":[{"path":"build/bootstrap/acquire_toolchain.py","content":"FULL Python3.11 stdlib source"}],"notes":["unverified items"]}. You generate code, not execute it; no fabricated success.
Implement a small reproducible acquisition CLI --studio-root required, using toolchain.lock.json schema HH-STUDIO-TOOLCHAIN-LOCK-2. Only current pinned Godot editor ZIP + SUMS + matching templates. No Blender, no fallback/latest. Download exact lock URLs with HTTPS host allowlist github.com/godotengine/godot-builds/releases/download/4.7.2-stable/; urllib redirects to release-assets.githubusercontent.com allowed. Install only within studio/.local/tooling, no system caches or PATH. Stream sha256; known byte limit from lock for templates, ZIP 86013866, SUMS 5682; reject excess/truncated bytes, timeout30 per read. Download .part exclusive, verify then rename. Reuse only when hash verified. SUMS text actual hash must equal lock; parse entry filename exact and compare SHA512 for editor and templates BEFORE extraction. Archive safe extraction: editor exactly expected GUI+console names, size bounds, no symlink/absolute/traversal, no existing target overwrite; if installed verify both hashes. Extract to new staging directory then rename final godot-4.7.2-stable. Verify installed GUI/console SHA from lock. Keep templates archive verified but not globally installed. Write portable receipt under studio/.local with observed size/hash/SHA512/official source URLs; no absolute path in printed summary. Python source <=180 lines, comments for safety. No evidence claim until host executes script. All context lock below.\n""" + source(["toolchain.lock.json"]),
    "blender-fixture": """Return valid JSON ONLY {"files":[{"path":"fixtures/sample-blender/create_fixture.py","content":"FULL SOURCE"},{"path":"fixtures/sample-blender/README.md","content":"FULL TEXT"}],"notes":["unverified items"]}. Generate code only; don't claim execution. Create original simple Blender5.2.1 background fixture with bpy trusted script, use --background --factory-startup --disable-autoexec --python script -- --output <new .blend>. Require output parent exists, output filename .blend, output does not exist; reject symlink/reparse output/ancestors before resolve, don't overwrite any artist file. Start from empty scene (factory startup process only), create named unit cube mesh centered at local origin, deterministic material, applied identity transform, meters/unit1, Blender Z-up right-handed. Save to staging .blend in same directory, reopen using bpy.ops.wm.open_mainfile then verify object name, one mesh, exact expected bounds/identity transform/material/units via readback, atomic rename to requested new output (no replace). No texture download or external references. Print one GT01_BLENDER_TRACE JSON result PASS with relative filename/version/axis/origin and actual mesh counts only after save+reopen verified; exception exits nonzero (host must use --python-exit-code 2). No bridge/export/GT04 functionality. Source under120lines. Include user command and clear candidate-only limits; original mesh no third-party assets.\n"""
}
rows = []
for name, task in tasks.items():
    attempt = batch_root / name
    workspace = attempt / "workspace"
    workspace.mkdir(parents=True)
    config = {"id":"hh3d-gt01-"+name,"attempt":stamp,"session":str(uuid.uuid4()),
              "workspace":str(workspace),"notification_repo":str(ZDOC.parents[2]/"hoan-hao"),
              "turn_limit":4,"max_seconds":420,"notify":True,"web_search":False,
              "delivery":"JSON_BUNDLE","tools":"read_file"}
    (attempt/"TASK.txt").write_text(task,encoding="utf-8")
    (attempt/"config.json").write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    shutil.copy2(PREVIOUS/"Run-Worker.ps1",attempt/"Run-Worker.ps1")
    rows.append({"role":name,"attempt_dir":str(attempt),"workspace":str(workspace),
                 "session":config["session"],"supervisor_pid":None,"task_sha256":hashlib.sha256(task.encode()).hexdigest()})
record = {"schema":"HH3D-WORKER-BATCH-1","created_utc":stamp,"batch_root":str(batch_root),
          "model":"grok-4.6","reasoning_effort":"xhigh","poll_budget":2,"polls_used":0,
          "lease_policy":"All workers supply read-only code/review bundles; no canonical path write.",
          "jobs":rows}
(HERE/"active-batch.local.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
(batch_root/"batch.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print(batch_root)
