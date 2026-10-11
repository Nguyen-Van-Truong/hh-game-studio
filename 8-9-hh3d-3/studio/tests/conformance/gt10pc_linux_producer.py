"""Host owner for the bounded offline Linux installed-artifact diagnostic."""
from __future__ import annotations
import inspect as inspect_module, json, os, re, shutil, uuid
from pathlib import Path

from studio.build.bootstrap.run_fixture import run_process
from studio.package.release_contract import _safe_member, digest_file, need, safe_path, strict_json, verify_package
from studio.package.trust import load_trust

STUDIO = Path(__file__).resolve().parents[2]
DOCKER = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")
CONTEXT = "desktop-linux"
IMAGE = "sha256:7e51d8b09fe7e3778402d55ca7bfd05a1a02cf4dbc4a7308b4a0b3cb607ae8e7"
BINARY = "Godot_v4.7.2-stable_linux.x86_64"

def export_public_evidence(output, destination):
    """Export bounded raw observations, never recurse into consumer/private state."""
    candidates = [output / "linux.json"]
    for fixture in ("gt09-arena", "gt09-room"):
        consumer = output / "consumer" / fixture
        candidates.extend(consumer / name for name in (
            "project-before.json", "project-before-play.json", "project-after-play.json",
            "project-after-uninstall.json", "project-after-reinstall.json",
            "native-phases.json", "install-state.json"))
        for phase in ("install", "upgrade", "rollback", "reinstall"):
            for domain, labels in (("drivers", ("driver",)), ("native", ("parse", "godot"))):
                folder = consumer / domain / phase
                candidates.append(folder / "receipt.json")
                candidates.extend(folder / (label + suffix) for label in labels
                                  for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
    for path in candidates:
        relative = path.relative_to(output)
        current = output
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Linux evidence path is a symlink")
        if path.is_file():
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Linux evidence file exceeds bound")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)

def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with safe_path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")

def _clean(row: dict) -> bool:
    return row.get("exit_code") == 0 and row.get("wrapper_exit_code") == 0 and row.get("tree_verified") is True and row.get("timed_out") is False

def _preflight(artifact: Path, trust: Path, trust_sha256: str, upgrade: Path | None) -> dict:
    need(os.name == "nt" and DOCKER.is_file(), "GT10PC_LINUX_WINDOWS_DOCKER_HOST_REQUIRED")
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target="Linux-headless", expected_version="0.1.0")
    lock = strict_json(package["members"]["payload/studio/godot-addon/validator-toolchain.lock.json"])
    need(lock.get("image_id") == IMAGE and lock.get("docker_context") == CONTEXT and lock.get("binary_name") == BINARY, "GT10PC_LINUX_TOOLCHAIN_LOCK")
    tool = safe_path(STUDIO / ".local/tooling/godot-4.7.2-stable-linux" / BINARY)
    need(digest_file(tool) == lock["binary_sha256"], "GT10PC_LINUX_GODOT_PIN")
    wheel_root = safe_path(STUDIO / ".local/gt10pc-linux-wheels")
    wheel_lock = strict_json((wheel_root / "wheel-lock.json").read_bytes())
    need(wheel_lock.get("schema") == "hh-gt10pc-linux-wheels-1" and wheel_lock.get("python") == "3.12" and isinstance(wheel_lock.get("files"), dict) and len(wheel_lock["files"]) == 3, "GT10PC_LINUX_WHEEL_LOCK")
    for name, row in wheel_lock["files"].items():
        _safe_member(name)
        path = wheel_root / name
        need(path.is_file() and digest_file(path) == row["sha256"] and path.stat().st_size == row["size"], "GT10PC_LINUX_WHEEL_BYTES")
    upgraded = None
    if upgrade is not None:
        upgraded = verify_package(upgrade, trusted_keys=keys, target="Linux-headless", expected_version="0.1.1")
        need(upgraded["manifest"]["source_closure_sha256"] == package["manifest"]["source_closure_sha256"], "GT10PC_LINUX_UPGRADE_CLOSURE")
    worker_hash = package["manifest"]["files"]["payload/studio/tests/conformance/gt10pc_linux_worker.py"]["sha256"]
    need(worker_hash == digest_file(Path(__file__).with_name("gt10pc_linux_worker.py")), "GT10PC_LINUX_WORKER_SOURCE_DRIFT")
    return {"package": package, "upgrade": upgraded, "lock": lock, "tool": tool, "wheel_root": wheel_root}

def dry_run(*, artifact: Path, trust: Path, trust_sha256: str, upgrade_artifact: Path | None = None) -> dict:
    frozen = _preflight(safe_path(artifact), safe_path(trust), trust_sha256, None if upgrade_artifact is None else safe_path(upgrade_artifact))
    return {"schema": "hh-gt10pc-linux-plan-1", "authority": 0, "acceptance": False, "target": "Linux-headless", "image_id": IMAGE, "network": "none", "cpus": 12, "artifact_sha256": frozen["package"]["archive_sha256"], "source_closure_sha256": frozen["package"]["manifest"]["source_closure_sha256"]}

def run_linux(output: Path, *, artifact: Path, trust: Path, trust_sha256: str, upgrade_artifact: Path | None = None) -> dict:
    artifact, trust, output = safe_path(artifact), safe_path(trust), safe_path(output)
    upgrade_artifact = None if upgrade_artifact is None else safe_path(upgrade_artifact)
    frozen = _preflight(artifact, trust, trust_sha256, upgrade_artifact)
    need(not output.exists(), "GT10PC_LINUX_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    host = output / "host"
    host.mkdir()
    scratch = safe_path(Path(STUDIO.anchor) / ("hh-g10-" + uuid.uuid4().hex))
    scratch.mkdir()
    inputs, raw = scratch / "input", scratch / "evidence"
    inputs.mkdir(); raw.mkdir()
    package, upgraded, lock = frozen["package"], frozen["upgrade"], frozen["lock"]
    shutil.copyfile(artifact, inputs / "release.hhpkg")
    if upgrade_artifact is not None:
        shutil.copyfile(upgrade_artifact, inputs / "upgrade.hhpkg")
    shutil.copyfile(trust, inputs / "trust.json")
    shutil.copytree(frozen["wheel_root"], inputs / "wheels")
    worker = package["manifest"]["files"]["payload/studio/tests/conformance/gt10pc_linux_worker.py"]["sha256"]
    bootstrap = """import hashlib,json,os,pathlib,runpy,shutil,subprocess,sys,zipfile
source=pathlib.Path('/input')
request=json.loads((source/'request.json').read_bytes())
if sys.version_info[:2] != (3,12): raise RuntimeError('Linux Python pin mismatch')
def sha(path):
  with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
if sha(source/'release.hhpkg') != request['artifact_sha256']: raise RuntimeError('Linux artifact changed')
if sha(source/'trust.json') != request['trust_sha256']: raise RuntimeError('Linux trust changed')
if sha(source/'wheels/wheel-lock.json') != request['wheel_lock_sha256']: raise RuntimeError('Linux wheel lock changed')
lock=json.loads((source/'wheels/wheel-lock.json').read_bytes())
wheels=[]
for name,row in lock['files'].items():
  path=source/'wheels'/name
  if '/' in name or '\\\\' in name or sha(path) != row['sha256'] or path.stat().st_size != row['size']: raise RuntimeError('Linux wheel pin mismatch')
  wheels.append(str(path))
subprocess.run([sys.executable,'-B','-m','pip','install','--no-index','--no-deps','--no-cache-dir','--no-compile','--disable-pip-version-check','--target','/tmp/deps',*wheels],check=True)
sys.path.insert(0,'/tmp/deps')
base=pathlib.Path('/tmp/bootstrap')
with zipfile.ZipFile(source/'release.hhpkg') as archive:
  for name in archive.namelist():
    if not name.startswith('payload/studio/'): continue
    rel=pathlib.PurePosixPath(name[len('payload/'):])
    if rel.is_absolute() or any(part in ('','..','.') for part in rel.parts): raise RuntimeError('unsafe package member')
    target=base/rel; target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream: stream.write(archive.read(name))
worker=base/'studio/tests/conformance/gt10pc_linux_worker.py'
if sha(worker) != request['worker_sha256']: raise RuntimeError('Linux worker changed')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['PIP_NO_INDEX']='1'
os.environ['PIP_NO_CACHE_DIR']='1'
os.environ['HOME']='/tmp'
os.environ['XDG_CACHE_HOME']='/tmp/cache'
os.environ['PIP_CACHE_DIR']='/tmp/pip-cache'
pathlib.Path('/tmp/pip-cache').mkdir(parents=True,exist_ok=True)
__EXPORT_FUNCTION__
try:
  runpy.run_path(str(worker),run_name='__main__')
finally:
  # Export only raw observations, including on failure. Releases, caches and
  # private owner state stay in Linux tmpfs and are never evidence inputs.
  export_public_evidence(pathlib.Path('/output'), pathlib.Path('/evidence'))
"""
    bootstrap = bootstrap.replace("__EXPORT_FUNCTION__", inspect_module.getsource(export_public_evidence))
    compile(bootstrap, "gt10pc-linux-bootstrap", "exec")
    (inputs / "bootstrap.py").write_text(bootstrap, encoding="utf-8", newline="\n")
    request = {"schema": "hh-gt10pc-linux-request-1", "trust_sha256": trust_sha256, "artifact_sha256": package["archive_sha256"], "manifest_sha256": package["manifest_sha256"], "source_closure_sha256": package["manifest"]["source_closure_sha256"], "upgrade_artifact_sha256": None if upgraded is None else upgraded["archive_sha256"], "upgrade_manifest_sha256": None if upgraded is None else upgraded["manifest_sha256"], "wheel_lock_sha256": digest_file(inputs / "wheels/wheel-lock.json"), "binary_name": lock["binary_name"], "binary_sha256": lock["binary_sha256"], "worker_sha256": worker}
    _write(inputs / "request.json", request)
    for name in ("request.json", "bootstrap.py", "wheels/wheel-lock.json"):
        target = output / "input" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inputs / name, target)
    name = "hh-gt10pc-linux-" + uuid.uuid4().hex
    rows, inspected, container_id, removed = {}, {}, None, False

    def cli(args: list[str], label: str, timeout: int = 40):
        row = run_process([str(DOCKER), "--context", CONTEXT, *args], cwd=STUDIO, output=host, timeout=timeout, label=label)
        rows[label] = row
        _write(host / (label + "-receipt.json"), row)
        return row, (host / row["stdout"]).read_bytes()

    def inspect(label: str) -> dict:
        row, raw_json = cli(["inspect", container_id], label)
        need(_clean(row), "GT10PC_LINUX_INSPECT_EXIT")
        value = strict_json(raw_json)
        need(isinstance(value, list) and len(value) == 1, "GT10PC_LINUX_INSPECT_SHAPE")
        doc = value[0]
        need(doc.get("Id") == container_id and doc.get("Name") == "/" + name and doc.get("Image") == IMAGE and doc.get("Config", {}).get("Labels", {}).get("hh.gt10pc.owner") == name, "GT10PC_LINUX_OWNER_IDENTITY")
        inspected[label] = doc
        return doc

    error = None
    try:
        row, image_raw = cli(["image", "inspect", IMAGE], "image")
        images = strict_json(image_raw)
        need(_clean(row) and isinstance(images, list) and len(images) == 1 and images[0].get("Id") == IMAGE and images[0].get("Os") == "linux" and images[0].get("Architecture") == "amd64", "GT10PC_LINUX_PINNED_IMAGE_MISSING")
        create = ["create", "--pull=never", "--name", name, "--label", "hh.gt10pc.owner=" + name, "--platform", "linux/amd64", "--read-only", "--network", "none", "--ipc", "private", "--cgroupns", "private", "--user", "65532:65532", "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true", "--security-opt", "seccomp=builtin", "--memory", "1g", "--memory-swap", "1g", "--cpus", "12", "--pids-limit", "64", "--log-driver", "none", "--restart", "no", "--no-healthcheck", "--stop-timeout", "2", "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=768m,mode=1777", "--workdir", "/output", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PIP_NO_INDEX=1", "--env", "PIP_NO_CACHE_DIR=1", "--env", "PIP_DISABLE_PIP_VERSION_CHECK=1"]
        create += ["--tmpfs", "/output:rw,nosuid,nodev,exec,size=512m,mode=1777"]
        for folder, destination, readonly in ((inputs, "/input", True), (raw, "/evidence", False)):
            create += ["--mount", "type=bind,src=" + str(folder) + ",dst=" + destination + (",readonly" if readonly else "") + ",bind-propagation=rprivate"]
        create += ["--entrypoint", "/usr/local/bin/python3", IMAGE, "-B", "/input/bootstrap.py"]
        row, stdout = cli(create, "create")
        need(_clean(row), "GT10PC_LINUX_CREATE_EXIT")
        container_id = stdout.decode("ascii").strip()
        need(re.fullmatch(r"[0-9a-f]{64}", container_id), "GT10PC_LINUX_CONTAINER_ID")
        created = inspect("inspect-created")
        config = created["HostConfig"]
        need(config.get("NetworkMode") == "none" and config.get("ReadonlyRootfs") is True and config.get("CapDrop") == ["ALL"] and config.get("Privileged") is False and config.get("Memory") == 1073741824 and config.get("MemorySwap") == 1073741824 and config.get("NanoCpus") == 12000000000 and config.get("PidsLimit") == 64 and set(config.get("SecurityOpt", [])) == {"no-new-privileges=true", "seccomp=builtin"}, "GT10PC_LINUX_CONFINEMENT")
        mounts = created.get("Mounts", [])
        need(len(mounts) == 2 and {m.get("Destination"): m.get("RW") for m in mounts} == {"/input": False, "/evidence": True}, "GT10PC_LINUX_MOUNTS")
        row, _ = cli(["start", "--attach", container_id], "run", timeout=590)
        ended = inspect("inspect-exited")
        state = ended["State"]
        need(_clean(row) and state.get("Status") == "exited" and state.get("Running") is False and state.get("ExitCode") == 0 and state.get("OOMKilled") is False and not state.get("Error"), "GT10PC_LINUX_CONTAINER_EXIT")
        need(not (host / "run-stderr.txt").read_bytes(), "GT10PC_LINUX_CONTAINER_STDERR")
        native = strict_json((raw / "linux.json").read_bytes())
        need(native.get("artifact_sha256") == package["archive_sha256"] and native.get("manifest_sha256") == package["manifest_sha256"] and native.get("source_closure_sha256") == package["manifest"]["source_closure_sha256"], "GT10PC_LINUX_NATIVE_BINDING")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        if container_id is not None:
            current = inspect("inspect-closeout")
            if current["State"].get("Running"):
                row, _ = cli(["kill", container_id], "kill")
                need(_clean(row), "GT10PC_LINUX_KILL_EXIT")
                inspect("inspect-killed")
            row, _ = cli(["rm", container_id], "remove")
            need(_clean(row), "GT10PC_LINUX_REMOVE_EXIT")
            row, left = cli(["ps", "--all", "--filter", "label=hh.gt10pc.owner=" + name, "--format", "{{.ID}}"], "leftover")
            removed = _clean(row) and not left.strip()
            need(removed, "GT10PC_LINUX_LEFTOVER")

    for directory, dirs, files in os.walk(raw):
        for filename in files:
            source = safe_path(Path(directory) / filename)
            relative = source.relative_to(raw)
            _safe_member(relative.as_posix())
            target = output / "native" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    evidence = {p.relative_to(output).as_posix(): digest_file(p) for p in output.rglob("*") if p.is_file()}
    receipt = {"schema": "hh-gt10pc-linux-producer-1", "authority": 0, "acceptance": False, "mode": "DIAGNOSTIC", "target": "Linux-headless", "status": "DIAGNOSTIC_PASS" if error is None else "DIAGNOSTIC_FAIL", "error": error, "run_id": name, "container_id": container_id, "image_id": IMAGE, "context": CONTEXT, "artifact_sha256": package["archive_sha256"], "manifest_sha256": package["manifest_sha256"], "source_closure_sha256": package["manifest"]["source_closure_sha256"], "trust_sha256": trust_sha256, "upgrade_artifact_sha256": request["upgrade_artifact_sha256"], "upgrade_manifest_sha256": request["upgrade_manifest_sha256"], "wheel_lock_sha256": request["wheel_lock_sha256"], "processes": rows, "inspections": inspected, "owned_removed": removed, "evidence": evidence, "native": "native/linux.json" if (output / "native/linux.json").is_file() else None}
    _write(output / "producer.json", receipt)
    need(error is None, "GT10PC_LINUX_DIAGNOSTIC_FAILED:" + str(error))
    return receipt

