"""Coordinator verification of bounded GT01 source. NOT full WP acceptance."""
from pathlib import Path
import datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
import re
sys.stdout.reconfigure(encoding="utf-8")
HERE=Path(__file__).resolve().parent
STUDIO=HERE.parents[2]/"studio"
spec=importlib.util.spec_from_file_location("runner",STUDIO/"build/bootstrap/run_fixture.py")
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
root=Path(tempfile.mkdtemp(prefix="hh-gt01-"+stamp+" có dấu "))
(HERE/"partial-run.local.json").write_text(json.dumps({"output":str(root),"run_id":stamp}),encoding="utf-8")
lock=json.loads((STUDIO/"toolchain.lock.json").read_text())
godot=STUDIO/".local/tooling/godot-4.7.2-stable"/lock["godot"]["console_executable"]
blender=STUDIO/".local/tooling/blender-5.2.1-windows-x64/blender.exe"
source=runner.checked_files(STUDIO)
snapshot=root/"snapshot"
shutil.copytree(STUDIO/"fixtures/sample-game",snapshot,ignore=shutil.ignore_patterns(".godot","__pycache__","*.pyc"))
blender_script=root/"create_fixture.py"
shutil.copyfile(STUDIO/"fixtures/sample-blender/create_fixture.py",blender_script)
copy_ok=runner.checked_files(snapshot)==runner.checked_files(STUDIO/"fixtures/sample-game")
assert copy_ok
rows=[]
def run(label,argv,cwd=snapshot,expected_exit=0):
    row=runner.run_process([str(a) for a in argv],cwd=cwd,output=root,timeout=40,label=label)
    stdout=(root/row["stdout"]).read_text(encoding="utf-8",errors="replace")
    stderr=(root/row["stderr"]).read_text(encoding="utf-8",errors="replace")
    row["label"]=label
    row["expected_exit"]=expected_exit
    row["check_pass"]=row["exit_code"]==expected_exit and row["tree_verified"] and not row["timed_out"] and (not stderr.strip() if expected_exit==0 else True)
    if expected_exit==0:
        row["stdout_clean"]=not bool(re.search(r"(?m)^(?:ERROR:|WARNING:|SCRIPT ERROR:)|\|\s*(?:WARNING|ERROR)\b",stdout))
        row["check_pass"] &= row["stdout_clean"]
    if "trace" in label:
        lines=[line for line in stdout.splitlines() if line.startswith("GT01_TRACE ")]
        row["trace"]=[json.loads(line[len("GT01_TRACE "):]) for line in lines]
        row["check_pass"] &= len(lines)==1 and row["trace"][0].get("result")=="PASS" and row["trace"][0].get("phase")=="QUITTING"
    if label=="blender":
        lines=[line for line in stdout.splitlines() if line.startswith("GT01_BLENDER_TRACE ")]
        row["trace"]=[json.loads(line[len("GT01_BLENDER_TRACE "):]) for line in lines]
        row["check_pass"] &= len(lines)==1 and row["trace"][0].get("result")=="PASS"
    rows.append(row)
    print(json.dumps({"label":label,"exit":row["exit_code"],"tree":row["tree_verified"],"check":row["check_pass"]}),flush=True)
    return row["check_pass"]

try:
    assert run("version",[godot,"--version"])
    version=(root/"version-stdout.txt").read_text().strip()
    assert version==lock["godot"]["observed_version"]
    assert runner.hash_file(godot)==lock["godot"]["console_sha256"]
    assert runner.hash_file(godot.with_name(lock["godot"]["gui_executable"]))==lock["godot"]["gui_sha256"]
    assert run("import",[godot,"--headless","--path",snapshot,"--import"])
    assert run("parse",[godot,"--headless","--path",snapshot,"--check-only","--script","res://scripts/trace.gd"])
    assert run("trace-headless",[godot,"--headless","--path",snapshot,"--script","res://scripts/trace.gd"])
    assert run("trace-menu-quit",[godot,"--headless","--path",snapshot,"--script","res://scripts/trace.gd","--","--menu-quit"])
    assert run("trace-window",[godot,"--path",snapshot,"--script","res://scripts/trace.gd","--","--capture"])
    assert run("trace-window-quit",[godot,"--path",snapshot,"--script","res://scripts/trace.gd","--","--menu-quit"])
    assert run("blender",[blender,"--background","--factory-startup","--disable-autoexec","--python-exit-code","2","--python",blender_script,"--","--output",root/"cube.blend"],root)
    saved_hash=runner.hash_file(root/"cube.blend")
    assert run("blender-reject-existing",[blender,"--background","--factory-startup","--disable-autoexec","--python-exit-code","2","--python",blender_script,"--","--output",root/"cube.blend"],root,2)
    assert runner.hash_file(root/"cube.blend")==saved_hash
    assert source==runner.checked_files(STUDIO)
    passed=True
except Exception as error:
    print(type(error).__name__,str(error),flush=True)
    passed=False
finally:
    evidence={"schema":"hh-gt01-partial-v1","run_id":stamp,"status":"PARTIAL_RUNTIME_PASS" if passed else "PARTIAL_RUNTIME_FAIL",
        "source_manifest":source,"snapshot_matches":copy_ok,"source_unchanged":source==runner.checked_files(STUDIO),
        "runs":rows,"limits":["Not GT01 acceptance: bootstrap hardening/reproducibility/rollback/independent critics remain.",
                            "Synthetic input through native Godot event path; not human playtest or OS input automation."]}
    (root/"evidence.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
    print("OUTPUT",root,flush=True)
raise SystemExit(0 if passed else 2)
