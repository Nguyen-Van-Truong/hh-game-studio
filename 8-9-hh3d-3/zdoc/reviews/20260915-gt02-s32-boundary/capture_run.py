"""Capture one fresh bounded diagnostic; never overwrite a previous run."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

base = Path(__file__).resolve().parent
source = base / "boundary_probe.py"
run_id = re.search(r'^RUN_ID = "([A-Z0-9-]+)"$', source.read_text(), re.M).group(1)
stem = "run-" + run_id.rsplit("-", 1)[1]
paths = [base / (stem + suffix) for suffix in (".stdout.json", ".stderr.txt", ".host.json")]
if any(path.exists() for path in paths):
    raise SystemExit("Run already captured; choose a fresh source/run ID")
host = {"run_id": run_id, "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python -B boundary_probe.py", "timeout_seconds": 120,
        "probe_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "timed_out": False}
try:
    result = subprocess.run([sys.executable, "-B", str(source)], cwd=base, capture_output=True, timeout=120)
    stdout, stderr = result.stdout, result.stderr
    host["host_exit"] = result.returncode
except subprocess.TimeoutExpired as exc:
    stdout, stderr = exc.stdout or b"", exc.stderr or b""
    host.update(host_exit=None, timed_out=True, cleanup="UNCONFIRMED_AFTER_PROBE_TIMEOUT")
for path, raw in zip(paths, (stdout, stderr)):
    with path.open("xb") as stream:
        stream.write(raw)
host["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
host["stdout_sha256"], host["stderr_sha256"] = [hashlib.sha256(raw).hexdigest() for raw in (stdout, stderr)]
with paths[2].open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(host, indent=2) + "\n")
print(json.dumps(host))
sys.exit(0 if host["host_exit"] == 0 and not host["timed_out"] else 1)
