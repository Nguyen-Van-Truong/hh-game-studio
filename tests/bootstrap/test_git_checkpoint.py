#!/usr/bin/env python3
"""R7-WP3: Git checkpoint, asset LFS, rollback (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP3 [ ]; while unticked CURRENT_VALID_WP=R7-WP3; after tick allow R7-WP4+.
Must NOT lock [x] forever. Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable.
No skip-PASS. Does not start R7-WP4 or R8. Does not tick G4.
No snake demo. No R8 dogfood tree. No driver scripts for the snake demo.

Verify (encoded here; this file is the official harness):
  - dirty user file survives checkpoint/revert (not overwritten)
  - untracked asset is not silently eaten; allowlisted+LFS or left untracked/paused
  - merge conflict → blocked/paused, not green done
  - large binary without LFS is refused (not a raw blob commit)
  - detached HEAD + kill/restart still finds the checkpoint (RESUME)
  - LIVE path through real git.checkpoint / git.revert_checkpoint (sidecar)

Labels: DIRTY_USER, UNTRACKED_ASSET, CONFLICT, LARGE_BINARY, DETACHED, RESUME
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r7w3"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
LFS_THRESHOLD = 65536


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def git_bin() -> str:
    return "git.exe" if os.name == "nt" else "git"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP3 [ ]; while unticked require CURRENT_VALID_WP=R7-WP3."""
    errors: list[str] = []
    current = ""
    wp3 = None
    wp4 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP3\b", stripped):
            wp3 = stripped
        if re.match(r"^R7-WP4\b", stripped):
            wp4 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp3 is None:
        return ["plan missing R7-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R7-WP3 heading must keep [ ] until coordinator tick")
        if current != "R7-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP3 while WP3 is unticked)")
        if wp4 and re.search(r"\[x\]", wp4, re.IGNORECASE):
            errors.append("R7-WP4 must stay unticked; this WP does not start multi-agent scheduler")
    elif not re.match(r"^R7-WP([4-9]|\d{2,})$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP4+ after R7-WP3 tick)")
    if g4 is not None and re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("official harness must not tick G4")
    return errors


def _unlock_and_remove(func, path, _exc) -> None:
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def wipe_dir(folder: Path) -> None:
    if not folder.exists():
        return
    for child in folder.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                os.chmod(child, 0o700)
                child.unlink()
        except OSError:
            pass
    try:
        shutil.rmtree(folder, onexc=_unlock_and_remove)
    except TypeError:
        shutil.rmtree(folder, onerror=_unlock_and_remove)


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for _ in range(8):
        if not TEMP_DIR.exists():
            break
        wipe_dir(TEMP_DIR)
        time.sleep(0.25)
    if TEMP_DIR.exists():
        leftovers = [p.as_posix() for p in TEMP_DIR.rglob("*") if p.is_file()]
        if leftovers:
            errors.append(f"r7w3 leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in ("DIRTY_USER", "UNTRACKED_ASSET", "CONFLICT", "LARGE_BINARY", "DETACHED", "RESUME"):
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "drive_" + "snake" in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "does not tick G4" not in self_text:
        errors.append("official test must refuse to tick G4")
    if "does not start R7-WP4" not in self_text:
        errors.append("official test must refuse to start R7-WP4")
    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r7w3/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r7w3/")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if 'p.contains("/r7w3' not in export_gd and 'p.contains("r7w3' not in export_gd:
        errors.append("export _should_skip must contain() r7w3")
    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "r7w3" not in constants:
        errors.append("hh_constants must name r7w3")
    adapter = BRIDGE / "src" / "ledger" / "git_adapter.ts"
    jail_ts = BRIDGE / "src" / "ledger" / "git_jail.ts"
    if not adapter.is_file():
        errors.append("missing git_adapter.ts")
    else:
        atext = adapter.read_text(encoding="utf-8")
        jtext = jail_ts.read_text(encoding="utf-8") if jail_ts.is_file() else ""
        if "agent/" not in atext and "agent/" not in jtext:
            errors.append("git adapter must create branch agent/<project>/<run>")
        if "git_real" not in atext:
            errors.append("git adapter must distinguish real git from COW")
        if "LFS_THRESHOLD" not in atext and "lfs_threshold" not in atext:
            errors.append("git adapter must name LFS threshold")
        if "renameSync" not in atext and ".tmp" not in atext:
            errors.append("git adapter must tmp+rename the manifest")
        if "parent walk" not in atext.lower() and "parent_walk" not in atext:
            errors.append("git adapter must refuse parent .git walk")
    jail = BRIDGE / "src" / "ledger" / "git_jail.ts"
    if not jail.is_file():
        errors.append("missing git_jail.ts")
    else:
        jtext = jail.read_text(encoding="utf-8")
        if 'FORBIDDEN_SUB' not in jtext and '"reset"' not in jtext:
            errors.append("git jail must forbid git reset")
        if "--hard" not in jtext:
            errors.append("git jail must deny --hard")
        if "--force" not in jtext:
            errors.append("git jail must deny --force")
        if "--amend" not in jtext:
            errors.append("git jail must deny --amend")
        if "GIT_DIR" not in jtext:
            errors.append("git jail must isolate GIT_DIR from the parent environment")
    reads = (BRIDGE / "src" / "read" / "sidecar_reads.ts").read_text(encoding="utf-8")
    if "readGitStatus" not in reads:
        errors.append("sidecar git.status must use the jailed adapter")
    if 'spawnSync("git"' in reads or "spawnSync('git'" in reads:
        errors.append("sidecar_reads must not spawn git against projectRoot (monorepo walk)")
    txn = (BRIDGE / "src" / "ledger" / "transaction.ts").read_text(encoding="utf-8")
    if "applyGitSliceCheckpoint" not in txn:
        errors.append("transaction must call the real git slice checkpoint")
    if "sidecar-cow" not in txn:
        errors.append("COW fallback must not claim to be real git")
    ckpt = (BRIDGE / "src" / "policy" / "checkpoint.ts").read_text(encoding="utf-8")
    if "resolveJailedGit" not in ckpt:
        errors.append("R3 COW must jail git (no parent update-ref)")
    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if ("kho" + "-bi-an") in blob or ("/snake/") in blob.replace("\\", "/"):
            errors.append(f"{posix} mentions R8/snake trees")
    return errors


def run_git(repo: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git_bin(), "-c", "core.autocrlf=false", "-C", str(repo), *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=check,
        encoding="utf-8",
        errors="replace",
    )


def studio_head() -> str:
    proc = subprocess.run(
        [git_bin(), "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return (proc.stdout or "").strip()


def studio_branch_exists(name: str) -> bool:
    proc = subprocess.run(
        [git_bin(), "-C", str(REPO_ROOT), "rev-parse", "--verify", f"refs/heads/{name}"],
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0


def init_fixture(job: str) -> Path:
    repo = TEMP_DIR / job
    if repo.exists():
        shutil.rmtree(repo, ignore_errors=True)
    repo.mkdir(parents=True)
    run_git(repo, ["init"])
    run_git(repo, ["config", "user.email", "r7w3@localhost"])
    run_git(repo, ["config", "user.name", "r7w3"])
    run_git(repo, ["config", "core.autocrlf", "false"])
    (repo / "README.md").write_text(f"seed {job}\n", encoding="utf-8", newline="\n")
    run_git(repo, ["add", "--", "README.md"])
    committed = run_git(repo, ["commit", "-m", f"seed {job}"])
    if committed.returncode != 0:
        raise RuntimeError(f"fixture commit failed: {committed.stderr} {committed.stdout}")
    return repo


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def start_sidecar() -> tuple[subprocess.Popen[str], Path, str, list[str]]:
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(PLUGIN_PROJECT)],
        cwd=str(BRIDGE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    err_lines: list[str] = []
    threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
    desc_path, desc = sess.find_descriptor(proc.pid)
    secret = str(desc.get("token") or "")
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-git-checkpoint", "version": "0"},
                },
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    init_line = sess.readline_timeout(proc.stdout, 8.0)
    if "result" not in json.loads(init_line):
        raise RuntimeError(f"MCP initialize failed: {init_line}")
    return proc, desc_path, secret, err_lines


def stop_sidecar(proc: subprocess.Popen[str] | None, desc_path: Path | None) -> None:
    if proc is not None:
        life.stop_proc(proc)
    if desc_path and desc_path.is_file():
        try:
            desc_path.unlink()
        except OSError:
            pass
        lock = desc_path.with_name("sidecar.lock")
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def tool_git(
    proc: subprocess.Popen[str],
    req_id: int,
    action: str,
    params: dict,
    timeout: float = 20.0,
) -> tuple[int, dict]:
    return pin.tool_call(proc, req_id, "godot.git", action, params, timeout=timeout)


def after_of(body: dict) -> dict:
    return pin.after_of(body)


def err_code(body: dict) -> str:
    return pin.err_code(body)


def tracked_paths(repo: Path) -> set[str]:
    listed = run_git(repo, ["ls-files"])
    return {line.strip().replace("\\", "/") for line in (listed.stdout or "").splitlines() if line.strip()}


def blob_in_history(repo: Path, name: str) -> bool:
    listed = run_git(repo, ["rev-list", "--objects", "--all"])
    return any(line.strip().endswith(name) for line in (listed.stdout or "").splitlines())


def live_errors() -> tuple[list[str], str, str, str, str, str, str, str]:
    errors: list[str] = []
    live = "unrun"
    dirty_l = "unproven"
    untrack_l = "unproven"
    conflict_l = "unproven"
    large_l = "unproven"
    detached_l = "unproven"
    resume_l = "unproven"
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    req_id = 2
    before_head = studio_head()
    try:
        proc, desc_path, secret, err_lines = start_sidecar()
        live = "sidecar"

        req_id, none_status = tool_git(proc, req_id, "status", {"detail": "short"})
        none_after = after_of(none_status)
        if none_after.get("parent_walk_refused") is not True and none_after.get("repo") not in {"none", ""}:
            errors.append(f"git.status without project repo must refuse parent walk: {none_after}")
        dumped = json.dumps(none_after)
        if "bridge/src" in dumped or "zdocs/" in dumped:
            errors.append("git.status dumped monorepo paths")

        dirty_repo = init_fixture("dirtyuser")
        (dirty_repo / "user_notes.txt").write_text("USER-KEEP-1\n", encoding="utf-8", newline="\n")
        (dirty_repo / "slice.gd").write_text("var n := 1\n", encoding="utf-8", newline="\n")
        run_git(dirty_repo, ["add", "--", "user_notes.txt"])
        run_git(dirty_repo, ["commit", "-m", "track user notes"])
        (dirty_repo / "user_notes.txt").write_text("USER-KEEP-1\nDIRTY-TRACKED\n", encoding="utf-8", newline="\n")
        run_git(dirty_repo, ["add", "--", "user_notes.txt"])
        req_id, ckpt = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "r7w3 dirty slice",
                "paths": ["res://r7w3/dirtyuser/slice.gd"],
                "repo": "r7w3/dirtyuser",
                "run_id": "dirtyuser",
                "project": "r7w3",
            },
        )
        ckpt_after = after_of(ckpt)
        if ckpt.get("ok") is not True or ckpt_after.get("git_real") is not True:
            errors.append(f"DIRTY_USER checkpoint not real git: {sess.redact(json.dumps(ckpt), secret)}")
        if ckpt_after.get("branch") != "agent/r7w3/dirtyuser":
            errors.append(f"DIRTY_USER branch={ckpt_after.get('branch')!r}")
        if "USER-KEEP-1" not in (dirty_repo / "user_notes.txt").read_text(encoding="utf-8"):
            errors.append("DIRTY_USER user file clobbered by checkpoint")
        if "user_notes.txt" in str(ckpt_after.get("files") or "") or "user_notes.txt" in str(
            ckpt_after.get("staged") or ""
        ):
            errors.append("DIRTY_USER checkpoint included the staged user file")
        branch = run_git(dirty_repo, ["rev-parse", "--abbrev-ref", "HEAD"])
        if (branch.stdout or "").strip() != "agent/r7w3/dirtyuser":
            errors.append(f"DIRTY_USER fixture HEAD branch={branch.stdout!r}")
        commit = str(ckpt_after.get("git_commit") or "")
        if len(commit) < 7:
            errors.append("DIRTY_USER missing git_commit")
        show_user = run_git(dirty_repo, ["show", f"{commit}:user_notes.txt"]) if commit else None
        if show_user is not None and show_user.returncode == 0 and "DIRTY-TRACKED" in (show_user.stdout or ""):
            errors.append("DIRTY_USER committed staged user dirt via whole-index commit")
        if "DIRTY-TRACKED" not in (dirty_repo / "user_notes.txt").read_text(encoding="utf-8"):
            errors.append("DIRTY_USER lost tracked dirty notes after checkpoint")
        show = run_git(dirty_repo, ["log", "-1", "--format=%B"])
        if "command_id=" not in (show.stdout or "") and str(ckpt.get("command_id") or "") not in (show.stdout or ""):
            if commit and commit not in (run_git(dirty_repo, ["rev-parse", "HEAD"]).stdout or ""):
                errors.append(f"DIRTY_USER commit not on fixture HEAD: {show.stdout}")
        (dirty_repo / "user_notes.txt").write_text("USER-KEEP-1\nUSER-KEEP-2\n", encoding="utf-8", newline="\n")
        (dirty_repo / "slice.gd").write_text("var n := 99\n", encoding="utf-8", newline="\n")
        req_id, diff_body = tool_git(
            proc,
            req_id,
            "diff",
            {"path": "res://r7w3/dirtyuser/slice.gd", "repo": "r7w3/dirtyuser"},
        )
        diff_after = after_of(diff_body)
        if "99" not in str(diff_after.get("text") or "") and "99" not in json.dumps(diff_body):
            errors.append(f"DIRTY_USER git.diff missed slice dirt: {diff_body}")
        req_id, poison = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "r7w3 dirty poison",
                "paths": ["res://r7w3/dirtyuser/slice.gd"],
                "repo": "r7w3/dirtyuser",
                "run_id": "dirtyuser",
                "project": "r7w3",
            },
        )
        poison_after = after_of(poison)
        if poison.get("ok") is not True or str(poison_after.get("git_commit") or "") == commit:
            errors.append(f"DIRTY_USER poison slice commit failed: {poison}")
        ckpt_id = str(ckpt_after.get("checkpoint_id") or "")
        req_id, reverted = tool_git(
            proc,
            req_id,
            "revert_checkpoint",
            {"ref": ckpt_id, "paths": ["res://r7w3/dirtyuser/slice.gd"]},
        )
        rev_after = after_of(reverted)
        if reverted.get("ok") is not True or rev_after.get("git_real") is not True:
            errors.append(f"DIRTY_USER revert not real git: {sess.redact(json.dumps(reverted), secret)}")
        slice_txt = (dirty_repo / "slice.gd").read_text(encoding="utf-8")
        if slice_txt != "var n := 1\n":
            errors.append(f"DIRTY_USER revert did not restore slice: {slice_txt!r}")
        notes = (dirty_repo / "user_notes.txt").read_text(encoding="utf-8")
        if "USER-KEEP-2" not in notes or "USER-KEEP-1" not in notes:
            errors.append(f"DIRTY_USER revert overwrote user file: {notes!r}")
        revert_commit = str(rev_after.get("revert_commit") or "")
        if len(revert_commit) < 7 or revert_commit == commit:
            errors.append(f"DIRTY_USER revert must be a new commit, got {revert_commit!r} vs {commit!r}")
        log = run_git(dirty_repo, ["log", "-1", "--format=%B"])
        if "hh-agent revert" not in (log.stdout or ""):
            errors.append(f"DIRTY_USER revert commit message missing: {log.stdout!r}")
        pre = rev_after.get("dest_preimage") if isinstance(rev_after.get("dest_preimage"), dict) else {}
        if not pre.get("checkpoint_id"):
            errors.append(f"DIRTY_USER dest A10 preimage missing: {rev_after}")
        if not any("DIRTY_USER" in e for e in errors):
            dirty_l = "proven"

        un_repo = init_fixture("untrack1")
        (un_repo / "slice.gd").write_text("var ok := true\n", encoding="utf-8", newline="\n")
        (un_repo / "art.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"tiny-asset" * 8)
        req_id, uckpt = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "r7w3 untracked asset",
                "paths": ["res://r7w3/untrack1/slice.gd"],
                "repo": "r7w3/untrack1",
                "run_id": "untrack1",
                "project": "r7w3",
            },
        )
        u_after = after_of(uckpt)
        st = run_git(un_repo, ["status", "--porcelain", "--", "art.png"])
        if "art.png" in tracked_paths(un_repo) or blob_in_history(un_repo, "art.png"):
            errors.append("UNTRACKED_ASSET was silently committed")
        if "??" not in (st.stdout or "") and "art.png" not in (st.stdout or ""):
            errors.append(f"UNTRACKED_ASSET should stay untracked: {st.stdout!r}")
        if "art.png" not in (u_after.get("untracked_assets") or []) and "art.png" not in json.dumps(u_after):
            req_id, ust = tool_git(
                proc,
                req_id,
                "status",
                {
                    "detail": "short",
                    "repo": "r7w3/untrack1",
                    "run_id": "untrack1",
                    "allowlist": ["res://r7w3/untrack1/slice.gd"],
                },
            )
            ust_after = after_of(ust)
            assets = ust_after.get("untracked_assets") if isinstance(ust_after.get("untracked_assets"), list) else []
            if "r7w3/untrack1/art.png" not in assets and "art.png" not in json.dumps(ust_after):
                errors.append(f"UNTRACKED_ASSET missing from status: {ust_after}")
        if uckpt.get("ok") is True and not any("UNTRACKED_ASSET" in e for e in errors):
            untrack_l = "proven"

        c_repo = init_fixture("conflict")
        (c_repo / "shared.txt").write_text("base\n", encoding="utf-8", newline="\n")
        (c_repo / "slice.gd").write_text("var ok := true\n", encoding="utf-8", newline="\n")
        run_git(c_repo, ["add", "--", "shared.txt", "slice.gd"])
        run_git(c_repo, ["commit", "-m", "conflict base"])
        base_branch = (run_git(c_repo, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout or "master").strip()
        run_git(c_repo, ["checkout", "-b", "other"])
        (c_repo / "shared.txt").write_text("other\n", encoding="utf-8", newline="\n")
        run_git(c_repo, ["add", "--", "shared.txt"])
        run_git(c_repo, ["commit", "-m", "other side"])
        run_git(c_repo, ["checkout", base_branch])
        (c_repo / "shared.txt").write_text("main\n", encoding="utf-8", newline="\n")
        run_git(c_repo, ["add", "--", "shared.txt"])
        run_git(c_repo, ["commit", "-m", "main side"])
        merged = run_git(c_repo, ["merge", "other"])
        if merged.returncode == 0 and "CONFLICT" not in (merged.stdout or "") + (merged.stderr or ""):
            errors.append("CONFLICT fixture failed to create a merge conflict")
        req_id, blocked = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "must not be green",
                "paths": ["res://r7w3/conflict/slice.gd"],
                "repo": "r7w3/conflict",
                "run_id": "conflict",
                "project": "r7w3",
            },
        )
        if blocked.get("ok") is True:
            errors.append("CONFLICT stamped green done")
        if err_code(blocked) != "E_CONFLICT":
            errors.append(f"CONFLICT must be E_CONFLICT, got {blocked}")
        b_after = after_of(blocked)
        ack = b_after.get("pause_ack") if isinstance(b_after.get("pause_ack"), dict) else {}
        if b_after.get("paused") is not True or ack.get("paused") is not True:
            errors.append(f"CONFLICT must flip PauseGate, got {b_after}")
        if (c_repo / "slice.gd").read_text(encoding="utf-8") != "var ok := true\n":
            errors.append("CONFLICT mutated the allowlisted file")
        req_id, paused_mut = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "must be paused",
                "paths": ["res://r7w3/conflict/slice.gd"],
                "repo": "r7w3/conflict",
                "run_id": "conflict-paused",
                "project": "r7w3",
            },
        )
        if err_code(paused_mut) != "E_PAUSED":
            errors.append(f"CONFLICT follow-up mutate must be E_PAUSED, got {paused_mut}")
        req_id, resumed = pin.tool_call(proc, req_id, "godot.editor", "pause", {"op": "resume"})
        res_after = after_of(resumed)
        if resumed.get("ok") is not True or res_after.get("paused") is not False:
            errors.append(f"CONFLICT editor.pause resume failed: {resumed}")
        if (
            err_code(blocked) == "E_CONFLICT"
            and err_code(paused_mut) == "E_PAUSED"
            and resumed.get("ok") is True
            and not any(e.startswith("CONFLICT") for e in errors)
        ):
            conflict_l = "proven"

        big_repo = init_fixture("largebin")
        payload = b"\x89PNG\r\n\x1a\n" + os.urandom(LFS_THRESHOLD + 4096)
        (big_repo / "blob.png").write_bytes(payload)
        req_id, refused = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "must refuse raw blob",
                "paths": ["res://r7w3/largebin/blob.png"],
                "repo": "r7w3/largebin",
                "run_id": "largebin",
                "project": "r7w3",
            },
        )
        r_after = after_of(refused)
        if refused.get("ok") is True:
            errors.append("LARGE_BINARY accepted a raw blob commit")
        if r_after.get("lfs") is True:
            errors.append("LARGE_BINARY stamped lfs:true without a pointer")
        if "blob.png" in tracked_paths(big_repo) or blob_in_history(big_repo, "blob.png"):
            errors.append("LARGE_BINARY committed the raw blob")
        if err_code(refused) not in {"E_POLICY", "E_CHECKPOINT"}:
            errors.append(f"LARGE_BINARY must refuse honestly, got {refused}")
        if refused.get("ok") is not True and "blob.png" not in tracked_paths(big_repo):
            large_l = "proven"

        det_repo = init_fixture("detached")
        (det_repo / "slice.gd").write_text("var slice := 1\n", encoding="utf-8", newline="\n")
        (det_repo / "user_notes.txt").write_text("DETACH-USER\n", encoding="utf-8", newline="\n")
        req_id, dckpt = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "r7w3 detached slice",
                "paths": ["res://r7w3/detached/slice.gd"],
                "repo": "r7w3/detached",
                "run_id": "detached",
                "project": "r7w3",
            },
        )
        d_after = after_of(dckpt)
        d_commit = str(d_after.get("git_commit") or "")
        if dckpt.get("ok") is not True or d_after.get("git_real") is not True or len(d_commit) < 7:
            errors.append(f"DETACHED checkpoint failed: {dckpt}")
        detached = run_git(det_repo, ["checkout", "--detach"])
        if detached.returncode != 0:
            errors.append(f"DETACHED checkout --detach failed: {detached.stderr}")
        req_id, dst = tool_git(
            proc,
            req_id,
            "status",
            {"detail": "short", "repo": "r7w3/detached", "run_id": "detached"},
        )
        dst_after = after_of(dst)
        if dst_after.get("detached") is not True:
            errors.append(f"DETACHED status missed detached HEAD: {dst_after}")
        if str(dst_after.get("checkpoint_commit") or "") != d_commit and str(dst_after.get("checkpoint_id") or "") != str(
            d_after.get("checkpoint_id") or ""
        ):
            errors.append(f"DETACHED did not find checkpoint: {dst_after}")
        if not dst_after.get("checkpoint_id"):
            errors.append(f"DETACHED lost checkpoint id: {dst_after}")
        if dst_after.get("resume_ok") is True:
            errors.append(f"DETACHED claimed resume_ok while detached: {dst_after}")
        if dst_after.get("detached") is True and dst_after.get("checkpoint_id") and dst_after.get("resume_ok") is not True:
            detached_l = "proven" if not any("DETACHED" in e for e in errors) else "unproven"

        stop_sidecar(proc, desc_path)
        proc = None
        desc_path = None
        time.sleep(0.5)
        pin.kill_plugin_project_holders(godot=True, node=True)
        time.sleep(1.0)
        proc, desc_path, secret, err_lines = start_sidecar()
        req_id = 2
        req_id, rst = tool_git(
            proc,
            req_id,
            "status",
            {"detail": "short", "repo": "r7w3/detached", "run_id": "detached"},
        )
        rst_after = after_of(rst)
        if str(rst_after.get("checkpoint_commit") or "") != d_commit and str(rst_after.get("checkpoint_id") or "") != str(
            d_after.get("checkpoint_id") or ""
        ):
            errors.append(f"RESUME status lost checkpoint after restart: {rst_after}")
        req_id, resumed = tool_git(
            proc,
            req_id,
            "checkpoint",
            {
                "message": "resume after detach",
                "repo": "r7w3/detached",
                "run_id": "detached",
                "project": "r7w3",
                "resume": True,
            },
        )
        res_after = after_of(resumed)
        if resumed.get("ok") is not True or res_after.get("resume_ok") is not True:
            errors.append(f"RESUME reattach failed: {sess.redact(json.dumps(resumed), secret)}")
        head_br = (run_git(det_repo, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout or "").strip()
        if head_br != "agent/r7w3/detached":
            errors.append(f"RESUME left branch={head_br!r}")
        if (det_repo / "slice.gd").read_text(encoding="utf-8") != "var slice := 1\n":
            errors.append("RESUME lost the green slice")
        if "DETACH-USER" not in (det_repo / "user_notes.txt").read_text(encoding="utf-8"):
            errors.append("RESUME clobbered the dirty user file")
        if (
            resumed.get("ok") is True
            and head_br == "agent/r7w3/detached"
            and not any(e.startswith("RESUME") for e in errors)
        ):
            resume_l = "proven"

        if studio_head() != before_head:
            errors.append("official test mutated the studio monorepo HEAD")
        if studio_branch_exists("agent/r7w3/dirtyuser") or studio_branch_exists("agent/r7w3/detached"):
            errors.append("official test created an agent/* branch on the studio monorepo")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live git_checkpoint failed: {type(exc).__name__}: {exc}")
        if live != "sidecar":
            live = "failed"
    finally:
        stop_sidecar(proc, desc_path)
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        errors.extend(pin.project_godot_leak_errors("after live"))
    return errors, live, dirty_l, untrack_l, conflict_l, large_l, detached_l, resume_l


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    built = subprocess.run(
        [npm(), "run", "generate"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge generate failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    for verb in ("git.status", "git.diff", "git.checkpoint", "git.revert_checkpoint"):
        if verb not in actions:
            errors.append(f"actions.json missing {verb}")
    validator = BRIDGE / "generated" / "plugin-validator.json"
    vbody = json.loads(validator.read_text(encoding="utf-8")) if validator.is_file() else {}
    vactions = vbody.get("actions") if isinstance(vbody.get("actions"), dict) else {}
    ckpt_spec = vactions.get("git.checkpoint") if isinstance(vactions.get("git.checkpoint"), dict) else {}
    props = ((ckpt_spec.get("input_schema") or {}).get("properties") or {}) if isinstance(ckpt_spec, dict) else {}
    if "run_id" not in props or "repo" not in props:
        errors.append("git.checkpoint schema must include repo/run_id")

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    errors.extend(cleanup_temp())
    live = "unrun"
    dirty_l = untrack_l = conflict_l = large_l = detached_l = resume_l = "unproven"
    if not any("bridge generate failed" in e for e in errors):
        live_errs, live, dirty_l, untrack_l, conflict_l, large_l, detached_l, resume_l = live_errors()
        errors.extend(live_errs)

    if dirty_l != "proven":
        errors.append("DIRTY_USER not proven")
    if untrack_l != "proven":
        errors.append("UNTRACKED_ASSET not proven")
    if conflict_l != "proven":
        errors.append("CONFLICT not proven")
    if large_l != "proven":
        errors.append("LARGE_BINARY not proven")
    if detached_l != "proven":
        errors.append("DETACHED not proven")
    if resume_l != "proven":
        errors.append("RESUME not proven")
    if live not in {"sidecar", "plugin"}:
        errors.append("LIVE path through real git.checkpoint is required (src_scan is not enough)")

    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.5)
    errors.extend(cleanup_temp())
    banner = (
        f"LIVE={live}; DIRTY_USER={dirty_l}; UNTRACKED_ASSET={untrack_l}; "
        f"CONFLICT={conflict_l}; LARGE_BINARY={large_l}; DETACHED={detached_l}; RESUME={resume_l}"
    )
    if errors:
        print(f"FAIL: git_checkpoint; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: git_checkpoint; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
